"""全书知识图谱生产流水线编排。

放置位置: backend/src/core/knowledge_qa/d2g/book_pipeline.py

端到端流程:
  Phase 0 → Phase 1（逐章） → Phase 2（逐章审核） → Phase 3（质量检查） → Phase 4（入库）
"""

from __future__ import annotations

import asyncio
import logging
from typing import Callable, Optional, Protocol

from .book_reader import deep_book_reading, validate_book_context
from .global_relation_inference import run_global_relation_inference
from src.core.knowledge_qa.neo4j.chapter_parser import Chapter, ChapterParseResult
from .chapter_extractor import extract_chapter
from .entity_resolver import resolve_and_merge
from .graph_committer import commit_to_neo4j
from .graph_quality import audit_graph_quality, generate_quality_report
from .master_graph import MasterGraph
from .models import BookContext, ChapterExtraction, ModelConfig, PipelineConfig, QualityThresholds
from .review_md_generator import generate_review_md

logger = logging.getLogger(__name__)

# ── 非内容章节过滤 ─────────────────────────────────────────
# 匹配到这些标题的章节跳过提取（参考文献、目录、致谢等）
# 仅匹配独立标题或以这些词开头/结尾的标题，避免误杀正文章节
_NON_CONTENT_PATTERNS: list[str] = [
    "参考文献", "目录", "致谢", "前言", "后记", "附录", "索引",
    "版权页", "封面", "扉页", "跋", "序言", "序", "声明",
    "内容简介", "作者简介", "译者简介", "出版信息",
    "写在前面", "写在后面", "编写说明", "凡例",
    # 英文
    "references", "bibliography", "table of contents", "contents",
    "acknowledgment", "acknowledgement", "acknowledgements",
    "foreword", "preface", "appendix", "index", "abstract",
    "copyright", "about the author",
]


def _is_non_content_chapter(title: str) -> bool:
    """判断章节标题是否为非内容章节（参考文献/目录/致谢等）。"""
    t = title.strip().lower()
    # 去掉常见前缀如 "第X章"、数字编号
    import re
    t_clean = re.sub(r'^第[一二三四五六七八九十百千\d]+章\s*', '', t)
    t_clean = re.sub(r'^[\d.]+\s*', '', t_clean).strip()
    for pat in _NON_CONTENT_PATTERNS:
        if t_clean == pat or t_clean.startswith(pat) or t_clean.endswith(pat):
            return True
    return False


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
    # 过滤非内容章节（参考文献、目录、致谢等）
    skipped: list[str] = []
    content_chapters: list[Chapter] = []
    for ch in chapters:
        if _is_non_content_chapter(ch.title):
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
    logger.info("Phase 1: 开始逐章提取，共 %d 章 (串行模式，保证跨章上下文)", len(content_chapters))

    for chapter in content_chapters:
        # Phase 1: 提取到 staging（不入主图，供后续全局消歧）
        logger.info("Phase 1: 提取章节 '%s'", chapter.title)
        extraction = await extract_chapter(
            chapter=chapter,
            book_context=state.book_context,
            existing_entities=state.staging_entities,
            llm_client=llm_client,
            config=config.models,
            long_chapter_threshold=config.long_chapter_threshold,
        )
        state.staging_extractions[chapter.id] = extraction
        logger.info(
            "Phase 1 完成: 章节 '%s' (%d 实体, %d 关系)",
            chapter.title, len(extraction.entities), len(extraction.relationships),
        )

        # 更新 staging 上下文（供下一章 LLM 提取参考）
        for entity in extraction.entities:
            state.staging_entities.append({
                "name": entity.name,
                "entity_type": entity.entity_type,
                "description": entity.description,
                "source_chapter": chapter.id,
            })

        if on_progress:
            on_progress(state.progress)

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
    para_count = max(
        (pid for e in extraction.entities for pid in e.source_para_ids),
        default=0,
    )
    state.master_graph.chapter_para_count[chapter_id] = para_count

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
        logger.warning("图质量检查未通过，%d 个问题。请审核后重新提交。", len(issues))
        return False, report

    # Phase 4: 入库 Neo4j
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
    """Phase 5: 跨书实体消歧与全局图更新。

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
