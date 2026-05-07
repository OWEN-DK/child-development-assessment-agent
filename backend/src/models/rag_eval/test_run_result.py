from datetime import datetime
from typing import Any

from sqlalchemy import (DECIMAL, JSON, Boolean, DateTime, Integer, String, Text,
                        func)
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base


class TestRunResult(Base):
    __tablename__ = "test_run_results"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    test_case_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    query: Mapped[str] = mapped_column(Text, nullable=False)
    # 检索结果
    retrieved_doc_ids: Mapped[list[str] | None] = mapped_column(
        JSON, comment="检索到的文档 ID 列表"
    )
    retrieved_contexts: Mapped[list[str] | None] = mapped_column(
        JSON, nullable=True, comment="检索上下文文本列表"
    )
    relevant_doc_ids: Mapped[list[str] | None] = mapped_column(
        JSON, comment="相关文档 ID 列表"
    )
    expected_knowledge_ids: Mapped[list[str] | None] = mapped_column(
        JSON, comment="期望知识片段 ID"
    )
    actual_knowledge_ids: Mapped[list[str] | None] = mapped_column(
        JSON, comment="实际匹配的知识片段 ID"
    )
    matched_count: Mapped[int] = mapped_column(Integer, default=0)
    expected_count: Mapped[int] = mapped_column(Integer, default=0)
    actual_count: Mapped[int] = mapped_column(Integer, default=0)
    # 检索指标
    precision: Mapped[float | None] = mapped_column(DECIMAL(5, 4))
    recall: Mapped[float | None] = mapped_column(DECIMAL(5, 4))
    f1: Mapped[float | None] = mapped_column(DECIMAL(5, 4))
    mrr: Mapped[float | None] = mapped_column(DECIMAL(5, 4), default=0)
    ndcg: Mapped[float | None] = mapped_column(DECIMAL(5, 4))
    hit_rate_1: Mapped[float | None] = mapped_column(DECIMAL(5, 4), default=0)
    hit_rate_3: Mapped[float | None] = mapped_column(DECIMAL(5, 4), default=0)
    hit_rate_5: Mapped[float | None] = mapped_column(DECIMAL(5, 4), default=0)
    # 生成答案
    actual_answer: Mapped[str | None] = mapped_column(
        Text, comment="RAG 生成的实际答案"
    )
    # 双轨指标
    l1_metrics_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, comment="单用例 L1 指标"
    )
    l2_metrics_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, comment="单用例 L2 指标"
    )
    diagnosis_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, comment="单用例诊断结果"
    )
    # 执行信息
    passed: Mapped[bool | None] = mapped_column(Boolean, comment="是否通过")
    error_message: Mapped[str | None] = mapped_column(Text)
    execution_time_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = {"extend_existing": True}
