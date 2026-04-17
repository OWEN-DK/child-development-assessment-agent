# 19 - Enum 映射验证规范 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 19 - Enum 映射验证规范

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

## 背景
根据项目核心踩坑经验，SQLAlchemy的Enum类型默认使用枚举类的`name`属性映射到数据库，而不是`value`属性，容易出现大小写不匹配或者值不一致导致的`LookupError`异常。因此需要统一规范Enum的映射方式。

## 统一规范
### 定义要求
所有在SQLAlchemy模型中使用的Enum类型必须满足：
1. 枚举值使用小写字符串
2. 定义模型时必须显式传递`values_callable=lambda obj: [e.value for e in obj]`参数
3. 插入和查询时必须使用枚举类成员，禁止直接传字符串

### Enum 定义位置
所有RAG评估相关的Enum统一定义在 `backend/src/models/rag_eval/enums.py` 文件中。

### 示例代码
```python
from enum import Enum as PyEnum

class RagEvalTestRunStatus(PyEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
```

```python
from sqlalchemy import Enum as SAEnum
from src.models.rag_eval.enums import RagEvalTestRunStatus

class RagEvalTestRun(Base):
    status: Mapped[RagEvalTestRunStatus] = mapped_column(
        SAEnum(
            RagEvalTestRunStatus,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        default=RagEvalTestRunStatus.PENDING,
    )
```

## 所有需要定义的Enum列表

| 枚举类名 | 枚举值 | 用途 | 所在模型 |
|----------|--------|------|---------|
| RagEvalTestSetSourceType | book_generated, json_imported, manual | 测试集来源类型 | RagEvalTestSet |
| TestDomain | gross_motor, fine_motor, language, cognitive, social_emotional, sensory_integration | 发展领域 | RagEvalTestCase, RagEvalTestCaseDraft（复用现有枚举） |
| RagEvalTestRunStatus | pending, running, completed, failed, cancelled | 测试运行状态 | RagEvalTestRun |
| RagEvalTestRunResultStatus | passed, failed | 用例执行状态 | RagEvalTestRunResult |
| RagEvalTestCaseDraftStatus | draft, reviewed, rejected, imported | 草稿状态 | RagEvalTestCaseDraft |
| RagEvalTestReportStatus | processing, completed, superseded | 报告状态 | RagEvalTestReport |
| RagEvalChangeSetStatus | committed, rolled_back | 变更集状态 | RagEvalConfigChangeSet |
| RagEvalSuggestionSource | rule_engine, history, llm | 建议来源 | RagEvalTuningSuggestionRecord |
| RagEvalPromptSuggestionType | add_constraint, rewrite, parameter_tweak | 提示词建议类型 | RagEvalPromptSuggestionRecord |
| RagEvalIgnoredSuggestionType | config, prompt | 忽略建议类型 | RagEvalIgnoredSuggestion |
| RagEvalIgnoreScope | report, test_set | 忽略范围 | RagEvalIgnoredSuggestion |
| RagEvalSynonymSource | builtin, auto_extracted, manual | 同义词来源 | RagEvalSynonymQueryPair |
| RagEvalABTestSide | a, b | A/B测试侧 | RagEvalTestRun |

## 完整 enums.py 定义

```python
from enum import Enum as PyEnum


class RagEvalTestSetSourceType(PyEnum):
    BOOK_GENERATED = "book_generated"
    JSON_IMPORTED = "json_imported"
    MANUAL = "manual"


class RagEvalTestRunStatus(PyEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RagEvalTestRunResultStatus(PyEnum):
    PASSED = "passed"
    FAILED = "failed"


class RagEvalTestCaseDraftStatus(PyEnum):
    DRAFT = "draft"
    REVIEWED = "reviewed"
    REJECTED = "rejected"
    IMPORTED = "imported"


class RagEvalTestReportStatus(PyEnum):
    PROCESSING = "processing"
    COMPLETED = "completed"
    SUPERSEDED = "superseded"


class RagEvalChangeSetStatus(PyEnum):
    COMMITTED = "committed"
    ROLLED_BACK = "rolled_back"


class RagEvalSuggestionSource(PyEnum):
    RULE_ENGINE = "rule_engine"
    HISTORY = "history"
    LLM = "llm"


class RagEvalPromptSuggestionType(PyEnum):
    ADD_CONSTRAINT = "add_constraint"
    REWRITE = "rewrite"
    PARAMETER_TWEAK = "parameter_tweak"


class RagEvalIgnoredSuggestionType(PyEnum):
    CONFIG = "config"
    PROMPT = "prompt"


class RagEvalIgnoreScope(PyEnum):
    REPORT = "report"
    TEST_SET = "test_set"


class RagEvalSynonymSource(PyEnum):
    BUILTIN = "builtin"
    AUTO_EXTRACTED = "auto_extracted"
    MANUAL = "manual"


class RagEvalABTestSide(PyEnum):
    A = "a"
    B = "b"
```

## 检查验证步骤
1. 检查所有枚举类是否继承自 `PyEnum`，值是否为小写字符串
2. 检查所有模型中Enum字段是否都显式传递了 `values_callable` 参数
3. 检查业务代码中是否都是使用枚举成员进行赋值和查询，没有直接传字符串
4. 执行单元测试验证枚举值的读写是否正常

## 常见错误规避
- ❌ 禁止省略 `values_callable` 参数
- ❌ 禁止直接传入字符串作为Enum字段的值
- ✅ 所有枚举值必须和数据库中存储的值完全一致
- ✅ 所有枚举在 `enums.py` 中统一定义
