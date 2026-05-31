"""v2 节点单元测试 — 验证降级行为和 Neo4j 知识融合。"""

import pytest
from types import SimpleNamespace
from unittest.mock import patch, AsyncMock


def _make_state(**kwargs):
    """创建模拟 KnowledgeQAState。"""
    defaults = {
        "question": "孩子注意力不集中怎么办",
        "child_profile": {"age": 8},
        "matched_book_ids": ["book_001"],
        "matched_books": [{"book_id": "book_001"}],
        "sections": {},
        "section_queries": {},
        "knowledge_context": "",
        "exercise_context": "",
        "filtered_exercise_candidates": "",
        "neo4j_knowledge": {},
        "errors": [],
        "s4_needs_retry": False,
        "s4_retry_count": 0,
        "section_4_outline": None,
        "section_4_slots": None,
        "section_4_group_results": None,
        "contradictions": [],
        "retry_counts": {},
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


class TestAnalyzeChildV2:
    """analyze_child_v2 降级测试。"""

    @pytest.mark.asyncio
    async def test_empty_neo4j_falls_back_to_v1(self):
        """Neo4j 知识为空时，回退到 v1 行为。"""
        from src.core.knowledge_qa.nodes_v2.analyze_child_v2 import (
            _build_neo4j_problem_context,
        )
        result = _build_neo4j_problem_context({})
        assert result == ""

    @pytest.mark.asyncio
    async def test_build_problem_context_with_data(self):
        """Neo4j 有数据时生成上下文。"""
        from src.core.knowledge_qa.nodes_v2.analyze_child_v2 import (
            _build_neo4j_problem_context,
        )
        knowledge = {
            "problem_context": {
                "problems": [
                    {"name": "ADHD", "severity": "high", "description": "注意力缺陷", "symptoms": "多动"},
                ]
            },
            "source_coverage": {"total_books": 3},
        }
        result = _build_neo4j_problem_context(knowledge)
        assert "ADHD" in result
        assert "注意力缺陷" in result
        assert "3 本书" in result


class TestIdentifyProblemsV2:
    """identify_problems_v2 降级测试。"""

    def test_empty_neo4j_returns_empty(self):
        from src.core.knowledge_qa.nodes_v2.identify_problems_v2 import (
            _build_neo4j_rootcause_context,
        )
        result = _build_neo4j_rootcause_context({})
        assert result == ""

    def test_build_rootcause_context(self):
        from src.core.knowledge_qa.nodes_v2.identify_problems_v2 import (
            _build_neo4j_rootcause_context,
        )
        knowledge = {
            "problem_context": {
                "root_causes": [
                    {"name": "多巴胺不足", "description": "神经递质", "related_problems": ["ADHD"]},
                ]
            }
        }
        result = _build_neo4j_rootcause_context(knowledge)
        assert "多巴胺不足" in result
        assert "ADHD" in result


class TestRecommendTypesV2:
    """recommend_types_v2 降级测试。"""

    def test_format_neo4j_exercises(self):
        from src.core.knowledge_qa.nodes_v2.recommend_types_v2 import (
            _format_neo4j_exercises_as_markdown,
        )
        exercises = [
            {"name": "跑步", "category": "有氧", "age_range": "6-18", "benefits": "改善注意力", "source_book": "运动改变大脑"},
        ]
        md = _format_neo4j_exercises_as_markdown(exercises)
        assert "跑步" in md
        assert "有氧" in md

    def test_format_empty_exercises(self):
        from src.core.knowledge_qa.nodes_v2.recommend_types_v2 import (
            _format_neo4j_exercises_as_markdown,
        )
        assert _format_neo4j_exercises_as_markdown([]) == ""


class TestPlanOutlineV2:
    """plan_outline_v2 降级测试。"""

    def test_build_neo4j_outline_context_empty(self):
        from src.core.knowledge_qa.nodes_v2.plan_outline_v2 import (
            _build_neo4j_outline_context,
        )
        result = _build_neo4j_outline_context({})
        assert result == ""

    def test_build_neo4j_outline_context_with_data(self):
        from src.core.knowledge_qa.nodes_v2.plan_outline_v2 import (
            _build_neo4j_outline_context,
        )
        knowledge = {
            "exercises": [{"name": "跑步"}, {"name": "游泳"}],
            "cross_book_relations": {
                "consensus": [{"topic": "有氧运动益处"}],
                "conflicts": [{"topic": "运动强度"}],
            },
        }
        result = _build_neo4j_outline_context(knowledge)
        assert "跑步" in result
        assert "有氧运动益处" in result
        assert "运动强度" in result


class TestContradictionAuditV2:
    """contradiction_audit_v2 降级测试。"""

    def test_extract_neo4j_contradictions_empty(self):
        from src.core.knowledge_qa.nodes_v2.contradiction_audit_v2 import (
            _extract_neo4j_contradictions,
        )
        assert _extract_neo4j_contradictions({}) == []

    def test_extract_neo4j_contradictions_with_conflicts(self):
        from src.core.knowledge_qa.nodes_v2.contradiction_audit_v2 import (
            _extract_neo4j_contradictions,
        )
        knowledge = {
            "cross_book_relations": {
                "conflicts": [
                    {
                        "topic": "运动强度",
                        "view_a": "书A: 高强度更好",
                        "view_b": "书B: 低强度更安全",
                        "resolution": "根据年龄选择",
                        "severity": "moderate",
                    }
                ]
            }
        }
        result = _extract_neo4j_contradictions(knowledge)
        assert len(result) == 1
        assert result[0]["topic"] == "运动强度"
        assert result[0]["source"] == "neo4j"


class TestAssemblyV2:
    """_assembly_v2 图组装测试。"""

    def test_v2_graph_importable(self):
        from src.core.knowledge_qa._assembly_v2 import (
            knowledge_qa_v2_graph, create_knowledge_qa_v2_graph,
        )
        assert knowledge_qa_v2_graph is not None
        assert callable(create_knowledge_qa_v2_graph)

    def test_v2_graph_has_all_nodes(self):
        from src.core.knowledge_qa._assembly_v2 import knowledge_qa_v2_graph
        # 检查图包含所有预期节点
        graph = knowledge_qa_v2_graph
        # LangGraph CompiledGraph 的 node 名称
        node_names = set(graph.get_graph().nodes.keys())
        expected = {
            "match_books", "query_neo4j_graph", "prefetch_context",
            "analyze_child_v2", "identify_problems_v2", "recommend_types_v2",
            "plan_outline_v2", "plan_expand_parallel_v2", "plan_assemble",
            "generate_s4_citations", "fast_knowledge_match", "knowledge_synthesis_v2",
            "conclusion", "verify_citations", "finalize",
        }
        # __start__ 和 __end__ 是 LangGraph 自动添加的
        assert expected.issubset(node_names)


class TestPlanExpandParallelV2:
    """plan_expand_parallel_v2 降级测试。"""

    def test_find_prescriptions_with_data(self):
        from src.core.knowledge_qa.nodes_v2.plan_expand_parallel_v2 import (
            _find_prescriptions,
        )
        knowledge = {
            "exercises": [
                {"name": "跑步", "prescription": {"frequency": "每天", "duration": "30分钟"}},
                {"name": "游泳", "prescription": None},
            ]
        }
        result = _find_prescriptions(knowledge, ["跑步", "游泳"])
        assert "跑步" in result
        assert result["跑步"]["frequency"] == "每天"
        assert "游泳" not in result

    def test_find_prescriptions_empty(self):
        from src.core.knowledge_qa.nodes_v2.plan_expand_parallel_v2 import (
            _find_prescriptions,
        )
        assert _find_prescriptions({}, []) == {}
