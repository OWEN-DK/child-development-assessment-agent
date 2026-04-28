"""三层标准化指标 Schema"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class MetricScore(BaseModel):
    """单个指标评分"""

    value: float  # 0-1 归一化
    passed: bool
    threshold: float
    details: dict[str, Any] = {}


class MetricInput(BaseModel):
    """指标计算器输入"""

    run_id: str
    test_case_id: str
    query: str
    retrieved_contexts: list[str] = []
    expected_knowledge_ids: list[str] = []
    actual_knowledge_ids: list[str] = []
    expected_answer: Optional[str] = None
    actual_answer: Optional[str] = None
    execution_time_ms: Optional[int] = None
    token_count: Optional[int] = None
    cost_usd: Optional[float] = None


class MetricOutput(BaseModel):
    """指标计算器输出"""

    score: float
    passed: bool
    threshold: float
    details: dict[str, Any] = {}


class Layer1Metrics(BaseModel):
    """L1 检索质量指标"""

    context_precision: MetricScore
    context_recall: MetricScore
    noise_sensitivity: MetricScore
    mrr: MetricScore
    ndcg: MetricScore


class Layer2Metrics(BaseModel):
    """L2 生成质量指标"""

    faithfulness: MetricScore
    answer_relevancy: MetricScore
    groundedness: MetricScore


class Layer3Metrics(BaseModel):
    """L3 系统质量指标"""

    rule_compliance: MetricScore
    regression_score: MetricScore
    cost_efficiency: MetricScore
    config_stability: MetricScore


class RunMetrics(BaseModel):
    """单次运行的三层指标汇总"""

    l1: Layer1Metrics
    l2: Layer2Metrics
    l3: Layer3Metrics
    overall_score: float
    weights: dict[str, float]  # {"l1": 0.4, "l2": 0.4, "l3": 0.2}
    calculated_at: datetime
