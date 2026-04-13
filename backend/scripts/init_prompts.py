import asyncio
import sys
import os

# 把项目根目录加入路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.prompt.manager import prompt_manager
from src.core.prompts import (
    QUERY_REWRITE_PROMPT,
    SYNONYM_EXPANSION_PROMPT,
    METADATA_EXTRACTION_PROMPT,
    TEST_CASE_DRAFT_GENERATION_PROMPT,
    VALIDATION_SYSTEM_PROMPT,
    INTENSITY_INFERENCE_PROMPT,
    CATEGORY_INFERENCE_PROMPT,
    ASSESSMENT_SYSTEM_PROMPT,
    SCORING_SYSTEM_PROMPT,
    REPORTING_SYSTEM_PROMPT,
)

# 定义所有默认提示词，key与前端保持一致
DEFAULT_PROMPTS = [
    {
        "key": "rag_query_rewrite",
        "content": QUERY_REWRITE_PROMPT,
        "description": "查询重写提示词，用于将用户查询优化为更适合检索的形式",
        "variables": ["query", "age"],
        "tags": ["retrieval", "optimization"],
    },
    {
        "key": "synonym_expansion",
        "content": SYNONYM_EXPANSION_PROMPT,
        "description": "同义词扩展提示词，用于生成查询的相关同义词",
        "variables": ["query"],
        "tags": ["retrieval", "optimization"],
    },
    {
        "key": "metadata_extraction",
        "content": METADATA_EXTRACTION_PROMPT,
        "description": "元数据提取提示词，用于从文档块中提取结构化元数据",
        "variables": ["text"],
        "tags": ["ingestion", "metadata"],
    },
    {
        "key": "test_case_generation",
        "content": TEST_CASE_DRAFT_GENERATION_PROMPT,
        "description": "测试用例草稿生成提示词，用于从文档中自动生成RAG测试用例",
        "variables": ["count", "text", "domains", "age_range_min", "age_range_max"],
        "tags": ["rag_eval", "test_case"],
    },
    {
        "key": "validation",
        "content": VALIDATION_SYSTEM_PROMPT,
        "description": "校验节点系统提示词，用于校验用户输入数据的完整性和合理性",
        "variables": [],
        "tags": ["agent", "validation"],
    },
    {
        "key": "intensity_inference",
        "content": INTENSITY_INFERENCE_PROMPT,
        "description": "运动强度推断提示词，用于根据运动名称和年龄推断运动强度",
        "variables": ["age", "activity_name"],
        "tags": ["agent", "validation"],
    },
    {
        "key": "category_inference",
        "content": CATEGORY_INFERENCE_PROMPT,
        "description": "运动类别推断提示词，用于根据运动名称和年龄推断运动类别",
        "variables": ["age", "activity_name"],
        "tags": ["agent", "validation"],
    },
    {
        "key": "child_assessment",
        "content": ASSESSMENT_SYSTEM_PROMPT,
        "description": "评估节点系统提示词，用于评估儿童的发展状态",
        "variables": ["milestones", "input_data"],
        "tags": ["agent", "assessment"],
    },
    {
        "key": "scoring",
        "content": SCORING_SYSTEM_PROMPT,
        "description": "评分节点系统提示词，用于对训练计划进行多维度打分",
        "variables": [],
        "tags": ["agent", "scoring"],
    },
    {
        "key": "report_generation",
        "content": REPORTING_SYSTEM_PROMPT,
        "description": "报告生成节点系统提示词，用于生成最终的儿童发展评估报告",
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


async def init_prompts():
    """初始化所有默认提示词到数据库"""
    print("开始初始化默认提示词...")

    for prompt in DEFAULT_PROMPTS:
        print(f"正在处理提示词: {prompt['key']}")
        try:
            version = await prompt_manager.create_prompt_version(
                prompt_key=prompt["key"],
                content=prompt["content"],
                description=prompt["description"],
                created_by="system",
                variables=prompt["variables"],
                tags=prompt["tags"],
                fallback=prompt["content"],
            )
            print(f"✅ 提示词 {prompt['key']} 初始化完成，版本: {version}")
        except Exception as e:
            print(f"❌ 提示词 {prompt['key']} 初始化失败: {e}")

    print("所有提示词初始化完成！")


if __name__ == "__main__":
    asyncio.run(init_prompts())
