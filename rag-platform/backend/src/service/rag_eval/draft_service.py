"""测试用例草稿服务"""
import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import async_sessionmaker

from src.models.rag_eval.draft import TestCaseDraft
from src.repository.rag_eval.draft_repo import DraftRepository
from src.repository.rag_eval.test_case_repo import TestCaseRepository
from src.schemas.rag_eval.draft import (
    CreateDraftReq,
    DraftList,
    DraftRead,
    DraftStatus,
    GenerateDraftReq,
    ReviewAction,
)
from src.schemas.rag_eval.test_case import CreateTestCaseReq, TestCaseRead
from src.utils.logger import logger


class DraftService:
    """测试用例草稿服务"""

    def __init__(self, session_factory: async_sessionmaker):
        self._session_factory = session_factory
        self._draft_repo = DraftRepository(session_factory)
        self._case_repo = TestCaseRepository(session_factory)

    async def list_drafts(
        self,
        tenant_id: str,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        search: Optional[str] = None,
    ) -> DraftList:
        """分页查询草稿"""
        items, total = await self._draft_repo.list_drafts(
            tenant_id=tenant_id,
            page=page,
            page_size=page_size,
            status=status,
            search=search,
        )
        return DraftList(
            items=[self._to_read(item) for item in items],
            total=total,
        )

    async def get_draft(self, tenant_id: str, draft_id: str) -> DraftRead:
        """获取单个草稿"""
        draft = await self._draft_repo.get_by_id(draft_id, tenant_id)
        if not draft:
            raise ValueError(f"草稿不存在: {draft_id}")
        return self._to_read(draft)

    async def create_draft(self, tenant_id: str, data: CreateDraftReq) -> DraftRead:
        """创建草稿"""
        draft_id = self._generate_id()
        draft_data = data.model_dump()
        draft_data.update({
            "id": draft_id,
            "tenant_id": tenant_id,
            "status": DraftStatus.PENDING.value,
            "version": 1,
        })
        # 枚举字段转为字符串
        if "difficulty_level" in draft_data and draft_data["difficulty_level"] is not None:
            draft_data["difficulty_level"] = str(draft_data["difficulty_level"])

        draft = await self._draft_repo.create(draft_data)
        logger.info(f"草稿创建成功: {draft_id}")
        return self._to_read(draft)

    async def update_draft(
        self, tenant_id: str, draft_id: str, data: dict
    ) -> DraftRead:
        """更新草稿（部分字段）"""
        draft = await self._draft_repo.get_by_id(draft_id, tenant_id)
        if not draft:
            raise ValueError(f"草稿不存在: {draft_id}")

        if draft.status != DraftStatus.PENDING.value:
            raise ValueError(f"草稿状态为 {draft.status}，无法编辑")

        update_data = {k: v for k, v in data.items() if v is not None}
        if "difficulty_level" in update_data and update_data["difficulty_level"] is not None:
            update_data["difficulty_level"] = str(update_data["difficulty_level"])

        draft = await self._draft_repo.update(draft_id, update_data, tenant_id)
        return self._to_read(draft)

    async def delete_draft(self, tenant_id: str, draft_id: str) -> None:
        """删除草稿"""
        deleted = await self._draft_repo.delete(draft_id, tenant_id)
        if not deleted:
            raise ValueError(f"草稿不存在: {draft_id}")
        logger.info(f"草稿删除成功: {draft_id}")

    async def review_draft(
        self, tenant_id: str, draft_id: str, action: ReviewAction
    ) -> DraftRead:
        """审核草稿（通过/拒绝）"""
        draft = await self._draft_repo.get_by_id(draft_id, tenant_id)
        if not draft:
            raise ValueError(f"草稿不存在: {draft_id}")

        if draft.status != DraftStatus.PENDING.value:
            raise ValueError(f"草稿状态为 {draft.status}，无法审核")

        if action == ReviewAction.APPROVE:
            new_status = DraftStatus.APPROVED.value
        else:
            new_status = DraftStatus.REJECTED.value

        draft = await self._draft_repo.update(draft_id, {"status": new_status}, tenant_id)
        logger.info(f"草稿 {draft_id} 审核: {action.value}")
        return self._to_read(draft)

    async def import_draft(self, tenant_id: str, draft_id: str) -> TestCaseRead:
        """将草稿导入为正式测试用例（原子操作）"""
        draft = await self._draft_repo.get_by_id(draft_id, tenant_id)
        if not draft:
            raise ValueError(f"草稿不存在: {draft_id}")

        if draft.status not in (DraftStatus.APPROVED.value,):
            raise ValueError(f"草稿状态为 {draft.status}，只有 approved 状态才可导入")

        case_id = self._generate_id()
        case_data = {
            "id": case_id,
            "tenant_id": tenant_id,
            "query": draft.query,
            "description": draft.description,
            "difficulty_level": draft.difficulty_level,
            "expected_knowledge_ids": draft.expected_knowledge_ids,
            "expected_keywords": draft.expected_keywords,
            "answer_points_summary": draft.answer_points,
            "professional_terms": draft.professional_terms,
            "source": "draft",
            "source_draft_id": draft_id,
            "version": 1,
        }

        # 在同一事务中完成用例创建 + 草稿状态更新
        from src.models.rag_eval.draft import TestCaseDraft
        from src.models.rag_eval.test_case import TestCase
        from sqlalchemy import select

        async with self._session_factory() as session:
            # 创建测试用例
            case_obj = TestCase(**case_data)
            session.add(case_obj)
            # 更新草稿状态
            stmt = select(TestCaseDraft).where(
                TestCaseDraft.id == draft_id,
                TestCaseDraft.tenant_id == tenant_id,
            )
            draft_obj = (await session.execute(stmt)).scalar_one_or_none()
            if not draft_obj:
                raise ValueError(f"草稿不存在: {draft_id}")
            draft_obj.status = DraftStatus.IMPORTED.value
            await session.commit()
            await session.refresh(case_obj)

        logger.info(f"草稿 {draft_id} 导入为测试用例 {case_id}")
        from src.service.rag_eval.case_service import TestCaseService
        svc = TestCaseService(self._session_factory)
        return svc._to_read(case_obj)

    async def generate_drafts(
        self, tenant_id: str, data: GenerateDraftReq
    ) -> list[DraftRead]:
        """从文档批量生成草稿（LLM 调用存根）"""
        # TODO: Phase 7 完整实现
        # 当前返回空列表，等待 LLM 集成
        logger.info(
            f"草稿生成请求: tenant={tenant_id}, kb={data.kb_id}, "
            f"docs={len(data.document_ids)}"
        )
        return []

    def _generate_id(self) -> str:
        """生成唯一 ID"""
        return str(uuid.uuid4()).replace("-", "")[:24]

    def _to_read(self, draft: TestCaseDraft) -> DraftRead:
        """ORM 模型转响应实体"""
        return DraftRead(
            id=draft.id,
            tenant_id=draft.tenant_id,
            query=draft.query,
            description=draft.description,
            difficulty_level=draft.difficulty_level or "medium",
            expected_knowledge_ids=draft.expected_knowledge_ids,
            expected_keywords=draft.expected_keywords,
            answer_points=draft.answer_points,
            professional_terms=draft.professional_terms,
            source_document_id=draft.source_document_id,
            faithfulness_score=(
                float(draft.faithfulness_score) if draft.faithfulness_score is not None else None
            ),
            status=DraftStatus(draft.status) if draft.status else DraftStatus.PENDING,
            version=draft.version or 1,
            created_at=draft.created_at,
        )
