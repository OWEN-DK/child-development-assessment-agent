# 08 - RagEvalConfigVersion 模型定义 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 08 - RagEvalConfigVersion 模型定义

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
配置版本模型，用于管理RAG系统所有配置的版本历史，支持配置的回滚、对比和测试复现。

## 实施文件
`backend/src/models/rag_eval/config_version.py`

## SQLAlchemy 模型定义
```python
import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, Integer, JSON, ForeignKey, func, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.core.database import Base


class RagEvalConfigVersion(Base):
    __tablename__ = "rag_eval_config_versions"
    __table_args__ = (
        Index("idx_rag_eval_config_version_created_at", "created_at"),
        {"comment": "RAG配置版本表"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    version_number: Mapped[int] = mapped_column(Integer, nullable=False, comment="自增序号，系统自动维护")
    version_label: Mapped[str] = mapped_column(String(32), nullable=False, comment="展示用语义版本号，如 v2.3")
    config_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, comment="完整配置快照")

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    created_by: Mapped[str | None] = mapped_column(String(36), comment="创建人用户ID")
    change_summary: Mapped[str | None] = mapped_column(Text, comment="变更摘要")

    test_runs: Mapped[list["RagEvalTestRun"]] = relationship(back_populates="config_version")
    change_sets: Mapped[list["RagEvalConfigChangeSet"]] = relationship(back_populates="config_version")
    reports: Mapped[list["RagEvalTestReport"]] = relationship(back_populates="config_version")
```

## 字段说明
| 字段名 | 类型 | 可空 | 说明 |
|--------|------|------|------|
| id | String(36) | 否 | 主键UUID |
| version_number | INT | 否 | 自增序号，系统自动维护 |
| version_label | VARCHAR(32) | 否 | 展示用语义版本号，如 "v2.3" |
| config_snapshot | JSON | 否 | 完整配置快照，包含所有RAG参数 |
| created_at | DATETIME | 否 | 创建时间 |
| created_by | String(36) | 是 | 创建人用户ID |
| change_summary | TEXT | 是 | 变更摘要 |

## 业务规则
- 不将参数拆为独立列，避免新增参数时 ALTER TABLE
- version_label 生成规则：查询最大 version_number N，新标签为 "v{N+1}.0"；小修订时递增小数位（version_number 不变）
- version_label 是配置版本号（用于展示和趋势图）；change_set_label 是变更集编号（用于审计追踪），两者用途不同
- version_number 是数字排序字段，解决 version_label 字符串排序不准确的问题

## 关联关系
- 1对多关联RagEvalTestRun
- 1对多关联RagEvalConfigChangeSet
- 1对多关联RagEvalTestReport
