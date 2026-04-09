from pydantic import Field
from pydantic_settings import BaseSettings
from typing import Dict, Any, List

class RAGSettings(BaseSettings):
    rag_hybrid_bm25_weight: float = Field(
        0.5, validation_alias="RAG_HYBRID_BM25_WEIGHT",
        description="混合检索中BM25的默认权重"
    )
    rag_hybrid_vector_weight: float = Field(
        0.5, validation_alias="RAG_HYBRID_VECTOR_WEIGHT",
        description="混合检索中向量检索的默认权重"
    )
    bm25_scale_factor: float = Field(
        5, validation_alias="BM25_SCALE_FACTOR",
        description="BM25分数缩放因子，用于sigmoid校准到[0,1]区间"
    )
    hybrid_weights: Dict[str, float] = Field(
        default_factory=lambda: {
            "default": 0.5,
            "keyword_query": 0.7,
            "semantic_query": 0.3
        },
        description="不同查询类型的BM25权重配置"
    )
    rag_hybrid_merge_mode: str = Field("OR", validation_alias="RAG_HYBRID_MERGE_MODE",
        description="混合检索结果合并模式，OR表示取并集，AND表示取交集"
    )
    rag_hybrid_bm25_top_k: int = Field(10, validation_alias="RAG_HYBRID_BM25_TOP_K",
        description="BM25检索返回的Top K结果数量"
    )
    rag_hybrid_vector_top_k: int = Field(10, validation_alias="RAG_HYBRID_VECTOR_TOP_K",
        description="向量检索返回的Top K结果数量"
    )
    rag_cache_enabled: bool = Field(True, validation_alias="RAG_CACHE_ENABLED",
        description="是否启用RAG查询结果缓存"
    )
    rag_cache_max_size: int = Field(1000, validation_alias="RAG_CACHE_MAX_SIZE",
        description="RAG缓存的最大条目数"
    )
    rag_cache_ttl_seconds: int = Field(3600, validation_alias="RAG_CACHE_TTL_SECONDS",
        description="RAG缓存条目过期时间（秒）"
    )
    rag_query_rewrite_enabled: bool = Field(
        True, validation_alias="RAG_QUERY_REWRITE_ENABLED",
        description="是否启用查询重写功能"
    )
    rag_similarity_threshold: float = Field(
        0.7, validation_alias="RAG_SIMILARITY_THRESHOLD",
        description="向量检索相似度阈值，低于此值的结果将被过滤"
    )
    rag_min_result_count: int = Field(3, validation_alias="RAG_MIN_RESULT_COUNT",
        description="检索结果最小数量，不足时自动降低阈值"
    )
    rag_chunk_size: int = Field(1024, validation_alias="RAG_CHUNK_SIZE",
        description="默认文档分块大小（字符）"
    )
    rag_epub_chunk_target_size: int = Field(
        1024, validation_alias="RAG_EPUB_CHUNK_TARGET_SIZE",
        description="EPUB文档分块目标大小（字符）"
    )
    rag_pdf_chunk_size: int = Field(1536, validation_alias="RAG_PDF_CHUNK_SIZE",
        description="PDF文档分块大小（字符）"
    )
    rag_chunk_overlap: int = Field(200, validation_alias="RAG_CHUNK_OVERLAP",
        description="文档分块重叠大小（字符）"
    )
    rag_ocr_extraction_rate_threshold: float = Field(
        0.5, validation_alias="RAG_OCR_EXTRACTION_THRESHOLD",
        description="OCR提取率阈值，低于此值时判定为扫描版PDF"
    )
    rag_ocr_min_avg_length_threshold: int = Field(
        100, validation_alias="RAG_OCR_MIN_AVG_TEXT_LENGTH",
        description="PDF文本平均长度阈值，低于此值时启用OCR"
    )
    rag_hybrid_bm25_weight_dense: float = Field(
        0.7, validation_alias="RAG_HYBRID_BM25_WEIGHT_DENSE",
        description="密集场景下混合检索BM25权重"
    )
    rag_hybrid_vector_weight_dense: float = Field(
        0.3, validation_alias="RAG_HYBRID_VECTOR_WEIGHT_DENSE",
        description="密集场景下混合检索向量权重"
    )
    rag_hybrid_base_threshold: float = Field(
        0.1, validation_alias="RAG_HYBRID_BASE_THRESHOLD",
        description="混合检索结果最低分数阈值"
    )
    rag_vector_base_threshold: float = Field(
        0.5, validation_alias="RAG_VECTOR_BASE_THRESHOLD",
        description="向量检索结果最低分数阈值"
    )
    rag_relative_cutoff_ratio: float = Field(
        0.3, validation_alias="RAG_RELATIVE_CUTOFF_RATIO",
        description="检索结果相对截断比例，保留Top N%的结果"
    )
    rag_search_bm25_weight: float = Field(
        0.5, validation_alias="RAG_SEARCH_BM25_WEIGHT",
        description="搜索页面BM25权重，降低避免校准后分数过度衰减"
    )
    rag_search_vector_weight: float = Field(
        0.5, validation_alias="RAG_SEARCH_VECTOR_WEIGHT",
        description="搜索页面向量权重，提高平衡语义匹配分数"
    )
    rag_search_no_match_vector_penalty: float = Field(
        0.5, validation_alias="RAG_SEARCH_NO_MATCH_VECTOR_PENALTY",
        description="搜索页面纯向量结果的惩罚系数"
    )
    rag_search_score_threshold_hybrid: float = Field(
        0.25, validation_alias="RAG_SEARCH_SCORE_THRESHOLD_HYBRID",
        description="搜索页面混合检索分数阈值，推荐0.2-0.3"
    )
    rag_search_score_threshold_vector: float = Field(
        0.25, validation_alias="RAG_SEARCH_SCORE_THRESHOLD_VECTOR",
        description="搜索页面向量检索分数阈值，推荐0.2-0.3"
    )
    rag_search_relative_cutoff_ratio: float = Field(
        0.5, validation_alias="RAG_SEARCH_RELATIVE_CUTOFF_RATIO",
        description="搜索页面结果相对截断比例，保留Top 50%的结果"
    )
    rag_search_min_similarity_threshold: float = Field(
        0.2, validation_alias="RAG_SEARCH_MIN_SIMILARITY_THRESHOLD",
        description="搜索页面最小相似度阈值"
    )
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
    rag_vl_max_workers: int = Field(2, validation_alias="RAG_VL_MAX_WORKERS",
        description="多模态处理最大线程数"
    )
    rag_upload_max_concurrent_tasks: int = Field(
        5, validation_alias="RAG_UPLOAD_MAX_CONCURRENT_TASKS",
        description="文档上传最大并发任务数"
    )
    rag_metadata_extraction_concurrency: int = Field(
        20, validation_alias="RAG_METADATA_EXTRACTION_CONCURRENCY",
        description="元数据提取最大并发数"
    )
    rag_layered_content_enabled: bool = Field(True, validation_alias="RAG_LAYERED_CONTENT_ENABLED",
        description="是否启用分层内容生成功能"
    )
    rag_layered_content_enable_llm_generation: bool = Field(True, validation_alias="RAG_LAYERED_CONTENT_ENABLE_LLM_GENERATION",
        description="是否启用LLM内容生成"
    )
    rag_layered_content_enable_local_fallback: bool = Field(True, validation_alias="RAG_LAYERED_CONTENT_ENABLE_LOCAL_FALLBACK",
        description="是否启用本地知识库内容兜底"
    )
    rag_layered_content_l0_max_length: int = Field(100, validation_alias="RAG_LAYERED_CONTENT_L0_MAX_LENGTH",
        description="L0层（摘要）最大长度"
    )
    rag_layered_content_l1_max_length: int = Field(500, validation_alias="RAG_LAYERED_CONTENT_L1_MAX_LENGTH",
        description="L1层（详细）最大长度"
    )
    rag_layered_content_batch_size: int = Field(20, validation_alias="RAG_LAYERED_CONTENT_BATCH_SIZE",
        description="分层内容生成批处理大小"
    )
    rag_layered_content_large_batch_threshold: int = Field(1000, validation_alias="RAG_LAYERED_CONTENT_LARGE_BATCH_THRESHOLD",
        description="大批次内容阈值，超过则使用小批次处理"
    )
    rag_layered_content_large_batch_size: int = Field(10, validation_alias="RAG_LAYERED_CONTENT_LARGE_BATCH_SIZE",
        description="大批次处理时的批次大小"
    )
    rag_layered_content_concurrency_limit: int = Field(8, validation_alias="RAG_LAYERED_CONTENT_CONCURRENCY_LIMIT",
        description="分层内容生成最大并发数"
    )
    rag_monitoring_enabled: bool = Field(
        True,
        validation_alias="RAG_MONITORING_ENABLED",
        description="是否启用RAG监控",
    )
    rag_monitoring_log_level: str = Field(
        "INFO",
        validation_alias="RAG_MONITORING_LOG_LEVEL",
        description="监控日志级别",
    )
    rag_monitoring_metrics_interval: int = Field(
        60,
        validation_alias="RAG_MONITORING_METRICS_INTERVAL",
        description="指标采集间隔（秒）",
    )
