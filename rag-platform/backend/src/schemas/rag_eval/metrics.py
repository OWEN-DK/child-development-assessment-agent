"""评估指标实体类"""
from typing import Optional

from pydantic import BaseModel, Field


class MetricScore(BaseModel):
    """单项指标分数

    N/A 状态：score=-1 且 passed=None 表示该指标不适用（无 Ground Truth）。
    """
    name: str = Field(description="指标名称")
    display_name: str = Field(description="显示名称")
    score: float = Field(description="分数，-1 表示 N/A")
    passed: Optional[bool] = Field(default=None, description="是否通过阈值，None 表示 N/A")
    weight: float = Field(ge=0, le=1, description="权重")


class LayerMetrics(BaseModel):
    """层级指标（L1/L2/L3）

    avg_score=-1 表示该层所有指标均为 N/A。
    """
    layer: str = Field(description="层级标识，如 l1/l2/l3")
    scores: list[MetricScore] = Field(default_factory=list, description="各指标分数")
    avg_score: float = Field(description="加权平均分，-1 表示该层全部 N/A")


class CrossDomainMetrics(BaseModel):
    """跨域指标"""
    domain_activation_accuracy: float = Field(ge=0, le=1, description="域激活准确率")
    cross_domain_coverage: float = Field(ge=0, le=1, description="跨域覆盖率")
    conflict_detection_rate: float = Field(ge=0, le=1, description="冲突检测率")
    e2e_latency_p95: float = Field(ge=0, description="端到端 P95 延迟（毫秒）")


class DomainContribution(BaseModel):
    """域贡献度"""
    domain_id: str = Field(description="域ID")
    domain_name: Optional[str] = Field(default=None, description="域名称")
    contribution_score: float = Field(ge=0, le=1, description="贡献分数")
    activation_accuracy: float = Field(ge=0, le=1, description="激活准确率")
    chunk_count: int = Field(ge=0, description="检索到的分块数")


class RunMetrics(BaseModel):
    """运行指标汇总"""
    l1: LayerMetrics = Field(description="L1 检索层指标")
    l2: LayerMetrics = Field(description="L2 生成层指标")
    l3: LayerMetrics = Field(description="L3 系统层指标")
    cross_domain: Optional[CrossDomainMetrics] = Field(default=None, description="跨域指标（单域管道时为 None）")
    overall_score: float = Field(ge=0, le=1, description="综合得分")


# ==================== 指标计算器输入/输出（旧 backend 迁移） ====================


class MetricInput(BaseModel):
    """指标计算器输入

    所有字段均为 Optional，计算器按需取用。
    """
    query: Optional[str] = Field(default=None, description="查询文本")
    expected_knowledge_ids: list[str] = Field(default_factory=list, description="期望命中的知识片段 ID 列表")
    actual_knowledge_ids: list[str] = Field(default_factory=list, description="实际检索到的知识片段 ID 列表")
    retrieved_contexts: list[str] = Field(default_factory=list, description="检索返回的上下文文本列表")
    actual_answer: Optional[str] = Field(default=None, description="LLM 生成的答案")
    execution_time_ms: Optional[int] = Field(default=None, description="执行耗时（毫秒）")
    error_message: Optional[str] = Field(default=None, description="错误信息")
    cost_usd: Optional[float] = Field(default=None, description="LLM 调用成本（美元）")
    details: dict = Field(default_factory=dict, description="扩展明细（如 baseline_metrics、quality_score 等）")


class MetricOutput(BaseModel):
    """指标计算器输出"""
    score: float = Field(description="0-1 归一化分数")
    passed: bool = Field(description="是否通过阈值")
    threshold: float = Field(description="判定阈值")
    details: Optional[dict] = Field(default=None, description="计算明细")


class MetricResult(BaseModel):
    """单项指标计算结果（评分门面内部使用）

    与 MetricScore 不同，MetricResult 面向计算器输出而非展示层。
    """
    value: float = Field(description="0-1 归一化分数")
    passed: bool = Field(description="是否通过阈值")
    threshold: float = Field(description="判定阈值")
    details: dict = Field(default_factory=dict, description="计算明细")


class Layer1Metrics(BaseModel):
    """L1 检索质量指标（计算器聚合输出）"""
    context_precision: MetricResult
    context_recall: MetricResult
    noise_sensitivity: MetricResult
    mrr: MetricResult
    ndcg: MetricResult


class Layer2Metrics(BaseModel):
    """L2 生成质量指标（计算器聚合输出）"""
    faithfulness: MetricResult
    answer_relevancy: MetricResult
    groundedness: MetricResult


class Layer3Metrics(BaseModel):
    """L3 系统质量指标（计算器聚合输出）"""
    rule_compliance: MetricResult
    regression_score: MetricResult
    cost_efficiency: MetricResult
    config_stability: MetricResult
