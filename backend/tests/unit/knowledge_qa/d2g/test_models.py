"""D2G 数据模型单元测试

测试所有枚举、Pydantic 模型的正确性。
"""

import pytest
from pydantic import ValidationError

from src.core.knowledge_qa.d2g.models import (
    EntityType,
    RelationType,
    ExtractedEntity,
    ExtractedRelationship,
    ExtractedCase,
    ExtractedDataPoint,
    ExtractedQuote,
    ChapterDetails,
    ChapterExtraction,
    BookContext,
    EntityMatchJudgment,
    GraphQualityMetrics,
    ModelConfig,
    PipelineConfig,
    QualityThresholds,
    CrossBookMatch,
    CrossBookRelationRecord,
    Phase5Result,
    GlobalRebuildResult,
)


# ──────────────────────────────────────────────────────────────
# EntityType 枚举测试
# ──────────────────────────────────────────────────────────────


class TestEntityType:
    """EntityType 枚举测试"""

    def test_entity_type_count(self):
        """应有 15 种实体类型"""
        assert len(list(EntityType)) == 15

    def test_all_entity_types_present(self):
        """验证所有 15 种实体类型都存在"""
        expected = {
            "Problem", "Solution", "BrainRegion", "Risk", "Exercise",
            "RootCause", "Prescription", "ChildProfile", "CognitiveProcess",
            "Theory", "Mechanism", "DevelopmentalStage", "Strategy",
            "KeyInsight", "ResearchFinding",
        }
        actual = {et.value for et in EntityType}
        assert actual == expected

    def test_entity_type_str_behavior(self):
        """EntityType 应可作为字符串使用"""
        assert EntityType.Problem == "Problem"
        assert EntityType.Solution.value == "Solution"

    def test_entity_type_from_string(self):
        """应能从字符串创建 EntityType"""
        assert EntityType("BrainRegion") == EntityType.BrainRegion

    def test_entity_type_invalid_value(self):
        """无效值应抛出 ValueError"""
        with pytest.raises(ValueError):
            EntityType("InvalidType")


# ──────────────────────────────────────────────────────────────
# RelationType 枚举测试
# ──────────────────────────────────────────────────────────────


class TestRelationType:
    """RelationType 枚举测试"""

    def test_relation_type_count(self):
        """应有 6 种关系类型"""
        assert len(list(RelationType)) == 6

    def test_all_relation_types_present(self):
        """验证所有 6 种关系类型都存在"""
        expected = {"CAUSES", "SOLVES", "AFFECTS", "REQUIRES", "PRESCRIBES", "RELATES_TO"}
        actual = {rt.value for rt in RelationType}
        assert actual == expected


# ──────────────────────────────────────────────────────────────
# ExtractedEntity 测试
# ──────────────────────────────────────────────────────────────


class TestExtractedEntity:
    """ExtractedEntity 模型测试"""

    def test_valid_entity(self):
        """有效实体应通过验证"""
        entity = ExtractedEntity(
            name="注意力不集中",
            entity_type=EntityType.Problem,
            description="儿童在学习或活动中难以持续关注目标刺激，容易被外界干扰分散注意力",
            source_para_ids=[1, 3, 5],
        )
        assert entity.name == "注意力不集中"
        assert entity.entity_type == EntityType.Problem
        assert len(entity.description) >= 20
        assert entity.source_para_ids == [1, 3, 5]

    def test_description_too_short(self):
        """描述少于 20 字应验证失败"""
        with pytest.raises(ValidationError):
            ExtractedEntity(
                name="测试",
                entity_type=EntityType.Problem,
                description="太短了",
            )

    def test_default_source_para_ids(self):
        """source_para_ids 默认为空列表"""
        entity = ExtractedEntity(
            name="测试实体名称",
            entity_type=EntityType.Solution,
            description="这是一个足够长的描述文本用于通过验证检查",
        )
        assert entity.source_para_ids == []


# ──────────────────────────────────────────────────────────────
# ExtractedRelationship 测试
# ──────────────────────────────────────────────────────────────


class TestExtractedRelationship:
    """ExtractedRelationship 模型测试"""

    def test_valid_relationship(self):
        """有效关系应通过验证"""
        rel = ExtractedRelationship(
            source="注意力不集中",
            target="感觉统合训练",
            relation_type=RelationType.SOLVES,
            evidence="研究表明感觉统合训练可以有效改善儿童注意力问题",
            source_para_ids=[2],
        )
        assert rel.source == "注意力不集中"
        assert rel.target == "感觉统合训练"
        assert rel.relation_type == RelationType.SOLVES


# ──────────────────────────────────────────────────────────────
# ExtractedCase 测试
# ──────────────────────────────────────────────────────────────


class TestExtractedCase:
    """ExtractedCase 模型测试"""

    def test_valid_case(self):
        """有效案例应通过验证"""
        case = ExtractedCase(
            title="小明的注意力改善案例",
            background="小明，6岁，被老师反映上课总是走神",
            process="经过3个月的感觉统合训练和家庭干预",
            result="注意力持续时间从5分钟提升到20分钟",
            insight="早期干预对注意力问题效果显著",
            related_entities=["注意力不集中", "感觉统合训练"],
        )
        assert case.title == "小明的注意力改善案例"
        assert len(case.related_entities) == 2

    def test_default_related_entities(self):
        """related_entities 默认为空列表"""
        case = ExtractedCase(
            title="测试案例",
            background="背景",
            process="过程",
            result="结果",
            insight="启示",
        )
        assert case.related_entities == []


# ──────────────────────────────────────────────────────────────
# ChapterExtraction 测试
# ──────────────────────────────────────────────────────────────


class TestChapterExtraction:
    """ChapterExtraction 模型测试"""

    def test_valid_chapter_extraction(self):
        """有效章节提取结果应通过验证"""
        extraction = ChapterExtraction(
            chapter_id="ch01",
            chapter_title="第一章 注意力发展",
            entities=[
                ExtractedEntity(
                    name="注意力发展",
                    entity_type=EntityType.DevelopmentalStage,
                    description="儿童注意力从无意注意到有意注意的发展过程",
                ),
            ],
            relationships=[],
            cases=[],
            data_points=[],
            quotes=[],
            key_arguments=["注意力是认知发展的基础"],
            recommendations=[{"type": "exercise", "name": "专注力训练"}],
        )
        assert extraction.chapter_id == "ch01"
        assert len(extraction.entities) == 1
        assert extraction.key_arguments == ["注意力是认知发展的基础"]

    def test_default_empty_lists(self):
        """默认值应为空列表"""
        extraction = ChapterExtraction(
            chapter_id="ch01",
            chapter_title="测试章节",
        )
        assert extraction.entities == []
        assert extraction.relationships == []
        assert extraction.cases == []
        assert extraction.data_points == []
        assert extraction.quotes == []
        assert extraction.key_arguments == []
        assert extraction.recommendations == []


# ──────────────────────────────────────────────────────────────
# BookContext 测试
# ──────────────────────────────────────────────────────────────


class TestBookContext:
    """BookContext 模型测试"""

    def test_valid_book_context(self):
        """有效书籍上下文应通过验证"""
        ctx = BookContext(
            book_title="儿童发展心理学",
            core_thesis="儿童发展是一个动态的、多维度的过程，受遗传和环境共同影响",
            key_arguments=["发展具有阶段性", "环境塑造大脑", "早期干预关键"],
            terminology={"敏感期": "特定能力发展的最佳窗口期"},
            chapter_outline="从认知发展到社会性发展的递进结构",
        )
        assert ctx.book_title == "儿童发展心理学"
        assert len(ctx.key_arguments) == 3
        assert "敏感期" in ctx.terminology


# ──────────────────────────────────────────────────────────────
# EntityMatchJudgment 测试
# ──────────────────────────────────────────────────────────────


class TestEntityMatchJudgment:
    """EntityMatchJudgment 模型测试"""

    def test_same_entity(self):
        """判断为同一实体"""
        judgment = EntityMatchJudgment(
            same=True,
            reason="两者都指儿童注意力无法集中的问题",
        )
        assert judgment.same is True

    def test_different_entity(self):
        """判断为不同实体"""
        judgment = EntityMatchJudgment(
            same=False,
            reason="前者是问题描述，后者是解决方案",
        )
        assert judgment.same is False


# ──────────────────────────────────────────────────────────────
# GraphQualityMetrics 测试
# ──────────────────────────────────────────────────────────────


class TestGraphQualityMetrics:
    """GraphQualityMetrics 模型测试"""

    def test_valid_metrics(self):
        """有效指标应通过验证"""
        metrics = GraphQualityMetrics(
            total_entities=100,
            total_relationships=250,
            orphan_entities=5,
            orphan_rate=0.05,
            avg_degree=5.0,
            connected_components=2,
            largest_component_ratio=0.92,
            chapter_coverage={"ch01": 0.95, "ch02": 0.88},
            overall_para_coverage=0.91,
        )
        assert metrics.total_entities == 100
        assert metrics.orphan_rate == 0.05
        assert metrics.chapter_coverage["ch01"] == 0.95


# ──────────────────────────────────────────────────────────────
# PipelineConfig 测试
# ──────────────────────────────────────────────────────────────


class TestPipelineConfig:
    """PipelineConfig 模型测试"""

    def test_default_config(self):
        """默认配置值应正确"""
        config = PipelineConfig()
        assert config.models.context == "qwen-turbo"
        assert config.models.extraction == "qwen-turbo"
        assert config.models.resolution == "qwen-turbo"
        assert config.concurrency == 3
        assert config.long_chapter_threshold == 20_000
        assert config.segment_target_size == 12_000
        assert config.overlap_size == 1_500
        assert config.entity_similarity_threshold == 0.85
        assert config.max_gap_fill_iterations == 1

    def test_custom_config(self):
        """自定义配置应正确覆盖默认值"""
        config = PipelineConfig(
            concurrency=5,
            long_chapter_threshold=30_000,
        )
        assert config.concurrency == 5
        assert config.long_chapter_threshold == 30_000
        # 未覆盖的应保持默认
        assert config.overlap_size == 1_500


# ──────────────────────────────────────────────────────────────
# QualityThresholds 测试
# ──────────────────────────────────────────────────────────────


class TestQualityThresholds:
    """QualityThresholds 模型测试"""

    def test_default_thresholds(self):
        """默认阈值应正确"""
        t = QualityThresholds()
        assert t.max_orphan_rate == 0.15
        assert t.max_connected_components == 3
        assert t.min_largest_component_ratio == 0.70
        assert t.min_avg_degree == 1.5
        assert t.min_chapter_coverage == 0.80
        assert t.min_overall_para_coverage == 0.75


# ──────────────────────────────────────────────────────────────
# CrossBook 模型测试
# ──────────────────────────────────────────────────────────────


class TestCrossBookModels:
    """跨书扩展模型测试"""

    def test_cross_book_match(self):
        """CrossBookMatch 应正确创建"""
        match = CrossBookMatch(
            entity_name="注意力不集中",
            matched_entity_name="注意缺陷",
            matched_book_id="book-002",
            matched_book_title="儿童心理学导论",
            similarity=0.92,
            llm_same=True,
            llm_reason="同一概念的不同表述",
        )
        assert match.similarity == 0.92
        assert match.llm_same is True
        assert match.reviewer_decision is None

    def test_cross_book_relation_record(self):
        """CrossBookRelationRecord 应正确创建"""
        record = CrossBookRelationRecord(
            source_entity="感觉统合训练",
            source_book="book-001",
            target_entity="感觉统合理论",
            target_book="book-002",
            relation_type="CONSENSUS",
            confidence=0.88,
            explanation="两本书对感觉统合训练的效果持一致观点",
        )
        assert record.relation_type == "CONSENSUS"

    def test_phase5_result_defaults(self):
        """Phase5Result 默认值应正确"""
        result = Phase5Result(book_id="book-001")
        assert result.total_entities == 0
        assert result.high_sim_pairs == 0
        assert result.merged_count == 0
        assert result.errors == []

    def test_global_rebuild_result(self):
        """GlobalRebuildResult 应正确创建"""
        result = GlobalRebuildResult(
            mode="full",
            total_entities=500,
            merged_entities=20,
            community_count=15,
            leaf_count=100,
            elapsed_s=45.2,
        )
        assert result.mode == "full"
        assert result.error is None


# ──────────────────────────────────────────────────────────────
# ModelConfig 测试
# ──────────────────────────────────────────────────────────────


class TestModelConfig:
    """ModelConfig 模型测试"""

    def test_default_models(self):
        """默认模型配置应正确"""
        config = ModelConfig()
        assert config.context == "qwen-turbo"
        assert config.extraction == "qwen-turbo"
        assert config.resolution == "qwen-turbo"

    def test_custom_models(self):
        """自定义模型配置应正确"""
        config = ModelConfig(
            context="qwen-plus",
            extraction="qwen-turbo",
            resolution="qwen-plus",
        )
        assert config.context == "qwen-plus"
        assert config.resolution == "qwen-plus"
