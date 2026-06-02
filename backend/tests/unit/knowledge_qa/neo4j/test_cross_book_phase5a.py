"""Phase 5a 跨书匹配预计算单元测试

测试数据结构、常量、纯函数逻辑。
"""

import pytest

from src.core.knowledge_qa.neo4j.cross_book_phase5a import (
    EntityCandidate,
    EntityMatchCandidate,
    CrossRelationCandidate,
    CrossBookAnalysisResult,
    CrossBookPhase5a,
)


# ──────────────────────────────────────────────────────────────
# 数据结构测试
# ──────────────────────────────────────────────────────────────


class TestEntityCandidate:
    """EntityCandidate 数据类测试"""

    def test_create_entity_candidate(self):
        """应能正确创建"""
        ec = EntityCandidate(
            name="注意力不集中",
            entity_type="Problem",
            description="儿童注意力问题",
            book_id="book-001",
        )
        assert ec.name == "注意力不集中"
        assert ec.entity_type == "Problem"
        assert ec.embedding == []

    def test_with_embedding(self):
        """embedding 应正确记录"""
        embedding = [0.1, 0.2, 0.3]
        ec = EntityCandidate(
            name="测试",
            entity_type="Problem",
            description="描述",
            book_id="book-001",
            embedding=embedding,
        )
        assert len(ec.embedding) == 3


class TestEntityMatchCandidate:
    """EntityMatchCandidate 数据类测试"""

    def test_create_match_candidate(self):
        """应能正确创建"""
        match = EntityMatchCandidate(
            index=0,
            new_entity="注意力训练",
            new_type="Solution",
            new_desc="注意力训练方法",
            new_book_id="book-002",
            matched_entity="注意力缺陷干预",
            matched_type="Solution",
            matched_desc="针对 ADHD 的干预",
            matched_book_id="book-001",
            matched_book_title="运动与大脑",
            similarity=0.92,
        )
        assert match.index == 0
        assert match.similarity == 0.92
        assert match.reviewer_decision == "skip"

    def test_reviewer_decisions(self):
        """审核者决策选项应正确"""
        decisions = ["merge", "separate", "auto", "skip"]
        for decision in decisions:
            match = EntityMatchCandidate(
                index=0,
                new_entity="A",
                new_type="Problem",
                new_desc="",
                new_book_id="book-002",
                matched_entity="B",
                matched_type="Problem",
                matched_desc="",
                matched_book_id="book-001",
                matched_book_title="",
                similarity=0.9,
                reviewer_decision=decision,
            )
            assert match.reviewer_decision == decision


class TestCrossRelationCandidate:
    """CrossRelationCandidate 数据类测试"""

    def test_create_relation_candidate(self):
        """应能正确创建"""
        rel = CrossRelationCandidate(
            index=0,
            source_entity="有氧运动",
            source_type="Exercise",
            source_book="book-001",
            target_entity="ADHD",
            target_type="Problem",
            target_book="book-002",
            relation_type="CROSS_TREATS",
            confidence=0.88,
            reason="运动改善注意力",
        )
        assert rel.relation_type == "CROSS_TREATS"
        assert rel.confidence == 0.88
        assert rel.reviewer_decision == "skip"

    def test_reviewer_decisions(self):
        """审核者决策选项应正确"""
        decisions = ["confirm", "ignore", "modify", "auto", "skip"]
        for decision in decisions:
            rel = CrossRelationCandidate(
                index=0,
                source_entity="A",
                source_type="Exercise",
                source_book="book-001",
                target_entity="B",
                target_type="Problem",
                target_book="book-002",
                relation_type="CROSS_TREATS",
                confidence=0.8,
                reason="",
                reviewer_decision=decision,
            )
            assert rel.reviewer_decision == decision


class TestCrossBookAnalysisResult:
    """CrossBookAnalysisResult 数据类测试"""

    def test_default_result(self):
        """默认值应正确"""
        result = CrossBookAnalysisResult(
            book_id="book-001",
            generated_at="2026-06-01T10:00:00Z",
        )
        assert result.book_id == "book-001"
        assert result.entity_matches == []
        assert result.cross_relations == []
        assert result.total_new_entities == 0
        assert result.total_other_entities == 0

    def test_result_with_data(self):
        """有数据的结果应正确"""
        matches = [
            EntityMatchCandidate(
                index=0,
                new_entity="A",
                new_type="Problem",
                new_desc="",
                new_book_id="book-002",
                matched_entity="B",
                matched_type="Problem",
                matched_desc="",
                matched_book_id="book-001",
                matched_book_title="",
                similarity=0.9,
            ),
        ]
        relations = [
            CrossRelationCandidate(
                index=0,
                source_entity="X",
                source_type="Exercise",
                source_book="book-001",
                target_entity="Y",
                target_type="Problem",
                target_book="book-002",
                relation_type="CROSS_TREATS",
                confidence=0.8,
                reason="",
            ),
        ]
        result = CrossBookAnalysisResult(
            book_id="book-001",
            generated_at="2026-06-01T10:00:00Z",
            entity_matches=matches,
            cross_relations=relations,
            total_new_entities=10,
            total_other_entities=20,
            match_candidates_count=1,
            relation_candidates_count=1,
        )
        assert len(result.entity_matches) == 1
        assert len(result.cross_relations) == 1
        assert result.total_new_entities == 10


# ──────────────────────────────────────────────────────────────
# 引擎测试（Mock）
# ──────────────────────────────────────────────────────────────


class TestCrossBookPhase5a:
    """CrossBookPhase5a 引擎测试"""

    def test_init(self):
        """初始化应正确"""
        engine = CrossBookPhase5a(
            neo4j_driver=None,
            embedding_helper=None,
            llm_client=None,
        )
        assert engine._entity_sim_th == 0.85
        assert engine._cross_rel_th == 0.45

    def test_custom_thresholds(self):
        """自定义阈值应正确"""
        engine = CrossBookPhase5a(
            neo4j_driver=None,
            entity_similarity_threshold=0.9,
            cross_relation_threshold=0.6,
        )
        assert engine._entity_sim_th == 0.9
        assert engine._cross_rel_th == 0.6
