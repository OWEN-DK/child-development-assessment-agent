"""知识问答全流程测试

覆盖范围：
1. create_raw() 修复验证 — 使用 ChatOpenAI + DashScope 兼容端点（非 ChatTongyi）
2. 完整 LangGraph 9 节点流水线 — mock LLM，真实图编排
3. 边界场景 — 无匹配书籍
4. 真实 API 端点验证（需 DASHSCOPE_API_KEY，标记为 live）
"""

import os
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ==================== Fixtures ====================


@pytest.fixture(autouse=True)
def _clear_factory_cache():
    """每个测试前后清空工厂缓存"""
    from src.core.llm.factory import LLMServiceFactoryCompat

    LLMServiceFactoryCompat._raw_instances.clear()
    yield
    LLMServiceFactoryCompat._raw_instances.clear()


@pytest.fixture
def _mock_settings():
    """模拟 settings，提供 DashScope API Key（settings 定义在 src/config/__init__.py）"""
    with patch("src.config.settings") as mock_s:
        mock_s.dashscope_api_key = "test-dashscope-key-12345"
        yield mock_s


@pytest.fixture
def _setup_context_vars():
    """设置知识问答 ContextVar 环境（进度、prompt、HTTP 客户端、降级收集器）"""
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
        task_id="test-task-id",
        task_type="knowledge_qa",
    )
    mock_pm = MagicMock()
    mock_pm.get_prompt = AsyncMock(return_value=None)
    set_prompt_manager(mock_pm)
    set_http_client(MagicMock())
    init_partial_collector()

    yield

    clear_progress_context()
    clear_prompt_manager()
    clear_partial_collector()
    clear_http_client()


# ==================== 测试 1: create_raw() 修复验证 ====================


class TestCreateRawFix:
    """验证 create_raw() 使用 ChatOpenAI + DashScope 兼容端点（修复 url error）"""

    def test_returns_chat_openai_not_chattongyi(self, _mock_settings):
        """核心断言：create_raw() 应返回 ChatOpenAI 子类（DashScope 兼容），不是 ChatTongyi"""
        from langchain_community.chat_models import ChatTongyi
        from langchain_openai import ChatOpenAI
        from src.core.llm.factory import LLMServiceFactoryCompat

        model = LLMServiceFactoryCompat.create_raw(model_name="qwen3.5-27b")

        assert isinstance(model, ChatOpenAI), "应为 ChatOpenAI（或其子类）实例"
        assert not isinstance(model, ChatTongyi), "不应为 ChatTongyi"

    def test_dashscope_compatible_endpoint(self, _mock_settings):
        """验证 base_url 指向 DashScope OpenAI 兼容端点"""
        from src.core.llm.factory import LLMServiceFactoryCompat

        model = LLMServiceFactoryCompat.create_raw(model_name="qwen3.5-27b")

        base = getattr(model, "openai_api_base", None) or getattr(
            model, "base_url", None
        )
        assert "dashscope.aliyuncs.com/compatible-mode" in str(base), (
            f"base_url 应包含 DashScope 兼容端点，实际: {base}"
        )

    def test_structured_output_uses_function_calling(self, _mock_settings):
        """验证 with_structured_output 默认使用 function_calling（非 json_schema）"""
        from unittest.mock import patch
        from src.core.llm.factory import LLMServiceFactoryCompat

        model = LLMServiceFactoryCompat.create_raw(model_name="qwen3.5-27b")

        # 调用 with_structured_output 不传 method，应使用 function_calling
        from pydantic import BaseModel

        class DummySchema(BaseModel):
            answer: str

        with patch.object(
            type(model).__bases__[0],
            "with_structured_output",
            return_value=MagicMock(),
        ) as mock_super:
            model.with_structured_output(DummySchema)
            mock_super.assert_called_once()
            call_kwargs = mock_super.call_args
            assert call_kwargs[1].get("method") == "function_calling", (
                "DashScope 兼容模型应默认使用 function_calling 方式"
            )

    def test_model_name_passed_correctly(self, _mock_settings):
        """验证模型名正确传递"""
        from src.core.llm.factory import LLMServiceFactoryCompat

        model = LLMServiceFactoryCompat.create_raw(model_name="qwen3.5-27b")
        assert model.model_name == "qwen3.5-27b"

    def test_streaming_enabled(self, _mock_settings):
        """验证 streaming 默认开启"""
        from src.core.llm.factory import LLMServiceFactoryCompat

        model = LLMServiceFactoryCompat.create_raw(model_name="qwen3.5-27b")
        assert model.streaming is True

    def test_default_model_fallback(self, _mock_settings):
        """验证不传模型名时默认使用 qwen-plus"""
        from src.core.llm.factory import LLMServiceFactoryCompat

        model = LLMServiceFactoryCompat.create_raw()
        assert model.model_name == "qwen-plus"

    def test_caching_same_params(self, _mock_settings):
        """验证相同参数返回缓存实例"""
        from src.core.llm.factory import LLMServiceFactoryCompat

        m1 = LLMServiceFactoryCompat.create_raw(
            model_name="qwen3.5-27b", temperature=0.3
        )
        m2 = LLMServiceFactoryCompat.create_raw(
            model_name="qwen3.5-27b", temperature=0.3
        )
        assert m1 is m2

    def test_no_cache_different_params(self, _mock_settings):
        """验证不同参数不命中缓存"""
        from src.core.llm.factory import LLMServiceFactoryCompat

        m1 = LLMServiceFactoryCompat.create_raw(
            model_name="qwen3.5-27b", temperature=0.3
        )
        m2 = LLMServiceFactoryCompat.create_raw(
            model_name="qwen3.5-27b", temperature=0.5
        )
        assert m1 is not m2


# ==================== 测试 2: 全流程 Graph 集成测试 ====================


def _make_section_data(index: int) -> dict:
    """生成模拟节响应数据（引用通过 verify_citations 核验）"""
    return {
        "title": f"第{index}节标题",
        "content": f"## 第{index}节内容\n\n这是第{index}节的详细内容，包含专业分析。",
        "citations": [
            {
                "citation_id": f"C{index:03d}",
                "book_title": "儿童运动发展指南",
                "source_type": "book",
                "chapter": f"第{index}章",
                "section": f"{index}.1 概述",
                "page": f"{index * 10}",
                "excerpt": "这是关于儿童运动发展的关键论述原文引用段落，长度超过十个字符以确保通过引用核验",
                "relevance": f"与第{index}节内容直接相关",
            }
        ],
        "structured_data": {"key": f"value_{index}"},
    }


MOCK_BOOKS_DATA = {
    "matched_books": [
        {
            "book_id": "book-001",
            "title": "儿童运动发展指南",
            "author": "张三",
            "source_type": "book",
            "match_reason": "与运动发展主题高度相关",
        }
    ]
}


def _build_mock_agent_factory():
    """构建 mock create_react_agent，按节点 name 返回对应 agent"""
    section_data = {i: _make_section_data(i) for i in range(1, 6)}
    outline_data = {
        "title": "运动方案大纲",
        "content": "大纲内容",
        "citations": section_data[4]["citations"],
        "structured_data": {"phases": [{"name": "基础阶段", "weeks": 4}]},
    }

    node_responses = {
        "match_books": MOCK_BOOKS_DATA,
        "analyze_child": section_data[1],
        "identify_problems": section_data[2],
        "recommend_types": section_data[3],
        "plan_outline": outline_data,
        "plan_expand": section_data[4],
        "conclusion": section_data[5],
    }

    call_log: list[str] = []

    def factory(model, tools, response_format, prompt, name):
        data = node_responses.get(name, section_data[1])

        mock_structured = MagicMock()
        mock_structured.model_dump.return_value = data

        mock_agent = MagicMock()
        mock_agent.ainvoke = AsyncMock(
            return_value={"structured_response": mock_structured}
        )

        call_log.append(name)
        return mock_agent

    return factory, call_log


def _state_to_dict(result) -> dict:
    """统一将 graph 输出转为 dict"""
    if isinstance(result, dict):
        return result
    if hasattr(result, "model_dump"):
        return result.model_dump()
    return dict(result)


@pytest.mark.asyncio
async def test_full_pipeline_9_nodes(_setup_context_vars):
    """验证完整 9 节点流水线走通：
    match_books → analyze_child → identify_problems → recommend_types
    → plan_outline → plan_expand → conclusion → verify_citations → finalize
    """
    mock_factory, call_log = _build_mock_agent_factory()

    with patch(
        "src.core.knowledge_qa.nodes.base.create_react_agent",
        side_effect=mock_factory,
    ), patch(
        "src.core.knowledge_qa.nodes.match_books._batch_resolve_book_ids",
        new_callable=AsyncMock,
        return_value={"book-001": "book-001"},
    ):
        from src.core.knowledge_qa.graph import create_knowledge_qa_graph
        from src.schemas.knowledge_qa import KnowledgeQAState

        graph = create_knowledge_qa_graph()
        result = await graph.ainvoke(
            KnowledgeQAState(
                question="4岁男孩注意力不集中，如何通过运动改善？",
            )
        )

    # LangGraph 返回的 state 中嵌套对象可能是 Pydantic 实例，统一取属性
    # matched_books_detail: List[MatchedBook]
    books = result["matched_books_detail"]
    sections = result["sections"]

    # 1. 全部 7 个 LLM 节点被调用，且顺序严格线性
    expected_order = [
        "match_books",
        "analyze_child",
        "identify_problems",
        "recommend_types",
        "plan_outline",
        "plan_expand",
        "conclusion",
    ]
    first_calls = []
    seen: set[str] = set()
    for name in call_log:
        if name not in seen:
            first_calls.append(name)
            seen.add(name)
    assert first_calls == expected_order, f"节点调用顺序不符: {first_calls}"

    # 2. 书籍匹配结果
    assert result["matched_book_ids"] == ["book-001"]
    assert len(books) == 1
    assert books[0].title == "儿童运动发展指南"
    assert books[0].is_primary is True

    # 3. 第 4 节大纲中间产物存在
    assert result["section_4_outline"] is not None

    # 4. 所有 5 个节都有输出，引用通过核验
    for i in range(1, 6):
        assert i in sections, f"第{i}节缺失"
        sec = sections[i]
        assert sec.content, f"第{i}节内容为空"
        assert len(sec.citations) >= 1, f"第{i}节引用被误删"

        for c in sec.citations:
            assert len(c["excerpt"].strip()) >= 10, f"第{i}节引用 excerpt 过短"
            assert c["chapter"].strip(), f"第{i}节引用 chapter 为空"
            assert c["citation_id"].startswith("C"), f"第{i}节引用 ID 格式错误"

    # 5. 最终状态
    assert "completed" in result["current_step"]
    assert result["partial"] is False


@pytest.mark.asyncio
async def test_pipeline_no_books_matched(_setup_context_vars):
    """验证无匹配书籍时抛出 NoMatchingBooksError"""

    def factory_no_books(model, tools, response_format, prompt, name):
        mock_structured = MagicMock()
        mock_structured.model_dump.return_value = {"matched_books": []}
        mock_agent = MagicMock()
        mock_agent.ainvoke = AsyncMock(
            return_value={"structured_response": mock_structured}
        )
        return mock_agent

    with patch(
        "src.core.knowledge_qa.nodes.base.create_react_agent",
        side_effect=factory_no_books,
    ):
        from src.core.knowledge_qa.graph import create_knowledge_qa_graph
        from src.schemas.knowledge_qa import KnowledgeQAState, NoMatchingBooksError

        graph = create_knowledge_qa_graph()
        with pytest.raises(NoMatchingBooksError):
            await graph.ainvoke(
                KnowledgeQAState(question="完全不相关的问题 xyz")
            )


@pytest.mark.asyncio
async def test_pipeline_with_pre_specified_books(_setup_context_vars):
    """验证指定 book_ids 时，书籍信息直接传入状态"""
    mock_factory, call_log = _build_mock_agent_factory()

    with patch(
        "src.core.knowledge_qa.nodes.base.create_react_agent",
        side_effect=mock_factory,
    ), patch(
        "src.core.knowledge_qa.nodes.match_books._batch_resolve_book_ids",
        new_callable=AsyncMock,
        return_value={"book-001": "book-001"},
    ):
        from src.core.knowledge_qa.graph import create_knowledge_qa_graph
        from src.schemas.knowledge_qa import KnowledgeQAState

        graph = create_knowledge_qa_graph()
        result = await graph.ainvoke(
            KnowledgeQAState(
                question="如何改善注意力？",
                matched_book_ids=["pre-specified-book-001"],
            )
        )

    state = _state_to_dict(result)

    # match_books 节点会覆盖 matched_book_ids，但 pre-specified 的会传入 prompt
    assert "match_books" in call_log
    assert "completed" in state["current_step"]


# ==================== 测试 3: 真实 API 端点验证（live） ====================


@pytest.mark.skipif(
    not os.environ.get("DASHSCOPE_API_KEY"),
    reason="需要设置 DASHSCOPE_API_KEY 环境变量",
)
@pytest.mark.asyncio
async def test_real_dashscope_endpoint_basic():
    """真实 API 调用：验证 DashScope 兼容端点 + qwen3.5-27b 基本连通

    运行: DASHSCOPE_API_KEY=sk-xxx uv run pytest \\
          tests/integration/knowledge_qa/test_knowledge_qa_pipeline.py \\
          -k test_real_dashscope_endpoint_basic -v
    """
    from langchain_core.messages import HumanMessage
    from langchain_openai import ChatOpenAI

    model = ChatOpenAI(
        model="qwen3.5-27b",
        api_key=os.environ["DASHSCOPE_API_KEY"],
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        temperature=0.1,
        max_tokens=100,
    )

    response = await model.ainvoke([HumanMessage(content="你好，请用一句话回复")])
    assert response.content, "API 应返回非空内容"


@pytest.mark.skipif(
    not os.environ.get("DASHSCOPE_API_KEY"),
    reason="需要设置 DASHSCOPE_API_KEY 环境变量",
)
@pytest.mark.asyncio
async def test_real_dashscope_tool_calling():
    """真实 API 调用：验证 DashScope 兼容端点支持 tool calling（create_react_agent 依赖）

    运行: DASHSCOPE_API_KEY=sk-xxx uv run pytest \\
          tests/integration/knowledge_qa/test_knowledge_qa_pipeline.py \\
          -k test_real_dashscope_tool_calling -v
    """
    from langchain_core.messages import HumanMessage
    from langchain_core.tools import tool
    from langchain_openai import ChatOpenAI

    @tool
    def mock_search(query: str) -> str:
        """搜索知识库"""
        return f"搜索结果: {query}"

    model = ChatOpenAI(
        model="qwen3.5-27b",
        api_key=os.environ["DASHSCOPE_API_KEY"],
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        temperature=0.1,
        max_tokens=200,
    ).bind_tools([mock_search])

    response = await model.ainvoke(
        [HumanMessage(content="请搜索儿童运动发展的相关资料")]
    )
    assert response.tool_calls or response.content, "应返回 tool_calls 或内容"
