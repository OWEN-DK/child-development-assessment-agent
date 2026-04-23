"""测试用例生成配置模块

通过 ConfigManager 从 MySQL 读取，.env 兜底，支持热更新
"""

from typing import List

from pydantic import BaseModel, Field


class TestCaseGenerationConfig(BaseModel):
    """测试用例草稿生成配置"""

    # ========== 默认选择 ==========
    default_domains: List[str] = Field(
        default_factory=lambda: ["粗大动作", "精细动作", "语言发展", "认知能力", "社交情感", "感觉统合"],
        description="上传书籍后默认选中的发展领域（可多选）",
    )
    default_age_stages: List[str] = Field(
        default_factory=lambda: ["0-1岁", "1-3岁", "3-6岁", "6-9岁", "9-12岁", "12-15岁", "15-18岁"],
        description="上传书籍后默认选中的年龄段（可多选）",
    )
    default_drafts_per_combination: int = Field(
        default=3, ge=1, le=10, description="每个组合默认生成草稿数（范围 1-10）",
    )

    # ========== 查询类型与难度 ==========
    default_query_types: List[str] = Field(
        default_factory=lambda: ["事实性查询", "比较性查询", "方案性查询"],
        description="默认勾选的查询类型",
    )
    default_difficulty_levels: List[str] = Field(
        default_factory=lambda: ["入门级", "中级", "高级"],
        description="默认勾选的难度级别",
    )

    # ========== 模型与成本 ==========
    default_model: str = Field(
        default="qwen-plus",
        description="草稿生成默认模型（必须在系统配置中已配置成本）",
    )

    # ========== 去重与质量 ==========
    deduplication_threshold: float = Field(
        default=0.85, ge=0.7, le=0.95, description="语义去重相似度阈值",
    )

    # ========== 执行控制 ==========
    batch_size: int = Field(
        default=5, ge=1, le=10, description="执行批次大小（每批任务数打包一次 LLM 调用）",
    )
    combination_interval_seconds: float = Field(
        default=1.0, ge=0.0, le=5.0, description="组合间间隔秒数",
    )
    max_concurrent_tasks: int = Field(
        default=1, ge=1, le=3, description="同一文档最大并发任务数",
    )

    # ========== 资源限制 ==========
    max_tokens_per_generation: int = Field(
        default=500000, gt=0, description="单次生成任务 TOKEN 消耗上限",
    )
    max_memory_mb: int = Field(
        default=500, gt=0, description="生成任务内存硬上限（MB）",
    )
    max_llm_retries: int = Field(
        default=2, ge=0, le=5, description="单组合 LLM 调用最大重试次数",
    )

    # ========== 保留：多维度矩阵定义 ==========
    supported_domains: List[str] = Field(
        default_factory=lambda: [
            "粗大动作", "精细动作", "语言发展",
            "认知能力", "社交情感", "感觉统合",
        ],
        description="支持的发展领域列表",
    )
    age_stages: List[dict] = Field(
        default_factory=lambda: [
            {"label": "0-1岁", "age_min_months": 0, "age_max_months": 12},
            {"label": "1-3岁", "age_min_months": 12, "age_max_months": 36},
            {"label": "3-6岁", "age_min_months": 36, "age_max_months": 72},
            {"label": "6-9岁", "age_min_months": 72, "age_max_months": 108},
            {"label": "9-12岁", "age_min_months": 108, "age_max_months": 144},
            {"label": "12-15岁", "age_min_months": 144, "age_max_months": 180},
            {"label": "15-18岁", "age_min_months": 180, "age_max_months": 216},
        ],
        description="年龄段划分（左闭右开，月龄精确）",
    )
    query_types: List[dict] = Field(
        default_factory=lambda: [
            {"name": "事实性查询", "description": "是什么/有什么/定义类问题"},
            {"name": "比较性查询", "description": "区别/对比/优劣类问题"},
            {"name": "方案性查询", "description": "怎么做/如何改善/训练方法类问题"},
            {"name": "原因分析性查询", "description": "为什么/成因/机制类问题"},
        ],
        description="查询类型定义",
    )
    difficulty_levels: List[dict] = Field(
        default_factory=lambda: [
            {"name": "入门级", "description": "基础概念认知，适合家长日常提问"},
            {"name": "中级", "description": "场景应用和对比分析，适合有一定知识的家长"},
            {"name": "高级", "description": "专业深度和机制分析，适合专业人士"},
        ],
        description="难度级别定义",
    )

    # ========== 功能开关（保留） ==========
    enable_breakpoint_resume: bool = Field(default=True, description="是否启用断点续传")
    enable_quality_check: bool = Field(default=True, description="是否启用质量校验")
    enable_relevance_check: bool = Field(default=True, description="是否启用相关性校验")
