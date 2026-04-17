# 09 - RagEvalPromptVersion 模型定义 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 09 - RagEvalPromptVersion 模型定义

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
提示词版本模型，用于管理所有LLM提示词的版本历史，支持提示词的回滚、对比、测试和热重载。

## 实施文件
`backend/src/models/rag_eval/prompt_version.py`

## SQLAlchemy 模型定义
```python
import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, Integer, JSON, ForeignKey, func, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.core.database import Base


class RagEvalPromptVersion(Base):
    __tablename__ = "rag_eval_prompt_versions"
    __table_args__ = (
        Index("idx_rag_eval_prompt_key_version", "prompt_key", "version_label", unique=True),
        Index("idx_rag_eval_prompt_key_created", "prompt_key", "created_at"),
        {"comment": "提示词版本表"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    prompt_key: Mapped[str] = mapped_column(String(255), nullable=False, comment="如 query_rewrite, query_routing")
    version_label: Mapped[str] = mapped_column(String(36), nullable=False, comment="展示用版本号，如 v3, v4-new-constraint")
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, comment="该prompt_key下的自增序号，仅用于排序")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="提示词完整内容")
    variables_extracted: Mapped[list | None] = mapped_column(JSON, comment="自动从content中提取的变量列表")
    change_impact: Mapped[dict | None] = mapped_column(JSON, comment="变更影响分析")

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    created_by: Mapped[str | None] = mapped_column(String(36), comment="创建人用户ID")
    change_summary: Mapped[str | None] = mapped_column(Text, comment="变更摘要")

    change_set_prompts: Mapped[list["RagEvalConfigChangeSetPrompt"]] = relationship(back_populates="prompt_version")
    prompt_suggestions_current: Mapped[list["RagEvalPromptSuggestionRecord"]] = relationship(
        back_populates="current_prompt_version",
        foreign_keys="RagEvalPromptSuggestionRecord.current_version_id",
        primaryjoin="RagEvalPromptVersion.id==RagEvalPromptSuggestionRecord.current_version_id",
    )
    prompt_suggestions_suggested: Mapped[list["RagEvalPromptSuggestionRecord"]] = relationship(
        back_populates="suggested_prompt_version",
        foreign_keys="RagEvalPromptSuggestionRecord.suggested_version_id",
        primaryjoin="RagEvalPromptVersion.id==RagEvalPromptSuggestionRecord.suggested_version_id",
    )
```

## 字段说明
| 字段名 | 类型 | 可空 | 说明 |
|--------|------|------|------|
| id | String(36) | 否 | 主键UUID |
| prompt_key | VARCHAR(255) | 否 | 提示词唯一标识key |
| version_label | VARCHAR(64) | 否 | 展示用版本号 |
| version_number | INT | 否 | 自增序号，仅用于排序 |
| content | TEXT | 否 | 提示词完整内容 |
| variables_extracted | JSON | 是 | 自动提取的变量列表 |
| change_impact | JSON | 是 | 变更影响分析 |
| created_at | DATETIME | 否 | 创建时间 |
| created_by | String(36) | 是 | 创建人用户ID |
| change_summary | TEXT | 是 | 变更摘要 |

## 约束说明
- 唯一索引：UNIQUE(prompt_key, version_label)

## 业务规则
- version_number 生成：SELECT COALESCE(MAX(version_number), 0) + 1 WHERE prompt_key = ? FOR UPDATE（行锁保证并发安全）
- variables_extracted：保存时自动从 content 中提取
- change_impact：保存时自动计算，格式：{"variables_added": [], "variables_removed": [], "config_dependencies_changed": false, "affected_code_files": []}

## 关联关系
- 1对多关联RagEvalConfigChangeSetPrompt
- 1对多关联RagEvalPromptSuggestionRecord（当前版本）
- 1对多关联RagEvalPromptSuggestionRecord（建议版本）
