"""LLM 配置模块

提供 LLMSceneConfig 模型 + LLMSettings（BaseSettings）用于多提供商配置。
"""
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).parent.parent.parent.parent.parent.resolve()


class LLMSceneConfig(BaseModel):
    """LLM 场景配置（每个业务场景的模型参数）

    用于 Pydantic 校验，确保从 MySQL 读取的配置符合约束。
    """
    provider: str = Field(default="dashscope", description="LLM 提供商")
    model: str = Field(default="qwen-plus", description="模型名称")
    temperature: float = Field(default=0.7, ge=0, le=2, description="温度参数")
    max_tokens: int = Field(default=2000, gt=0, description="最大 Token 数")
    top_p: float = Field(default=0.8, ge=0, le=1, description="Top-p 采样参数")
    presence_penalty: float = Field(default=0.0, ge=-2, le=2, description="存在惩罚")
    frequency_penalty: float = Field(default=0.0, ge=-2, le=2, description="频率惩罚")

    @classmethod
    def from_db_config(cls, data: dict[str, Any]) -> "LLMSceneConfig":
        """从数据库配置创建（容错处理）"""
        allowed_keys = set(cls.model_fields.keys())
        filtered = {k: v for k, v in data.items() if k in allowed_keys}
        return cls(**filtered)


class LLMProviderConfig(BaseModel):
    """LLM 提供商凭证配置"""
    api_key: Optional[str] = Field(default=None, description="API 密钥")
    base_url: Optional[str] = Field(default=None, description="API 基础 URL")


class ModelPricingConfig(BaseModel):
    """模型定价配置"""
    input_per_million: float = Field(default=0.0, description="输入 Token 每百万个费用")
    output_per_million: float = Field(default=0.0, description="输出 Token 每百万个费用")
    currency: str = Field(default="CNY", description="货币单位")


# 默认场景列表（rag-platform 场景）
_DEFAULT_SCENES = [
    "report_generation",
    "assessment",
    "validation",
    "metadata_extraction",
    "query_rewrite",
    "query_routing",
    "content_generation",
    "vl_parsing",
    "ml_scoring",
    "rag_eval",
]


class LLMSettings(BaseSettings):
    """LLM 多提供商统一配置"""

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    dashscope_api_key: str = Field(default="", validation_alias="DASHSCOPE_API_KEY", description="DashScope API 密钥")
    openai_api_key: str = Field(default="", validation_alias="OPENAI_API_KEY", description="OpenAI API 密钥")
    anthropic_api_key: str = Field(default="", validation_alias="ANTHROPIC_API_KEY", description="Anthropic API 密钥")
    deepseek_api_key: str = Field(default="", validation_alias="DEEPSEEK_API_KEY", description="DeepSeek API 密钥")

    llm_multimodal_model_prefixes: List[str] = Field(
        default_factory=lambda: [
            "qwen-vl", "qwen-audio", "qwen-omni", "qwen-vl-plus", "qwen-vl-max",
            "qwen-vl-max-latest", "qwen-audio-turbo", "qwen-audio-turbo-latest",
            "qwen-omni-turbo", "qwen-omni-flash", "qwen3-omni-flash", "qwen3-omni-turbo",
        ],
        validation_alias="LLM_MULTIMODAL_MODEL_PREFIXES",
        description="多模态模型前缀列表",
    )

    es_url: str = Field(default="", validation_alias="ES_URL", description="Elasticsearch URL（向量后端）")
    milvus_host: str = Field(default="", validation_alias="MILVUS_HOST", description="Milvus 主机地址")
    milvus_port: int = Field(default=19530, validation_alias="MILVUS_PORT", description="Milvus 端口")

    @property
    def llm_providers(self) -> Dict[str, LLMProviderConfig]:
        """从 API Key 构建提供商配置字典"""
        providers = {}
        if self.dashscope_api_key:
            providers["dashscope"] = LLMProviderConfig(api_key=self.dashscope_api_key)
        if self.openai_api_key:
            providers["openai"] = LLMProviderConfig(
                api_key=self.openai_api_key,
                base_url="https://api.openai.com",
            )
        if self.anthropic_api_key:
            providers["anthropic"] = LLMProviderConfig(api_key=self.anthropic_api_key)
        if self.deepseek_api_key:
            providers["deepseek"] = LLMProviderConfig(
                api_key=self.deepseek_api_key,
                base_url="https://api.deepseek.com",
            )
        return providers

    @property
    def model_pricing(self) -> Dict[str, ModelPricingConfig]:
        """模型定价（默认 DashScope 定价）"""
        return {
            "qwen-turbo": ModelPricingConfig(input_per_million=0.3, output_per_million=0.6),
            "qwen-plus": ModelPricingConfig(input_per_million=0.8, output_per_million=2.0),
            "qwen-max": ModelPricingConfig(input_per_million=2.5, output_per_million=10.0),
            "qwen3-omni-flash": ModelPricingConfig(input_per_million=0.2, output_per_million=2.0),
        }

    @property
    def llm_scene_configs(self) -> Dict[str, LLMSceneConfig]:
        """从提供商配置构建场景配置字典（向后兼容）"""
        configs = {}
        for scene in _DEFAULT_SCENES:
            configs[scene] = LLMSceneConfig(
                provider="dashscope",
                model="qwen-plus",
            )
        return configs
