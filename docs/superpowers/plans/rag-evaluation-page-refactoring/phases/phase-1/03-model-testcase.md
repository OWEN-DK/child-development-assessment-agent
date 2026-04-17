# 03 - RagEvalTestCase 模型定义 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 03 - RagEvalTestCase 模型定义

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
测试用例模型，定义RAG检索效果评估的最小测试单元。

## 实施文件
`backend/src/models/rag_eval/test_case.py`

## SQLAlchemy 模型定义
```python
import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, Integer, JSON, ForeignKey, func, Index, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.core.database import Base
from src.models.test_case import TestDomain


class RagEvalTestCase(Base):
    __tablename__ = "rag_eval_test_cases"
    __table_args__ = (
        Index("idx_rag_eval_test_case_domain_age", "domain", "age_months"),
        {"comment": "RAG评估测试用例表"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    query: Mapped[str] = mapped_column(Text, nullable=False)
    age_months: Mapped[int | None] = mapped_column(Integer)
    domain: Mapped[TestDomain] = mapped_column(
        SAEnum(TestDomain, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
    )

    expected_document_ids: Mapped[list] = mapped_column(JSON, default=list, comment="期望命中的文档ID列表")
    expected_key_points: Mapped[list] = mapped_column(JSON, default=list, comment="期望知识点列表")

    source_draft_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("rag_eval_test_case_drafts.id", ondelete="SET NULL"),
        comment="来源草稿ID",
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    test_sets: Mapped[list["RagEvalTestSetCase"]] = relationship(back_populates="test_case", cascade="all, delete-orphan")
    run_results: Mapped[list["RagEvalTestRunResult"]] = relationship(back_populates="test_case", cascade="all, delete-orphan")
    intent_annotations: Mapped[list["RagEvalIntentAnnotation"]] = relationship(back_populates="test_case", cascade="all, delete-orphan")
    source_draft: Mapped["RagEvalTestCaseDraft | None"] = relationship(back_populates="imported_test_cases")
```

## 字段说明
| 字段名 | 类型 | 可空 | 说明 |
|--------|------|------|------|
| id | String(36) | 否 | 主键UUID |
| query | TEXT | 否 | 测试查询内容 |
| age_months | INT | 是 | 适用儿童月龄（整数）。注：现有 TestCase 模型使用 age DECIMAL(4,1)，新模型简化为 INT，因测试用例场景不需要小数月龄精度。如需兼容现有数据，转换公式：age_months = ROUND(age) |
| domain | VARCHAR(128) | 否 | 所属发展领域 |
| expected_document_ids | JSON | 否 | Golden Dataset：期望命中的文档ID列表 |
| expected_key_points | JSON | 否 | 期望知识点列表 |
| source_draft_id | String(36) | 是 | 来源草稿ID，FK→rag_eval_test_case_drafts.id |
| created_at | DATETIME | 否 | 创建时间 |

## 关联关系
- 多对多关联RagEvalTestSet（通过RagEvalTestSetCase中间表）
- 1对多关联RagEvalTestRunResult
- 1对多关联RagEvalIntentAnnotation
- 多对1关联RagEvalTestCaseDraft（来源草稿）

## 注意事项
- 不再包含 test_set_id，用例通过 TestSetCase 中间表与测试集关联
