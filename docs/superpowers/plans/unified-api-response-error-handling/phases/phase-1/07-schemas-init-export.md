# Phase 1-7: schemas __init__.py 导出

> **需求来源**: spec 文档 `unified-api-response-and-error-handling.md` 中 `2.5 导入规范` 节
> **所属 Phase**: Phase 1

## 需求定义

创建 `backend/src/schemas/__init__.py`，统一导出所有实体类，提供简洁的导入入口。

## 验收标准

- [ ] `__init__.py` 导出所有实体类
- [ ] 支持 `from src.schemas import Xxx` 导入方式
- [ ] 支持 `from src.schemas.assessment import Xxx` 模块级导入
- [ ] 无循环导入

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `backend/src/schemas/__init__.py` | 新增 | 统一导出入口 |

## 实现方案

### __init__.py 内容

```python
"""
Schema 模块 - 统一实体类管理

所有 Pydantic 实体类集中在此目录，按业务模块组织。
禁止在 service/、controller/、core/ 中定义 class xxx(BaseModel)。
"""

# 通用模型
from src.schemas.common import (
    APIResponse,
    PaginatedResponse,
    HealthResponse,
    Message,
    LLMMessage,
    LLMResponse,
    LLMRequest,
    User,
)

# 评估模块
from src.schemas.assessment import (
    ChildProfile,
    Activity,
    ProposedPlan,
    HistoryActivity,
    HistoryRecord,
    UserInput,
    CondensedContext,
    DevelopmentStatus,
    ChildState,
    KnowledgeItem,
    DimensionAnalysis,
    EvaluationResult,
    FinalReport,
    AgentState,
)

# RAG 模块
from src.schemas.rag import (
    DocumentMetadata,
    DocumentRecord,
    DocumentStore,
    SynonymExpansionResult,
    QueryClassification,
    ExtractedMetadata,
)

# 测试模块
from src.schemas.test_case import (
    # 请求 DTO
    CreateTestCaseRequest,
    UpdateTestCaseRequest,
    CreateSnapshotRequest,
    BatchImportRequest,
    BatchDeleteRequest,
    RunTestsRequest,
    GenerateDraftsRequest,
    UpdateDraftRequest,
    ImportDraftsRequest,
    CreateTestSetRequest,
    UpdateTestSetRequest,
    AddCasesToSetRequest,
    # 领域模型
    TestCase,
    TestSet,
    TestRun,
    TestCaseDraft,
    TestResultItem,
    TestResult,
    KnowledgeSnapshot,
    GenerationParams,
    TuningSuggestion,
    HistoryReference,
    LLMFinding,
    LLMDiagnosis,
    TuningSuggestionResponse,
    # Store 模型
    TestCaseStore,
    SourceDocumentStore,
    TestCaseDraftStore,
    TestSetStore,
    ChapterInfo,
    QualityReport,
    SourceDocument,
)

# 配置模块
from src.schemas.config import (
    # 请求 DTO
    ConfigSaveRequest,
    ConfigRollbackRequest,
    ConfigResetRequest,
    ConfigValidateRequest,
    ConfigImportRequest,
    ConfigValidationRequest,
    ConfigConflictRequest,
    RollbackRequest,
    HealthDiagnosticRequest,
    PreviewRequest,
    ApplyRequest,
    IgnoreSuggestionRequest,
    ConfigChangeSetRequest,
    # 响应 DTO
    ValidationError,
    ConfigValidateResponse,
    ConfigExportResponse,
    ConfigVersionResponse,
    ConfigMetadataResponse,
    ConfigMetadataListResponse,
    ConfigGroupResponse,
    HealthDiagnosticResponse,
    DiagnosticSuggestion,
    ApplyResponse,
    ConfigChangeSetResponse,
    # 领域模型
    Conflict,
    ValidationResult,
    AgeFilterConfig,
    LLMProviderConfig,
    ModelPricingConfig,
    LLMSceneConfig,
    TestCaseGenerationConfig,
    ValidationRules,
    AssessmentRules,
    ScoringRules,
    PreprocessingRules,
    MetadataRules,
    ConfigVersion,
)

# 提示词模块
from src.schemas.prompt import (
    # 请求 DTO
    CreateVersionRequest,
    CreateABTestRequest,
    ToggleABTestRequest,
    UpdatePromptRequest,
    PromptTestRequest,
    # 响应 DTO
    PromptMetadataResponse,
    PromptVersionResponse,
    PromptListResponse,
    PromptDetailResponse,
    ImpactAnalysisResponse,
    PromptTestResponse,
    PromptComparisonResponse,
    PromptItem,
    SuggestionResponse,
    IgnoreSuggestionResponse,
    IgnoredSuggestionItem,
    IgnoredSuggestionsResponse,
    RestoreIgnoredSuggestionResponse,
    DeleteIgnoredSuggestionResponse,
    # 领域模型
    CodeReference,
    VariableChanges,
    ConfigDependency,
    ImpactAnalysisResult,
)

# 监控模块
from src.schemas.monitoring import (
    TraceMetadata,
)

# SSE 事件模型
from src.schemas.events import (
    OverallMetrics,
    ValidationSummaryItem,
    RunStartedEvent,
    ProgressEvent,
    CaseResultEvent,
    TestCompletedEvent,
    ValidationStartedEvent,
    ValidationCompletedEvent,
    ReportReadyEvent,
    RunFailedEvent,
    HeartbeatEvent,
    ExportReadyEvent,
    ExportFailedEvent,
)

__all__ = [
    # common
    "APIResponse",
    "PaginatedResponse",
    "HealthResponse",
    "Message",
    "LLMMessage",
    "LLMResponse",
    "LLMRequest",
    "User",
    # assessment
    "ChildProfile",
    "Activity",
    "ProposedPlan",
    "UserInput",
    "ChildState",
    "FinalReport",
    "AgentState",
    # rag
    "DocumentMetadata",
    "SynonymExpansionResult",
    "QueryClassification",
    "ExtractedMetadata",
    # test_case
    "CreateTestCaseRequest",
    "TestCase",
    "TestSet",
    "TestRun",
    "TestCaseDraft",
    # config
    "ConfigSaveRequest",
    "LLMProviderConfig",
    "Conflict",
    "ValidationResult",
    # prompt
    "CreateVersionRequest",
    "ImpactAnalysisResult",
    # monitoring
    "TraceMetadata",
    # events
    "RunStartedEvent",
    "ProgressEvent",
    "HeartbeatEvent",
]
```

### 导入规范

```python
# 推荐：从 schemas 统一导入
from src.schemas import CreateTestCaseRequest, APIResponse, TestCase

# 推荐：按模块导入（避免 __init__.py 过大时）
from src.schemas.assessment import ChildState, FinalReport
from src.schemas.config import LLMProviderConfig, ConfigValidationResult

# 禁止：从 controller 或 service 导入
# from src.controller.rag_test_controller import CreateTestCaseRequest  ❌
# from src.service.config_validation_engine import ValidationResult     ❌
```

## 测试方案

1. `from src.schemas import Xxx` 导入无错误
2. `from src.schemas.assessment import Xxx` 模块导入无错误
3. `__all__` 列表与实际导出一致

## 注意事项

- `__init__.py` 仅负责导出，不定义任何类
- 如果某个模块文件过大，可使用 `TYPE_CHECKING` 避免循环导入
- `__all__` 列表必须与导入一致，避免 `import *` 时遗漏
