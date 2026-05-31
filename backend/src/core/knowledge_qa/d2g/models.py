"""D2G 流水线数据模型 — 所有 Pydantic 模型定义。

放置位置: backend/src/core/knowledge_qa/d2g/models.py
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, validator, field_validator


# ──────────────────────────────────────────────────────────────
# 枚举类型（与 schema.py 保持一致）
# ──────────────────────────────────────────────────────────────


class EntityType(str, Enum):
    """实体类型枚举（15+ 种，与 schema.py D2G_ENTITY_TYPES 一致）。"""
    Problem = "Problem"
    Solution = "Solution"
    BrainRegion = "BrainRegion"
    Risk = "Risk"
    Exercise = "Exercise"
    RootCause = "RootCause"
    Prescription = "Prescription"
    ChildProfile = "ChildProfile"
    CognitiveProcess = "CognitiveProcess"
    Theory = "Theory"
    Mechanism = "Mechanism"
    DevelopmentalStage = "DevelopmentalStage"
    Strategy = "Strategy"
    KeyInsight = "KeyInsight"
    ResearchFinding = "ResearchFinding"
    # LLM 可能额外生成的类型（宽松匹配）
    BookTitle = "BookTitle"
    Concept = "Concept"
    Fact = "Fact"
    Quote = "Quote"
    DataPoint = "DataPoint"


class RelationType(str, Enum):
    """关系类型枚举（大类.子类型 层级结构）。

    命名规则: MAJOR_MINOR，大类全称 + 子类型，以下划线连接。
    LLM 输出时必须从本列表中选择，不得自行编造。
    """

    # ── 因果关系 ──
    CAUSAL_CAUSES = "CAUSAL_CAUSES"               # A 导致 B
    CAUSAL_LEADS_TO = "CAUSAL_LEADS_TO"           # A 导向 B（长期/间接）
    CAUSAL_RESULTS_IN = "CAUSAL_RESULTS_IN"       # A 产生 B（直接结果）
    CAUSAL_CONTRIBUTES_TO = "CAUSAL_CONTRIBUTES_TO"  # A 促成 B（多因素之一）
    CAUSAL_TRIGGERS = "CAUSAL_TRIGGERS"           # A 触发 B（即时/急性）

    # ── 治疗/干预关系 ──
    THERAPEUTIC_TREATS = "THERAPEUTIC_TREATS"         # A 治疗/治愈 B
    THERAPEUTIC_PREVENTS = "THERAPEUTIC_PREVENTS"     # A 预防 B
    THERAPEUTIC_ALLEVIATES = "THERAPEUTIC_ALLEVIATES" # A 缓解 B
    THERAPEUTIC_IMPROVES = "THERAPEUTIC_IMPROVES"     # A 改善 B
    THERAPEUTIC_INHIBITS = "THERAPEUTIC_INHIBITS"     # A 抑制 B
    THERAPEUTIC_ENHANCES = "THERAPEUTIC_ENHANCES"     # A 增强 B

    # ── 结构/组成关系 ──
    STRUCTURAL_PART_OF = "STRUCTURAL_PART_OF"     # A 是 B 的一部分
    STRUCTURAL_CONTAINS = "STRUCTURAL_CONTAINS"   # A 包含 B
    STRUCTURAL_CONSISTS_OF = "STRUCTURAL_CONSISTS_OF"  # A 由 B 组成
    STRUCTURAL_BELONGS_TO = "STRUCTURAL_BELONGS_TO"    # A 属于 B

    # ── 功能/参与关系 ──
    FUNCTIONAL_REGULATES = "FUNCTIONAL_REGULATES"     # A 调节 B
    FUNCTIONAL_MODULATES = "FUNCTIONAL_MODULATES"     # A 调制 B
    FUNCTIONAL_PARTICIPATES_IN = "FUNCTIONAL_PARTICIPATES_IN"  # A 参与 B
    FUNCTIONAL_INVOLVED_IN = "FUNCTIONAL_INVOLVED_IN"         # A 涉及 B
    FUNCTIONAL_PLAYS_ROLE_IN = "FUNCTIONAL_PLAYS_ROLE_IN"     # A 在 B 中发挥作用
    FUNCTIONAL_MEDIATES = "FUNCTIONAL_MEDIATES"       # A 介导 B
    FUNCTIONAL_TRANSFORMS = "FUNCTIONAL_TRANSFORMS"   # A 转化为 B

    # ── 证据/研究关系 ──
    EVIDENCE_SUPPORTS = "EVIDENCE_SUPPORTS"       # A 支持 B（论点/理论）
    EVIDENCE_PROVEN_BY = "EVIDENCE_PROVEN_BY"     # A 被 B 证明
    EVIDENCE_BASED_ON = "EVIDENCE_BASED_ON"       # A 基于 B
    EVIDENCE_CONTRADICTS = "EVIDENCE_CONTRADICTS" # A 与 B 矛盾
    EVIDENCE_DEMONSTRATES = "EVIDENCE_DEMONSTRATES"  # A 演示/展示 B

    # ── 时间/发展关系 ──
    TEMPORAL_PRECEDES = "TEMPORAL_PRECEDES"       # A 先于 B
    TEMPORAL_FOLLOWS = "TEMPORAL_FOLLOWS"         # A 后于 B
    TEMPORAL_DURING = "TEMPORAL_DURING"           # A 在 B 期间发生
    TEMPORAL_DEVELOPS_INTO = "TEMPORAL_DEVELOPS_INTO"  # A 发展为 B

    # ── 比较关系 ──
    COMPARISON_SIMILAR_TO = "COMPARISON_SIMILAR_TO"       # A 类似于 B
    COMPARISON_DIFFERENT_FROM = "COMPARISON_DIFFERENT_FROM" # A 不同于 B
    COMPARISON_ALTERNATIVE_TO = "COMPARISON_ALTERNATIVE_TO" # A 是 B 的替代

    # ── 属性/关联关系 ──
    ATTRIBUTE_ASSOCIATED_WITH = "ATTRIBUTE_ASSOCIATED_WITH"  # A 与 B 相关
    ATTRIBUTE_HAS_PROPERTY = "ATTRIBUTE_HAS_PROPERTY"        # A 具有属性 B
    ATTRIBUTE_CHARACTERIZED_BY = "ATTRIBUTE_CHARACTERIZED_BY"  # A 以 B 为特征
    ATTRIBUTE_MEASURED_BY = "ATTRIBUTE_MEASURED_BY"          # A 通过 B 测量

    # ── 兜底 ──
    RELATES_TO = "RELATES_TO"  # 通用关联（无法归入以上类别时使用）


# ──────────────────────────────────────────────────────────────
# 提取结果模型（Phase 1 输出）
# ──────────────────────────────────────────────────────────────


class ExtractedEntity(BaseModel):
    """单个实体。"""
    name: str = Field(description="实体名称")
    entity_type: str = Field(description="实体类型，如 Person、Event、Theory、BrainRegion 等，LLM 可自由输出最贴切的类型名称")

    description: str = Field(default="", description="实体描述")

    @validator("description", pre=True, always=True)
    def validate_description(cls, v):
        """确保描述至少有内容，短描述自动补充"""
        if not v or not v.strip():
            return "待补充描述"
        v = v.strip()
        # 如果描述太短，添加前缀使其更有意义
        if len(v) < 10:
            return f"关于{v}的概念"
        return v
    source_para_ids: list[int] = Field(
        default_factory=list,
        description="来源段落序号，如 [3, 5, 7]",
    )


class ExtractedRelationship(BaseModel):
    """两个实体之间的关系。"""
    source: str = Field(description="起点实体名称，必须与实体列表中的 name 一致")
    target: str = Field(description="终点实体名称")
    relation_type: str = Field(description="关系类型（LLM 可自由输出，后续语义合并归类）")
    evidence: str = Field(description="支撑证据，原文直接引用")
    source_para_ids: list[int] = Field(default_factory=list)
    relation_source: str = Field(
        default="llm_extraction",
        description="关系来源: llm_joint / llm_coverage_fix / heuristic_rule / embedding_sim / llm_global_fix",
    )
    confidence: float = Field(default=1.0, description="置信度: LLM=1.0, 规则=0.5, embedding=0.4")


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


# ── 结构化输出包装模型（用于 with_structured_output） ──

class EntityListResponse(BaseModel):
    """实体列表响应（用于 Phase 1 第 1 轮结构化输出）。"""
    items: list[ExtractedEntity] = Field(default_factory=list)


class RelationshipListResponse(BaseModel):
    """关系列表响应（用于 Phase 1 第 2 轮结构化输出）。"""
    items: list[ExtractedRelationship] = Field(default_factory=list)


class JointExtractionResponse(BaseModel):
    """单 Pass 联合提取响应（实体 + 关系一体输出）。"""
    entities: list[ExtractedEntity] = Field(
        default_factory=list,
        description="提取的实体列表",
    )
    relations: list[ExtractedRelationship] = Field(
        default_factory=list,
        description="提取的关系列表，每个实体必须至少出现在 1 条关系中",
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


def _get_d2g_default_model() -> str:
    """读取 D2G 默认模型（优先从 settings，回退 qwen-plus）"""
    try:
        from src.config import settings
        return settings.d2g_model
    except Exception:
        return "qwen-plus"


class ModelConfig(BaseModel):
    """分层模型配置。"""
    context: str = Field(default_factory=_get_d2g_default_model, description="Phase 0 全书阅读")
    extraction: str = Field(default_factory=_get_d2g_default_model, description="Phase 1 实体/关系/细节提取")
    resolution: str = Field(default_factory=_get_d2g_default_model, description="Phase 2 实体消歧")


class PipelineConfig(BaseModel):
    """流水线配置。"""
    models: ModelConfig = Field(default_factory=ModelConfig)
    concurrency: int = Field(default=5, description="章节间并发数")
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


# ── 跨书扩展模型（§08-7） ──────────────────────────────────────


class CrossBookMatch(BaseModel):
    """跨书匹配结果（写入审核 MD）"""
    entity_name: str = Field(description="本章实体名称")
    matched_entity_name: str = Field(description="匹配到的其他书实体名称")
    matched_book_id: str = Field(description="匹配到的书籍 ID")
    matched_book_title: str = Field(description="匹配到的书籍标题")
    similarity: float = Field(description="embedding cosine similarity")
    llm_same: Optional[bool] = Field(default=None, description="LLM 判断是否同一概念")
    llm_reason: Optional[str] = Field(default=None, description="LLM 判断理由")
    reviewer_decision: Optional[str] = Field(
        default=None,
        description="审核者决策: merge/separate/skip",
    )


class CrossBookRelationRecord(BaseModel):
    """跨书关系记录"""
    source_entity: str
    source_book: str
    target_entity: str
    target_book: str
    relation_type: str = Field(description="CONSENSUS / COMPLEMENTS / CONFLICTS")
    confidence: float
    explanation: str


class Phase5Result(BaseModel):
    """Phase 5 执行结果"""
    book_id: str
    total_entities: int = 0
    high_sim_pairs: int = Field(default=0, description="高相似度实体对数")
    mid_sim_pairs: int = Field(default=0, description="中相似度实体对数")
    merged_count: int = 0
    same_as_count: int = 0
    reviewer_override_count: int = Field(default=0, description="审核者覆盖自动决策的数量")
    cross_book_relations: int = 0
    duration_ms: int = 0
    errors: list[str] = Field(default_factory=list)


class GlobalRebuildResult(BaseModel):
    """全局图重建结果"""
    mode: str = Field(description="full / incremental")
    total_entities: int = 0
    merged_entities: int = 0
    community_count: int = 0
    leaf_count: int = 0
    elapsed_s: float = 0.0
    error: Optional[str] = None
