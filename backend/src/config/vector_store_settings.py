from pydantic import Field
from pydantic_settings import BaseSettings
from typing import Dict

class VectorStoreSettings(BaseSettings):
    vector_store_type: str = Field(
        "chroma",
        validation_alias="VECTOR_STORE_TYPE",
        description="向量存储类型: chroma, pinecone, milvus, weaviate"
    )
    vector_store_config: dict = Field(
        default_factory=lambda: {
            "persist_dir": "./storage/vector_store",
            "collection_name": "child_development"
        },
        validation_alias="VECTOR_STORE_CONFIG",
        description="向量存储配置，根据不同类型填写对应参数"
    )
