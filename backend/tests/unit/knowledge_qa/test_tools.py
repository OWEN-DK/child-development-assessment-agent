"""单元测试：知识问答工具 (tools.py)

覆盖 search_knowledge_base 工具的三层防护机制：
1. 类型兼容：book_ids 自动转换字符串为列表
2. 调用计数：单节点最多调用 N 次（由 init_tool_call_state 的 max_calls 决定）
3. 重复检测：相同查询直接返回缓存结果
"""

import json

import httpx
import pytest
from unittest.mock import AsyncMock, MagicMock

from src.core.knowledge_qa.tools import (
    DEFAULT_MAX_TOOL_CALLS,
    clear_http_client,
    clear_tool_call_state,
    init_tool_call_state,
    search_knowledge_base,
    set_http_client,
)


@pytest.fixture(autouse=True)
def _setup_tools_context():
    """每个测试前设置 HTTP 客户端和工具调用状态，测试后清理"""
    mock_client = MagicMock()
    mock_client.search_chunks = AsyncMock(
        return_value=[
            {"chunk_id": "c1", "text": "测试内容"},
        ]
    )
    set_http_client(mock_client)
    init_tool_call_state()
    yield
    clear_tool_call_state()
    clear_http_client()


# ==================== 基本搜索测试 ====================


class TestSearchKnowledgeBase:
    """search_knowledge_base 工具测试"""

    @pytest.mark.asyncio
    async def test_search_knowledge_base_basic(self):
        """基本搜索应返回摘要字典（含 summary、top_hits、统计信息）"""
        results = await search_knowledge_base.ainvoke(
            {"query": "儿童注意力发展", "book_ids": None, "top_k": 10}
        )

        # 新格式：返回 1 个摘要 dict
        assert isinstance(results, list)
        assert len(results) == 1

        summary = results[0]
        assert "summary" in summary
        assert "top_hits" in summary
        assert "hit_count" in summary
        assert summary["hit_count"] == 1
        assert summary["call_count"] == 1
        assert summary["remaining_calls"] == DEFAULT_MAX_TOOL_CALLS - 1
        assert "hint" in summary

    @pytest.mark.asyncio
    async def test_type_compatibility_string_book_ids(self):
        """book_ids 传入 JSON 字符串时应自动解析为列表"""
        results = await search_knowledge_base.coroutine(
            query="测试查询", book_ids='["b1","b2"]', top_k=5
        )

        from src.core.knowledge_qa.tools import _get_http_client

        client = _get_http_client()
        client.search_chunks.assert_called_once_with(
            question="测试查询",
            book_ids=["b1", "b2"],
            limit=5,
        )
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_type_compatibility_single_string(self):
        """book_ids 传入单个非 JSON 字符串时应包裹为单元素列表"""
        results = await search_knowledge_base.coroutine(
            query="测试查询", book_ids="single-id", top_k=10
        )

        from src.core.knowledge_qa.tools import _get_http_client

        client = _get_http_client()
        client.search_chunks.assert_called_once_with(
            question="测试查询",
            book_ids=["single-id"],
            limit=10,
        )
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_call_count_limit(self):
        """超出 max_calls 次调用应返回 call_limit_reached"""
        max_calls = 3
        # 重新初始化，使用自定义 max_calls
        clear_tool_call_state()
        init_tool_call_state(max_calls=max_calls)

        for i in range(max_calls):
            await search_knowledge_base.ainvoke(
                {"query": f"查询_{i}", "book_ids": None, "top_k": 5}
            )

        # 第 max_calls+1 次应被拒绝
        results = await search_knowledge_base.ainvoke(
            {"query": "超额查询", "book_ids": None, "top_k": 5}
        )

        assert len(results) == 1
        assert results[0]["info"] == "call_limit_reached"
        assert "搜索次数上限" in results[0]["message"]
        assert results[0]["total_calls"] == max_calls + 1

    @pytest.mark.asyncio
    async def test_duplicate_query_detection(self):
        """相同查询第二次调用应返回 duplicate_query"""
        first = await search_knowledge_base.ainvoke(
            {"query": "重复查询", "book_ids": None, "top_k": 5}
        )
        assert len(first) == 1  # 新格式：1 个摘要 dict

        second = await search_knowledge_base.ainvoke(
            {"query": "重复查询", "book_ids": None, "top_k": 5}
        )

        assert len(second) == 1
        assert second[0]["info"] == "duplicate_query"
        assert "已经用相同的关键词搜索过" in second[0]["message"]
        assert second[0]["original_query"] == "重复查询"

    @pytest.mark.asyncio
    async def test_http_client_not_set_raises_runtime_error(self):
        """HTTP 客户端未设置时应抛出 RuntimeError"""
        clear_http_client()

        with pytest.raises(RuntimeError, match="HTTP 客户端未设置"):
            await search_knowledge_base.ainvoke(
                {"query": "测试查询", "book_ids": None, "top_k": 5}
            )

    @pytest.mark.asyncio
    async def test_retry_on_httpx_errors(self):
        """httpx 超时/连接错误后应自动重试一次，重试成功则正常返回摘要"""
        from src.core.knowledge_qa.tools import _get_http_client

        client = _get_http_client()
        client.search_chunks = AsyncMock(
            side_effect=[
                httpx.TimeoutException("连接超时"),
                [{"chunk_id": "c2", "text": "重试成功"}],
            ]
        )

        results = await search_knowledge_base.ainvoke(
            {"query": "超时测试", "book_ids": None, "top_k": 5}
        )

        # 新格式：返回 1 个摘要 dict
        assert isinstance(results, list)
        assert len(results) == 1
        assert "summary" in results[0]
        assert results[0]["hit_count"] == 1
        assert client.search_chunks.call_count == 2
