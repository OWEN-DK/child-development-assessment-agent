from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
import os
from pathlib import Path
from typing import Dict, Any
from llama_index.core import Settings
from llama_index.embeddings.dashscope import DashScopeEmbedding

# 获取当前文件所在目录的绝对路径
BASE_DIR = Path(__file__).parent.parent.parent.resolve()


class Settings(BaseSettings):
    app_name: str = "Child Development Assessment Agent"
    app_version: str = "0.1.0"
    debug: bool = True
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    app_reload: bool = True

    # Model Config
    dashscope_api_key: str = Field(default="", validation_alias="DASHSCOPE_API_KEY")

    # Model Names (individual fields for env override)
    model_report_generation: str = Field(
        "qwen3.5-plus", validation_alias="MODEL_REPORT_GENERATION"
    )
    model_assessment: str = Field("qwen3.5-plus", validation_alias="MODEL_ASSESSMENT")
    model_validation: str = Field("qwen3.5-turbo", validation_alias="MODEL_VALIDATION")
    model_query_rewrite: str = Field(
        "qwen3-omni-flash", validation_alias="MODEL_QUERY_REWRITE"
    )
    model_metadata_extraction: str = Field(
        "qwen3-omni-flash", validation_alias="MODEL_METADATA_EXTRACTION"
    )
    model_vl_parsing: str = Field(
        "qwen3-omni-flash", validation_alias="MODEL_VL_PARSING"
    )

    # Log Config
    log_level: str = Field("INFO", validation_alias="LOG_LEVEL")
    log_file: str = Field("./logs/app.log", validation_alias="LOG_FILE")

    # RAG Configuration (individual fields)
    rag_hybrid_bm25_weight: float = Field(
        0.5, validation_alias="RAG_HYBRID_BM25_WEIGHT"
    )
    rag_hybrid_vector_weight: float = Field(
        0.5, validation_alias="RAG_HYBRID_VECTOR_WEIGHT"
    )
    rag_hybrid_merge_mode: str = Field("OR", validation_alias="RAG_HYBRID_MERGE_MODE")
    rag_hybrid_bm25_top_k: int = Field(10, validation_alias="RAG_HYBRID_BM25_TOP_K")
    rag_hybrid_vector_top_k: int = Field(10, validation_alias="RAG_HYBRID_VECTOR_TOP_K")
    rag_cache_enabled: bool = Field(True, validation_alias="RAG_CACHE_ENABLED")
    rag_cache_max_size: int = Field(1000, validation_alias="RAG_CACHE_MAX_SIZE")
    rag_cache_ttl_seconds: int = Field(3600, validation_alias="RAG_CACHE_TTL_SECONDS")
    rag_query_rewrite_enabled: bool = Field(
        True, validation_alias="RAG_QUERY_REWRITE_ENABLED"
    )
    rag_similarity_threshold: float = Field(
        0.7, validation_alias="RAG_SIMILARITY_THRESHOLD"
    )
    rag_min_result_count: int = Field(3, validation_alias="RAG_MIN_RESULT_COUNT")
    # RAG 路径配置
    rag_storage_dir: str = Field("./storage", validation_alias="RAG_STORAGE_DIR")
    # RAG 分块配置
    rag_chunk_size: int = Field(1024, validation_alias="RAG_CHUNK_SIZE")
    rag_epub_chunk_target_size: int = Field(
        800, validation_alias="RAG_EPUB_CHUNK_TARGET_SIZE"
    )
    rag_pdf_chunk_size: int = Field(1536, validation_alias="RAG_PDF_CHUNK_SIZE")
    rag_chunk_overlap: int = Field(20, validation_alias="RAG_CHUNK_OVERLAP")
    # RAG OCR 配置
    rag_ocr_extraction_rate_threshold: float = Field(
        0.5, validation_alias="RAG_OCR_EXTRACTION_THRESHOLD"
    )
    rag_ocr_min_avg_length_threshold: int = Field(
        100, validation_alias="RAG_OCR_MIN_AVG_TEXT_LENGTH"
    )
    # RAG 混合检索密集模式配置
    rag_hybrid_bm25_weight_dense: float = Field(
        0.7, validation_alias="RAG_HYBRID_BM25_WEIGHT_DENSE"
    )
    rag_hybrid_vector_weight_dense: float = Field(
        0.3, validation_alias="RAG_HYBRID_VECTOR_WEIGHT_DENSE"
    )
    # RAG 阈值配置
    rag_hybrid_base_threshold: float = Field(
        0.1, validation_alias="RAG_HYBRID_BASE_THRESHOLD"
    )
    rag_vector_base_threshold: float = Field(
        0.5, validation_alias="RAG_VECTOR_BASE_THRESHOLD"
    )
    rag_relative_cutoff_ratio: float = Field(
        0.3, validation_alias="RAG_RELATIVE_CUTOFF_RATIO"
    )
    # RAG 搜索配置（前端搜索页面专用）
    rag_search_bm25_weight: float = Field(
        0.7, validation_alias="RAG_SEARCH_BM25_WEIGHT"
    )
    rag_search_vector_weight: float = Field(
        0.3, validation_alias="RAG_SEARCH_VECTOR_WEIGHT"
    )
    rag_search_no_match_vector_penalty: float = Field(
        0.3, validation_alias="RAG_SEARCH_NO_MATCH_VECTOR_PENALTY"
    )
    rag_search_score_threshold_hybrid: float = Field(
        0.1, validation_alias="RAG_SEARCH_SCORE_THRESHOLD_HYBRID"
    )
    rag_search_score_threshold_vector: float = Field(
        0.3, validation_alias="RAG_SEARCH_SCORE_THRESHOLD_VECTOR"
    )
    rag_search_relative_cutoff_ratio: float = Field(
        0.1, validation_alias="RAG_SEARCH_RELATIVE_CUTOFF_RATIO"
    )
    rag_search_min_similarity_threshold: float = Field(
        0.3, validation_alias="RAG_SEARCH_MIN_SIMILARITY_THRESHOLD"
    )
    # RAG 年龄过滤配置
    rag_age_filter_strictness: float = Field(
        0.7,
        validation_alias="RAG_AGE_FILTER_STRICTNESS",
        description="年龄过滤严格程度，0-1，0最宽松，1最严格",
    )
    rag_age_filter_tolerance: int = Field(
        2,
        validation_alias="RAG_AGE_FILTER_TOLERANCE",
        description="年龄过滤弹性容忍范围（岁）",
    )
    rag_age_fit_weight: float = Field(
        0.3,
        validation_alias="RAG_AGE_FIT_WEIGHT",
        description="年龄适配度在最终得分中的权重",
    )

    # RAG 自动持久化配置
    rag_auto_persist_enabled: bool = Field(
        True,
        validation_alias="RAG_AUTO_PERSIST_ENABLED",
        description="是否启用索引自动持久化",
    )
    rag_auto_persist_interval: int = Field(
        300,
        validation_alias="RAG_AUTO_PERSIST_INTERVAL",
        description="自动持久化间隔（秒），默认5分钟",
    )

    # RAG 性能配置
    rag_vl_max_workers: int = Field(2, validation_alias="RAG_VL_MAX_WORKERS")
    rag_upload_max_concurrent_tasks: int = Field(
        5, validation_alias="RAG_UPLOAD_MAX_CONCURRENT_TASKS"
    )
    rag_temp_upload_dir: str = Field(
        "./temp_uploads", validation_alias="RAG_TEMP_UPLOAD_DIR"
    )
    rag_metadata_extraction_concurrency: int = Field(
        20, validation_alias="RAG_METADATA_EXTRACTION_CONCURRENCY"
    )
    # Embedding 模型配置
    embedding_model_name: str = Field(
        "text-embedding-v2", validation_alias="EMBEDDING_MODEL_NAME"
    )
    embedding_max_text_length: int = Field(
        1536,
        validation_alias="EMBEDDING_MAX_TEXT_LENGTH",
        description="Embedding 文本最大长度（字符），超过此长度将被截断",
    )

    # 语义分块配置
    semantic_splitter_buffer_size: int = Field(
        3,
        validation_alias="SEMANTIC_SPLITTER_BUFFER_SIZE",
        description="语义分块时比较的前后段落数",
    )
    semantic_splitter_breakpoint_threshold: int = Field(
        95,
        validation_alias="SEMANTIC_SPLITTER_BREAKPOINT_THRESHOLD",
        description="语义分块相似度阈值（百分比），低于此值则分割",
    )
    semantic_splitter_chapter_buffer_size: int = Field(
        1,
        validation_alias="SEMANTIC_SPLITTER_CHAPTER_BUFFER_SIZE",
        description="长章节语义分块时比较的前后段落数",
    )
    semantic_splitter_chapter_breakpoint_threshold: int = Field(
        80,
        validation_alias="SEMANTIC_SPLITTER_CHAPTER_BREAKPOINT_THRESHOLD",
        description="长章节语义分块相似度阈值（百分比），低于此值则分割",
    )

    # ML评分配置
    ml_scoring_enabled: bool = Field(False, validation_alias="ML_SCORING_ENABLED")
    ml_scoring_mode: str = Field(
        "qwen", validation_alias="ML_SCORING_MODE"
    )  # qwen / xgboost
    ml_scoring_model_path: str = Field(
        "./models/scoring_xgb.model", validation_alias="ML_SCORING_MODEL_PATH"
    )
    ml_scoring_weight_ahp: float = Field(0.7, validation_alias="ML_SCORING_WEIGHT_AHP")
    ml_scoring_weight_ml: float = Field(0.3, validation_alias="ML_SCORING_WEIGHT_ML")
    ml_scoring_qwen_model: str = Field(
        "qwen3.5-turbo", validation_alias="ML_SCORING_QWEN_MODEL"
    )

    @property
    def llm_models(self) -> Dict[str, str]:
        return {
            "report_generation": self.model_report_generation,
            "assessment": self.model_assessment,
            "validation": self.model_validation,
            "query_rewrite": self.model_query_rewrite,
            "metadata_extraction": self.model_metadata_extraction,
        }

    @property
    def rag_config(self) -> Dict[str, Any]:
        return {
            "hybrid_retrieval": {
                "bm25_weight": self.rag_hybrid_bm25_weight,
                "vector_weight": self.rag_hybrid_vector_weight,
                "merge_mode": self.rag_hybrid_merge_mode,  # AND/OR
                "bm25_top_k": self.rag_hybrid_bm25_top_k,
                "vector_top_k": self.rag_hybrid_vector_top_k,
            },
            "cache": {
                "enabled": self.rag_cache_enabled,
                "max_size": self.rag_cache_max_size,  # Maximum number of cache entries
                "ttl_seconds": self.rag_cache_ttl_seconds,  # Cache expiration time in seconds (1 hour)
            },
            "query_rewrite": {"enabled": self.rag_query_rewrite_enabled},
            "filters": {
                "similarity_threshold": self.rag_similarity_threshold,
                "min_result_count": self.rag_min_result_count,
            },
        }

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env.dev"), env_file_encoding="utf-8", extra="ignore"
    )


settings = Settings()

# 全局配置LlamaIndex嵌入模型
from llama_index.core import Settings as LlamaSettings
from src.core.embedding import SafeDashScopeEmbedding

try:
    LlamaSettings.embed_model = SafeDashScopeEmbedding(
        model_name=settings.embedding_model_name, api_key=settings.dashscope_api_key
    )
except Exception as e:
    # 避免在导入阶段因配置错误导致整个应用崩溃
    import logging

    logging.getLogger("src.config.settings").error(
        f"Failed to initialize embedding model: {e}"
    )
