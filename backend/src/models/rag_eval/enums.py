"""RAG 评估系统所有 Enum 定义

所有枚举值使用小写字符串（MySQL 兼容），RagEvalABTestSide 除外。
TestDomain 复用现有 src.models.test_case.TestDomain，不在此定义。
"""

import enum


class RagEvalTestSetSourceType(enum.Enum):
    """测试集来源类型"""

    BOOK_GENERATED = "book_generated"
    JSON_IMPORTED = "json_imported"
    MANUAL = "manual"


class RagEvalTestRunStatus(enum.Enum):
    """测试运行状态"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RagEvalTestRunResultStatus(enum.Enum):
    """用例执行状态"""

    PASSED = "passed"
    FAILED = "failed"


class RagEvalTestCaseDraftStatus(enum.Enum):
    """草稿状态"""

    DRAFT = "draft"
    REVIEWED = "reviewed"
    REJECTED = "rejected"
    IMPORTED = "imported"


class RagEvalTestReportStatus(enum.Enum):
    """报告状态"""

    PROCESSING = "processing"
    COMPLETED = "completed"
    SUPERSEDED = "superseded"


class RagEvalChangeSetStatus(enum.Enum):
    """变更集状态"""

    COMMITTED = "committed"
    ROLLED_BACK = "rolled_back"


class RagEvalSuggestionSource(enum.Enum):
    """建议来源"""

    RULE_ENGINE = "rule_engine"
    HISTORY = "history"
    LLM = "llm"


class RagEvalPromptSuggestionType(enum.Enum):
    """提示词建议类型"""

    ADD_CONSTRAINT = "add_constraint"
    REWRITE = "rewrite"
    PARAMETER_TWEAK = "parameter_tweak"


class RagEvalIgnoredSuggestionType(enum.Enum):
    """忽略建议类型"""

    CONFIG = "config"
    PROMPT = "prompt"


class RagEvalIgnoreScope(enum.Enum):
    """忽略范围"""

    REPORT = "report"
    TEST_SET = "test_set"


class RagEvalSynonymSource(enum.Enum):
    """同义词来源"""

    BUILTIN = "builtin"
    AUTO_EXTRACTED = "auto_extracted"
    MANUAL = "manual"


class RagEvalABTestSide(enum.Enum):
    """A/B 测试侧（例外：枚举值使用大写）"""

    A = "A"
    B = "B"


class RagEvalTestCaseStatus(enum.Enum):
    """测试用例状态（Phase 5 草稿审核用）"""

    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class RagEvalIntentType(enum.Enum):
    """意图类型（Phase 5 意图标注用）"""

    DIRECT_RETRIEVAL = "direct_retrieval"
    COMPARISON = "comparison"
    PROCEDURAL = "procedural"
    CONCEPT_EXPLANATION = "concept_explanation"


class RagEvalValidationStatus(enum.Enum):
    """校验状态（Phase 4 校验引擎用）"""

    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    TIMEOUT = "timeout"
    DEGRADED = "degraded"
    SKIPPED = "skipped"


class RagEvalSuggestionType(enum.Enum):
    """建议类型（Phase 5 推荐面板用）"""

    PARAM_TUNING = "param_tuning"
    FUNCTION_SWITCH = "function_switch"
    SAFE_RANGE = "safe_range"
