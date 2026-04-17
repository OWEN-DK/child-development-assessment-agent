# 01 - PromptMetadata 模型 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 01 - PromptMetadata 模型

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

> **Phase**: 7
> **需求点**: 1
> **需求来源**: spec `07a-prompt-data-model.md` §2.1

## 目标

新增提示词元数据表，包含中文字段和变量声明。

## 方案设计

### 数据模型定义

```python
# backend/src/models/rag_eval/prompt_metadata.py

import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, Boolean, JSON, Enum as SAEnum, func, Index
from sqlalchemy.orm import Mapped, mapped_column
from src.core.database import Base
from src.models.rag_eval.enums import RagEvalPromptCategory


class RagEvalPromptMetadata(Base):
    """提示词元数据 - 提示词级别的静态信息（一个 prompt_key 只有一份）"""
    __tablename__ = "rag_eval_prompt_metadata"
    __table_args__ = (
        Index("idx_rag_eval_prompt_key", "prompt_key", unique=True),
        Index("idx_rag_eval_prompt_category_active", "category", "is_active"),
        {"comment": "RAG评估提示词元数据表"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    prompt_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    name_zh: Mapped[str] = mapped_column(String(255), nullable=False)
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[RagEvalPromptCategory] = mapped_column(
        SAEnum(RagEvalPromptCategory, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
    )
    subcategory: Mapped[str | None] = mapped_column(String(64))
    variables_schema: Mapped[dict | None] = mapped_column(JSON)
    code_references: Mapped[dict | None] = mapped_column(JSON)
    config_dependencies: Mapped[dict | None] = mapped_column(JSON)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[str | None] = mapped_column(String(64))
    updated_by: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
```

### 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | String(36) | 是 | 主键，UUID |
| prompt_key | VARCHAR(255) | 是 | 唯一标识，唯一索引 |
| name_zh | VARCHAR(255) | 是 | 中文名称 |
| purpose | TEXT | 是 | 用途说明 |
| category | VARCHAR(64) | 是 | 分类：rag_retrieval/rag_generation/assessment/scoring/reporting/test_case_generation |
| subcategory | VARCHAR(64) | 否 | 子分类 |
| variables_schema | JSON | 否 | 变量声明 schema |
| code_references | JSON | 否 | 代码引用位置 |
| config_dependencies | JSON | 否 | 配置参数依赖 |
| is_active | BOOLEAN | 是 | 是否启用 |
| is_system | BOOLEAN | 是 | 是否系统内置（系统内置不可删除） |

### variables_schema 格式

```json
{
  "query": {"type": "string", "required": true, "description": "用户原始查询"},
  "age": {"type": "number", "required": true, "description": "儿童年龄", "default": 0}
}
```

### code_references 格式

```json
[
  {"file": "src/service/retrieval_service.py", "line": 868, "function": "rewrite_query"}
]
```

### config_dependencies 格式

```json
[
  {"param": "rag_similarity_threshold", "category": "rag.retrieval", "description": "相似度阈值"}
]
```

### 初始化数据

系统初始化时必须为所有现有提示词创建元数据记录：

| prompt_key | name_zh | purpose | category |
|-----------|---------|---------|----------|
| `rag_query_rewrite` | 查询重写提示词 | 将用户原始查询重写为更适合知识库检索的形式 | rag_retrieval |
| `synonym_expansion` | 同义词扩展提示词 | 为查询词生成同义词/相关词列表，提升检索召回率 | rag_retrieval |
| `metadata_extraction` | 元数据提取提示词 | 从文档块中提取结构化元数据（主题、年龄、类型等） | rag_retrieval |
| `test_case_generation` | 测试用例生成提示词 | 根据文档内容自动生成 RAG 测试用例草稿 | test_case_generation |
| `validation` | 数据校验提示词 | 校验用户输入的儿童画像和拟定计划是否完整合理 | assessment |
| `intensity_inference` | 强度等级推断提示词 | 根据运动名称推断强度等级（low/medium/high） | assessment |
| `category_inference` | 类别推断提示词 | 根据运动名称推断类别（前庭觉/本体觉/触觉等） | assessment |
| `assessment_system` | 评估系统提示词 | 根据儿童画像进行多维度感统能力评估 | assessment |
| `scoring` | 评分提示词 | 对拟定的训练计划进行多维度打分 | scoring |
| `report_generation` | 报告生成提示词 | 生成专业、详细的儿童运动发展评估报告 | reporting |

### 验收标准

- [ ] `rag_eval_prompt_metadata` 表创建成功
- [ ] 主键为 String(36) UUID
- [ ] prompt_key 唯一索引
- [ ] 使用 Mapped/mapped_column 风格（与 Phase 1 模型一致）
- [ ] Enum 使用 values_callable 显式传递
- [ ] 所有现有提示词都有元数据记录
- [ ] variables_schema 格式正确
