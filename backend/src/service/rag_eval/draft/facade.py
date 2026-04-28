"""DraftEngineFacade - 草稿引擎门面"""

import asyncio
from typing import Optional

from src.schemas.rag_eval.draft import (
    DraftGenerationConfig, DraftList, DraftRead, DraftReview, DraftUpdate,
)
from src.schemas.rag_eval.test_case import TestCaseRead
from src.config.core.manager import ConfigManager
from src.models.rag_eval.enums import TestCaseStatus
from src.repository.rag_eval.draft_repository import DraftRepository
from src.repository.rag_eval.test_case_repository import TestCaseRepository
from src.service.rag_eval.draft.book_analyzer import BookMetadataAnalyzer
from src.service.rag_eval.draft.deduplicator import DraftDeduplicator
from src.service.rag_eval.draft.faithfulness_checker import FaithfulnessChecker
from src.service.rag_eval.draft.generator import DraftGenerator
from src.service.task_sse_publisher import TaskSsePublisher
from src.utils.id_generator import generate_prefixed_id
from src.utils.logger import logger
from src.utils.orm_mapper import OrmMapper


class DraftEngineFacade:
    """草稿引擎门面"""

    def __init__(
        self, draft_generator: DraftGenerator, faithfulness_checker: FaithfulnessChecker,
        deduplicator: DraftDeduplicator, book_analyzer: BookMetadataAnalyzer,
        draft_repository: DraftRepository, test_case_repository: TestCaseRepository,
        config_cache: Optional[ConfigManager] = None, async_task_manager=None,
    ):
        self._gen, self._faith, self._dedup = draft_generator, faithfulness_checker, deduplicator
        self._analyzer, self._draft_repo, self._tc_repo = book_analyzer, draft_repository, test_case_repository
        self._config = config_cache or ConfigManager()
        self._async = async_task_manager

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
            chunks = await self._load_chunks(source_document_id)
            await pub("generation_started", "开始", document_id=source_document_id)
            meta = await self._analyzer.analyze(doc)
            await pub("metadata_analyzed", "元数据完成",
                age_ranges=meta.age_ranges, domains=meta.domains, topic_summary=meta.topic_summary)
            drafts = await self._gen.generate(chunks, meta, config)
            batch_id = generate_prefixed_id("batch")
            await pub("drafts_generated", f"生成: {len(drafts)}", count=len(drafts), batch_id=batch_id)
            scored = await self._faith.batch_check(drafts)
            t = self._config.get_config_value("rag.eval.draft.faithfulness_threshold", 0.7)
            await pub("faithfulness_checked", f"校验: {len(scored)}", checked=len(scored),
                low=sum(1 for _, s in scored if s < t))
            before = len(scored)
            deduped = await self._dedup.deduplicate(scored, source_document_id)
            await pub("deduplication_completed", f"去重: {before}→{len(deduped)}", before=before, after=len(deduped))
            saved = 0
            for idx, (d, s) in enumerate(deduped):
                try:
                    await self._draft_repo.create(dict(
                        id=generate_prefixed_id("draft"), source_document_id=source_document_id,
                        query=d.query, age=float(d.age), age_stage_label=d.age_stage_label or "",
                        domain=d.domain, description=d.description,
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

    async def get_drafts(self, page=1, page_size=20, status=None, domain=None,
                         source_document_id=None, batch_id=None) -> DraftList:
        skip = (page - 1) * page_size
        f = {}
        for k, v in [("status", status), ("source_document_id", source_document_id), ("batch_id", batch_id)]:
            if v is not None:
                f[k] = v
        if domain:
            try:
                from src.models.rag_eval.enums import TestDomain as TD
                f["domain"] = TD(domain)
            except ValueError:
                pass
        orms = await (self._draft_repo.get_all(skip=skip, limit=page_size) if not f
                      else self._draft_repo.get_by_filter(**f, skip=skip, limit=page_size))
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
        tc = await self._tc_repo.create(self._tc_dict(o, draft_id))
        await self._draft_repo.update(draft_id, {"status": TestCaseStatus.REVIEWED, "version": o.version + 1})
        return OrmMapper.to_read(tc, TestCaseRead).model_dump()

    async def batch_import(self, draft_ids: list[str]) -> list[dict]:
        r = []
        for did in draft_ids:
            try:
                o = await self._draft_repo.get_by_id(did)
                if not o or o.status != TestCaseStatus.REVIEWED:
                    continue
                tc = await self._tc_repo.get_by_source_draft(did) or await self._tc_repo.create(self._tc_dict(o, did))
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
    def _tc_dict(o, draft_id) -> dict:
        return dict(id=generate_prefixed_id("tc"), query=o.query, age=float(o.age),
            age_stage_label=o.age_stage_label or "", domain=o.domain, description=o.description,
            expected_knowledge_ids=o.expected_knowledge_ids or [],
            expected_keywords=o.expected_keywords or [], answer_points_summary=(o.description or "")[:500],
            difficulty_level=o.difficulty_level, professional_terms=o.professional_terms or [],
            source="draft", source_draft_id=draft_id, source_document_id=o.source_document_id, version=1)

    async def _load_doc(self, doc_id: str):
        from src.schemas.rag_eval.source_document import SourceDocumentRead
        from src.repository.document_repository import SourceDocumentRepository
        o = await SourceDocumentRepository().get_by_id(doc_id)
        if not o:
            raise ValueError(f"源文档不存在: {doc_id}")
        return OrmMapper.to_read(o, SourceDocumentRead)

    async def _load_chunks(self, source_document_id: str) -> list[dict]:
        try:
            from src.service.rag_service import rag_service
            info = rag_service.get_chunk_detail(source_document_id)
            return [{"id": source_document_id, "content": info.get("content", ""), "page": None}] if info else []
        except Exception as e:
            logger.warning(f"加载分块失败: {e}")
        return [{"id": source_document_id, "content": "", "page": None}]
