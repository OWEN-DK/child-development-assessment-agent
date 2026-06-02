"""单元测试：Bundle 消费层 (bundle_consumer.py)

覆盖：
- extract_for_section 各节提取逻辑
- build_priority_context 三层优先级构造
- _prefilter_citations 白名单预校验
- _section_quota 配额计算
- 空 Bundle 降级
"""

import pytest

from src.core.knowledge_qa.bundle import (
    BookMeta,
    CrossBookConflict,
    CrossBookConsensus,
    CustomRuleMatch,
    GraphEntity,
    GraphRelation,
    KnowledgeBundle,
    Passage,
    PriorityConflict,
    RetrievalStats,
)
from src.core.knowledge_qa.bundle_consumer import (
    SECTION_QUOTAS,
    build_priority_context,
    extract_for_section,
)


# ── Fixtures ──


def _make_passage(id: str, book_id: str, content: str, score: float = 0.9,
                  source: str = "chroma", neo4j_verified: bool = False) -> Passage:
    return Passage(
        id=id, book_id=book_id, book_title=book_id,
        chapter_title="", content=content, score=score,
        source=source, neo4j_verified=neo4j_verified,
    )


def _make_bundle(passages: list[Passage] = None,
                 entities: dict = None,
                 consensus: list[CrossBookConsensus] = None,
                 rules: list[CustomRuleMatch] = None) -> KnowledgeBundle:
    return KnowledgeBundle(
        question="测试问题",
        matched_book_ids=["b1", "b2"],
        passages=passages or [],
        neo4j_entities=entities or {},
        cross_book_consensus=consensus or [],
        custom_rules=rules or [],
        book_index={"b1": BookMeta(book_id="b1", title="书A", normalized_title="书A")},
        retrieval_stats=RetrievalStats(),
    )


# ── extract_for_section ──


class TestExtractForSection:
    def test_empty_bundle(self):
        bundle = _make_bundle()
        result = extract_for_section(bundle, 1)
        assert result == []

    def test_section_1_prefers_entity_types(self):
        passages = [_make_passage(f"p{i}", "b1", f"内容{i}") for i in range(3)]
        entities = {
            "Problem": [
                GraphEntity(name="注意力", entity_type="Problem", book_id="b1", book_title="b1"),
            ]
        }
        bundle = _make_bundle(passages=passages, entities=entities)
        result = extract_for_section(bundle, 1)
        assert len(result) > 0

    def test_section_2_problem_related(self):
        passages = [_make_passage(f"p{i}", "b1", f"注意力缺陷内容{i}") for i in range(3)]
        entities = {
            "Problem": [
                GraphEntity(name="注意力缺陷", entity_type="Problem", book_id="b1", book_title="b1"),
            ]
        }
        bundle = _make_bundle(passages=passages, entities=entities)
        result = extract_for_section(bundle, 2)
        assert len(result) >= 1

    def test_section_3_exercise_related(self):
        passages = [_make_passage(f"p{i}", "b1", f"运动推荐内容{i}") for i in range(3)]
        entities = {
            "Exercise": [
                GraphEntity(name="跑步", entity_type="Exercise", book_id="b1", book_title="b1"),
            ]
        }
        bundle = _make_bundle(passages=passages, entities=entities)
        result = extract_for_section(bundle, 3)
        assert len(result) >= 1

    def test_section_5_retrieves_all(self):
        passages = [_make_passage(f"p{i}", "b1", f"全部内容{i}") for i in range(5)]
        bundle = _make_bundle(passages=passages)
        result = extract_for_section(bundle, 5)
        assert len(result) >= 1

    def test_fallback_to_keyword_search(self):
        """Section 1 实体类型无匹配时回退到关键字搜索"""
        passages = [_make_passage("p1", "b1", "运动能够显著改善儿童的认知功能")]
        # 无 Problem 实体，将回退到关键字搜索
        bundle = _make_bundle(passages=passages)
        result = extract_for_section(bundle, 1, section_query="运动")
        assert len(result) >= 1


# ── build_priority_context ──


class TestBuildPriorityContext:
    def test_empty_all(self):
        bundle = _make_bundle()
        result = build_priority_context(bundle, [], 1)
        # 只应该包含引用规则
        assert "引用规则" in result

    def test_includes_custom_knowledge(self):
        bundle = _make_bundle()
        result = build_priority_context(
            bundle, [], 1,
            custom_knowledge_context="专家建议：每天运动30分钟",
        )
        assert "专家建议" in result
        assert "专家知识" in result

    def test_includes_neo4j_layer(self):
        passages = [_make_passage("p1", "b1", "运动有益健康", neo4j_verified=True)]
        entities = {
            "Problem": [
                GraphEntity(name="注意缺陷", entity_type="Problem", book_id="b1", book_title="b1"),
            ]
        }
        bundle = _make_bundle(passages=passages, entities=entities)
        result = build_priority_context(bundle, passages, 1)
        assert "知识图谱" in result

    def test_includes_citation_rules(self):
        bundle = _make_bundle()
        bundle = KnowledgeBundle(
            question="测试",
            matched_book_ids=["b1"],
            passages=[],
            book_index={"b1": BookMeta(book_id="b1", title="书A", normalized_title="书A")},
        )
        result = build_priority_context(bundle, [], 1)
        assert "引用规则" in result
        assert "书A" in result

    def test_includes_consensus(self):
        passages = [_make_passage("p1", "b1", "运动有益健康")]
        consensus = [
            CrossBookConsensus(
                entity_name="运动干预",
                books=["书A", "书B"],
                relation_type="SAME_AS",
                description="两书一致认为运动有效",
            )
        ]
        bundle = _make_bundle(passages=passages, consensus=consensus)
        result = build_priority_context(bundle, passages, 1)
        assert "跨书共识" in result


# ── SECTION_QUOTAS ──


class TestSectionQuotas:
    def test_quotas_sum_close_to_one(self):
        total = sum(SECTION_QUOTAS.values())
        assert abs(total - 1.0) < 0.01

    def test_each_section_defined(self):
        for i in range(1, 6):
            assert i in SECTION_QUOTAS
            assert SECTION_QUOTAS[i] > 0


# ── _prefilter_citations ──


class TestPrefilterCitations:
    def test_removes_unknown_books(self):
        from src.core.knowledge_qa.bundle_consumer import _prefilter_citations
        book_index = {
            "b1": BookMeta(book_id="b1", title="书A", normalized_title="书A"),
        }
        citations = [
            {"book_title": "书A", "excerpt": "test"},
            {"book_title": "不存在的书", "excerpt": "test2"},
        ]
        result = _prefilter_citations(citations, book_index)
        assert len(result) == 1
        assert result[0]["book_title"] == "书A"

    def test_all_valid_kept(self):
        from src.core.knowledge_qa.bundle_consumer import _prefilter_citations
        book_index = {
            "b1": BookMeta(book_id="b1", title="书A", normalized_title="书A"),
            "b2": BookMeta(book_id="b2", title="书B", normalized_title="书B"),
        }
        citations = [
            {"book_title": "书A", "excerpt": "test1"},
            {"book_title": "书B.epub", "excerpt": "test2"},  # 含扩展名应被规范化后匹配
        ]
        result = _prefilter_citations(citations, book_index)
        assert len(result) == 2

    def test_empty_citations(self):
        from src.core.knowledge_qa.bundle_consumer import _prefilter_citations
        result = _prefilter_citations([], {})
        assert result == []
