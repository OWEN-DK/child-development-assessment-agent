"""存储路径配置"""
from pydantic import Field
from pydantic_settings import BaseSettings


class PathSettings(BaseSettings):
    data_dir: str = Field("./app_data/data", validation_alias="DATA_DIR", description="数据目录")
    rag_storage_dir: str = Field("./app_data/storage", validation_alias="RAG_STORAGE_DIR", description="RAG 存储目录")
    rag_temp_upload_dir: str = Field(
        "./app_data/temp_uploads", validation_alias="RAG_TEMP_UPLOAD_DIR", description="临时上传目录"
    )
