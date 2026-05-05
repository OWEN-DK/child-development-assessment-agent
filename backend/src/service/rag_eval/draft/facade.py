"""DraftEngineFacade - 草稿引擎门面"""

import asyncio
import re
from typing import ClassVar, Optional

from src.schemas.rag_eval.draft import (
    DraftGenerationConfig, DraftList, DraftRead, DraftReview, DraftUpdate,
)
from src.schemas.rag_eval.test_case import TestCaseRead
from src.config.core.manager import ConfigManager
from src.models.rag_eval.draft import TestCaseDraft
from src.models.rag_eval.enums import TestCaseStatus
from src.repository.rag_eval.draft_repository import DraftRepository
from src.repository.rag_eval.test_case_repository import TestCaseRepository
from src.repository.document_repository import SourceDocumentRepository
from src.service.rag_eval.draft.book_analyzer import BookMetadataAnalyzer
from src.service.rag_eval.draft.deduplicator import DraftDeduplicator
from src.service.rag_eval.draft.faithfulness_checker import FaithfulnessChecker
from src.service.rag_eval.draft.generator import DraftGenerator
from src.service.task_sse_publisher import TaskSsePublisher
from src.utils.id_generator import generate_prefixed_id
from src.utils.logger import logger
from src.utils.orm_mapper import OrmMapper


class DraftEngineFacade:
    """草稿引擎门面——流水线化生成与忠诚度检查"""

    _SKIP_PATTERNS: ClassVar[list[str]] = [
        "目录", "版权", "版权所有", "出版信息", "前言", "序言",
        "ISBN", "责任编辑", "封面设计", "版次", "印次",
    ]

    def __init__(
        self, draft_generator: DraftGenerator, faithfulness_checker: FaithfulnessChecker,
        deduplicator: DraftDeduplicator, book_analyzer: BookMetadataAnalyzer,
        draft_repository: DraftRepository, test_case_repository: TestCaseRepository,
        source_document_repository: SourceDocumentRepository,
        config_cache: Optional[ConfigManager] = None, async_task_manager=None,
    ):
        from src.core.async_task import AsyncTaskManager
        self._gen, self._faith, self._dedup = draft_generator, faithfulness_checker, deduplicator
        self._analyzer, self._draft_repo, self._tc_repo = book_analyzer, draft_repository, test_case_repository
        self._doc_repo = source_document_repository
        self._config = config_cache or ConfigManager()
        self._async = async_task_manager or AsyncTaskManager()

    # ── 后台生成 ──

    async def start_generation(self, source_document_id: str, config: DraftGenerationConfig = None) -> str:
        if not self._async:
            raise RuntimeError("AsyncTaskManager 未注入")
        return await self._async.start_task(
            task_type="draft_generation", task_func=self._run_generation,
            source_document_id=source_document_id, config=config or DraftGenerationConfig())

    async def _run_generation(self, source_document_id: str, config: DraftGenerationConfig, **ctx) -> dict:
        tid, tt = ctx.get("task_id", ""), "draft_generation"
        pub = lambda s, m, **d: TaskSsePublisher.publish(
            task_type=tt, task_id=tid, event_type="progress",
            data={"status": "running", "stage": s, "message": m, "metadata": d})
        try:
            doc = await self._load_doc(source_document_id)
            chunks = await self._load_chunks(doc.file_hash)
            chunks = self._filter_chunks(chunks)
            await pub("generation_started", "开始", document_id=source_document_id)
            meta = await self._analyzer.analyze(
                title=doc.title or "",
                file_type=doc.file_type or "",
                content_summary=getattr(doc, "content_summary", None) or "",
            )
            await pub("metadata_analyzed", "元数据完成", topic_summary=meta.topic_summary)

            # ── 流水线: 生成器 → Queue → 检查器 ──
            concurrency = self._config.get_config_value("rag.eval.draft.concurrency", 15)
            queue: asyncio.Queue = asyncio.Queue(maxsize=concurrency * 2)
            all_scored: list = []
            total_chunks = len(chunks)
            gen_completed = [0]
            check_completed = [0]
            check_sem = asyncio.Semaphore(concurrency)
            checker_count = min(4, concurrency)

            async def checker_worker():
                """从队列消费草稿批次并执行忠实度检查"""
                while True:
                    batch = await queue.get()
                    if batch is None:
                        queue.task_done()
                        break
                    try:
                        scored = await self._faith.batch_check(batch, semaphore=check_sem)
                        all_scored.extend(scored)
                        check_completed[0] += len(batch)
                    except Exception as e:
                        logger.error(f"检查器异常: {e}")
                    finally:
                        queue.task_done()

            checker_tasks = [asyncio.create_task(checker_worker()) for _ in range(checker_count)]

            async def on_draft_batch(batch):
                if batch:
                    await queue.put(batch)

            async def on_gen_progress(done: int, total: int):
                gen_completed[0] = done
                pct = 15 + int((done / max(total, 1)) * 70)
                await pub("pipeline_running",
                    f"生成+校验: {done}/{total} 分块, 已校验 {check_completed[0]} 条",
                    done=done, total=total, checked=check_completed[0], pct=pct)

            await self._gen.generate(
                chunks, config,
                progress_callback=on_gen_progress,
                draft_batch_callback=on_draft_batch,
            )

            for _ in range(checker_count):
                await queue.put(None)
            await asyncio.gather(*checker_tasks)

            scored = all_scored
            batch_id = generate_prefixed_id("batch")
            await pub("drafts_generated", f"生成+校验完成: {len(scored)} 条",
                count=len(scored), batch_id=batch_id)

            # 去重
            t = self._config.get_config_value("rag.eval.draft.faithfulness_threshold", 0.7)
            low_count = sum(1 for _, s in scored if s < t)
            await pub("faithfulness_checked", f"校验: {len(scored)}", checked=len(scored), low=low_count)
            before = len(scored)
            deduped = await self._dedup.deduplicate(scored, source_document_id)
            await pub("deduplication_completed", f"去重: {before}→{len(deduped)}", before=before, after=len(deduped))

            # 保存
            saved = 0
            for idx, (d, s) in enumerate(deduped):
                try:
                    await self._draft_repo.create(dict(
                        id=generate_prefixed_id("draft"), source_document_id=source_document_id,
                        query=d.query, description=d.description,
                        expected_knowledge_ids=d.expected_knowledge_ids or [],
                        expected_keywords=d.expected_keywords or [], answer_points=d.answer_points or [],
                        professional_terms=d.professional_terms or [], difficulty_level=d.difficulty_level,
                        faithfulness_score=float(s), source_chunk_id=d.source_chunk_id,
                        source_page=d.source_page, source_content_snippet=d.source_content_snippet,
                        generation_params=d.generation_params, batch_id=batch_id, draft_index=idx,
                        status=TestCaseStatus.DRAFT, version=1))
                    saved += 1
                except Exception as e:
                    logger.error(f"保存失败: {e}")
            result = {"saved_count": saved, "skipped": len(deduped) - saved, "batch_id": batch_id}
            await TaskSsePublisher.publish_complete(task_type=tt, task_id=tid, result=result,
                message=f"完成: {saved}/{len(deduped)}")
            return result
        except asyncio.CancelledError:
            await TaskSsePublisher.publish_cancelled(task_type=tt, task_id=tid)
            return {}
        except Exception as e:
            logger.error(f"生成失败: {e}")
            await TaskSsePublisher.publish_error(task_type=tt, task_id=tid, error=str(e))
            raise

    # ── CRUD ──

    _ALLOWED_SORT_FIELDS: ClassVar[set[str]] = {
        "faithfulness_score", "status", "created_at", "updated_at",
    }

    async def get_drafts(self, page=1, page_size=20, status=None,
                         source_document_id=None, batch_id=None,
                         sort_by: Optional[str] = None,
                         sort_order: Optional[str] = None) -> DraftList:
        from sqlalchemy import asc, desc
        skip = (page - 1) * page_size
        f = {}
        for k, v in [("status", status), ("source_document_id", source_document_id), ("batch_id", batch_id)]:
            if v is not None:
                f[k] = v

        # 构建排序子句
        order_by = None
        if sort_by and sort_by in self._ALLOWED_SORT_FIELDS:
            col = getattr(TestCaseDraft, sort_by)
            order_by = desc(col) if sort_order == "desc" else asc(col)

        orms = await (self._draft_repo.get_all(skip=skip, limit=page_size, order_by=order_by) if not f
                      else self._draft_repo.get_by_filter(**f, skip=skip, limit=page_size, order_by=order_by))
        total = await (self._draft_repo.count_all() if not f else self._draft_repo.count_by_filter(**f))
        return DraftList(items=OrmMapper.to_read_list(orms, DraftRead), total=total, page=page, page_size=page_size)

    async def get_draft(self, draft_id: str) -> DraftRead:
        o = await self._draft_repo.get_by_id(draft_id)
        if not o:
            raise ValueError(f"草稿不存在: {draft_id}")
        return OrmMapper.to_read(o, DraftRead)

    async def update_draft(self, draft_id: str, update: DraftUpdate) -> DraftRead:
        if not await self._draft_repo.get_by_id(draft_id):
            raise ValueError(f"草稿不存在: {draft_id}")
        await self._draft_repo.update(draft_id, update.model_dump(exclude_unset=True))
        return OrmMapper.to_read(await self._draft_repo.get_by_id(draft_id), DraftRead)

    async def review_draft(self, draft_id: str, review: DraftReview) -> Optional[dict]:
        o = await self._draft_repo.get_by_id(draft_id)
        if not o or o.status != TestCaseStatus.DRAFT:
            raise ValueError(f"草稿不可审核: {draft_id}")
        if review.action == "reject":
            await self._draft_repo.update(draft_id, {"status": TestCaseStatus.REJECTED, "version": o.version + 1})
            return None
        tc = await self._tc_repo.create(self._tc_dict(o, draft_id, o.source_document_id))
        await self._draft_repo.update(draft_id, {"status": TestCaseStatus.REVIEWED, "version": o.version + 1})
        return OrmMapper.to_read(tc, TestCaseRead).model_dump()

    async def batch_import(self, draft_ids: list[str]) -> list[dict]:
        r = []
        for did in draft_ids:
            try:
                o = await self._draft_repo.get_by_id(did)
                if not o or o.status != TestCaseStatus.REVIEWED:
                    continue
                tc = await self._tc_repo.get_by_source_draft(did) or await self._tc_repo.create(
                    self._tc_dict(o, did, o.source_document_id))
                await self._draft_repo.update(did, {"status": TestCaseStatus.IMPORTED, "version": o.version + 1})
                r.append(OrmMapper.to_read(tc, TestCaseRead).model_dump())
            except Exception as e:
                logger.error(f"导入失败 {did}: {e}")
        return r

    async def batch_delete(self, draft_ids: list[str]) -> None:
        for did in draft_ids:
            try:
                await self._draft_repo.delete(did)
            except Exception as e:
                logger.error(f"删除失败 {did}: {e}")

    async def delete_by_document(self, source_document_id: str) -> int:
        drafts = await self._draft_repo.get_by_source_document(source_document_id, limit=10000)
        for d in drafts:
            await self._draft_repo.delete(d.id)
        return len(drafts)

    async def cleanup_orphaned_drafts(self, retention_days: int = 7) -> int:
        """清理过期的未审核草稿"""
        from datetime import datetime, timedelta
        from sqlalchemy import select
        from src.models.rag_eval.draft import TestCaseDraft

        cutoff = datetime.now() - timedelta(days=retention_days)

        async with self._draft_repo.db_session_factory() as session:
            stmt = select(TestCaseDraft).where(
                TestCaseDraft.status == TestCaseStatus.DRAFT,
                TestCaseDraft.created_at < cutoff,
            )
            result = await session.execute(stmt)
            old_drafts = result.scalars().all()

        cleaned_count = 0
        for draft in old_drafts:
            try:
                await self._draft_repo.delete(draft.id)
                cleaned_count += 1
            except Exception as e:
                logger.error(f"清理草稿 {draft.id} 失败: {e}")

        return cleaned_count

    # ── 内部辅助 ──

    @staticmethod
    def _tc_dict(o, draft_id, source_document_id) -> dict:
        return dict(
            id=generate_prefixed_id("tc"), query=o.query,
            age=None, age_stage_label="", domain=None,
            description=o.description,
            expected_knowledge_ids=o.expected_knowledge_ids or [],
            expected_keywords=o.expected_keywords or [],
            answer_points_summary=(o.description or "")[:500],
            difficulty_level=o.difficulty_level,
            professional_terms=o.professional_terms or [],
            source="draft", source_draft_id=draft_id,
            source_document_id=source_document_id, version=1,
        )

    async def _load_doc(self, doc_id: str):
        from src.schemas.rag_eval.source_document import SourceDocumentRead
        o = await self._doc_repo.get_by_id(doc_id)
        if not o:
            raise ValueError(f"源文档不存在: {doc_id}")
        return OrmMapper.to_read(o, SourceDocumentRead)

    def _filter_chunks(self, chunks: list[dict]) -> list[dict]:
        """过滤掉不适合生成测试用例的分块（过短、无实质内容、非正文）"""
        min_length = self._config.get_config_value(
            "rag.eval.draft.min_chunk_length", 100,
        )
        filtered = []
        for c in chunks:
            content = c.get("content", "")
            # 过短
            if len(content) < min_length:
                continue
            # 去除空白和标点后实质内容过少（纯数字/符号分隔线等）
            text = re.sub(r"[\s\d\W_]+", "", content)
            if len(text) < min_length * 0.3:
                continue
            # 短内容匹配非正文模式（目录/版权页等），仅对 <300 字符检查避免误杀正文
            if len(content) < 300 and any(p in content for p in self._SKIP_PATTERNS):
                continue
            filtered.append(c)
        skipped = len(chunks) - len(filtered)
        if skipped:
            logger.info(f"分块预过滤: {len(chunks)} → {len(filtered)} (跳过 {skipped})")
        return filtered

    async def _load_chunks(self, file_hash: str) -> list[dict]:
        """按 file_hash 从向量库加载文档的所有分块"""
        try:
            from src.service.rag_service import rag_service
            raw_chunks = rag_service.get_all_chunks_by_file_hash(file_hash)
            if not raw_chunks:
                logger.warning(f"未找到分块: file_hash={file_hash}")
                return []
            return [
                {"id": c.get("id", ""), "content": c.get("content", ""),
                 "page": c.get("metadata", {}).get("page_label")}
                for c in raw_chunks
            ]
        except Exception as e:
            logger.error(f"加载分块失败: {e}")
            return []
