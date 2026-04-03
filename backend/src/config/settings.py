from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
import os
from pathlib import Path
from typing import Dict, Any, List
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

    # Data directory config
    data_dir: str = Field("./data", validation_alias="DATA_DIR", description="Base directory for application data files")

    # RAG Configuration (individual fields)
    rag_hybrid_bm25_weight: float = Field(
        0.5, validation_alias="RAG_HYBRID_BM25_WEIGHT"
    )
    rag_hybrid_vector_weight: float = Field(
        0.5, validation_alias="RAG_HYBRID_VECTOR_WEIGHT"
    )
    # BM25分数校准配置
    bm25_scale_factor: float = Field(
        5, validation_alias="BM25_SCALE_FACTOR",
        description="BM25分数缩放因子，用于sigmoid校准到[0,1]区间"
    )
    # 混合检索动态权重配置
    hybrid_weights: Dict[str, float] = Field(
        default_factory=lambda: {
            "default": 0.5,
            "keyword_query": 0.7,
            "semantic_query": 0.3
        },
        description="不同查询类型的BM25权重配置"
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
        1024, validation_alias="RAG_EPUB_CHUNK_TARGET_SIZE"
    )
    rag_pdf_chunk_size: int = Field(1536, validation_alias="RAG_PDF_CHUNK_SIZE")
    rag_chunk_overlap: int = Field(200, validation_alias="RAG_CHUNK_OVERLAP")
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
        0.5, validation_alias="RAG_SEARCH_BM25_WEIGHT",
        description="降低 BM25 权重，避免校准后分数过度衰减"
    )
    rag_search_vector_weight: float = Field(
        0.5, validation_alias="RAG_SEARCH_VECTOR_WEIGHT",
        description="提高向量权重，平衡语义匹配分数"
    )
    rag_search_no_match_vector_penalty: float = Field(
        0.5, validation_alias="RAG_SEARCH_NO_MATCH_VECTOR_PENALTY",
        description="降低纯向量结果的惩罚力度"
    )
    rag_search_score_threshold_hybrid: float = Field(
        0.35, validation_alias="RAG_SEARCH_SCORE_THRESHOLD_HYBRID",
        description="混合检索阈值，业界推荐 0.35-0.5"
    )
    rag_search_score_threshold_vector: float = Field(
        0.35, validation_alias="RAG_SEARCH_SCORE_THRESHOLD_VECTOR",
        description="向量检索阈值，业界推荐 0.35-0.5"
    )
    rag_search_relative_cutoff_ratio: float = Field(
        0.5, validation_alias="RAG_SEARCH_RELATIVE_CUTOFF_RATIO",
        description="相对截断比例，保留 Top 50% 的结果"
    )
    rag_search_min_similarity_threshold: float = Field(
        0.2, validation_alias="RAG_SEARCH_MIN_SIMILARITY_THRESHOLD"
    )
    # RAG 年龄过滤配置
    rag_age_filter_strictness: float = Field(
        0.7,
        validation_alias="RAG_AGE_FILTER_STRICTNESS",
        description="年龄过滤严格程度，0-1，0 最宽松，1 最严格",
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
    
    # PageIndex 配置（增强：熔断、重试、降级）
    pageindex_enabled: bool = Field(
        default=False,
        validation_alias="PAGEINDEX_ENABLED"
    )
    pageindex_base_url: str = Field(
        default="https://api.pageindex.ai",
        validation_alias="PAGEINDEX_BASE_URL"
    )
    pageindex_api_key: str = Field(
        default="",
        validation_alias="PAGEINDEX_API_KEY"
    )
    pageindex_max_concurrency: int = Field(
        default=5,
        validation_alias="PAGEINDEX_MAX_CONCURRENCY"
    )
    pageindex_max_tree_depth: int = Field(
        default=3,
        validation_alias="PAGEINDEX_MAX_TREE_DEPTH"
    )
    pageindex_timeout_seconds: int = Field(
        default=10,
        validation_alias="PAGEINDEX_TIMEOUT_SECONDS"
    )
    # 熔断配置
    pageindex_circuit_breaker_failure_threshold: int = Field(
        default=5,
        validation_alias="PAGEINDEX_CIRCUIT_BREAKER_FAILURE_THRESHOLD"
    )
    pageindex_circuit_breaker_reset_timeout: int = Field(
        default=60,
        validation_alias="PAGEINDEX_CIRCUIT_BREAKER_RESET_TIMEOUT"
    )
    # 重试配置
    pageindex_max_retries: int = Field(
        default=3,
        validation_alias="PAGEINDEX_MAX_RETRIES"
    )
    pageindex_retry_base_delay: float = Field(
        default=0.5,
        validation_alias="PAGEINDEX_RETRY_BASE_DELAY"
    )
    pageindex_retry_max_delay: float = Field(
        default=10.0,
        validation_alias="PAGEINDEX_RETRY_MAX_DELAY"
    )
    # 降级配置
    pageindex_fallback_to_hybrid: bool = Field(
        default=True,
        validation_alias="PAGEINDEX_FALLBACK_TO_HYBRID"
    )
    
    # 查询分类器配置
    query_router_llm_enabled: bool = Field(
        default=True,
        validation_alias="QUERY_ROUTER_LLM_ENABLED"
    )
    model_query_classification: str = Field(
        default="qwen3-omni-flash",
        validation_alias="MODEL_QUERY_CLASSIFICATION"
    )
    query_router_confidence_threshold: float = Field(
        default=0.8,
        validation_alias="QUERY_ROUTER_CONFIDENCE_THRESHOLD"
    )
    query_router_llm_max_retries: int = Field(
        default=2,
        validation_alias="QUERY_ROUTER_LLM_MAX_RETRIES"
    )
    
    # 结果融合配置
    fusion_score_boost_for_pageindex: float = Field(
        default=1.2,
        validation_alias="FUSION_SCORE_BOOST_FOR_PAGEINDEX"
    )
    fusion_hybrid_supplement_limit: int = Field(
        default=5,
        validation_alias="FUSION_HYBRID_SUPPLEMENT_LIMIT"
    )
    fusion_dedup_normalize: bool = Field(
        default=True,
        validation_alias="FUSION_DEDUP_NORMALIZE"
    )

    # RAG 重排序器配置
    rag_reranker_model: str = Field(
        "BAAI/bge-reranker-v2-m3",
        validation_alias="RAG_RERANKER_MODEL",
        description="Cross-Encoder 重排序模型名称",
    )
    rag_reranker_initial_k: int = Field(
        30,
        validation_alias="RAG_RERANKER_INITIAL_K",
        description="重排序前初始检索结果数量",
    )
    rag_reranker_final_k: int = Field(
        5,
        validation_alias="RAG_RERANKER_FINAL_K",
        description="重排序后最终返回结果数量",
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
    
    # 分层内容生成配置
    rag_layered_content_enabled: bool = Field(True, validation_alias="RAG_LAYERED_CONTENT_ENABLED")
    rag_layered_content_enable_llm_generation: bool = Field(True, validation_alias="RAG_LAYERED_CONTENT_ENABLE_LLM_GENERATION")
    rag_layered_content_enable_local_fallback: bool = Field(True, validation_alias="RAG_LAYERED_CONTENT_ENABLE_LOCAL_FALLBACK")
    rag_layered_content_l0_max_length: int = Field(100, validation_alias="RAG_LAYERED_CONTENT_L0_MAX_LENGTH")
    rag_layered_content_l1_max_length: int = Field(500, validation_alias="RAG_LAYERED_CONTENT_L1_MAX_LENGTH")
    rag_layered_content_batch_size: int = Field(20, validation_alias="RAG_LAYERED_CONTENT_BATCH_SIZE")
    rag_layered_content_large_batch_threshold: int = Field(1000, validation_alias="RAG_LAYERED_CONTENT_LARGE_BATCH_THRESHOLD")
    rag_layered_content_large_batch_size: int = Field(10, validation_alias="RAG_LAYERED_CONTENT_LARGE_BATCH_SIZE")
    rag_layered_content_concurrency_limit: int = Field(8, validation_alias="RAG_LAYERED_CONTENT_CONCURRENCY_LIMIT")
    # Embedding 模型配置
    embedding_model_name: str = Field(
        "text-embedding-v4", validation_alias="EMBEDDING_MODEL_NAME"
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

    # 向量存储配置
    vector_store_type: str = Field(
        "chroma",
        validation_alias="VECTOR_STORE_TYPE",
        description="向量存储类型: chroma, pinecone, milvus, weaviate"
    )
    vector_store_config: dict = Field(
        default_factory=dict,
        validation_alias="VECTOR_STORE_CONFIG",
        description="向量存储配置，根据不同类型填写对应参数"
    )

    # 语义分块配置
    semantic_splitter_buffer_size: int = Field(
        5,
        validation_alias="SEMANTIC_SPLITTER_BUFFER_SIZE",
        description="语义分块时比较的前后段落数",
    )
    semantic_splitter_breakpoint_threshold: int = Field(
        90,
        validation_alias="SEMANTIC_SPLITTER_BREAKPOINT_THRESHOLD",
        description="语义分块相似度阈值（百分比），低于此值则分割",
    )
    semantic_splitter_chapter_buffer_size: int = Field(
        3,
        validation_alias="SEMANTIC_SPLITTER_CHAPTER_BUFFER_SIZE",
        description="长章节语义分块时比较的前后段落数",
    )
    semantic_splitter_chapter_breakpoint_threshold: int = Field(
        75,
        validation_alias="SEMANTIC_SPLITTER_CHAPTER_BREAKPOINT_THRESHOLD",
        description="长章节语义分块相似度阈值（百分比），低于此值则分割",
    )
    # 语义分块边界配置
    semantic_splitter_separators: List[str] = Field(
        default_factory=lambda: [
            "\n## ", "\n### ", "\n#### ",  # 标题边界
            "\n\n",                        # 段落边界
            "\n",                          # 换行边界
            "。", "！", "？",              # 中文句子结束
            ". ", "! ", "? "               # 英文句子结束
        ],
        description="语义分块优先使用的分隔符列表，按优先级排序"
    )
    
    # 规则元数据提取配置
    rule_metadata_development_domains: List[str] = Field(
        default_factory=lambda: [
            "粗大动作", "精细动作", "认知能力", "语言发展", "社交情感", "感觉统合"
        ],
        description="儿童发展领域标签列表"
    )
    rule_metadata_age_patterns: List[str] = Field(
        default_factory=lambda: [
            r"(\d+)~(\d+)个月", r"(\d+)-(\d+)个月", r"适合(\d+)到(\d+)岁", 
            r"(\d+)岁左右", r"(\d+)月龄", r"(\d+)岁"
        ],
        description="规则提取年龄的正则表达式列表"
    )
    rule_metadata_difficulty_easy_threshold: int = Field(
        300,
        description="内容长度低于此值判定为简单难度"
    )
    rule_metadata_difficulty_hard_threshold: int = Field(
        1000,
        description="内容长度高于此值判定为困难难度"
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
            "layered_content": {
                "enabled": self.rag_layered_content_enabled,
                "enable_llm_generation": self.rag_layered_content_enable_llm_generation,
                "enable_local_fallback": self.rag_layered_content_enable_local_fallback,
                "l0_max_length": self.rag_layered_content_l0_max_length,
                "l1_max_length": self.rag_layered_content_l1_max_length,
                "batch_size": self.rag_layered_content_batch_size,
                "large_batch_threshold": self.rag_layered_content_large_batch_threshold,
                "large_batch_size": self.rag_layered_content_large_batch_size,
                "concurrency_limit": self.rag_layered_content_concurrency_limit,
            }
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
        model_name=settings.embedding_model_name,
        api_key=settings.dashscope_api_key,
        embed_batch_size=settings.embedding_batch_size,
    )
except Exception as e:
    # 避免在导入阶段因配置错误导致整个应用崩溃
    import logging

    logging.getLogger("src.config.settings").error(
        f"Failed to initialize embedding model: {e}"
    )
