# 10 - RagEvalConfigChangeSet 模型定义 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 10 - RagEvalConfigChangeSet 模型定义

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
配置变更集模型，用于原子保存配置+提示词的整体版本。

## 实施文件
`backend/src/models/rag_eval/config_change_set.py`

## SQLAlchemy 模型定义
```python
import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, JSON, ForeignKey, func, Index, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.core.database import Base
from src.models.rag_eval.enums import RagEvalChangeSetStatus


class RagEvalConfigChangeSet(Base):
    __tablename__ = "rag_eval_config_change_sets"
    __table_args__ = (
        Index("idx_rag_eval_config_change_set_status", "status"),
        Index("idx_rag_eval_config_change_set_config_version", "config_version_id"),
        {"comment": "配置变更集表"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    change_set_label: Mapped[str] = mapped_column(String(32), nullable=False, comment="展示用标签，格式 CS-20260416-001")
    config_version_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("rag_eval_config_versions.id", ondelete="SET NULL"),
        comment="发布后生成的配置版本ID",
    )

    status: Mapped[RagEvalChangeSetStatus] = mapped_column(
        SAEnum(RagEvalChangeSetStatus, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=RagEvalChangeSetStatus.COMMITTED,
    )
    rollback_reason: Mapped[str | None] = mapped_column(String(500), comment="回滚原因")

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    config_version: Mapped["RagEvalConfigVersion | None"] = relationship(back_populates="change_sets")
    prompt_changes: Mapped[list["RagEvalConfigChangeSetPrompt"]] = relationship(back_populates="change_set", cascade="all, delete-orphan")
```

## 字段说明
| 字段名 | 类型 | 可空 | 说明 |
|--------|------|------|------|
| id | String(36) | 否 | 主键UUID |
| change_set_label | VARCHAR(32) | 否 | 展示用标签，格式 "CS-20260416-001" |
| config_version_id | String(36) | 是 | 发布后生成的配置版本ID |
| status | VARCHAR(64) | 否 | COMMITTED、ROLLED_BACK |
| rollback_reason | VARCHAR(500) | 是 | 回滚原因 |
| created_at | DATETIME | 否 | 创建时间 |

## 业务规则
- prompt_version_ids 不再存为 JSON 数组，改用 ConfigChangeSetPrompt 关联表
- change_set_label 是变更集编号（审计用），version_label 是配置版本号（展示用），两者独立编号

## 关联关系
- 多对1关联RagEvalConfigVersion
- 1对多关联RagEvalConfigChangeSetPrompt
