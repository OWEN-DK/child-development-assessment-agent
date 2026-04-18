"""LLM 多提供商配置模块

向后兼容设计：
- 保留旧的字符串字段（model_report_generation 等）从 .env 读取模型名称
- 新增 llm_providers 字典存储提供商凭证
- 新增 model_pricing 字典存储定价信息
- 业务代码可通过 settings.llm_scene_configs["report_generation"] 获取完整场景配置
"""

from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Dict, Optional
from pathlib import Path

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

    # ===== 新增：提供商凭证配置 =====
    llm_providers: Dict[str, LLMProviderConfig] = Field(
        default_factory=lambda: {
            "dashscope": LLMProviderConfig(
                api_key="",
                base_url=None,
                api_version=None,
            )
        },
        description="LLM 提供商凭证映射（支持 dashscope/openai/anthropic/ollama）",
    )

    # ===== 新增：模型定价配置 =====
    model_pricing: Dict[str, ModelPricingConfig] = Field(
        default_factory=lambda: {
            "qwen3.5-plus": ModelPricingConfig(
                input_per_million=0.004,
                output_per_million=0.012,
                currency="CNY",
            ),
            "qwen3.5-turbo": ModelPricingConfig(
                input_per_million=0.002,
                output_per_million=0.006,
                currency="CNY",
            ),
            "qwen3-omni-flash": ModelPricingConfig(
                input_per_million=0.001,
                output_per_million=0.003,
                currency="CNY",
            ),
        },
        description="模型定价配置（每百万 Token 费用，单位：元）",
    )

    # ===== 保留：旧的字符串字段（向后兼容）=====
    model_report_generation: str = Field(
        default="qwen3.5-plus",
        validation_alias="MODEL_REPORT_GENERATION",
        description="评估报告生成使用的模型",
    )
    model_assessment: str = Field(
        default="qwen3.5-plus",
        validation_alias="MODEL_ASSESSMENT",
        description="儿童发展评估使用的模型",
    )
    model_validation: str = Field(
        default="qwen3.5-turbo",
        validation_alias="MODEL_VALIDATION",
        description="结果校验使用的模型",
    )
    model_query_rewrite: str = Field(
        default="qwen3-omni-flash",
        validation_alias="MODEL_QUERY_REWRITE",
        description="查询重写使用的模型",
    )
    model_metadata_extraction: str = Field(
        default="qwen3-omni-flash",
        validation_alias="MODEL_METADATA_EXTRACTION",
        description="元数据提取使用的模型",
    )
    model_vl_parsing: str = Field(
        default="qwen3-omni-flash",
        validation_alias="MODEL_VL_PARSING",
        description="多模态内容解析使用的模型",
    )
    model_query_classification: str = Field(
        default="qwen3-omni-flash",
        validation_alias="MODEL_QUERY_CLASSIFICATION",
        description="查询分类使用的模型名称",
    )
    ml_scoring_qwen_model: str = Field(
        default="qwen3.5-turbo",
        validation_alias="ML_SCORING_QWEN_MODEL",
        description="大模型评分使用的模型名称",
    )

    # ===== 新增：从旧字段自动构建的场景配置 =====
    @property
    def llm_scene_configs(self) -> Dict[str, LLMSceneConfig]:
        """获取所有场景的完整配置（自动从旧字段构建）"""
        return {
            "report_generation": LLMSceneConfig(
                provider="dashscope",
                model=self.model_report_generation or "qwen3.5-plus",
            ),
            "assessment": LLMSceneConfig(
                provider="dashscope",
                model=self.model_assessment or "qwen3.5-plus",
            ),
            "validation": LLMSceneConfig(
                provider="dashscope",
                model=self.model_validation or "qwen3.5-turbo",
            ),
            "query_rewrite": LLMSceneConfig(
                provider="dashscope",
                model=self.model_query_rewrite or "qwen3-omni-flash",
            ),
            "metadata_extraction": LLMSceneConfig(
                provider="dashscope",
                model=self.model_metadata_extraction or "qwen3-omni-flash",
            ),
            "query_classification": LLMSceneConfig(
                provider="dashscope",
                model=self.model_query_classification or "qwen3-omni-flash",
            ),
            "vl_parsing": LLMSceneConfig(
                provider="dashscope",
                model=self.model_vl_parsing or "qwen3-omni-flash",
            ),
            "ml_scoring": LLMSceneConfig(
                provider="dashscope",
                model=self.ml_scoring_qwen_model or "qwen3.5-turbo",
            ),
            "content_generation": LLMSceneConfig(
                provider="dashscope",
                model=self.model_report_generation or "qwen3.5-plus",
            ),
        }

    def get_scene_config(self, scene: str) -> LLMSceneConfig:
        """获取指定场景的配置"""
        return self.llm_scene_configs.get(scene)
