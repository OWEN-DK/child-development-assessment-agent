# 04 - RagEvalTestRun 模型定义 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 04 - RagEvalTestRun 模型定义

**Architecture:** 参考下方原文档的实现方案和数据模型

**Tech Stack:** Python, FastAPI, TypeScript, React

---

### Task 1: 实现核心逻辑与测试

**Files:**
- Test: `tests/test_placeholder.py`

- [ ] **Step 1: Write the failing test**
  - 根据下方的验收标准和测试方案，编写对应的测试用例
- [ ] **Step 2: Run test to verify it fails**
  - 执行测试并确保看到预期失败信息 (Red)
- [ ] **Step 3: Write minimal implementation**
  - 根据下方"实现方案"中的步骤，编写或修改业务代码
- [ ] **Step 4: Run test to verify it passes**
  - 执行测试确保通过 (Green)
- [ ] **Step 5: Commit**
  - `git add` 相关文件并提交 commit

---

## 原始需求与设计细节 (供参考)

## 模型说明
测试运行记录模型，记录每次测试集运行的元数据、状态、配置版本等信息。

## 实施文件
`backend/src/models/rag_eval/test_run.py`

## SQLAlchemy 模型定义
```python
import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, Integer, Float, JSON, ForeignKey, func, Index, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.core.database import Base
from src.models.rag_eval.enums import RagEvalTestRunStatus, RagEvalABTestSide


class RagEvalTestRun(Base):
    __tablename__ = "rag_eval_test_runs"
    __table_args__ = (
        Index("idx_rag_eval_test_run_testset_status_created", "test_set_id", "status", "created_at"),
        Index("idx_rag_eval_test_run_config_version", "config_version_id"),
        {"comment": "RAG评估测试运行记录表"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[RagEvalTestRunStatus] = mapped_column(
        SAEnum(RagEvalTestRunStatus, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=RagEvalTestRunStatus.PENDING,
    )

    test_set_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("rag_eval_test_sets.id", ondelete="CASCADE"),
        nullable=False,
    )
    config_version_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("rag_eval_config_versions.id", ondelete="SET NULL"),
    )

    created_by: Mapped[str | None] = mapped_column(String(36), comment="触发运行的用户ID")

    overall_precision: Mapped[float | None] = mapped_column(Float)
    overall_recall: Mapped[float | None] = mapped_column(Float)
    overall_f1: Mapped[float | None] = mapped_column(Float)
    overall_mrr: Mapped[float | None] = mapped_column(Float)
    overall_ndcg: Mapped[float | None] = mapped_column(Float)

    total_test_cases: Mapped[int] = mapped_column(Integer, default=0)
    passed_test_cases: Mapped[int] = mapped_column(Integer, default=0)
    failed_at_case_id: Mapped[str | None] = mapped_column(String(36), comment="失败时的用例ID")

    ab_test_id: Mapped[str | None] = mapped_column(String(36), comment="A/B测试组ID")
    ab_test_side: Mapped[RagEvalABTestSide | None] = mapped_column(
        SAEnum(RagEvalABTestSide, values_callable=lambda obj: [e.value for e in obj]),
        comment="标识本次运行是配置A还是配置B",
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, comment="仅在status=completed时填写")

    test_set: Mapped["RagEvalTestSet"] = relationship(back_populates="test_runs")
    config_version: Mapped["RagEvalConfigVersion | None"] = relationship(back_populates="test_runs")
    run_results: Mapped[list["RagEvalTestRunResult"]] = relationship(back_populates="test_run", cascade="all, delete-orphan")
    reports: Mapped[list["RagEvalTestReport"]] = relationship(back_populates="test_run", cascade="all, delete-orphan")
    intent_logs: Mapped[list["RagEvalQueryIntentLog"]] = relationship(back_populates="test_run", cascade="all, delete-orphan")
```

## 字段说明
| 字段名 | 类型 | 可空 | 说明 |
|--------|------|------|------|
| id | String(36) | 否 | 主键UUID |
| name | VARCHAR(255) | 否 | 运行名称 |
| status | VARCHAR(64) | 否 | PENDING、RUNNING、COMPLETED、FAILED、CANCELLED |
| test_set_id | String(36) | 否 | 测试集ID，FK→rag_eval_test_sets.id |
| config_version_id | String(36) | 是 | 配置版本ID，FK→rag_eval_config_versions.id |
| created_by | String(36) | 是 | 触发运行的用户ID |
| overall_precision | FLOAT | 是 | 汇总精确率 |
| overall_recall | FLOAT | 是 | 汇总召回率 |
| overall_f1 | FLOAT | 是 | 汇总F1 |
| overall_mrr | FLOAT | 是 | 汇总MRR |
| overall_ndcg | FLOAT | 是 | 汇总NDCG |
| total_test_cases | INT | 否 | 总测试用例数 |
| passed_test_cases | INT | 否 | 通过测试用例数 |
| failed_at_case_id | String(36) | 是 | 失败时的用例ID |
| ab_test_id | String(36) | 是 | A/B测试组ID |
| ab_test_side | VARCHAR(64) | 是 | A或B |
| created_at | DATETIME | 否 | 创建时间 |
| completed_at | DATETIME | 是 | 完成时间，仅status=completed时填写 |

## 关联关系
- 多对1关联RagEvalTestSet
- 多对1关联RagEvalConfigVersion
- 1对多关联RagEvalTestRunResult
- 1对多关联RagEvalTestReport
- 1对多关联RagEvalQueryIntentLog

## 注意事项
- 不持有 report_id FK，通过 TestReport.run_id 反向查询
- completed_at 语义：仅在 status=completed 时填写（失败/取消时为 NULL）
