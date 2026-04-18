"""RAG 评估系统数据模型

导出所有 17 个模型 + 13 个 Enum。
"""

# Enums
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
    RagEvalTestCaseStatus,
    RagEvalIntentType,
    RagEvalValidationStatus,
    RagEvalSuggestionType,
    RagEvalPromptCategory,
)

# 核心业务模型
from src.models.rag_eval.test_set import RagEvalTestSet
from src.models.rag_eval.test_set_case import RagEvalTestSetCase
from src.models.rag_eval.test_case import RagEvalTestCase
from src.models.rag_eval.test_run import RagEvalTestRun
from src.models.rag_eval.test_run_result import RagEvalTestRunResult
from src.models.rag_eval.test_case_draft import RagEvalTestCaseDraft
from src.models.rag_eval.intent_annotation import RagEvalIntentAnnotation

# 配置与提示词模型
from src.models.rag_eval.config_version import RagEvalConfigVersion
from src.models.rag_eval.prompt_version import RagEvalPromptVersion
from src.models.rag_eval.prompt_metadata import RagEvalPromptMetadata
from src.models.rag_eval.config_change_set import RagEvalConfigChangeSet
from src.models.rag_eval.config_change_set_prompt import RagEvalConfigChangeSetPrompt

# 报告与建议模型
from src.models.rag_eval.test_report import RagEvalTestReport
from src.models.rag_eval.tuning_suggestion import RagEvalTuningSuggestionRecord
from src.models.rag_eval.prompt_suggestion import RagEvalPromptSuggestionRecord
from src.models.rag_eval.ignored_suggestion import RagEvalIgnoredSuggestion

# 辅助模型
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
    "RagEvalTestCaseStatus",
    "RagEvalIntentType",
    "RagEvalValidationStatus",
    "RagEvalSuggestionType",
    "RagEvalPromptCategory",
    # 核心业务模型
    "RagEvalTestSet",
    "RagEvalTestSetCase",
    "RagEvalTestCase",
    "RagEvalTestRun",
    "RagEvalTestRunResult",
    "RagEvalTestCaseDraft",
    "RagEvalIntentAnnotation",
    # 配置与提示词模型
    "RagEvalConfigVersion",
    "RagEvalPromptVersion",
    "RagEvalPromptMetadata",
    "RagEvalConfigChangeSet",
    "RagEvalConfigChangeSetPrompt",
    # 报告与建议模型
    "RagEvalTestReport",
    "RagEvalTuningSuggestionRecord",
    "RagEvalPromptSuggestionRecord",
    "RagEvalIgnoredSuggestion",
    # 辅助模型
    "RagEvalQueryIntentLog",
    "RagEvalSynonymQueryPair",
]
