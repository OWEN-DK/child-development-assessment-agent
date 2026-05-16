"""测试运行模型"""
from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, Integer, Numeric, String, Text

from src.models.base import Base


class TestRun(Base):
    """测试运行表"""
    __tablename__ = "test_runs"

    id = Column(String(64), primary_key=True, comment="运行ID")
    tenant_id = Column(String(64), nullable=False, index=True, comment="租户ID")
    name = Column(String(255), comment="运行名称")
    status = Column(String(20), nullable=False, default="pending", comment="状态：pending/running/completed/failed/cancelled")
    pipeline_id = Column(String(64), nullable=False, index=True, comment="被评估的管道ID")
    pipeline_version = Column(Integer, nullable=False, comment="管道版本")
    test_set_ids = Column(JSON, comment="测试集ID列表")
    snapshot_id = Column(String(64), comment="知识库快照ID")
    config_version_id = Column(String(64), comment="评估配置版本ID")
    task_id = Column(String(64), comment="异步任务ID")
    total_test_cases = Column(Integer, nullable=False, default=0)
    passed_test_cases = Column(Integer, nullable=False, default=0)
    overall_score = Column(Numeric(5, 4), comment="综合得分")
    l1_metrics_json = Column(JSON, comment="L1 检索层指标")
    l2_metrics_json = Column(JSON, comment="L2 生成层指标")
    l3_metrics_json = Column(JSON, comment="L3 系统层指标")
    cross_domain_metrics_json = Column(JSON, comment="跨域指标")
    diagnosis_json = Column(JSON, comment="诊断结果")
    domain_results_json = Column(JSON, comment="域结果详情")
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    run_as_user_id = Column(String(64), comment="以哪个用户身份运行")
    simulated_role_id = Column(String(64), comment="模拟的角色ID")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class TestRunResult(Base):
    """测试运行结果表"""
    __tablename__ = "test_run_results"

    id = Column(String(64), primary_key=True, comment="结果ID")
    run_id = Column(String(64), nullable=False, index=True, comment="运行ID")
    test_case_id = Column(String(64), nullable=False, comment="用例ID")
    tenant_id = Column(String(64), nullable=False, index=True, comment="租户ID")
    query = Column(Text, nullable=False)
    retrieved_doc_ids = Column(JSON)
    retrieved_contexts = Column(JSON)
    expected_knowledge_ids = Column(JSON)
    actual_knowledge_ids = Column(JSON)
    precision = Column(Numeric(5, 4))
    recall = Column(Numeric(5, 4))
    f1 = Column(Numeric(5, 4))
    mrr = Column(Numeric(5, 4))
    ndcg = Column(Numeric(5, 4))
    actual_answer = Column(Text)
    domain_results_json = Column(JSON)
    l1_metrics_json = Column(JSON)
    l2_metrics_json = Column(JSON)
    diagnosis_json = Column(JSON)
    passed = Column(Integer, comment="是否通过（1/0/null）")
    error_message = Column(Text)
    execution_time_ms = Column(Integer)
