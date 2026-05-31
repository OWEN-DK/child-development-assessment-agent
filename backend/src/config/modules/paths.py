from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).parent.parent.parent.parent.parent.resolve()

class PathSettings(BaseSettings):
    data_dir: str = Field(
        default=str(BASE_DIR / "app_data" / "data"),
        validation_alias="DATA_DIR",
        description="应用数据文件根目录"
    )
    rag_storage_dir: str = Field(
        default=str(BASE_DIR / "app_data" / "storage"),
        validation_alias="RAG_STORAGE_DIR",
        description="RAG索引和向量数据存储目录"
    )
    rag_temp_upload_dir: str = Field(
        default=str(BASE_DIR / "app_data" / "temp_uploads"),
        validation_alias="RAG_TEMP_UPLOAD_DIR",
        description="上传文件临时存储目录"
    )
    rag_books_dir: str = Field(
        default=str(BASE_DIR / "app_data" / "books"),
        validation_alias="RAG_BOOKS_DIR",
        description="上传书籍永久存储目录（处理完成后从临时目录移入）"
    )
