from pydantic import Field
from pydantic_settings import BaseSettings

class EmbeddingSettings(BaseSettings):
    embedding_model_name: str = Field(
        "text-embedding-v4", validation_alias="EMBEDDING_MODEL_NAME",
        description="向量嵌入模型名称"
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
