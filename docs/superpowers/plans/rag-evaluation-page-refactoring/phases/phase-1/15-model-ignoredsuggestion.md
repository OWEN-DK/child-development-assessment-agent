# 15 - RagEvalIgnoredSuggestion 模型定义 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 15 - RagEvalIgnoredSuggestion 模型定义

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
忽略建议记录模型，独立表，支持高效跨报告查询。

## 实施文件
`backend/src/models/rag_eval/ignored_suggestion.py`

## SQLAlchemy 模型定义
```python
import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, Boolean, ForeignKey, func, Index, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.core.database import Base
from src.models.rag_eval.enums import RagEvalIgnoredSuggestionType, RagEvalIgnoreScope


class RagEvalIgnoredSuggestion(Base):
    __tablename__ = "rag_eval_ignored_suggestions"
    __table_args__ = (
        Index("idx_rag_eval_ignored_suggestion_testset_scope_restored", "test_set_id", "ignore_scope", "restored"),
        Index("idx_rag_eval_ignored_suggestion_report", "report_id"),
        {"comment": "忽略的调优建议记录表"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    test_set_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("rag_eval_test_sets.id", ondelete="CASCADE"),
        nullable=False,
        comment="绑定测试集",
    )
    report_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("rag_eval_test_reports.id", ondelete="CASCADE"),
        comment="report级别时填写",
    )

    param_name: Mapped[str] = mapped_column(String(255), nullable=False, comment="参数名或prompt_key")
    suggestion_type: Mapped[RagEvalIgnoredSuggestionType] = mapped_column(
        SAEnum(RagEvalIgnoredSuggestionType, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
    )
    ignore_scope: Mapped[RagEvalIgnoreScope] = mapped_column(
        SAEnum(RagEvalIgnoreScope, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
    )

    ignored_by: Mapped[str | None] = mapped_column(String(36), comment="操作用户")
    ignored_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    ignore_reason: Mapped[str | None] = mapped_column(String(500))

    restored: Mapped[bool] = mapped_column(Boolean, default=False)
    restored_at: Mapped[datetime | None] = mapped_column(DateTime)

    test_set: Mapped["RagEvalTestSet"] = relationship(back_populates="ignored_suggestions")
    report: Mapped["RagEvalTestReport | None"] = relationship(back_populates="ignored_suggestions")
```

## 字段说明
| 字段名 | 类型 | 可空 | 说明 |
|--------|------|------|------|
| id | String(36) | 否 | 主键UUID |
| test_set_id | String(36) | 否 | 绑定测试集，FK→rag_eval_test_sets.id |
| report_id | String(36) | 是 | report级别时填写，FK→rag_eval_test_reports.id |
| param_name | VARCHAR(255) | 否 | 参数名或prompt_key |
| suggestion_type | VARCHAR(64) | 否 | CONFIG、PROMPT |
| ignore_scope | VARCHAR(64) | 否 | REPORT、TEST_SET |
| ignored_by | String(36) | 是 | 操作用户 |
| ignored_at | DATETIME | 否 | 忽略时间 |
| ignore_reason | VARCHAR(500) | 是 | 忽略原因 |
| restored | BOOLEAN | 否 | 是否已恢复 |
| restored_at | DATETIME | 是 | 恢复时间 |

## 级联删除策略
- test_set_id 删除时：ON DELETE CASCADE，自动清理该测试集关联的所有忽略记录
- report_id 删除时：ON DELETE CASCADE，清理该 report 级别的忽略记录

## 关联关系
- 多对1关联RagEvalTestSet
- 多对1关联RagEvalTestReport
