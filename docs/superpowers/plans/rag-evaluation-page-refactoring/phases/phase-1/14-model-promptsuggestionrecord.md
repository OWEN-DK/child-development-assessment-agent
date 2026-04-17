# 14 - RagEvalPromptSuggestionRecord 模型定义 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 14 - RagEvalPromptSuggestionRecord 模型定义

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
提示词优化建议模型，仅存储提示词内容修改建议。

## 实施文件
`backend/src/models/rag_eval/prompt_suggestion.py`

## SQLAlchemy 模型定义
```python
import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, JSON, Boolean, ForeignKey, func, Index, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.core.database import Base
from src.models.rag_eval.enums import RagEvalPromptSuggestionType


class RagEvalPromptSuggestionRecord(Base):
    __tablename__ = "rag_eval_prompt_suggestion_records"
    __table_args__ = (
        Index("idx_rag_eval_prompt_suggestion_report_applied", "report_id", "applied"),
        {"comment": "提示词调优建议记录表"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    report_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        comment="测试报告ID（弱引用，无外键约束）",
    )
    prompt_key: Mapped[str] = mapped_column(String(128), nullable=False)
    current_version_id: Mapped[str | None] = mapped_column(
        String(36),
        comment="当前提示词版本ID（弱引用，无外键约束）",
    )
    suggested_version_id: Mapped[str | None] = mapped_column(
        String(36),
        comment="建议的提示词版本ID（弱引用，无外键约束）",
    )

    reason: Mapped[str | None] = mapped_column(Text)
    expected_effect: Mapped[str | None] = mapped_column(String(255))
    priority: Mapped[str | None] = mapped_column(String(32))
    source: Mapped[str | None] = mapped_column(String(36))
    suggestion_type: Mapped[RagEvalPromptSuggestionType | None] = mapped_column(
        SAEnum(RagEvalPromptSuggestionType, values_callable=lambda obj: [e.value for e in obj]),
    )
    applied: Mapped[bool] = mapped_column(Boolean, default=False)
    applied_version_id: Mapped[str | None] = mapped_column(
        String(36),
        comment="采纳后的提示词版本ID（弱引用，无外键约束）",
    )

    report: Mapped["RagEvalTestReport"] = relationship(back_populates="prompt_suggestions")
    current_prompt_version: Mapped["RagEvalPromptVersion | None"] = relationship(foreign_keys=[current_version_id])
    suggested_prompt_version: Mapped["RagEvalPromptVersion | None"] = relationship(foreign_keys=[suggested_version_id])
    applied_prompt_version: Mapped["RagEvalPromptVersion | None"] = relationship(foreign_keys=[applied_version_id])
```

## 字段说明
| 字段名 | 类型 | 可空 | 说明 |
|--------|------|------|------|
| id | String(36) | 否 | 主键UUID |
| report_id | String(36) | 否 | 测试报告ID（弱引用，无外键约束） |
| prompt_key | VARCHAR(128) | 否 | 提示词key |
| current_version_id | String(36) | 是 | 当前提示词版本ID（弱引用） |
| suggested_version_id | String(36) | 是 | 建议的提示词版本ID（弱引用） |
| reason | TEXT | 是 | 调优理由 |
| expected_effect | VARCHAR(255) | 是 | 预期效果 |
| priority | VARCHAR(32) | 是 | 优先级 |
| source | VARCHAR(64) | 是 | 来源 |
| suggestion_type | VARCHAR(64) | 是 | ADD_CONSTRAINT、REWRITE、PARAMETER_TWEAK |
| applied | BOOLEAN | 否 | 是否已采纳 |
| applied_version_id | String(36) | 是 | 采纳后的提示词版本ID（弱引用） |

## 注意事项
- 忽略状态由独立表 IgnoredSuggestion 管理，不在此表存储
- 本表仅存储提示词优化建议，与 TuningSuggestionRecord 职责分离

## 关联关系
- 多对1关联RagEvalTestReport
- 多对1关联RagEvalPromptVersion（当前版本）
- 多对1关联RagEvalPromptVersion（建议版本）
- 多对1关联RagEvalPromptVersion（采纳版本）
