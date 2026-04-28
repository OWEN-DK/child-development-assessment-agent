"""测试运行 Schema"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class TestRunCreate(BaseModel):
    """测试运行创建请求"""

    name: str
    description: str = ""
    test_set_ids: list[str]
    custom_case_ids: list[str] = []
    snapshot_id: Optional[str] = None
    auto_snapshot: bool = True


class TestRunRead(BaseModel):
    """测试运行读取"""

    id: str
    name: str
    description: str
    test_set_ids: list[str]
    custom_case_ids: list[str]
    snapshot_id: Optional[str] = None
    config_version_id: Optional[str] = None
    config_snapshot: Optional[dict] = None
    status: str
    total_test_cases: int
    passed_test_cases: int
    overall_precision: Optional[float] = None
    overall_recall: Optional[float] = None
    overall_f1: Optional[float] = None
    overall_mrr: Optional[float] = None
    overall_ndcg: Optional[float] = None
    overall_score: Optional[float] = None
    l1_metrics_json: Optional[dict] = None
    l2_metrics_json: Optional[dict] = None
    l3_metrics_json: Optional[dict] = None
    diagnosis_json: Optional[dict] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TestRunList(BaseModel):
    """测试运行分页列表"""

    items: list[TestRunRead]
    total: int
    page: int
    page_size: int


class RetrievalMetrics(BaseModel):
    """检索指标计算结果"""

    precision: float
    recall: float
    f1: float
    mrr: float
    ndcg: float
    hit_rate_1: float
    hit_rate_3: float
    hit_rate_5: float
    matched_count: int
    expected_count: int
    actual_count: int


class TestRunResultItem(BaseModel):
    """测试运行结果项"""

    id: str
    run_id: str
    test_case_id: str
    query: str
    retrieved_doc_ids: list[str] = []
    relevant_doc_ids: list[str] = []
    expected_knowledge_ids: list[str] = []
    actual_knowledge_ids: list[str] = []
    matched_count: int = 0
    expected_count: int = 0
    actual_count: int = 0
    precision: Optional[float] = None
    recall: Optional[float] = None
    f1: Optional[float] = None
    mrr: Optional[float] = None
    ndcg: Optional[float] = None
    hit_rate_1: Optional[float] = None
    hit_rate_3: Optional[float] = None
    hit_rate_5: Optional[float] = None
    actual_answer: Optional[str] = None
    passed: bool = False
    error_message: Optional[str] = None
    execution_time_ms: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RunComparison(BaseModel):
    """运行对比结果"""

    run_1: TestRunRead
    run_2: TestRunRead
    metric_deltas: dict[str, float]  # {"precision": 0.02, "recall": -0.01, ...}
    improved: list[str]  # 改进的指标名列表
    degraded: list[str]  # 退化的指标名列表
    common_bad_cases: list[str]  # 两次运行都失败的用例 ID
    new_bad_cases: list[str]  # run_2 新增的坏案
    fixed_bad_cases: list[str]  # run_2 修复的坏案
