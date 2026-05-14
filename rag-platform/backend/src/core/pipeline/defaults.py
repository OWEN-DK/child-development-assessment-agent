"""节点默认参数（L0 层）

所有 28 种节点类型的参数默认值。
四层配置覆盖：L3（API 参数） > L2（管道配置） > L1（租户覆盖） > L0（此处）
"""

NODE_DEFAULTS: dict[str, dict] = {
    # ── 查询理解（7 个）─────────────────────────────
    "query_rewrite": {
        "model": "qwen-turbo",
        "prompt_template": "请将以下查询改写为更适合检索的形式，保持语义不变：\n{query}",
        "max_retries": 2,
    },
    "synonym_expand": {
        "synonym_source": "builtin",
        "max_synonyms": 5,
        "expansion_mode": "key_terms",
    },
    "query_decompose": {
        "model": "qwen-turbo",
        "max_subqueries": 5,
        "decomposition_strategy": "auto",
    },
    "term_normalize": {
        "terminology_source": "domain",
        "normalize_mode": "both",
        "model": "qwen-turbo",
    },
    "intent_classify": {
        "model": "qwen-turbo",
        "categories": [],
        "routing_rules": {},
    },
    "stopword_filter": {
        "stop_words": [],
        "enabled": False,
        "case_sensitive": False,
    },
    "query_expand": {
        "model": "qwen-turbo",
        "expansion_count": 3,
        "expansion_method": ["rewrite", "add_constraint", "change_perspective"],
    },

    # ── 检索策略（5 个）─────────────────────────────
    "bm25_search": {
        "top_k": 10,
        "k1": 1.5,
        "b": 0.75,
        "field_weights": {"title": 2.0, "body": 1.0},
        "score_threshold": 0.0,
    },
    "vector_search": {
        "embedding_model": "text-embedding-v3",
        "top_k": 10,
        "similarity_threshold": 0.0,
        "similarity_metric": "cosine",
    },
    "hybrid_search": {
        "vector_weight": 0.6,
        "keyword_weight": 0.4,
        "top_k": 10,
        "fusion_method": "rrf",
        "rrf_k": 60,
    },
    "multimodal_search": {
        "weights": {"text": 1.0, "image": 0.5, "table": 0.5},
        "top_k": 10,
        "fusion_method": "rrf",
    },
    "result_fusion": {
        "fusion_method": "rrf",
        "weights": {},
        "final_top_k": 10,
        "rrf_k": 60,
    },

    # ── 安全合规（3 个）─────────────────────────────
    "sensitive_filter": {
        "word_list": [],
        "filter_mode": "remove",
        "apply_to": "results",
    },
    "pii_mask": {
        "target_types": ["phone", "id_card", "email"],
        "mask_char": "*",
        "preserve_pattern": "",
    },
    "content_audit": {
        "model": "qwen-turbo",
        "audit_rules": ["porn", "violence", "politics"],
        "action": "filter",
        "threshold": 0.7,
    },

    # ── 质量增强（4 个）─────────────────────────────
    "rerank": {
        "model": "gte-rerank",
        "initial_k": 30,
        "final_k": 5,
    },
    "dedup": {
        "method": "minhash",
        "threshold": 0.85,
        "scope": "both",
    },
    "hallucination_check": {
        "model": "qwen-turbo",
        "threshold": 0.5,
        "action": "flag",
    },
    "citation_verify": {
        "mode": "lax",
        "model": "qwen-turbo",
    },

    # ── 性能优化（2 个）─────────────────────────────
    "semantic_cache": {
        "cache_backend": "redis",
        "similarity_threshold": 0.95,
        "ttl": 3600,
        "cache_key_strategy": "semantic",
        "max_cache_size": 1000,
        "cache_key_scope": "role_aware",
    },
    "rate_limiter": {
        "max_qps": 50,
        "algorithm": "token_bucket",
        "scope": "per_pipeline",
        "action_on_limit": "reject",
    },

    # ── 答案合成（1 个）─────────────────────────────
    "structured_output": {
        "output_format": "json",
        "schema_definition": None,
        "model": "qwen-turbo",
        "strict_mode": False,
    },

    # ── 聚合层（6 个）─────────────────────────────
    "query_analyzer": {
        "model": "qwen-turbo",
        "max_domains": 5,
        "min_confidence": 0.6,
        "domain_keywords": {},
    },
    "domain_dispatch": {
        "parallel": True,
        "timeout_ms": 3000,
        "max_concurrency": 5,
    },
    "cross_fusion": {
        "fusion_method": "weighted_rrf",
        "weights": {},
        "rrf_k": 60,
        "final_top_k": 10,
    },
    "cross_dedup": {
        "dedup_threshold": 0.85,
        "dedup_method": "minhash",
    },
    "conflict_detect": {
        "model": "qwen-turbo",
        "enabled": True,
        "conflict_threshold": 0.7,
    },
    "unified_generate": {
        "model": "qwen-turbo",
        "temperature": 0.3,
        "max_tokens": 2048,
        "include_citations": True,
        "citation_format": "[{domain}] {source}",
    },
}
