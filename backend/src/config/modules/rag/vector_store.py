from pathlib import Path
from typing import Dict

from pydantic import Field
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).parent.parent.parent.parent.parent.parent.resolve()

class VectorStoreSettings(BaseSettings):
    vector_store_type: str = Field(
        "chroma",
        validation_alias="VECTOR_STORE_TYPE",
        description="向量存储类型: chroma, pinecone, milvus, weaviate"
    )
    vector_store_config: dict = Field(
        default_factory=lambda: {
            "persist_dir": str(BASE_DIR / "app_data" / "storage" / "vector_store"),
            "collection_name": "child_development"
        },
        validation_alias="VECTOR_STORE_CONFIG",
        description="向量存储配置，根据不同类型填写对应参数"
    )
