"""知识问答全流程 Live 测试

从 DashScope API 到完整 LangGraph 图，逐层验证真实调用链路。
需要 DASHSCOPE_API_KEY 环境变量（.env.dev 中已配置即可）。

层级:
  L1: DashScope 兼容端点基本连通
  L2: Tool calling 支持
  L3: Structured output (function_calling) 收敛
  L4: create_react_agent + response_format 正常终止（修复 GraphRecursionError）
  L5: 完整 match_books 节点（真实 LLM + mock RAG）
  L6: 完整 9 节点 graph（真实 LLM + mock RAG）

运行: cd backend && uv run pytest tests/integration/knowledge_qa/test_live_pipeline.py -v -s
"""

import asyncio
import json
import os
import time
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock

import pytest


# ==================== 前置检查 ====================

DASHSCOPE_API_KEY = os.environ.get("DASHSCOPE_API_KEY") or os.environ.get(
    "DASHSCOPE_API_KEY"
)

# 如果从 .env.dev 加载
if not DASHSCOPE_API_KEY:
    _env_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env.dev")
    if os.path.exists(_env_path):
        with open(_env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("DASHSCOPE_API_KEY="):
                    DASHSCOPE_API_KEY = line.split("=", 1)[1].strip()
                    break

pytestmark = pytest.mark.skipif(
    not DASHSCOPE_API_KEY,
    reason="需要 DASHSCOPE_API_KEY（设置环境变量或在 .env.dev 中配置）",
)


# ==================== Mock RAG 数据 ====================

MOCK_RAG_RESULTS: List[Dict[str, Any]] = [
    {
        "chunk_id": "chunk-001",
        "text": "幼儿注意力发展特点是儿童认知发展的重要组成部分。研究表明，3-6岁儿童的注意力持续时间通常为5-15分钟，"
        "这是正常的发育阶段。注意力不集中可能表现为：无法完成一项活动就转向下一项、"
        "对需要持续注意的任务表现出困难、容易被外界刺激分散注意力等。",
        "chapter": "第3章",
        "section": "3.2 注意力发展",
        "page": "45",
        "book_title": "儿童发展心理学",
        "source_document_id": "doc-001",
        "score": 0.92,
    },
    {
        "chunk_id": "chunk-002",
        "text": "运动干预对改善儿童注意力具有显著效果。有氧运动如跑步、跳绳等能促进前额叶皮层发育，"
        "从而提升执行功能和注意力控制能力。建议每天进行30分钟中等强度的有氧运动，"
        "每周至少5次，持续8周以上可观察到明显改善。",
        "chapter": "第5章",
        "section": "5.1 运动与认知发展",
        "page": "89",
        "book_title": "儿童发展心理学",
        "source_document_id": "doc-001",
        "score": 0.88,
    },
    {
        "chunk_id": "chunk-003",
        "text": "感觉统合训练是通过有目的的感觉刺激活动，帮助儿童大脑更好地组织和处理感觉信息。"
        "常用的感觉统合训练包括：平衡木训练、触觉游戏、前庭刺激活动等。"
        "这些训练对注意力不集中的儿童尤其有效。",
        "chapter": "第7章",
        "section": "7.3 感觉统合训练方法",
        "page": "134",
        "book_title": "感觉统合与儿童发展",
        "source_document_id": "doc-002",
        "score": 0.85,
    },
    {
        "chunk_id": "chunk-004",
        "text": "精细动作训练如拼图、串珠、剪纸等活动可以帮助儿童提高专注力和手眼协调能力。"
        "每次训练15-20分钟，每周3-4次。训练过程中应遵循由简到难的原则，"
        "根据儿童的完成情况逐步增加难度。",
        "chapter": "第4章",
        "section": "4.2 精细动作训练",
        "page": "72",
        "book_title": "儿童运动发展指南",
        "source_document_id": "doc-003",
        "score": 0.82,
    },
]


class MockRagHttpClient:
    """模拟 RAG HTTP 客户端，返回预设的检索结果"""

    async def search_chunks(
        self,
        question: str,
        book_ids: list | None = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        return MOCK_RAG_RESULTS[:limit]

    async def close(self):
        pass


# ==================== Fixtures ====================


@pytest.fixture(autouse=True)
def _clear_factory_cache():
    from src.core.llm.factory import LLMServiceFactoryCompat

    LLMServiceFactoryCompat._raw_instances.clear()
    yield
    LLMServiceFactoryCompat._raw_instances.clear()


@pytest.fixture
def _setup_live_context():
    """设置知识问答 ContextVar（mock RAG + mock 进度回调）"""
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

    progress_log: list[str] = []

    async def mock_progress(step: str, message: str, **meta):
        progress_log.append(f"[{step}] {message}")
        print(f"  📌 {step}: {message}")

    set_progress_context(callback=mock_progress, task_id="live-test", task_type="knowledge_qa")

    mock_pm = MagicMock()
    mock_pm.get_prompt = AsyncMock(return_value=None)
    set_prompt_manager(mock_pm)

    set_http_client(MockRagHttpClient())
    init_partial_collector()

    yield progress_log

    clear_progress_context()
    clear_prompt_manager()
    clear_partial_collector()
    clear_http_client()


# ==================== L1: 基本连通 ====================


@pytest.mark.asyncio
async def test_l1_dashscope_basic():
    """L1: DashScope 兼容端点 + qwen3.5-27b 基本连通"""
    from langchain_core.messages import HumanMessage

    from src.core.llm.factory import LLMServiceFactoryCompat

    model = LLMServiceFactoryCompat.create_raw(model_name="qwen3.5-27b")
    response = await model.ainvoke(
        [HumanMessage(content="请用一句话回答：1+1等于几？")]
    )
    assert response.content, "L1 失败：API 应返回非空内容"
    print(f"  ✅ L1 通过: {response.content[:80]}")


# ==================== L2: Tool Calling ====================


@pytest.mark.asyncio
async def test_l2_tool_calling():
    """L2: DashScope 兼容端点支持 tool calling"""
    from langchain_core.messages import HumanMessage
    from langchain_core.tools import tool

    from src.core.llm.factory import LLMServiceFactoryCompat

    @tool
    def get_weather(city: str) -> str:
        """获取城市天气"""
        return f"{city}今天晴，25°C"

    model = LLMServiceFactoryCompat.create_raw(model_name="qwen3.5-27b")
    model_with_tools = model.bind_tools([get_weather])

    response = await model_with_tools.ainvoke(
        [HumanMessage(content="北京今天天气怎么样？")]
    )
    assert response.tool_calls or response.content, "L2 失败：应返回 tool_calls 或内容"

    if response.tool_calls:
        tc = response.tool_calls[0]
        print(f"  ✅ L2 通过: tool_call={tc['name']}({tc['args']})")
    else:
        print(f"  ✅ L2 通过（模型直接回答）: {response.content[:80]}")


# ==================== L3: Structured Output ====================


@pytest.mark.asyncio
async def test_l3_structured_output_function_calling():
    """L3: with_structured_output(method='function_calling') 能收敛"""
    from langchain_core.messages import HumanMessage
    from pydantic import BaseModel, Field

    from src.core.llm.factory import LLMServiceFactoryCompat

    class SimpleAnswer(BaseModel):
        answer: str = Field(description="回答内容")
        confidence: float = Field(description="置信度 0-1")

    model = LLMServiceFactoryCompat.create_raw(model_name="qwen3.5-27b")
    structured_model = model.with_structured_output(SimpleAnswer)

    result = await structured_model.ainvoke(
        [HumanMessage(content="请回答：太阳从哪个方向升起？并给出置信度。")]
    )
    assert isinstance(result, SimpleAnswer), f"L3 失败：应为 SimpleAnswer，实际: {type(result)}"
    assert result.answer, "L3 失败：answer 不应为空"
    print(f"  ✅ L3 通过: answer={result.answer[:60]}, confidence={result.confidence}")


# ==================== L4: create_react_agent + response_format ====================


@pytest.mark.asyncio
async def test_l4_react_agent_with_response_format():
    """L4: create_react_agent + response_format 正常终止（不触发 GraphRecursionError）

    这是修复 GraphRecursionError 的核心验证：
    DashScopeChatOpenAI.with_structured_output 默认 method='function_calling'，
    确保代理循环能正确收敛并产出 structured_response。
    """
    from langchain_core.tools import tool
    from langgraph.prebuilt import create_react_agent
    from pydantic import BaseModel, Field

    from src.core.llm.factory import LLMServiceFactoryCompat

    class BookRecommendation(BaseModel):
        book_name: str = Field(description="推荐的书名")
        reason: str = Field(description="推荐理由")

    @tool
    def search_books(topic: str) -> str:
        """搜索相关书籍"""
        return f"找到关于'{topic}'的书籍：《儿童发展心理学》、《感觉统合与儿童发展》"

    model = LLMServiceFactoryCompat.create_raw(model_name="qwen3.5-27b")

    agent = create_react_agent(
        model=model,
        tools=[search_books],
        response_format=BookRecommendation,
        prompt="你是一个书籍推荐助手。请搜索相关书籍并推荐一本最相关的。",
    )

    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": "推荐一本关于儿童注意力的书"}]},
        config={"recursion_limit": 15},
    )

    structured = result.get("structured_response")
    assert structured is not None, "L4 失败：structured_response 为空（可能触发递归循环）"
    assert isinstance(structured, BookRecommendation), (
        f"L4 失败：应为 BookRecommendation，实际: {type(structured)}"
    )
    assert structured.book_name, "L4 失败：book_name 不应为空"
    print(f"  ✅ L4 通过: book={structured.book_name}, reason={structured.reason[:60]}")


# ==================== L5: 单节点 match_books ====================


@pytest.mark.asyncio
async def test_l5_match_books_node(_setup_live_context):
    """L5: match_books 节点端到端执行（真实 LLM + mock RAG）

    验证：create_section_agent 创建的 ReAct Agent 能调用 search_knowledge_base 工具，
    并产出 MatchedBookSchema 结构化输出。
    """
    from src.core.knowledge_qa.graph import create_knowledge_qa_graph
    from src.schemas.knowledge_qa import KnowledgeQAState

    graph = create_knowledge_qa_graph()
    result = await graph.ainvoke(
        KnowledgeQAState(
            question="孩子5岁，注意力不集中，怎么办？",
        )
    )

    books = result["matched_books_detail"]
    assert len(books) >= 1, f"L5 失败：应匹配到至少 1 本书，实际: {len(books)}"
    assert books[0].title, "L5 失败：书名不应为空"
    assert books[0].book_id, "L5 失败：book_id 不应为空"
    print(f"  ✅ L5 通过: 匹配到 {len(books)} 本书 — {books[0].title}")
    print(f"     book_id={books[0].book_id}, reason={books[0].match_reason[:60]}")


# ==================== L6: 完整 9 节点 graph ====================


@pytest.mark.asyncio
async def test_l6_full_graph_pipeline(_setup_live_context):
    """L6: 完整 9 节点知识问答流水线（真实 LLM + mock RAG）

    match_books → analyze_child → identify_problems → recommend_types
    → plan_outline → plan_expand → conclusion → verify_citations → finalize

    验证所有节点正常执行，最终输出完整报告。
    注意：此测试耗时较长（约 2-5 分钟），因为每个节点都要调用真实 LLM。
    """
    from src.core.knowledge_qa.graph import create_knowledge_qa_graph
    from src.schemas.knowledge_qa import KnowledgeQAState

    graph = create_knowledge_qa_graph()

    start = time.monotonic()
    result = await graph.ainvoke(
        KnowledgeQAState(
            question="孩子5岁，经常精神不集中，一件事没有做完就会做下一件，有什么运动建议？",
        )
    )
    elapsed = time.monotonic() - start

    # --- 基本断言 ---
    assert "completed" in result["current_step"], (
        f"L6 失败：graph 未完成。current_step={result['current_step']}"
    )

    books = result["matched_books_detail"]
    assert len(books) >= 1, f"L6 失败：未匹配到书籍"
    print(f"\n  📚 匹配书籍: {', '.join(b.title for b in books)}")

    sections = result["sections"]
    assert len(sections) >= 4, f"L6 失败：节产出不足，仅 {len(sections)} 节"

    for i in range(1, 6):
        sec = sections.get(i)
        if sec is None:
            print(f"  ⚠️  第{i}节缺失")
            continue
        # 引用统计
        valid_cites = len(sec.citations)
        print(f"  📝 第{i}节 [{sec.title}]: {len(sec.content)} 字, {valid_cites} 条引用")
        assert sec.content, f"L6 失败：第{i}节内容为空"

    # 最终判定
    total_sections = len(sections)
    total_citations = sum(len(sec.citations) for sec in sections.values())
    partial = result.get("partial", True)

    print(f"\n  {'✅' if not partial else '⚠️ '} L6 结果:")
    print(f"     总耗时: {elapsed:.1f}s")
    print(f"     完成节数: {total_sections}/5")
    print(f"     总引用数: {total_citations}")
    print(f"     降级标记: {'是' if partial else '否'}")
    print(f"     错误列表: {result.get('errors', [])}")

    # 至少完成 4 节才算通过（允许第 5 节偶发失败）
    assert total_sections >= 4, f"L6 失败：仅完成 {total_sections} 节，期望 >= 4"
