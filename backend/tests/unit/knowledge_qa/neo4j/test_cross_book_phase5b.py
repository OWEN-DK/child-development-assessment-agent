"""Phase 5b 执行决策逻辑单元测试

测试数据结构、常量、纯函数逻辑。
"""

import pytest

from src.core.knowledge_qa.neo4j.cross_book_phase5b import (
    EntityMatchDecision,
    CrossRelationDecision,
    Phase5bOutcome,
    CrossBookPhase5b,
)


# ──────────────────────────────────────────────────────────────
# 数据结构测试
# ──────────────────────────────────────────────────────────────


class TestEntityMatchDecision:
    """EntityMatchDecision 数据类测试"""

    def test_create_decision(self):
        """应能正确创建"""
        decision = EntityMatchDecision(
            index=0,
            new_entity="注意力训练",
            new_type="Solution",
            new_book_id="book-002",
            matched_entity="注意力缺陷干预",
            matched_type="Solution",
            matched_book_id="book-001",
            similarity=0.92,
            llm_same=True,
            reviewer_decision="merge",
        )
        assert decision.index == 0
        assert decision.reviewer_decision == "merge"

    def test_all_decisions(self):
        """所有决策选项应正确"""
        decisions = ["merge", "separate", "auto", "skip"]
        for d in decisions:
            decision = EntityMatchDecision(
                index=0,
                new_entity="A",
                new_type="Problem",
                new_book_id="book-002",
                matched_entity="B",
                matched_type="Problem",
                matched_book_id="book-001",
                similarity=0.9,
                llm_same=True,
                reviewer_decision=d,
            )
            assert decision.reviewer_decision == d


class TestCrossRelationDecision:
    """CrossRelationDecision 数据类测试"""

    def test_create_decision(self):
        """应能正确创建"""
        decision = CrossRelationDecision(
            index=0,
            source_entity="有氧运动",
            source_type="Exercise",
            source_book="book-001",
            target_entity="ADHD",
            target_type="Problem",
            target_book="book-002",
            relation_type="CROSS_TREATS",
            confidence=0.88,
            reviewer_decision="confirm",
        )
        assert decision.relation_type == "CROSS_TREATS"
        assert decision.reviewer_decision == "confirm"

    def test_all_decisions(self):
        """所有决策选项应正确"""
        decisions = ["confirm", "ignore", "modify", "auto", "skip"]
        for d in decisions:
            decision = CrossRelationDecision(
                index=0,
                source_entity="A",
                source_type="Exercise",
                source_book="book-001",
                target_entity="B",
                target_type="Problem",
                target_book="book-002",
                relation_type="CROSS_TREATS",
                confidence=0.8,
                reviewer_decision=d,
            )
            assert decision.reviewer_decision == d


class TestPhase5bOutcome:
    """Phase5bOutcome 数据类测试"""

    def test_default_outcome(self):
        """默认值应正确"""
        outcome = Phase5bOutcome(book_id="book-001")
        assert outcome.book_id == "book-001"
        assert outcome.merged_count == 0
        assert outcome.separated_count == 0
        assert outcome.auto_merged_count == 0
        assert outcome.same_as_count == 0
        assert outcome.skipped_count == 0
        assert outcome.relations_created == 0
        assert outcome.auto_relations == 0
        assert outcome.relations_skipped == 0
        assert outcome.errors == []
        assert outcome.duration_ms == 0

    def test_outcome_with_data(self):
        """有数据的结果应正确"""
        outcome = Phase5bOutcome(
            book_id="book-001",
            merged_count=3,
            same_as_count=2,
            relations_created=5,
            duration_ms=1500,
        )
        assert outcome.merged_count == 3
        assert outcome.same_as_count == 2
        assert outcome.relations_created == 5
        assert outcome.duration_ms == 1500


# ──────────────────────────────────────────────────────────────
# 引擎测试（Mock）
# ──────────────────────────────────────────────────────────────


class TestCrossBookPhase5b:
    """CrossBookPhase5b 引擎测试"""

    def test_init(self):
        """初始化应正确"""
        engine = CrossBookPhase5b(neo4j_driver=None)
        assert engine._neo4j is None
