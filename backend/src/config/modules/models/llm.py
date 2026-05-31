"""LLM 多提供商配置模块

向后兼容设计：
- 保留旧的字符串字段（model_report_generation 等）从 .env 读取模型名称
- 新增 llm_providers 字典存储提供商凭证
- 新增 model_pricing 字典存储定价信息
- 业务代码可通过 settings.llm_scene_configs["report_generation"] 获取完整场景配置
"""

from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).parent.parent.parent.parent.resolve()


class LLMProviderConfig(BaseModel):
    """LLM 提供商凭证配置"""

    api_key: Optional[str] = Field(default=None, description="API 密钥")
    base_url: Optional[str] = Field(default=None, description="API 基础 URL")
    api_version: Optional[str] = Field(default=None, description="API 版本")


class ModelPricingConfig(BaseModel):
    """模型定价配置"""

    input_per_million: float = Field(description="输入 Token 每百万个费用")
    output_per_million: float = Field(description="输出 Token 每百万个费用")
    currency: str = Field(default="CNY", description="货币单位")


class LLMSceneConfig(BaseModel):
    """LLM 场景配置（每个业务场景的模型参数）"""

    provider: str = Field(default="dashscope", description="LLM 提供商")
    model: str = Field(description="模型名称")
    temperature: float = Field(default=0.7, ge=0, le=2, description="温度参数")
    max_tokens: int = Field(default=2000, gt=0, description="最大 Token 数")
    top_p: float = Field(default=0.8, ge=0, le=1, description="Top-p 采样参数")
    presence_penalty: float = Field(default=0.0, ge=-2, le=2, description="存在惩罚")
    frequency_penalty: float = Field(default=0.0, ge=-2, le=2, description="频率惩罚")


class LLMSettings(BaseSettings):
    """LLM 多提供商统一配置（向后兼容）"""

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env.dev"),
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )

    # ===== 保留：向后兼容的 API Key 字段 =====
    dashscope_api_key: str = Field(
        default="",
        validation_alias="DASHSCOPE_API_KEY",
        description="阿里云百炼 API 密钥",
    )
    
    deepseek_api_key: str = Field(
        default="",
        validation_alias="DEEPSEEK_API_KEY",
        description="DeepSeek API 密钥",
    )

    # ===== 新增：提供商凭证配置 =====
    llm_providers: Dict[str, LLMProviderConfig] = Field(
        default_factory=lambda: {
            "dashscope": LLMProviderConfig(
                api_key="",
                base_url=None,
                api_version=None,
            ),
            "deepseek": LLMProviderConfig(
                api_key="",
                base_url="https://api.deepseek.com/v1",
                api_version=None,
            ),
        },
        description="LLM 提供商凭证映射（支持 dashscope/openai/anthropic/ollama/deepseek）",
    )

    def model_post_init(self, __context) -> None:
        """初始化后将 API Key 同步到 llm_providers 中（仅当 providers 未单独配置时）"""
        if (
            self.dashscope_api_key
            and "dashscope" in self.llm_providers
            and not self.llm_providers["dashscope"].api_key
        ):
            self.llm_providers["dashscope"].api_key = self.dashscope_api_key
        
        if (
            self.deepseek_api_key
            and "deepseek" in self.llm_providers
            and not self.llm_providers["deepseek"].api_key
        ):
            self.llm_providers["deepseek"].api_key = self.deepseek_api_key

    # ===== 新增：多模态模型前缀列表 =====
    llm_multimodal_model_prefixes: List[str] = Field(
        default=[
            "qwen-vl",
            "qwen-audio",
            "qwen-omni",
            "qwen-vl-plus",
            "qwen-vl-max",
            "qwen-vl-max-latest",
            "qwen-audio-turbo",
            "qwen-audio-turbo-latest",
            "qwen-omni-turbo",
            "qwen-omni-flash",
            "qwen3-omni-flash",
            "qwen3-omni-turbo",
            # Qwen3.5/3.6 多模态变体（vl/omni），文本模型如 qwen-plus 不在此列
            "qwen3.5-vl",
            "qwen3.5-omni",
            "qwen3.6-vl",
            "qwen3.6-omni",
        ],
        validation_alias="LLM_MULTIMODAL_MODEL_PREFIXES",
        description="DashScope 多模态模型前缀列表（用于自动选择 API，匹配任一前缀即使用 MultiModalConversation API）",
    )

    # ===== 新增：模型定价配置 =====
    # 价格来源：阿里云百炼官网（中国内地，每百万 Token，CNY）
    # https://help.aliyun.com/zh/model-studio/getting-started/models
    model_pricing: Dict[str, ModelPricingConfig] = Field(
        default_factory=lambda: {
            # 旗舰模型
            "qwen3-max": ModelPricingConfig(
                input_per_million=2.5,
                output_per_million=10.0,
                currency="CNY",
            ),
            "qwen3.6-plus": ModelPricingConfig(
                input_per_million=2.0,
                output_per_million=12.0,
                currency="CNY",
            ),
            "qwen3.6-flash": ModelPricingConfig(
                input_per_million=1.2,
                output_per_million=7.2,
                currency="CNY",
            ),
            # 性价比之王（推荐默认）
            "qwen-plus": ModelPricingConfig(
                input_per_million=0.8,
                output_per_million=4.8,
                currency="CNY",
            ),
            # 均衡模型（非思考模式最便宜）
            "qwen-plus": ModelPricingConfig(
                input_per_million=0.8,
                output_per_million=2.0,
                currency="CNY",
            ),
            # 速度优先模型（RAG 评估指标计算）
            "qwen-turbo": ModelPricingConfig(
                input_per_million=0.3,
                output_per_million=0.6,
                currency="CNY",
            ),
            # DeepSeek V4 Flash
            "deepseek-v4-flash": ModelPricingConfig(
                input_per_million=0.5,
                output_per_million=2.0,
                currency="CNY",
            ),
            # 多模态模型
            "qwen3-omni-flash": ModelPricingConfig(
                input_per_million=0.2,
                output_per_million=2.0,
                currency="CNY",
            ),
            "qwen-vl-max": ModelPricingConfig(
                input_per_million=2.0,
                output_per_million=8.0,
                currency="CNY",
            ),
            "qwen3.5-27b": ModelPricingConfig(
                input_per_million=1.0,
                output_per_million=4.0,
                currency="CNY",
            ),
        },
        description="模型定价配置（每百万 Token 费用，单位：元）",
    )

    # ===== 保留：旧的字符串字段（向后兼容）=====
    model_report_generation: str = Field(
        default="qwen-plus",
        validation_alias="MODEL_REPORT_GENERATION",
        description="评估报告生成使用的模型（性价比之王，效果媲美 Max）",
    )
    model_assessment: str = Field(
        default="qwen-plus",
        validation_alias="MODEL_ASSESSMENT",
        description="儿童发展评估使用的模型（性价比之王）",
    )
    model_validation: str = Field(
        default="qwen-plus",
        validation_alias="MODEL_VALIDATION",
        description="结果校验使用的模型（最便宜）",
    )
    model_query_rewrite: str = Field(
        default="qwen-plus",
        validation_alias="MODEL_QUERY_REWRITE",
        description="查询重写使用的模型（最便宜）",
    )
    model_metadata_extraction: str = Field(
        default="qwen-plus",
        validation_alias="MODEL_METADATA_EXTRACTION",
        description="元数据提取使用的模型（最便宜）",
    )
    model_vl_parsing: str = Field(
        default="qwen3-omni-flash",
        validation_alias="MODEL_VL_PARSING",
        description="多模态内容解析使用的模型",
    )
    model_query_classification: str = Field(
        default="qwen-plus",
        validation_alias="MODEL_QUERY_CLASSIFICATION",
        description="查询分类使用的模型名称（最便宜）",
    )
    ml_scoring_qwen_model: str = Field(
        default="qwen-plus",
        validation_alias="ML_SCORING_QWEN_MODEL",
        description="大模型评分使用的模型名称（最便宜）",
    )
    model_rag_eval: str = Field(
        default="qwen-plus",
        validation_alias="MODEL_RAG_EVAL",
        description="RAG 评估指标计算使用的模型（性价比之王，JSON 输出稳定）",
    )
    model_knowledge_qa: str = Field(
        default="qwen3.5-27b",
        validation_alias="MODEL_KNOWLEDGE_QA",
        description="知识问答使用的模型（指令遵循能力强，支持 function calling + structured output）",
    )
    d2g_model: str = Field(
        default="qwen-plus",
        validation_alias="D2G_MODEL",
        description="D2G 知识图谱流水线使用的模型（性价比之王，支持 deepseek-v4-flash 等）",
    )
    d2g_max_tokens: int = Field(
        default=393216,
        validation_alias="D2G_MAX_TOKENS",
        description="D2G 流水线最大输出 Token 数（DeepSeek 支持最大 384K，建议 32K 起步）",
    )

    # ===== 新增：从旧字段自动构建的场景配置 =====
    @property
    def llm_scene_configs(self) -> Dict[str, LLMSceneConfig]:
        """获取所有场景的完整配置（自动从旧字段构建）"""
        return {
            "report_generation": LLMSceneConfig(
                provider="dashscope",
                model=self.model_report_generation or "qwen-plus",
            ),
            "assessment": LLMSceneConfig(
                provider="dashscope",
                model=self.model_assessment or "qwen-plus",
            ),
            "validation": LLMSceneConfig(
                provider="dashscope",
                model=self.model_validation or "qwen-plus",
            ),
            "query_rewrite": LLMSceneConfig(
                provider="dashscope",
                model=self.model_query_rewrite or "qwen-plus",
            ),
            "metadata_extraction": LLMSceneConfig(
                provider="dashscope",
                model=self.model_metadata_extraction or "qwen-plus",
            ),
            "query_classification": LLMSceneConfig(
                provider="dashscope",
                model=self.model_query_classification or "qwen-plus",
            ),
            "vl_parsing": LLMSceneConfig(
                provider="dashscope",
                model=self.model_vl_parsing or "qwen3-omni-flash",
            ),
            "ml_scoring": LLMSceneConfig(
                provider="dashscope",
                model=self.ml_scoring_qwen_model or "qwen-plus",
            ),
            "content_generation": LLMSceneConfig(
                provider="dashscope",
                model=self.model_report_generation or "qwen-plus",
            ),
            "draft_generation": LLMSceneConfig(
                provider="dashscope",
                model="qwen-plus",
            ),
            "rag_eval": LLMSceneConfig(
                provider="dashscope",
                model=self.model_rag_eval or "qwen-plus",
                max_tokens=4000,
            ),
            "knowledge_qa": LLMSceneConfig(
                provider="dashscope",
                model=self.model_knowledge_qa or "qwen3.5-27b",
                max_tokens=4000,
            ),
        }

    def get_scene_config(self, scene: str) -> LLMSceneConfig:
        """获取指定场景的配置"""
        return self.llm_scene_configs.get(scene)
