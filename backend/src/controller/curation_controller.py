"""知识审核 (Curation) API 控制器

端点：
- GET    /api/v2/curation/books                 策管书籍列表
- DELETE /api/v2/curation/books/{book_id}        删除策管书籍
- POST   /api/v2/curation/books/{book_id}/generate  触发 AI 生成
- GET    /api/v2/curation/books/{book_id}/generate/progress  生成进度 SSE
- GET    /api/v2/curation/books/{book_id}/chapters   获取章节列表
- GET    /api/v2/curation/kb-books               知识库可绑定书籍
- POST   /api/v2/curation/bind                   绑定知识库书籍
- GET    /api/v2/curation/drafts                 草稿列表
- GET    /api/v2/curation/drafts/{id}            获取 MD 草稿
- PUT    /api/v2/curation/drafts/{id}            保存审核修改
- POST   /api/v2/curation/drafts/{id}/review     标记已审核
- POST   /api/v2/curation/drafts/{id}/publish    入库 Neo4j
- GET    /api/v2/curation/graph                  KG 可视化数据
- GET    /api/v2/curation/pending                待提炼队列
"""

import logging
import os as _os
import uuid
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from src.schemas.common import APIResponse
import asyncio as _asyncio
import json
import traceback as _traceback
import time as _time

logger = logging.getLogger(__name__)

# ── 运行中的 D2G 流水线任务（独立于 SSE 连接，浏览器断开不影响） ──
_running_tasks: dict[str, _asyncio.Task] = {}    # book_id → task
_progress_states: dict[str, dict] = {}            # book_id → 共享进度状态
_progress_events: dict[str, _asyncio.Event] = {}  # book_id → 进度更新信号


class BindBookRequest(BaseModel):
    kb_book_id: str
    book_title: str
    author: Optional[str] = None


class CrossBookDecisionRequest(BaseModel):
    book_id: str
    decision_type: str  # "entity_match" / "cross_relation"
    index: int
    decision: str  # merge / separate / auto / skip / confirm / ignore / modify
    custom_type: Optional[str] = None


class CrossBookBatchDecisionRequest(BaseModel):
    book_id: str
    decision_type: str  # "entity_match" / "cross_relation"
    indices: list[int]
    decision: str



def _generate_sample_md(book_title: str, chapters: list) -> str:
    """生成示例 MD 内容（模拟 AI 生成的结构化知识）"""
    md = f"# {book_title}\n\n"
    md += "> 本文档由 AI 自动生成，请审核后入库。\n\n"
    md += "## 概要\n\n"
    md += f"本书共 {len(chapters)} 章，涵盖儿童发展与运动科学的核心知识。\n\n"

    # 问题
    md += "## 问题 (Problem)\n\n"
    md += "### 注意力缺陷多动障碍 (ADHD)\n\n"
    md += "- **entity_type**: Problem\n"
    md += "- **severity**: high\n"
    md += "- **来源**: 第二章\n"
    md += "- 注意力缺陷是儿童发展中常见的神经发育障碍，表现为注意力不集中、过度活跃和冲动。\n\n"
    md += "### 阅读障碍\n\n"
    md += "- **entity_type**: Problem\n"
    md += "- **severity**: medium\n"
    md += "- **来源**: 第三章\n"
    md += "- 阅读障碍影响约5-17%的儿童，与脑区神经连接异常有关。\n\n"

    # 方案
    md += "## 方案 (Solution)\n\n"
    md += "### 有氧运动干预\n\n"
    md += "- **entity_type**: Solution\n"
    md += "- **有效性**: high\n"
    md += "- **来源**: 第四章\n"
    md += "- 每天30分钟中等强度有氧运动可显著改善注意力和认知功能。\n\n"
    md += "### 精细动作训练\n\n"
    md += "- **entity_type**: Solution\n"
    md += "- **有效性**: medium\n"
    md += "- **来源**: 第五章\n"
    md += "- 精细动作训练有助于改善书写能力和阅读流畅性。\n\n"

    # 脑区
    md += "## 脑区 (BrainRegion)\n\n"
    md += "### 前额叶皮层 (PFC)\n\n"
    md += "- **entity_type**: BrainRegion\n"
    md += "- **功能**: 执行功能、注意力控制\n"
    md += "- **来源**: 第二章\n"
    md += "- 前额叶皮层是注意力和执行功能的核心脑区。\n\n"
    md += "### 海马体\n\n"
    md += "- **entity_type**: BrainRegion\n"
    md += "- **功能**: 学习与记忆\n"
    md += "- **来源**: 第三章\n"
    md += "- 海马体负责将短期记忆转化为长期记忆。\n\n"

    # 运动
    md += "## 运动 (Exercise)\n\n"
    md += "### 跑步\n\n"
    md += "- **entity_type**: Exercise\n"
    md += "- **强度**: 中等\n"
    md += "- **时长**: 30分钟\n"
    md += "- **来源**: 第四章\n"
    md += "- 跑步是最易实施的有氧运动，可促进BDNF分泌。\n\n"
    md += "### 游泳\n\n"
    md += "- **entity_type**: Exercise\n"
    md += "- **强度**: 中等\n"
    md += "- **时长**: 45分钟\n"
    md += "- **来源**: 第五章\n"
    md += "- 游泳是全身运动，对协调性和心肺功能都有益处。\n\n"

    # 处方
    md += "## 处方 (Prescription)\n\n"
    md += "### ADHD 运动处方\n\n"
    md += "- **target_problem**: ADHD\n"
    md += "- **exercise**: 跑步 + 精细动作训练\n"
    md += "- **frequency**: 每周5次\n"
    md += "- **来源**: 第四章\n"
    md += "- 建议每天30分钟有氧运动配合15分钟精细动作训练。\n\n"

    # 根因
    md += "## 根因 (RootCause)\n\n"
    md += "### BDNF 分泌不足\n\n"
    md += "- **entity_type**: RootCause\n"
    md += "- **关联问题**: ADHD, 阅读障碍\n"
    md += "- **来源**: 第二章\n"
    md += "- 脑源性神经营养因子(BDNF)分泌不足是注意力和学习障碍的重要生理因素。\n\n"

    return md


def _write_md_file(book_id: str, version_id: str, content: str) -> str:
    """将 MD 内容写入本地文件，返回相对于 curation_md_dir 的路径。"""
    # 路径穿越防护：book_id / version_id 必须为安全 slug
    for val, label in [(book_id, "book_id"), (version_id, "version_id")]:
        if ".." in val or val.startswith("/") or val.startswith("\\"):
            raise ValueError(f"非法的 {label}: {val}")
    from src.config import settings
    base = Path(settings.curation_md_dir).resolve()
    fpath = (base / book_id / f"{version_id}.md").resolve()
    if not str(fpath).startswith(str(base) + _os.sep):
        raise ValueError(f"路径穿越检测: {book_id}/{version_id}")
    fpath.parent.mkdir(parents=True, exist_ok=True)
    fpath.write_text(content, encoding="utf-8")
    return str(fpath.relative_to(base))


def _read_md_file(md_path: str) -> str:
    """从本地文件读取 MD 内容。"""
    if not md_path:
        return ""
    # 路径穿越防护
    if ".." in md_path:
        logger.warning("拒绝路径穿越读取: %s", md_path)
        return ""
    from src.config import settings
    base = Path(settings.curation_md_dir).resolve()
    fpath = (base / md_path).resolve()
    if not str(fpath).startswith(str(base) + _os.sep):
        logger.warning("拒绝路径穿越读取: %s", md_path)
        return ""
    if fpath.exists():
        return fpath.read_text(encoding="utf-8")
    logger.warning("MD 文件不存在: %s", fpath)
    return ""


# ═══════════════════════════════════════════════════════════════
# D2G 流水线独立任务（不依赖 SSE 连接）
# ═══════════════════════════════════════════════════════════════


def _update_progress(book_id: str, **kwargs):
    """更新共享进度状态并通知 SSE 订阅者。"""
    if book_id in _progress_states:
        _progress_states[book_id].update(kwargs)
    if book_id in _progress_events:
        _progress_events[book_id].set()


def _cleanup_task(book_id: str):
    """任务完成后的清理（done callback）。"""
    task = _running_tasks.pop(book_id, None)
    if task and not task.cancelled():
        try:
            exc = task.exception()
            if exc and book_id in _progress_states:
                _update_progress(book_id, status="failed", error=str(exc)[:200],
                                 phase_label="流水线异常")
        except asyncio.InvalidStateError:
            pass  # 异常已被 _run_d2g_pipeline 的 except 分支消费
    if book_id in _progress_events:
        _progress_events[book_id].set()


async def _cascade_cleanup_stale_cross_refs(
    book_id: str, output_dir: str,
) -> None:
    """级联清理：删除 / 重生成某本书后，清理其他书 JSON 中的陈旧引用。

    修复 P4 (删除不完整) 和 P10 (重生成后跨书关系过期)。
    """
    import json as _json
    from src.models.md_metadata import MDMetadata
    from src.core.database import async_session_factory
    from sqlalchemy import select

    try:
        # 获取其他已入库书籍
        async with async_session_factory() as session:
            result = await session.execute(
                select(MDMetadata).where(
                    MDMetadata.status == "published",
                    MDMetadata.book_id != book_id,
                )
            )
            other_books = result.scalars().all()

        redis_deleted = 0
        json_cleaned = 0

        for other in other_books:
            # 清理 Redis 缓存
            try:
                import redis as _redis
                from src.config.modules.redis import get_sync_redis as _get_sync_redis
                r = _get_sync_redis()
                for key in [
                    f"d2g:cross_analysis:{other.book_id}",
                    f"d2g:cross_decisions:{other.book_id}",
                    f"d2g:cross_result:{other.book_id}",
                ]:
                    if r.delete(key):
                        redis_deleted += 1
            except Exception:
                pass

            # 清理 JSON 文件中引用已删除/重生成书的条目
            json_path = Path(output_dir) / other.book_id / "cross_book_relations.json"
            if not json_path.exists():
                continue
            try:
                data = _json.loads(json_path.read_text("utf-8"))
                dirty = False

                # 过滤 entity_matches 中引用 book_id 的条目
                em_before = len(data.get("entity_matches", []))
                data["entity_matches"] = [
                    m for m in data.get("entity_matches", [])
                    if m.get("matched_book_id") != book_id
                    and m.get("new_book_id") != book_id
                ]
                if len(data["entity_matches"]) < em_before:
                    dirty = True

                # 过滤 cross_relations 中引用 book_id 的条目
                cr_before = len(data.get("cross_relations", []))
                data["cross_relations"] = [
                    r for r in data.get("cross_relations", [])
                    if r.get("source_book") != book_id
                    and r.get("target_book") != book_id
                ]
                if len(data["cross_relations"]) < cr_before:
                    dirty = True

                # 清理 source_books
                sb_before = len(data.get("source_books", []))
                data["source_books"] = [
                    b for b in data.get("source_books", [])
                    if b.get("book_id") != book_id
                ]
                if len(data["source_books"]) < sb_before:
                    dirty = True

                if dirty:
                    json_path.write_text(_json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
                    json_cleaned += 1
                    logger.info(
                        "[级联清理] 已清理 %s 中引用 %s 的陈旧条目",
                        other.book_id, book_id,
                    )
            except Exception:
                pass

        if redis_deleted or json_cleaned:
            logger.info(
                "[级联清理] 完成: %d Redis keys, %d JSON 文件",
                redis_deleted, json_cleaned,
            )
    except Exception as e:
        logger.warning("[级联清理] 执行异常（不阻塞主流程）: %s", e)


async def _save_draft_from_result(book_id: str, book_title: str,
                                   result) -> None:
    """从 D2G 流水线结果保存 MD 草稿到数据库。

    独立于 SSE 连接，失败不影响任务成功状态。
    """
    try:
        review_md = ""
        if hasattr(result, "review_mds") and result.review_mds:
            for ch_id, md_text in result.review_mds.items():
                if md_text:
                    review_md += md_text + "\n\n---\n\n"
        if not review_md:
            if hasattr(result, "book_context") and result.book_context:
                bc = result.book_context
                review_md = f"# {bc.book_title}\n\n"
                review_md += f"## 全书主旨\n\n{bc.core_thesis}\n\n"
                if bc.key_arguments:
                    review_md += "## 核心论点\n\n"
                    for arg in bc.key_arguments:
                        review_md += f"- {arg}\n"
                    review_md += "\n"
        if not review_md:
            review_md = _generate_sample_md(book_title, [])

        from src.models.md_metadata import MDMetadata
        from src.models.md_version import MDVersion
        from src.core.database import async_session_factory
        from sqlalchemy import select

        async with async_session_factory() as session:
            result_db = await session.execute(
                select(MDMetadata).where(MDMetadata.book_id == book_id)
            )
            meta = result_db.scalar_one_or_none()
            if meta:
                meta.status = "draft"
                import uuid as _uuid
                if meta.current_version_id:
                    ver_result = await session.execute(
                        select(MDVersion).where(
                            MDVersion.id == meta.current_version_id)
                    )
                    version = ver_result.scalar_one_or_none()
                    if version:
                        # 已有版本：覆盖同文件路径
                        _write_md_file(book_id, version.id, review_md)
                else:
                    version_id = str(_uuid.uuid4())
                    md_path = _write_md_file(book_id, version_id, review_md)
                    version = MDVersion(
                        id=version_id,
                        book_id=book_id,
                        md_path=md_path,
                        version=1,
                        status="draft",
                    )
                    session.add(version)
                    meta.current_version_id = version_id
                await session.commit()
        logger.info("[生成流程] 草稿保存成功 book_id=%s", book_id)
    except Exception as e:
        logger.error("[生成流程] 草稿保存失败 book_id=%s: %s", book_id, e)


async def _run_d2g_pipeline(book_id: str, book_title: str):
    """独立 asyncio.Task：Phase 0→4 + 保存草稿。

    不依赖任何 SSE 连接，浏览器断开不影响执行。
    """
    _t0 = _time.monotonic()
    neo4j_session = None  # 初始化，finally 中需要

    try:
        _update_progress(book_id, phase="phase0_reading",
                         phase_label="正在初始化...", progress=0)

        from src.models.md_metadata import MDMetadata
        from src.core.database import async_session_factory
        from sqlalchemy import select

        async with async_session_factory() as session:
            result = await session.execute(
                select(MDMetadata).where(MDMetadata.book_id == book_id)
            )
            meta = result.scalar_one_or_none()
            if not meta:
                _update_progress(book_id, status="failed",
                                 error="书籍未绑定", progress=0)
                return

        file_hash = meta.file_hash
        if not file_hash:
            _update_progress(book_id, status="failed",
                             error="无源文件", progress=0)
            return

        from src.core.knowledge_qa.neo4j.chapter_parser import ChapterParser

        parser = ChapterParser()
        parse_result = await parser.parse_by_hash(file_hash)
        chapters_raw = parse_result.chapters
        chapters = [{"title": ch.title, "id": ch.id, "status": "pending"}
                     for ch in chapters_raw]

        _update_progress(book_id, chapters=chapters, progress=5,
                         phase_label=f"已解析 {len(chapters)} 章")
        logger.info("[生成流程] EPUB 解析完成 book_id=%s, %d 章, %.1fs",
                    book_id, len(chapters), _time.monotonic() - _t0)

        from src.config import settings
        from src.core.llm.factory import LLMServiceFactoryCompat

        d2g_model = settings.d2g_model
        d2g_max_tokens = settings.d2g_max_tokens
        llm_factory = LLMServiceFactoryCompat()
        llm_adapter = llm_factory.create(model_name=d2g_model, max_tokens=d2g_max_tokens)
        logger.info("[生成流程] LLM 适配器就绪 book_id=%s, model=%s", book_id, d2g_model)

        from src.utils.di import get_embedding_helper

        emb_helper = get_embedding_helper()

        class _D2GEmbedAdapter:
            def __init__(self, h):
                self._h = h

            async def embed(self, texts):
                if isinstance(texts, str):
                    texts = [texts]
                return await self._h.embed_batch(texts)

        emb_adapter = _D2GEmbedAdapter(emb_helper)
        logger.info("[生成流程] Embedding 适配器就绪 book_id=%s", book_id)

        from src.core.knowledge_qa.neo4j.driver import get_async_neo4j_driver

        neo4j_driver = get_async_neo4j_driver()
        neo4j_session = neo4j_driver.session() if neo4j_driver else None
        logger.info("[生成流程] Neo4j 驱动就绪 book_id=%s", book_id)

        # ── 重新生成前清理旧的 Neo4j 数据，避免节点重复 ──
        if neo4j_driver:
            try:
                from src.core.knowledge_qa.neo4j.cross_book_cleanup import CrossBookCleanup
                cleanup = CrossBookCleanup(neo4j_driver=neo4j_driver)
                cleanup_result = await cleanup.cleanup_book(book_id)
                logger.info("[生成流程] 旧 Neo4j 数据已清理: %s", cleanup_result)
            except Exception as e:
                logger.warning("[生成流程] 清理旧数据失败（不阻塞生成）: %s", e)

        import os
        from src.core.knowledge_qa.d2g.models import PipelineConfig, ModelConfig
        from src.core.knowledge_qa.d2g.models import QualityThresholds

        config = PipelineConfig(
            concurrency=int(os.environ.get("D2G_CONCURRENCY", "5")),
            models=ModelConfig(
                context=d2g_model,
                extraction=d2g_model,
                resolution=d2g_model,
            ),
        )

        from src.core.knowledge_qa.d2g.book_pipeline import (
            run_full_pipeline, finalize_and_commit,
        )
        from src.core.knowledge_qa.neo4j.cross_book_phase5a import run_phase5a_cross_book_analysis

        phase_progress_map = {
            "phase0_reading": (5, 15),
            "phase1_extraction": (15, 55),
            "phase2_resolution": (55, 75),
            "phase2_5_global_inference": (75, 85),
            "phase3_quality": (85, 93),
            "phase4_commit": (93, 98),
            "phase5_cross_book": (98, 100),
        }

        phase_labels = {
            "phase0_reading": "正在深度阅读全书...",
            "phase1_extraction": "正在逐章提取实体与关系...",
            "phase2_resolution": "正在全局消歧合并...",
            "phase2_5_global_inference": "正在补全跨章关系...",
            "phase3_quality": "正在质量检查...",
            "phase4_commit": "正在入库 Neo4j...",
            "phase5_cross_book": "正在跨书分析...",
            "completed": "生成完成",
        }

        def _on_progress(progress_dict: dict):
            phase = progress_dict.get("phase", "")
            lo, hi = phase_progress_map.get(phase, (85, 90))
            approved_raw = progress_dict.get("approved_chapters", 0)
            total_raw = progress_dict.get("total_chapters", len(chapters))

            approved_set = (set(approved_raw) if isinstance(approved_raw, list)
                           else set())
            # Phase 1 用 staging_extractions，Phase 2+ 用 chapter_extractions
            extracted_set = set(
                progress_dict.get("staging_extractions", {}).keys()
                or progress_dict.get("chapter_extractions", {}).keys()
            )
            total = (len(total_raw) if isinstance(total_raw, list)
                     else (total_raw if isinstance(total_raw, int) else len(chapters)))
            approved_count = len(approved_set)

            # 计算总体进度百分比
            if phase == "phase1_extraction" and total > 0:
                pct = lo + int(len(extracted_set) / total * (hi - lo))
            elif phase == "phase2_resolution":
                pct = lo  # 全局消歧是单步操作，无法细分
            elif phase == "phase2_5_global_inference":
                pct = lo
            else:
                pct = lo

            # 同步各章节状态
            updated_chapters = []
            for ch in chapters:
                cid = ch["id"]
                if cid in approved_set:
                    ch_status = "completed"
                elif cid in extracted_set:
                    ch_status = "completed"
                else:
                    ch_status = "pending"
                updated_chapters.append({**ch, "status": ch_status})

            label = progress_dict.get("phase_label") or phase_labels.get(phase, phase)
            _update_progress(book_id, phase=phase, phase_label=label,
                             progress=min(pct, 99), chapters=updated_chapters)

        state = await run_full_pipeline(
            parse_result=parse_result,
            llm_client=llm_adapter,
            embedding_client=emb_adapter,
            neo4j_session=neo4j_session,
            config=config,
            on_progress=_on_progress,
        )

        logger.info("[生成流程] Phase 0-2 完成 book_id=%s (%.1fs)",
                    book_id, _time.monotonic() - _t0)

        _update_progress(book_id, phase="phase3_quality",
                         phase_label="正在质量检查...", progress=85)

        success, report = await finalize_and_commit(
            state=state,
            neo4j_session=neo4j_session,
            thresholds=QualityThresholds(),
            embedding_client=emb_adapter,
            llm_client=llm_adapter,
        )

        if report:
            logger.info("[生成流程] 质量报告 book_id=%s\n%s", book_id, report)

        if not success:
            logger.error("[生成流程] Neo4j 入库失败 book_id=%s", book_id)
            _update_progress(book_id, status="failed",
                             error="Neo4j 入库失败",
                             progress=90)
            return  # Neo4j 入库失败无法继续

        # ── 回写实体/主张/处方计数到 MDMetadata ──
        try:
            mg = state.master_graph.graph
            _total_entities = len(mg.nodes)
            _total_claims = len(mg.edges)
            _total_prescriptions = sum(
                1 for _, ndata in mg.nodes(data=True)
                if ndata.get("entity_type") == "Prescription"
            )
            async with async_session_factory() as _ses:
                _r = await _ses.execute(
                    select(MDMetadata).where(MDMetadata.book_id == book_id))
                _m = _r.scalar_one_or_none()
                if _m:
                    _m.total_entities = _total_entities
                    _m.total_claims = _total_claims
                    _m.total_prescriptions = _total_prescriptions
                    await _ses.commit()
            logger.info(
                "[生成流程] 计数已回写 book_id=%s: entities=%d, claims=%d, prescriptions=%d",
                book_id, _total_entities, _total_claims, _total_prescriptions,
            )
        except Exception as e:
            logger.warning("[生成流程] 计数回写失败（不阻塞主流程）: %s", e)

        enable_phase5 = os.environ.get("D2G_ENABLE_PHASE5", "true").lower() == "true"
        if enable_phase5:
            _update_progress(book_id, phase="phase5_cross_book",
                             phase_label="正在跨书分析...", progress=98)
            from src.config import settings as _cfg
            _output_dir = str(Path(_cfg.data_dir))

            # Phase 5a 带重试机制（最多 3 次，间隔递增）
            MAX_PHASE5A_RETRIES = 3
            _phase5a_result = None
            _phase5a_failed = False
            for _retry_attempt in range(MAX_PHASE5A_RETRIES):
                try:
                    _phase5a_result = await run_phase5a_cross_book_analysis(
                        book_id=book_id,
                        neo4j_driver=neo4j_driver,
                        embedding_helper=emb_helper,
                        llm_client=llm_adapter,
                        output_dir=_output_dir,
                    )
                    logger.info(
                        "[生成流程] Phase 5a 完成 book_id=%s, 匹配=%d, 关系=%d (attempt=%d)",
                        book_id,
                        len(_phase5a_result.entity_matches),
                        len(_phase5a_result.cross_relations),
                        _retry_attempt + 1,
                    )
                    _phase5a_failed = False
                    break
                except Exception as e:
                    if _retry_attempt < MAX_PHASE5A_RETRIES - 1:
                        delay = 30 * (2 ** _retry_attempt)
                        logger.warning(
                            "[生成流程] Phase 5a 失败 (attempt=%d/%d): %s，%ds 后重试",
                            _retry_attempt + 1, MAX_PHASE5A_RETRIES, e, delay,
                        )
                        _update_progress(book_id, phase_label=f"跨书分析重试中 ({_retry_attempt + 1}/{MAX_PHASE5A_RETRIES})...")
                        await _asyncio.sleep(delay)
                    else:
                        logger.error(
                            "[生成流程] Phase 5a 最终失败 book_id=%s: %s", book_id, e,
                        )
                        _phase5a_failed = True
                        _update_progress(book_id, phase5a_failed=True,
                                         phase_label=f"跨书分析失败（已重试 {MAX_PHASE5A_RETRIES} 次）")

            # Phase 5a 成功后：级联清理其他书 JSON 中引用本书的陈旧条目（修复 P10）
            if _phase5a_result and not _phase5a_failed:
                await _cascade_cleanup_stale_cross_refs(book_id, _output_dir)

        _update_progress(book_id, phase_label="正在保存草稿...", progress=99)
        await _save_draft_from_result(book_id, book_title, state)

        elapsed = _time.monotonic() - _t0
        _update_progress(book_id, status="completed", progress=100,
                         phase_label=f"生成完成 ({elapsed:.0f}s)")
        logger.info("[生成流程] 全部完成 book_id=%s (%.1fs)", book_id, elapsed)

    except _asyncio.CancelledError:
        _update_progress(book_id, status="cancelled", phase_label="任务已取消")
        logger.info("[生成流程] 任务取消 book_id=%s", book_id)
    except Exception as e:
        logger.error("[生成流程] 流水线异常 book_id=%s: %s\n%s",
                     book_id, e, _traceback.format_exc())
        _update_progress(book_id, status="failed", error=str(e)[:200],
                         phase_label="流水线异常")
    finally:
        try:
            from src.models.md_metadata import MDMetadata
            from src.core.database import async_session_factory as _asf
            from sqlalchemy import select as _sel
            async with _asf() as _ses:
                _r = await _ses.execute(
                    _sel(MDMetadata).where(MDMetadata.book_id == book_id))
                _m = _r.scalar_one_or_none()
                if _m and _m.status == "generating":
                    final_status = _progress_states.get(book_id, {}).get("status", "failed")
                    _m.status = "draft" if final_status == "completed" else "failed"
                    await _ses.commit()
        except Exception:
            pass
        if neo4j_session:
            try:
                await neo4j_session.close()
            except Exception:
                pass


class CurationController:
    """知识审核控制器"""

    def __init__(self, neo4j_driver=None):
        self._driver = neo4j_driver

    def register(self, router: APIRouter) -> None:
        """注册所有路由"""
        # 书籍管理
        router.add_api_route(
            "/curation/books",
            self.list_books,
            methods=["GET"],
            summary="策管书籍列表",
        )
        router.add_api_route(
            "/curation/books/{book_id}",
            self.delete_book,
            methods=["DELETE"],
            summary="删除策管书籍",
        )
        router.add_api_route(
            "/curation/books/{book_id}/generate",
            self.start_generation,
            methods=["POST"],
            summary="触发 AI 生成",
        )
        router.add_api_route(
            "/curation/books/{book_id}/generate/progress",
            self.generation_progress,
            methods=["GET"],
            summary="生成进度 SSE",
        )
        router.add_api_route(
            "/curation/books/{book_id}/generate/cancel",
            self.cancel_generation,
            methods=["POST"],
            summary="取消生成任务",
        )
        router.add_api_route(
            "/curation/books/{book_id}/chapters",
            self.get_chapters,
            methods=["GET"],
            summary="获取章节列表",
        )
        router.add_api_route(
            "/curation/books/{book_id}/refresh-counts",
            self.refresh_counts,
            methods=["POST"],
            summary="从 Neo4j 刷新实体/主张/处方计数",
        )
        # 绑定
        router.add_api_route(
            "/curation/kb-books",
            self.list_kb_books,
            methods=["GET"],
            summary="知识库可绑定书籍",
        )
        router.add_api_route(
            "/curation/bind",
            self.bind_book,
            methods=["POST"],
            summary="绑定知识库书籍",
        )
        # 草稿
        router.add_api_route(
            "/curation/drafts",
            self.list_drafts,
            methods=["GET"],
            summary="草稿列表",
        )
        router.add_api_route(
            "/curation/drafts/{draft_id}",
            self.get_draft,
            methods=["GET"],
            summary="获取 MD 草稿",
        )
        router.add_api_route(
            "/curation/drafts/{draft_id}",
            self.update_draft,
            methods=["PUT"],
            summary="保存审核修改",
        )
        router.add_api_route(
            "/curation/drafts/{draft_id}/review",
            self.mark_reviewed,
            methods=["POST"],
            summary="标记已审核",
        )
        router.add_api_route(
            "/curation/drafts/{draft_id}/publish",
            self.publish_to_neo4j,
            methods=["POST"],
            summary="入库 Neo4j",
        )
        # 图谱
        router.add_api_route(
            "/curation/graph",
            self.get_graph,
            methods=["GET"],
            summary="KG 可视化数据",
        )
        # 导出
        router.add_api_route(
            "/curation/graph/export-cypher",
            self.export_cypher,
            methods=["GET"],
            summary="导出 Cypher 查询",
        )
        # 清空图谱
        router.add_api_route(
            "/curation/graph/clear",
            self.clear_graph,
            methods=["POST"],
            summary="清空知识图谱",
        )
        # 跨书关系
        router.add_api_route(
            "/curation/cross-book/pairs",
            self.cross_book_pairs,
            methods=["GET"],
            summary="获取跨书关系对",
        )
        # 队列
        router.add_api_route(
            "/curation/pending",
            self.get_pending_queue,
            methods=["GET"],
            summary="待提炼队列",
        )
        # 跨书融合 (Phase 5a/5b)
        router.add_api_route(
            "/curation/cross-book/relations/{book_id}",
            self.get_cross_book_relations,
            methods=["GET"],
            summary="获取跨书融合分析结果",
        )
        router.add_api_route(
            "/curation/cross-book/decision",
            self.update_cross_book_decision,
            methods=["POST"],
            summary="更新审核者决策",
        )
        router.add_api_route(
            "/curation/cross-book/decision/batch",
            self.batch_update_cross_book_decisions,
            methods=["POST"],
            summary="批量更新审核者决策",
        )
        # 全局跨书分析 + 手动重试
        router.add_api_route(
            "/curation/cross-book/analyze-all",
            self.analyze_all_books,
            methods=["POST"],
            summary="对所有已入库书籍执行成对跨书分析",
        )
        router.add_api_route(
            "/curation/books/{book_id}/cross-book/retry",
            self.retry_cross_book_analysis,
            methods=["POST"],
            summary="手动触发单书的 Phase 5a 跨书分析重试",
        )

    # ================================================================
    # 书籍管理
    # ================================================================

    async def list_books(
        self,
        status: Optional[str] = Query(None),
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
    ) -> APIResponse:
        """获取策管书籍列表"""
        try:
            from src.models.md_metadata import MDMetadata
            from src.core.database import async_session_factory
            from sqlalchemy import select, func

            async with async_session_factory() as session:
                query = select(MDMetadata)
                count_query = select(func.count()).select_from(MDMetadata)

                if status:
                    query = query.where(MDMetadata.status == status)
                    count_query = count_query.where(MDMetadata.status == status)

                query = query.order_by(MDMetadata.updated_at.desc())
                query = query.offset((page - 1) * page_size).limit(page_size)

                result = await session.execute(query)
                drafts = result.scalars().all()

                total_result = await session.execute(count_query)
                total = total_result.scalar() or 0

            return APIResponse.success(data={
                "books": [
                    {
                        "id": d.id,
                        "book_id": d.book_id,
                        "book_title": d.book_title,
                        "status": d.status,
                        "version": d.version,
                        "total_entities": d.total_entities or 0,
                        "total_claims": d.total_claims or 0,
                        "total_prescriptions": d.total_prescriptions or 0,
                        "neo4j_synced": bool(d.neo4j_synced),
                        "author": d.author,
                        "bind_source": d.bind_source or "kb_bind",
                        "reviewed_by": d.reviewed_by if hasattr(d, "reviewed_by") else None,
                        "created_at": d.created_at.isoformat() if d.created_at else None,
                        "updated_at": d.updated_at.isoformat() if d.updated_at else None,
                    }
                    for d in drafts
                ],
                "total": total,
                "page": page,
                "page_size": page_size,
            })
        except Exception as e:
            logger.error("获取策管书籍列表失败: %s", e)
            raise HTTPException(status_code=500, detail=str(e))

    async def refresh_counts(self, book_id: str) -> APIResponse:
        """从 Neo4j 刷新该书的实体/主张/处方计数"""
        try:
            from src.core.knowledge_qa.neo4j.driver import get_neo4j_driver, neo4j_available
            if not neo4j_available():
                raise HTTPException(status_code=503, detail="Neo4j 不可用")

            # 查找 Neo4j 中实际使用的 book_id（可能是 SourceDocument.id）
            neo4j_book_id = book_id
            from src.models.md_metadata import MDMetadata
            from src.core.database import async_session_factory
            from sqlalchemy import select

            async with async_session_factory() as session:
                meta_res = await session.execute(
                    select(MDMetadata).where(MDMetadata.book_id == book_id))
                meta = meta_res.scalar_one_or_none()
                if not meta:
                    raise HTTPException(status_code=404, detail="书籍不存在")

                # 通过 file_hash 查找 SourceDocument.id（D2G 流水线用它作为 Neo4j book_id）
                if meta.file_hash:
                    from src.models.document import SourceDocument
                    doc_res = await session.execute(
                        select(SourceDocument).where(SourceDocument.file_hash == meta.file_hash))
                    doc = doc_res.scalar_one_or_none()
                    if doc and doc.id:
                        neo4j_book_id = doc.id

            driver = get_neo4j_driver()
            with driver.session() as session:
                ent_res = session.run(
                    "MATCH (ae) WHERE ae.book_id = $bid "
                    "RETURN count(ae) AS cnt", bid=neo4j_book_id)
                ent_cnt = ent_res.single()["cnt"]

                rel_res = session.run(
                    "MATCH (ae1)-[r]->(ae2) "
                    "WHERE ae1.book_id = $bid AND ae2.book_id = $bid "
                    "RETURN count(r) AS cnt", bid=neo4j_book_id)
                rel_cnt = rel_res.single()["cnt"]

                rx_res = session.run(
                    "MATCH (p:Prescription) WHERE p.book_id = $bid "
                    "RETURN count(p) AS cnt", bid=neo4j_book_id)
                rx_cnt = rx_res.single()["cnt"]

            async with async_session_factory() as session:
                result = await session.execute(
                    select(MDMetadata).where(MDMetadata.book_id == book_id))
                meta = result.scalar_one_or_none()
                if meta:
                    meta.total_entities = ent_cnt
                    meta.total_claims = rel_cnt
                    meta.total_prescriptions = rx_cnt
                    await session.commit()

            return APIResponse.success(data={
                "total_entities": ent_cnt,
                "total_claims": rel_cnt,
                "total_prescriptions": rx_cnt,
            })
        except HTTPException:
            raise
        except Exception as e:
            logger.error("刷新计数失败: %s", e)
            raise HTTPException(status_code=500, detail=str(e))

    async def delete_book(self, book_id: str) -> APIResponse:
        """删除策管书籍 — 同时清理 MD 文件、Neo4j 节点、Redis 缓存和跨书文件"""
        try:
            from src.models.md_metadata import MDMetadata
            from src.models.md_version import MDVersion
            from src.core.database import async_session_factory
            from sqlalchemy import select, delete

            # ── 1. 查询关联的版本，收集待删除的 MD 文件路径 ──
            md_files_to_delete: list[str] = []
            async with async_session_factory() as session:
                ver_result = await session.execute(
                    select(MDVersion.md_path).where(MDVersion.book_id == book_id)
                )
                md_files_to_delete = [row[0] for row in ver_result.fetchall() if row[0]]

            # ── 2. 清理 Neo4j 中该书的所有节点和关系 ──
            try:
                from src.core.knowledge_qa.neo4j.driver import get_async_neo4j_driver, neo4j_available
                if neo4j_available():
                    driver = get_async_neo4j_driver()
                    if driver:
                        from src.core.knowledge_qa.neo4j.cross_book_cleanup import CrossBookCleanup
                        cleanup = CrossBookCleanup(neo4j_driver=driver)
                        cleanup_result = await cleanup.cleanup_book(book_id)
                        logger.info("Neo4j 清理完成: %s", cleanup_result)
            except Exception as e:
                logger.warning("Neo4j 清理失败（不阻塞删除）: %s", e)

            # ── 3. 清理 Redis 缓存 ──
            try:
                from src.config.modules.redis import get_sync_redis as _get_sync
                r = _get_sync()
                keys_to_delete = [
                    f"d2g:cross_analysis:{book_id}",
                    f"d2g:cross_decisions:{book_id}",
                    f"d2g:cross_result:{book_id}",
                    f"master_graph:{book_id}",
                ]
                for key in keys_to_delete:
                    r.delete(key)
            except Exception as e:
                logger.warning("Redis 清理失败（不阻塞删除）: %s", e)

            # ── 4. 清理磁盘文件 ──
            try:
                from src.config import settings
                import shutil
                # 4a. 删除 curation_md/{book_id}/ 整个目录
                md_dir = Path(settings.curation_md_dir) / book_id
                if md_dir.exists() and md_dir.is_dir():
                    shutil.rmtree(md_dir)
                    logger.info("已删除 MD 目录: %s", md_dir)
                # 4b. 删除 data_dir/{book_id}/ 下的跨书关系 JSON
                data_dir = Path(settings.data_dir) / book_id
                if data_dir.exists() and data_dir.is_dir():
                    shutil.rmtree(data_dir)
                    logger.info("已删除数据目录: %s", data_dir)
            except Exception as e:
                logger.warning("磁盘文件清理失败（不阻塞删除）: %s", e)

            # ── 5. 删除 MySQL 记录 ──
            async with async_session_factory() as session:
                await session.execute(
                    delete(MDVersion).where(MDVersion.book_id == book_id)
                )
                result = await session.execute(
                    delete(MDMetadata).where(MDMetadata.book_id == book_id)
                )
                if result.rowcount == 0:
                    raise HTTPException(status_code=404, detail="书籍不存在")
                await session.commit()

            # ── 6. 级联清理：清除其他书籍中引用本书的跨书条目 ──
            from src.config import settings as _cfg
            await _cascade_cleanup_stale_cross_refs(
                book_id, str(Path(_cfg.data_dir)),
            )

            return APIResponse.success(message="删除成功")
        except HTTPException:
            raise
        except Exception as e:
            logger.error("删除策管书籍失败: %s", e)
            raise HTTPException(status_code=500, detail=str(e))

    async def start_generation(self, book_id: str) -> APIResponse:
        """触发 AI 生成 — 启动独立 asyncio.Task。

        任务在后台运行（Phase 0→4 + 保存草稿），不受 SSE 连接影响。
        浏览器断开后任务继续执行，重新连接 SSE 可恢复进度。
        """
        try:
            from src.models.md_metadata import MDMetadata
            from src.core.database import async_session_factory
            from sqlalchemy import select

            # 检查是否已在运行
            if book_id in _running_tasks and not _running_tasks[book_id].done():
                return APIResponse.success(
                    message="任务已在运行中", data={"book_id": book_id, "status": "running"}
                )

            # 检查书籍是否绑定
            async with async_session_factory() as session:
                result = await session.execute(
                    select(MDMetadata).where(MDMetadata.book_id == book_id)
                )
                meta = result.scalar_one_or_none()
                if not meta:
                    raise HTTPException(status_code=404, detail="书籍未绑定")

                # 更新状态为生成中
                meta.status = "generating"
                await session.commit()

                book_title = meta.book_title

            # 初始化进度状态
            _progress_states[book_id] = {
                "book_id": book_id,
                "book_title": book_title,
                "status": "generating",
                "phase": "phase0_reading",
                "phase_label": "正在初始化...",
                "progress": 0,
                "chapters": [],
                "error": None,
            }
            _progress_events[book_id] = _asyncio.Event()

            # 启动独立任务
            task = _asyncio.create_task(
                _run_d2g_pipeline(book_id, book_title),
                name=f"d2g-{book_id}",
            )
            _running_tasks[book_id] = task
            task.add_done_callback(lambda t: _cleanup_task(book_id))

            logger.info("[生成流程] 独立任务已启动 book_id=%s", book_id)
            return APIResponse.success(
                message="生成任务已启动",
                data={"book_id": book_id, "status": "running"},
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error("启动生成失败: %s", e)
            raise HTTPException(status_code=500, detail=str(e))

    async def cancel_generation(self, book_id: str) -> APIResponse:
        """取消正在进行的生成任务。"""
        task = _running_tasks.get(book_id)
        if not task or task.done():
            _update_progress(book_id, status="cancelled", phase_label="任务已取消")
            return APIResponse.success(message="任务已结束", data={"book_id": book_id, "status": "cancelled"})
        task.cancel()
        logger.info("[生成流程] 收到取消请求 book_id=%s", book_id)
        return APIResponse.success(message="取消请求已发送", data={"book_id": book_id, "status": "cancelling"})

    async def generation_progress(self, book_id: str):
        """生成进度 SSE — 纯只读订阅，不驱动任何任务逻辑。

        只从共享状态 _progress_states 读取进度并推送。
        浏览器断开不影响后台任务。
        """
        from fastapi.responses import StreamingResponse

        async def event_stream():
            try:
                # 等待进度状态初始化（最多 10 秒）
                for _ in range(20):
                    if book_id in _progress_states:
                        break
                    await _asyncio.sleep(0.5)
                else:
                    # 没有运行中的任务 — 检查数据库是否有残留的 "generating" 状态
                    # （后端重启后内存状态丢失，但 DB 元数据仍标记为 generating）
                    try:
                        from src.models.md_metadata import MDMetadata
                        from src.core.database import async_session_factory
                        from sqlalchemy import select

                        async with async_session_factory() as session:
                            result = await session.execute(
                                select(MDMetadata).where(MDMetadata.book_id == book_id)
                            )
                            meta = result.scalar_one_or_none()
                            if meta and meta.status == "generating":
                                # 残留状态：任务已丢失，重置为 failed
                                meta.status = "failed"
                                await session.commit()
                                logger.warning(
                                    "[SSE] 检测到残留 generating 状态，已重置为 failed book_id=%s",
                                    book_id,
                                )
                                yield f"data: {json.dumps({'status': 'failed', 'error': '生成任务已中断（可能因服务重启），请重试'}, ensure_ascii=False)}\n\n"
                                return
                    except Exception as _db_exc:
                        logger.warning("[SSE] 检查 DB 状态失败: %s", _db_exc)

                    yield f"data: {json.dumps({'status': 'not_found', 'message': '任务未启动或已完成'})}\n\n"
                    return

                if book_id not in _progress_events:
                    _progress_events[book_id] = _asyncio.Event()

                # 如果进度是终态且无运行中任务，说明是旧残留，返回 not_found
                _state = _progress_states.get(book_id, {})
                _task = _running_tasks.get(book_id)
                if _state.get("status") in ("completed", "failed", "cancelled") and (
                    _task is None or _task.done()
                ):
                    _progress_states.pop(book_id, None)
                    _progress_events.pop(book_id, None)
                    yield f"data: {json.dumps({'status': 'not_found', 'message': '任务未启动或已完成'}, ensure_ascii=False)}\n\n"
                    return

                # 发送首条快照（当前状态）
                state = _progress_states[book_id]
                yield f"data: {json.dumps(state, ensure_ascii=False)}\n\n"

                # 轮询进度直到任务完成
                while True:
                    try:
                        evt = _progress_events.get(book_id)
                        if evt:
                            await _asyncio.wait_for(evt.wait(), timeout=15.0)
                            evt.clear()
                        else:
                            await _asyncio.sleep(1.0)
                    except _asyncio.TimeoutError:
                        pass  # 超时发送心跳

                    state = _progress_states.get(book_id, {})
                    yield f"data: {json.dumps(state, ensure_ascii=False)}\n\n"

                    if state.get("status") in ("completed", "failed", "cancelled"):
                        break

                    # 任务已完成但状态未更新
                    task = _running_tasks.get(book_id)
                    if task is None or task.done():
                        final = _progress_states.get(book_id, {})
                        if final.get("status") not in ("completed", "failed", "cancelled"):
                            final["status"] = "failed"
                            final["error"] = final.get("error") or "任务已结束"
                        yield f"data: {json.dumps(final, ensure_ascii=False)}\n\n"
                        break
            except Exception as _sse_exc:
                logger.warning("[SSE] event_stream 异常 book_id=%s: %s", book_id, _sse_exc)
                try:
                    yield f"data: {json.dumps({'status': 'failed', 'error': f'SSE 异常: {str(_sse_exc)[:100]}'})}\n\n"
                except Exception:
                    pass

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # ================================================================
    # 章节
    # ================================================================

    async def get_chapters(self, book_id: str) -> APIResponse:
        """获取书籍章节列表"""
        try:
            from src.models.md_metadata import MDMetadata
            from src.models.document import SourceDocument
            from src.core.database import async_session_factory
            from sqlalchemy import select

            async with async_session_factory() as session:
                # 查找策管元数据
                result = await session.execute(
                    select(MDMetadata).where(MDMetadata.book_id == book_id)
                )
                meta = result.scalar_one_or_none()
                if not meta:
                    raise HTTPException(status_code=404, detail="书籍未绑定")

                # 获取知识库文档信息
                doc_result = await session.execute(
                    select(SourceDocument).where(SourceDocument.id == book_id)
                )
                doc = doc_result.scalar_one_or_none()
                if not doc:
                    raise HTTPException(status_code=404, detail="知识库中未找到该书籍")

            # 返回章节信息（从数据库中读取）
            chapter_count = doc.chapter_count or 0
            chapters = []
            for i in range(chapter_count):
                chapters.append({
                    "id": f"{book_id}_ch{i:03d}",
                    "title": f"Chapter {i + 1}",
                    "order": i,
                    "token_count": 0,
                    "markdown_preview": "",
                })

            return APIResponse.success(data={
                "book_id": book_id,
                "book_title": meta.book_title,
                "chapters": chapters,
                "total_chapters": chapter_count,
                "total_tokens": 0,
            })
        except HTTPException:
            raise
        except Exception as e:
            logger.error("获取章节列表失败: %s", e)
            raise HTTPException(status_code=500, detail=str(e))

    # ================================================================
    # 绑定
    # ================================================================

    async def list_kb_books(self) -> APIResponse:
        """获取知识库中可绑定的 EPUB 书籍"""
        try:
            from src.models.document import SourceDocument, DocumentStatus
            from src.models.md_metadata import MDMetadata
            from src.core.database import async_session_factory
            from sqlalchemy import select

            async with async_session_factory() as session:
                # 查询知识库中的 EPUB 书籍
                result = await session.execute(
                    select(SourceDocument).where(
                        SourceDocument.file_type == "epub",
                        SourceDocument.status != DocumentStatus.ARCHIVED,
                    )
                )
                kb_books = result.scalars().all()

                # 查询已绑定的 book_id
                bound_result = await session.execute(select(MDMetadata.book_id))
                bound_ids = {row[0] for row in bound_result.all()}

            return APIResponse.success(data={
                "books": [
                    {
                        "id": book.id,
                        "title": book.title,
                        "author": book.author,
                        "file_type": book.file_type,
                        "file_hash": book.file_hash,
                        "chapter_count": book.chapter_count,
                        "status": book.status.value if hasattr(book.status, 'value') else book.status,
                        "created_at": book.created_at.isoformat() if book.created_at else None,
                        "bound": book.id in bound_ids,
                    }
                    for book in kb_books
                ],
                "total": len(kb_books),
            })
        except Exception as e:
            logger.error("获取知识库书籍失败: %s", e)
            raise HTTPException(status_code=500, detail=str(e))

    async def bind_book(self, req: BindBookRequest) -> APIResponse:
        """绑定知识库书籍到策管"""
        try:
            from src.models.md_metadata import MDMetadata
            from src.models.document import SourceDocument
            from src.core.database import async_session_factory
            from sqlalchemy import select

            async with async_session_factory() as session:
                # 检查知识库书籍是否存在
                result = await session.execute(
                    select(SourceDocument).where(SourceDocument.id == req.kb_book_id)
                )
                kb_book = result.scalar_one_or_none()
                if not kb_book:
                    raise HTTPException(status_code=404, detail="知识库中未找到该书籍")
                if kb_book.file_type != "epub":
                    raise HTTPException(status_code=400, detail="仅支持 EPUB 格式")

                # 检查是否已绑定
                existing = await session.execute(
                    select(MDMetadata).where(MDMetadata.book_id == req.kb_book_id)
                )
                if existing.scalar_one_or_none():
                    raise HTTPException(status_code=409, detail="该书籍已绑定到策管")

                # 创建策管元数据（状态为 bound，等待 AI 生成）
                meta_id = str(uuid.uuid4())
                meta = MDMetadata(
                    id=meta_id,
                    book_id=req.kb_book_id,
                    book_title=req.book_title,
                    author=req.author,
                    status="bound",
                    bind_source="kb_bind",
                    file_hash=kb_book.file_hash,
                    total_entities=0,
                    total_claims=0,
                    total_prescriptions=0,
                    neo4j_synced=0,
                )
                session.add(meta)
                # 不再创建示例草稿，等待用户触发 AI 生成
                await session.commit()

            logger.info("绑定书籍成功: %s -> %s", req.kb_book_id, meta_id)
            # 跨书分析由 AI 生成流程统一处理（Phase 5a），不在绑定时触发
            return APIResponse.success(data={"book_id": req.kb_book_id, "meta_id": meta_id})
        except HTTPException:
            raise
        except Exception as e:
            logger.error("绑定书籍失败: %s", e)
            raise HTTPException(status_code=500, detail=str(e))

    # ================================================================
    # 草稿
    # ================================================================

    async def list_drafts(
        self,
        status: Optional[str] = Query(None, description="按状态筛选: draft/reviewed/published"),
        book_id: Optional[str] = Query(None, description="按书籍筛选"),
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
    ) -> APIResponse:
        """获取草稿列表"""
        try:
            from src.models.md_metadata import MDMetadata
            from src.core.database import async_session_factory
            from sqlalchemy import select

            async with async_session_factory() as session:
                query = select(MDMetadata)
                if status:
                    query = query.where(MDMetadata.status == status)
                if book_id:
                    query = query.where(MDMetadata.book_id == book_id)
                query = query.offset((page - 1) * page_size).limit(page_size)

                result = await session.execute(query)
                drafts = result.scalars().all()

            return APIResponse.success(data={
                "drafts": [
                    {
                        "id": d.id,
                        "book_id": d.book_id,
                        "book_title": d.book_title,
                        "status": d.status,
                        "version": d.version,
                        "generated_at": d.created_at.isoformat() if d.created_at else None,
                        "reviewed_by": d.reviewed_by if hasattr(d, 'reviewed_by') else None,
                    }
                    for d in drafts
                ],
                "page": page,
                "page_size": page_size,
            })
        except HTTPException:
            raise
        except Exception as e:
            logger.error("获取草稿列表失败: %s", e)
            raise HTTPException(status_code=500, detail=str(e))

    async def get_draft(self, draft_id: str) -> APIResponse:
        """获取单个 MD 草稿内容"""
        try:
            from src.models.md_metadata import MDMetadata
            from src.models.md_version import MDVersion
            from src.core.database import async_session_factory
            from sqlalchemy import select

            async with async_session_factory() as session:
                result = await session.execute(
                    select(MDMetadata).where(MDMetadata.id == draft_id)
                )
                draft = result.scalar_one_or_none()
                if not draft:
                    raise HTTPException(status_code=404, detail="草稿不存在")

                content = ""
                if draft.current_version_id:
                    ver_result = await session.execute(
                        select(MDVersion).where(MDVersion.id == draft.current_version_id)
                    )
                    version = ver_result.scalar_one_or_none()
                    if version:
                        content = _read_md_file(version.md_path or "")

            return APIResponse.success(data={
                "id": draft.id,
                "book_id": draft.book_id,
                "book_title": draft.book_title,
                "status": draft.status,
                "version": draft.version,
                "content": content,
                "generated_at": draft.created_at.isoformat() if draft.created_at else None,
                "reviewed_at": draft.updated_at.isoformat() if draft.updated_at else None,
                "reviewed_by": draft.reviewed_by if hasattr(draft, 'reviewed_by') else None,
            })
        except HTTPException:
            raise
        except Exception as e:
            logger.error("获取草稿失败: %s", e)
            raise HTTPException(status_code=500, detail=str(e))

    async def update_draft(self, draft_id: str, body: dict) -> APIResponse:
        """保存审核修改"""
        try:
            from src.models.md_metadata import MDMetadata
            from src.models.md_version import MDVersion
            from src.core.database import async_session_factory
            from sqlalchemy import select

            content = body.get("content", "")

            async with async_session_factory() as session:
                result = await session.execute(
                    select(MDMetadata).where(MDMetadata.id == draft_id)
                )
                draft = result.scalar_one_or_none()
                if not draft:
                    raise HTTPException(status_code=404, detail="草稿不存在")

                if draft.current_version_id:
                    ver_result = await session.execute(
                        select(MDVersion).where(MDVersion.id == draft.current_version_id)
                    )
                    version = ver_result.scalar_one_or_none()
                    if version:
                        # 已有文件路径则覆盖写入，否则新创建
                        if version.md_path:
                            _write_md_file(draft.book_id, version.id, content)
                        else:
                            version.md_path = _write_md_file(draft.book_id, version.id, content)
                else:
                    # 创建新版本
                    version_id = str(uuid.uuid4())
                    md_path = _write_md_file(draft.book_id, version_id, content)
                    version = MDVersion(
                        id=version_id,
                        book_id=draft.book_id,
                        md_path=md_path,
                        version=1,
                    )
                    session.add(version)
                    draft.current_version_id = version_id

                await session.commit()

            return APIResponse.success(message="保存成功")
        except HTTPException:
            raise
        except Exception as e:
            logger.error("保存草稿失败: %s", e)
            raise HTTPException(status_code=500, detail=str(e))

    async def mark_reviewed(self, draft_id: str, body: dict) -> APIResponse:
        """标记已审核"""
        try:
            from src.models.md_metadata import MDMetadata
            from src.core.database import async_session_factory
            from sqlalchemy import select

            async with async_session_factory() as session:
                result = await session.execute(
                    select(MDMetadata).where(MDMetadata.id == draft_id)
                )
                draft = result.scalar_one_or_none()
                if not draft:
                    raise HTTPException(status_code=404, detail="草稿不存在")

                draft.status = "reviewed"
                if hasattr(draft, 'reviewed_by'):
                    draft.reviewed_by = body.get("reviewer", "admin")
                await session.commit()

            return APIResponse.success(message="已标记为已审核")
        except HTTPException:
            raise
        except Exception as e:
            logger.error("标记审核失败: %s", e)
            raise HTTPException(status_code=500, detail=str(e))

    async def publish_to_neo4j(self, draft_id: str) -> APIResponse:
        """入库 Neo4j"""
        try:
            from src.models.md_metadata import MDMetadata
            from src.models.md_version import MDVersion
            from src.core.database import async_session_factory
            from sqlalchemy import select

            async with async_session_factory() as session:
                result = await session.execute(
                    select(MDMetadata).where(MDMetadata.id == draft_id)
                )
                draft = result.scalar_one_or_none()
                if not draft:
                    raise HTTPException(status_code=404, detail="草稿不存在")

                if not draft.current_version_id:
                    raise HTTPException(status_code=400, detail="无草稿内容")

                ver_result = await session.execute(
                    select(MDVersion).where(MDVersion.id == draft.current_version_id)
                )
                version = ver_result.scalar_one_or_none()
                if not version:
                    raise HTTPException(status_code=404, detail="版本不存在")

            # 解析 MD → Cypher 并写入 Neo4j
            from src.core.knowledge_qa.neo4j.driver import get_neo4j_driver, neo4j_available
            if not neo4j_available():
                raise HTTPException(status_code=503, detail="Neo4j 未启用")

            from src.core.knowledge_qa.neo4j.md_parser import parse_md_to_cypher
            driver = get_neo4j_driver()
            md_content = _read_md_file(version.md_path or "")
            if not md_content:
                raise HTTPException(status_code=400, detail="MD 草稿内容为空，无法入库")
            parse_result = parse_md_to_cypher(md_content, draft.book_id)

            with driver.session() as session:
                for stmt in parse_result.cypher_statements:
                    session.run(stmt.query, stmt.params or {})

            # 更新状态
            async with async_session_factory() as session:
                result = await session.execute(
                    select(MDMetadata).where(MDMetadata.id == draft_id)
                )
                draft = result.scalar_one_or_none()
                if draft:
                    draft.status = "published"
                    await session.commit()

            # ── 回写实体/主张/处方计数到 MDMetadata ──
            try:
                # D2G 流水线用 SourceDocument.id 作为 Neo4j book_id，需要解析
                _neo4j_bid = draft.book_id
                if draft.file_hash:
                    from src.models.document import SourceDocument as _SD
                    async with async_session_factory() as _ses2:
                        _dr = await _ses2.execute(
                            select(_SD).where(_SD.file_hash == draft.file_hash))
                        _doc = _dr.scalar_one_or_none()
                        if _doc and _doc.id:
                            _neo4j_bid = _doc.id

                with driver.session() as _count_sess:
                    _ent_result = _count_sess.run(
                        "MATCH (ae) WHERE ae.book_id = $bid "
                        "RETURN count(ae) AS cnt",
                        bid=_neo4j_bid,
                    )
                    _ent_cnt = _ent_result.single()["cnt"]

                    _rel_result = _count_sess.run(
                        "MATCH (ae1)-[r]->(ae2) WHERE ae1.book_id = $bid AND ae2.book_id = $bid RETURN count(r) AS cnt",
                        bid=_neo4j_bid,
                    )
                    _rel_cnt = _rel_result.single()["cnt"]

                    _rx_result = _count_sess.run(
                        "MATCH (p:Prescription) WHERE p.book_id = $bid "
                        "RETURN count(p) AS cnt",
                        bid=_neo4j_bid,
                    )
                    _rx_cnt = _rx_result.single()["cnt"]

                async with async_session_factory() as _ses:
                    _r = await _ses.execute(
                        select(MDMetadata).where(MDMetadata.book_id == draft.book_id))
                    _m = _r.scalar_one_or_none()
                    if _m:
                        _m.total_entities = _ent_cnt
                        _m.total_claims = _rel_cnt
                        _m.total_prescriptions = _rx_cnt
                        await _ses.commit()
                logger.info(
                    "publish 计数已回写 book_id=%s (neo4j=%s): entities=%d, claims=%d, prescriptions=%d",
                    draft.book_id, _neo4j_bid, _ent_cnt, _rel_cnt, _rx_cnt,
                )
            except Exception as e:
                logger.warning("publish 计数回写失败（不阻塞主流程）: %s", e)

            # Phase 5b: 执行审核者跨书决策（实体合并 + 跨书关系建边）
            try:
                from src.core.knowledge_qa.neo4j.driver import get_async_neo4j_driver
                from src.core.knowledge_qa.neo4j.cross_book_phase5b import run_phase5b_execute_decisions

                async_driver = get_async_neo4j_driver()
                if async_driver:
                    phase5b_result = await run_phase5b_execute_decisions(
                        book_id=draft.book_id,
                        neo4j_driver=async_driver,
                    )
                    logger.info(
                        "Phase 5b 完成: book_id=%s, 合并=%d, SAME_AS=%d, 关系=%d",
                        draft.book_id,
                        phase5b_result.merged_count,
                        phase5b_result.same_as_count,
                        phase5b_result.relations_created,
                    )
            except Exception as e:
                logger.warning("Phase 5b 执行失败（不阻塞入库）: %s", e)

            return APIResponse.success(message="入库成功")
        except HTTPException:
            raise
        except Exception as e:
            logger.error("入库 Neo4j 失败: %s", e)
            raise HTTPException(status_code=500, detail=str(e))

    async def get_graph(
        self,
        book_id: Optional[str] = Query(None, description="单书 KG，不传则返回全景 KG"),
        limit: int = Query(500, ge=50, le=5000, description="返回节点数量上限"),
    ) -> APIResponse:
        """获取知识图谱可视化数据"""
        try:
            from src.core.knowledge_qa.neo4j.driver import get_neo4j_driver, neo4j_available
            if not neo4j_available():
                raise HTTPException(status_code=503, detail="Neo4j 不可用")

            driver = get_neo4j_driver()
            nodes = []
            edges = []
            edge_limit = int(limit * 2.5)

            with driver.session() as session:
                # 查询节点
                if book_id:
                    node_query = """
                    MATCH (ae) WHERE ae.book_id = $book_id
                    RETURN ae.name AS id, ae.name AS label, labels(ae)[0] AS type,
                           COALESCE(ae.description, '') AS description,
                           COALESCE(ae.severity, '') AS severity,
                           COALESCE(ae.category, '') AS category,
                           COALESCE(ae.brain_regions, '') AS brain_regions,
                           COALESCE(ae.evidence, '') AS evidence,
                           COALESCE(ae.key_figures, '') AS key_figures,
                           COALESCE(ae.mechanism_detail, '') AS mechanism_detail
                    UNION
                    MATCH (b:Book {book_id: $book_id})
                    RETURN b.book_id AS id, COALESCE(b.title, b.book_id) AS label, 'Book' AS type, '' AS description,
                           '' AS severity, '' AS category, '' AS brain_regions,
                           '' AS evidence, '' AS key_figures, '' AS mechanism_detail
                    """
                    node_result = session.run(node_query + " LIMIT $lim", book_id=book_id, lim=limit)
                else:
                    node_query = """
                    MATCH (n) WHERE n:Book OR n:Problem OR n:Solution OR n:BrainRegion
                        OR n:Exercise OR n:Prescription OR n:RootCause OR n:AutoEntity
                        OR n:AutoCommunity OR n:CognitiveProcess OR n:Theory
                        OR n:Mechanism OR n:DevelopmentalStage OR n:Strategy
                        OR n:KeyInsight OR n:ResearchFinding
                        OR n:Risk OR n:ChildProfile OR n:Chapter
                        OR n:Person OR n:Location OR n:Object
                        OR n:AssessmentTool OR n:Symptom OR n:Intervention OR n:Diagnosis
                        OR n:Organization OR n:Study OR n:Neurotransmitter
                        OR n:Milestone OR n:Environment OR n:CustomRule
                    RETURN COALESCE(n.name, n.book_id, n.node_id) AS id,
                           COALESCE(n.name, n.title, n.label) AS label,
                           labels(n)[0] AS type,
                           COALESCE(n.description, '') AS description,
                           COALESCE(n.severity, '') AS severity,
                           COALESCE(n.category, '') AS category,
                           COALESCE(n.brain_regions, '') AS brain_regions,
                           COALESCE(n.evidence, '') AS evidence,
                           COALESCE(n.key_figures, '') AS key_figures,
                           COALESCE(n.mechanism_detail, '') AS mechanism_detail
                    LIMIT $lim
                    """
                    node_result = session.run(node_query, lim=limit)

                for record in node_result:
                    node_data = {
                        "id": record["id"],
                        "label": record["label"],
                        "type": record["type"],
                        "description": record["description"],
                    }
                    # 附加元数据字段
                    for field in ("severity", "category", "brain_regions",
                                  "evidence", "key_figures", "mechanism_detail"):
                        val = record.get(field, "")
                        if val:
                            node_data[field] = val
                    nodes.append(node_data)

                # 查询关系
                if book_id:
                    edge_query = """
                    MATCH (ae1)-[r]->(ae2)
                    WHERE ae1.book_id = $book_id AND ae2.book_id = $book_id
                    RETURN ae1.name AS source, ae2.name AS target,
                           COALESCE(r.relationship_type, type(r)) AS type,
                           COALESCE(r.weight, 1) AS weight,
                           COALESCE(r.label, r.relationship_type, type(r)) AS label,
                           COALESCE(r.evidence, '') AS evidence,
                           COALESCE(r.confidence, '') AS confidence
                    """
                    edge_result = session.run(edge_query + " LIMIT $lim", book_id=book_id, lim=edge_limit)
                else:
                    edge_query = """
                    MATCH (a)-[r]->(b)
                    RETURN a.name AS source, b.name AS target,
                           COALESCE(r.relationship_type, type(r)) AS type,
                           COALESCE(r.weight, 1) AS weight,
                           COALESCE(r.label, r.relationship_type, type(r)) AS label,
                           COALESCE(r.evidence, '') AS evidence,
                           COALESCE(r.confidence, '') AS confidence
                    LIMIT $lim
                    """
                    edge_result = session.run(edge_query, lim=edge_limit)

                for record in edge_result:
                    edge_data = {
                        "source": record["source"],
                        "target": record["target"],
                        "type": record["type"],
                        "weight": record["weight"],
                        "label": record.get("label", record["type"]),
                    }
                    if record.get("evidence"):
                        edge_data["evidence"] = record["evidence"]
                    if record.get("confidence"):
                        edge_data["confidence"] = record["confidence"]
                    edges.append(edge_data)

            return APIResponse.success(data={"nodes": nodes, "edges": edges})
        except HTTPException:
            raise
        except Exception as e:
            logger.error("获取 KG 数据失败: %s", e)
            raise HTTPException(status_code=500, detail=str(e))

    async def export_cypher(
        self,
        book_id: Optional[str] = Query(None),
    ) -> APIResponse:
        """导出图谱为 Cypher 查询语句"""
        try:
            from src.core.knowledge_qa.neo4j.driver import get_neo4j_driver, neo4j_available
            if not neo4j_available():
                raise HTTPException(status_code=503, detail="Neo4j 不可用")

            driver = get_neo4j_driver()
            statements = []

            with driver.session() as session:
                if book_id:
                    query = """
                    MATCH (ae) WHERE ae.book_id = $book_id
                    OPTIONAL MATCH (ae)-[r]->(ae2)
                    RETURN ae, r, ae2
                    """
                    result = session.run(query, book_id=book_id)
                else:
                    query = """
                    MATCH (n) WHERE n:AutoEntity OR n:Book
                    OPTIONAL MATCH (n)-[r:RELATES_TO]->(m)
                    RETURN n, r, m
                    LIMIT 500
                    """
                    result = session.run(query)

                for record in result:
                    # Generate MERGE statements
                    node = record.get("ae") or record.get("n")
                    if node:
                        name = node.get("name", "").replace("'", "\\'")
                        ntype = list(node.labels)[0] if node.labels else "Node"
                        desc = node.get("description", "").replace("'", "\\'")
                        statements.append(
                            f"MERGE (n:{ntype} {{name: '{name}'}}) SET n.description = '{desc}';"
                        )

            return APIResponse.success(data={
                "statements": statements,
                "count": len(statements),
            })
        except HTTPException:
            raise
        except Exception as e:
            logger.error("导出 Cypher 失败: %s", e)
            raise HTTPException(status_code=500, detail=str(e))


    async def clear_graph(
        self,
        book_id: Optional[str] = Query(None, description="仅清空指定书籍，留空清空全部"),
    ) -> APIResponse:
        """清空 Neo4j 知识图谱（全部或单书）"""
        try:
            from src.core.knowledge_qa.neo4j.driver import get_neo4j_driver, neo4j_available
            if not neo4j_available():
                raise HTTPException(status_code=503, detail="Neo4j 未启用")

            driver = get_neo4j_driver()
            with driver.session() as session:
                if book_id:
                    result = session.run(
                        "MATCH (n {book_id: $book_id}) "
                        "WITH count(n) AS cnt "
                        "MATCH (n {book_id: $book_id}) DETACH DELETE n "
                        "RETURN cnt",
                        book_id=book_id,
                    )
                    deleted = result.single()["cnt"]
                    return APIResponse.success(data={
                        "message": f"已清空书籍 {book_id} 的知识图谱",
                        "deleted_nodes": deleted,
                    })
                else:
                    result = session.run("MATCH (n) RETURN count(n) AS cnt")
                    total = result.single()["cnt"]
                    session.run("MATCH (n) DETACH DELETE n")
                    return APIResponse.success(data={
                        "message": "已清空全部知识图谱",
                        "deleted_nodes": total,
                    })
        except HTTPException:
            raise
        except Exception as e:
            logger.error("清空图谱失败: %s", e)
            raise HTTPException(status_code=500, detail=str(e))


    async def cross_book_pairs(
        self,
        book_ids: Optional[str] = Query(None, description="comma separated book_id list"),
    ) -> APIResponse:
        """Get cross-book relationship pairs for multi-book compare mode"""
        try:
            from src.core.knowledge_qa.neo4j.driver import get_neo4j_driver, neo4j_available
            if not neo4j_available():
                return APIResponse.success(data={"pairs": [], "relations": []})

            driver = get_neo4j_driver()
            pairs = []
            relations = []

            ids = [bid.strip() for bid in book_ids.split(",")] if book_ids else []

            with driver.session() as session:
                if len(ids) >= 2:
                    query = (
                        "MATCH (e1:AutoEntity)-[r:RELATES_TO]->(e2:AutoEntity) "
                        "WHERE e1.book_id = $id1 AND e2.book_id = $id2 "
                        "RETURN e1.name AS source, e2.name AS target, "
                        "r.relationship_type AS type, r.weight AS weight, "
                        "b1.book_id AS book1, b2.book_id AS book2"
                    )
                    result = session.run(query, id1=ids[0], id2=ids[1])
                    for record in result:
                        relations.append({
                            "source": record["source"],
                            "target": record["target"],
                            "type": record["type"],
                            "weight": record["weight"],
                            "book1": record["book1"],
                            "book2": record["book2"],
                        })

                    summary_query = (
                        "MATCH (e1:AutoEntity)-[r:RELATES_TO]->(e2:AutoEntity) "
                        "WHERE e1.book_id = $id1 AND e2.book_id = $id2 "
                        "RETURN r.relationship_type AS type, count(r) AS cnt"
                    )
                    summary_result = session.run(summary_query, id1=ids[0], id2=ids[1])
                    for record in summary_result:
                        pairs.append({"type": record["type"], "count": record["cnt"]})
                else:
                    query = (
                        "MATCH (e1:AutoEntity)-[r:RELATES_TO]->(e2:AutoEntity) "
                        "WHERE e1.book_id <> e2.book_id "
                        "WHERE b1 <> b2 "
                        "RETURN e1.name AS source, e2.name AS target, "
                        "r.relationship_type AS type, r.weight AS weight, "
                        "b1.book_id AS book1, b2.book_id AS book2 LIMIT 100"
                    )
                    result = session.run(query)
                    for record in result:
                        relations.append({
                            "source": record["source"],
                            "target": record["target"],
                            "type": record["type"],
                            "weight": record["weight"],
                            "book1": record["book1"],
                            "book2": record["book2"],
                        })

            return APIResponse.success(data={"pairs": pairs, "relations": relations})
        except Exception as e:
            logger.error("Cross-book pairs query failed: %s", e)
            raise HTTPException(status_code=500, detail=str(e))

    async def get_pending_queue(
        self,
        status: Optional[str] = Query(None),
        book_id: Optional[str] = Query(None),
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
    ) -> APIResponse:
        """获取待提炼队列"""
        try:
            from src.core.knowledge_qa.neo4j.pending_queue import get_pending_items
            items = await get_pending_items(page=page, page_size=page_size)
            return APIResponse.success(data=items)
        except Exception as e:
            logger.error("获取待提炼队列失败: %s", e)
            raise HTTPException(status_code=500, detail=str(e))


    # ── 跨书融合审核者决策 API ──────────────────────────────────

    async def get_cross_book_relations(
        self,
        book_id: str,
    ) -> APIResponse:
        """获取跨书融合分析结果（Phase 5a 输出）。"""
        try:
            # 从 JSON 文件读取（主要存储方式）
            from src.config import settings
            json_path = Path(settings.data_dir) / book_id / "cross_book_relations.json"
            if json_path.exists():
                with open(json_path, "r", encoding="utf-8") as f:
                    return APIResponse.success(data=json.load(f))

            # 尝试从 Redis 读取（备选）
            try:
                import redis
                from src.config.modules.redis import get_sync_redis
                r = get_sync_redis()
                key = f"d2g:cross_analysis:{book_id}"
                data = r.get(key)
                if data:
                    return APIResponse.success(data=json.loads(data))
            except Exception:
                pass

            return APIResponse.success(data=None, message="未找到跨书分析结果")
        except Exception as e:
            logger.error("获取跨书关系失败: %s", e)
            raise HTTPException(status_code=500, detail=str(e))

    async def update_cross_book_decision(
        self,
        request: CrossBookDecisionRequest,
    ) -> APIResponse:
        """更新审核者对某个跨书匹配/关系的决策。"""
        book_id = request.book_id
        decision_type = request.decision_type
        index = request.index
        decision = request.decision
        custom_type = request.custom_type
        try:
            from src.config import settings
            json_path = Path(settings.data_dir) / book_id / "cross_book_relations.json"

            # 优先从 JSON 文件读取
            if not json_path.exists():
                raise HTTPException(status_code=404, detail="未找到跨书分析结果")

            with open(json_path, "r", encoding="utf-8") as f:
                result = json.load(f)

            # 更新决策
            if decision_type == "entity_match":
                matches = result.get("entity_matches", [])
                if 0 <= index < len(matches):
                    matches[index]["reviewer_decision"] = decision
                else:
                    raise HTTPException(status_code=400, detail="索引超出范围")
            elif decision_type == "cross_relation":
                relations = result.get("cross_relations", [])
                if 0 <= index < len(relations):
                    relations[index]["reviewer_decision"] = decision
                    if custom_type:
                        relations[index]["relation_type"] = custom_type
                else:
                    raise HTTPException(status_code=400, detail="索引超出范围")
            else:
                raise HTTPException(status_code=400, detail="无效的 decision_type")

            # 保存回 JSON 文件（原子写入，修复 RACE-2）
            import os as _os
            tmp_path = json_path.with_suffix(".json.tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            _os.replace(str(tmp_path), str(json_path))

            # 可选：同步到 Redis 缓存
            try:
                import redis
                from src.config.modules.redis import get_sync_redis
                r = get_sync_redis()
                key = f"d2g:cross_analysis:{book_id}"
                r.setex(key, 86400 * 30, json.dumps(result, ensure_ascii=False))
            except Exception:
                pass  # Redis 不可用不影响主流程

            return APIResponse.success(message="决策已更新")
        except HTTPException:
            raise
        except Exception as e:
            logger.error("更新跨书决策失败: %s", e)
            raise HTTPException(status_code=500, detail=str(e))

    async def batch_update_cross_book_decisions(
        self,
        request: CrossBookBatchDecisionRequest,
    ) -> APIResponse:
        """批量更新审核者决策。"""
        book_id = request.book_id
        decision_type = request.decision_type
        indices = request.indices
        decision = request.decision
        try:
            from src.config import settings
            json_path = Path(settings.data_dir) / book_id / "cross_book_relations.json"

            # 优先从 JSON 文件读取
            if not json_path.exists():
                raise HTTPException(status_code=404, detail="未找到跨书分析结果")

            with open(json_path, "r", encoding="utf-8") as f:
                result = json.load(f)

            # 批量更新
            if decision_type == "entity_match":
                matches = result.get("entity_matches", [])
                for idx in indices:
                    if 0 <= idx < len(matches):
                        matches[idx]["reviewer_decision"] = decision
            elif decision_type == "cross_relation":
                relations = result.get("cross_relations", [])
                for idx in indices:
                    if 0 <= idx < len(relations):
                        relations[idx]["reviewer_decision"] = decision
            else:
                raise HTTPException(status_code=400, detail="无效的 decision_type")

            # 保存回 JSON 文件（原子写入，修复 RACE-2）
            import os as _os
            tmp_path = json_path.with_suffix(".json.tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            _os.replace(str(tmp_path), str(json_path))

            # 可选：同步到 Redis 缓存
            try:
                import redis
                from src.config.modules.redis import get_sync_redis
                r = get_sync_redis()
                key = f"d2g:cross_analysis:{book_id}"
                r.setex(key, 86400 * 30, json.dumps(result, ensure_ascii=False))
            except Exception:
                pass  # Redis 不可用不影响主流程

            return APIResponse.success(message=f"已批量更新 {len(indices)} 条决策")
        except HTTPException:
            raise
        except Exception as e:
            logger.error("批量更新跨书决策失败: %s", e)
            raise HTTPException(status_code=500, detail=str(e))

    # ── 全局跨书分析 + 手动重试（Phase 4） ──────────────────

    async def analyze_all_books(
        self,
        force: bool = Query(False, description="是否全量重分析（忽略已有 JSON 文件）"),
    ) -> APIResponse:
        """对所有 status=published 的书籍执行成对跨书分析。

        增量策略：已有有效 JSON 文件的书籍对跳过，除非传入 force=true。
        """
        try:
            from src.models.md_metadata import MDMetadata
            from src.core.database import async_session_factory
            from sqlalchemy import select

            async with async_session_factory() as session:
                result = await session.execute(
                    select(MDMetadata).where(MDMetadata.status == "published")
                )
                books = result.scalars().all()

            if len(books) < 2:
                return APIResponse.success(data={
                    "message": "需要至少 2 本已入库的书籍",
                    "total_pairs": 0,
                })

            from src.config import settings as _cfg
            from src.core.knowledge_qa.neo4j.driver import get_async_neo4j_driver
            from src.core.knowledge_qa.neo4j.cross_book_phase5a import (
                run_phase5a_cross_book_analysis,
            )
            from src.utils.di import get_embedding_helper
            from src.core.llm.factory import LLMServiceFactoryCompat

            neo4j_driver = get_async_neo4j_driver()
            emb_helper = get_embedding_helper()
            llm_factory = LLMServiceFactoryCompat()
            llm_adapter = llm_factory.create(
                model_name=_cfg.d2g_model, max_tokens=_cfg.d2g_max_tokens,
            )
            _output_dir = str(Path(_cfg.data_dir))

            pairs = []
            for i, book_i in enumerate(books):
                for book_j in books[i + 1:]:
                    json_path = Path(_output_dir) / book_i.book_id / "cross_book_relations.json"
                    if not force and json_path.exists():
                        pairs.append({
                            "book_id": book_i.book_id,
                            "target_book_id": book_j.book_id,
                            "status": "skipped",
                        })
                        continue
                    pairs.append({
                        "book_id": book_i.book_id,
                        "target_book_id": book_j.book_id,
                        "status": "pending",
                    })

            # 并行分析（semaphore 控流）
            sem = _asyncio.Semaphore(2)

            async def analyze_pair(pair):
                if pair["status"] == "skipped":
                    return pair
                async with sem:
                    try:
                        analysis = await run_phase5a_cross_book_analysis(
                            book_id=pair["book_id"],
                            neo4j_driver=neo4j_driver,
                            embedding_helper=emb_helper,
                            llm_client=llm_adapter,
                            output_dir=_output_dir,
                        )
                        pair["status"] = "completed"
                        pair["entity_matches"] = analysis.match_candidates_count
                        pair["cross_relations"] = analysis.relation_candidates_count
                    except Exception as e:
                        pair["status"] = "failed"
                        pair["error"] = str(e)[:200]
                return pair

            results = await _asyncio.gather(*[analyze_pair(p) for p in pairs])
            completed = sum(1 for r in results if r["status"] == "completed")
            skipped = sum(1 for r in results if r["status"] == "skipped")
            failed = sum(1 for r in results if r["status"] == "failed")

            return APIResponse.success(data={
                "total_pairs": len(results),
                "analyzed": completed,
                "skipped": skipped,
                "failed": failed,
                "results": results,
            })
        except Exception as e:
            logger.error("全局跨书分析失败: %s", e)
            raise HTTPException(status_code=500, detail=str(e))

    async def retry_cross_book_analysis(self, book_id: str) -> APIResponse:
        """手动触发单书的 Phase 5a 跨书分析重试。"""
        try:
            from src.models.md_metadata import MDMetadata
            from src.core.database import async_session_factory
            from sqlalchemy import select

            async with async_session_factory() as session:
                result = await session.execute(
                    select(MDMetadata).where(MDMetadata.book_id == book_id)
                )
                meta = result.scalar_one_or_none()
                if not meta:
                    raise HTTPException(status_code=404, detail="书籍不存在")
                if meta.status != "published":
                    raise HTTPException(status_code=400, detail="仅已入库书籍可重试跨书分析")

            from src.config import settings as _cfg
            from src.core.knowledge_qa.neo4j.driver import get_async_neo4j_driver
            from src.core.knowledge_qa.neo4j.cross_book_phase5a import (
                run_phase5a_cross_book_analysis,
            )
            from src.utils.di import get_embedding_helper
            from src.core.llm.factory import LLMServiceFactoryCompat

            neo4j_driver = get_async_neo4j_driver()
            emb_helper = get_embedding_helper()
            llm_factory = LLMServiceFactoryCompat()
            llm_adapter = llm_factory.create(
                model_name=_cfg.d2g_model, max_tokens=_cfg.d2g_max_tokens,
            )
            _output_dir = str(Path(_cfg.data_dir))

            analysis = await run_phase5a_cross_book_analysis(
                book_id=book_id,
                neo4j_driver=neo4j_driver,
                embedding_helper=emb_helper,
                llm_client=llm_adapter,
                output_dir=_output_dir,
            )

            return APIResponse.success(data={
                "book_id": book_id,
                "entity_matches": analysis.match_candidates_count,
                "cross_relations": analysis.relation_candidates_count,
            })
        except HTTPException:
            raise
        except Exception as e:
            logger.error("跨书分析重试失败: %s", e)
            raise HTTPException(status_code=500, detail=str(e))
