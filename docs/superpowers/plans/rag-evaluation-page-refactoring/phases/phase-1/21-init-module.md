# 21 - RagEval Models __init__.py 导出 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 21 - RagEval Models __init__.py 导出

**Architecture:** 参考下方原文档的实现方案和数据模型

**Tech Stack:** Python, FastAPI, TypeScript, React

---

### Task 1: 实现核心逻辑与测试

**Files:**
- Create: `backend/src/models/rag_eval/__init__.py`
- Test: `backend/tests/test_placeholder.py`

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

> **需求来源**: Phase 1 数据模型创建，模块导出入口
> **所属 Phase**: Phase 1

## 需求定义

`backend/src/models/rag_eval/__init__.py` 作为模块入口，导出所有 RagEval 模型和 Enum，方便外部统一导入。

## 验收标准

- [ ] 所有 17 个模型类可通过 `from src.models.rag_eval import Xxx` 导入
- [ ] 所有 Enum 可通过 `from src.models.rag_eval import XxxEnum` 导入
- [ ] 无循环导入问题

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `backend/src/models/rag_eval/__init__.py` | 新增 | 模块导出入口 |

## 实现方案

### 后端实现

```python
# backend/src/models/rag_eval/__init__.py
"""RAG 评估数据模型模块

包含测试集、测试运行、校验报告、配置版本、提示词版本等全部 RagEval 相关模型。
所有模型使用 String(36) UUID 主键，表名统一 rag_eval_ 前缀。
"""

from src.models.rag_eval.enums import (
    RagEvalTestSetSourceType,
    RagEvalTestRunStatus,
    RagEvalTestRunResultStatus,
    RagEvalTestCaseDraftStatus,
    RagEvalTestReportStatus,
    RagEvalChangeSetStatus,
    RagEvalSuggestionSource,
    RagEvalPromptSuggestionType,
    RagEvalIgnoredSuggestionType,
    RagEvalIgnoreScope,
    RagEvalSynonymSource,
    RagEvalABTestSide,
    # Phase 4+ 新增
    RagEvalTestCaseStatus,
    RagEvalIntentType,
    RagEvalValidationStatus,
    RagEvalSuggestionType,
)

from src.models.rag_eval.test_set import RagEvalTestSet
from src.models.rag_eval.test_set_case import RagEvalTestSetCase
from src.models.rag_eval.test_case import RagEvalTestCase
from src.models.rag_eval.test_run import RagEvalTestRun
from src.models.rag_eval.test_run_result import RagEvalTestRunResult
from src.models.rag_eval.test_case_draft import RagEvalTestCaseDraft
from src.models.rag_eval.intent_annotation import RagEvalIntentAnnotation
from src.models.rag_eval.config_version import RagEvalConfigVersion
from src.models.rag_eval.prompt_version import RagEvalPromptVersion
from src.models.rag_eval.config_change_set import RagEvalConfigChangeSet
from src.models.rag_eval.config_change_set_prompt import RagEvalConfigChangeSetPrompt
from src.models.rag_eval.test_report import RagEvalTestReport
from src.models.rag_eval.tuning_suggestion import RagEvalTuningSuggestionRecord
from src.models.rag_eval.prompt_suggestion import RagEvalPromptSuggestionRecord
from src.models.rag_eval.ignored_suggestion import RagEvalIgnoredSuggestion
from src.models.rag_eval.query_intent_log import RagEvalQueryIntentLog
from src.models.rag_eval.synonym_query_pair import RagEvalSynonymQueryPair

__all__ = [
    # Enums
    "RagEvalTestSetSourceType",
    "RagEvalTestRunStatus",
    "RagEvalTestRunResultStatus",
    "RagEvalTestCaseDraftStatus",
    "RagEvalTestReportStatus",
    "RagEvalChangeSetStatus",
    "RagEvalSuggestionSource",
    "RagEvalPromptSuggestionType",
    "RagEvalIgnoredSuggestionType",
    "RagEvalIgnoreScope",
    "RagEvalSynonymSource",
    "RagEvalABTestSide",
    # Phase 4+ 新增
    "RagEvalTestCaseStatus",
    "RagEvalIntentType",
    "RagEvalValidationStatus",
    "RagEvalSuggestionType",
    # Models
    "RagEvalTestSet",
    "RagEvalTestSetCase",
    "RagEvalTestCase",
    "RagEvalTestRun",
    "RagEvalTestRunResult",
    "RagEvalTestCaseDraft",
    "RagEvalIntentAnnotation",
    "RagEvalConfigVersion",
    "RagEvalPromptVersion",
    "RagEvalConfigChangeSet",
    "RagEvalConfigChangeSetPrompt",
    "RagEvalTestReport",
    "RagEvalTuningSuggestionRecord",
    "RagEvalPromptSuggestionRecord",
    "RagEvalIgnoredSuggestion",
    "RagEvalQueryIntentLog",
    "RagEvalSynonymQueryPair",
]
```

## 注意事项

1. **导入顺序**：先导入 enums（模型依赖），再导入各模型
2. **`__all__` 明确列出**所有导出项，避免 `import *` 时导入不必要的内容
3. 模型文件内部的 `relationship` 使用字符串前向引用（如 `"RagEvalTestSetCase"`），不直接导入避免循环依赖
