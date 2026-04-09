# 配置文件拆分与热更新实施方案计划

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按照设计文档拆分原有的settings.py配置文件，实现配置热更新能力，保持现有代码零修改兼容。

**Architecture:** 
- 按功能领域拆分配置到独立文件，每个文件职责单一
- 聚合所有配置到统一的Settings类，对外保持相同接口
- 使用watchdog监控配置文件变更，实现热更新能力
- 通过事件总线通知相关组件配置变更

**Tech Stack:** Python, Pydantic, Pydantic Settings, watchdog

---

## Chunk 1: 拆分后的配置文件创建

### Task 1: 创建app_settings.py

**Files:**
- Create: `backend/src/config/app_settings.py`

- [ ] **Step 1: 编写AppSettings类**

```python
from pydantic import Field
from pydantic_settings import BaseSettings

class AppSettings(BaseSettings):
    app_name: str = Field("Child Development Assessment Agent", description="应用名称")
    app_version: str = Field("0.1.0", description="应用版本号")
    debug: bool = Field(True, description="是否启用调试模式")
    app_host: str = Field("127.0.0.1", description="服务绑定IP地址")
    app_port: int = Field(8000, description="服务监听端口")
    app_reload: bool = Field(True, description="是否启用代码热重载")
```

- [ ] **Step 2: 验证文件语法正确**

Run: `cd /Users/owen/project/ai/child-development-assessment-agent && python -c "from backend.src.config.app_settings import AppSettings; print('AppSettings loaded successfully')"`
Expected: "AppSettings loaded successfully"

---

### Task 2: 创建model_settings.py

**Files:**
- Create: `backend/src/config/model_settings.py`

- [ ] **Step 1: 编写ModelSettings类**

```python
from pydantic import Field
from pydantic_settings import BaseSettings

class ModelSettings(BaseSettings):
    dashscope_api_key: str = Field(default="", validation_alias="DASHSCOPE_API_KEY", description="阿里云百炼API密钥")
    model_report_generation: str = Field(
        "qwen3.5-plus", validation_alias="MODEL_REPORT_GENERATION", description="评估报告生成使用的模型"
    )
    model_assessment: str = Field("qwen3.5-plus", validation_alias="MODEL_ASSESSMENT", description="儿童发展评估使用的模型")
    model_validation: str = Field("qwen3.5-turbo", validation_alias="MODEL_VALIDATION", description="结果校验使用的模型")
    model_query_rewrite: str = Field(
        "qwen3-omni-flash", validation_alias="MODEL_QUERY_REWRITE", description="查询重写使用的模型"
    )
    model_metadata_extraction: str = Field(
        "qwen3-omni-flash", validation_alias="MODEL_METADATA_EXTRACTION", description="元数据提取使用的模型"
    )
    model_vl_parsing: str = Field(
        "qwen3-omni-flash", validation_alias="MODEL_VL_PARSING", description="多模态内容解析使用的模型"
    )
    model_query_classification: str = Field(
        default="qwen3-omni-flash",
        validation_alias="MODEL_QUERY_CLASSIFICATION",
        description="查询分类使用的模型名称"
    )
    ml_scoring_qwen_model: str = Field(
        "qwen3.5-turbo", validation_alias="ML_SCORING_QWEN_MODEL",
        description="大模型评分使用的模型名称"
    )
```

- [ ] **Step 2: 验证文件语法正确**

Run: `cd /Users/owen/project/ai/child-development-assessment-agent && python -c "from backend.src.config.model_settings import ModelSettings; print('ModelSettings loaded successfully')"`
Expected: "ModelSettings loaded successfully"

---

### Task 3: 创建log_settings.py

**Files:**
- Create: `backend/src/config/log_settings.py`

- [ ] **Step 1: 编写LogSettings类**

```python
from pydantic import Field
from pydantic_settings import BaseSettings

class LogSettings(BaseSettings):
    log_level: str = Field("INFO", validation_alias="LOG_LEVEL", description="日志输出级别")
    log_file: str = Field("./logs/app.log", validation_alias="LOG_FILE", description="日志文件存储路径")
```

- [ ] **Step 2: 验证文件语法正确**

Run: `cd /Users/owen/project/ai/child-development-assessment-agent && python -c "from backend.src.config.log_settings import LogSettings; print('LogSettings loaded successfully')"`
Expected: "LogSettings loaded successfully"

---

### Task 4: 创建path_settings.py

**Files:**
- Create: `backend/src/config/path_settings.py`

- [ ] **Step 1: 编写PathSettings类**

```python
from pydantic import Field
from pydantic_settings import BaseSettings

class PathSettings(BaseSettings):
    data_dir: str = Field("./data", validation_alias="DATA_DIR", description="应用数据文件根目录")
    rag_storage_dir: str = Field("./storage", validation_alias="RAG_STORAGE_DIR",
        description="RAG索引和向量数据存储目录"
    )
    rag_temp_upload_dir: str = Field(
        "./temp_uploads", validation_alias="RAG_TEMP_UPLOAD_DIR",
        description="上传文件临时存储目录"
    )
```

- [ ] **Step 2: 验证文件语法正确**

Run: `cd /Users/owen/project/ai/child-development-assessment-agent && python -c "from backend.src.config.path_settings import PathSettings; print('PathSettings loaded successfully')"`
Expected: "PathSettings loaded successfully"

---

### Task 5: 创建rag_settings.py

**Files:**
- Create: `backend/src/config/rag_settings.py`

- [ ] **Step 1: 编写RAGSettings类**

```python
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
```

- [ ] **Step 2: 验证文件语法正确**

Run: `cd /Users/owen/project/ai/child-development-assessment-agent && python -c "from backend.src.config.rag_settings import RAGSettings; print('RAGSettings loaded successfully')"`
Expected: "RAGSettings loaded successfully"

---

### Task 6: 创建pageindex_settings.py

**Files:**
- Create: `backend/src/config/pageindex_settings.py`

- [ ] **Step 1: 编写PageIndexSettings类**

```python
from pydantic import Field
from pydantic_settings import BaseSettings

class PageIndexSettings(BaseSettings):
    pageindex_enabled: bool = Field(
        default=False,
        validation_alias="PAGEINDEX_ENABLED",
        description="是否启用PageIndex全网检索功能"
    )
    pageindex_base_url: str = Field(
        default="https://api.pageindex.ai",
        validation_alias="PAGEINDEX_BASE_URL",
        description="PageIndex服务API地址"
    )
    pageindex_api_key: str = Field(
        default="",
        validation_alias="PAGEINDEX_API_KEY",
        description="PageIndex服务API密钥"
    )
    pageindex_max_concurrency: int = Field(
        default=5,
        validation_alias="PAGEINDEX_MAX_CONCURRENCY",
        description="PageIndex最大并发请求数"
    )
    pageindex_max_tree_depth: int = Field(
        default=3,
        validation_alias="PAGEINDEX_MAX_TREE_DEPTH",
        description="PageIndex检索结果最大树深度"
    )
    pageindex_timeout_seconds: int = Field(
        default=10,
        validation_alias="PAGEINDEX_TIMEOUT_SECONDS",
        description="PageIndex请求超时时间（秒）"
    )
    pageindex_circuit_breaker_failure_threshold: int = Field(
        default=5,
        validation_alias="PAGEINDEX_CIRCUIT_BREAKER_FAILURE_THRESHOLD",
        description="PageIndex熔断失败次数阈值"
    )
    pageindex_circuit_breaker_reset_timeout: int = Field(
        default=60,
        validation_alias="PAGEINDEX_CIRCUIT_BREAKER_RESET_TIMEOUT",
        description="PageIndex熔断后自动重置时间（秒）"
    )
    pageindex_max_retries: int = Field(
        default=3,
        validation_alias="PAGEINDEX_MAX_RETRIES",
        description="PageIndex请求最大重试次数"
    )
    pageindex_retry_base_delay: float = Field(
        default=0.5,
        validation_alias="PAGEINDEX_RETRY_BASE_DELAY",
        description="PageIndex重试基础延迟（秒）"
    )
    pageindex_retry_max_delay: float = Field(
        default=10.0,
        validation_alias="PAGEINDEX_RETRY_MAX_DELAY",
        description="PageIndex重试最大延迟（秒）"
    )
    pageindex_fallback_to_hybrid: bool = Field(
        default=True,
        validation_alias="PAGEINDEX_FALLBACK_TO_HYBRID",
        description="PageIndex失败时是否降级到本地混合检索"
    )
```

- [ ] **Step 2: 验证文件语法正确**

Run: `cd /Users/owen/project/ai/child-development-assessment-agent && python -c "from backend.src.config.pageindex_settings import PageIndexSettings; print('PageIndexSettings loaded successfully')"`
Expected: "PageIndexSettings loaded successfully"

---

### Task 7: 创建query_fusion_settings.py

**Files:**
- Create: `backend/src/config/query_fusion_settings.py`

- [ ] **Step 1: 编写QueryFusionSettings类**

```python
from pydantic import Field
from pydantic_settings import BaseSettings

class QueryFusionSettings(BaseSettings):
    query_router_llm_enabled: bool = Field(
        default=True,
        validation_alias="QUERY_ROUTER_LLM_ENABLED",
        description="是否启用LLM查询路由分类功能"
    )
    query_router_confidence_threshold: float = Field(
        default=0.8,
        validation_alias="QUERY_ROUTER_CONFIDENCE_THRESHOLD",
        description="查询分类置信度阈值，低于此值使用 fallback 策略"
    )
    query_router_llm_max_retries: int = Field(
        default=2,
        validation_alias="QUERY_ROUTER_LLM_MAX_RETRIES",
        description="查询分类LLM调用最大重试次数"
    )
    fusion_score_boost_for_pageindex: float = Field(
        default=1.2,
        validation_alias="FUSION_SCORE_BOOST_FOR_PAGEINDEX",
        description="PageIndex结果的分数提升系数"
    )
    fusion_hybrid_supplement_limit: int = Field(
        default=5,
        validation_alias="FUSION_HYBRID_SUPPLEMENT_LIMIT",
        description="混合检索补充结果的最大数量"
    )
    fusion_dedup_normalize: bool = Field(
        default=True,
        validation_alias="FUSION_DEDUP_NORMALIZE",
        description="是否启用融合结果的去重和分数归一化"
    )
```

- [ ] **Step 2: 验证文件语法正确**

Run: `cd /Users/owen/project/ai/child-development-assessment-agent && python -c "from backend.src.config.query_fusion_settings import QueryFusionSettings; print('QueryFusionSettings loaded successfully')"`
Expected: "QueryFusionSettings loaded successfully"

---

### Task 8: 创建embedding_settings.py

**Files:**
- Create: `backend/src/config/embedding_settings.py`

- [ ] **Step 1: 编写EmbeddingSettings类**

```python
from pydantic import Field
from pydantic_settings import BaseSettings

class EmbeddingSettings(BaseSettings):
    embedding_model_name: str = Field(
        "text-embedding-v4", validation_alias="EMBEDDING_MODEL_NAME",
        description="向量嵌入模型名称"
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
```

- [ ] **Step 2: 验证文件语法正确**

Run: `cd /Users/owen/project/ai/child-development-assessment-agent && python -c "from backend.src.config.embedding_settings import EmbeddingSettings; print('EmbeddingSettings loaded successfully')"`
Expected: "EmbeddingSettings loaded successfully"

---

### Task 9: 创建vector_store_settings.py

**Files:**
- Create: `backend/src/config/vector_store_settings.py`

- [ ] **Step 1: 编写VectorStoreSettings类**

```python
from pydantic import Field
from pydantic_settings import BaseSettings
from typing import Dict

class VectorStoreSettings(BaseSettings):
    vector_store_type: str = Field(
        "chroma",
        validation_alias="VECTOR_STORE_TYPE",
        description="向量存储类型: chroma, pinecone, milvus, weaviate"
    )
    vector_store_config: dict = Field(
        default_factory=lambda: {
            "persist_dir": "./storage/vector_store",
            "collection_name": "child_development"
        },
        validation_alias="VECTOR_STORE_CONFIG",
        description="向量存储配置，根据不同类型填写对应参数"
    )
```

- [ ] **Step 2: 验证文件语法正确**

Run: `cd /Users/owen/project/ai/child-development-assessment-agent && python -c "from backend.src.config.vector_store_settings import VectorStoreSettings; print('VectorStoreSettings loaded successfully')"`
Expected: "VectorStoreSettings loaded successfully"

---

### Task 10: 创建semantic_splitter_settings.py

**Files:**
- Create: `backend/src/config/semantic_splitter_settings.py`

- [ ] **Step 1: 编写SemanticSplitterSettings类**

```python
from pydantic import Field
from pydantic_settings import BaseSettings
from typing import List

class SemanticSplitterSettings(BaseSettings):
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
```

- [ ] **Step 2: 验证文件语法正确**

Run: `cd /Users/owen/project/ai/child-development-assessment-agent && python -c "from backend.src.config.semantic_splitter_settings import SemanticSplitterSettings; print('SemanticSplitterSettings loaded successfully')"`
Expected: "SemanticSplitterSettings loaded successfully"

---

### Task 11: 创建ml_scoring_settings.py

**Files:**
- Create: `backend/src/config/ml_scoring_settings.py`

- [ ] **Step 1: 编写MLScoringSettings类**

```python
from pydantic import Field
from pydantic_settings import BaseSettings

class MLScoringSettings(BaseSettings):
    ml_scoring_enabled: bool = Field(False, validation_alias="ML_SCORING_ENABLED",
        description="是否启用ML智能评分功能"
    )
    ml_scoring_mode: str = Field(
        "qwen", validation_alias="ML_SCORING_MODE",
        description="评分模式：qwen(大模型评分)/xgboost(机器学习模型评分)"
    )
    ml_scoring_model_path: str = Field(
        "./models/scoring_xgb.model", validation_alias="ML_SCORING_MODEL_PATH",
        description="XGBoost评分模型文件路径"
    )
    ml_scoring_weight_ahp: float = Field(0.7, validation_alias="ML_SCORING_WEIGHT_AHP",
        description="层次分析法评分权重"
    )
    ml_scoring_weight_ml: float = Field(0.3, validation_alias="ML_SCORING_WEIGHT_ML",
        description="机器学习评分权重"
    )
```

- [ ] **Step 2: 验证文件语法正确**

Run: `cd /Users/owen/project/ai/child-development-assessment-agent && python -c "from backend.src.config.ml_scoring_settings import MLScoringSettings; print('MLScoringSettings loaded successfully')"`
Expected: "MLScoringSettings loaded successfully"

---

## Chunk 2: 配置聚合入口与热更新实现

### Task 12: 实现__init__.py聚合配置和热更新逻辑

**Files:**
- Create: `backend/src/config/__init__.py`

- [ ] **Step 1: 编写聚合配置和热更新逻辑**

```python
import os
import logging
from pathlib import Path
from typing import Dict, Any, List
from dataclasses import dataclass
from pydantic_settings import SettingsConfigDict
from threading import RLock
import asyncio
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# 导入各个配置类
from .app_settings import AppSettings
from .model_settings import ModelSettings
from .rag_settings import RAGSettings
from .log_settings import LogSettings
from .path_settings import PathSettings
from .pageindex_settings import PageIndexSettings
from .query_fusion_settings import QueryFusionSettings
from .embedding_settings import EmbeddingSettings
from .vector_store_settings import VectorStoreSettings
from .semantic_splitter_settings import SemanticSplitterSettings
from .ml_scoring_settings import MLScoringSettings

logger = logging.getLogger(__name__)
BASE_DIR = Path(__file__).parent.parent.parent.resolve()

@dataclass
class ConfigFieldMetadata:
    key: str
    category: str
    description: str
    hot_reloadable: bool
    requires_restart: bool
    affected_components: list[str]
    field_type: str
    default_value: Any


class Settings(
    AppSettings,
    ModelSettings,
    RAGSettings,
    LogSettings,
    PathSettings,
    PageIndexSettings,
    QueryFusionSettings,
    EmbeddingSettings,
    VectorStoreSettings,
    SemanticSplitterSettings,
    MLScoringSettings,
):
    """统一的配置类，聚合所有拆分后的配置"""
    
    # 规则相关配置（合并到rules.py体系）
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

    def _infer_category(self, field_name: str) -> str:
        if field_name.startswith(("rag_hybrid_", "rag_search_", "rag_cache_")):
            return "混合检索配置"
        elif field_name.startswith("model_"):
            return "模型设置"
        elif field_name.startswith("rag_reranker_"):
            return "重排序配置"
        elif field_name.startswith(("rag_chunk_", "semantic_splitter_")):
            return "分块配置"
        elif field_name.startswith("embedding_"):
            return "Embedding配置"
        elif field_name.startswith("pageindex_"):
            return "PageIndex配置"
        elif field_name.startswith("rag_"):
            return "RAG配置"
        elif field_name.startswith("ml_"):
            return "ML评分配置"
        elif field_name.startswith("query_router_") or field_name.startswith("fusion_"):
            return "查询与融合配置"
        elif field_name.startswith("rule_metadata_"):
            return "规则元数据配置"
        elif field_name.startswith("log_"):
            return "日志配置"
        elif field_name.startswith("data_dir") or field_name.startswith("rag_storage_dir"):
            return "路径配置"
        elif field_name.startswith("rule_validation_"):
            return "校验规则配置"
        elif field_name.startswith("rule_assessment_"):
            return "评估规则配置"
        elif field_name.startswith("rule_scoring_"):
            return "评分规则配置"
        elif field_name.startswith("rule_preprocessing_"):
            return "预处理规则配置"
        elif field_name.startswith("rule_metadata_"):
            return "元数据提取规则配置"
        else:
            return "其他配置"

    def _is_hot_reloadable(self, field_name: str) -> bool:
        hot_reload_prefixes = (
            "rag_hybrid_", "rag_search_", "rag_cache_", "rag_reranker_",
            "rag_similarity_threshold", "rag_min_result_count",
            "rag_age_filter_", "query_router_", "fusion_",
            "rag_layered_content_", "bm25_scale_factor",
            "hybrid_weights", "rag_chunk_", "semantic_splitter_",
            "embedding_batch_size", "rule_",
        )
        cold_reload_prefixes = (
            "model_", "dashscope_api_key", "pageindex_",
            "rag_storage_dir", "data_dir", "log_",
            "vector_store_", "ml_scoring_model_path",
            "rag_upload_max_concurrent_tasks", "rag_temp_upload_dir",
            "rag_metadata_extraction_concurrency", "rag_vl_max_workers",
        )
        if field_name.startswith(hot_reload_prefixes):
            return True
        if field_name.startswith(cold_reload_prefixes):
            return False
        return True

    def _get_affected_components(self, field_name: str) -> list[str]:
        components = []
        if "hybrid" in field_name or "search" in field_name:
            components.append("混合检索引擎")
        if "reranker" in field_name:
            components.append("重排序器")
        if "chunk" in field_name or "splitter" in field_name:
            components.append("文档分块")
        if "embedding" in field_name:
            components.append("Embedding模型")
        if "cache" in field_name:
            components.append("缓存系统")
        if "age_filter" in field_name:
            components.append("年龄过滤")
        if "pageindex" in field_name:
            components.append("PageIndex服务")
        if "query_router" in field_name or "fusion" in field_name:
            components.append("查询路由与融合")
        if "layered_content" in field_name:
            components.append("分层内容生成")
        if not components:
            components.append("通用配置")
        return components

    def get_all_config_metadata(self) -> Dict[str, ConfigFieldMetadata]:
        metadata = {}
        for field_name, field_info in self.model_fields.items():
            category = self._infer_category(field_name)
            hot_reloadable = self._is_hot_reloadable(field_name)
            annotation = field_info.annotation
            type_name = annotation.__name__ if hasattr(annotation, '__name__') else str(annotation)
            metadata[field_name] = ConfigFieldMetadata(
                key=field_name,
                category=category,
                description=field_info.description or "",
                hot_reloadable=hot_reloadable,
                requires_restart=not hot_reloadable,
                affected_components=self._get_affected_components(field_name),
                field_type=type_name,
                default_value=field_info.default
            )
        return metadata

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


# 配置实例管理
_settings_instance = None
_lock = RLock()

def get_settings() -> Settings:
    """获取配置单例"""
    global _settings_instance
    if _settings_instance is None:
        with _lock:
            if _settings_instance is None:
                _settings_instance = Settings()
    return _settings_instance

def reload_settings() -> Settings:
    """重新加载配置并返回新的Settings实例
    
    实现失败回退机制：重载失败时返回原有配置实例
    """
    global _settings_instance
    with _lock:
        try:
            new_settings = Settings()
            # 执行Pydantic校验，确保配置合法
            new_settings.model_validate(new_settings.model_dump())
            old_settings = _settings_instance
            _settings_instance = new_settings
            logger.info("配置重载成功")
            
            # 对比变更并派发事件
            if old_settings:
                changed_fields = compare_config_changes(old_settings, new_settings)
                if changed_fields:
                    logger.info(f"配置变更字段: {list(changed_fields.keys())}")
                    # TODO: 集成事件总线，派发ConfigChangedEvent
                    
            return new_settings
        except Exception as e:
            logger.error(f"配置重载失败，保留原有配置: {e}")
            return _settings_instance if _settings_instance else Settings()

def compare_config_changes(old_settings: Settings, new_settings: Settings) -> Dict[str, tuple[Any, Any]]:
    """比较新旧配置的差异"""
    changes = {}
    for field_name in old_settings.model_fields.keys():
        old_value = getattr(old_settings, field_name)
        new_value = getattr(new_settings, field_name)
        if old_value != new_value:
            changes[field_name] = (old_value, new_value)
    return changes


# 文件系统监控实现
class ConfigFileChangeHandler(FileSystemEventHandler):
    """配置文件变更处理器"""
    def on_modified(self, event):
        if event.is_directory:
            return
        file_path = Path(event.src_path)
        if file_path.suffix in ('.py', '.env') and not file_path.name.startswith('__'):
            logger.info(f"检测到配置文件变更: {file_path}")
            reload_settings()

def start_config_watcher() -> Observer:
    """启动配置文件监控"""
    event_handler = ConfigFileChangeHandler()
    observer = Observer()
    # 监控配置目录
    config_dir = Path(__file__).parent
    observer.schedule(event_handler, str(config_dir), recursive=False)
    # 监控.env文件
    env_file = BASE_DIR / ".env.dev"
    if env_file.exists():
        observer.schedule(event_handler, str(env_file), recursive=False)
    observer.start()
    logger.info("配置文件监控已启动")
    return observer


# 对外导出统一的settings实例
settings = get_settings()

# 初始化嵌入模型（保持与原逻辑一致）
try:
    from llama_index.core import Settings as LlamaSettings
    from src.core.embedding import SafeDashScopeEmbedding
    
    LlamaSettings.embed_model = SafeDashScopeEmbedding(
        model_name=settings.embedding_model_name,
        api_key=settings.dashscope_api_key,
        embed_batch_size=settings.embedding_batch_size,
    )
except Exception as e:
    logger.error(f"Failed to initialize embedding model: {e}")


__all__ = [
    "Settings",
    "settings",
    "get_settings",
    "reload_settings",
    "start_config_watcher",
    "ConfigFieldMetadata",
]
```

- [ ] **Step 2: 验证文件语法正确**

Run: `cd /Users/owen/project/ai/child-development-assessment-agent && python -c "from backend.src.config import settings; print('Settings loaded successfully, app_name:', settings.app_name)"`
Expected: "Settings loaded successfully, app_name: Child Development Assessment Agent"

---

## Chunk 3: 兼容过渡与测试

### Task 13: 修改原settings.py实现兼容过渡

**Files:**
- Modify: `backend/src/config/settings.py`

- [ ] **Step 1: 更新settings.py内容**

```python
import warnings
import logging

# 弃用警告
warnings.warn(
    "src.config.settings 已弃用，请迁移到 src.config import settings",
    DeprecationWarning,
    stacklevel=2
)

# 重定向到新的配置实例
from src.config import settings, Settings, ConfigFieldMetadata

logger = logging.getLogger("src.config.settings")
logger.warning("src.config.settings 已弃用，请迁移到 src.config import settings")

__all__ = ["settings", "Settings", "ConfigFieldMetadata"]
```

- [ ] **Step 2: 验证向后兼容性**

Run: `cd /Users/owen/project/ai/child-development-assessment-agent && python -Wd -c "from src.config.settings import settings; print('Legacy import works, app_version:', settings.app_version)"`
Expected: 看到DeprecationWarning，然后输出 "Legacy import works, app_version: 0.1.0"

---

### Task 14: 验证配置正确性

- [ ] **Step 1: 验证所有配置字段存在且值正确**

Run: `cd /Users/owen/project/ai/child-development-assessment-agent && python -c "
from src.config import settings
from src.config.settings import settings as old_settings

# 比较新旧配置的字段
new_fields = set(settings.model_fields.keys())
old_fields = set(old_settings.model_fields.keys())
missing_fields = old_fields - new_fields
extra_fields = new_fields - old_fields

print(f'总字段数: 新配置={len(new_fields)}, 原配置={len(old_fields)}')
print(f'缺失字段: {missing_fields}' if missing_fields else '无缺失字段')
print(f'额外字段: {extra_fields}' if extra_fields else '无额外字段')

# 测试属性访问
print(f'app_name: {settings.app_name}')
print(f'model_report_generation: {settings.model_report_generation}')
print(f'rag_hybrid_bm25_weight: {settings.rag_hybrid_bm25_weight}')
print(f'llm_models property works: {len(settings.llm_models) > 0}')
print(f'rag_config property works: {len(settings.rag_config) > 0}')
print(f'get_all_config_metadata works: {len(settings.get_all_config_metadata()) > 0}')
"`
Expected: 无缺失字段，所有属性访问正常

---

### Task 15: 安装watchdog依赖（如果需要）

- [ ] **Step 1: 检查并安装watchdog**

Run: `cd /Users/owen/project/ai/child-development-assessment-agent && pip show watchdog || pip install watchdog`
Expected: watchdog安装成功

---

## 实施完成标准
1. ✅ 所有拆分后的配置文件创建完成，语法正确
2. ✅ 配置聚合入口__init__.py实现完成，所有属性和方法与原配置兼容
3. ✅ 原settings.py实现了向后兼容，正确输出弃用警告
4. ✅ 所有配置字段可以正常访问，值与原配置一致
5. ✅ 热更新逻辑实现完成，配置文件变更可以自动重载
