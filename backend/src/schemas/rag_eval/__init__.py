"""RAG 评估模块 Schema 统一导出"""

from src.models.rag_eval.enums import (
    DifficultyLevel,
    DocumentStatus,
    TestCaseStatus,
    TestRunStatus,
    TestSourceType,
)
from src.schemas.rag_eval.diagnosis import (
    DiagnosisResult,
    LayerIssue,
    LayerResult,
)
from src.schemas.rag_eval.draft import (
    BookMetadata,
    DraftCreate,
    DraftGenerationConfig,
    DraftList,
    DraftRead,
    DraftReview,
    DraftUpdate,
)
from src.schemas.rag_eval.metrics import (
    Layer1Metrics,
    Layer2Metrics,
    Layer3Metrics,
    MetricInput,
    MetricOutput,
    MetricScore,
    RunMetrics,
)
from src.schemas.rag_eval.report import (
    BadCaseEntry,
    DiagnosisSection,
    EvalReportData,
    EvalReportRead,
    MetricCard,
    OverallSummary,
    ScoringDashboard,
    TrendData,
    TuningEntry,
)
from src.schemas.rag_eval.snapshot import (
    SnapshotCreate,
    SnapshotRead,
)
from src.schemas.rag_eval.source_document import (
    SourceDocumentRead,
    SourceDocumentUpload,
)
from src.schemas.rag_eval.test_case import (
    TestCaseCreate,
    TestCaseImportData,
    TestCaseImportItem,
    TestCaseList,
    TestCaseRead,
    TestCaseUpdate,
)
from src.schemas.rag_eval.test_run import (
    RetrievalMetrics,
    RunComparison,
    TestRunCreate,
    TestRunList,
    TestRunRead,
    TestRunResultItem,
)
from src.schemas.rag_eval.test_set import (
    TestSetCreate,
    TestSetExport,
    TestSetRead,
    TestSetUpdate,
)
from src.schemas.rag_eval.tuning import (
    ConfigChangeSetRead,
    ConfigVersionRead,
    ConflictPair,
    TuningSuggestion,
)

__all__ = [
    # 枚举
    "TestRunStatus",
    "TestSourceType",
    "DifficultyLevel",
    "DocumentStatus",
    "TestCaseStatus",
    # 源文档
    "SourceDocumentRead",
    "SourceDocumentUpload",
    # 草稿
    "DraftCreate",
    "DraftRead",
    "DraftUpdate",
    "DraftReview",
    "DraftList",
    "DraftGenerationConfig",
    "BookMetadata",
    # 测试用例
    "TestCaseCreate",
    "TestCaseRead",
    "TestCaseUpdate",
    "TestCaseList",
    "TestCaseImportItem",
    "TestCaseImportData",
    # 测试集
    "TestSetCreate",
    "TestSetRead",
    "TestSetUpdate",
    "TestSetExport",
    # 测试运行
    "TestRunCreate",
    "TestRunRead",
    "TestRunList",
    "TestRunResultItem",
    "RunComparison",
    "RetrievalMetrics",
    # 三层指标
    "MetricScore",
    "MetricInput",
    "MetricOutput",
    "Layer1Metrics",
    "Layer2Metrics",
    "Layer3Metrics",
    "RunMetrics",
    # 六层诊断
    "LayerIssue",
    "LayerResult",
    "DiagnosisResult",
    # 报告
    "OverallSummary",
    "MetricCard",
    "ScoringDashboard",
    "DiagnosisSection",
    "BadCaseEntry",
    "TuningEntry",
    "EvalReportData",
    "EvalReportRead",
    "TrendData",
    # 快照
    "SnapshotRead",
    "SnapshotCreate",
    # 调优
    "TuningSuggestion",
    "ConflictPair",
    "ConfigVersionRead",
    "ConfigChangeSetRead",
]
