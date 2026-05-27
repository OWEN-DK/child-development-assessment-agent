"""真实全流程流水线测试

用真实 LLM + 真实 RAG + 真实 prompts 运行完整 9 节点流水线。
观察每个节点的工具调用次数和总耗时。

运行方式：
cd backend && uv run pytest tests/integration/knowledge_qa/test_real_pipeline.py -v -s
"""

import asyncio
import json
import logging
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

logging.basicConfig(level=logging.INFO)
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
        task_id="test-real-pipeline",
        task_type="knowledge_qa",
    )
    mock_pm = MagicMock()
    mock_pm.get_prompt = AsyncMock(return_value=None)
    set_prompt_manager(mock_pm)

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
async def test_full_pipeline_real():
    """真实全流程测试：观察每个节点的行为"""
    from src.core.knowledge_qa.graph import create_knowledge_qa_graph
    from src.schemas.knowledge_qa import KnowledgeQAState

    graph = create_knowledge_qa_graph()

    state = KnowledgeQAState(
        question="4岁男孩注意力不集中，如何通过运动改善？",
    )

    print("\n" + "=" * 70)
    print("开始真实全流程测试")
    print(f"问题: {state.question}")
    print("=" * 70)

    start = time.monotonic()

    try:
        result = await asyncio.wait_for(
            graph.ainvoke(state),
            timeout=300,  # 5 分钟超时
        )

        elapsed = time.monotonic() - start
        print(f"\n✅ 流水线完成，总耗时: {elapsed:.1f}s")

        # 检查每节结果
        sections = result.get("sections", {})
        print(f"\n节数: {len(sections)}")
        for i in sorted(sections.keys()):
            sec = sections[i]
            content_len = len(sec.content) if sec.content else 0
            citation_count = len(sec.citations) if sec.citations else 0
            print(f"  第{i}节: 内容{content_len}字, 引用{citation_count}条")
            if sec.content and "生成失败" in sec.content:
                print(f"    ⚠️ 降级内容: {sec.content[:100]}")

        # 检查错误
        errors = result.get("errors", [])
        if errors:
            print(f"\n错误 ({len(errors)}):")
            for e in errors:
                print(f"  - {e}")

        # 检查匹配的书籍
        matched = result.get("matched_books_detail", [])
        print(f"\n匹配书籍: {len(matched)}")
        for b in matched:
            print(f"  - {b.title} ({b.match_reason[:50] if b.match_reason else 'N/A'})")

        # 检查最终状态
        current_step = result.get("current_step", [])
        print(f"\n最终状态: {current_step}")
        print(f"partial: {result.get('partial', False)}")

    except asyncio.TimeoutError:
        elapsed = time.monotonic() - start
        print(f"\n⏰ 超时! 耗时: {elapsed:.1f}s")
        raise
    except Exception as e:
        elapsed = time.monotonic() - start
        print(f"\n❌ 异常: {type(e).__name__}: {e}")
        print(f"耗时: {elapsed:.1f}s")
        raise
