# 11 - RagEvalConfigChangeSetPrompt 模型定义 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 11 - RagEvalConfigChangeSetPrompt 模型定义

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
配置变更集与提示词版本的关联中间表。

## 实施文件
`backend/src/models/rag_eval/config_change_set_prompt.py`

## SQLAlchemy 模型定义
```python
import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, func, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.core.database import Base


class RagEvalConfigChangeSetPrompt(Base):
    __tablename__ = "rag_eval_config_change_set_prompts"
    __table_args__ = (
        Index("uk_rag_eval_change_set_prompt", "change_set_id", "prompt_version_id", unique=True),
        Index("idx_rag_eval_change_set_prompt_version", "prompt_version_id"),
        {"comment": "变更集-提示词版本关联表"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    change_set_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("rag_eval_config_change_sets.id", ondelete="CASCADE"),
        nullable=False,
    )
    prompt_version_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("rag_eval_prompt_versions.id", ondelete="CASCADE"),
        nullable=False,
    )

    change_set: Mapped["RagEvalConfigChangeSet"] = relationship(back_populates="prompt_changes")
    prompt_version: Mapped["RagEvalPromptVersion"] = relationship(back_populates="change_set_prompts")
```

## 字段说明
| 字段名 | 类型 | 可空 | 说明 |
|--------|------|------|------|
| id | String(36) | 否 | 主键UUID |
| change_set_id | String(36) | 否 | 变更集ID，FK→rag_eval_config_change_sets.id |
| prompt_version_id | String(36) | 否 | 提示词版本ID，FK→rag_eval_prompt_versions.id |

## 约束说明
- 唯一约束：UNIQUE(change_set_id, prompt_version_id)
- 索引：INDEX(prompt_version_id) 支持反向查询"哪些变更集包含某提示词版本"

## 关联关系
- 多对1关联RagEvalConfigChangeSet
- 多对1关联RagEvalPromptVersion
