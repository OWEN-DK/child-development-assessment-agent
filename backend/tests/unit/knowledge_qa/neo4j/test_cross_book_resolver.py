"""跨书实体消歧引擎单元测试

测试数据结构、常量、纯函数逻辑。
"""

import pytest

from src.core.knowledge_qa.neo4j.cross_book_resolver import (
    D2G_LABELS,
    HIGH_SIMILARITY_THRESHOLD,
    MID_SIMILARITY_THRESHOLD,
    EntityCandidate,
    SimilarityPair,
    ReviewerDecision,
    Phase5Outcome,
)


# ──────────────────────────────────────────────────────────────
# 常量测试
# ──────────────────────────────────────────────────────────────


class TestConstants:
    """常量测试"""

    def test_d2g_labels_count(self):
        """应有 15 种 D2G 实体类型标签"""
        assert len(D2G_LABELS) == 15

    def test_d2g_labels_match_schema(self):
        """标签应与 schema.py D2G_ENTITY_TYPES 一致"""
        expected = {
            "Problem", "Solution", "BrainRegion", "Risk", "Exercise",
            "RootCause", "Prescription", "ChildProfile",
            "CognitiveProcess", "Theory", "Mechanism",
            "DevelopmentalStage", "Strategy", "KeyInsight", "ResearchFinding",
        }
        assert set(D2G_LABELS) == expected

    def test_similarity_thresholds(self):
        """阈值应合理"""
        assert HIGH_SIMILARITY_THRESHOLD > MID_SIMILARITY_THRESHOLD
        assert 0 < MID_SIMILARITY_THRESHOLD < 1
        assert 0 < HIGH_SIMILARITY_THRESHOLD <= 1


# ──────────────────────────────────────────────────────────────
# EntityCandidate 测试
# ──────────────────────────────────────────────────────────────


class TestEntityCandidate:
    """EntityCandidate 数据类测试"""

    def test_create_entity_candidate(self):
        """应能正确创建"""
        ec = EntityCandidate(
            name="注意力不集中",
            name_normalized="注意力不集中",
            entity_type="Problem",
            description="儿童注意力问题",
            book_id="book-001",
        )
        assert ec.name == "注意力不集中"
        assert ec.entity_type == "Problem"
        assert ec.book_ids == []

    def test_with_book_ids(self):
        """多书来源应正确记录"""
        ec = EntityCandidate(
            name="感觉统合",
            name_normalized="感觉统合",
            entity_type="Theory",
            description="感觉统合理论",
            book_id="book-001",
            book_ids=["book-001", "book-002"],
        )
        assert len(ec.book_ids) == 2


# ──────────────────────────────────────────────────────────────
# SimilarityPair 测试
# ──────────────────────────────────────────────────────────────


class TestSimilarityPair:
    """SimilarityPair 数据类测试"""

    def test_create_similarity_pair(self):
        """应能正确创建"""
        new = EntityCandidate(
            name="注意力缺陷", name_normalized="注意力缺陷",
            entity_type="Problem", description="注意力缺陷问题",
            book_id="book-002",
        )
        existing = EntityCandidate(
            name="注意力不集中", name_normalized="注意力不集中",
            entity_type="Problem", description="注意力不集中问题",
            book_id="book-001",
        )
        pair = SimilarityPair(
            new_entity=new,
            existing_entity=existing,
            similarity=0.92,
        )
        assert pair.similarity == 0.92
        assert pair.llm_same is None
        assert pair.llm_reason == ""

    def test_with_llm_judgment(self):
        """LLM 判断应正确记录"""
        new = EntityCandidate(
            name="A", name_normalized="A",
            entity_type="Problem", description="desc",
            book_id="b1",
        )
        existing = EntityCandidate(
            name="B", name_normalized="B",
            entity_type="Problem", description="desc",
            book_id="b2",
        )
        pair = SimilarityPair(
            new_entity=new,
            existing_entity=existing,
            similarity=0.95,
            llm_same=True,
            llm_reason="同一概念",
        )
        assert pair.llm_same is True


# ──────────────────────────────────────────────────────────────
# ReviewerDecision 测试
# ──────────────────────────────────────────────────────────────


class TestReviewerDecision:
    """ReviewerDecision 数据类测试"""

    def test_merge_decision(self):
        """合并决策"""
        d = ReviewerDecision(
            entity_name="注意力缺陷",
            matched_entity_name="注意力不集中",
            matched_book_id="book-001",
            decision="merge",
        )
        assert d.decision == "merge"

    def test_separate_decision(self):
        """保留决策"""
        d = ReviewerDecision(
            entity_name="A",
            matched_entity_name="B",
            matched_book_id="book-001",
            decision="separate",
        )
        assert d.decision == "separate"


# ──────────────────────────────────────────────────────────────
# Phase5Outcome 测试
# ──────────────────────────────────────────────────────────────


class TestPhase5Outcome:
    """Phase5Outcome 数据类测试"""

    def test_default_outcome(self):
        """默认值应正确"""
        outcome = Phase5Outcome(book_id="book-001")
        assert outcome.total_entities == 0
        assert outcome.high_sim_pairs == 0
        assert outcome.mid_sim_pairs == 0
        assert outcome.merged_count == 0
        assert outcome.same_as_count == 0
        assert outcome.reviewer_override_count == 0
        assert outcome.cross_book_relations == 0
        assert outcome.duration_ms == 0
        assert outcome.errors == []

    def test_outcome_with_data(self):
        """有数据的结果应正确"""
        outcome = Phase5Outcome(
            book_id="book-001",
            total_entities=50,
            high_sim_pairs=5,
            mid_sim_pairs=10,
            merged_count=3,
            same_as_count=2,
            cross_book_relations=8,
            duration_ms=1500,
        )
        assert outcome.total_entities == 50
        assert outcome.merged_count == 3
        assert outcome.duration_ms == 1500
