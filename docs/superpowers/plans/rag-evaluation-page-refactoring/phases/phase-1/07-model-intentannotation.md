# 07 - RagEvalIntentAnnotation 模型定义 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 07 - RagEvalIntentAnnotation 模型定义

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
意图标注模型，用于存储测试用例的用户意图人工标注记录，是 Layer 5b 意图识别准确率校验的数据来源。

## 实施文件
`backend/src/models/rag_eval/intent_annotation.py`

## SQLAlchemy 模型定义
```python
import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, func, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.core.database import Base


class RagEvalIntentAnnotation(Base):
    __tablename__ = "rag_eval_intent_annotations"
    __table_args__ = (
        Index("uk_rag_eval_intent_annotation_case", "case_id", unique=True),
        {"comment": "测试用例意图标注表"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    case_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("rag_eval_test_cases.id", ondelete="CASCADE"),
        nullable=False,
    )

    intent_type: Mapped[str] = mapped_column(String(36), nullable=False, comment="如: factual_query, how_to, comparison, definition")
    annotated_by: Mapped[str | None] = mapped_column(String(36), comment="标注人ID")
    annotated_at: Mapped[datetime | None] = mapped_column(DateTime)

    test_case: Mapped["RagEvalTestCase"] = relationship(back_populates="intent_annotations")
```

## 字段说明
| 字段名 | 类型 | 可空 | 说明 |
|--------|------|------|------|
| id | String(36) | 否 | 主键UUID |
| case_id | String(36) | 否 | 关联的测试用例ID，FK→rag_eval_test_cases.id |
| intent_type | VARCHAR(64) | 否 | 标注的意图类型 |
| annotated_by | String(36) | 是 | 标注人ID |
| annotated_at | DATETIME | 是 | 标注时间 |

## 约束说明
- 唯一约束：每个用例最多一条人工标注

## 关联关系
- 多对1关联RagEvalTestCase
