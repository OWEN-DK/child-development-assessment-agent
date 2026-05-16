"""LLM 场景配置模型

提供 LLMSceneConfig Pydantic 模型用于配置校验。
被 core/llm/factory.py 和 core/llm/config_validator.py 引用。
"""
from typing import Any, Optional

from pydantic import BaseModel, Field


class LLMSceneConfig(BaseModel):
    """LLM 场景配置（每个业务场景的模型参数）

    用于 Pydantic 校验，确保从 MySQL 读取的配置符合约束。
    所有字段均有合理默认值，仅 model 字段必填。
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
