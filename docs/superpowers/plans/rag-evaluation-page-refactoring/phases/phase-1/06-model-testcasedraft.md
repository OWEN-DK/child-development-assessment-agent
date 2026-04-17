# 06 - RagEvalTestCaseDraft 模型定义 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 06 - RagEvalTestCaseDraft 模型定义

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
测试用例草稿模型，用于存储书籍导入后生成的待审核用例。

## 实施文件
`backend/src/models/rag_eval/test_case_draft.py`

## SQLAlchemy 模型定义
```python
import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, Integer, JSON, ForeignKey, func, Index, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.core.database import Base
from src.models.rag_eval.enums import RagEvalTestCaseDraftStatus
from src.models.test_case import TestDomain


class RagEvalTestCaseDraft(Base):
    __tablename__ = "rag_eval_test_case_drafts"
    __table_args__ = (
        Index("idx_rag_eval_test_case_draft_doc_status", "source_document_id", "status"),
        {"comment": "测试用例草稿表"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    source_document_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        comment="源文档ID（弱引用，无外键约束）",
    )

    query: Mapped[str] = mapped_column(Text, nullable=False)
    age_months: Mapped[int | None] = mapped_column(Integer)
    domain: Mapped[TestDomain] = mapped_column(
        SAEnum(TestDomain, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
    )
    expected_key_points: Mapped[list] = mapped_column(JSON, default=list, comment="期望知识点列表")

    status: Mapped[RagEvalTestCaseDraftStatus] = mapped_column(
        SAEnum(RagEvalTestCaseDraftStatus, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=RagEvalTestCaseDraftStatus.DRAFT,
    )
    reviewed_by: Mapped[str | None] = mapped_column(String(36), comment="审核人ID")
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    source_document: Mapped["SourceDocument"] = relationship(foreign_keys=[source_document_id])
    imported_test_cases: Mapped[list["RagEvalTestCase"]] = relationship(back_populates="source_draft")
```

## 字段说明
| 字段名 | 类型 | 可空 | 说明 |
|--------|------|------|------|
| id | String(36) | 否 | 主键UUID |
| source_document_id | String(36) | 否 | 源文档ID（弱引用，无外键约束） |
| query | TEXT | 否 | 测试查询内容 |
| age_months | INT | 是 | 适用儿童月龄 |
| domain | VARCHAR(128) | 否 | 所属发展领域 |
| expected_key_points | JSON | 否 | 期望知识点列表 |
| status | VARCHAR(64) | 否 | DRAFT、REVIEWED、REJECTED、IMPORTED |
| reviewed_by | String(36) | 是 | 审核人ID |
| reviewed_at | DATETIME | 是 | 审核时间 |
| created_at | DATETIME | 否 | 创建时间 |

## 级联规则
- Document 删除时，应用层删除关联的草稿

## 状态机
```
┌───────┐   通过    ┌─────────┐   归入    ┌─────────┐
│ draft ├──────────►│ reviewed├──────────►│ imported│
└───┬───┘           └─────────┘           └─────────┘
    │ 拒绝               │ 取消归入
    ▼                    ▼
┌──────────┐        ┌───────┐
│ rejected │        │ draft │ (重新编辑后)
└──────────┘        └───────┘
```

## 关联关系
- 多对1关联SourceDocument
- 1对多关联RagEvalTestCase（审核通过后生成的正式用例）

## 注意事项
- `imported` 后，TestCaseDraft 保留作为历史记录，TestCase 为独立副本，两者数据解耦
