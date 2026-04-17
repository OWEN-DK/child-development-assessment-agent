# 01 - RagEvalTestSet 模型定义 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 01 - RagEvalTestSet 模型定义

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
测试集模型，用于管理一组相关的测试用例，是RAG评估的核心业务单元。

## 实施文件
`backend/src/models/rag_eval/test_set.py`

## SQLAlchemy 模型定义
```python
import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, ForeignKey, func, Index, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.core.database import Base
from src.models.rag_eval.enums import RagEvalTestSetSourceType


class RagEvalTestSet(Base):
    __tablename__ = "rag_eval_test_sets"
    __table_args__ = (
        Index("idx_rag_eval_test_set_created_at", "created_at"),
        {"comment": "RAG评估测试集表"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    source_type: Mapped[RagEvalTestSetSourceType] = mapped_column(
        SAEnum(RagEvalTestSetSourceType, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
    )
    source_document_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        comment="关联的源文档ID（弱引用，无外键约束）",
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    source_document: Mapped["SourceDocument | None"] = relationship(foreign_keys=[source_document_id])
    test_cases: Mapped[list["RagEvalTestSetCase"]] = relationship(back_populates="test_set", cascade="all, delete-orphan")
    test_runs: Mapped[list["RagEvalTestRun"]] = relationship(back_populates="test_set", cascade="all, delete-orphan")
    reports: Mapped[list["RagEvalTestReport"]] = relationship(back_populates="test_set", cascade="all, delete-orphan")
    ignored_suggestions: Mapped[list["RagEvalIgnoredSuggestion"]] = relationship(back_populates="test_set", cascade="all, delete-orphan")
```

## 字段说明
| 字段名 | 类型 | 可空 | 说明 |
|--------|------|------|------|
| id | String(36) | 否 | 主键UUID |
| name | VARCHAR(255) | 否 | 测试集名称 |
| description | TEXT | 是 | 测试集描述 |
| source_type | VARCHAR(64) | 否 | 来源类型：BOOK_GENERATED、JSON_IMPORTED、MANUAL |
| source_document_id | String(36) | 是 | 关联的源文档ID（弱引用，无外键约束） |
| created_at | DATETIME | 否 | 创建时间 |
| updated_at | DATETIME | 否 | 更新时间 |

## 级联规则
- TestSetCase: 应用层级联删除
- TestCase: 不级联（用例可能被其他测试集复用，仅删除关联关系）
- TestRun: 应用层联删除
- TestReport: 随 TestRun 应用层删除
- TestCaseDraft: 应用层删除（通过 source_document_id 关联）
- IgnoredSuggestion: 应用层删除

**注意**：所有级联删除均由应用层逻辑处理，不使用数据库外键约束。

## 关联关系
- 1对多关联RagEvalTestSetCase
- 1对多关联RagEvalTestRun
- 1对多关联RagEvalTestReport
- 1对多关联RagEvalIgnoredSuggestion
- 多对1关联SourceDocument

## 注意事项
- `total_cases` 通过 COUNT(test_set_cases) 实时计算，不存储冗余字段
