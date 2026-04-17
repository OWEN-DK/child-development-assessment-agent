# 05 - RagEvalTestRunResult 模型定义 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 05 - RagEvalTestRunResult 模型定义

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
测试运行结果模型，记录每个测试用例在某次测试运行中的具体检索结果、命中情况。

## 实施文件
`backend/src/models/rag_eval/test_run_result.py`

## SQLAlchemy 模型定义
```python
import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, Integer, Boolean, JSON, Float, ForeignKey, func, Index, Enum as SAEnum
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

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

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

    matched_doc_ids: Mapped[list] = mapped_column(JSON, default=list, comment="实际命中的文档ID列表")
    matched_doc_scores: Mapped[list] = mapped_column(JSON, default=list, comment="命中文档的分数列表")

    status: Mapped[RagEvalTestRunResultStatus] = mapped_column(
        SAEnum(RagEvalTestRunResultStatus, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer, comment="单用例执行耗时(毫秒)")

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    test_run: Mapped["RagEvalTestRun"] = relationship(back_populates="run_results")
    test_case: Mapped["RagEvalTestCase"] = relationship(back_populates="run_results")
```

## 字段说明
| 字段名 | 类型 | 可空 | 说明 |
|--------|------|------|------|
| id | String(36) | 否 | 主键UUID |
| run_id | String(36) | 否 | 测试运行ID，FK→rag_eval_test_runs.id |
| case_id | String(36) | 否 | 测试用例ID，FK→rag_eval_test_cases.id |
| query | TEXT | 否 | 查询文本快照 |
| hit_at_1 | BOOLEAN | 否 | Top1是否命中 |
| hit_at_3 | BOOLEAN | 否 | Top3是否命中 |
| hit_at_5 | BOOLEAN | 否 | Top5是否命中 |
| matched_doc_ids | JSON | 否 | 实际命中的文档ID列表 |
| matched_doc_scores | JSON | 否 | 命中文档的分数列表 |
| status | VARCHAR(64) | 否 | PASSED、FAILED |
| duration_ms | INT | 是 | 单用例执行耗时(毫秒) |
| created_at | DATETIME | 否 | 创建时间 |

## 关联关系
- 多对1关联RagEvalTestRun
- 多对1关联RagEvalTestCase

## 用途
- 断线重连时从数据库恢复进度（Redis无数据时的降级方案）
- 运行详情页展示用例明细
