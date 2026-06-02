"""单元测试：Bundle 组装逻辑 (bundle_builder.py 中的纯函数)

覆盖：
- _prune_book_ids 精简逻辑
- _dedup_simple / _dedup_by_content / _semantic_dedup
- _detect_priority_conflicts
- normalize_book_title 边界
- 各可配置阈值默认值
"""

import pytest

from src.core.knowledge_qa.bundle import (
    CrossBookConflict,
    KnowledgeBundle,
    Passage,
    PriorityConflict,
)


# ── _dedup_simple ──


class TestDedupSimple:
    def test_empty_list(self):
        from src.core.knowledge_qa.bundle_builder import _dedup_simple
        assert _dedup_simple([]) == []

    def test_single_passage(self):
        from src.core.knowledge_qa.bundle_builder import _dedup_simple
        p = Passage(id="1", book_id="b", book_title="T", chapter_title="", content="test", score=0.5, source="chroma")
        result = _dedup_simple([p])
        assert len(result) == 1
        assert result[0].id == "1"

    def test_exact_prefix_dedup_keeps_higher_score(self):
        from src.core.knowledge_qa.bundle_builder import _dedup_simple
        content = "运动可以改善注意力缺陷，多项研究表明规律运动对大脑发育有积极影响"
        p1 = Passage(id="1", book_id="b1", book_title="T1", chapter_title="", content=content, score=0.5, source="chroma")
        p2 = Passage(id="2", book_id="b2", book_title="T2", chapter_title="", content=content, score=0.9, source="chroma")
        result = _dedup_simple([p1, p2])
        assert len(result) == 1
        assert result[0].id == "2"  # 更高 score

    def test_different_prefix_kept(self):
        from src.core.knowledge_qa.bundle_builder import _dedup_simple
        p1 = Passage(id="1", book_id="b1", book_title="T1", chapter_title="", content="AAA BBB CCC DDD EEE FFF GGG HHH III JJJ KKK LLL MMM NNN OOO PPP QQQ RRR SSS TTT UUU VVV WWW XXX YYY. First text.", score=0.5, source="chroma")
        p2 = Passage(id="2", book_id="b2", book_title="T2", chapter_title="", content="ZZZ YYY XXX WWW VVV UUU TTT SSS RRR QQQ PPP OOO NNN MMM LLL KKK JJJ III HHH GGG FFF EEE. Second text.", score=0.9, source="chroma")
        result = _dedup_simple([p1, p2])
        assert len(result) == 2  # 前 80 字符不同


# ── _semantic_dedup ──


class TestSemanticDedup:
    def test_near_duplicate_removed(self):
        """高相似度（>90%）的 passages 只保留 score 高的"""
        from src.core.knowledge_qa.bundle_builder import _semantic_dedup
        base = "规律运动可以改善儿童的注意力水平，多项研究表明每周3-5次中等强度运动对ADHD儿童有显著效果。运动促进脑源性神经营养因子（BDNF）的分泌，这有助于改善"
        p1 = Passage(id="1", book_id="b1", book_title="T1", chapter_title="", content=base + "认知功能。", score=0.5, source="chroma")
        p2 = Passage(id="2", book_id="b2", book_title="T2", chapter_title="", content=base + "大脑发育。", score=0.9, source="chroma")
        result = _semantic_dedup([p2, p1])  # p2 first (higher score)
        assert len(result) == 1
        assert result[0].id == "2"

    def test_distinct_content_both_kept(self):
        from src.core.knowledge_qa.bundle_builder import _semantic_dedup
        p1 = Passage(id="1", book_id="b1", book_title="T1", chapter_title="", content="运动可以改善认知功能。多项研究表明规律运动对大脑有积极影响。从神经科学角度看，运动促进BDNF分泌。", score=0.5, source="chroma")
        p2 = Passage(id="2", book_id="b2", book_title="T2", chapter_title="", content="营养干预同样重要。均衡饮食对儿童成长发育不可或缺。蛋白质摄入不足会导致生长迟缓。维生素D缺乏影响骨骼发育。", score=0.9, source="chroma")
        result = _semantic_dedup([p1, p2])
        assert len(result) == 2

    def test_short_passage_duplicate_removed(self):
        """短文本（< 50 字符）完全相同 → 保留第一个（精确去重）"""
        from src.core.knowledge_qa.bundle_builder import _semantic_dedup
        p1 = Passage(id="1", book_id="b1", book_title="T1", chapter_title="", content="运动有益健康。", score=0.5, source="chroma")
        p2 = Passage(id="2", book_id="b2", book_title="T2", chapter_title="", content="运动有益健康。", score=0.9, source="chroma")
        result = _semantic_dedup([p1, p2])
        # 短文本相同内容 → 精确去重（保留第一个）
        assert len(result) == 1
        assert result[0].id == "1"

    def test_short_passage_different_preserved(self):
        """短文本（< 50 字符）内容不同 → 全部保留"""
        from src.core.knowledge_qa.bundle_builder import _semantic_dedup
        p1 = Passage(id="1", book_id="b1", book_title="T1", chapter_title="", content="运动有益健康。", score=0.5, source="chroma")
        p2 = Passage(id="2", book_id="b2", book_title="T2", chapter_title="", content="饮食同样重要。", score=0.9, source="chroma")
        result = _semantic_dedup([p1, p2])
        assert len(result) == 2


# ── _dedup_by_content ──


class TestDedupByContent:
    def test_integrates_exact_and_semantic(self):
        """两阶段去重集成：精确前缀去重 + 语义近似去重"""
        from src.core.knowledge_qa.bundle_builder import _dedup_by_content
        base = "运动对儿童发展的影响是一个复杂而重要的研究课题，越来越多的证据表明体育活动能显著改善儿童的"
        # p1 and p2 share same prefix → exact dedup keeps p2 (higher score)
        p1 = Passage(id="1", book_id="b1", book_title="T1", chapter_title="", content=base + "认知能力。", score=0.5, source="chroma")
        p2 = Passage(id="2", book_id="b2", book_title="T2", chapter_title="", content=base + "专注力水平。", score=0.9, source="chroma")
        # p3 is distinct
        p3 = Passage(id="3", book_id="b3", book_title="T3", chapter_title="", content="完全不同的内容：营养学研究表明均衡饮食对大脑发育至关重要。", score=0.8, source="chroma")
        result = _dedup_by_content([p1, p2, p3])
        assert len(result) == 2
        ids = {p.id for p in result}
        assert ids == {"2", "3"}


# ── _prune_book_ids ──


class TestPruneBookIds:
    @staticmethod
    def _make_result(entities_map: dict[str, list] = None, conflicts=None, consensus=None):
        from src.core.knowledge_qa.neo4j.enhanced_query import EnhancedNeo4jResult
        return EnhancedNeo4jResult(
            entities=entities_map or {},
            relations=[],
            cross_book_conflicts=conflicts or [],
            cross_book_consensus=consensus or [],
            entity_seeds=[],
            source_para_ids={},
        )

    @staticmethod
    def _make_entity(name, book_id, entity_type="Problem"):
        from src.core.knowledge_qa.bundle import GraphEntity
        return GraphEntity(name=name, entity_type=entity_type, book_id=book_id, book_title=book_id)

    def test_prunes_under_threshold(self):
        from src.core.knowledge_qa.bundle_builder import _prune_book_ids
        neo4j = self._make_result({
            "Problem": [self._make_entity("注意力", "b1")],
        })
        passages = [
            Passage(id="p1", book_id="b1", book_title="b1", chapter_title="", content="test", score=0.5, source="chroma"),
            Passage(id="p2", book_id="b1", book_title="b1", chapter_title="", content="test2", score=0.5, source="chroma"),
        ]
        # b1: 1 entity (< 3), 2 passages (< 5) → 低于阈值
        # b2: 0 entities, 0 passages → 低于阈值
        # 但 fallback 保证至少保留 first book (b1)
        pruned, retained = _prune_book_ids(["b1", "b2"], neo4j, passages)
        assert "b2" in pruned          # b2 correctly pruned (0 hits)
        assert "b1" in retained        # b1 rescued by fallback (at least one book)
        assert len(retained) == 1

    def test_keeps_above_entity_threshold(self):
        from src.core.knowledge_qa.bundle_builder import _prune_book_ids
        entities = {f"e{i}": self._make_entity(f"实体{i}", "b1") for i in range(5)}
        neo4j = self._make_result({"Problem": list(entities.values())})
        passages = []
        pruned, retained = _prune_book_ids(["b1"], neo4j, passages)
        assert len(retained) == 1
        assert "b1" in retained

    def test_keeps_above_passage_threshold(self):
        from src.core.knowledge_qa.bundle_builder import _prune_book_ids
        neo4j = self._make_result()
        passages = [
            Passage(id=f"p{i}", book_id="b1", book_title="b1", chapter_title="", content=f"内容{i}", score=0.5, source="chroma")
            for i in range(6)
        ]
        pruned, retained = _prune_book_ids(["b1"], neo4j, passages)
        assert len(retained) == 1

    def test_at_least_one_retained(self):
        from src.core.knowledge_qa.bundle_builder import _prune_book_ids
        neo4j = self._make_result()
        passages = []
        pruned, retained = _prune_book_ids(["only_book"], neo4j, passages)
        assert len(retained) == 1
        assert retained[0] == "only_book"


# ── _detect_priority_conflicts ──


class TestDetectPriorityConflicts:
    @staticmethod
    def _make_result(conflicts=None):
        from src.core.knowledge_qa.neo4j.enhanced_query import EnhancedNeo4jResult
        return EnhancedNeo4jResult(
            entities={}, relations=[],
            cross_book_conflicts=conflicts or [],
            cross_book_consensus=[],
            entity_seeds=[], source_para_ids={},
        )

    def test_no_conflicts_empty_list(self):
        from src.core.knowledge_qa.bundle_builder import _detect_priority_conflicts
        neo4j = self._make_result()
        result = _detect_priority_conflicts(neo4j, [])
        assert result == []

    def test_conflict_with_matching_passage(self):
        from src.core.knowledge_qa.bundle_builder import _detect_priority_conflicts
        cc = CrossBookConflict(
            entity_name="运动频率",
            books=["书A", "书B"],
            positions=["书A认为每周3次", "书B认为每天"],
            neo4j_relation_type="CROSS_BOOK_CONFLICTS",
        )
        neo4j = self._make_result([cc])
        p = Passage(
            id="p1", book_id="b1", book_title="书A", chapter_title="",
            content="关于运动频率的研究表明，不同文献对运动频率的建议存在差异。有些认为每周3次足够，有些认为需要每天坚持。",
            score=0.5, source="chroma",
        )
        result = _detect_priority_conflicts(neo4j, [p])
        assert len(result) == 1
        assert result[0].entity_name == "运动频率"

    def test_conflict_without_matching_passage(self):
        from src.core.knowledge_qa.bundle_builder import _detect_priority_conflicts
        cc = CrossBookConflict(
            entity_name="不存在实体",
            books=["书A", "书B"],
            positions=["立场A", "立场B"],
            neo4j_relation_type="CROSS_BOOK_CONFLICTS",
        )
        neo4j = self._make_result([cc])
        p = Passage(
            id="p1", book_id="b1", book_title="书A", chapter_title="",
            content="完全不相关的内容。", score=0.5, source="chroma",
        )
        result = _detect_priority_conflicts(neo4j, [p])
        assert result == []


# ── 配置常量 ──


class TestConfigConstants:
    def test_bundle_book_thresholds_defined(self):
        from src.core.knowledge_qa import bundle_builder
        assert bundle_builder.BUNDLE_BOOK_MIN_ENTITY_HITS >= 1
        assert bundle_builder.BUNDLE_BOOK_MIN_PASSAGE_HITS >= 1

    def test_max_passages_per_bundle_positive(self):
        from src.core.knowledge_qa import bundle_builder
        assert bundle_builder.MAX_PASSAGES_PER_BUNDLE > 0

    def test_semantic_dedup_threshold_range(self):
        from src.core.knowledge_qa import bundle_builder
        assert 0.5 < bundle_builder.SEMANTIC_DEDUP_THRESHOLD < 1.0
