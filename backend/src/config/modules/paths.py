from pydantic import Field
from pydantic_settings import BaseSettings

class PathSettings(BaseSettings):
    data_dir: str = Field("./data", validation_alias="DATA_DIR", description="应用数据文件根目录")
    rag_storage_dir: str = Field("./storage", validation_alias="RAG_STORAGE_DIR",
        description="RAG索引和向量数据存储目录"
    )
    rag_temp_upload_dir: str = Field(
        "./temp_uploads", validation_alias="RAG_TEMP_UPLOAD_DIR",
        description="上传文件临时存储目录"
    )
