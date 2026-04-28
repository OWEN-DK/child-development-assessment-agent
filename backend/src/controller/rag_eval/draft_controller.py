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
        router.add_api_route("/drafts/generation/{task_id}/stream", self.stream_generation, methods=["GET"])

    async def list_source_docs(
        self,
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
    ):
        """列出源文档（从 DocumentManager 获取已索引的知识库文档）"""
        from src.service.document_manager import document_manager
        all_docs = document_manager.list_documents()
        indexed_docs = [d for d in all_docs if d.status == "indexed"]
        total = len(indexed_docs)
        skip = (page - 1) * page_size
        page_docs = indexed_docs[skip:skip + page_size]
        items = []
        for d in page_docs:
            items.append({
                "id": d.file_hash,
                "name": d.file_name,
                "file_hash": d.file_hash,
                "status": d.status,
                "page_count": d.metadata.total_pages if d.metadata else None,
                "created_at": d.upload_date.isoformat() if d.upload_date else None,
                "updated_at": d.upload_date.isoformat() if d.upload_date else None,
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
        domain: Optional[str] = Query(None),
    ):
        result = await self._draft.get_drafts(page, page_size, status, domain)
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

    async def stream_generation(self, task_id: str = Path(...)):
        """SSE 草稿生成进度"""
        channel = f"draft_generation:{task_id}"
        return sse_response(channel)
