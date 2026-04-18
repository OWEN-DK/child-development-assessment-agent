# Phase 1-2: Controller 实体迁移

> **需求来源**: spec 文档 `unified-api-response-and-error-handling.md` 中 `2.4 迁移清单` 节
> **所属 Phase**: Phase 1

## 需求定义

将 9 个 Controller 文件中定义的 55 个 Pydantic BaseModel 类迁移至 `schemas/` 对应模块文件。

## 验收标准

- [ ] 所有 Controller 中 `class xxx(BaseModel)` 定义迁移完成
- [ ] Controller 文件中不再有 BaseModel 定义
- [ ] 所有引用处 import 更新为 `from src.schemas import Xxx`
- [ ] 功能回归测试通过

## 涉及文件

| 源文件 | 类数量 | 迁移目标 |
|-------|--------|---------|
| `controller/rag_test_controller.py` | 11 | `schemas/test_case.py` |
| `controller/config_controller.py` | 9 | `schemas/config.py` |
| `controller/prompt_management_controller.py` | 9 | `schemas/prompt.py` |
| `controller/tuning_controller.py` | 13 | `schemas/config.py` + `schemas/prompt.py` |
| `controller/config_management_controller.py` | 5 | `schemas/config.py` |
| `controller/prompt_controller.py` | 3 | `schemas/prompt.py` |
| `controller/rollback_controller.py` | 1 | `schemas/config.py` |
| `controller/health_controller.py` | 1 | `schemas/common.py` |
| `controller/config_health_controller.py` | 3 | `schemas/config.py` |

## 迁移清单

### controller/rag_test_controller.py → schemas/test_case.py

```python
# 迁移类：
CreateTestCaseRequest          # line 44
UpdateTestCaseRequest          # line 52
CreateSnapshotRequest          # line 60
BatchImportRequest             # line 119
BatchDeleteRequest             # line 181
RunTestsRequest                # line 193
GenerateDraftsRequest          # line 477
UpdateDraftRequest             # line 524
ImportDraftsRequest            # line 587
CreateTestSetRequest           # line 618
UpdateTestSetRequest           # line 651
AddCasesToSetRequest           # line 675
```

### controller/config_controller.py → schemas/config.py

```python
# 迁移类：
ConfigSaveRequest              # line 24
ConfigRollbackRequest          # line 31
ConfigResetRequest             # line 37
ConfigValidateRequest          # line 44
ConfigImportRequest            # line 50
ValidationError                # line 57
ConfigValidateResponse         # line 65
ConfigExportResponse           # line 72
ConfigVersionResponse          # line 80
```

### controller/prompt_management_controller.py → schemas/prompt.py

```python
# 迁移类：
PromptMetadataResponse         # line 15
PromptVersionResponse          # line 29
PromptListResponse             # line 43
PromptDetailResponse           # line 49
UpdatePromptRequest            # line 56
ImpactAnalysisResponse         # line 63
PromptTestRequest              # line 72
PromptTestResponse             # line 79
PromptComparisonResponse       # line 86
```

### controller/tuning_controller.py → schemas/config.py + schemas/prompt.py

```python
# 迁移至 schemas/config.py：
PreviewRequest                 # line 17
ApplyRequest                   # line 29
IgnoreSuggestionRequest        # line 39
ConfigChangeSetRequest         # line 118
ConfigChangeSetResponse        # line 126

# 迁移至 schemas/prompt.py：
PromptItem                     # line 109

# 迁移至 schemas/common.py（通用响应）：
PreviewResponse                # line 23
ApplyResponse                  # line 34
SuggestionResponse             # line 49
IgnoreSuggestionResponse       # line 64
IgnoredSuggestionItem          # line 71
IgnoredSuggestionsResponse     # line 86
RestoreIgnoredSuggestionResponse  # line 93
DeleteIgnoredSuggestionResponse   # line 102
```

### controller/prompt_controller.py → schemas/prompt.py

```python
CreateVersionRequest           # line 11
CreateABTestRequest            # line 20
ToggleABTestRequest            # line 27
```

### controller/config_management_controller.py → schemas/config.py

```python
ConfigMetadataResponse         # line 17
ConfigMetadataListResponse     # line 36
ConfigValidationRequest        # line 43
ConfigConflictRequest          # line 49
ConfigGroupResponse            # line 56
```

### controller/rollback_controller.py → schemas/config.py

```python
RollbackRequest                # line 17
```

### controller/health_controller.py → schemas/common.py

```python
HealthResponse                 # line 7
```

### controller/config_health_controller.py → schemas/config.py

```python
HealthDiagnosticRequest        # line 15
DiagnosticSuggestion           # line 21
HealthDiagnosticResponse       # line 32
```

## 实现方案

### 迁移步骤

1. 在目标 schemas 文件中定义类（保持原有字段不变）
2. 在 Controller 文件中删除类定义
3. 在 Controller 文件顶部添加 import：`from src.schemas import Xxx`
4. 运行测试验证

### 迁移后 Controller 示例

**迁移前** (`controller/config_controller.py`):
```python
from pydantic import BaseModel

class ConfigSaveRequest(BaseModel):
    key: str
    value: str
    description: str | None = None
```

**迁移后** (`controller/config_controller.py`):
```python
from src.schemas import ConfigSaveRequest
```

**迁移后** (`schemas/config.py`):
```python
from pydantic import BaseModel

class ConfigSaveRequest(BaseModel):
    key: str
    value: str
    description: str | None = None
```

## 测试方案

1. 每个 Controller 文件 import 无错误
2. FastAPI 路由注册正常
3. 请求/响应序列化正确

## 注意事项

- 命名规范：Request DTO 使用 `{Entity}{Action}Request`，Response DTO 使用 `{Entity}Response`
- 迁移时保持类定义完全不变，只改变位置
- 注意处理同名类冲突（如多个文件都定义了 `ValidationError`）
