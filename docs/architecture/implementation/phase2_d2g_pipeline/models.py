"""D2G 流水线数据模型 — 所有 Pydantic 模型定义。

放置位置: backend/src/core/knowledge_qa/neo4j/models.py
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ──────────────────────────────────────────────────────────────
# 枚举类型（与 schema.py 保持一致）
# ──────────────────────────────────────────────────────────────


class EntityType(str, Enum):
    """实体类型枚举。"""
    Problem = "Problem"
    Solution = "Solution"
    BrainRegion = "BrainRegion"
    CognitiveProcess = "CognitiveProcess"
    Theory = "Theory"
    Mechanism = "Mechanism"
    Risk = "Risk"
    DevelopmentalStage = "DevelopmentalStage"
    Strategy = "Strategy"
    KeyInsight = "KeyInsight"
    ResearchFinding = "ResearchFinding"
    Exercise = "Exercise"
    RootCause = "RootCause"


class RelationType(str, Enum):
    """关系类型枚举。"""
    CAUSES = "CAUSES"
    SOLVES = "SOLVES"
    AFFECTS = "AFFECTS"
    REQUIRES = "REQUIRES"
    PRESCRIBES = "PRESCRIBES"
    RELATES_TO = "RELATES_TO"


# ──────────────────────────────────────────────────────────────
# 提取结果模型（Phase 1 输出）
# ──────────────────────────────────────────────────────────────


class ExtractedEntity(BaseModel):
    """单个实体。"""
    name: str = Field(description="实体名称")
    entity_type: EntityType = Field(description="实体类型")
    description: str = Field(min_length=20, description="完整描述，不少于 20 字")
    source_para_ids: list[int] = Field(
        default_factory=list,
        description="来源段落序号，如 [3, 5, 7]",
    )


class ExtractedRelationship(BaseModel):
    """两个实体之间的关系。"""
    source: str = Field(description="起点实体名称，必须与实体列表中的 name 一致")
    target: str = Field(description="终点实体名称")
    relation_type: RelationType = Field(description="关系类型")
    evidence: str = Field(description="支撑证据，原文直接引用")
    source_para_ids: list[int] = Field(default_factory=list)


class ExtractedCase(BaseModel):
    """案例/故事。"""
    title: str = Field(description="案例标题")
    background: str = Field(description="背景：起因描述")
    process: str = Field(description="过程：完整经过，保留人名、地名、时间")
    result: str = Field(description="结果：具体结果，保留数据")
    insight: str = Field(description="启示：这个案例说明了什么")
    related_entities: list[str] = Field(
        default_factory=list,
        description="涉及的实体名称列表",
    )
    source_para_ids: list[int] = Field(default_factory=list)


class ExtractedDataPoint(BaseModel):
    """数据/事实。"""
    metric: str = Field(description="指标名称")
    value: str = Field(description="具体数值")
    context: str = Field(description="数据出现的上下文")
    source_attribution: str = Field(
        default="",
        description="数据来源（论文、实验、调查）",
    )
    source_para_ids: list[int] = Field(default_factory=list)


class ExtractedQuote(BaseModel):
    """引言/金句。"""
    text: str = Field(description="引言原文，保留原话")
    speaker: str = Field(default="未知", description="说话人")
    context: str = Field(default="", description="这句话在什么背景下说的")
    source_para_ids: list[int] = Field(default_factory=list)


# ──────────────────────────────────────────────────────────────
# 章节级聚合模型（Phase 1 最终输出）
# ──────────────────────────────────────────────────────────────


class ChapterDetails(BaseModel):
    """Round 3 细节提取的输出。"""
    cases: list[ExtractedCase] = Field(default_factory=list)
    data_points: list[ExtractedDataPoint] = Field(default_factory=list)
    quotes: list[ExtractedQuote] = Field(default_factory=list)
    key_arguments: list[str] = Field(
        default_factory=list,
        description="本章核心论点列表",
    )
    recommendations: list[dict] = Field(
        default_factory=list,
        description="实践建议列表",
    )


class ChapterExtraction(BaseModel):
    """单章 3 轮提取的合并结果。"""
    chapter_id: str
    chapter_title: str
    entities: list[ExtractedEntity] = Field(default_factory=list)
    relationships: list[ExtractedRelationship] = Field(default_factory=list)
    cases: list[ExtractedCase] = Field(default_factory=list)
    data_points: list[ExtractedDataPoint] = Field(default_factory=list)
    quotes: list[ExtractedQuote] = Field(default_factory=list)
    key_arguments: list[str] = Field(default_factory=list)
    recommendations: list[dict] = Field(default_factory=list)


# ──────────────────────────────────────────────────────────────
# 全书级模型（Phase 0 输出）
# ──────────────────────────────────────────────────────────────


class BookContext(BaseModel):
    """Phase 0 全书深度阅读的输出。"""
    book_title: str
    core_thesis: str = Field(description="全书主旨：2-3 句话概括作者最核心的主张")
    key_arguments: list[str] = Field(
        default_factory=list,
        description="3-5 个关键论点",
    )
    terminology: dict[str, str] = Field(
        default_factory=dict,
        description="术语表：{术语: 定义}",
    )
    chapter_outline: str = Field(description="各章之间的逻辑关系描述")


# ──────────────────────────────────────────────────────────────
# 实体消歧模型
# ──────────────────────────────────────────────────────────────


class EntityMatchJudgment(BaseModel):
    """LLM 判断两个实体是否为同一事物的输出。"""
    same: bool = Field(description="是否为同一实体")
    reason: str = Field(description="判断理由")


# ──────────────────────────────────────────────────────────────
# 图质量模型
# ──────────────────────────────────────────────────────────────


class GraphQualityMetrics(BaseModel):
    """图质量指标。"""
    total_entities: int
    total_relationships: int
    orphan_entities: int = Field(description="无任何关系的实体数")
    orphan_rate: float = Field(description="孤立实体比率")
    avg_degree: float = Field(description="平均关系数")
    connected_components: int = Field(description="连通分量数")
    largest_component_ratio: float = Field(description="最大连通分量占比")
    chapter_coverage: dict[str, float] = Field(
        default_factory=dict,
        description="{chapter_id: 段落覆盖率百分比}",
    )
    overall_para_coverage: float = Field(description="全书段落覆盖率")


# ──────────────────────────────────────────────────────────────
# 流水线配置模型
# ──────────────────────────────────────────────────────────────


class ModelConfig(BaseModel):
    """分层模型配置。"""
    context: str = Field(default="qwen-turbo", description="Phase 0 全书阅读")
    extraction: str = Field(default="qwen-turbo", description="Phase 1 实体/关系/细节提取")
    resolution: str = Field(default="qwen-turbo", description="Phase 2 实体消歧")


class PipelineConfig(BaseModel):
    """流水线配置。"""
    models: ModelConfig = Field(default_factory=ModelConfig)
    concurrency: int = Field(default=3, description="章节间并发数")
    long_chapter_threshold: int = Field(default=20_000, description="长章节阈值 (tokens)")
    segment_target_size: int = Field(default=12_000, description="分段目标大小 (tokens)")
    overlap_size: int = Field(default=1_500, description="分段重叠大小 (tokens)")
    entity_similarity_threshold: float = Field(default=0.85, description="实体消歧 embedding 阈值")
    max_gap_fill_iterations: int = Field(default=1, description="质量不达标时的最大重提取次数")


class QualityThresholds(BaseModel):
    """图质量阈值。"""
    max_orphan_rate: float = Field(default=0.15)
    max_connected_components: int = Field(default=3)
    min_largest_component_ratio: float = Field(default=0.70)
    min_avg_degree: float = Field(default=1.5)
    min_chapter_coverage: float = Field(default=0.80)
    min_overall_para_coverage: float = Field(default=0.75)
