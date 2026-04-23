"""提示词系统枚举定义"""

import enum


class PromptCategory(enum.Enum):
    """提示词分类"""

    RAG_RETRIEVAL = "rag_retrieval"
    RAG_GENERATION = "rag_generation"
    ASSESSMENT = "assessment"
    SCORING = "scoring"
    REPORTING = "reporting"
    TEST_CASE_GENERATION = "test_case_generation"
