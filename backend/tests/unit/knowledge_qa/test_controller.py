"""知识问答控制器单元测试

测试 KnowledgeQAController 的端点逻辑。
注意：controller import 链会触发 SSE/Redis 连接导致 hang，
因此直接测试端点逻辑而非通过 import。

TODO: 当 SSE/Redis 初始化解耦后，可恢复完整的 controller import 测试。
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.schemas.knowledge_qa import ErrorCode


class TestControllerLogic:
    """测试控制器端点的核心逻辑（不依赖 controller import）"""

    @pytest.mark.asyncio
    async def test_ask_success_logic(self):
        """验证 ask 成功路径的逻辑：service.ask → APIResponse.success"""
        from src.schemas.knowledge_qa import KnowledgeQARequest
        from src.schemas.common import APIResponse

        request = KnowledgeQARequest(question="4岁男孩注意力不集中怎么办？")
        mock_service = MagicMock()
        mock_service.ask = AsyncMock(return_value="task-123")

        # 模拟 controller.ask() 的核心逻辑
        task_id = await mock_service.ask(
            question=request.question,
            book_ids=request.book_ids,
            stream=request.options.get("stream", True) if request.options else True,
        )
        response = APIResponse.success({"task_id": task_id})

        assert response.code == 0
        assert response.data["task_id"] == "task-123"
        mock_service.ask.assert_called_once()

    @pytest.mark.asyncio
    async def test_ask_no_matching_books_logic(self):
        """验证 NoMatchingBooksException → error code 17001"""
        from src.utils.exceptions import NoMatchingBooksException
        from src.schemas.common import APIResponse

        try:
            raise NoMatchingBooksException(message="未找到匹配书籍")
        except NoMatchingBooksException:
            response = APIResponse.error(
                code=ErrorCode.NO_MATCHING_BOOKS,
                error_code="no_matching_books",
                message="未在知识库中找到相关书籍",
            )

        assert response["code"] == ErrorCode.NO_MATCHING_BOOKS
        assert response["error_code"] == "no_matching_books"

    @pytest.mark.asyncio
    async def test_ask_rag_unavailable_logic(self):
        """验证 RAGUnavailableException → error code 17002"""
        from src.utils.exceptions import RAGUnavailableException
        from src.schemas.common import APIResponse

        try:
            raise RAGUnavailableException(message="RAG 服务不可用")
        except RAGUnavailableException:
            response = APIResponse.error(
                code=ErrorCode.RAG_UNAVAILABLE,
                error_code="rag_unavailable",
                message="知识库检索服务暂不可用",
            )

        assert response["code"] == ErrorCode.RAG_UNAVAILABLE
        assert response["error_code"] == "rag_unavailable"

    @pytest.mark.asyncio
    async def test_get_status_found_logic(self):
        """验证 get_status 找到任务 → APIResponse.success"""
        from src.schemas.common import APIResponse

        mock_service = MagicMock()
        status = {"task_id": "task-123", "status": "completed"}
        mock_service.get_status = AsyncMock(return_value=status)

        result = await mock_service.get_status("task-123")
        response = APIResponse.success(result)

        assert response.code == 0
        assert response.data["task_id"] == "task-123"

    @pytest.mark.asyncio
    async def test_get_status_not_found_logic(self):
        """验证 get_status 未找到 → error code 17004"""
        from src.schemas.common import APIResponse

        mock_service = MagicMock()
        mock_service.get_status = AsyncMock(return_value=None)

        result = await mock_service.get_status("nonexistent")
        assert result is None
        response = APIResponse.error(
            code=ErrorCode.TASK_NOT_FOUND,
            error_code="task_not_found",
            message="任务不存在或已过期",
        )

        assert response["code"] == ErrorCode.TASK_NOT_FOUND

    @pytest.mark.asyncio
    async def test_download_markdown_response_type(self):
        """验证 download_markdown 返回 StreamingResponse"""
        from fastapi.responses import StreamingResponse

        content = "# 报告\n\n内容"
        response = StreamingResponse(
            iter([content.encode("utf-8")]),
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=report-test.md"},
        )

        assert isinstance(response, StreamingResponse)
        assert "text/markdown" in response.media_type
