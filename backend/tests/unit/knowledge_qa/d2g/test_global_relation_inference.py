"""测试 Phase 2.5 全局关系补全模块。"""

import pytest
import networkx as nx

from src.core.knowledge_qa.d2g.global_relation_inference import (
    infer_relations_by_type_rules,
    _cosine_similarity,
)
from src.core.knowledge_qa.d2g.master_graph import MasterGraph
from src.core.knowledge_qa.d2g.models import ExtractedEntity, ExtractedRelationship, RelationType


class TestTypeRules:
    """测试类型规则推断。"""

    def _make_master(self, entities: list[tuple[str, str]], relations: list[tuple[str, str]] = None) -> MasterGraph:
        """创建测试用主图。"""
        master = MasterGraph(book_id="test-book", book_title="Test Book")
        for name, etype in entities:
            master.add_entity(
                ExtractedEntity(name=name, entity_type=etype, description=f"desc of {name}"),
                chapter_id="ch1",
            )
        if relations:
            for src, tgt in relations:
                master.add_relationship(
                    ExtractedRelationship(
                        source=src, target=tgt,
                        relation_type=RelationType.RELATES_TO,
                        evidence="test",
                    ),
                    chapter_id="ch1",
                )
        return master

    def test_exercise_improves_cognitive(self):
        """Exercise → CognitiveProcess 应推断 THERAPEUTIC_IMPROVES"""
        master = self._make_master([
            ("有氧运动", "Exercise"),
            ("注意力", "CognitiveProcess"),
        ])
        rels = infer_relations_by_type_rules(master)
        assert len(rels) >= 1
        found = any(
            r.source == "有氧运动" and r.target == "注意力"
            and r.relation_type == RelationType.THERAPEUTIC_IMPROVES
            for r in rels
        )
        assert found, f"Expected Exercise→CognitiveProcess IMPROVES, got {[(r.source, r.target, r.relation_type) for r in rels]}"

    def test_problem_rootcause(self):
        """Problem → RootCause 应推断 CAUSAL_CAUSES"""
        master = self._make_master([
            ("ADHD", "Problem"),
            ("前额叶发育不足", "RootCause"),
        ])
        rels = infer_relations_by_type_rules(master)
        found = any(
            r.relation_type == RelationType.CAUSAL_CAUSES
            for r in rels
        )
        assert found

    def test_skip_existing_relations(self):
        """已有直接关系的实体对不应再推断"""
        master = self._make_master(
            [("有氧运动", "Exercise"), ("注意力", "CognitiveProcess")],
            relations=[("有氧运动", "注意力")],
        )
        rels = infer_relations_by_type_rules(master)
        # 不应为已有边的实体对再添加关系
        for r in rels:
            assert not (r.source == "有氧运动" and r.target == "注意力"), \
                "Should not add relation to already-connected pair"

    def test_no_self_relations(self):
        """同类型同名实体不应产生自环关系"""
        master = self._make_master([
            ("海马体", "BrainRegion"),
            ("前额叶", "BrainRegion"),
        ])
        rels = infer_relations_by_type_rules(master)
        for r in rels:
            assert r.source != r.target, "No self-loops allowed"

    def test_confidence_marked(self):
        """规则推断的关系应标记 confidence=0.5"""
        master = self._make_master([
            ("有氧运动", "Exercise"),
            ("注意力", "CognitiveProcess"),
        ])
        rels = infer_relations_by_type_rules(master)
        for r in rels:
            assert r.confidence == 0.5
            assert r.relation_source == "heuristic_rule"

    def test_empty_graph(self):
        """空图不应报错"""
        master = MasterGraph(book_id="test", book_title="Test")
        rels = infer_relations_by_type_rules(master)
        assert rels == []


class TestCosineSimilarity:
    """测试余弦相似度计算。"""

    def test_identical_vectors(self):
        assert abs(_cosine_similarity([1, 0, 0], [1, 0, 0]) - 1.0) < 1e-6

    def test_orthogonal_vectors(self):
        assert abs(_cosine_similarity([1, 0], [0, 1])) < 1e-6

    def test_opposite_vectors(self):
        assert abs(_cosine_similarity([1, 0], [-1, 0]) - (-1.0)) < 1e-6

    def test_zero_vector(self):
        assert _cosine_similarity([0, 0], [1, 0]) == 0.0


class TestOrphanDetection:
    """测试孤立实体检测（通过 master graph）。"""

    def test_orphan_entities_detected(self):
        master = MasterGraph(book_id="test", book_title="Test")
        # 添加 3 个实体，只有 2 个有关系
        master.add_entity(ExtractedEntity(name="A", entity_type="Problem"), "ch1")
        master.add_entity(ExtractedEntity(name="B", entity_type="Solution"), "ch1")
        master.add_entity(ExtractedEntity(name="C", entity_type="Risk"), "ch1")
        master.add_relationship(
            ExtractedRelationship(source="A", target="B", relation_type=RelationType.THERAPEUTIC_TREATS, evidence="test"),
            "ch1",
        )

        orphans = [n for n in master.graph.nodes if master.graph.degree(n) == 0]
        assert orphans == ["C"]

    def test_no_orphans_after_rules(self):
        """类型规则应消除部分孤立实体"""
        master = MasterGraph(book_id="test", book_title="Test")
        master.add_entity(ExtractedEntity(name="运动", entity_type="Exercise"), "ch1")
        master.add_entity(ExtractedEntity(name="注意力", entity_type="CognitiveProcess"), "ch1")
        master.add_entity(ExtractedEntity(name="ADHD", entity_type="Problem"), "ch1")

        # 初始全部孤立
        orphans_before = [n for n in master.graph.nodes if master.graph.degree(n) == 0]
        assert len(orphans_before) == 3

        # 应用规则
        rels = infer_relations_by_type_rules(master)
        for rel in rels:
            master.add_relationship(rel, "__heuristic__")

        # 运动→注意力 应被规则连接
        assert master.graph.degree("运动") > 0
        assert master.graph.degree("注意力") > 0


class TestJointExtractionHelpers:
    """测试联合提取辅助函数。"""

    def test_find_orphan_entities(self):
        """测试孤立实体检测函数。"""
        from src.core.knowledge_qa.d2g.chapter_extractor import _find_orphan_entities
        from src.core.knowledge_qa.d2g.models import ExtractedEntity, ExtractedRelationship, RelationType

        entities = [
            ExtractedEntity(name="A", entity_type="Problem"),
            ExtractedEntity(name="B", entity_type="Solution"),
            ExtractedEntity(name="C", entity_type="Risk"),
        ]
        relations = [
            ExtractedRelationship(
                source="A", target="B",
                relation_type=RelationType.THERAPEUTIC_TREATS,
                evidence="test",
            ),
        ]

        orphans = _find_orphan_entities(entities, relations)
        assert orphans == ["C"]

    def test_find_orphan_entities_all_connected(self):
        """所有实体都有关系时，孤立列表为空。"""
        from src.core.knowledge_qa.d2g.chapter_extractor import _find_orphan_entities

        entities = [
            ExtractedEntity(name="A", entity_type="Problem"),
            ExtractedEntity(name="B", entity_type="Solution"),
        ]
        relations = [
            ExtractedRelationship(
                source="A", target="B",
                relation_type=RelationType.THERAPEUTIC_TREATS,
                evidence="test",
            ),
        ]

        orphans = _find_orphan_entities(entities, relations)
        assert orphans == []

    def test_find_orphan_entities_empty(self):
        """空实体列表返回空孤立列表。"""
        from src.core.knowledge_qa.d2g.chapter_extractor import _find_orphan_entities

        orphans = _find_orphan_entities([], [])
        assert orphans == []

    def test_mark_relation_source(self):
        """测试关系来源标记。"""
        from src.core.knowledge_qa.d2g.chapter_extractor import _mark_relation_source

        rels = [
            ExtractedRelationship(
                source="A", target="B",
                relation_type=RelationType.RELATES_TO,
                evidence="test",
            ),
        ]
        _mark_relation_source(rels, "llm_joint")
        assert rels[0].relation_source == "llm_joint"


class TestQualityReport:
    """测试质量报告生成。"""

    def test_relation_source_report(self):
        """测试关系来源分布报告。"""
        from src.core.knowledge_qa.d2g.graph_quality import generate_relation_source_report

        master = MasterGraph(book_id="test", book_title="Test")
        master.add_entity(ExtractedEntity(name="A", entity_type="Problem"), "ch1")
        master.add_entity(ExtractedEntity(name="B", entity_type="Solution"), "ch1")
        master.add_entity(ExtractedEntity(name="C", entity_type="Risk"), "ch1")

        master.add_relationship(
            ExtractedRelationship(
                source="A", target="B",
                relation_type=RelationType.THERAPEUTIC_TREATS,
                evidence="test",
                relation_source="llm_joint",
            ),
            "ch1",
        )
        master.add_relationship(
            ExtractedRelationship(
                source="A", target="C",
                relation_type=RelationType.CAUSAL_CONTRIBUTES_TO,
                evidence="test",
                relation_source="heuristic_rule",
            ),
            "ch1",
        )

        report = generate_relation_source_report(master)
        assert "LLM 联合提取" in report
        assert "类型规则推断" in report
        assert "2 条" in report


class TestAsModelNormalization:
    """测试 _as_model 的 LLM 输出字段名规范化。"""

    def test_joint_extraction_with_type_field(self):
        """LLM 输出 'type' 字段应被正确规范化。"""
        from src.core.knowledge_qa.d2g.chapter_extractor import _as_model
        from src.core.knowledge_qa.d2g.models import JointExtractionResponse

        r = _as_model(
            {
                'entities': [{'name': '海马体', 'type': 'BrainRegion', 'description': 'test'}],
                'relations': [{'source': '海马体', 'target': '记忆', 'type': 'FUNCTIONAL_REGULATES', 'evidence': 'test'}],
            },
            JointExtractionResponse,
        )
        assert isinstance(r, JointExtractionResponse)
        assert len(r.entities) == 1
        assert r.entities[0].entity_type == 'BrainRegion'
        assert len(r.relations) == 1
        assert r.relations[0].relation_type == 'FUNCTIONAL_REGULATES'

    def test_entity_list_response_with_type_field(self):
        """EntityListResponse 的 items 应正确规范化。"""
        from src.core.knowledge_qa.d2g.chapter_extractor import _as_model
        from src.core.knowledge_qa.d2g.models import EntityListResponse

        r = _as_model(
            {'items': [{'name': '前额叶', 'type': 'BrainRegion', 'description': 'test'}]},
            EntityListResponse,
        )
        assert len(r.items) == 1
        assert r.items[0].entity_type == 'BrainRegion'

    def test_relationship_list_response_with_type_field(self):
        """RelationshipListResponse 的 items 应正确规范化。"""
        from src.core.knowledge_qa.d2g.chapter_extractor import _as_model
        from src.core.knowledge_qa.d2g.models import RelationshipListResponse

        r = _as_model(
            {'items': [{'source': 'A', 'target': 'B', 'type': 'CAUSAL_CAUSES', 'evidence': 'test'}]},
            RelationshipListResponse,
        )
        assert len(r.items) == 1
        assert r.items[0].relation_type == 'CAUSAL_CAUSES'


class TestRelationTypeMerge:
    """测试关系类型语义合并。"""

    def test_canonical_types_preserved(self):
        """标准关系类型不应被改变。"""
        from src.core.knowledge_qa.d2g.global_relation_inference import CANONICAL_RELATION_TYPES
        assert "FUNCTIONAL_REGULATES" in CANONICAL_RELATION_TYPES
        assert "CAUSAL_CAUSES" in CANONICAL_RELATION_TYPES
        assert "THERAPEUTIC_IMPROVES" in CANONICAL_RELATION_TYPES
        assert "RELATES_TO" in CANONICAL_RELATION_TYPES

    def test_free_types_preserved_when_no_embedding(self):
        """无 embedding 客户端时，自由关系类型保留原值。"""
        master = MasterGraph(book_id="test", book_title="Test")
        master.add_entity(ExtractedEntity(name="A", entity_type="Problem"), "ch1")
        master.add_entity(ExtractedEntity(name="B", entity_type="Solution"), "ch1")
        master.add_relationship(
            ExtractedRelationship(
                source="A", target="B",
                relation_type="CUSTOM_RELATION",
                evidence="test",
            ),
            "ch1",
        )
        # 关系类型应保留
        edge_data = master.graph.edges["A", "B"]
        assert edge_data["relation_type"] == "CUSTOM_RELATION"
