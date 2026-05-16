"""节点执行器单元测试

覆盖 P0 闭环节点（6 个）和 P1 查询理解节点（4 个）。
"""
import asyncio
from unittest.mock import MagicMock, patch

import pytest

from src.core.pipeline.node_context import AuthContext, NodeContext
from src.core.pipeline.node_result import NodeResult


# ══════════════════════════════════════════════════════
# 共享 fixtures + helpers
# ══════════════════════════════════════════════════════

@pytest.fixture
def auth():
    return AuthContext(tenant_id="t-test", user_id="u-1", roles=["admin"])


@pytest.fixture
def ctx(auth):
    return NodeContext(
        input_data="测试查询",
        config={},
        auth=auth,
        node_id="test-node-1",
        node_type="unknown",
        knowledge_base_id="kb-test",
    )


def _run(coro):
    """同步运行 async 函数"""
    return asyncio.run(coro)


# ══════════════════════════════════════════════════════
# P0 闭环节点：检索策略
# ══════════════════════════════════════════════════════

class TestBM25SearchExecutor:
    """BM25 检索节点"""

    def test_validate_config_default(self):
        from src.core.pipeline.nodes.retrieval.bm25_search import BM25SearchExecutor
        e = BM25SearchExecutor()
        errors = e.validate_config({})
        # 基类默认返回空列表（无校验）
        assert isinstance(errors, list)

    def test_execute_empty_query(self, ctx):
        from src.core.pipeline.nodes.retrieval.bm25_search import BM25SearchExecutor
        ctx.input_data = ""
        e = BM25SearchExecutor()
        result = _run(e.execute(ctx))
        assert isinstance(result, NodeResult)
        assert result.output == []

    def test_execute_no_kb_id(self, ctx):
        from src.core.pipeline.nodes.retrieval.bm25_search import BM25SearchExecutor
        ctx.knowledge_base_id = ""
        e = BM25SearchExecutor()
        result = _run(e.execute(ctx))
        assert isinstance(result, NodeResult)

    def test_node_metadata(self):
        from src.core.pipeline.nodes.retrieval.bm25_search import BM25SearchExecutor
        e = BM25SearchExecutor()
        assert e.category == "retrieval"
        assert e.node_type == "BM25SearchExecutor"


class TestVectorSearchExecutor:
    """向量检索节点"""

    def test_validate_config_default(self):
        from src.core.pipeline.nodes.retrieval.vector_search import VectorSearchExecutor
        e = VectorSearchExecutor()
        errors = e.validate_config({})
        assert isinstance(errors, list)

    def test_execute_empty_query(self, ctx):
        from src.core.pipeline.nodes.retrieval.vector_search import VectorSearchExecutor
        ctx.input_data = ""
        e = VectorSearchExecutor()
        result = _run(e.execute(ctx))
        assert result.output == []

    def test_execute_no_kb_id(self, ctx):
        from src.core.pipeline.nodes.retrieval.vector_search import VectorSearchExecutor
        ctx.knowledge_base_id = ""
        e = VectorSearchExecutor()
        result = _run(e.execute(ctx))
        assert result.output == []
        assert "error" in result.metadata

    def test_node_metadata(self):
        from src.core.pipeline.nodes.retrieval.vector_search import VectorSearchExecutor
        e = VectorSearchExecutor()
        assert e.category == "retrieval"


class TestHybridSearchExecutor:
    """混合检索节点"""

    def test_validate_config_default(self):
        from src.core.pipeline.nodes.retrieval.hybrid_search import HybridSearchExecutor
        e = HybridSearchExecutor()
        errors = e.validate_config({})
        assert isinstance(errors, list)

    def test_execute_empty_query(self, ctx):
        from src.core.pipeline.nodes.retrieval.hybrid_search import HybridSearchExecutor
        ctx.input_data = ""
        e = HybridSearchExecutor()
        result = _run(e.execute(ctx))
        assert result.output == []

    def test_execute_no_kb_id(self, ctx):
        from src.core.pipeline.nodes.retrieval.hybrid_search import HybridSearchExecutor
        ctx.knowledge_base_id = ""
        e = HybridSearchExecutor()
        result = _run(e.execute(ctx))
        assert isinstance(result, NodeResult)

    def test_node_metadata(self):
        from src.core.pipeline.nodes.retrieval.hybrid_search import HybridSearchExecutor
        e = HybridSearchExecutor()
        assert e.category == "retrieval"


# ══════════════════════════════════════════════════════
# P0 闭环节点：聚合层
# ══════════════════════════════════════════════════════

class TestQueryAnalyzerExecutor:
    """查询分析节点"""

    def test_execute_empty_query(self, ctx):
        from src.core.pipeline.nodes.aggregation.query_analyzer import QueryAnalyzerExecutor
        ctx.input_data = ""
        e = QueryAnalyzerExecutor()
        result = _run(e.execute(ctx))
        assert isinstance(result.output, list)
        assert len(result.output) == 0

    @patch("src.core.pipeline.nodes.aggregation.query_analyzer.call_llm_json")
    def test_execute_single_domain(self, mock_llm, ctx):
        from src.core.pipeline.nodes.aggregation.query_analyzer import QueryAnalyzerExecutor
        mock_llm.return_value = [
            {"domain_id": "dom-1", "domain_name": "心血管", "confidence": 0.9, "reason": "查询涉及心血管术语"}
        ]
        ctx.config = {
            "model": "qwen-turbo",
            "domain_keywords": {
                "dom-1": {"name": "心血管域", "keywords": ["心血管", "心脏"], "kb_id": "kb-1"}
            },
        }

        e = QueryAnalyzerExecutor()
        result = _run(e.execute(ctx))
        assert len(result.output) == 1
        assert result.output[0]["domain_id"] == "dom-1"

    @patch("src.core.pipeline.nodes.aggregation.query_analyzer.call_llm_json")
    def test_execute_llm_returns_list_of_dicts(self, mock_llm, ctx):
        from src.core.pipeline.nodes.aggregation.query_analyzer import QueryAnalyzerExecutor
        mock_llm.return_value = [
            {"domain_id": "dom-1", "domain_name": "域1", "confidence": 0.8, "reason": "匹配关键词"},
            {"domain_id": "dom-2", "domain_name": "域2", "confidence": 0.6, "reason": "可能相关"},
        ]
        ctx.config = {
            "model": "qwen-turbo",
            "domain_keywords": {
                "dom-1": {"name": "域1", "keywords": ["中医"], "kb_id": "kb-1"},
                "dom-2": {"name": "域2", "keywords": ["西医"], "kb_id": "kb-2"},
            },
        }
        e = QueryAnalyzerExecutor()
        result = _run(e.execute(ctx))
        assert len(result.output) == 2

    def test_node_metadata(self):
        from src.core.pipeline.nodes.aggregation.query_analyzer import QueryAnalyzerExecutor
        e = QueryAnalyzerExecutor()
        assert e.category == "aggregation"


class TestDomainDispatchExecutor:
    """域分发节点"""

    def test_execute_empty_plans(self, ctx):
        from src.core.pipeline.nodes.aggregation.domain_dispatch import DomainDispatchExecutor
        ctx.input_data = []
        e = DomainDispatchExecutor()
        result = _run(e.execute(ctx))
        assert result.output == []

    def test_node_metadata(self):
        from src.core.pipeline.nodes.aggregation.domain_dispatch import DomainDispatchExecutor
        e = DomainDispatchExecutor()
        assert e.category == "aggregation"


class TestUnifiedGenerateExecutor:
    """统一答案合成节点"""

    def test_execute_empty_sources(self, ctx):
        from src.core.pipeline.nodes.aggregation.unified_generate import UnifiedGenerateExecutor
        ctx.input_data = {"query": "测试", "sources": [], "conflict_report": {}}
        e = UnifiedGenerateExecutor()
        result = _run(e.execute(ctx))
        assert isinstance(result.output, str)

    def test_execute_without_input_dict(self, ctx):
        from src.core.pipeline.nodes.aggregation.unified_generate import UnifiedGenerateExecutor
        ctx.input_data = "直接传字符串查询"
        e = UnifiedGenerateExecutor()
        result = _run(e.execute(ctx))
        assert isinstance(result.output, str)

    @patch("src.core.pipeline.nodes.aggregation.unified_generate.call_llm")
    def test_execute_with_sources(self, mock_llm, ctx):
        from src.core.pipeline.nodes.aggregation.unified_generate import UnifiedGenerateExecutor
        mock_llm.return_value = "基于检索结果的合成答案"
        ctx.input_data = {
            "query": "高血压如何用药",
            "sources": [{"content": "CCC 指南建议...", "score": 0.9}],
            "conflict_report": {},
        }
        e = UnifiedGenerateExecutor()
        result = _run(e.execute(ctx))
        assert "合成答案" in result.output

    def test_node_metadata(self):
        from src.core.pipeline.nodes.aggregation.unified_generate import UnifiedGenerateExecutor
        e = UnifiedGenerateExecutor()
        assert e.category == "aggregation"


# ══════════════════════════════════════════════════════
# P1 查询理解节点
# ══════════════════════════════════════════════════════

class TestQueryRewriteExecutor:
    """查询改写节点"""

    def test_execute_empty_query(self, ctx):
        from src.core.pipeline.nodes.query.query_rewrite import QueryRewriteExecutor
        ctx.input_data = ""
        e = QueryRewriteExecutor()
        result = _run(e.execute(ctx))
        assert result.output == []

    @patch("src.core.pipeline.nodes.query.query_rewrite.call_llm_json")
    def test_execute_with_llm(self, mock_llm, ctx):
        from src.core.pipeline.nodes.query.query_rewrite import QueryRewriteExecutor
        mock_llm.return_value = ["改写变体1", "改写变体2"]
        e = QueryRewriteExecutor()
        result = _run(e.execute(ctx))
        assert len(result.output) == 2
        assert "改写变体1" in result.output

    @patch("src.core.pipeline.nodes.query.query_rewrite.call_llm_json")
    def test_execute_llm_returns_invalid_format(self, mock_llm, ctx):
        from src.core.pipeline.nodes.query.query_rewrite import QueryRewriteExecutor
        mock_llm.return_value = "非数组字符串"
        e = QueryRewriteExecutor()
        result = _run(e.execute(ctx))
        # 应降级返回原查询
        assert result.output == [ctx.input_data]

    def test_node_metadata(self):
        from src.core.pipeline.nodes.query.query_rewrite import QueryRewriteExecutor
        e = QueryRewriteExecutor()
        assert e.category == "query"
        assert e.input_type == "str"
        assert e.output_type == "list[str]"


class TestSynonymExpandExecutor:
    """同义词扩展节点"""

    def test_execute_empty_query(self, ctx):
        from src.core.pipeline.nodes.query.synonym_expand import SynonymExpandExecutor
        ctx.input_data = ""
        e = SynonymExpandExecutor()
        result = _run(e.execute(ctx))
        assert isinstance(result.output, str)
        assert result.output == ""

    def test_execute_basic(self, ctx):
        from src.core.pipeline.nodes.query.synonym_expand import SynonymExpandExecutor
        ctx.input_data = "高血压"
        e = SynonymExpandExecutor()
        result = _run(e.execute(ctx))
        assert isinstance(result.output, str)
        assert len(result.output) > 0

    def test_node_metadata(self):
        from src.core.pipeline.nodes.query.synonym_expand import SynonymExpandExecutor
        e = SynonymExpandExecutor()
        assert e.category == "query"


class TestTermNormalizeExecutor:
    """术语标准化节点"""

    def test_execute_empty_query(self, ctx):
        from src.core.pipeline.nodes.query.term_normalize import TermNormalizeExecutor
        ctx.input_data = ""
        e = TermNormalizeExecutor()
        result = _run(e.execute(ctx))
        assert result.output == ""

    def test_execute_basic(self, ctx):
        from src.core.pipeline.nodes.query.term_normalize import TermNormalizeExecutor
        ctx.input_data = "心脏病"
        e = TermNormalizeExecutor()
        result = _run(e.execute(ctx))
        assert isinstance(result.output, str)
        assert len(result.output) > 0

    def test_node_metadata(self):
        from src.core.pipeline.nodes.query.term_normalize import TermNormalizeExecutor
        e = TermNormalizeExecutor()
        assert e.category == "query"


class TestStopwordFilterExecutor:
    """禁用词过滤节点"""

    def test_execute_empty_query(self, ctx):
        from src.core.pipeline.nodes.query.stopword_filter import StopwordFilterExecutor
        ctx.input_data = ""
        e = StopwordFilterExecutor()
        result = _run(e.execute(ctx))
        assert result.output == ""

    def test_execute_disabled(self, ctx):
        from src.core.pipeline.nodes.query.stopword_filter import StopwordFilterExecutor
        ctx.input_data = "这个是一个测试查询"
        ctx.config = {"enabled": False}
        e = StopwordFilterExecutor()
        result = _run(e.execute(ctx))
        assert result.output == "这个是一个测试查询"

    def test_execute_filter_enabled(self, ctx):
        from src.core.pipeline.nodes.query.stopword_filter import StopwordFilterExecutor
        ctx.input_data = "这个是一个测试查询"
        ctx.config = {"enabled": True, "stop_words": ["这个", "一个"]}
        e = StopwordFilterExecutor()
        result = _run(e.execute(ctx))
        assert "这个" not in result.output
        assert "一个" not in result.output
        assert "测试查询" in result.output

    def test_node_metadata(self):
        from src.core.pipeline.nodes.query.stopword_filter import StopwordFilterExecutor
        e = StopwordFilterExecutor()
        assert e.category == "query"


# ══════════════════════════════════════════════════════
# 降级链测试
# ══════════════════════════════════════════════════════

class TestDegradationChain:
    """降级链"""

    def test_registry_register_and_get_chain(self):
        from src.core.pipeline.degradation import DegradationRegistry
        reg = DegradationRegistry()
        reg.register("node-1", strategies=["skip_node", "reroute"])
        chain = reg.get_chain("node-1")
        assert "skip_node" in chain
        assert "reroute" in chain
        assert "abort" in chain  # 自动追加

    def test_registry_build_from_config(self):
        from src.core.pipeline.degradation import DegradationRegistry
        config = {
            "domains": [{
                "id": "d1",
                "pipeline": {
                    "nodes": [],
                    "edges": [],
                    "degradation_edges": [
                        {"source": "vs", "strategies": ["skip_node", "degrade_cache"]}
                    ],
                },
            }],
        }
        reg = DegradationRegistry()
        reg.build_from_pipeline_config(config)
        chain = reg.get_chain("vs")
        assert "skip_node" in chain
        assert "degrade_cache" in chain

    def test_wrapper_skip_node_on_error(self):
        from src.core.pipeline.degradation import DegradationRegistry, NodeExecutorWrapper
        from src.core.pipeline.base_node import BaseNodeExecutor

        class FailingExecutor(BaseNodeExecutor):
            async def execute(self, context):
                raise RuntimeError("模拟失败")

            @property
            def category(self):
                return "test"

        from src.core.pipeline.registry import registry
        registry.register("failing_test_skip", FailingExecutor)

        dreg = DegradationRegistry()
        dreg.register("node-x", strategies=["skip_node"])
        wrapper = NodeExecutorWrapper(dreg)

        ctx = NodeContext(
            input_data="hello",
            node_id="node-x",
            node_type="failing_test_skip",
        )

        result = _run(wrapper.execute("node-x", ctx))
        assert result.degraded is True
        assert result.degradation_strategy == "skip_node"
        assert result.output == "hello"

    def test_wrapper_abort_on_empty_chain(self):
        from src.core.pipeline.degradation import DegradationRegistry, NodeExecutorWrapper
        from src.core.pipeline.base_node import BaseNodeExecutor
        from src.core.pipeline.exceptions import DegradationChainExhaustedError

        class AlwaysFailExecutor(BaseNodeExecutor):
            async def execute(self, context):
                raise RuntimeError("永远失败")

            @property
            def category(self):
                return "test"

        from src.core.pipeline.registry import registry
        registry.register("always_fail_abort", AlwaysFailExecutor)

        dreg = DegradationRegistry()
        wrapper = NodeExecutorWrapper(dreg)

        ctx = NodeContext(
            input_data="hello",
            node_id="no-strategy",
            node_type="always_fail_abort",
        )

        with pytest.raises(DegradationChainExhaustedError):
            _run(wrapper.execute("no-strategy", ctx))


# ══════════════════════════════════════════════════════
# NodeRegistry 测试
# ══════════════════════════════════════════════════════

class TestNodeRegistry:
    """节点注册表"""

    def test_all_core_types_registered(self):
        from src.core.pipeline.registry import registry
        types = registry.list_types()
        # 核心 28 种 + 测试注册（degradation 测试用）
        assert len(types) >= 28
        assert "vector_search" in types
        assert "bm25_search" in types
        assert "hybrid_search" in types
        assert "query_analyzer" in types
        assert "domain_dispatch" in types
        assert "unified_generate" in types
        assert "query_rewrite" in types

    def test_list_by_category(self):
        from src.core.pipeline.registry import registry
        cats = registry.list_by_category()
        assert "retrieval" in cats
        assert "aggregation" in cats
        assert "query" in cats
        assert "security" in cats
        assert "quality" in cats
        assert "performance" in cats
        assert "synthesis" in cats

    def test_create_executor(self):
        from src.core.pipeline.registry import registry
        executor = registry.create_executor("vector_search")
        assert executor is not None
        assert executor.category == "retrieval"

    def test_get_unknown_type_raises(self):
        from src.core.pipeline.registry import registry
        with pytest.raises(KeyError, match="节点类型未注册"):
            registry.get("nonexistent_type")
