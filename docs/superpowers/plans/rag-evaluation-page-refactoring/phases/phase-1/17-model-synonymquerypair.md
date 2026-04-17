# 17 - RagEvalSynonymQueryPair 模型定义 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 17 - RagEvalSynonymQueryPair 模型定义

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
同义查询对模型，是 Layer 5a Embedding 质量校验的数据来源。

## 实施文件
`backend/src/models/rag_eval/synonym_query_pair.py`

## SQLAlchemy 模型定义
```python
import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, Boolean, ForeignKey, func, Index, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.core.database import Base
from src.models.rag_eval.enums import RagEvalSynonymSource


class RagEvalSynonymQueryPair(Base):
    __tablename__ = "rag_eval_synonym_query_pairs"
    __table_args__ = (
        Index("idx_rag_eval_synonym_domain_active", "domain", "active"),
        {"comment": "同义查询对表"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    query_a: Mapped[str] = mapped_column(Text, nullable=False)
    query_b: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str] = mapped_column(String(36), nullable=False, comment="发展领域")

    created_by: Mapped[str | None] = mapped_column(String(36), comment="创建者")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    source: Mapped[RagEvalSynonymSource] = mapped_column(
        SAEnum(RagEvalSynonymSource, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")
```

## 字段说明
| 字段名 | 类型 | 可空 | 说明 |
|--------|------|------|------|
| id | String(36) | 否 | 主键UUID |
| query_a | TEXT | 否 | 查询A |
| query_b | TEXT | 否 | 查询B |
| domain | VARCHAR(64) | 否 | 发展领域 |
| created_by | String(36) | 是 | 创建者 |
| created_at | DATETIME | 否 | 创建时间 |
| source | VARCHAR(64) | 否 | BUILTIN、AUTO_EXTRACTED、MANUAL |
| active | BOOLEAN | 否 | 是否启用 |

## 用途
- Layer 5a 读取此表获取同义查询对，计算 embedding 余弦相似度
