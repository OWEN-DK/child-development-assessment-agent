"""真实 ReAct Agent 行为测试

目的：观察真实 LLM (qwen3.5-27b) 在 create_react_agent + response_format 下的
实际工具调用行为，验证 P0 死循环问题。

运行方式：
cd backend && uv run pytest tests/integration/knowledge_qa/test_real_react_agent.py -v -s
"""

import asyncio
import json
import logging
import os
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


@pytest.fixture(autouse=True)
def _setup_env():
    """设置测试环境"""
    from src.core.knowledge_qa.tools import (
        clear_http_client,
        set_http_client,
    )
    from src.schemas.knowledge_qa import (
        clear_partial_collector,
        clear_progress_context,
        clear_prompt_manager,
        init_partial_collector,
        set_progress_context,
        set_prompt_manager,
    )

    set_progress_context(
        callback=AsyncMock(),
        task_id="test-real",
        task_type="knowledge_qa",
    )
    mock_pm = MagicMock()
    mock_pm.get_prompt = AsyncMock(return_value=None)
    set_prompt_manager(mock_pm)

    # 使用真实的 HTTP 客户端（指向本地开发服务器 8000 端口）
    from src.utils.http_client import RagHttpClient

    http_client = RagHttpClient(base_url="http://127.0.0.1:8000")
    set_http_client(http_client)
    init_partial_collector()

    yield

    clear_progress_context()
    clear_prompt_manager()
    clear_partial_collector()
    clear_http_client()
    asyncio.get_event_loop().run_until_complete(http_client.close())


@pytest.mark.asyncio
async def test_observe_react_agent_tool_calling_behavior():
    """观察真实 ReAct Agent 的工具调用行为

    核心问题：create_react_agent + response_format 下，LLM 是否会无限循环调用工具？
    """
    from langchain_core.messages import HumanMessage
    from langgraph.prebuilt import create_react_agent
    from pydantic import BaseModel, Field

    from src.core.llm.factory import LLMServiceFactoryCompat
    from src.core.knowledge_qa.tools import search_knowledge_base

    # 定义简单的结构化输出 schema
    class SimpleResponse(BaseModel):
        answer: str = Field(description="回答内容")
        tool_call_count: int = Field(description="工具调用次数")

    # 创建真实 LLM
    model = LLMServiceFactoryCompat.create_raw(
        model_name="qwen3.5-27b",
        temperature=0.3,
    )

    # 创建 ReAct agent（带结构化输出）
    # 注意：不加"最多搜索N次"的限制，观察自然行为
    agent = create_react_agent(
        model=model,
        tools=[search_knowledge_base],
        response_format=SimpleResponse,
        prompt="你是一个儿童发展专家。使用 search_knowledge_base 工具搜索相关信息来回答问题。如果搜索结果不理想，可以换关键词重试。",
        name="test_agent",
    )

    # 记录工具调用
    tool_call_log = []

    # 包装工具来记录调用
    original_tool = search_knowledge_base

    # 运行 agent，观察行为
    print("\n" + "=" * 60)
    print("开始测试：真实 ReAct Agent 行为观察")
    print("=" * 60)

    start_time = time.monotonic()

    try:
        # 使用较低的 recursion_limit 来快速观察行为
        result = await asyncio.wait_for(
            agent.ainvoke(
                {"messages": [{"role": "user", "content": "4岁男孩注意力不集中，如何通过运动改善？"}]},
                config={"recursion_limit": 15},  # 故意设低，观察行为
            ),
            timeout=60,
        )

        elapsed = time.monotonic() - start_time

        print(f"\n✅ Agent 完成，耗时: {elapsed:.1f}s")
        print(f"structured_response 是否存在: {result.get('structured_response') is not None}")

        # 检查 messages 历史
        messages = result.get("messages", [])
        print(f"消息总数: {len(messages)}")

        tool_calls_count = 0
        for msg in messages:
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                tool_calls_count += len(msg.tool_calls)
                for tc in msg.tool_calls:
                    print(f"  工具调用: {tc.get('name', 'unknown')} - args: {str(tc.get('args', {}))[:100]}")

        print(f"工具调用总次数: {tool_calls_count}")

        if result.get("structured_response"):
            structured = result["structured_response"]
            print(f"结构化输出: {structured.model_dump() if hasattr(structured, 'model_dump') else structured}")

    except asyncio.TimeoutError:
        elapsed = time.monotonic() - start_time
        print(f"\n⏰ 超时! 耗时: {elapsed:.1f}s")
        print("这说明 Agent 确实存在死循环或执行过慢的问题")
        raise

    except Exception as e:
        elapsed = time.monotonic() - start_time
        print(f"\n❌ 异常: {type(e).__name__}: {e}")
        print(f"耗时: {elapsed:.1f}s")

        # 检查是否是 recursion_limit 错误
        if "recursion_limit" in str(e).lower() or "graphrecursionerror" in type(e).__name__.lower():
            print("🔍 确认：这是 GraphRecursionError，符合 P0 问题描述")
        raise


@pytest.mark.asyncio
async def test_observe_tool_call_count_with_different_limits():
    """测试不同 recursion_limit 下的工具调用行为

    验证：提升 limit 是否真的让更多节点失败（P0 文档描述的现象）
    """
    from langgraph.prebuilt import create_react_agent
    from pydantic import BaseModel, Field

    from src.core.llm.factory import LLMServiceFactoryCompat
    from src.core.knowledge_qa.tools import search_knowledge_base

    class SimpleResponse(BaseModel):
        answer: str = Field(description="回答内容")

    model = LLMServiceFactoryCompat.create_raw(
        model_name="qwen3.5-27b",
        temperature=0.3,
    )

    results = {}

    for limit in [10, 15, 20, 25, 30]:
        print(f"\n{'='*40}")
        print(f"测试 recursion_limit={limit}")
        print(f"{'='*40}")

        agent = create_react_agent(
            model=model,
            tools=[search_knowledge_base],
            response_format=SimpleResponse,
            prompt="你是一个儿童发展专家。使用 search_knowledge_base 工具搜索信息。如果找不到信息，直接基于你的知识回答。",
            name=f"test_limit_{limit}",
        )

        start = time.monotonic()
        try:
            result = await asyncio.wait_for(
                agent.ainvoke(
                    {"messages": [{"role": "user", "content": "儿童运动发展"}]},
                    config={"recursion_limit": limit},
                ),
                timeout=30,
            )
            elapsed = time.monotonic() - start
            messages = result.get("messages", [])
            tool_calls = sum(1 for m in messages if hasattr(m, "tool_calls") and m.tool_calls)
            has_structured = result.get("structured_response") is not None

            results[limit] = {
                "status": "success",
                "elapsed": elapsed,
                "tool_calls": tool_calls,
                "has_structured": has_structured,
                "message_count": len(messages),
            }
            print(f"✅ 成功 - 耗时:{elapsed:.1f}s, 工具调用:{tool_calls}, 有结构化输出:{has_structured}")

        except Exception as e:
            elapsed = time.monotonic() - start
            results[limit] = {
                "status": "failed",
                "error": str(e)[:100],
                "elapsed": elapsed,
            }
            print(f"❌ 失败 - {type(e).__name__}: {str(e)[:80]}")

    print("\n" + "=" * 60)
    print("汇总:")
    for limit, r in results.items():
        print(f"  limit={limit}: {r}")


@pytest.mark.asyncio
async def test_search_knowledge_base_directly():
    """直接测试 search_knowledge_base 工具是否可用"""
    from src.core.knowledge_qa.tools import search_knowledge_base

    print("\n测试 search_knowledge_base 工具...")

    try:
        results = await search_knowledge_base.ainvoke({"query": "儿童运动发展"})
        print(f"搜索结果数: {len(results) if isinstance(results, list) else 'N/A'}")
        if isinstance(results, list) and results:
            print(f"第一条结果: {str(results[0])[:200]}")
        elif isinstance(results, list) and not results:
            print("⚠️ 搜索结果为空")
        return results
    except Exception as e:
        print(f"❌ 搜索失败: {type(e).__name__}: {e}")
        raise
