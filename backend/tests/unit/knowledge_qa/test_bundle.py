"""单元测试：KnowledgeBundle 数据模型

覆盖：
- 所有 dataclass 的字段默认值和 frozen 不可变性
- normalize_book_title 边界情况
- CitationVerdict trust_level 各状态
"""

import pytest
from dataclasses import FrozenInstanceError

from src.core.knowledge_qa.bundle import (
    BookMeta,
    CitationVerdict,
    CrossBookConflict,
    CrossBookConsensus,
    CustomRuleMatch,
    GraphEntity,
    GraphRelation,
    KnowledgeBundle,
    Passage,
    PriorityConflict,
    RetrievalStats,
    normalize_book_title,
)


class TestNormalizeBookTitle:
    """书名规范化测试"""

    def test_strips_epub_extension(self):
        assert normalize_book_title("运动改变大脑.epub") == "运动改变大脑"

    def test_strips_pdf_extension(self):
        assert normalize_book_title("儿童发展心理学.pdf") == "儿童发展心理学"

    def test_no_extension_unchanged(self):
        assert normalize_book_title("跑步圣经") == "跑步圣经"

    def test_empty_returns_unknown(self):
        assert normalize_book_title("") == "未知"

    def test_whitespace_trimmed(self):
        assert normalize_book_title("  学习之道.md  ") == "学习之道"

    def test_multiple_dots(self):
        assert normalize_book_title("test.v2.epub") == "test.v2"


class TestKnowledgeBundle:
    """Bundle 不可变数据模型测试"""

    def test_default_construction(self):
        bundle = KnowledgeBundle(question="测试问题", matched_book_ids=["book1"])
        assert bundle.question == "测试问题"
        assert bundle.matched_book_ids == ["book1"]
        assert bundle.passages == []
        assert bundle.book_index == {}
        assert bundle.passage_index == {}
        assert isinstance(bundle.retrieval_stats, RetrievalStats)

    def test_frozen_cannot_modify(self):
        bundle = KnowledgeBundle(question="test", matched_book_ids=["b1"])
        with pytest.raises(FrozenInstanceError):
            bundle.question = "modified"

    def test_full_construction(self):
        passages = [
            Passage(
                id="p1", book_id="b1", book_title="书A",
                chapter_title="第1章", content="测试内容", score=0.95,
                source="chroma", neo4j_verified=True,
            )
        ]
        entities = {
            "Problem": [
                GraphEntity(
                    name="注意力缺陷", entity_type="Problem",
                    book_id="b1", book_title="书A", description="注意力不集中",
                )
            ]
        }
        bundle = KnowledgeBundle(
            question="注意力问题",
            matched_book_ids=["b1", "b2", "b3"],
            neo4j_entities=entities,
            passages=passages,
            cross_book_consensus=[
                CrossBookConsensus(
                    entity_name="运动干预", books=["书A", "书B"],
                    relation_type="SAME_AS", description="一致认为运动有效",
                )
            ],
            retrieval_stats=RetrievalStats(
                neo4j_entity_count=5,
                retrieval_duration_ms=1200,
                seed_source="question_embedding",
            ),
        )
        assert len(bundle.passages) == 1
        assert len(bundle.neo4j_entities["Problem"]) == 1
        assert bundle.retrieval_stats.neo4j_entity_count == 5


class TestPassage:
    """Passage 数据模型测试"""

    def test_hash_by_id(self):
        p1 = Passage(
            id="abc", book_id="b1", book_title="T",
            chapter_title="", content="c", score=0.5, source="chroma",
        )
        p2 = Passage(
            id="abc", book_id="b2", book_title="U",
            chapter_title="", content="d", score=0.9, source="lazy_graph_rag",
        )
        assert hash(p1) == hash(p2)  # 相同 ID

    def test_hash_different_id(self):
        p1 = Passage(
            id="a", book_id="b1", book_title="T",
            chapter_title="", content="c", score=0.5, source="chroma",
        )
        p2 = Passage(
            id="b", book_id="b1", book_title="T",
            chapter_title="", content="c", score=0.5, source="chroma",
        )
        assert p1 != p2


class TestCitationVerdict:
    """引用校验结果测试"""

    def test_trust_level_verified(self):
        v = CitationVerdict(
            passed=True,
            neo4j_verified_entities=["运动干预"],
        )
        assert v.trust_level == "verified"

    def test_trust_level_corrected(self):
        v = CitationVerdict(
            passed=True,
            corrected_book_title="运动改变大脑",
        )
        assert v.trust_level == "corrected"

    def test_trust_level_semantic_questionable(self):
        v = CitationVerdict(
            passed=True,
            semantic_mismatch=True,
        )
        assert v.trust_level == "semantic_questionable"

    def test_trust_level_text_verified(self):
        v = CitationVerdict(passed=True)
        assert v.trust_level == "text_verified"

    def test_trust_level_failed(self):
        v = CitationVerdict(passed=False, reason="book_title不在白名单")
        assert v.trust_level == "failed"


class TestRetrievalStats:
    """检索统计测试"""

    def test_defaults(self):
        stats = RetrievalStats()
        assert stats.neo4j_entity_count == 0
        assert stats.seed_source == ""
        assert stats.pruned_book_ids == []
