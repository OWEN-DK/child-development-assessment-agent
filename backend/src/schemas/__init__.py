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
                                 CreateVersionRequest,
                                 ImpactAnalysisResponse, ImpactAnalysisResult,
                                 PromptComparisonResponse, PromptDetailResponse,
                                 PromptItem, PromptListResponse,
                                 PromptMetadataResponse, PromptTestRequest,
                                 PromptTestResponse, PromptVersionResponse,
                                 UpdatePromptRequest,
                                 VariableChanges)
# 查询路由模块
from src.schemas.query import QueryClassification, QueryType
# RAG 模块
from src.schemas.rag import (DocumentMetadata, DocumentRecord, DocumentStore,
                             SynonymExpansionResult)
# RAG Eval 模块（v2 重构）
from src.schemas.rag_eval.diagnosis import DiagnosisResult, LayerIssue, LayerResult
from src.schemas.rag_eval.draft import (BookMetadata, DraftCreate, DraftGenerationConfig,
                                        DraftList, DraftRead, DraftReview, DraftUpdate)
from src.schemas.rag_eval.metrics import (Layer1Metrics, Layer2Metrics, Layer3Metrics,
                                          MetricInput, MetricOutput, MetricScore, RunMetrics)
from src.schemas.rag_eval.report import (BadCaseEntry, DiagnosisSection, EvalReportData,
                                         EvalReportRead, MetricCard, OverallSummary,
                                         ScoringDashboard, TrendData, TuningEntry)
from src.schemas.rag_eval.snapshot import SnapshotCreate, SnapshotRead
from src.schemas.rag_eval.source_document import SourceDocumentRead, SourceDocumentUpload
from src.schemas.rag_eval.test_case import (TestCaseCreate, TestCaseImportData, TestCaseImportItem,
                                            TestCaseList, TestCaseRead, TestCaseUpdate)
from src.schemas.rag_eval.test_run import (RetrievalMetrics, RunComparison, TestRunCreate,
                                           TestRunList, TestRunRead, TestRunResultItem)
from src.schemas.rag_eval.test_set import TestSetCreate, TestSetExport, TestSetRead, TestSetUpdate
from src.schemas.rag_eval.tuning import (ConfigChangeSetRead, ConfigVersionRead, ConflictPair,
                                          TuningSuggestion)

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
    # RAG Eval v2
    "DraftCreate",
    "DraftRead",
    "DraftUpdate",
    "DraftReview",
    "DraftList",
    "DraftGenerationConfig",
    "BookMetadata",
    "TestCaseCreate",
    "TestCaseRead",
    "TestCaseUpdate",
    "TestCaseList",
    "TestCaseImportItem",
    "TestCaseImportData",
    "TestSetCreate",
    "TestSetRead",
    "TestSetUpdate",
    "TestSetExport",
    "TestRunCreate",
    "TestRunRead",
    "TestRunList",
    "TestRunResultItem",
    "RunComparison",
    "RetrievalMetrics",
    "MetricScore",
    "MetricInput",
    "MetricOutput",
    "Layer1Metrics",
    "Layer2Metrics",
    "Layer3Metrics",
    "RunMetrics",
    "LayerIssue",
    "LayerResult",
    "DiagnosisResult",
    "OverallSummary",
    "MetricCard",
    "ScoringDashboard",
    "DiagnosisSection",
    "BadCaseEntry",
    "TuningEntry",
    "EvalReportData",
    "EvalReportRead",
    "TrendData",
    "SnapshotCreate",
    "SnapshotRead",
    "SourceDocumentRead",
    "SourceDocumentUpload",
    "TuningSuggestion",
    "ConflictPair",
    "ConfigVersionRead",
    "ConfigChangeSetRead",
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
    # 调参 (removed - migrated to RAG Eval v2)
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
