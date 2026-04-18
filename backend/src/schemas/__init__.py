"""Schemas 统一导出入口

所有 Pydantic 实体类统一从本模块导出。
使用方式：
    from src.schemas import APIResponse, ChildProfile, TestCase, ...
"""

# 评估模块
from src.schemas.assessment import (  # 枚举类型; 输入模型; 中间状态; LangGraph State
    Activity, ActivityCategory, AgentState, ChildProfile, ChildState,
    CondensedContext, DevelopmentStatus, DimensionAnalysis, EvaluationResult,
    FinalReport, GenderType, HistoryActivity, HistoryRecord, IntensityType,
    KnowledgeItem, ProposedPlan, RiskLevel, StatusType, UserInput)
# 认证模块
from src.schemas.auth import User
# 通用模型
from src.schemas.common import APIResponse, HealthResponse, PaginatedResponse
# 配置模块新增
# 配置模块
from src.schemas.config import (AgeFilterConfig, ApplyRequest, ApplyResponse,
                                ConfigChangeSetRequest,
                                ConfigChangeSetResponse, ConfigConflictRequest,
                                ConfigExportResponse, ConfigGroupResponse,
                                ConfigImportRequest,
                                ConfigMetadataListResponse,
                                ConfigMetadataResponse, ConfigResetRequest,
                                ConfigRollbackRequest, ConfigSaveRequest,
                                ConfigValidateRequest, ConfigValidateResponse,
                                ConfigValidationRequest, ConfigVersionResponse,
                                Conflict, DeleteIgnoredSuggestionResponse,
                                DiagnosticSuggestion, HealthDiagnosticRequest,
                                HealthDiagnosticResponse,
                                IgnoredSuggestionItem,
                                IgnoredSuggestionsResponse,
                                IgnoreSuggestionRequest,
                                IgnoreSuggestionResponse, LLMProviderConfig,
                                PreviewRequest, PreviewResponse,
                                RestoreIgnoredSuggestionResponse,
                                RollbackRequest, SuggestionResponse,
                                ValidationError, ValidationResult)
# SSE 事件模块
from src.schemas.events import (CaseResultEvent, ExportFailedEvent,
                                ExportReadyEvent, HeartbeatEvent,
                                OverallMetrics, ProgressEvent,
                                ReportReadyEvent, RunFailedEvent,
                                RunStartedEvent, SseEvent, SseEventType,
                                TestCompletedEvent, ValidationCompletedEvent,
                                ValidationStartedEvent, ValidationSummaryItem)
# LLM 模块
from src.schemas.llm import (LLMMessage, LLMRequest, LLMResponse, Message,
                             MessageRole)
# 元数据提取模块
from src.schemas.metadata import ExtractedMetadata
# ML 评分模块
from src.schemas.ml import QwenScoringOutput
# 监控模块
from src.schemas.monitoring import (HealthCheckResponse, MetricData,
                                    PerformanceMetrics, TraceMetadata)
# 提示词模块新增
# 提示词模块
from src.schemas.prompt import (CodeReference, ConfigDependency,
                                CreateABTestRequest, CreateVersionRequest,
                                ImpactAnalysisResponse, ImpactAnalysisResult,
                                PromptComparisonResponse, PromptDetailResponse,
                                PromptItem, PromptListResponse,
                                PromptMetadataResponse, PromptTestRequest,
                                PromptTestResponse, PromptVersionResponse,
                                ToggleABTestRequest, UpdatePromptRequest,
                                VariableChanges)
# 查询路由模块
from src.schemas.query import QueryClassification, QueryType
# RAG 模块
from src.schemas.rag import (DocumentMetadata, DocumentRecord, DocumentStore,
                             SynonymExpansionResult)
# 测试模块
from src.schemas.test_case import AddCasesToSetRequest  # 枚举; 核心模型; 请求 DTO
from src.schemas.test_case import (BatchDeleteRequest, BatchImportRequest,
                                   ChapterInfo, CreateSnapshotRequest,
                                   CreateTestCaseRequest, CreateTestSetRequest,
                                   DifficultyLevel, DocumentStatus,
                                   DraftStatus, GenerateDraftsRequest,
                                   GenerationParams, ImportDraftsRequest,
                                   KnowledgeSnapshot, QualityReport,
                                   ReportExportFormat, RunTestsRequest,
                                   SourceDocument, TestCase, TestCaseDraft,
                                   TestDomain, TestResult, TestResultItem,
                                   TestRun, TestRunStatus, TestSet,
                                   TestSourceType, UpdateDraftRequest,
                                   UpdateTestCaseRequest, UpdateTestSetRequest)
# 调参模块
from src.schemas.tuning import (HistoryReference, LLMDiagnosis, LLMFinding,
                                TuningSuggestion, TuningSuggestionResponse)

__all__ = [
    # 通用
    "APIResponse",
    "PaginatedResponse",
    "HealthResponse",
    # 评估
    "GenderType",
    "IntensityType",
    "ActivityCategory",
    "RiskLevel",
    "StatusType",
    "ChildProfile",
    "Activity",
    "ProposedPlan",
    "HistoryActivity",
    "HistoryRecord",
    "UserInput",
    "CondensedContext",
    "DevelopmentStatus",
    "ChildState",
    "KnowledgeItem",
    "DimensionAnalysis",
    "EvaluationResult",
    "FinalReport",
    "AgentState",
    # RAG
    "DocumentMetadata",
    "DocumentRecord",
    "DocumentStore",
    "SynonymExpansionResult",
    # 测试
    "DraftStatus",
    "DocumentStatus",
    "TestRunStatus",
    "TestDomain",
    "DifficultyLevel",
    "TestSourceType",
    "ReportExportFormat",
    "ChapterInfo",
    "QualityReport",
    "SourceDocument",
    "GenerationParams",
    "TestCaseDraft",
    "TestSet",
    "TestCase",
    "TestResultItem",
    "TestResult",
    "TestRun",
    "KnowledgeSnapshot",
    "CreateTestCaseRequest",
    "UpdateTestCaseRequest",
    "CreateSnapshotRequest",
    "BatchImportRequest",
    "BatchDeleteRequest",
    "RunTestsRequest",
    "GenerateDraftsRequest",
    "UpdateDraftRequest",
    "ImportDraftsRequest",
    "CreateTestSetRequest",
    "UpdateTestSetRequest",
    "AddCasesToSetRequest",
    # 配置
    "ConfigSaveRequest",
    "ConfigRollbackRequest",
    "ConfigResetRequest",
    "ConfigValidateRequest",
    "ConfigImportRequest",
    "ValidationError",
    "ConfigValidateResponse",
    "ConfigExportResponse",
    "ConfigVersionResponse",
    "ConfigMetadataResponse",
    "ConfigMetadataListResponse",
    "ConfigValidationRequest",
    "ConfigConflictRequest",
    "ConfigGroupResponse",
    "RollbackRequest",
    "HealthDiagnosticRequest",
    "DiagnosticSuggestion",
    "HealthDiagnosticResponse",
    "LLMProviderConfig",
    "AgeFilterConfig",
    "PreviewRequest",
    "PreviewResponse",
    "ApplyRequest",
    "ApplyResponse",
    "SuggestionResponse",
    "IgnoreSuggestionRequest",
    "IgnoreSuggestionResponse",
    "IgnoredSuggestionItem",
    "IgnoredSuggestionsResponse",
    "RestoreIgnoredSuggestionResponse",
    "DeleteIgnoredSuggestionResponse",
    "ConfigChangeSetRequest",
    "ConfigChangeSetResponse",
    # 提示词
    "CreateVersionRequest",
    "CreateABTestRequest",
    "ToggleABTestRequest",
    "PromptMetadataResponse",
    "PromptVersionResponse",
    "PromptListResponse",
    "PromptDetailResponse",
    "UpdatePromptRequest",
    "ImpactAnalysisResponse",
    "PromptTestRequest",
    "PromptTestResponse",
    "PromptComparisonResponse",
    "PromptItem",
    # 监控
    "TraceMetadata",
    "MetricData",
    "HealthCheckResponse",
    "PerformanceMetrics",
    # SSE 事件
    "SseEventType",
    "OverallMetrics",
    "ValidationSummaryItem",
    "RunStartedEvent",
    "ProgressEvent",
    "CaseResultEvent",
    "TestCompletedEvent",
    "ValidationStartedEvent",
    "ValidationCompletedEvent",
    "ReportReadyEvent",
    "RunFailedEvent",
    "HeartbeatEvent",
    "ExportReadyEvent",
    "ExportFailedEvent",
    "SseEvent",
    # LLM
    "MessageRole",
    "Message",
    "LLMMessage",
    "LLMResponse",
    "LLMRequest",
    # 调参
    "TuningSuggestion",
    "HistoryReference",
    "LLMFinding",
    "LLMDiagnosis",
    "TuningSuggestionResponse",
    # 认证
    "User",
    # 查询路由
    "QueryType",
    "QueryClassification",
    # 元数据提取
    "ExtractedMetadata",
    # ML 评分
    "QwenScoringOutput",
    # 配置新增
    "Conflict",
    "ValidationResult",
    # 提示词新增
    "CodeReference",
    "VariableChanges",
    "ConfigDependency",
    "ImpactAnalysisResult",
]
