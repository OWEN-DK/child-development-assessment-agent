"""节点类型定义控制器

GET /api/v1/pipeline/node-types — 返回所有已注册节点类型及参数 Schema（供编辑器面板使用）。
"""
from fastapi import APIRouter

from src.core.pipeline.registry import registry
from src.schemas.common import APIResponse
from src.schemas.pipeline.node import NodeDefinition, NodeTypeList

router = APIRouter(prefix="/api/v1/pipeline", tags=["管道节点类型"])

# ── 28 种节点类型的显示元数据 ──────────────────────

_NODE_METADATA: dict[str, dict] = {
    # 查询理解（7 个）
    "query_rewrite": {
        "label": "查询改写", "category": "query", "category_icon": "SearchOutlined",
        "icon": "EditOutlined", "description": "使用 LLM 将用户查询改写为更适合检索的形式",
        "config_schema": {
            "model": {"type": "string", "default": "qwen-turbo", "label": "LLM 模型"},
            "prompt_template": {"type": "text", "default": "", "label": "提示词模板"},
            "max_retries": {"type": "integer", "default": 2, "min": 0, "max": 5, "label": "最大重试次数"},
        },
        "input_ports": ["str"], "output_ports": ["list[str]"],
    },
    "synonym_expand": {
        "label": "同义词扩展", "category": "query", "category_icon": "SearchOutlined",
        "icon": "ExpandOutlined", "description": "查同义词库扩展查询词",
        "config_schema": {
            "synonym_source": {"type": "select", "default": "builtin", "options": ["builtin", "domain", "custom"], "label": "同义词来源"},
            "max_synonyms": {"type": "integer", "default": 5, "min": 1, "max": 20, "label": "每词最大扩展数"},
            "expansion_mode": {"type": "select", "default": "key_terms", "options": ["all", "nouns_only", "key_terms"], "label": "扩展模式"},
        },
        "input_ports": ["str"], "output_ports": ["str"],
    },
    "query_decompose": {
        "label": "查询分解", "category": "query", "category_icon": "SearchOutlined",
        "icon": "SplitCellsOutlined", "description": "使用 LLM 将复杂查询拆解为子查询",
        "config_schema": {
            "model": {"type": "string", "default": "qwen-turbo", "label": "LLM 模型"},
            "max_subqueries": {"type": "integer", "default": 5, "min": 1, "max": 10, "label": "最大子查询数"},
            "decomposition_strategy": {"type": "select", "default": "auto", "options": ["parallel", "hierarchical", "auto"], "label": "分解策略"},
        },
        "input_ports": ["str"], "output_ports": ["list[str]"],
    },
    "term_normalize": {
        "label": "术语标准化", "category": "query", "category_icon": "SearchOutlined",
        "icon": "TranslationOutlined", "description": "查术语映射表替换非标准术语",
        "config_schema": {
            "terminology_source": {"type": "select", "default": "builtin", "options": ["builtin", "domain", "custom"], "label": "术语来源"},
            "normalize_mode": {"type": "select", "default": "both", "options": ["exact", "llm", "both"], "label": "标准化模式"},
            "model": {"type": "string", "default": "", "label": "LLM 模型（动态标准化时）"},
        },
        "input_ports": ["str"], "output_ports": ["str"],
    },
    "intent_classify": {
        "label": "意图分类", "category": "query", "category_icon": "SearchOutlined",
        "icon": "TagOutlined", "description": "使用 LLM 分类查询意图，支持条件边路由",
        "config_schema": {
            "model": {"type": "string", "default": "qwen-turbo", "label": "LLM 模型"},
            "categories": {"type": "json", "default": [], "label": "分类体系定义"},
            "routing_rules": {"type": "json", "default": {}, "label": "路由规则"},
        },
        "input_ports": ["str"], "output_ports": ["list[str]"],
    },
    "stopword_filter": {
        "label": "禁用词过滤", "category": "query", "category_icon": "SearchOutlined",
        "icon": "StopOutlined", "description": "正则/列表匹配移除禁用词",
        "config_schema": {
            "stop_words": {"type": "json", "default": [], "label": "禁用词列表"},
            "enabled": {"type": "boolean", "default": False, "label": "是否启用"},
            "case_sensitive": {"type": "boolean", "default": False, "label": "区分大小写"},
        },
        "input_ports": ["str"], "output_ports": ["str"],
    },
    "query_expand": {
        "label": "查询扩展", "category": "query", "category_icon": "SearchOutlined",
        "icon": "PlusCircleOutlined", "description": "使用 LLM 生成扩展查询变体",
        "config_schema": {
            "model": {"type": "string", "default": "qwen-turbo", "label": "LLM 模型"},
            "expansion_count": {"type": "integer", "default": 3, "min": 1, "max": 10, "label": "扩展查询数"},
            "expansion_method": {"type": "multi-select", "default": ["rewrite"], "options": ["rewrite", "constrain", "rephrase"], "label": "扩展方法"},
        },
        "input_ports": ["str"], "output_ports": ["list[str]"],
    },

    # 检索策略（5 个）
    "bm25_search": {
        "label": "BM25 检索", "category": "retrieval", "category_icon": "DatabaseOutlined",
        "icon": "FileSearchOutlined", "description": "关键词 BM25 检索，支持字段权重",
        "config_schema": {
            "top_k": {"type": "integer", "default": 10, "min": 1, "max": 200, "label": "返回数量"},
            "k1": {"type": "float", "default": 1.5, "min": 0.1, "max": 5.0, "label": "词频饱和度 k1"},
            "b": {"type": "float", "default": 0.75, "min": 0.0, "max": 1.0, "label": "文档长度归一化 b"},
            "field_weights": {"type": "json", "default": {"title": 2.0, "body": 1.0}, "label": "字段权重"},
            "score_threshold": {"type": "float", "default": 0.0, "min": 0.0, "max": 100.0, "label": "最低分数阈值"},
        },
        "input_ports": ["str"], "output_ports": ["list[Candidate]"],
    },
    "vector_search": {
        "label": "向量检索", "category": "retrieval", "category_icon": "DatabaseOutlined",
        "icon": "AimOutlined", "description": "向量相似度检索，支持 embedding 模型选择",
        "config_schema": {
            "embedding_model": {"type": "string", "default": "dashscope", "label": "Embedding 模型"},
            "top_k": {"type": "integer", "default": 10, "min": 1, "max": 200, "label": "返回数量"},
            "similarity_threshold": {"type": "float", "default": 0.0, "min": -1.0, "max": 1.0, "label": "相似度阈值"},
            "similarity_metric": {"type": "select", "default": "cosine", "options": ["cosine", "euclidean", "dot_product"], "label": "相似度度量"},
        },
        "input_ports": ["str"], "output_ports": ["list[Candidate]"],
    },
    "hybrid_search": {
        "label": "混合检索", "category": "retrieval", "category_icon": "DatabaseOutlined",
        "icon": "MergeCellsOutlined", "description": "BM25 + 向量并行检索 → RRF 融合",
        "config_schema": {
            "vector_weight": {"type": "float", "default": 0.6, "min": 0.0, "max": 1.0, "label": "向量权重"},
            "keyword_weight": {"type": "float", "default": 0.4, "min": 0.0, "max": 1.0, "label": "关键词权重"},
            "top_k": {"type": "integer", "default": 10, "min": 1, "max": 200, "label": "返回数量"},
            "fusion_method": {"type": "select", "default": "rrf", "options": ["rrf", "weighted_sum", "linear_combination"], "label": "融合方法"},
            "rrf_k": {"type": "integer", "default": 60, "min": 1, "max": 200, "label": "RRF k 常数"},
        },
        "input_ports": ["str"], "output_ports": ["list[Candidate]"],
    },
    "multimodal_search": {
        "label": "多模态检索", "category": "retrieval", "category_icon": "DatabaseOutlined",
        "icon": "PictureOutlined", "description": "文本/图片/表格多模态检索 → 融合",
        "config_schema": {
            "text_weight": {"type": "float", "default": 0.5, "min": 0.0, "max": 1.0, "label": "文本权重"},
            "image_weight": {"type": "float", "default": 0.3, "min": 0.0, "max": 1.0, "label": "图片权重"},
            "table_weight": {"type": "float", "default": 0.2, "min": 0.0, "max": 1.0, "label": "表格权重"},
            "top_k": {"type": "integer", "default": 10, "min": 1, "max": 200, "label": "返回数量"},
            "fusion_method": {"type": "select", "default": "rrf", "options": ["rrf", "weighted_sum"], "label": "融合方法"},
        },
        "input_ports": ["str"], "output_ports": ["list[Candidate]"],
    },
    "result_fusion": {
        "label": "结果融合", "category": "retrieval", "category_icon": "DatabaseOutlined",
        "icon": "ConsolidateOutlined", "description": "多分支 CandidateSet → RRF/加权融合",
        "config_schema": {
            "fusion_method": {"type": "select", "default": "rrf", "options": ["rrf", "weighted_sum", "linear_combination"], "label": "融合方法"},
            "weights": {"type": "json", "default": [], "label": "各分支权重"},
            "final_top_k": {"type": "integer", "default": 10, "min": 1, "max": 200, "label": "最终保留数"},
        },
        "input_ports": ["list[Candidate]"], "output_ports": ["list[Candidate]"],
    },

    # 安全合规（3 个）
    "sensitive_filter": {
        "label": "敏感词过滤", "category": "security", "category_icon": "SafetyOutlined",
        "icon": "FilterOutlined", "description": "敏感词列表/正则过滤检索结果",
        "config_schema": {
            "word_list": {"type": "json", "default": [], "label": "敏感词列表"},
            "filter_mode": {"type": "select", "default": "remove", "options": ["remove", "mask", "flag"], "label": "过滤模式"},
            "apply_to": {"type": "select", "default": "results", "options": ["query", "results", "both"], "label": "应用范围"},
        },
        "input_ports": ["any"], "output_ports": ["any"],
    },
    "pii_mask": {
        "label": "PII 脱敏", "category": "security", "category_icon": "SafetyOutlined",
        "icon": "EyeInvisibleOutlined", "description": "正则匹配脱敏：手机号/身份证/邮箱/姓名/地址/银行卡",
        "config_schema": {
            "target_types": {"type": "multi-select", "default": ["phone", "id_card", "email"], "options": ["phone", "id_card", "email", "name", "address", "bank_card"], "label": "脱敏目标"},
            "mask_char": {"type": "string", "default": "*", "label": "替换字符"},
            "preserve_pattern": {"type": "string", "default": "", "label": "保留格式正则"},
        },
        "input_ports": ["any"], "output_ports": ["any"],
    },
    "content_audit": {
        "label": "内容审核", "category": "security", "category_icon": "SafetyOutlined",
        "icon": "AuditOutlined", "description": "LLM/规则审核：色情/暴力/政治/违法/歧视/广告",
        "config_schema": {
            "model": {"type": "string", "default": "qwen-turbo", "label": "审核 LLM 模型"},
            "audit_rules": {"type": "multi-select", "default": ["porn", "violence", "illegal"], "options": ["porn", "violence", "politics", "illegal", "discrimination", "ad"], "label": "审核规则集"},
            "action": {"type": "select", "default": "filter", "options": ["filter", "flag", "reject"], "label": "命中后行为"},
            "threshold": {"type": "float", "default": 0.7, "min": 0.0, "max": 1.0, "label": "审核敏感度"},
        },
        "input_ports": ["any"], "output_ports": ["any"],
    },

    # 质量增强（4 个）
    "rerank": {
        "label": "重排序", "category": "quality", "category_icon": "TrophyOutlined",
        "icon": "OrderedListOutlined", "description": "DashScope rerank 或本地 cross-encoder 重排序",
        "config_schema": {
            "model": {"type": "string", "default": "gte-rerank", "label": "重排序模型"},
            "initial_k": {"type": "integer", "default": 30, "min": 5, "max": 200, "label": "送入候选数"},
            "final_k": {"type": "integer", "default": 5, "min": 1, "max": 50, "label": "输出保留数"},
        },
        "input_ports": ["list[Candidate]"], "output_ports": ["list[Candidate]"],
    },
    "dedup": {
        "label": "去重", "category": "quality", "category_icon": "TrophyOutlined",
        "icon": "DeleteOutlined", "description": "MinHash 或 embedding 相似度去重",
        "config_schema": {
            "method": {"type": "select", "default": "minhash", "options": ["minhash", "embedding"], "label": "去重方法"},
            "threshold": {"type": "float", "default": 0.85, "min": 0.0, "max": 1.0, "label": "相似度阈值"},
            "scope": {"type": "select", "default": "both", "options": ["intra_domain", "cross_doc", "both"], "label": "去重范围"},
        },
        "input_ports": ["list[Candidate]"], "output_ports": ["list[Candidate]"],
    },
    "hallucination_check": {
        "label": "幻觉检测", "category": "quality", "category_icon": "TrophyOutlined",
        "icon": "ExclamationCircleOutlined", "description": "使用 LLM 检测答案中的幻觉内容",
        "config_schema": {
            "model": {"type": "string", "default": "qwen-turbo", "label": "检测 LLM 模型"},
            "threshold": {"type": "float", "default": 0.5, "min": 0.0, "max": 1.0, "label": "检测阈值"},
            "action": {"type": "select", "default": "flag", "options": ["filter", "flag", "both"], "label": "命中后行为"},
        },
        "input_ports": ["any"], "output_ports": ["any"],
    },
    "citation_verify": {
        "label": "引用验证", "category": "quality", "category_icon": "TrophyOutlined",
        "icon": "LinkOutlined", "description": "使用 LLM 验证答案引用是否来自检索结果",
        "config_schema": {
            "mode": {"type": "select", "default": "lax", "options": ["strict", "lax"], "label": "验证模式"},
            "model": {"type": "string", "default": "qwen-turbo", "label": "验证 LLM 模型"},
        },
        "input_ports": ["any"], "output_ports": ["any"],
    },

    # 性能优化（2 个）
    "semantic_cache": {
        "label": "语义缓存", "category": "performance", "category_icon": "ThunderboltOutlined",
        "icon": "FieldTimeOutlined", "description": "Redis/内存语义缓存，命中跳过检索链",
        "config_schema": {
            "cache_backend": {"type": "select", "default": "redis", "options": ["redis", "memory"], "label": "缓存后端"},
            "similarity_threshold": {"type": "float", "default": 0.95, "min": 0.0, "max": 1.0, "label": "命中阈值"},
            "ttl": {"type": "integer", "default": 3600, "min": 0, "max": 86400, "label": "缓存过期时间 (s)"},
            "cache_key_strategy": {"type": "select", "default": "semantic", "options": ["exact", "semantic"], "label": "缓存键策略"},
            "max_cache_size": {"type": "integer", "default": 10000, "min": 1, "label": "最大缓存条目"},
            "cache_key_scope": {"type": "select", "default": "role_aware", "options": ["role_aware", "role_agnostic"], "label": "缓存键范围"},
        },
        "input_ports": ["str"], "output_ports": ["any"],
    },
    "rate_limiter": {
        "label": "速率限制", "category": "performance", "category_icon": "ThunderboltOutlined",
        "icon": "DashboardOutlined", "description": "令牌桶/滑动窗口/漏桶算法限流",
        "config_schema": {
            "max_qps": {"type": "integer", "default": 10, "min": 1, "max": 10000, "label": "每秒最大请求数"},
            "algorithm": {"type": "select", "default": "token_bucket", "options": ["token_bucket", "sliding_window", "leaky_bucket"], "label": "限流算法"},
            "scope": {"type": "select", "default": "per_pipeline", "options": ["per_domain", "per_pipeline", "per_user"], "label": "限流范围"},
            "action_on_limit": {"type": "select", "default": "reject", "options": ["queue", "reject", "degrade_cache"], "label": "超限行为"},
        },
        "input_ports": ["any"], "output_ports": ["any"],
    },

    # 答案合成（1 个）
    "structured_output": {
        "label": "结构化输出", "category": "synthesis", "category_icon": "FileTextOutlined",
        "icon": "CodeOutlined", "description": "使用 LLM 格式化为 JSON/Table/Markdown/自定义 Schema",
        "config_schema": {
            "output_format": {"type": "select", "default": "json", "options": ["json", "table", "markdown", "custom"], "label": "输出格式"},
            "schema_definition": {"type": "json", "default": {}, "label": "自定义 JSON Schema"},
            "model": {"type": "string", "default": "qwen-turbo", "label": "LLM 模型"},
            "strict_mode": {"type": "boolean", "default": True, "label": "严格模式"},
        },
        "input_ports": ["any"], "output_ports": ["any"],
    },

    # 聚合层（6 个）
    "query_analyzer": {
        "label": "查询分析", "category": "aggregation", "category_icon": "ApartmentOutlined",
        "icon": "RadarChartOutlined", "description": "使用 LLM 识别查询涉及的领域，输出 DomainPlan[]",
        "config_schema": {
            "model": {"type": "string", "default": "qwen-turbo", "label": "LLM 模型"},
            "max_domains": {"type": "integer", "default": 5, "min": 1, "max": 50, "label": "最大激活域数"},
            "min_confidence": {"type": "float", "default": 0.6, "min": 0.0, "max": 1.0, "label": "域激活阈值"},
            "domain_keywords": {"type": "json", "default": {}, "label": "各域触发关键词"},
        },
        "input_ports": ["str"], "output_ports": ["list[DomainPlan]"],
    },
    "domain_dispatch": {
        "label": "域分发", "category": "aggregation", "category_icon": "ApartmentOutlined",
        "icon": "SendOutlined", "description": "并行启动各域管道 + 权限裁剪（库级别过滤）",
        "config_schema": {
            "parallel": {"type": "boolean", "default": True, "label": "并行执行"},
            "timeout_ms": {"type": "integer", "default": 3000, "min": 100, "max": 60000, "label": "单域超时 (ms)"},
            "max_concurrency": {"type": "integer", "default": 5, "min": 1, "max": 50, "label": "最大并发域数"},
        },
        "input_ports": ["list[DomainPlan]"], "output_ports": ["list[DomainResult]"],
    },
    "cross_fusion": {
        "label": "跨域融合", "category": "aggregation", "category_icon": "ApartmentOutlined",
        "icon": "UngroupOutlined", "description": "多域结果 weighted RRF 融合",
        "config_schema": {
            "fusion_method": {"type": "select", "default": "weighted_rrf", "options": ["weighted_rrf", "weighted_sum", "priority_ordered"], "label": "融合方法"},
            "weights": {"type": "json", "default": [], "label": "各域权重"},
            "rrf_k": {"type": "integer", "default": 60, "min": 1, "max": 200, "label": "RRF k 常数"},
            "final_top_k": {"type": "integer", "default": 10, "min": 1, "max": 200, "label": "最终保留数"},
        },
        "input_ports": ["list[DomainResult]"], "output_ports": ["list[Candidate]"],
    },
    "cross_dedup": {
        "label": "跨域去重", "category": "aggregation", "category_icon": "ApartmentOutlined",
        "icon": "ScissorOutlined", "description": "MinHash/embedding 跨域文档去重",
        "config_schema": {
            "dedup_threshold": {"type": "float", "default": 0.85, "min": 0.0, "max": 1.0, "label": "相似度阈值"},
            "dedup_method": {"type": "select", "default": "minhash", "options": ["minhash", "embedding"], "label": "去重方法"},
        },
        "input_ports": ["list[Candidate]"], "output_ports": ["list[Candidate]"],
    },
    "conflict_detect": {
        "label": "冲突检测", "category": "aggregation", "category_icon": "ApartmentOutlined",
        "icon": "WarningOutlined", "description": "使用 LLM 检测跨域矛盾表述",
        "config_schema": {
            "model": {"type": "string", "default": "qwen-turbo", "label": "LLM 模型"},
            "enabled": {"type": "boolean", "default": True, "label": "是否启用"},
            "conflict_threshold": {"type": "float", "default": 0.7, "min": 0.0, "max": 1.0, "label": "矛盾检测敏感度"},
        },
        "input_ports": ["list[Candidate]"], "output_ports": ["ConflictReport"],
    },
    "unified_generate": {
        "label": "统一答案合成", "category": "aggregation", "category_icon": "ApartmentOutlined",
        "icon": "FileDoneOutlined", "description": "使用 LLM 综合多域结果生成最终答案",
        "config_schema": {
            "model": {"type": "string", "default": "qwen-turbo", "label": "LLM 模型"},
            "temperature": {"type": "float", "default": 0.3, "min": 0.0, "max": 2.0, "label": "温度"},
            "max_tokens": {"type": "integer", "default": 2048, "min": 1, "max": 32768, "label": "最大 Token"},
            "include_citations": {"type": "boolean", "default": True, "label": "标注来源域"},
            "citation_format": {"type": "select", "default": "inline", "options": ["inline", "footnote", "appendix"], "label": "引用格式"},
        },
        "input_ports": ["dict"], "output_ports": ["str"],
    },
}

# 类别显示信息
_CATEGORY_INFO = {
    "query": {"name": "查询理解", "icon": "SearchOutlined", "order": 1},
    "retrieval": {"name": "检索策略", "icon": "DatabaseOutlined", "order": 2},
    "security": {"name": "安全合规", "icon": "SafetyOutlined", "order": 3},
    "quality": {"name": "质量增强", "icon": "TrophyOutlined", "order": 4},
    "performance": {"name": "性能优化", "icon": "ThunderboltOutlined", "order": 5},
    "synthesis": {"name": "答案合成", "icon": "FileTextOutlined", "order": 6},
    "aggregation": {"name": "聚合层", "icon": "ApartmentOutlined", "order": 7},
}


@router.get("/node-types")
def get_node_types():
    """返回所有已注册节点类型及参数 Schema

    供编辑器节点面板使用。按类别分组返回。
    """
    registered_types = registry.list_types()

    categories_map: dict[str, list[dict]] = {}
    for node_type in registered_types:
        meta = _NODE_METADATA.get(node_type, {})
        category = meta.get("category", "unknown")

        if category not in categories_map:
            categories_map[category] = []

        executor_class = registry.get(node_type)
        try:
            instance = executor_class()
            input_type = instance.input_type
            output_type = instance.output_type
        except Exception:
            input_type = "any"
            output_type = "any"

        definition = NodeDefinition(
            type=node_type,
            label=meta.get("label", node_type),
            category=category,
            category_icon=meta.get("category_icon", ""),
            icon=meta.get("icon", ""),
            description=meta.get("description", ""),
            config_schema=meta.get("config_schema", {}),
            default_config={},
            input_ports=meta.get("input_ports", [input_type]),
            output_ports=meta.get("output_ports", [output_type]),
        )

        categories_map[category].append(definition.model_dump())

    # 按类别排序
    sorted_categories = []
    for cat_name, cat_info in sorted(_CATEGORY_INFO.items(), key=lambda x: x[1]["order"]):
        if cat_name in categories_map:
            sorted_categories.append({
                "name": cat_info["name"],
                "icon": cat_info["icon"],
                "types": categories_map[cat_name],
            })

    # 补充 unregistered 类别
    for cat_name, types in categories_map.items():
        if cat_name not in _CATEGORY_INFO:
            sorted_categories.append({
                "name": cat_name,
                "icon": "",
                "types": types,
            })

    return APIResponse.success(NodeTypeList(categories=sorted_categories))
