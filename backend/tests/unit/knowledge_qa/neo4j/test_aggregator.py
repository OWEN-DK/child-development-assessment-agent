"""跨章聚合器测试。"""

import pytest
from src.core.knowledge_qa.neo4j.aggregator import (
    AggregatedEntity, AggregatedBook, aggregate_chapters, _detect_contradictions,
)


class TestAggregatedEntity:
    """AggregatedEntity 数据类。"""

    def test_defaults(self):
        ent = AggregatedEntity(name="ADHD", entity_type="Problem")
        assert ent.name == "ADHD"
        assert ent.entity_type == "Problem"
        assert ent.confidence == 0.0
        assert ent.sources == []
        assert ent.merged_from == []

    def test_with_sources(self):
        ent = AggregatedEntity(
            name="ADHD", entity_type="Problem",
            sources=["第1章", "第2章"], confidence=0.8,
        )
        assert len(ent.sources) == 2
        assert ent.confidence == 0.8


class TestAggregateChapters:
    """aggregate_chapters() 测试。"""

    def test_empty_chapters(self):
        result = aggregate_chapters([], "b1", "测试书")
        assert isinstance(result, AggregatedBook)
        assert result.book_id == "b1"
        assert result.entities == []

    def test_single_chapter_with_concepts(self):
        chapters = [{
            "success": True,
            "chapter_id": "ch001",
            "concepts": [
                {"name": "ADHD", "entity_type": "Problem", "description": "注意力缺陷"},
            ],
            "claims": [],
            "prescriptions": [],
        }]
        result = aggregate_chapters(chapters, "b1", "测试书")
        assert len(result.entities) == 1
        assert result.entities[0].name == "ADHD"

    def test_dedup_across_chapters(self):
        chapters = [
            {
                "success": True, "chapter_id": "ch001",
                "concepts": [{"name": "ADHD", "entity_type": "Problem"}],
                "claims": [], "prescriptions": [],
            },
            {
                "success": True, "chapter_id": "ch002",
                "concepts": [{"name": "ADHD", "entity_type": "Problem"}],
                "claims": [], "prescriptions": [],
            },
        ]
        result = aggregate_chapters(chapters, "b1", "测试书")
        names = [e.name for e in result.entities]
        assert names.count("ADHD") == 1
        # merged_from 应包含两个章节
        assert len(result.entities[0].merged_from) == 2

    def test_failed_chapter_skipped(self):
        chapters = [{
            "success": False,
            "chapter_id": "ch001",
            "concepts": [{"name": "X", "entity_type": "Problem"}],
        }]
        result = aggregate_chapters(chapters, "b1", "测试书")
        assert len(result.entities) == 0


class TestDetectContradictions:
    """_detect_contradictions() 测试。"""

    def test_no_contradictions_single_entity(self):
        entities = [
            AggregatedEntity(name="ADHD", entity_type="Problem", descriptions=["注意力缺陷"]),
        ]
        result = _detect_contradictions(entities)
        assert isinstance(result, list)

    def test_empty_entities(self):
        assert _detect_contradictions([]) == []
