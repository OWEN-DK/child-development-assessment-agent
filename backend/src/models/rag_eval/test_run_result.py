import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime
from sqlalchemy import Enum as SAEnum
from sqlalchemy import Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base
from src.models.rag_eval.enums import RagEvalTestRunResultStatus


class RagEvalTestRunResult(Base):
    __tablename__ = "rag_eval_test_run_results"
    __table_args__ = (
        Index("idx_rag_eval_test_run_result_run_id", "run_id"),
        Index("idx_rag_eval_test_run_result_run_status", "run_id", "status"),
        {"comment": "测试运行结果详情表"},
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("rag_eval_test_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    case_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("rag_eval_test_cases.id", ondelete="CASCADE"),
        nullable=False,
    )

    query: Mapped[str] = mapped_column(Text, nullable=False, comment="查询文本快照")

    hit_at_1: Mapped[bool] = mapped_column(Boolean, default=False)
    hit_at_3: Mapped[bool] = mapped_column(Boolean, default=False)
    hit_at_5: Mapped[bool] = mapped_column(Boolean, default=False)

    matched_doc_ids: Mapped[list] = mapped_column(
        JSON, default=list, comment="实际命中的文档ID列表"
    )
    matched_doc_scores: Mapped[list] = mapped_column(
        JSON, default=list, comment="命中文档的分数列表"
    )

    status: Mapped[RagEvalTestRunResultStatus] = mapped_column(
        SAEnum(
            RagEvalTestRunResultStatus,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
    )
    duration_ms: Mapped[int | None] = mapped_column(
        Integer, comment="单用例执行耗时(毫秒)"
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    test_run: Mapped["RagEvalTestRun"] = relationship(back_populates="run_results")
    test_case: Mapped["RagEvalTestCase"] = relationship(back_populates="run_results")
