"""全书知识图谱生产流水线编排。

放置位置: backend/src/core/knowledge_qa/d2g/book_pipeline.py

端到端流程:
  Phase 0 → Phase 1（逐章） → Phase 2（逐章审核） → Phase 3（质量检查） → Phase 4（入库）
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Callable, Optional, Protocol

from .book_reader import deep_book_reading, validate_book_context
from .global_relation_inference import run_global_relation_inference
from src.core.knowledge_qa.neo4j.chapter_parser import Chapter, ChapterParseResult
from .chapter_extractor import extract_chapter
from .entity_resolver import resolve_and_merge
from .graph_committer import commit_to_neo4j
from .graph_quality import audit_graph_quality, generate_quality_report
from .long_chapter import split_paragraphs
from .master_graph import MasterGraph
from .models import BookContext, ChapterExtraction, ModelConfig, PipelineConfig, QualityThresholds
from .review_md_generator import generate_review_md

logger = logging.getLogger(__name__)

# ── 非内容章节过滤 ─────────────────────────────────────────
# 匹配到这些标题的章节跳过提取（参考文献、目录、致谢等）
# 仅匹配独立标题或以这些词开头/结尾的标题，避免误杀正文章节
_NON_CONTENT_PATTERNS: list[str] = [
    "参考文献", "目录", "致谢", "前言", "后记", "附录", "索引",
    "版权页", "版权信息", "封面", "扉页", "跋", "序言", "序", "声明",
    "内容简介", "作者简介", "译者简介", "出版信息",
    "写在前面", "写在后面", "编写说明", "凡例",
    # 英文
    "references", "bibliography", "table of contents", "contents",
    "acknowledgment", "acknowledgement", "acknowledgements",
    "foreword", "preface", "appendix", "index", "abstract",
    "copyright", "about the author",
    # 电子书平台水印
    "读累了记得休息一会哦~",
]


def _is_non_content_chapter(title: str) -> bool:
    """判断章节标题是否为非内容章节（参考文献/目录/致谢等）。"""
    t = title.strip().lower()
    # 去掉常见前缀如 "第X章"、数字编号
    t_clean = re.sub(r'^第[一二三四五六七八九十百千\d]+章\s*', '', t)
    t_clean = re.sub(r'^[\d.]+\s*', '', t_clean).strip()
    for pat in _NON_CONTENT_PATTERNS:
        if t_clean == pat or t_clean.startswith(pat) or t_clean.endswith(pat):
            return True
    return False


def _is_toc_chapter(title: str) -> bool:
    """判断章节标题是否为目录。"""
    t = title.strip().lower()
    t_clean = re.sub(r'^[\d.]+\s*', '', t).strip()
    return t_clean in ("目录", "table of contents", "contents")


def _is_first_content_chapter(title: str) -> bool:
    """判断章节是否为正文第一章（如 '第一章...', '01 xxx'）。"""
    t = title.strip()
    return bool(re.match(
        r'^(第[一二三四五六七八九十百千\d]+章|\d{1,2}\s|\d{1,2}[^\d])', t,
    ))


def _is_acknowledgment_chapter(title: str) -> bool:
    """判断章节标题是否为致谢。"""
    t = title.strip().lower()
    t_clean = re.sub(r'^[\d.]+\s*', '', t).strip()
    return t_clean in ("致谢", "acknowledgment", "acknowledgement", "acknowledgements")


def _get_non_content_chapter_ids(chapters: list) -> set[str]:
    """返回所有非内容章节的 ID 集合（目录前 + 致谢后）。

    过滤策略（按优先级）:
    1. 目录之前的章节全部跳过（含目录本身）
    2. 若无目录，跳到第一个"第X章"或"NN标题"正文章节之前的所有章节
    3. 致谢及其之后的章节全部跳过
    """
    skip_ids: set[str] = set()

    # ── 前端：找到正文起点 ──
    toc_idx = None
    first_content_idx = None
    for i, ch in enumerate(chapters):
        if _is_toc_chapter(ch.title) and toc_idx is None:
            toc_idx = i
        if _is_first_content_chapter(ch.title) and first_content_idx is None:
            first_content_idx = i

    # 以目录位置为准（若有），否则用第一章位置
    cutoff_start = toc_idx if toc_idx is not None else first_content_idx
    if cutoff_start is not None:
        # 跳过目录及其之前的所有章节（含目录本身）
        for ch in chapters[:cutoff_start + (1 if toc_idx is not None else 0)]:
            skip_ids.add(ch.id)

    # ── 尾端：致谢之后全部跳过 ──
    ack_idx = None
    for i, ch in enumerate(chapters):
        if _is_acknowledgment_chapter(ch.title):
            ack_idx = i
            break  # 取第一个致谢
    if ack_idx is not None:
        for ch in chapters[ack_idx:]:
            skip_ids.add(ch.id)

    return skip_ids


class LLMClient(Protocol):
    async def generate_structured(self, prompt: str, schema: type, model: str) -> dict | list: ...


class EmbeddingClient(Protocol):
    async def embed(self, texts: str | list[str]) -> list[list[float]]: ...


class RedisClient(Protocol):
    async def set(self, key: str, value: str, ex: int | None = None) -> None: ...
    async def get(self, key: str) -> str | None: ...
    async def delete(self, key: str) -> None: ...


# ──────────────────────────────────────────────────────────────
# 流水线状态
# ──────────────────────────────────────────────────────────────


class PipelineState:
    """流水线运行状态。"""

    def __init__(self, book_id: str, book_title: str):
        self.book_id = book_id
        self.book_title = book_title
        self.book_context: BookContext | None = None
        self.master_graph = MasterGraph(book_id=book_id, book_title=book_title)
        self.chapter_extractions: dict[str, ChapterExtraction] = {}
        self.review_mds: dict[str, str] = {}  # chapter_id → review MD
        self.approved_chapters: set[str] = set()
        self.non_content_chapters: set[str] = set()  # 跳过的非内容章节 ID
        self.staging_extractions: dict[str, ChapterExtraction] = {}  # Phase 1 暂存
        self.chapter_texts: dict[str, str] = {}  # chapter_id → markdown 原文
        self.staging_entities: list[dict] = []  # 供 LLM 跨章上下文
        self.merge_map: dict[str, str] = {}  # 消歧合并映射 {alias: representative}
        self.merge_log: list[dict] = []  # 消歧合并日志
        self.current_phase: str = "pending"
        self.errors: list[str] = []

    @property
    def progress(self) -> dict:
        approved_list = list(self.approved_chapters)
        # Phase 1 用 staging_extractions 计数，Phase 2+ 用 chapter_extractions
        total = len(self.chapter_extractions) or len(self.staging_extractions)
        non_content = len(self.non_content_chapters)
        return {
            "phase": self.current_phase,
            "total_chapters": total,
            "content_chapters": total - non_content,
            "approved_chapters": approved_list,
            "approved_count": len(approved_list),
            "chapter_extractions": dict(self.chapter_extractions),
            "staging_extractions": {k: True for k in self.staging_extractions},
            "non_content_chapters": list(self.non_content_chapters),
            "errors": self.errors,
        }


# ──────────────────────────────────────────────────────────────
# 公开 API
# ──────────────────────────────────────────────────────────────


async def run_full_pipeline(
    parse_result: ChapterParseResult,
    llm_client: LLMClient,
    embedding_client: EmbeddingClient,
    redis_client: RedisClient | None = None,
    neo4j_session=None,
    config: PipelineConfig | None = None,
    on_progress: Callable[[dict], None] | None = None,
    on_review_needed: Callable[[str, str], None] | None = None,
) -> PipelineState:
    """运行完整的 D2G 流水线。

    Args:
        parse_result: EPUB 解析结果
        llm_client: LLM 客户端
        embedding_client: embedding 客户端
        redis_client: Redis 客户端（可选，用于主图持久化）
        neo4j_session: Neo4j session（可选，Phase 4 入库用）
        config: 流水线配置
        on_progress: 进度回调
        on_review_needed: 审核回调 (chapter_id, review_md) → None

    Returns:
        PipelineState 最终状态
    """
    if config is None:
        config = PipelineConfig()

    state = PipelineState(
        book_id=parse_result.book_id,
        book_title=parse_result.book_title,
    )

    # ─── Phase 0: 全书深度阅读 ───
    state.current_phase = "phase0_reading"
    if on_progress:
        on_progress(state.progress)

    logger.info("Phase 0: 全书深度阅读 '%s'", parse_result.book_title)

    def _phase0_progress(p: dict):
        if on_progress:
            on_progress({**state.progress, **p})

    state.book_context = await deep_book_reading(
        parse_result=parse_result,
        llm_client=llm_client,
        model=config.models.context,
        on_progress=_phase0_progress,
    )
    logger.info("Phase 0 完成: 主旨=%s", state.book_context.core_thesis[:50])

    # Phase 0 自校验（§07-8.1）
    validation = await validate_book_context(
        book_context=state.book_context,
        segment_analyses=state.book_context.key_arguments or [],
    )
    if not validation["validation_passed"]:
        logger.warning(
            "Phase 0 自校验未通过: issues=%s, term_overlap=%.1f%%",
            validation["issues"],
            validation["term_overlap_rate"] * 100,
        )
        # 不阻塞流水线，但记录告警

    # ─── Phase 1 + 2: 逐章提取 + 审核 ───
    state.current_phase = "phase1_extraction"
    if on_progress:
        on_progress(state.progress)

    chapters = parse_result.chapters
    # 过滤非内容章节（参考文献、目录、致谢等 + 目录前/致谢后）
    auto_skip_ids = _get_non_content_chapter_ids(chapters)
    skipped: list[str] = []
    content_chapters: list[Chapter] = []
    for ch in chapters:
        if _is_non_content_chapter(ch.title) or ch.id in auto_skip_ids:
            skipped.append(ch.title)
            state.non_content_chapters.add(ch.id)
            # 创建空提取结果，保留在 state 中但不调用 LLM
            state.chapter_extractions[ch.id] = ChapterExtraction(
                chapter_id=ch.id, chapter_title=ch.title,
            )
            state.approved_chapters.add(ch.id)
        else:
            content_chapters.append(ch)
    if skipped:
        logger.info("跳过非内容章节 (%d 章): %s", len(skipped), ", ".join(skipped))
    concurrency = config.concurrency
    logger.info("Phase 1: 开始提取，共 %d 章 (并发=%d)", len(content_chapters), concurrency)

    # 并行提取：所有章节共享同一份 staging_entities 快照作为上下文
    # 互不影响，提取完成后再统一合入
    semaphore = asyncio.Semaphore(concurrency)
    completed_count = 0

    async def _extract_one(ch: Chapter) -> tuple[str, ChapterExtraction]:
        nonlocal completed_count
        async with semaphore:
            extraction = await extract_chapter(
                chapter=ch,
                book_context=state.book_context,
                existing_entities=state.staging_entities,
                llm_client=llm_client,
                config=config.models,
                long_chapter_threshold=config.long_chapter_threshold,
            )
            # 立即更新 staging（不等 gather），让 on_progress 能感知
            state.staging_extractions[ch.id] = extraction
            state.chapter_texts[ch.id] = ch.markdown
            completed_count += 1
            logger.info(
                "Phase 1 进度: [%d/%d] 章节 '%s' 完成 (%d 实体, %d 关系)",
                completed_count, len(content_chapters), ch.title,
                len(extraction.entities), len(extraction.relationships),
            )
            if on_progress:
                on_progress(state.progress)
            return ch.id, extraction

    # 并发提交所有章节
    tasks = [_extract_one(ch) for ch in content_chapters]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 收集结果，处理异常 + 累积 staging 实体
    for result in results:
        if isinstance(result, Exception):
            logger.error("章节提取异常: %s", result)
            continue
        ch_id, extraction = result
        # staging_extractions 和 chapter_texts 已在 _extract_one 中更新
        # 这里只累积 staging 实体（供全局消歧用）
        for entity in extraction.entities:
            state.staging_entities.append({
                "name": entity.name,
                "entity_type": entity.entity_type,
                "description": entity.description,
                "source_chapter": ch_id,
            })

    logger.info("Phase 1 全部完成，共 %d 章已提取", len(state.staging_extractions))

    # ─── Phase 2: 逐章审核 + 合入主图 ───
    # 全局消歧后入主图
    logger.info("Phase 1 全部完成，共 %d 章已提取", len(state.staging_extractions))
    if on_review_needed is None:
        from .entity_resolver import batch_resolve_entities

        logger.info("无审核回调，执行全局消歧")
        state.current_phase = "phase2_resolution"
        if on_progress:
            on_progress(state.progress)

        merge_map, merge_log = await batch_resolve_entities(
            staging_extractions=state.staging_extractions,
            master=state.master_graph,
            embedding_client=embedding_client,
            llm_client=llm_client,
            model=config.models.resolution,
            similarity_threshold=config.entity_similarity_threshold,
        )
        state.merge_map = merge_map
        state.merge_log = merge_log
        logger.info("Phase 2 消歧完成: %d 次合并", len(merge_log))

        # 标记所有章节为已审核，填充 chapter_extractions
        for ch_id in state.staging_extractions:
            state.approved_chapters.add(ch_id)
            state.chapter_extractions[ch_id] = state.staging_extractions[ch_id]

        # 生成审核 MD（消歧后）
        for ch_id, extraction in state.chapter_extractions.items():
            if ch_id in state.non_content_chapters:
                continue
            review_md = generate_review_md(extraction, state.master_graph)
            state.review_mds[ch_id] = review_md

        # 追加消歧合并记录到第一个内容章节的审核 MD
        if state.merge_log:
            from .review_md_generator import generate_merge_log_section
            merge_section = generate_merge_log_section(state.merge_log)
            first_content = next(
                (cid for cid in state.chapter_extractions
                 if cid not in state.non_content_chapters),
                None,
            )
            if first_content and first_content in state.review_mds:
                state.review_mds[first_content] += "\n" + merge_section

        if on_progress:
            on_progress(state.progress)

    return state


def _detect_heading_para_ids(chapter_text: str) -> set[int]:
    """识别 Markdown 小节标题段落的编号（1-based）。

    标题段落 = 以 # 开头的行。这些段落不含可提取实体，
    不应计入覆盖率的"未覆盖"。
    """
    paragraphs = split_paragraphs(chapter_text)
    heading_ids: set[int] = set()
    for i, p in enumerate(paragraphs):
        if p.lstrip().startswith("#"):
            heading_ids.add(i + 1)  # 1-based
    return heading_ids

async def approve_chapter(
    state: PipelineState,
    chapter_id: str,
    llm_client: LLMClient,
    embedding_client: EmbeddingClient,
    config: PipelineConfig,
    redis_client: RedisClient | None = None,
) -> None:
    """审核通过一章，执行实体消歧并合入主图。

    在人工审核流程中，前端审核通过后调用此方法。
    """
    extraction = state.chapter_extractions.get(chapter_id)
    if not extraction:
        raise ValueError(f"章节 {chapter_id} 未找到提取结果")

    logger.info("Phase 2: 审核通过 '%s'，开始实体消歧", extraction.chapter_title)

    # 实体消歧 + 合入主图
    para_count = extraction.para_count or max(
        (pid for e in extraction.entities for pid in e.source_para_ids),
        default=0,
    )
    state.master_graph.chapter_para_count[chapter_id] = para_count

    # 注册标题段落（不参与覆盖率计算）
    ch_text = state.chapter_texts.get(chapter_id, "")
    if ch_text:
        heading_ids = _detect_heading_para_ids(ch_text)
        if heading_ids:
            state.master_graph.register_heading_paras(chapter_id, heading_ids)

    # 先做实体消歧
    await resolve_and_merge(
        new_entities=extraction.entities,
        chapter_id=chapter_id,
        master=state.master_graph,
        embedding_client=embedding_client,
        llm_client=llm_client,
        model=config.models.resolution,
        similarity_threshold=config.entity_similarity_threshold,
    )

    # 添加关系
    for rel in extraction.relationships:
        state.master_graph.add_relationship(rel, chapter_id)

    state.approved_chapters.add(chapter_id)

    # 持久化到 Redis
    if redis_client:
        await redis_client.set(
            f"master_graph:{state.book_id}",
            state.master_graph.to_json(),
            ex=86400,  # 24 小时过期
        )

    logger.info(
        "章节 '%s' 已入图: %d 实体, %d 关系",
        extraction.chapter_title,
        state.master_graph.graph.number_of_nodes(),
        state.master_graph.graph.number_of_edges(),
    )


# ──────────────────────────────────────────────────────────────
# Gap fill: 段落覆盖度补全
# ──────────────────────────────────────────────────────────────


def _find_uncovered_paragraphs(state: PipelineState) -> dict[str, list[int]]:
    """找出每个章节中未被任何实体/关系覆盖的段落。

    Returns:
        {chapter_id: [未覆盖的段落编号列表]}
    """
    master = state.master_graph
    uncovered: dict[str, list[int]] = {}

    for ch_id, total in master.chapter_para_count.items():
        if ch_id in state.non_content_chapters:
            continue
        covered = master.para_coverage.get(ch_id, set())
        missing = [pid for pid in range(1, total + 1) if pid not in covered]
        if missing:
            uncovered[ch_id] = missing

    return uncovered


async def _fill_coverage_gaps(
    state: PipelineState,
    uncovered: dict[str, list[int]],
    llm_client,
    embedding_client,
) -> None:
    """对未覆盖段落做定向提取补全（并行）。"""

    from .models import ExtractedEntity, ExtractedRelationship

    GAP_FILL_PROMPT = """你是知识图谱提取专家。以下是书籍章节的部分段落，这些段落在之前的提取中未被覆盖。

## 章节标题
{chapter_title}

## 未覆盖段落（带段落编号）
{paragraphs}

## 已有实体列表（供参考，避免重复）
{existing_entities}

## 任务
从以上段落中提取：
1. **实体**：关键概念、理论、方法、脑区、问题、策略、人名(Person)、地名(Location)、物品/工具(Object)、评估工具(AssessmentTool)、症状(Symptom)、干预方案(Intervention)、诊断(Diagnosis)、组织机构(Organization)、研究(Study)、神经递质(Neurotransmitter)、发展里程碑(Milestone)、环境/场景(Environment)等
2. **实体之间的关系**：因果、治疗/干预、结构/组成、功能/参与、证据/研究、时间/发展、评估/诊断、空间/归属、层级/分类、发布/创作、属性/关联等

注意：
- 每个实体必须标注 source_para_ids（来自哪些段落）和 entity_type
- 优先提取段落中明确提到的概念和关系
- 不要重复已有实体"""

    async def _fill_one(ch_id: str, para_ids: list[int]) -> int:
        """补全一个章节的未覆盖段落，返回新增实体数。"""
        chapter_text = state.chapter_texts.get(ch_id, "")
        if not chapter_text or not para_ids:
            return 0

        paragraphs = split_paragraphs(chapter_text)
        gap_texts = []
        for pid in para_ids:
            if 0 < pid <= len(paragraphs):
                gap_texts.append(f"[P{pid}] {paragraphs[pid - 1]}")

        if not gap_texts:
            return 0

        gap_content = "\n\n".join(gap_texts[:50])
        existing = [
            name for name in state.master_graph.chapter_entities.get(ch_id, [])
        ]
        existing_str = ", ".join(existing[:50]) if existing else "无"

        logger.info("Gap fill: 章节 '%s' %d 个未覆盖段落", ch_id, len(para_ids))

        try:
            result = await llm_client.generate_structured(
                prompt=GAP_FILL_PROMPT.format(
                    chapter_title=state.chapter_extractions.get(ch_id, ChapterExtraction(
                        chapter_id=ch_id, chapter_title=ch_id,
                    )).chapter_title,
                    paragraphs=gap_content,
                    existing_entities=existing_str,
                ),
                schema=dict,
                model="qwen-plus",
            )

            if not result:
                return 0

            entities = result.get("entities", [])
            relationships = result.get("relationships", [])

            added_entities = 0
            for e in entities:
                if isinstance(e, dict) and e.get("name"):
                    entity = ExtractedEntity(
                        name=e["name"],
                        entity_type=e.get("entity_type", "AutoEntity"),
                        description=e.get("description", ""),
                        source_para_ids=e.get("source_para_ids", []),
                    )
                    state.master_graph.add_entity(entity, ch_id)
                    added_entities += 1

            added_rels = 0
            for r in relationships:
                if isinstance(r, dict) and r.get("source") and r.get("target"):
                    rel = ExtractedRelationship(
                        source=r["source"],
                        target=r["target"],
                        relation_type=r.get("relation_type", "RELATES_TO"),
                        evidence=r.get("evidence", "gap fill 补全"),
                        source_para_ids=r.get("source_para_ids", []),
                        relation_source="llm_coverage_fix",
                        confidence=0.6,
                    )
                    state.master_graph.add_relationship(rel, ch_id)
                    added_rels += 1

            logger.info(
                "Gap fill: 章节 '%s' 新增 %d 实体, %d 关系",
                ch_id, added_entities, added_rels,
            )
            return added_entities

        except Exception as e:
            logger.warning("Gap fill 章节 '%s' 失败: %s", ch_id, e)
            return 0

    # 并行补全所有未覆盖章节
    tasks = [
        _fill_one(ch_id, para_ids)
        for ch_id, para_ids in uncovered.items()
    ]
    results = await asyncio.gather(*tasks)
    total_added = sum(r for r in results if r)
    logger.info("Gap fill: 并行补全完成，%d 个章节共新增 %d 个实体", len(tasks), total_added)


async def finalize_and_commit(
    state: PipelineState,
    neo4j_session,
    thresholds: QualityThresholds | None = None,
    redis_client: RedisClient | None = None,
    embedding_client=None,
    llm_client=None,
) -> tuple[bool, str]:
    """Phase 2.5 + 3 + 4: 全局关系补全 + 质量检查 + 入库 Neo4j。

    所有章节审核通过后调用。

    Args:
        state: 流水线状态
        neo4j_session: Neo4j session
        thresholds: 质量阈值
        redis_client: Redis 客户端
        embedding_client: embedding 客户端（Phase 2.5 Step 2 需要）
        llm_client: LLM 客户端（Phase 2.5 Step 3 需要）

    Returns:
        (success, report) — success 表示是否入库成功，report 是质量报告
    """
    # Phase 2.5: 全局关系补全
    state.current_phase = "phase2_5_global_inference"
    logger.info("Phase 2.5: 全局关系补全")
    try:
        phase25_result = await run_global_relation_inference(
            master=state.master_graph,
            embedding_client=embedding_client,
            llm_client=llm_client,
        )
        logger.info("Phase 2.5 完成: %s", phase25_result)
    except Exception as e:
        logger.warning("Phase 2.5 失败（不影响后续流程）: %s", e)

    # Phase 3: 质量检查
    state.current_phase = "phase3_quality"
    metrics, issues = audit_graph_quality(
        state.master_graph, thresholds,
        skip_chapters=state.non_content_chapters,
    )
    report = generate_quality_report(metrics, issues)

    # 记录完整质量报告到日志
    logger.info("质量审计报告:\n%s", report)

    if issues:
        # ── 段落覆盖度补全循环 ──
        from .models import PipelineConfig
        max_iterations = PipelineConfig().max_gap_fill_iterations
        for gap_iter in range(max_iterations):
            uncovered = _find_uncovered_paragraphs(state)
            if not uncovered:
                logger.info("Gap fill: 无未覆盖段落，停止补全")
                break
            logger.info(
                "Gap fill 第 %d/%d 轮: %d 个章节有未覆盖段落",
                gap_iter + 1, max_iterations, len(uncovered),
            )
            await _fill_coverage_gaps(state, uncovered, llm_client, embedding_client)

            # 重新运行 Phase 2.5 + 质量检查
            try:
                await run_global_relation_inference(
                    master=state.master_graph,
                    embedding_client=embedding_client,
                    llm_client=llm_client,
                )
            except Exception as e:
                logger.warning("Gap fill Phase 2.5 失败: %s", e)

            metrics, issues = audit_graph_quality(
                state.master_graph, thresholds,
                skip_chapters=state.non_content_chapters,
            )
            report = generate_quality_report(metrics, issues)
            if not issues:
                logger.info("Gap fill 第 %d 轮后质量达标", gap_iter + 1)
                break

    if issues:
        logger.warning("图质量检查未通过（不阻断入库），%d 个问题。", len(issues))
        for issue in issues:
            logger.warning("  质量告警: %s", issue)

    # Phase 4: 入库 Neo4j（质量告警不阻断流程）
    state.current_phase = "phase4_commit"
    logger.info("Phase 4: 入库 Neo4j")

    success = await commit_to_neo4j(state.master_graph, neo4j_session, use_staging=True)

    if success:
        state.current_phase = "completed"
        # 清理 Redis 临时数据
        if redis_client:
            await redis_client.delete(f"master_graph:{state.book_id}")
        logger.info("全书入库完成: %s", state.book_title)
    else:
        state.current_phase = "failed"
        state.errors.append("Neo4j 入库失败")

    return success, report


# ──────────────────────────────────────────────────────────────
# 内部工具
# ──────────────────────────────────────────────────────────────


def _get_existing_entities(state: PipelineState) -> list[dict]:
    """获取已审核章节的实体列表（供关系提取参考）。"""
    entities = []
    for ch_id in state.approved_chapters:
        for name in state.master_graph.chapter_entities.get(ch_id, []):
            node = state.master_graph.graph.nodes.get(name, {})
            entities.append({
                "name": name,
                "entity_type": node.get("entity_type", "AutoEntity"),
                "description": node.get("description", ""),
                "source_chapter": ch_id,
            })
    return entities


# ──────────────────────────────────────────────────────────────
# Phase 5: 跨书实体消歧（§08-4）
# ──────────────────────────────────────────────────────────────


async def run_phase5_cross_book(
    book_id: str,
    neo4j_driver,
    embedding_helper=None,
    llm_client=None,
    reviewer_decisions: list | None = None,
    enable_phase5: bool = True,
) -> dict:
    """⚠️ DEPRECATED (2026-06): 已被 curation_controller._run_d2g_pipeline 中直接调用的
    cross_book_phase5a.run_phase5a_cross_book_analysis 替代。
    新路径: Phase 5a（生成阶段匹配+关系发现）→ Phase 5b（入库时执行决策）。
    旧路径仅支持 3 种跨书关系类型，保留仅供向后兼容。

    Phase 5: 跨书实体消歧与全局图更新。

    在 Phase 4 入库完成后调用。仅当 Neo4j 中已有其他书的实体时执行。

    Args:
        book_id: 新入库书籍 ID
        neo4j_driver: Neo4j Python Driver
        embedding_helper: embedding 工具（可选）
        llm_client: LLM 客户端（可选）
        reviewer_decisions: 审核者决策列表（可选）
        enable_phase5: 配置开关，设为 False 时跳过

    Returns:
        Phase 5 执行结果 dict
    """
    if not enable_phase5:
        logger.info("Phase 5 已禁用（enable_phase5=False），跳过")
        return {"skipped": True, "reason": "disabled"}

    from src.core.knowledge_qa.neo4j.cross_book_resolver import CrossBookResolver

    resolver = CrossBookResolver(
        neo4j_driver=neo4j_driver,
        embedding_helper=embedding_helper,
        llm_client=llm_client,
    )

    outcome = await resolver.run_phase5(
        book_id=book_id,
        reviewer_decisions=reviewer_decisions,
    )

    # Step 7: 触发全局图重建
    try:
        from src.core.knowledge_qa.graph.global_rebuild import rebuild_global_graph
        # 全局图重建需要 db_session_factory，这里通过 neo4j_driver 间接获取
        # 实际调用方应传入 db_session_factory
        logger.info("Phase 5 完成，全局图重建由调用方触发")
    except Exception as e:
        logger.warning("全局图重建触发失败: %s", e)

    return {
        "book_id": outcome.book_id,
        "total_entities": outcome.total_entities,
        "merged_count": outcome.merged_count,
        "same_as_count": outcome.same_as_count,
        "reviewer_override_count": outcome.reviewer_override_count,
        "cross_book_relations": outcome.cross_book_relations,
        "duration_ms": outcome.duration_ms,
        "errors": outcome.errors,
    }
