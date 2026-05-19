"""RAG 检索配置：混合检索、重排序、查询路由、融合、去重"""
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).parent.parent.parent.parent.parent.resolve()


class RagRetrievalSettings(BaseSettings):
    # 混合检索 BM25/向量权重
    rag_hybrid_bm25_weight: float = Field(
        default=0.5, validation_alias="RAG_HYBRID_BM25_WEIGHT", description="混合检索 BM25 权重"
    )
    rag_hybrid_vector_weight: float = Field(
        default=0.5, validation_alias="RAG_HYBRID_VECTOR_WEIGHT", description="混合检索向量权重"
    )
    rag_hybrid_bm25_top_k: int = Field(default=10, validation_alias="RAG_HYBRID_BM25_TOP_K", description="BM25 返回 Top K")
    rag_hybrid_vector_top_k: int = Field(default=10, validation_alias="RAG_HYBRID_VECTOR_TOP_K", description="向量检索返回 Top K")
    rag_hybrid_merge_mode: str = Field(default="OR", validation_alias="RAG_HYBRID_MERGE_MODE", description="合并模式：OR/AND")
    rag_hybrid_base_threshold: float = Field(
        default=0.1, validation_alias="RAG_HYBRID_BASE_THRESHOLD", description="混合检索最低分数阈值"
    )
    bm25_scale_factor: float = Field(default=5, validation_alias="BM25_SCALE_FACTOR", description="BM25 分数缩放因子")

    # 重排序
    rag_reranker_provider: str = Field(
        default="dashscope", validation_alias="RAG_RERANKER_PROVIDER", description="Reranker 提供商"
    )
    rag_reranker_model: str = Field(
        default="qwen3-rerank", validation_alias="RAG_RERANKER_MODEL", description="重排序模型"
    )
    rag_reranker_initial_k: int = Field(default=30, validation_alias="RAG_RERANKER_INITIAL_K", description="重排序前初始结果数")
    rag_reranker_final_k: int = Field(default=5, validation_alias="RAG_RERANKER_FINAL_K", description="重排序后最终返回数")

    # 查询路由
    rag_query_rewrite_enabled: bool = Field(
        default=True, validation_alias="RAG_QUERY_REWRITE_ENABLED", description="是否启用查询重写"
    )
    query_router_llm_enabled: bool = Field(
        default=True, validation_alias="QUERY_ROUTER_LLM_ENABLED", description="查询路由 LLM 开关"
    )
    query_router_confidence_threshold: float = Field(
        default=0.8, validation_alias="QUERY_ROUTER_CONFIDENCE_THRESHOLD", description="路由置信度阈值"
    )
    query_router_llm_max_retries: int = Field(
        default=2, validation_alias="QUERY_ROUTER_LLM_MAX_RETRIES", description="路由 LLM 最大重试次数"
    )

    # 融合
    fusion_hybrid_supplement_limit: int = Field(
        default=5, validation_alias="FUSION_HYBRID_SUPPLEMENT_LIMIT", description="混合补充限制"
    )
    fusion_dedup_normalize: bool = Field(
        default=True, validation_alias="FUSION_DEDUP_NORMALIZE", description="去重归一化"
    )

    # 去重
    rag_dedup_containment_threshold: float = Field(
        default=0.8, validation_alias="RAG_DEDUP_CONTAINMENT_THRESHOLD", description="去重包含关系阈值"
    )
    rag_dedup_similarity_threshold: float = Field(
        default=0.9, validation_alias="RAG_DEDUP_SIMILARITY_THRESHOLD", description="去重相似度阈值"
    )

    # 通用阈值
    rag_similarity_threshold: float = Field(
        default=0.7, validation_alias="RAG_SIMILARITY_THRESHOLD", description="相似度阈值"
    )
    rag_min_result_count: int = Field(default=3, validation_alias="RAG_MIN_RESULT_COUNT", description="最小结果数量")
    rag_relative_cutoff_ratio: float = Field(
        default=0.3, validation_alias="RAG_RELATIVE_CUTOFF_RATIO", description="相对截断比例"
    )

    # 搜索页面专用
    rag_search_bm25_weight: float = Field(
        default=0.5, validation_alias="RAG_SEARCH_BM25_WEIGHT", description="搜索页面 BM25 权重"
    )
    rag_search_vector_weight: float = Field(
        default=0.5, validation_alias="RAG_SEARCH_VECTOR_WEIGHT", description="搜索页面向量权重"
    )
    rag_search_score_threshold_hybrid: float = Field(
        default=0.003, validation_alias="RAG_SEARCH_SCORE_THRESHOLD_HYBRID", description="搜索页面混合阈值（RRF 分数）"
    )
    rag_search_score_threshold_vector: float = Field(
        default=0.003, validation_alias="RAG_SEARCH_SCORE_THRESHOLD_VECTOR", description="搜索页面向量阈值（RRF 分数）"
    )
    rag_search_min_similarity_threshold: float = Field(
        default=0.003, validation_alias="RAG_SEARCH_MIN_SIMILARITY_THRESHOLD", description="搜索页面最小相似度（RRF 分数）"
    )

    class Config:
        env_file = str(BASE_DIR / ".env")
        env_file_encoding = "utf-8"
