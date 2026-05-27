"""知识问答 API 控制器

端点：
- POST   /api/v1/knowledge-qa                    触发知识问答
- GET    /api/v1/knowledge-qa/status/{task_id}   查询任务状态
- GET    /api/v1/knowledge-qa/stream/{task_id}    SSE 进度流
- GET    /api/v1/knowledge-qa/download/{task_id}/markdown  下载 Markdown
- GET    /api/v1/knowledge-qa/download/{task_id}/pdf        下载 PDF
"""

import io
import logging
from typing import Optional

from fastapi import APIRouter, Path, Query, Request
from fastapi.responses import StreamingResponse

from src.schemas.common import APIResponse
from src.schemas.knowledge_qa import ErrorCode, KnowledgeQARequest
from src.service.knowledge_qa_service import KnowledgeQAService
from src.utils.exceptions import (
    KnowledgeQATaskNotFoundException,
    NoMatchingBooksException,
    RAGUnavailableException,
)

logger = logging.getLogger(__name__)


class KnowledgeQAController:
    """知识问答控制器"""

    def __init__(self, service: KnowledgeQAService):
        self._service = service

    def register(self, router: APIRouter) -> None:
        """注册所有路由"""
        router.add_api_route(
            "/knowledge-qa",
            self.ask,
            methods=["POST"],
            summary="触发知识问答",
            description="提交自然语言问题，返回 task_id。通过 stream/{task_id} 订阅进度。",
        )
        router.add_api_route(
            "/knowledge-qa/status/{task_id}",
            self.get_status,
            methods=["GET"],
            summary="查询任务状态",
        )
        router.add_api_route(
            "/knowledge-qa/stream/{task_id}",
            self.stream_progress,
            methods=["GET"],
            summary="SSE 进度流",
        )
        router.add_api_route(
            "/knowledge-qa/download/{task_id}/markdown",
            self.download_markdown,
            methods=["GET"],
            summary="下载 Markdown 报告",
        )
        router.add_api_route(
            "/knowledge-qa/download/{task_id}/pdf",
            self.download_pdf,
            methods=["GET"],
            summary="下载 PDF 报告",
        )
        router.add_api_route(
            "/knowledge-qa/graph/rebuild-global",
            self.rebuild_global_graph,
            methods=["POST"],
            summary="手动触发全局知识图谱重建",
            description="跨书实体去重 + 全局社区检测 + 层级树存储。",
        )

    # ===== 端点实现 =====

    async def ask(self, request: KnowledgeQARequest) -> APIResponse:
        """触发知识问答"""
        try:
            task_id = await self._service.ask(
                question=request.question,
                book_ids=request.book_ids,
                stream=request.options.get("stream", True) if request.options else True,
            )
            return APIResponse.success({"task_id": task_id})
        except NoMatchingBooksException:
            return APIResponse.error(
                code=ErrorCode.NO_MATCHING_BOOKS,
                error_code="no_matching_books",
                message="未在知识库中找到相关书籍，请联系管理员上传",
            )
        except RAGUnavailableException:
            return APIResponse.error(
                code=ErrorCode.RAG_UNAVAILABLE,
                error_code="rag_unavailable",
                message="知识库检索服务暂不可用，请稍后重试",
            )

    async def get_status(
        self,
        task_id: str = Path(..., description="任务 ID"),
    ) -> APIResponse:
        """查询任务状态"""
        status = await self._service.get_status(task_id)
        if status is None:
            return APIResponse.error(
                code=ErrorCode.TASK_NOT_FOUND,
                error_code="task_not_found",
                message="任务不存在或已过期",
            )
        return APIResponse.success(status)

    async def stream_progress(
        self,
        task_id: str = Path(...),
        request: Request = None,
    ):
        """SSE 流式端点"""
        from src.api.sse import sse_response

        channel = f"knowledge_qa:{task_id}"
        return sse_response(channel)

    async def download_markdown(
        self,
        task_id: str = Path(...),
    ):
        """下载 Markdown 报告"""
        try:
            content = await self._service.generate_markdown(task_id)
            return StreamingResponse(
                io.BytesIO(content.encode("utf-8")),
                media_type="text/markdown; charset=utf-8",
                headers={
                    "Content-Disposition": f"attachment; filename=report-{task_id}.md"
                },
            )
        except ValueError:
            return APIResponse.error(
                code=ErrorCode.TASK_NOT_FOUND,
                error_code="task_not_found",
                message="任务结果不存在或已过期",
            )

    async def download_pdf(
        self,
        task_id: str = Path(...),
    ):
        """下载 PDF 报告"""
        try:
            pdf_bytes = await self._service.generate_pdf(task_id)
            return StreamingResponse(
                io.BytesIO(pdf_bytes),
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f"attachment; filename=report-{task_id}.pdf"
                },
            )
        except ValueError:
            return APIResponse.error(
                code=ErrorCode.TASK_NOT_FOUND,
                error_code="task_not_found",
                message="任务结果不存在或已过期",
            )

    async def rebuild_global_graph(self) -> APIResponse:
        """手动触发全局知识图谱重建（通过 HTTP 调用 RAG 服务）"""
        import httpx
        from src.config import settings

        host = getattr(settings, "app_host", "127.0.0.1")
        port = getattr(settings, "app_port", 8000)

        async with httpx.AsyncClient(
            base_url=f"http://{host}:{port}",
            timeout=httpx.Timeout(300.0),
        ) as client:
            try:
                resp = await client.post("/rag/graph/global-rebuild")
                resp.raise_for_status()
                data = resp.json()
                return APIResponse.success(data.get("data", {}))
            except httpx.HTTPStatusError as e:
                return APIResponse.error(
                    code=e.response.status_code,
                    error_code="global_rebuild_failed",
                    message=f"全局图谱重建失败: HTTP {e.response.status_code}",
                )
            except Exception as e:
                return APIResponse.error(
                    code=500,
                    error_code="global_rebuild_failed",
                    message=f"全局图谱重建失败: {e}",
                )
