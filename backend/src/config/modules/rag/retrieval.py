"""RAG 检索配置：BM25/向量融合、重排序、查询路由、年龄过滤"""

from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings
from typing import Dict

BASE_DIR = Path(__file__).parent.parent.parent.parent.resolve()


class RagRetrievalSettings(BaseSettings):
    """RAG 检索配置"""

    # BM25 相关
    rag_hybrid_bm25_weight: float = Field(
        default=0.5,
        validation_alias="RAG_HYBRID_BM25_WEIGHT",
        description="混合检索 BM25 权重",
    )
    rag_hybrid_bm25_top_k: int = Field(
        default=10,
        validation_alias="RAG_HYBRID_BM25_TOP_K",
        description="BM25 返回 Top K",
    )
    bm25_scale_factor: float = Field(
        default=5, validation_alias="BM25_SCALE_FACTOR", description="BM25 分数缩放因子"
    )

    # 向量相关
    rag_hybrid_vector_weight: float = Field(
        default=0.5,
        validation_alias="RAG_HYBRID_VECTOR_WEIGHT",
        description="混合检索向量权重",
    )
    rag_hybrid_vector_top_k: int = Field(
        default=10,
        validation_alias="RAG_HYBRID_VECTOR_TOP_K",
        description="向量检索返回 Top K",
    )
    rag_vector_base_threshold: float = Field(
        default=0.5,
        validation_alias="RAG_VECTOR_BASE_THRESHOLD",
        description="向量检索最低分数阈值",
    )

    # 融合相关
    rag_hybrid_merge_mode: str = Field(
        default="OR",
        validation_alias="RAG_HYBRID_MERGE_MODE",
        description="合并模式：OR/AND",
    )
    rag_hybrid_bm25_weight_dense: float = Field(
        default=0.7,
        validation_alias="RAG_HYBRID_BM25_WEIGHT_DENSE",
        description="密集场景 BM25 权重",
    )
    rag_hybrid_vector_weight_dense: float = Field(
        default=0.3,
        validation_alias="RAG_HYBRID_VECTOR_WEIGHT_DENSE",
        description="密集场景向量权重",
    )
    rag_hybrid_base_threshold: float = Field(
        default=0.1,
        validation_alias="RAG_HYBRID_BASE_THRESHOLD",
        description="混合检索最低分数阈值",
    )
    rag_relative_cutoff_ratio: float = Field(
        default=0.3,
        validation_alias="RAG_RELATIVE_CUTOFF_RATIO",
        description="相对截断比例",
    )
    hybrid_weights: Dict[str, float] = Field(
        default_factory=lambda: {
            "default": 0.5,
            "keyword_query": 0.7,
            "semantic_query": 0.3,
        },
        description="不同查询类型的 BM25 权重",
    )

    # 查询权重动态策略
    rag_weight_strategy: str = Field(
        default="dynamic",
        validation_alias="RAG_WEIGHT_STRATEGY",
        description="权重策略：dynamic（动态）/ fixed（固定）",
    )
    rag_weight_by_query_type: Dict[str, Dict[str, float]] = Field(
        default_factory=lambda: {
            "short": {"bm25": 0.3, "vector": 0.7},
            "terminology": {"bm25": 0.7, "vector": 0.3},
            "descriptive": {"bm25": 0.4, "vector": 0.6},
            "complex": {"bm25": 0.5, "vector": 0.5},
            "default": {"bm25": 0.5, "vector": 0.5},
        },
        description="按查询类型的权重配置",
    )

    # 搜索页面专用
    rag_search_bm25_weight: float = Field(
        default=0.5,
        validation_alias="RAG_SEARCH_BM25_WEIGHT",
        description="搜索页面 BM25 权重",
    )
    rag_search_vector_weight: float = Field(
        default=0.5,
        validation_alias="RAG_SEARCH_VECTOR_WEIGHT",
        description="搜索页面向量权重",
    )
    rag_search_no_match_vector_penalty: float = Field(
        default=0.5,
        validation_alias="RAG_SEARCH_NO_MATCH_VECTOR_PENALTY",
        description="无关键词匹配惩罚",
    )
    rag_search_score_threshold_hybrid: float = Field(
        default=0.25,
        validation_alias="RAG_SEARCH_SCORE_THRESHOLD_HYBRID",
        description="搜索页面混合阈值",
    )
    rag_search_score_threshold_vector: float = Field(
        default=0.25,
        validation_alias="RAG_SEARCH_SCORE_THRESHOLD_VECTOR",
        description="搜索页面向量阈值",
    )
    rag_search_relative_cutoff_ratio: float = Field(
        default=0.5,
        validation_alias="RAG_SEARCH_RELATIVE_CUTOFF_RATIO",
        description="搜索页面截断比例",
    )
    rag_search_min_similarity_threshold: float = Field(
        default=0.2,
        validation_alias="RAG_SEARCH_MIN_SIMILARITY_THRESHOLD",
        description="搜索页面最小相似度",
    )

    # 重排序相关
    rag_reranker_provider: str = Field(
        default="local",
        validation_alias="RAG_RERANKER_PROVIDER",
        description="Reranker 提供商（local/cohere/voyage）",
    )
    rag_reranker_model: str = Field(
        default="BAAI/bge-reranker-v2-m3",
        validation_alias="RAG_RERANKER_MODEL",
        description="重排序模型",
    )
    rag_reranker_initial_k: int = Field(
        default=30,
        validation_alias="RAG_RERANKER_INITIAL_K",
        description="重排序前初始结果数",
    )
    rag_reranker_final_k: int = Field(
        default=5,
        validation_alias="RAG_RERANKER_FINAL_K",
        description="重排序后最终返回数",
    )

    # 查询路由相关
    rag_query_rewrite_enabled: bool = Field(
        default=True,
        validation_alias="RAG_QUERY_REWRITE_ENABLED",
        description="是否启用查询重写",
    )
    query_router_llm_enabled: bool = Field(
        default=True,
        validation_alias="QUERY_ROUTER_LLM_ENABLED",
        description="查询路由 LLM 开关",
    )
    query_router_confidence_threshold: float = Field(
        default=0.8,
        validation_alias="QUERY_ROUTER_CONFIDENCE_THRESHOLD",
        description="路由置信度阈值",
    )
    query_router_llm_max_retries: int = Field(
        default=2,
        validation_alias="QUERY_ROUTER_LLM_MAX_RETRIES",
        description="路由 LLM 最大重试次数",
    )

    # 年龄过滤相关
    rag_age_filter_mode: str = Field(
        default="strict",
        validation_alias="RAG_AGE_FILTER_MODE",
        description="年龄过滤模式：strict（严格）| loose（宽松）",
    )
    rag_age_filter_tolerance_strict: int = Field(
        default=1,
        validation_alias="RAG_AGE_FILTER_TOLERANCE_STRICT",
        description="严格模式 tolerance（岁）",
    )
    rag_age_filter_tolerance_loose: int = Field(
        default=2,
        validation_alias="RAG_AGE_FILTER_TOLERANCE_LOOSE",
        description="宽松模式 tolerance（岁）",
    )
    rag_age_filter_strictness: float = Field(
        default=0.7,
        validation_alias="RAG_AGE_FILTER_STRICTNESS",
        description="年龄过滤严格程度（向后兼容）",
    )
    rag_age_filter_tolerance: int = Field(
        default=2,
        validation_alias="RAG_AGE_FILTER_TOLERANCE",
        description="年龄容忍范围（岁）（向后兼容）",
    )
    rag_age_fit_weight: float = Field(
        default=0.3, validation_alias="RAG_AGE_FIT_WEIGHT", description="年龄适配度权重"
    )

    # 融合配置
    fusion_score_boost_for_pageindex: float = Field(
        default=1.2,
        validation_alias="FUSION_SCORE_BOOST_FOR_PAGEINDEX",
        description="PageIndex 分数提升",
    )
    fusion_hybrid_supplement_limit: int = Field(
        default=5,
        validation_alias="FUSION_HYBRID_SUPPLEMENT_LIMIT",
        description="混合补充限制",
    )
    fusion_dedup_normalize: bool = Field(
        default=True,
        validation_alias="FUSION_DEDUP_NORMALIZE",
        description="去重归一化",
    )

    # 去重相关
    rag_dedup_containment_threshold: float = Field(
        default=0.8,
        validation_alias="RAG_DEDUP_CONTAINMENT_THRESHOLD",
        description="去重包含关系阈值（较短内容占较长内容的比例）",
    )
    rag_dedup_length_diff_threshold: float = Field(
        default=0.2,
        validation_alias="RAG_DEDUP_LENGTH_DIFF_THRESHOLD",
        description="去重长度差异阈值（长度接近才进行相似度比较）",
    )
    rag_dedup_similarity_threshold: float = Field(
        default=0.9,
        validation_alias="RAG_DEDUP_SIMILARITY_THRESHOLD",
        description="去重相似度阈值（difflib.SequenceMatcher 比值）",
    )
    rag_dedup_prefix_check_length: int = Field(
        default=50,
        validation_alias="RAG_DEDUP_PREFIX_CHECK_LENGTH",
        description="去重前缀/后缀检查长度",
    )

    # 通用阈值
    rag_similarity_threshold: float = Field(
        default=0.7,
        validation_alias="RAG_SIMILARITY_THRESHOLD",
        description="相似度阈值",
    )
    rag_min_result_count: int = Field(
        default=3, validation_alias="RAG_MIN_RESULT_COUNT", description="最小结果数量"
    )
    rag_ocr_extraction_rate_threshold: float = Field(
        default=0.5,
        validation_alias="RAG_OCR_EXTRACTION_THRESHOLD",
        description="OCR 提取率阈值",
    )
    rag_ocr_min_avg_length_threshold: int = Field(
        default=100,
        validation_alias="RAG_OCR_MIN_AVG_TEXT_LENGTH",
        description="OCR 平均长度阈值",
    )

    class Config:
        env_file = str(BASE_DIR / ".env.dev")
        env_file_encoding = "utf-8"
