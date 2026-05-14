"""PipelineCompiler 单元测试"""
import pytest

from src.core.pipeline.compiler import PipelineCompiler, CompiledPipeline, ExecutionPlan
from src.core.pipeline.exceptions import PipelineCompilationError


@pytest.fixture
def compiler():
    return PipelineCompiler()


@pytest.fixture
def simple_config():
    """简单管道配置（单域 + 聚合）"""
    return {
        "pipeline": {"id": "test-pipeline", "type": "aggregation"},
        "domains": [
            {
                "id": "domain-1",
                "name": "测试域",
                "knowledge_base_id": "kb-1",
                "pipeline": {
                    "nodes": [
                        {"id": "qr", "type": "query_rewrite"},
                        {"id": "vs", "type": "vector_search"},
                    ],
                    "edges": [{"source": "qr", "target": "vs"}],
                },
            }
        ],
        "aggregation": {
            "nodes": [
                {"id": "qa", "type": "query_analyzer"},
                {"id": "dd", "type": "domain_dispatch"},
                {"id": "cf", "type": "cross_fusion"},
                {"id": "ug", "type": "unified_generate"},
            ],
            "edges": [
                {"source": "qa", "target": "dd"},
                {"source": "dd", "target": "cf"},
                {"source": "cf", "target": "ug"},
            ],
        },
    }


class TestPipelineCompiler:
    """编译器测试"""

    def test_compile_simple_config(self, compiler, simple_config):
        """编译简单配置"""
        compiled = compiler.compile(simple_config)
        assert isinstance(compiled, CompiledPipeline)
        assert len(compiled.execution_plan.sorted_ids) == 4
        assert len(compiled.domain_configs) == 1

    def test_validate_structure_missing_pipeline(self, compiler):
        """缺少 pipeline 字段"""
        with pytest.raises(PipelineCompilationError, match="缺少 pipeline"):
            compiler.compile({"domains": []})

    def test_validate_structure_missing_domains(self, compiler):
        """缺少 domains 字段"""
        with pytest.raises(PipelineCompilationError, match="缺少 domains"):
            compiler.compile({"pipeline": {"id": "test"}})

    def test_validate_unknown_node_type(self, compiler):
        """未知节点类型"""
        config = {
            "pipeline": {"id": "test"},
            "domains": [],
            "aggregation": {
                "nodes": [{"id": "x", "type": "unknown_node_type"}],
                "edges": [],
            },
        }
        with pytest.raises(PipelineCompilationError, match="节点类型未注册"):
            compiler.compile(config)

    def test_kahn_sort_linear(self, compiler, simple_config):
        """线性拓扑排序"""
        compiled = compiler.compile(simple_config)
        ids = compiled.execution_plan.sorted_ids
        # qa → dd → cf → ug
        assert ids.index("qa") < ids.index("dd")
        assert ids.index("dd") < ids.index("cf")
        assert ids.index("cf") < ids.index("ug")

    def test_kahn_sort_parallel(self, compiler):
        """并行节点拓扑排序"""
        config = {
            "pipeline": {"id": "test"},
            "domains": [],
            "aggregation": {
                "nodes": [
                    {"id": "a", "type": "query_rewrite"},
                    {"id": "b", "type": "bm25_search"},
                    {"id": "c", "type": "vector_search"},
                    {"id": "d", "type": "result_fusion"},
                ],
                "edges": [
                    {"source": "a", "target": "b"},
                    {"source": "a", "target": "c"},
                    {"source": "b", "target": "d"},
                    {"source": "c", "target": "d"},
                ],
            },
        }
        compiled = compiler.compile(config)
        ids = compiled.execution_plan.sorted_ids
        # a 在最前，d 在最后
        assert ids[0] == "a"
        assert ids[-1] == "d"
        # b 和 c 可以并行（都在 a 之后、d 之前）
        assert ids.index("b") < ids.index("d")
        assert ids.index("c") < ids.index("d")

    def test_cycle_detection(self, compiler):
        """环路检测"""
        config = {
            "pipeline": {"id": "test"},
            "domains": [],
            "aggregation": {
                "nodes": [
                    {"id": "a", "type": "query_rewrite"},
                    {"id": "b", "type": "bm25_search"},
                ],
                "edges": [
                    {"source": "a", "target": "b"},
                    {"source": "b", "target": "a"},  # 环路
                ],
            },
        }
        with pytest.raises(PipelineCompilationError, match="循环依赖"):
            compiler.compile(config)

    def test_domain_plan_extraction(self, compiler, simple_config):
        """域管道计划提取"""
        compiled = compiler.compile(simple_config)
        assert "domain-1" in compiled.execution_plan.domain_plans
        domain_nodes = compiled.execution_plan.domain_plans["domain-1"]
        assert "qr" in domain_nodes
        assert "vs" in domain_nodes
        assert domain_nodes.index("qr") < domain_nodes.index("vs")

    def test_parallel_groups(self, compiler):
        """并行组检测"""
        config = {
            "pipeline": {"id": "test"},
            "domains": [],
            "aggregation": {
                "nodes": [
                    {"id": "a", "type": "query_rewrite"},
                    {"id": "b", "type": "bm25_search"},
                    {"id": "c", "type": "vector_search"},
                ],
                "edges": [
                    {"source": "a", "target": "b"},
                    {"source": "a", "target": "c"},
                ],
            },
        }
        compiled = compiler.compile(config)
        groups = compiled.execution_plan.parallel_groups
        # 应该有 2 个并行组：[a] 和 [b, c]
        assert len(groups) == 2
        assert groups[0] == ["a"]
        assert set(groups[1]) == {"b", "c"}

    def test_merge_params_l0_l2_l3(self, compiler):
        """参数合并 L3 > L2 > L0"""
        params = {"top_k": 20}  # L3
        config = {"type": "bm25_search", "top_k": 15}  # L2
        merged = compiler._merge_params(params, config)
        # L3 覆盖 L2
        assert merged["top_k"] == 20
        # L0 默认值保留
        assert merged["k1"] == 1.5
