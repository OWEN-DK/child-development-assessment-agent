# 13 - RagEvalTuningSuggestionRecord 模型定义 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 13 - RagEvalTuningSuggestionRecord 模型定义

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
调优建议记录模型，仅存储配置参数调优建议（如 bm25_top_k, fusion_threshold 等）。

## 实施文件
`backend/src/models/rag_eval/tuning_suggestion.py`

## SQLAlchemy 模型定义
```python
import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, JSON, Boolean, Float, ForeignKey, func, Index, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.core.database import Base
from src.models.rag_eval.enums import RagEvalSuggestionSource


class RagEvalTuningSuggestionRecord(Base):
    __tablename__ = "rag_eval_tuning_suggestion_records"
    __table_args__ = (
        Index("idx_rag_eval_tuning_suggestion_report_applied", "report_id", "applied"),
        {"comment": "参数调优建议记录表"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    report_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("rag_eval_test_reports.id", ondelete="CASCADE"),
        nullable=False,
    )

    param_name: Mapped[str] = mapped_column(String(128), nullable=False)
    current_value: Mapped[dict | None] = mapped_column(JSON)
    suggested_value: Mapped[dict | None] = mapped_column(JSON)
    action: Mapped[str | None] = mapped_column(String(36))
    reason: Mapped[str | None] = mapped_column(Text)
    expected_effect: Mapped[dict | None] = mapped_column(JSON, comment="预期效果")
    priority: Mapped[str | None] = mapped_column(String(32))
    source: Mapped[RagEvalSuggestionSource | None] = mapped_column(
        SAEnum(RagEvalSuggestionSource, values_callable=lambda obj: [e.value for e in obj]),
    )
    safe_range: Mapped[dict | None] = mapped_column(JSON, comment="安全范围")
    applied: Mapped[bool] = mapped_column(Boolean, default=False)
    applied_config_version_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("rag_eval_config_versions.id", ondelete="SET NULL"),
        comment="采纳后应用到的配置版本ID",
    )

    report: Mapped["RagEvalTestReport"] = relationship(back_populates="tuning_suggestions")
    applied_config_version: Mapped["RagEvalConfigVersion | None"] = relationship()
```

## 字段说明
| 字段名 | 类型 | 可空 | 说明 |
|--------|------|------|------|
| id | String(36) | 否 | 主键UUID |
| report_id | String(36) | 否 | 测试报告ID，FK→rag_eval_test_reports.id |
| param_name | VARCHAR(128) | 否 | 参数名称 |
| current_value | JSON | 是 | 当前参数值 |
| suggested_value | JSON | 是 | 建议参数值 |
| action | VARCHAR(64) | 是 | 建议动作 |
| reason | TEXT | 是 | 调优理由 |
| expected_effect | JSON | 是 | 预期效果 |
| priority | VARCHAR(32) | 是 | 优先级 |
| source | VARCHAR(64) | 是 | 来源：RULE_ENGINE、HISTORY、LLM |
| safe_range | JSON | 是 | 安全范围 |
| applied | BOOLEAN | 否 | 是否已采纳 |
| applied_config_version_id | String(36) | 是 | 采纳后应用到的配置版本ID |

## 注意事项
- 忽略状态由独立表 IgnoredSuggestion 管理，不在此表存储
- 本表仅存储配置参数调优建议

## 关联关系
- 多对1关联RagEvalTestReport
- 多对1关联RagEvalConfigVersion
