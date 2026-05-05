from datetime import datetime
from typing import Any

from sqlalchemy import (DECIMAL, JSON, DateTime, Enum, Integer,
                        String, Text, func)
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.models.rag_eval.enums import TestRunStatus


class TestRun(Base):
    __tablename__ = "test_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    test_set_ids: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, comment="关联的测试集 ID 列表"
    )
    custom_case_ids: Mapped[list[str] | None] = mapped_column(
        JSON, comment="额外用例 ID 列表"
    )
    snapshot_id: Mapped[str | None] = mapped_column(
        String(64), index=True, comment="知识库快照 ID"
    )
    config_version_id: Mapped[str | None] = mapped_column(
        String(64), index=True, comment="配置版本 ID"
    )
    config_snapshot: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, comment="配置快照"
    )
    previous_config_version_id: Mapped[str | None] = mapped_column(
        String(64), comment="前一配置版本 ID"
    )
    task_id: Mapped[str | None] = mapped_column(
        String(64), index=True, comment="异步任务 ID，用于取消运行"
    )
    status: Mapped[TestRunStatus] = mapped_column(
        Enum(TestRunStatus, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=TestRunStatus.PENDING,
        index=True,
        comment="pending/running/completed/failed/cancelled",
    )
    total_test_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    passed_test_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    overall_precision: Mapped[float | None] = mapped_column(
        DECIMAL(5, 4), comment="整体精确率"
    )
    overall_recall: Mapped[float | None] = mapped_column(
        DECIMAL(5, 4), comment="整体召回率"
    )
    overall_f1: Mapped[float | None] = mapped_column(DECIMAL(5, 4), comment="整体F1")
    overall_mrr: Mapped[float | None] = mapped_column(DECIMAL(5, 4), comment="整体MRR")
    overall_ndcg: Mapped[float | None] = mapped_column(
        DECIMAL(5, 4), comment="整体NDCG"
    )
    l1_metrics_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, comment="L1 检索质量指标"
    )
    l2_metrics_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, comment="L2 生成质量指标"
    )
    l3_metrics_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, comment="L3 系统质量指标"
    )
    overall_score: Mapped[float | None] = mapped_column(
        DECIMAL(5, 4), comment="加权综合得分"
    )
    diagnosis_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, comment="六层诊断结果"
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = {"extend_existing": True}
