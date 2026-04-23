"""Embedding 配置模块（支持多提供商）"""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).parent.parent.parent.parent.resolve()


class EmbeddingSettings(BaseSettings):
    """Embedding 配置（支持多提供商）"""

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env.dev"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 向后兼容：旧的字符串字段
    embedding_model_name: str = Field(
        "text-embedding-v4",
        validation_alias="EMBEDDING_MODEL_NAME",
        description="向量嵌入模型名称",
    )
    embedding_max_text_length: int = Field(
        1536,
        validation_alias="EMBEDDING_MAX_TEXT_LENGTH",
        description="Embedding 文本最大长度（字符），超过此长度将被截断",
    )
    embedding_batch_size: int = Field(
        10,
        validation_alias="EMBEDDING_BATCH_SIZE",
        description="Embedding 批处理大小，降低可缓解 API 并发限制",
    )

    # 新增：提供商字段
    embedding_provider: str = Field(
        "dashscope",
        validation_alias="EMBEDDING_PROVIDER",
        description="Embedding 提供商（dashscope/openai/ollama）",
    )
    embedding_use_async_batch: bool = Field(
        False,
        validation_alias="EMBEDDING_USE_ASYNC_BATCH",
        description="是否使用异步批量 API（text-embedding-async-v2），适用于大规模文档导入",
    )
    embedding_async_batch_threshold: int = Field(
        50,
        validation_alias="EMBEDDING_ASYNC_BATCH_THRESHOLD",
        description="触发异步批量 API 的节点数量阈值，默认 50",
    )

    @property
    def embedding_config(self) -> dict:
        """获取完整的 Embedding 配置"""
        return {
            "provider": self.embedding_provider,
            "model": self.embedding_model_name,
            "batch_size": self.embedding_batch_size,
            "max_length": self.embedding_max_text_length,
            "use_async_batch": self.embedding_use_async_batch,
            "async_batch_threshold": self.embedding_async_batch_threshold,
        }
