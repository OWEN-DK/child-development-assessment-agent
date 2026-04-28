"""提示词自动初始化模块

应用启动时自动将默认提示词写入数据库（幂等操作，已存在则跳过）。
复用 prompts_fallback.py 中的提示词内容作为初始值。
"""

from src.core.prompt_impl.facade import prompt_manager
from src.core.prompts_fallback import (
    ASSESSMENT_SYSTEM_PROMPT,
    CATEGORY_INFERENCE_PROMPT,
    INTENSITY_INFERENCE_PROMPT,
    METADATA_EXTRACTION_PROMPT,
    QUERY_REWRITE_PROMPT,
    RAG_QUERY_TEMPLATE,
    REPORTING_SYSTEM_PROMPT,
    SCORING_SYSTEM_PROMPT,
    SYNONYM_EXPANSION_PROMPT,
    TEST_CASE_DRAFT_GENERATION_PROMPT,
    TEST_CASE_GENERATION_CHUNK_GROUNDED_PROMPT,
    VALIDATION_SYSTEM_PROMPT,
)
from src.utils.logger import logger

# 默认提示词定义
DEFAULT_PROMPTS = [
    {
        "key": "rag_query_rewrite",
        "content": QUERY_REWRITE_PROMPT,
        "name_zh": "查询重写",
        "purpose": "优化用户查询以提高检索准确率",
        "category": "rag_retrieval",
        "variables": ["query"],
        "tags": ["rag", "query"],
    },
    {
        "key": "synonym_expansion",
        "content": SYNONYM_EXPANSION_PROMPT,
        "name_zh": "同义词扩展",
        "purpose": "扩展查询的相关术语",
        "category": "rag_retrieval",
        "variables": ["query"],
        "tags": ["rag", "query"],
    },
    {
        "key": "rag_query_template",
        "content": RAG_QUERY_TEMPLATE,
        "name_zh": "RAG 查询模板",
        "purpose": "RAG 查询模板",
        "category": "rag_retrieval",
        "variables": ["query"],
        "tags": ["rag"],
    },
    {
        "key": "metadata_extraction",
        "content": METADATA_EXTRACTION_PROMPT,
        "name_zh": "元数据提取",
        "purpose": "从文档块中提取结构化元数据",
        "category": "rag_generation",
        "variables": ["text"],
        "tags": ["ingestion", "metadata"],
    },
    {
        "key": "test_case_generation",
        "content": TEST_CASE_DRAFT_GENERATION_PROMPT,
        "name_zh": "测试用例生成",
        "purpose": "从文档中自动生成 RAG 测试用例",
        "category": "test_case_generation",
        "variables": ["count", "text", "domains", "age_range_min", "age_range_max"],
        "tags": ["rag_eval", "test_case"],
    },
    {
        "key": "test_case_generation_chunk_grounded",
        "content": TEST_CASE_GENERATION_CHUNK_GROUNDED_PROMPT,
        "name_zh": "逐块测试用例生成",
        "purpose": "从单个文档块中生成忠实于原文的 RAG 测试用例",
        "category": "test_case_generation",
        "variables": ["chunk_id", "chunk_content", "chunk_page", "chunk_topics", "domain", "age_stage_label", "age_min_months", "age_max_months"],
        "tags": ["rag_eval", "test_case", "chunk"],
    },
    {
        "key": "validation",
        "content": VALIDATION_SYSTEM_PROMPT,
        "name_zh": "数据校验",
        "purpose": "校验用户输入数据的完整性和合理性",
        "category": "assessment",
        "variables": [],
        "tags": ["agent", "validation"],
    },
    {
        "key": "intensity_inference",
        "content": INTENSITY_INFERENCE_PROMPT,
        "name_zh": "运动强度推断",
        "purpose": "根据运动名称和年龄推断运动强度",
        "category": "assessment",
        "variables": ["age", "activity_name"],
        "tags": ["agent", "validation"],
    },
    {
        "key": "category_inference",
        "content": CATEGORY_INFERENCE_PROMPT,
        "name_zh": "运动类别推断",
        "purpose": "根据运动名称和年龄推断运动类别",
        "category": "assessment",
        "variables": ["age", "activity_name"],
        "tags": ["agent", "validation"],
    },
    {
        "key": "child_assessment",
        "content": ASSESSMENT_SYSTEM_PROMPT,
        "name_zh": "儿童发展评估",
        "purpose": "评估儿童的发展状态",
        "category": "assessment",
        "variables": ["milestones", "input_data"],
        "tags": ["agent", "assessment"],
    },
    {
        "key": "scoring",
        "content": SCORING_SYSTEM_PROMPT,
        "name_zh": "评分",
        "purpose": "对训练计划进行多维度打分",
        "category": "scoring",
        "variables": [],
        "tags": ["agent", "scoring"],
    },
    {
        "key": "report_generation",
        "content": REPORTING_SYSTEM_PROMPT,
        "name_zh": "报告生成",
        "purpose": "生成最终的儿童发展评估报告",
        "category": "reporting",
        "variables": [
            "reference_materials",
            "child_name",
            "date",
            "child_name_hash",
            "score",
            "overall_assessment",
            "issues_list",
            "development_details",
            "plan_name",
            "plan_content",
            "algo_analysis",
            "reasoning",
            "scientific_evidence",
            "suggestions",
        ],
        "tags": ["agent", "reporting"],
    },
]


async def init_default_prompts():
    """初始化默认提示词到数据库（幂等操作）

    遍历 DEFAULT_PROMPTS 列表，检查每个提示词是否存在：
    - 不存在：创建元数据 + 初始版本
    - 已存在：跳过

    该函数应在应用启动时调用，确保系统有可用的默认提示词。
    """
    try:
        initialized_count = 0
        skipped_count = 0

        for prompt in DEFAULT_PROMPTS:
            try:
                # 检查提示词是否已存在
                existing_versions = await prompt_manager.list_versions(prompt["key"])
                if existing_versions:
                    skipped_count += 1
                    continue

                # 创建元数据
                await prompt_manager.prompt_storage.get_or_create_metadata(
                    prompt_key=prompt["key"],
                    name_zh=prompt["name_zh"],
                    purpose=prompt["purpose"],
                    category=prompt["category"],
                    is_system=True,
                    created_by="system",
                )

                # 创建初始版本
                await prompt_manager.create_prompt_version(
                    prompt_key=prompt["key"],
                    content=prompt["content"],
                    description=prompt["purpose"],
                    created_by="system",
                    variables=prompt["variables"],
                    tags=prompt["tags"],
                    fallback=prompt["content"],
                )
                initialized_count += 1
                logger.info(f"✅ 初始化提示词: {prompt['key']}")

            except Exception as e:
                logger.warning(f"提示词 {prompt['key']} 初始化跳过: {e}")

        if initialized_count > 0:
            logger.info(f"✅ 已初始化 {initialized_count} 个默认提示词")
        if skipped_count > 0:
            logger.info(f"ℹ️  {skipped_count} 个提示词已存在，跳过")

    except Exception as e:
        logger.warning(f"提示词自动初始化失败（将使用 fallback）: {e}")
