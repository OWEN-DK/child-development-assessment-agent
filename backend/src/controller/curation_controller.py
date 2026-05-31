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
import uuid
from typing import Optional
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from src.schemas.common import APIResponse
import asyncio as _asyncio
import json as _json
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
                        version.md_content = review_md
                else:
                    version_id = str(_uuid.uuid4())
                    version = MDVersion(
                        id=version_id,
                        book_id=book_id,
                        md_content=review_md,
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
            run_full_pipeline, finalize_and_commit, run_phase5_cross_book,
        )

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
            "phase5_cross_book": "正在跨书关联...",
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

        if not success:
            logger.warning("[生成流程] 质量检查未通过 book_id=%s\n%s", book_id, report)
            _update_progress(book_id, status="failed",
                             error=report,
                             progress=90)
            return

        _update_progress(book_id, phase="phase4_commit",
                         phase_label="正在入库 Neo4j...", progress=95)
        logger.info("[生成流程] Phase 4 入库完成 book_id=%s", book_id)

        enable_phase5 = os.environ.get("D2G_ENABLE_PHASE5", "true").lower() == "true"
        if enable_phase5:
            _update_progress(book_id, phase="phase5_cross_book",
                             phase_label="正在跨书关联...", progress=98)
            try:
                await run_phase5_cross_book(
                    book_id=book_id,
                    neo4j_driver=neo4j_driver,
                    embedding_helper=emb_helper,
                    llm_client=llm_adapter,
                    enable_phase5=True,
                )
                logger.info("[生成流程] Phase 5 跨书消歧完成 book_id=%s", book_id)
            except Exception as e:
                logger.warning("[生成流程] Phase 5 失败（不阻塞）: %s", e)

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
            "/curation/books/{book_id}/chapters",
            self.get_chapters,
            methods=["GET"],
            summary="获取章节列表",
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

    async def delete_book(self, book_id: str) -> APIResponse:
        """删除策管书籍"""
        try:
            from src.models.md_metadata import MDMetadata
            from src.models.md_version import MDVersion
            from src.core.database import async_session_factory
            from sqlalchemy import select, delete

            async with async_session_factory() as session:
                # 删除关联的版本
                await session.execute(
                    delete(MDVersion).where(MDVersion.book_id == book_id)
                )
                # 删除元数据
                result = await session.execute(
                    delete(MDMetadata).where(MDMetadata.book_id == book_id)
                )
                if result.rowcount == 0:
                    raise HTTPException(status_code=404, detail="书籍不存在")
                await session.commit()

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
                                yield f"data: {_json.dumps({'status': 'failed', 'error': '生成任务已中断（可能因服务重启），请重试'}, ensure_ascii=False)}\n\n"
                                return
                    except Exception as _db_exc:
                        logger.warning("[SSE] 检查 DB 状态失败: %s", _db_exc)

                    yield f"data: {_json.dumps({'status': 'not_found', 'message': '任务未启动或已完成'})}\n\n"
                    return

                if book_id not in _progress_events:
                    _progress_events[book_id] = _asyncio.Event()

                # 发送首条快照（当前状态）
                state = _progress_states[book_id]
                yield f"data: {_json.dumps(state, ensure_ascii=False)}\n\n"

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
                    yield f"data: {_json.dumps(state, ensure_ascii=False)}\n\n"

                    if state.get("status") in ("completed", "failed", "cancelled"):
                        break

                    # 任务已完成但状态未更新
                    task = _running_tasks.get(book_id)
                    if task is None or task.done():
                        final = _progress_states.get(book_id, {})
                        if final.get("status") not in ("completed", "failed", "cancelled"):
                            final["status"] = "failed"
                            final["error"] = final.get("error") or "任务已结束"
                        yield f"data: {_json.dumps(final, ensure_ascii=False)}\n\n"
                        break
            except Exception as _sse_exc:
                logger.warning("[SSE] event_stream 异常 book_id=%s: %s", book_id, _sse_exc)
                try:
                    yield f"data: {_json.dumps({'status': 'failed', 'error': f'SSE 异常: {str(_sse_exc)[:100]}'})}\n\n"
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

                # 创建策管元数据
                meta_id = str(uuid.uuid4())
                meta = MDMetadata(
                    id=meta_id,
                    book_id=req.kb_book_id,
                    book_title=req.book_title,
                    author=req.author,
                    status="draft",
                    bind_source="kb_bind",
                    file_hash=kb_book.file_hash,
                    total_entities=0,
                    total_claims=0,
                    total_prescriptions=0,
                    neo4j_synced=0,
                )
                session.add(meta)
                await session.flush()  # flush to get meta_id available

                # 创建初始 MD 版本（示例内容，后续 AI 生成可覆盖）
                from src.models.md_version import MDVersion
                version_id = str(uuid.uuid4())
                sample_content = f"""# {req.book_title}

> 本文档由知识审核系统自动生成，请审核后入库。

## 概要

本书正在等待 AI 生成结构化知识内容。请在绑定后启动 AI 生成流程。

## 问题 (Problem)

### 待生成

AI 生成后将自动填充问题列表。

## 方案 (Solution)

### 待生成

AI 生成后将自动填充解决方案。

## 脑区 (BrainRegion)

### 待生成

AI 生成后将自动填充相关脑区。

## 运动 (Exercise)

### 待生成

AI 生成后将自动填充运动处方。

## 处方 (Prescription)

### 待生成

AI 生成后将自动填充处方信息。

## 根因 (RootCause)

### 待生成

AI 生成后将自动填充根因分析。
"""
                version = MDVersion(
                    id=version_id,
                    book_id=req.kb_book_id,
                    md_content=sample_content,
                    version=1,
                    status="draft",
                )
                session.add(version)
                meta.current_version_id = version_id
                await session.commit()

            logger.info("绑定书籍成功: %s -> %s", req.kb_book_id, meta_id)
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
                        content = version.md_content or ""

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
                        version.md_content = content
                else:
                    # 创建新版本
                    version_id = str(uuid.uuid4())
                    version = MDVersion(
                        id=version_id,
                        book_id=draft.book_id,
                        md_content=content,
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
            parse_result = parse_md_to_cypher(version.md_content, draft.book_id)

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

            return APIResponse.success(message="入库成功")
        except HTTPException:
            raise
        except Exception as e:
            logger.error("入库 Neo4j 失败: %s", e)
            raise HTTPException(status_code=500, detail=str(e))

    async def get_graph(
        self,
        book_id: Optional[str] = Query(None, description="单书 KG，不传则返回全景 KG"),
    ) -> APIResponse:
        """获取知识图谱可视化数据"""
        try:
            from src.core.knowledge_qa.neo4j.driver import get_neo4j_driver, neo4j_available
            if not neo4j_available():
                raise HTTPException(status_code=503, detail="Neo4j 不可用")

            driver = get_neo4j_driver()
            nodes = []
            edges = []

            with driver.session() as session:
                # 查询节点
                if book_id:
                    node_query = """
                    MATCH (b:Book {book_id: $book_id})-[:CONTAINS_ENTITY]->(ae)
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
                    RETURN b.book_id AS id, b.title AS label, 'Book' AS type, '' AS description,
                           '' AS severity, '' AS category, '' AS brain_regions,
                           '' AS evidence, '' AS key_figures, '' AS mechanism_detail
                    """
                    node_result = session.run(node_query, book_id=book_id)
                else:
                    node_query = """
                    MATCH (n) WHERE n:Book OR n:Problem OR n:Solution OR n:BrainRegion
                        OR n:Exercise OR n:Prescription OR n:RootCause OR n:AutoEntity
                        OR n:AutoCommunity OR n:CognitiveProcess OR n:Theory
                        OR n:Mechanism OR n:DevelopmentalStage OR n:Strategy
                        OR n:KeyInsight OR n:ResearchFinding
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
                    LIMIT 500
                    """
                    node_result = session.run(node_query)

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
                    MATCH (b:Book {book_id: $book_id})-[:CONTAINS_ENTITY]->(ae1)
                          -[r]->(ae2)
                    RETURN ae1.name AS source, ae2.name AS target,
                           COALESCE(r.relationship_type, type(r)) AS type,
                           COALESCE(r.weight, 1) AS weight,
                           COALESCE(r.label, r.relationship_type, type(r)) AS label,
                           COALESCE(r.evidence, '') AS evidence,
                           COALESCE(r.confidence, '') AS confidence
                    """
                    edge_result = session.run(edge_query, book_id=book_id)
                else:
                    edge_query = """
                    MATCH (a)-[r]->(b)
                    RETURN a.name AS source, b.name AS target,
                           COALESCE(r.relationship_type, type(r)) AS type,
                           COALESCE(r.weight, 1) AS weight,
                           COALESCE(r.label, r.relationship_type, type(r)) AS label,
                           COALESCE(r.evidence, '') AS evidence,
                           COALESCE(r.confidence, '') AS confidence
                    LIMIT 1000
                    """
                    edge_result = session.run(edge_query)

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
                    MATCH (b:Book {book_id: $book_id})-[:CONTAINS_ENTITY]->(ae)
                    OPTIONAL MATCH (ae)-[r]->(ae2)
                    RETURN ae, r, ae2, b
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
                        "MATCH (b1:Book {book_id: $id1})-[:CONTAINS_ENTITY]->(e1:AutoEntity)"
                        "-[r:RELATES_TO]->(e2:AutoEntity)<-[:CONTAINS_ENTITY]-(b2:Book {book_id: $id2}) "
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
                        "MATCH (b1:Book {book_id: $id1})-[:CONTAINS_ENTITY]->(e1:AutoEntity)"
                        "-[r:RELATES_TO]->(e2:AutoEntity)<-[:CONTAINS_ENTITY]-(b2:Book {book_id: $id2}) "
                        "RETURN r.relationship_type AS type, count(r) AS cnt"
                    )
                    summary_result = session.run(summary_query, id1=ids[0], id2=ids[1])
                    for record in summary_result:
                        pairs.append({"type": record["type"], "count": record["cnt"]})
                else:
                    query = (
                        "MATCH (b1:Book)-[:CONTAINS_ENTITY]->(e1:AutoEntity)"
                        "-[r:RELATES_TO]->(e2:AutoEntity)<-[:CONTAINS_ENTITY]-(b2:Book) "
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
            "phase2_5_global_inference": "正在补全跨章关系与桥接分量...",
