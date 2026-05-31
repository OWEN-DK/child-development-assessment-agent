"""长章节分段处理单元测试

测试 segment_chapter、merge_entity_results、merge_relationship_results、merge_detail_results。
"""

import pytest
from unittest.mock import MagicMock

from src.core.knowledge_qa.d2g.long_chapter import (
    Segment,
    MergedEntities,
    segment_chapter,
    merge_entity_results,
    merge_relationship_results,
    merge_detail_results,
)
from src.core.knowledge_qa.d2g.models import (
    EntityType,
    RelationType,
    ExtractedEntity,
    ExtractedRelationship,
    ExtractedCase,
    ExtractedDataPoint,
    ExtractedQuote,
    ChapterDetails,
)
from src.core.knowledge_qa.neo4j.chapter_parser import Chapter


def _make_chapter(title: str, markdown: str) -> Chapter:
    """构造测试用 Chapter 对象"""
    ch = MagicMock(spec=Chapter)
    ch.title = title
    ch.markdown = markdown
    return ch


# ──────────────────────────────────────────────────────────────
# segment_chapter 测试
# ──────────────────────────────────────────────────────────────


class TestSegmentChapter:
    """segment_chapter 函数测试"""

    def test_short_chapter_single_segment(self):
        """短章节应返回单个分段"""
        ch = _make_chapter("短章节", "段落一\n\n段落二\n\n段落三")
        segments = segment_chapter(ch, threshold=10_000)
        assert len(segments) == 1
        assert segments[0].index == 0
        assert segments[0].paragraph_ids == [1, 2, 3]
        assert "[P1]" in segments[0].text_with_ids
        assert "[P3]" in segments[0].text_with_ids

    def test_empty_chapter(self):
        """空章节应返回单个空分段"""
        ch = _make_chapter("空章节", "")
        segments = segment_chapter(ch, threshold=10_000)
        assert len(segments) == 1
        assert segments[0].paragraph_ids == []

    def test_long_chapter_multiple_segments(self):
        """长章节应分成多个分段"""
        # 构造足够长的章节（每个段落约 500 tokens）
        paragraphs = [f"这是第{i}段内容。" * 100 for i in range(1, 20)]
        markdown = "\n\n".join(paragraphs)
        ch = _make_chapter("长章节", markdown)
        segments = segment_chapter(
            ch, threshold=1000, seg_target=2000, overlap=300,
        )
        assert len(segments) >= 2
        # 验证分段索引连续
        for i, seg in enumerate(segments):
            assert seg.index == i

    def test_segment_ids_non_overlapping(self):
        """分段的 paragraph_ids 应正确编号"""
        paragraphs = [f"段落{i}内容。" * 50 for i in range(1, 10)]
        markdown = "\n\n".join(paragraphs)
        ch = _make_chapter("测试章节", markdown)
        segments = segment_chapter(
            ch, threshold=500, seg_target=800, overlap=200,
        )
        # 每个分段的 paragraph_ids 应非空
        for seg in segments:
            assert len(seg.paragraph_ids) > 0
            # IDs 应递增
            assert seg.paragraph_ids == sorted(seg.paragraph_ids)

    def test_max_segments_limit(self):
        """不应超过 MAX_SEGMENTS=8 个分段"""
        paragraphs = [f"段落{i}。" * 200 for i in range(1, 100)]
        markdown = "\n\n".join(paragraphs)
        ch = _make_chapter("超长章节", markdown)
        segments = segment_chapter(
            ch, threshold=100, seg_target=200, overlap=50,
        )
        assert len(segments) <= 8


# ──────────────────────────────────────────────────────────────
# merge_entity_results 测试
# ──────────────────────────────────────────────────────────────


class TestMergeEntityResults:
    """merge_entity_results 函数测试"""

    def test_merge_unique_entities(self):
        """不同实体应全部保留"""
        seg1 = [
            ExtractedEntity(
                name="注意力不集中",
                entity_type=EntityType.Problem,
                description="儿童在学习或活动中难以持续关注目标刺激的表现",
                source_para_ids=[1],
            ),
        ]
        seg2 = [
            ExtractedEntity(
                name="感觉统合训练",
                entity_type=EntityType.Exercise,
                description="通过多种感觉刺激改善大脑整合能力的训练方法",
                source_para_ids=[2],
            ),
        ]
        merged = merge_entity_results([seg1, seg2])
        assert len(merged.entities) == 2

    def test_merge_duplicate_entities_keep_longer_description(self):
        """重复实体应保留更长的描述"""
        seg1 = [
            ExtractedEntity(
                name="注意力不集中",
                entity_type=EntityType.Problem,
                description="这是一个较短的描述文本内容用于测试验证场景",
                source_para_ids=[1],
            ),
        ]
        seg2 = [
            ExtractedEntity(
                name="注意力不集中",
                entity_type=EntityType.Problem,
                description="这是一个更长更详细的描述文本，包含了更多的信息用于测试验证",
                source_para_ids=[2, 3],
            ),
        ]
        merged = merge_entity_results([seg1, seg2])
        assert len(merged.entities) == 1
        assert merged.entities[0].description == "这是一个更长更详细的描述文本，包含了更多的信息用于测试验证"
        assert sorted(merged.entities[0].source_para_ids) == [1, 2, 3]

    def test_merge_same_name_different_type(self):
        """同名不同类型应视为不同实体"""
        seg1 = [
            ExtractedEntity(
                name="注意力",
                entity_type=EntityType.CognitiveProcess,
                description="认知过程是大脑处理信息和进行思维活动的基本方式之一",
                source_para_ids=[1],
            ),
        ]
        seg2 = [
            ExtractedEntity(
                name="注意力",
                entity_type=EntityType.KeyInsight,
                description="这是一个关键洞察的详细描述内容用于测试验证场景",
                source_para_ids=[2],
            ),
        ]
        merged = merge_entity_results([seg1, seg2])
        assert len(merged.entities) == 2

    def test_merge_empty_input(self):
        """空输入应返回空结果"""
        merged = merge_entity_results([])
        assert len(merged.entities) == 0


# ──────────────────────────────────────────────────────────────
# merge_relationship_results 测试
# ──────────────────────────────────────────────────────────────


class TestMergeRelationshipResults:
    """merge_relationship_results 函数测试"""

    def test_merge_unique_relationships(self):
        """不同关系应全部保留"""
        rel1 = ExtractedRelationship(
            source="A", target="B",
            relation_type=RelationType.CAUSES,
            evidence="证据1",
        )
        rel2 = ExtractedRelationship(
            source="C", target="D",
            relation_type=RelationType.SOLVES,
            evidence="证据2",
        )
        merged = merge_relationship_results([[rel1], [rel2]], [])
        assert len(merged) == 2

    def test_merge_duplicate_relationships_keep_longer_evidence(self):
        """重复关系应保留更长的 evidence"""
        rel1 = ExtractedRelationship(
            source="A", target="B",
            relation_type=RelationType.CAUSES,
            evidence="短",
            source_para_ids=[1],
        )
        rel2 = ExtractedRelationship(
            source="A", target="B",
            relation_type=RelationType.CAUSES,
            evidence="更长的证据文本",
            source_para_ids=[2],
        )
        merged = merge_relationship_results([[rel1]], [rel2])
        assert len(merged) == 1
        assert merged[0].evidence == "更长的证据文本"
        assert sorted(merged[0].source_para_ids) == [1, 2]

    def test_merge_with_bridge_relationships(self):
        """桥接关系应正确合入"""
        rel = ExtractedRelationship(
            source="X", target="Y",
            relation_type=RelationType.AFFECTS,
            evidence="桥接证据",
        )
        merged = merge_relationship_results([], [rel])
        assert len(merged) == 1


# ──────────────────────────────────────────────────────────────
# merge_detail_results 测试
# ──────────────────────────────────────────────────────────────


class TestMergeDetailResults:
    """merge_detail_results 函数测试"""

    def test_merge_cases_dedup_by_title(self):
        """案例应按标题去重"""
        detail1 = ChapterDetails(
            cases=[ExtractedCase(
                title="案例A", background="bg", process="proc",
                result="res", insight="ins",
            )],
        )
        detail2 = ChapterDetails(
            cases=[ExtractedCase(
                title="案例A", background="bg2", process="proc2",
                result="res2", insight="ins2",
            )],
            key_arguments=["论点1"],
        )
        merged = merge_detail_results([detail1, detail2])
        assert len(merged["cases"]) == 1
        assert merged["key_arguments"] == ["论点1"]

    def test_merge_data_points_dedup(self):
        """数据点应按 metric+value 去重"""
        detail1 = ChapterDetails(
            data_points=[ExtractedDataPoint(
                metric="注意力时长", value="15分钟", context="测试",
            )],
        )
        detail2 = ChapterDetails(
            data_points=[ExtractedDataPoint(
                metric="注意力时长", value="15分钟", context="另一场景",
            )],
        )
        merged = merge_detail_results([detail1, detail2])
        assert len(merged["data_points"]) == 1

    def test_merge_empty_details(self):
        """空细节应返回空结构"""
        merged = merge_detail_results([])
        assert merged["cases"] == []
        assert merged["data_points"] == []
        assert merged["quotes"] == []
        assert merged["key_arguments"] == []
        assert merged["recommendations"] == []
