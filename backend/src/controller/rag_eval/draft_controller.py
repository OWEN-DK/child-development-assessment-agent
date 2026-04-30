"""草稿管理控制器"""

from typing import Optional

from fastapi import APIRouter, Body, Path, Query

from src.api.sse import sse_response
from src.repository.document_repository import SourceDocumentRepository
from src.schemas.common import APIResponse
from src.schemas.rag_eval.draft import DraftGenerationConfig, DraftReview, DraftUpdate
from src.service.rag_eval.draft.facade import DraftEngineFacade
from src.utils.exceptions import AppException


class DraftController:
    """草稿管理端点"""

    def __init__(
        self,
        draft_engine: DraftEngineFacade,
        source_document_repository: SourceDocumentRepository,
    ):
        self._draft = draft_engine
        self._doc_repo = source_document_repository

    def register(self, router: APIRouter) -> None:
        router.add_api_route("/source-documents/upload", self.upload_document, methods=["POST"])
        router.add_api_route("/source-documents", self.list_source_docs, methods=["GET"])
        router.add_api_route("/drafts", self.list_drafts, methods=["GET"])
        router.add_api_route("/drafts/{draft_id}", self.get_draft, methods=["GET"])
        router.add_api_route("/drafts/{draft_id}", self.update_draft, methods=["PUT"])
        router.add_api_route("/drafts/{draft_id}/review", self.review_draft, methods=["POST"])
        router.add_api_route("/drafts/batch-import", self.batch_import, methods=["POST"])
        router.add_api_route("/drafts/batch", self.batch_delete, methods=["DELETE"])
        router.add_api_route("/drafts/generate", self.start_generation, methods=["POST"])
        router.add_api_route("/drafts/generation/{task_id}/stream", self.stream_generation, methods=["GET"])

    async def list_source_docs(
        self,
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
    ):
        """列出源文档（从 source_documents 表查询就绪文档）"""
        skip = (page - 1) * page_size
        orms = await self._doc_repo.get_indexed(skip=skip, limit=page_size)
        total = await self._doc_repo.count_indexed()
        items = []
        for o in orms:
            items.append({
                "id": o.id,
                "name": o.title,
                "file_hash": o.file_hash,
                "status": o.status.value if hasattr(o.status, "value") else str(o.status),
                "page_count": o.page_count,
                "created_at": o.created_at.isoformat() if o.created_at else None,
                "updated_at": o.updated_at.isoformat() if o.updated_at else None,
            })
        return APIResponse.success({"items": items, "total": total, "page": page, "page_size": page_size})

    async def upload_document(self):
        """上传源文档并触发草稿生成"""
        raise AppException(501, 13001, "文档上传功能由 RAG 模块处理，请使用 /api/v1/rag/documents/upload", "NOT_IMPLEMENTED")

    async def list_drafts(
        self,
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
        status: Optional[str] = Query(None),
    ):
        result = await self._draft.get_drafts(page, page_size, status)
        return APIResponse.success(result.model_dump(mode="json"))

    async def get_draft(self, draft_id: str = Path(...)):
        result = await self._draft.get_draft(draft_id)
        return APIResponse.success(result.model_dump(mode="json"))

    async def update_draft(self, draft_id: str = Path(...), body: DraftUpdate = Body(...)):
        result = await self._draft.update_draft(draft_id, body)
        return APIResponse.success(result.model_dump(mode="json"))

    async def review_draft(self, draft_id: str = Path(...), body: DraftReview = Body(...)):
        result = await self._draft.review_draft(draft_id, body)
        return APIResponse.success(result)

    async def batch_import(self, body: dict = Body(...)):
        draft_ids = body.get("draft_ids", [])
        if not draft_ids:
            raise AppException(400, 13016, "draft_ids 不能为空", "INVALID_TEST_CASE_FORMAT")
        result = await self._draft.batch_import(draft_ids)
        return APIResponse.success(result)

    async def batch_delete(self, body: dict = Body(...)):
        draft_ids = body.get("draft_ids", [])
        if not draft_ids:
            raise AppException(400, 13016, "draft_ids 不能为空", "INVALID_TEST_CASE_FORMAT")
        await self._draft.batch_delete(draft_ids)
        return APIResponse.success(None)

    async def start_generation(self, body: dict = Body(...)):
        """启动草稿批量生成"""
        document_id = body.get("document_id")
        config = body.get("config", {})
        if not document_id:
            raise AppException(400, 13016, "document_id 不能为空", "INVALID_PARAMETER")
        from src.schemas.rag_eval.draft import DraftGenerationConfig
        task_id = await self._draft.start_generation(document_id, DraftGenerationConfig(**config))
        return APIResponse.success({"batch_id": task_id})

    async def stream_generation(self, task_id: str = Path(...)):
        """SSE 草稿生成进度"""
        channel = f"draft_generation:{task_id}"
        return sse_response(channel)
