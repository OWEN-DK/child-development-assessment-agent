"""管道引擎模块

初始化时注册全部 28 种节点执行器。
"""
from src.core.pipeline.registry import registry

# 查询理解（7 个）
from src.core.pipeline.nodes.query import (
    IntentClassifyExecutor,
    QueryDecomposeExecutor,
    QueryExpandExecutor,
    QueryRewriteExecutor,
    StopwordFilterExecutor,
    SynonymExpandExecutor,
    TermNormalizeExecutor,
)

# 检索策略（5 个）
from src.core.pipeline.nodes.retrieval import (
    BM25SearchExecutor,
    HybridSearchExecutor,
    ResultFusionExecutor,
    VectorSearchExecutor,
)

# 安全合规（3 个）
from src.core.pipeline.nodes.security import (
    ContentAuditExecutor,
    PIIMaskExecutor,
    SensitiveFilterExecutor,
)

# 质量增强（4 个）
from src.core.pipeline.nodes.quality import (
    CitationVerifyExecutor,
    DedupExecutor,
    HallucinationCheckExecutor,
    RerankExecutor,
)

# 性能优化（2 个）
from src.core.pipeline.nodes.performance import RateLimiterExecutor, SemanticCacheExecutor

# 答案合成（1 个）
from src.core.pipeline.nodes.synthesis import StructuredOutputExecutor

# 聚合层（6 个）
from src.core.pipeline.nodes.aggregation import (
    ConflictDetectExecutor,
    CrossDedupExecutor,
    CrossFusionExecutor,
    DomainDispatchExecutor,
    QueryAnalyzerExecutor,
    UnifiedGenerateExecutor,
)


def register_all_nodes():
    """注册全部 28 种节点执行器"""
    # 查询理解
    registry.register("query_rewrite", QueryRewriteExecutor)
    registry.register("synonym_expand", SynonymExpandExecutor)
    registry.register("query_decompose", QueryDecomposeExecutor)
    registry.register("term_normalize", TermNormalizeExecutor)
    registry.register("intent_classify", IntentClassifyExecutor)
    registry.register("stopword_filter", StopwordFilterExecutor)
    registry.register("query_expand", QueryExpandExecutor)

    # 检索策略
    registry.register("bm25_search", BM25SearchExecutor)
    registry.register("vector_search", VectorSearchExecutor)
    registry.register("hybrid_search", HybridSearchExecutor)
    registry.register("result_fusion", ResultFusionExecutor)

    # 安全合规
    registry.register("sensitive_filter", SensitiveFilterExecutor)
    registry.register("pii_mask", PIIMaskExecutor)
    registry.register("content_audit", ContentAuditExecutor)

    # 质量增强
    registry.register("rerank", RerankExecutor)
    registry.register("dedup", DedupExecutor)
    registry.register("hallucination_check", HallucinationCheckExecutor)
    registry.register("citation_verify", CitationVerifyExecutor)

    # 性能优化
    registry.register("semantic_cache", SemanticCacheExecutor)
    registry.register("rate_limiter", RateLimiterExecutor)

    # 答案合成
    registry.register("structured_output", StructuredOutputExecutor)

    # 聚合层
    registry.register("query_analyzer", QueryAnalyzerExecutor)
    registry.register("domain_dispatch", DomainDispatchExecutor)
    registry.register("cross_fusion", CrossFusionExecutor)
    registry.register("cross_dedup", CrossDedupExecutor)
    registry.register("conflict_detect", ConflictDetectExecutor)
    registry.register("unified_generate", UnifiedGenerateExecutor)


# 模块加载时自动注册
register_all_nodes()
