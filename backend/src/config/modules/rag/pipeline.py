"""RAG 导入流水线配置：解析/元数据提取/持久化/分层生成"""

from pydantic import Field
from pydantic_settings import BaseSettings


class RagPipelineSettings(BaseSettings):
    """RAG 导入流水线配置"""

    # 解析并发
    rag_vl_max_workers: int = Field(default=2, validation_alias="RAG_VL_MAX_WORKERS", description="VL 解析器最大并发线程数")
    rag_upload_max_concurrent_tasks: int = Field(default=5, validation_alias="RAG_UPLOAD_MAX_CONCURRENT_TASKS", description="文档上传最大并发任务数")
    rag_temp_upload_dir: str = Field(default="./temp_uploads", validation_alias="RAG_TEMP_UPLOAD_DIR", description="临时上传文件存储目录")

    # 元数据提取
    rag_metadata_extraction_concurrency: int = Field(default=20, validation_alias="RAG_METADATA_EXTRACTION_CONCURRENCY", description="元数据提取最大并发数")

    # 自动持久化
    rag_auto_persist_enabled: bool = Field(default=True, validation_alias="RAG_AUTO_PERSIST_ENABLED", description="是否启用自动持久化")
    rag_auto_persist_interval: int = Field(default=300, validation_alias="RAG_AUTO_PERSIST_INTERVAL", description="自动持久化间隔（秒）")

    # 分层内容生成
    rag_layered_content_enabled: bool = Field(default=True, validation_alias="RAG_LAYERED_CONTENT_ENABLED", description="是否启用分层内容生成")
    rag_layered_content_enable_llm_generation: bool = Field(default=True, validation_alias="RAG_LAYERED_CONTENT_ENABLE_LLM_GENERATION", description="是否启用 LLM 生成")
    rag_layered_content_enable_local_fallback: bool = Field(default=True, validation_alias="RAG_LAYERED_CONTENT_ENABLE_LOCAL_FALLBACK", description="是否启用本地知识库兜底")
    rag_layered_content_l0_max_length: int = Field(default=100, validation_alias="RAG_LAYERED_CONTENT_L0_MAX_LENGTH", description="L0 摘要最大长度")
    rag_layered_content_l1_max_length: int = Field(default=500, validation_alias="RAG_LAYERED_CONTENT_L1_MAX_LENGTH", description="L1 概览最大长度")
    rag_layered_content_batch_size: int = Field(default=20, validation_alias="RAG_LAYERED_CONTENT_BATCH_SIZE", description="分层生成批次大小")
    rag_layered_content_large_batch_threshold: int = Field(default=1000, validation_alias="RAG_LAYERED_CONTENT_LARGE_BATCH_THRESHOLD", description="大批次阈值")
    rag_layered_content_large_batch_size: int = Field(default=10, validation_alias="RAG_LAYERED_CONTENT_LARGE_BATCH_SIZE", description="大批次处理时的批次大小")
    rag_layered_content_concurrency_limit: int = Field(default=8, validation_alias="RAG_LAYERED_CONTENT_CONCURRENCY_LIMIT", description="分层生成最大并发数")

    class Config:
        env_file = ".env.dev"
        env_file_encoding = "utf-8"
