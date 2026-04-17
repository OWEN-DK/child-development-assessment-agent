# 02 - RagEvalTestSetCase 模型定义 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 02 - RagEvalTestSetCase 模型定义

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
测试集与测试用例的关联中间表，用于管理测试集包含的测试用例列表，支持用例被多个测试集复用。

## 实施文件
`backend/src/models/rag_eval/test_set_case.py`

## SQLAlchemy 模型定义
```python
import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, func, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.core.database import Base


class RagEvalTestSetCase(Base):
    __tablename__ = "rag_eval_test_set_cases"
    __table_args__ = (
        Index("idx_rag_eval_test_set_case_test_set", "test_set_id"),
        Index("idx_rag_eval_test_set_case_case", "case_id"),
        Index("uk_rag_eval_test_set_case", "test_set_id", "case_id", unique=True),
        {"comment": "测试集-测试用例关联表"},
    )

    # 主键
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # 关联字段
    test_set_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("rag_eval_test_sets.id", ondelete="CASCADE"),
        nullable=False,
    )
    case_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("rag_eval_test_cases.id", ondelete="CASCADE"),
        nullable=False,
    )

    # 元数据
    added_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    added_by: Mapped[str | None] = mapped_column(String(36), comment="添加用例的用户ID")

    # 关联关系
    test_set: Mapped["RagEvalTestSet"] = relationship(back_populates="test_cases")
    test_case: Mapped["RagEvalTestCase"] = relationship(back_populates="test_sets")
```

## 字段说明
| 字段名 | 类型 | 可空 | 说明 |
|--------|------|------|------|
| id | String(36) | 否 | 主键UUID |
| test_set_id | String(36) | 否 | 测试集ID，FK→rag_eval_test_sets.id，级联删除 |
| case_id | String(36) | 否 | 测试用例ID，FK→rag_eval_test_cases.id，级联删除 |
| added_at | DATETIME | 否 | 用例添加到测试集的时间 |
| added_by | String(36) | 是 | 添加用例的用户ID |

## 约束说明
- 唯一约束 `uk_rag_eval_test_set_case`：保证同一个测试集中不会重复添加同一个测试用例
- 级联删除：测试集删除时自动删除关联记录，测试用例删除时自动删除关联记录

## 关联关系
- 多对1关联RagEvalTestSet
- 多对1关联RagEvalTestCase
