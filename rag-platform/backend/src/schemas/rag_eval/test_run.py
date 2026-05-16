"""测试运行实体类"""
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class TestRunStatus(str, Enum):
    """测试运行状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ── 请求实体 ──────────────────────────────────────────

class CreateTestRunReq(BaseModel):
    """创建测试运行请求"""
    name: Optional[str] = Field(default=None, max_length=255, description="运行名称")
    pipeline_id: str = Field(..., description="被评估的管道ID")
    pipeline_version: int = Field(default=1, ge=1, description="管道版本")
    test_set_ids: list[str] = Field(default_factory=list, description="测试集ID列表")
    snapshot_id: Optional[str] = Field(default=None, description="知识库快照ID")
    auto_snapshot: bool = Field(default=True, description="是否自动创建快照")
    simulated_role_id: Optional[str] = Field(default=None, description="模拟的角色ID")


class CompareRunsReq(BaseModel):
    """对比两次运行请求"""
    run_id_1: str = Field(..., description="运行ID 1")
    run_id_2: str = Field(..., description="运行ID 2")


# ── 响应实体 ──────────────────────────────────────────

class TestRunRead(BaseModel):
    """测试运行读取"""
    id: str
    tenant_id: str
    name: Optional[str] = None
    status: TestRunStatus = TestRunStatus.PENDING
    pipeline_id: str
    pipeline_version: int
    test_set_ids: Optional[list[str]] = None
    snapshot_id: Optional[str] = None
    config_version_id: Optional[str] = None
    task_id: Optional[str] = None
    total_test_cases: int = 0
    passed_test_cases: int = 0
    overall_score: Optional[float] = None
    l1_metrics_json: Optional[dict[str, Any]] = None
    l2_metrics_json: Optional[dict[str, Any]] = None
    l3_metrics_json: Optional[dict[str, Any]] = None
    cross_domain_metrics_json: Optional[dict[str, Any]] = None
    diagnosis_json: Optional[dict[str, Any]] = None
    domain_results_json: Optional[dict[str, Any]] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    run_as_user_id: Optional[str] = None
    simulated_role_id: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class TestRunResultRead(BaseModel):
    """测试运行结果读取"""
    id: str
    run_id: str
    test_case_id: str
    tenant_id: str
    query: str
    retrieved_doc_ids: Optional[list[str]] = None
    retrieved_contexts: Optional[list[str]] = None
    expected_knowledge_ids: Optional[list[str]] = None
    actual_knowledge_ids: Optional[list[str]] = None
    precision: Optional[float] = None
    recall: Optional[float] = None
    f1: Optional[float] = None
    mrr: Optional[float] = None
    ndcg: Optional[float] = None
    actual_answer: Optional[str] = None
    domain_results_json: Optional[dict[str, Any]] = None
    l1_metrics_json: Optional[dict[str, Any]] = None
    l2_metrics_json: Optional[dict[str, Any]] = None
    diagnosis_json: Optional[dict[str, Any]] = None
    passed: Optional[int] = None
    error_message: Optional[str] = None
    execution_time_ms: Optional[int] = None

    model_config = {"from_attributes": True}


class TestRunList(BaseModel):
    """测试运行列表"""
    items: list[TestRunRead]
    total: int
