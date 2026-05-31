"""全书知识图谱生产流水线编排。

放置位置: backend/src/core/knowledge_qa/neo4j/book_pipeline.py

端到端流程:
  Phase 0 → Phase 1（逐章） → Phase 2（逐章审核） → Phase 3（质量检查） → Phase 4（入库）
"""

from __future__ import annotations

import asyncio
import logging
from typing import Callable, Optional, Protocol

from .book_reader import deep_book_reading
from .chapter_parser import Chapter, ChapterParseResult
from .chapter_extractor import extract_chapter
from .entity_resolver import resolve_and_merge
from .graph_committer import commit_to_neo4j
from .graph_quality import audit_graph_quality, generate_quality_report
from .master_graph import MasterGraph
from .models import BookContext, ChapterExtraction, ModelConfig, PipelineConfig, QualityThresholds
from .review_md_generator import generate_review_md

logger = logging.getLogger(__name__)


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
        self.current_phase: str = "pending"
        self.errors: list[str] = []

    @property
    def progress(self) -> dict:
        return {
            "phase": self.current_phase,
            "total_chapters": len(self.chapter_extractions),
            "approved_chapters": len(self.approved_chapters),
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
    state.book_context = await deep_book_reading(
        parse_result=parse_result,
        llm_client=llm_client,
        model=config.models.context,
    )
    logger.info("Phase 0 完成: 主旨=%s", state.book_context.core_thesis[:50])

    # ─── Phase 1 + 2: 逐章提取 + 审核 ───
    state.current_phase = "phase1_extraction"
    if on_progress:
        on_progress(state.progress)

    chapters = parse_result.chapters
    semaphore = asyncio.Semaphore(config.concurrency)

    async def _process_chapter(chapter: Chapter) -> None:
        async with semaphore:
            # Phase 1: 提取
            logger.info("Phase 1: 提取章节 '%s'", chapter.title)
            extraction = await extract_chapter(
                chapter=chapter,
                book_context=state.book_context,
                existing_entities=_get_existing_entities(state),
                llm_client=llm_client,
                config=config.models,
                long_chapter_threshold=config.long_chapter_threshold,
            )
            state.chapter_extractions[chapter.id] = extraction

            # Phase 2: 生成审核 MD
            review_md = generate_review_md(extraction, state.master_graph)
            state.review_mds[chapter.id] = review_md

            if on_progress:
                on_progress(state.progress)

            # 审核回调
            if on_review_needed:
                on_review_needed(chapter.id, review_md)

    # 并行提取所有章节
    tasks = [_process_chapter(ch) for ch in chapters]
    await asyncio.gather(*tasks)

    # ─── Phase 2: 逐章审核 + 合入主图 ───
    # 此阶段需要人工审核，通过 approve_chapter() 方法逐章确认
    # 如果没有设置审核回调，自动批准所有章节
    if on_review_needed is None:
        logger.info("无审核回调，自动批准所有章节")
        for ch_id, extraction in state.chapter_extractions.items():
            await approve_chapter(
                state=state,
                chapter_id=ch_id,
                llm_client=llm_client,
                embedding_client=embedding_client,
                config=config,
                redis_client=redis_client,
            )

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
) -> tuple[bool, str]:
    """Phase 3 + 4: 质量检查 + 入库 Neo4j。

    所有章节审核通过后调用。

    Returns:
        (success, report) — success 表示是否入库成功，report 是质量报告
    """
    # Phase 3: 质量检查
    state.current_phase = "phase3_quality"
    metrics, issues = audit_graph_quality(state.master_graph, thresholds)
    report = generate_quality_report(metrics, issues)

    if issues:
        logger.warning("图质量检查未通过，%d 个问题。请审核后重新提交。", len(issues))
        return False, report

    # Phase 4: 入库 Neo4j
    state.current_phase = "phase4_commit"
    logger.info("Phase 4: 入库 Neo4j")

    success = await commit_to_neo4j(state.master_graph, neo4j_session)

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
