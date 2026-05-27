"""单元测试：知识问答服务层 (knowledge_qa_service.py)

覆盖：并发限制、超时降级、知识上下文预取、响应构建
"""

import asyncio

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.schemas.knowledge_qa import (
    GenerationMetadata,
    KnowledgeQAResponse,
    KnowledgeQAState,
    MatchedBook,
    SectionOutput,
)
from src.service.knowledge_qa_service import (
    TASK_TYPE,
    KnowledgeQAService,
)
from src.utils.exceptions import KnowledgeQATooManyRequestsException


# ==================== 辅助函数 ====================


def _make_service() -> KnowledgeQAService:
    """构造绕过 __init__ 的 KnowledgeQAService 实例"""
    service = KnowledgeQAService.__new__(KnowledgeQAService)
    service._graph = MagicMock()
    service._async = MagicMock()
    service._task_state = MagicMock()
    service._prompt_manager = MagicMock()
    service._db_session_factory = MagicMock()
    service._concurrent_tasks = 0
    service._task_lock = asyncio.Lock()
    return service


def _make_state(
    question: str = "测试问题",
    sections: dict | None = None,
    matched_books: list | None = None,
    errors: list | None = None,
    partial: bool = False,
) -> KnowledgeQAState:
    """构造测试用 KnowledgeQAState"""
    return KnowledgeQAState(
        question=question,
        matched_books_detail=matched_books or [],
        sections=sections or {},
        errors=errors or [],
        partial=partial,
    )


# ==================== 并发限制测试 ====================


class TestConcurrencyLimit:
    """并发任务限制测试"""

    @pytest.mark.asyncio
    async def test_concurrency_limit_accepts_up_to_max(self):
        """未达上限时，MAX_CONCURRENT_TASKS 次调用应全部成功"""
        service = _make_service()
        # 模拟 AsyncTaskManager.start_task 返回 task_id
        service._async.start_task = AsyncMock(return_value="task-001")

        # 连续调用 MAX_CONCURRENT_TASKS 次，均不应抛异常
        for _ in range(KnowledgeQAService.MAX_CONCURRENT_TASKS):
            task_id = await service.ask(question="测试问题")
            assert task_id == "task-001"

        assert service._concurrent_tasks == KnowledgeQAService.MAX_CONCURRENT_TASKS

    @pytest.mark.asyncio
    async def test_concurrency_limit_rejects_over_max(self):
        """超过 MAX_CONCURRENT_TASKS 时应抛出 TooManyRequests 异常"""
        service = _make_service()
        service._async.start_task = AsyncMock(return_value="task-001")

        # 先消耗完所有并发槽位
        for _ in range(KnowledgeQAService.MAX_CONCURRENT_TASKS):
            await service.ask(question="测试问题")

        # 第 MAX_CONCURRENT_TASKS + 1 次调用应抛出异常
        with pytest.raises(KnowledgeQATooManyRequestsException):
            await service.ask(question="额外请求")


# ==================== 超时降级测试 ====================


class TestTimeoutDegradation:
    """逐节超时由各节点内部处理，Service 层只做异常传播"""

    @pytest.mark.asyncio
    async def test_graph_exception_propagates(self):
        """graph.ainvoke 抛出异常时，_run_qa_pipeline 应传播异常并发布错误事件"""
        service = _make_service()
        service._concurrent_tasks = 1

        # 模拟 graph 执行异常
        service._graph.ainvoke = AsyncMock(side_effect=RuntimeError("LLM 调用失败"))

        ctx = {
            "task_id": "test-error-task",
            "task_type": TASK_TYPE,
            "question": "测试问题",
            "book_ids": [],
            "stream": False,
        }

        mock_http_client = MagicMock()
        mock_http_client.close = AsyncMock()

        mock_sse = MagicMock()
        mock_sse.publish = AsyncMock()
        mock_sse.publish_error = AsyncMock()
        mock_sse.publish_complete = AsyncMock()

        with patch("src.service.knowledge_qa_service.TaskSsePublisher", mock_sse), \
             patch("src.service.knowledge_qa_service.set_progress_context"), \
             patch("src.service.knowledge_qa_service.set_prompt_manager"), \
             patch("src.service.knowledge_qa_service.clear_progress_context"), \
             patch("src.service.knowledge_qa_service.clear_prompt_manager"), \
             patch("src.core.knowledge_qa.tools.clear_http_client"), \
             patch("src.core.knowledge_qa.tools.set_http_client"), \
             patch("src.utils.http_client.RagHttpClient", return_value=mock_http_client):

            with pytest.raises(RuntimeError, match="LLM 调用失败"):
                await service._run_qa_pipeline(**ctx)

            # SSE 应发布错误事件
            mock_sse.publish_error.assert_called_once()


# ==================== 响应构建测试 ====================


class TestBuildResponse:
    """_build_response 响应构建测试"""

    def test_build_response_construction(self):
        """应从 State 正确构建 KnowledgeQAResponse，节按 index 排序"""
        service = _make_service()

        state = KnowledgeQAState(
            question="测试问题",
            matched_books_detail=[
                MatchedBook(book_id="b1", title="书1", match_reason="测试匹配"),
            ],
            sections={
                1: SectionOutput(
                    index=1,
                    title="第一节",
                    content="内容1",
                    citations=[{"citation_id": "C001", "excerpt": "引用1", "chapter": "第1章"}],
                    structured_data={},
                ),
                2: SectionOutput(
                    index=2,
                    title="第二节",
                    content="内容2",
                    citations=[],
                    structured_data={},
                ),
            },
            errors=[],
            partial=False,
        )

        response = service._build_response(state, elapsed_ms=5000)

        # 基本字段验证
        assert isinstance(response, KnowledgeQAResponse)
        assert response.question == "测试问题"

        # 匹配书籍
        assert len(response.matched_books) == 1
        assert response.matched_books[0].book_id == "b1"

        # 节按 index 排序
        assert len(response.sections) == 2
        assert response.sections[0].index == 1
        assert response.sections[1].index == 2
        assert response.sections[0].title == "第一节"
        assert response.sections[1].title == "第二节"

        # 元信息
        meta = response.generation_metadata
        assert isinstance(meta, GenerationMetadata)
        assert meta.total_sections == 2
        assert meta.total_citations == 1
        assert meta.total_time_ms == 5000
        assert meta.partial is False
