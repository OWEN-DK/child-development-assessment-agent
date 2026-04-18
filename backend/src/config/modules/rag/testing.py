"""测试用例生成配置模块

通过 ConfigManager 从 MySQL 读取，.env 兜底，支持热更新
"""

from pydantic import BaseModel, Field
from typing import List


class TestCaseGenerationConfig(BaseModel):
    """测试用例草稿生成配置"""

    # 数量控制
    test_case_draft_default_count: int = Field(
        default=100, ge=1, description="单篇文档默认生成草稿数量"
    )
    test_case_draft_max_count: int = Field(
        default=200, ge=1, description="单篇文档最大生成草稿数量"
    )
    test_case_draft_min_count: int = Field(
        default=20, ge=1, description="单篇文档最小生成草稿数量"
    )

    # 性能控制
    test_case_draft_concurrency: int = Field(
        default=20, ge=1, description="草稿生成并发数"
    )
    test_case_draft_batch_size: int = Field(
        default=10, ge=5, le=15, description="单次LLM调用生成草稿数量（10-15条）"
    )

    # 质量控制
    test_case_draft_deduplication_threshold: float = Field(
        default=0.8, ge=0.0, le=1.0, description="草稿去重相似度阈值"
    )
    test_case_draft_relevance_threshold: float = Field(
        default=0.6, ge=0.0, le=1.0, description="草稿相关性阈值，低于此值自动丢弃"
    )

    # 多维度差异化覆盖配置
    supported_domains: List[str] = Field(
        default_factory=lambda: [
            "粗大动作",
            "精细动作",
            "语言发展",
            "认知能力",
            "社交情感",
            "感觉统合",
        ],
        description="支持的发展领域列表",
    )
    age_stages: List[dict] = Field(
        default_factory=lambda: [
            {"name": "0-1岁", "age_min": 0, "age_max": 1, "min_count": 10},
            {"name": "1-3岁", "age_min": 1, "age_max": 3, "min_count": 10},
            {"name": "3-6岁", "age_min": 3, "age_max": 6, "min_count": 10},
            {"name": "6-12岁", "age_min": 6, "age_max": 12, "min_count": 10},
        ],
        description="年龄段划分及最小生成数量",
    )
    query_types: List[dict] = Field(
        default_factory=lambda: [
            {"name": "事实性查询", "description": "是什么/有什么", "min_count": 15},
            {"name": "比较性查询", "description": "区别/对比", "min_count": 15},
            {"name": "方案性查询", "description": "怎么做/如何", "min_count": 15},
            {"name": "原因分析性查询", "description": "为什么/原因", "min_count": 15},
        ],
        description="查询类型及最小生成数量",
    )
    difficulty_levels: List[dict] = Field(
        default_factory=lambda: [
            {"name": "入门级", "description": "基础概念", "min_count": 20},
            {"name": "中级", "description": "应用场景", "min_count": 20},
            {"name": "高级", "description": "复杂问题", "min_count": 20},
        ],
        description="难度级别及最小生成数量",
    )

    # 功能开关
    enable_breakpoint_resume: bool = Field(default=True, description="是否启用断点续传")
    enable_quality_check: bool = Field(default=True, description="是否启用质量校验")
    enable_relevance_check: bool = Field(default=True, description="是否启用相关性校验")


def calculate_draft_count_by_pages(
    page_count: int, config: TestCaseGenerationConfig
) -> int:
    """根据文档页数动态计算草稿生成数量"""
    if page_count < 50:
        return max(
            config.test_case_draft_min_count, config.test_case_draft_default_count // 5
        )
    elif page_count <= 200:
        return config.test_case_draft_default_count
    else:
        return min(
            config.test_case_draft_max_count, config.test_case_draft_default_count * 2
        )
