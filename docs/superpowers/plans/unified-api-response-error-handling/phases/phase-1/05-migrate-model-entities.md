# Phase 1-5: model 实体迁移

> **需求来源**: spec 文档 `unified-api-response-and-error-handling.md` 中 `2.4 迁移清单` 节
> **所属 Phase**: Phase 1

## 需求定义

将 `backend/src/model/`（单数）目录中 4 个文件的 37 个 Pydantic BaseModel 类迁移至 `schemas/` 对应模块文件。

**注意**：`model/`（单数）存放 Pydantic 模型，`models/`（复数）存放 SQLAlchemy ORM 模型，两者不同。

## 验收标准

- [ ] `model/` 中所有 BaseModel 迁移完成
- [ ] 31 处 `from src.model.` 引用全部更新为 `from src.schemas.`
- [ ] `model/` 目录可删除
- [ ] 功能回归测试通过

## 涉及文件

| 源文件 | 类数量 | 迁移目标 |
|-------|--------|---------|
| `model/schemas.py` | 14 | `schemas/assessment.py` |
| `model/tuning.py` | 5 | `schemas/test_case.py` |
| `model/document.py` | 3 | `schemas/rag.py` |
| `model/rag_test.py` | 15 | `schemas/test_case.py` |

## 迁移清单

### model/schemas.py → schemas/assessment.py

```python
ChildProfile                   # line 26
Activity                       # line 38
ProposedPlan                   # line 53
HistoryActivity                # line 61
HistoryRecord                  # line 70
UserInput                      # line 78
CondensedContext               # line 94
DevelopmentStatus              # line 106
ChildState                     # line 114
KnowledgeItem                  # line 126
DimensionAnalysis              # line 152
EvaluationResult               # line 161
FinalReport                    # line 175
AgentState                     # line 189
```

### model/tuning.py → schemas/test_case.py

```python
TuningSuggestion               # line 7
HistoryReference               # line 22
LLMFinding                     # line 32
LLMDiagnosis                   # line 40
TuningSuggestionResponse       # line 48
```

### model/document.py → schemas/rag.py

```python
DocumentMetadata               # line 6
DocumentRecord                 # line 13
DocumentStore                  # line 25
```

### model/rag_test.py → schemas/test_case.py

```python
ChapterInfo                    # line 23
QualityReport                  # line 32
SourceDocument                 # line 43
GenerationParams               # line 60
TestCaseDraft                  # line 71
TestSet                        # line 91
TestCase                       # line 103
TestResultItem                 # line 129
TestResult                     # line 139
TestRun                        # line 155
KnowledgeSnapshot              # line 180
TestCaseStore                  # line 195
SourceDocumentStore            # line 201
TestCaseDraftStore             # line 207
TestSetStore                   # line 213
```

## 实现方案

### 引用更新映射

所有 `from src.model.schemas import Xxx` → `from src.schemas.assessment import Xxx`
所有 `from src.model.tuning import Xxx` → `from src.schemas.test_case import Xxx`
所有 `from src.model.document import Xxx` → `from src.schemas.rag import Xxx`
所有 `from src.model.rag_test import Xxx` → `from src.schemas.test_case import Xxx`

### 迁移步骤

1. 在目标 schemas 文件中定义类（保持原有字段不变）
2. 全局搜索 `from src.model.` 更新所有引用
3. 确认无引用后删除 `model/` 目录
4. 运行测试验证

## 测试方案

1. 全局 import 无错误
2. Agent 工作流状态序列化正确
3. RAG 测试相关模型正确

## 注意事项

- `model/schemas.py` 文件名与目标目录 `schemas/` 重名，迁移后删除原文件
- `model/rag_test.py` 中的 `GenerationParams` 与 `models/test_case.py` 中的 `GenerationParams` 可能重复，需合并
- `model/rag_test.py` 中的 `TestResultItem` 与 `models/test_case.py` 中的 `TestResultItem` 可能重复，需合并
- 迁移后 `model/` 目录应完全删除
