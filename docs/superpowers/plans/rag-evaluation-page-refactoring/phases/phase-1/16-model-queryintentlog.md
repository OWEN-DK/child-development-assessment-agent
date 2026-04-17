# 16 - RagEvalQueryIntentLog 模型定义 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 16 - RagEvalQueryIntentLog 模型定义

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
查询意图自动分类日志模型，是 Layer 5b 意图识别的数据来源。

## 实施文件
`backend/src/models/rag_eval/query_intent_log.py`

## SQLAlchemy 模型定义
```python
import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, Float, ForeignKey, func, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.core.database import Base


class RagEvalQueryIntentLog(Base):
    __tablename__ = "rag_eval_query_intent_logs"
    __table_args__ = (
        Index("idx_rag_eval_query_intent_log_run", "run_id"),
        Index("idx_rag_eval_query_intent_log_case", "case_id"),
        {"comment": "查询意图自动分类日志表"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("rag_eval_test_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    case_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("rag_eval_test_cases.id", ondelete="CASCADE"),
    )

    query: Mapped[str] = mapped_column(Text, nullable=False)
    predicted_intent: Mapped[str] = mapped_column(String(36), nullable=False, comment="LLM自动分类的意图")
    confidence: Mapped[float | None] = mapped_column(Float, comment="置信度(0.0-1.0)")

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    test_run: Mapped["RagEvalTestRun"] = relationship(back_populates="intent_logs")
    test_case: Mapped["RagEvalTestCase | None"] = relationship()
```

## 字段说明
| 字段名 | 类型 | 可空 | 说明 |
|--------|------|------|------|
| id | String(36) | 否 | 主键UUID |
| run_id | String(36) | 否 | 测试运行ID，FK→rag_eval_test_runs.id |
| case_id | String(36) | 是 | 测试用例ID，FK→rag_eval_test_cases.id |
| query | TEXT | 否 | 查询文本 |
| predicted_intent | VARCHAR(64) | 否 | LLM自动分类的意图 |
| confidence | FLOAT | 是 | 置信度(0.0-1.0) |
| created_at | DATETIME | 否 | 创建时间 |

## 用途
- Layer 5b 读取此表获取"查询分析结果"，与 IntentAnnotation 对比计算准确率

## 关联关系
- 多对1关联RagEvalTestRun
- 多对1关联RagEvalTestCase
