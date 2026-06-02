"""MasterGraph 单元测试

测试主图的实体/关系操作、质量指标、序列化。
"""

import pytest
import json

from src.core.knowledge_qa.d2g.master_graph import MasterGraph
from src.core.knowledge_qa.d2g.models import (
    EntityType,
    RelationType,
    ExtractedEntity,
    ExtractedRelationship,
    ChapterExtraction,
)


@pytest.fixture
def empty_graph():
    """空主图"""
    return MasterGraph(book_id="book-001", book_title="测试书籍")


@pytest.fixture
def sample_graph():
    """含样本数据的主图"""
    mg = MasterGraph(book_id="book-001", book_title="测试书籍")

    # 添加实体
    mg.add_entity(ExtractedEntity(
        name="注意力不集中",
        entity_type=EntityType.Problem,
        description="儿童在学习或活动中难以持续关注目标刺激的表现",
        source_para_ids=[1, 2],
    ), chapter_id="ch01")

    mg.add_entity(ExtractedEntity(
        name="感觉统合训练",
        entity_type=EntityType.Exercise,
        description="通过多种感觉刺激改善大脑整合能力的训练方法",
        source_para_ids=[3],
    ), chapter_id="ch01")

    mg.add_entity(ExtractedEntity(
        name="前额叶皮层",
        entity_type=EntityType.BrainRegion,
        description="大脑前额叶皮层是负责执行功能和注意力调控的核心脑区",
        source_para_ids=[1],
    ), chapter_id="ch01")

    # 添加关系
    mg.add_relationship(ExtractedRelationship(
        source="感觉统合训练",
        target="注意力不集中",
        relation_type=RelationType.THERAPEUTIC_TREATS,
        evidence="研究表明有效",
        source_para_ids=[3],
    ), chapter_id="ch01")

    mg.add_relationship(ExtractedRelationship(
        source="前额叶皮层",
        target="注意力不集中",
        relation_type=RelationType.CAUSAL_CAUSES,
        evidence="脑科学依据",
        source_para_ids=[1],
    ), chapter_id="ch01")

    # 记录段落覆盖
    mg.chapter_para_count["ch01"] = 10

    return mg


# ──────────────────────────────────────────────────────────────
# 基础操作测试
# ──────────────────────────────────────────────────────────────


class TestMasterGraphBasic:
    """基础图操作测试"""

    def test_empty_graph(self, empty_graph):
        """空图应有 0 个节点和边"""
        assert empty_graph.graph.number_of_nodes() == 0
        assert empty_graph.graph.number_of_edges() == 0

    def test_add_entity(self, sample_graph):
        """添加实体后图应有正确数量的节点"""
        assert sample_graph.graph.number_of_nodes() == 3

    def test_add_relationship(self, sample_graph):
        """添加关系后图应有正确数量的边"""
        assert sample_graph.graph.number_of_edges() == 2

    def test_add_entity_metadata(self, sample_graph):
        """实体元数据应正确存储"""
        node = sample_graph.graph.nodes["注意力不集中"]
        assert node["entity_type"] == "Problem"
        assert node["description"] == "儿童在学习或活动中难以持续关注目标刺激的表现"
        assert "ch01" in node["source_chapters"]

    def test_add_duplicate_entity_merges(self, sample_graph):
        """重复实体应合并（保留更长描述）"""
        sample_graph.add_entity(ExtractedEntity(
            name="注意力不集中",
            entity_type=EntityType.Problem,
            description="这是一个更详细的注意力问题描述文本内容用于测试",
            source_para_ids=[5],
        ), chapter_id="ch02")

        assert sample_graph.graph.number_of_nodes() == 3  # 不应增加
        node = sample_graph.graph.nodes["注意力不集中"]
        assert node["description"] == "这是一个更详细的注意力问题描述文本内容用于测试"
        assert "ch02" in node["source_chapters"]

    def test_chapter_entities_tracking(self, sample_graph):
        """章节实体索引应正确"""
        assert "ch01" in sample_graph.chapter_entities
        assert "注意力不集中" in sample_graph.chapter_entities["ch01"]
        assert "感觉统合训练" in sample_graph.chapter_entities["ch01"]


# ──────────────────────────────────────────────────────────────
# 合并操作测试
# ──────────────────────────────────────────────────────────────


class TestMasterGraphMerge:
    """实体合并测试"""

    def test_merge_entity(self, sample_graph):
        """合并实体后 alias 应被移除"""
        sample_graph.add_entity(ExtractedEntity(
            name="注意力缺陷",
            entity_type=EntityType.Problem,
            description="注意力缺陷问题，表现为难以集中注意力和容易分心",
            source_para_ids=[4],
        ), chapter_id="ch01")

        assert sample_graph.graph.number_of_nodes() == 4
        sample_graph.merge_entity("注意力不集中", "注意力缺陷")
        assert sample_graph.graph.number_of_nodes() == 3
        assert "注意力缺陷" not in sample_graph.graph.nodes

    def test_merge_entity_migrates_edges(self, sample_graph):
        """合并后 alias 的边应迁移到 canonical"""
        sample_graph.add_entity(ExtractedEntity(
            name="注意力缺陷",
            entity_type=EntityType.Problem,
            description="注意力缺陷问题，表现为难以集中注意力和容易分心",
        ), chapter_id="ch01")

        sample_graph.add_relationship(ExtractedRelationship(
            source="前额叶皮层",
            target="注意力缺陷",
            relation_type=RelationType.CAUSAL_CAUSES,
            evidence="证据",
        ), chapter_id="ch01")

        sample_graph.merge_entity("注意力不集中", "注意力缺陷")
        # 前额叶皮层 -> 注意力不集中 应存在
        assert sample_graph.graph.has_edge("前额叶皮层", "注意力不集中")

    def test_merge_nonexistent_entity(self, sample_graph):
        """合并不在图中的实体应安全处理"""
        sample_graph.merge_entity("不存在1", "不存在2")
        assert sample_graph.graph.number_of_nodes() == 3


# ──────────────────────────────────────────────────────────────
# 质量指标测试
# ──────────────────────────────────────────────────────────────


class TestMasterGraphQuality:
    """质量指标测试"""

    def test_quality_metrics_basic(self, sample_graph):
        """质量指标应正确计算"""
        metrics = sample_graph.get_quality_metrics()
        assert metrics.total_entities == 3
        assert metrics.total_relationships == 2
        assert metrics.avg_degree == pytest.approx(4 / 3, rel=0.01)

    def test_quality_metrics_orphan_rate(self, sample_graph):
        """孤立实体率应正确计算"""
        metrics = sample_graph.get_quality_metrics()
        # 所有实体都有关系，orphan_rate 应为 0
        assert metrics.orphan_rate == 0.0

    def test_quality_metrics_with_orphan(self):
        """有孤立实体时 orphan_rate 应 > 0"""
        mg = MasterGraph(book_id="b", book_title="t")
        mg.add_entity(ExtractedEntity(
            name="孤立实体",
            entity_type=EntityType.KeyInsight,
            description="这是一个没有任何关系连接的孤立实体描述内容用于测试",
            source_para_ids=[1],
        ), chapter_id="ch01")
        mg.chapter_para_count["ch01"] = 1

        metrics = mg.get_quality_metrics()
        assert metrics.orphan_rate == 1.0
        assert metrics.orphan_entities == 1

    def test_quality_metrics_empty_graph(self, empty_graph):
        """空图的指标应安全处理"""
        metrics = empty_graph.get_quality_metrics()
        assert metrics.total_entities == 0
        assert metrics.total_relationships == 0
        assert metrics.orphan_rate == 0
        assert metrics.avg_degree == 0
        assert metrics.connected_components == 0

    def test_chapter_coverage(self, sample_graph):
        """章节覆盖率应正确计算"""
        metrics = sample_graph.get_quality_metrics()
        # ch01: 3 个实体覆盖了 para_ids [1,2,3]，总 10 段
        assert "ch01" in metrics.chapter_coverage
        assert metrics.chapter_coverage["ch01"] == pytest.approx(30.0, rel=0.01)


# ──────────────────────────────────────────────────────────────
# ingest_chapter 测试
# ──────────────────────────────────────────────────────────────


class TestIngestChapter:
    """ingest_chapter 方法测试"""

    def test_ingest_chapter(self, empty_graph):
        """整章合入应正确添加实体和关系"""
        extraction = ChapterExtraction(
            chapter_id="ch01",
            chapter_title="第一章",
            entities=[
                ExtractedEntity(
                    name="实体A",
                    entity_type=EntityType.Problem,
                    description="问题A的详细描述文本内容用于测试验证场景",
                    source_para_ids=[1],
                ),
                ExtractedEntity(
                    name="实体B",
                    entity_type=EntityType.Solution,
                    description="方案B的详细描述文本内容用于测试验证场景",
                    source_para_ids=[2],
                ),
            ],
            relationships=[
                ExtractedRelationship(
                    source="实体B",
                    target="实体A",
                    relation_type=RelationType.THERAPEUTIC_TREATS,
                    evidence="B 解决 A",
                    source_para_ids=[2],
                ),
            ],
        )
        empty_graph.ingest_chapter(extraction, para_count=10)
        assert empty_graph.graph.number_of_nodes() == 2
        assert empty_graph.graph.number_of_edges() == 1
        assert empty_graph.chapter_para_count["ch01"] == 10


# ──────────────────────────────────────────────────────────────
# 序列化测试
# ──────────────────────────────────────────────────────────────


class TestSerialization:
    """JSON 序列化/反序列化测试"""

    def test_to_json(self, sample_graph):
        """序列化应返回有效 JSON"""
        json_str = sample_graph.to_json()
        data = json.loads(json_str)
        assert "nodes" in data
        assert "edges" in data

    def test_roundtrip(self, sample_graph):
        """序列化 → 反序列化应保持数据一致"""
        json_str = sample_graph.to_json()
        restored = MasterGraph.from_json("book-001", "测试书籍", json_str)
        assert restored.graph.number_of_nodes() == sample_graph.graph.number_of_nodes()
        assert restored.graph.number_of_edges() == sample_graph.graph.number_of_edges()
        # 验证节点属性
        for node in sample_graph.graph.nodes:
            assert node in restored.graph.nodes
            assert restored.graph.nodes[node]["entity_type"] == sample_graph.graph.nodes[node]["entity_type"]
