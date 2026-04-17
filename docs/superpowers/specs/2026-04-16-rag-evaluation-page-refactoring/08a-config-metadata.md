# 08a - 配置元数据补充

> **本文档包含**: 所有配置项的中文名称、用途说明、取值范围、推荐范围

---

## 1. 现有配置分析

### 1.1 配置分类

当前系统配置按功能域分为以下类别:

| 分类 | 配置前缀 | 配置项数量 | 中文说明完整度 |
|------|---------|-----------|--------------|
| RAG 检索 | `rag_hybrid_`, `rag_search_`, `rag_reranker_`, `rag_age_filter_` | ~30 | 50% |
| RAG 分块 | `rag_chunk_`, `semantic_splitter_` | ~10 | 40% |
| RAG 向量库 | `rag_vector_store_`, `embedding_` | ~8 | 60% |
| LLM 模型 | `model_`, `llm_`, `dashscope_` | ~15 | 70% |
| 数据库 | `database_` | ~5 | 80% |
| Redis | `redis_` | ~8 | 70% |
| 日志 | `log_` | ~5 | 90% |
| 业务规则 | `rule_` | ~15 | 60% |
| 应用 | `app_`, `host`, `port` | ~5 | 80% |

### 1.2 问题清单

| 问题 | 示例 | 影响 |
|------|------|------|
| **纯英文描述** | `description="BM25 weight"` | 中文用户无法理解 |
| **无取值范围** | `rag_hybrid_bm25_weight: float = 0.5` | 用户可能输入负数或 >1 的值 |
| **无推荐范围** | 融合搜索阈值实际应 [0.2, 0.3]，但未声明 | 用户设置 0.7 导致无结果 |
| **无影响说明** | 修改 `rag_chunk_size` 会影响什么？ | 用户不知道需要重新索引 |

---

## 2. 配置元数据模型扩展

### 2.1 存储策略

配置元数据存储在独立的 `config_field_metadata` 表中，与 `ConfigVersion`（配置版本快照）分离：

| 表 | 职责 | 变更频率 |
|----|------|---------|
| `config_field_metadata` | 配置项的静态元数据（中文名称、取值范围、推荐范围、影响组件等） | 低：仅在新增/修改配置项定义时变更 |
| `config_versions` | 配置值的版本快照（某时刻所有配置项的具体取值） | 高：每次用户修改配置值时创建新版本 |

**关系**: `ConfigVersion.config_snapshot` (JSON) 存储配置键值对，`ConfigFieldMetadata` 提供每个配置键的元数据描述。前端展示配置编辑页时，先查询元数据获取表单 schema，再查询当前版本获取默认值。

### 2.2 新增字段

在现有 `ConfigFieldMetadata` 基础上新增以下字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| id | CHAR(36) | 主键，UUID |
| name_zh | string | 中文名称 |
| description_zh | string | 中文用途说明 |
| unit | string\|None | 单位（如"秒"、"MB"、"个"） |
| min_value | float\|None | 最小值 |
| max_value | float\|None | 最大值 |
| recommended_range | tuple | 推荐范围 |

保留字段：key, category, description, affected_components, hot_reloadable, requires_restart, field_type, default_value, current_value。

---

## 3. 完整配置元数据清单

### 3.1 RAG 检索配置

| 配置 Key | 中文名称 | 中文用途说明 | 取值范围 | 推荐范围 | 单位 | 影响组件 | 重载方式 |
|---------|---------|-------------|---------|---------|------|---------|---------|
| `rag_hybrid_bm25_weight` | BM25 权重 | 混合检索中 BM25 关键词匹配的权重占比 | [0, 1] | [0.3, 0.7] | - | 混合检索引擎 | 热重载 |
| `rag_hybrid_vector_weight` | 向量权重 | 混合检索中向量语义匹配的权重占比 | [0, 1] | [0.3, 0.7] | - | 混合检索引擎 | 热重载 |
| `rag_hybrid_merge_mode` | 合并模式 | BM25 和向量检索结果的合并方式：OR（并集）或 AND（交集） | OR/AND | OR | - | 混合检索引擎 | 热重载 |
| `rag_hybrid_bm25_top_k` | BM25 返回数量 | BM25 检索返回的顶部文档数量 | [1, 100] | [5, 20] | 个 | 混合检索引擎 | 热重载 |
| `rag_hybrid_vector_top_k` | 向量返回数量 | 向量检索返回的顶部文档数量 | [1, 100] | [5, 20] | 个 | 混合检索引擎 | 热重载 |
| `bm25_scale_factor` | BM25 分数缩放因子 | BM25 原始分数的缩放系数，用于与向量分数对齐 | [0.1, 20] | [3, 10] | - | 混合检索引擎 | 热重载 |
| `rag_hybrid_bm25_weight_dense` | 密集场景 BM25 权重 | 密集查询场景下 BM25 的权重（术语类查询） | [0, 1] | [0.5, 0.8] | - | 混合检索引擎 | 热重载 |
| `rag_hybrid_vector_weight_dense` | 密集场景向量权重 | 密集查询场景下向量的权重 | [0, 1] | [0.2, 0.5] | - | 混合检索引擎 | 热重载 |
| `rag_hybrid_base_threshold` | 混合检索最低分数 | 混合检索结果的最低分数阈值，低于此分数的结果被过滤 | [0, 1] | [0.05, 0.2] | - | 混合检索引擎 | 热重载 |
| `rag_relative_cutoff_ratio` | 相对截断比例 | 基于最高分数的相对截断比例，用于过滤低质量结果 | [0, 1] | [0.2, 0.5] | - | 混合检索引擎 | 热重载 |
| `rag_reranker_provider` | 重排序提供商 | 重排序使用的服务提供商：local（本地）/cohere/voyage | local/cohere/voyage | local | - | 重排序器 | 冷重启 |
| `rag_reranker_model` | 重排序模型 | 重排序使用的模型名称 | - | BAAI/bge-reranker-v2-m3 | - | 重排序器 | 冷重启 |
| `rag_reranker_initial_k` | 重排序初始数量 | 送入重排序器的初始结果数量 | [5, 100] | [20, 50] | 个 | 重排序器 | 热重载 |
| `rag_reranker_final_k` | 重排序返回数量 | 重排序后最终返回的结果数量 | [1, 20] | [3, 10] | 个 | 重排序器 | 热重载 |
| `rag_query_rewrite_enabled` | 查询重写开关 | 是否启用查询重写功能，将用户查询优化为更适合检索的形式 | true/false | true | - | 查询重写服务 | 热重载 |
| `query_router_confidence_threshold` | 路由置信度阈值 | 查询分类的最低置信度，低于此阈值走默认流水线 | [0, 1] | [0.7, 0.9] | - | 查询路由器 | 热重载 |
| `rag_age_filter_mode` | 年龄过滤模式 | 年龄过滤的严格程度：strict（严格）或 loose（宽松） | strict/loose | strict | - | 年龄过滤器 | 热重载 |
| `rag_age_filter_tolerance_strict` | 严格模式年龄容忍度 | 严格模式下允许偏离目标年龄的岁数 | [0, 5] | [1, 2] | 岁 | 年龄过滤器 | 热重载 |
| `rag_age_filter_tolerance_loose` | 宽松模式年龄容忍度 | 宽松模式下允许偏离目标年龄的岁数 | [0, 5] | [2, 3] | 岁 | 年龄过滤器 | 热重载 |
| `rag_age_fit_weight` | 年龄适配度权重 | 年龄适配度在最终评分中的权重占比 | [0, 1] | [0.2, 0.4] | - | 年龄过滤器 | 热重载 |
| `fusion_score_boost_for_pageindex` | PageIndex 分数提升 | PageIndex 匹配结果的分数提升倍数 | [1, 2] | [1.1, 1.3] | 倍 | 结果融合器 | 热重载 |
| `fusion_dedup_normalize` | 去重归一化开关 | 是否在融合前对结果进行去重和分数归一化 | true/false | true | - | 结果融合器 | 热重载 |
| `rag_similarity_threshold` | 相似度阈值 | 检索结果与查询的最低相似度要求，低于此值的结果被过滤 | [0, 1] | [0.5, 0.8] | - | 混合检索引擎 | 热重载 |
| `rag_min_result_count` | 最小结果数量 | 检索结果的最少返回数量，即使分数低于阈值也保证返回此数量 | [1, 10] | [3, 5] | 个 | 混合检索引擎 | 热重载 |

### 3.2 RAG 分块配置

| 配置 Key | 中文名称 | 中文用途说明 | 取值范围 | 推荐范围 | 单位 | 影响组件 | 重载方式 |
|---------|---------|-------------|---------|---------|------|---------|---------|
| `rag_chunk_size` | 分块大小 | 文档分块时每个块的目标字符数 | [100, 5000] | [500, 1500] | 字符 | 文档分块器 | 冷重启 |
| `rag_chunk_overlap` | 分块重叠大小 | 相邻分块之间的重叠字符数，用于保持上下文连贯性 | [0, 500] | [50, 200] | 字符 | 文档分块器 | 冷重启 |
| `semantic_splitter_chunk_size` | 语义分块大小 | 语义分割器的目标分块大小 | [200, 3000] | [500, 1000] | 字符 | 语义分割器 | 冷重启 |
| `semantic_splitter_buffer_size` | 语义分块缓冲区 | 语义分割器的缓冲区大小，用于上下文感知分割 | [50, 500] | [100, 200] | 字符 | 语义分割器 | 冷重启 |
| `rag_pdf_chunk_size` | PDF 分块大小 | PDF 文档分块时的目标字符数 | [200, 3000] | [500, 1000] | 字符 | PDF 分块器 | 冷重启 |
| `rag_epub_chunk_target_size` | EPUB 目标分块大小 | EPUB 文档分块时的目标字符数 | [200, 3000] | [500, 1000] | 字符 | EPUB 分块器 | 冷重启 |

### 3.3 RAG 向量库配置

| 配置 Key | 中文名称 | 中文用途说明 | 取值范围 | 推荐范围 | 单位 | 影响组件 | 重载方式 |
|---------|---------|-------------|---------|---------|------|---------|---------|
| `rag_vector_base_threshold` | 向量检索最低分数 | 向量检索结果的最低分数阈值 | [0, 1] | [0.3, 0.6] | - | 向量检索引擎 | 热重载 |
| `embedding_model_name` | Embedding 模型名称 | 用于文本向量化的 Embedding 模型名称 | - | text-embedding-v3 | - | Embedding 服务 | 冷重启 |
| `embedding_batch_size` | Embedding 批次大小 | Embedding 模型每次处理的文本批次大小 | [1, 100] | [10, 32] | 个 | Embedding 服务 | 热重载 |
| `rag_vector_store_path` | 向量库存储路径 | Chroma 向量库的本地存储路径 | - | storage/vector_store | - | 向量库 | 冷重启 |
| `rag_auto_persist_interval` | 自动持久化间隔 | 向量库自动保存的间隔时间 | [60, 3600] | [300, 600] | 秒 | 向量库 | 热重载 |

### 3.4 RAG 缓存配置

| 配置 Key | 中文名称 | 中文用途说明 | 取值范围 | 推荐范围 | 单位 | 影响组件 | 重载方式 |
|---------|---------|-------------|---------|---------|------|---------|---------|
| `rag_cache_enabled` | 缓存开关 | 是否启用检索结果缓存 | true/false | true | - | 缓存系统 | 热重载 |
| `rag_cache_max_size` | 缓存最大容量 | 缓存最多存储的条目数量 | [100, 100000] | [1000, 10000] | 个 | 缓存系统 | 热重载 |
| `rag_cache_ttl_seconds` | 缓存过期时间 | 缓存条目的存活时间，过期后自动清除 | [60, 86400] | [1800, 7200] | 秒 | 缓存系统 | 热重载 |

### 3.5 LLM 模型配置

| 配置 Key | 中文名称 | 中文用途说明 | 取值范围 | 推荐范围 | 单位 | 影响组件 | 重载方式 |
|---------|---------|-------------|---------|---------|------|---------|---------|
| `dashscope_api_key` | 阿里云 API 密钥 | 阿里云百炼平台的 API 密钥（敏感信息，加密存储） | - | - | - | LLM 服务 | 冷重启 |
| `model_report_generation` | 报告生成模型 | 生成儿童发展评估报告使用的 LLM 模型 | - | qwen3.5-plus | - | 报告生成服务 | 冷重启 |
| `model_assessment` | 评估模型 | 儿童发展多维度评估使用的 LLM 模型 | - | qwen3.5-plus | - | 评估服务 | 冷重启 |
| `model_validation` | 校验模型 | 数据校验和结果校验使用的 LLM 模型 | - | qwen3.5-turbo | - | 校验服务 | 冷重启 |
| `model_query_rewrite` | 查询重写模型 | 查询重写功能使用的 LLM 模型 | - | qwen3-omni-flash | - | 查询重写服务 | 冷重启 |
| `model_metadata_extraction` | 元数据提取模型 | 文档元数据提取使用的 LLM 模型 | - | qwen3-omni-flash | - | 元数据提取服务 | 冷重启 |
| `model_vl_parsing` | 多模态解析模型 | 图片和多模态内容解析使用的 LLM 模型 | - | qwen3-omni-flash | - | 多模态解析服务 | 冷重启 |
| `model_query_classification` | 查询分类模型 | 查询类型分类使用的 LLM 模型 | - | qwen3-omni-flash | - | 查询路由器 | 冷重启 |
| `ml_scoring_qwen_model` | ML 评分模型 | 机器学习评分功能使用的 LLM 模型 | - | qwen3.5-turbo | - | ML 评分服务 | 冷重启 |

### 3.6 LLM 场景配置（嵌套模型）

| 场景 Key | 中文名称 | 中文用途说明 | 参数 |
|---------|---------|-------------|------|
| `report_generation` | 报告生成场景 | 生成详细评估报告的场景配置 | provider, model, temperature, max_tokens, top_p |
| `assessment` | 评估场景 | 多维度感统能力评估的场景配置 | provider, model, temperature, max_tokens, top_p |
| `validation` | 校验场景 | 数据校验和结果校验的场景配置 | provider, model, temperature, max_tokens, top_p |
| `query_rewrite` | 查询重写场景 | 查询重写优化的场景配置 | provider, model, temperature, max_tokens, top_p |
| `metadata_extraction` | 元数据提取场景 | 文档元数据提取的场景配置 | provider, model, temperature, max_tokens, top_p |
| `query_classification` | 查询分类场景 | 查询类型分类的场景配置 | provider, model, temperature, max_tokens, top_p |
| `vl_parsing` | 多模态解析场景 | 图片等多模态内容解析的场景配置 | provider, model, temperature, max_tokens, top_p |
| `ml_scoring` | ML 评分场景 | 机器学习评分的场景配置 | provider, model, temperature, max_tokens, top_p |
| `content_generation` | 内容生成场景 | 通用内容生成的场景配置 | provider, model, temperature, max_tokens, top_p |

### 3.7 数据库配置

| 配置 Key | 中文名称 | 中文用途说明 | 取值范围 | 推荐范围 | 单位 | 影响组件 | 重载方式 |
|---------|---------|-------------|---------|---------|------|---------|---------|
| `database_url` | 数据库连接 URL | MySQL 数据库连接字符串（含用户名、密码、主机、端口、库名） | - | - | - | 数据库连接池 | 冷重启 |
| `database_pool_size` | 连接池大小 | 数据库连接池的最大连接数 | [1, 100] | [5, 20] | 个 | 数据库连接池 | 冷重启 |
| `database_max_overflow` | 连接池溢出上限 | 连接池允许的最大溢出连接数 | [0, 50] | [5, 10] | 个 | 数据库连接池 | 冷重启 |
| `database_pool_timeout` | 连接池超时时间 | 获取连接时的等待超时时间 | [1, 60] | [5, 10] | 秒 | 数据库连接池 | 冷重启 |
| `database_echo` | SQL 日志开关 | 是否打印 SQL 语句日志（调试用） | true/false | false | - | 数据库连接池 | 热重载 |

### 3.8 Redis 配置

| 配置 Key | 中文名称 | 中文用途说明 | 取值范围 | 推荐范围 | 单位 | 影响组件 | 重载方式 |
|---------|---------|-------------|---------|---------|------|---------|---------|
| `redis_host` | Redis 主机地址 | Redis 服务器的主机地址 | - | localhost | - | Redis 客户端 | 冷重启 |
| `redis_port` | Redis 端口 | Redis 服务器的端口号 | [1, 65535] | 6379 | - | Redis 客户端 | 冷重启 |
| `redis_password` | Redis 密码 | Redis 服务器的访问密码（敏感信息，加密存储） | - | - | - | Redis 客户端 | 冷重启 |
| `redis_db` | Redis 数据库编号 | Redis 逻辑数据库编号（0-15） | [0, 15] | 0 | - | Redis 客户端 | 冷重启 |
| `redis_max_connections` | Redis 最大连接数 | Redis 连接池的最大连接数 | [1, 100] | [10, 20] | 个 | Redis 客户端 | 冷重启 |
| `redis_socket_timeout` | Redis 连接超时 | Redis 连接的超时时间 | [1, 60] | [5, 10] | 秒 | Redis 客户端 | 冷重启 |
| `redis_cache_default_ttl` | Redis 缓存默认过期 | Redis 缓存条目的默认存活时间 | [60, 86400] | [300, 3600] | 秒 | Redis 缓存 | 热重载 |
| `redis_pubsub_channels` | Redis 发布订阅频道 | Redis Pub/Sub 使用的频道列表 | - | ["config:changed", "llm:call", "test:progress"] | - | Redis Pub/Sub | 冷重启 |

### 3.9 日志配置

| 配置 Key | 中文名称 | 中文用途说明 | 取值范围 | 推荐范围 | 单位 | 影响组件 | 重载方式 |
|---------|---------|-------------|---------|---------|------|---------|---------|
| `log_level` | 日志级别 | 日志输出的最低级别：DEBUG/INFO/WARNING/ERROR/CRITICAL | DEBUG/INFO/WARNING/ERROR/CRITICAL | INFO | - | 日志系统 | 热重载 |
| `log_format` | 日志格式 | 日志输出的格式模板 | - | %(asctime)s - %(name)s - %(levelname)s - %(message)s | - | 日志系统 | 热重载 |
| `log_file` | 日志文件路径 | 日志文件存储路径（为空则仅输出到控制台） | - | logs/app.log | - | 日志系统 | 热重载 |
| `log_max_bytes` | 日志文件最大大小 | 单个日志文件的最大大小，超过后自动切割 | [1048576, 104857600] | [10485760, 52428800] | 字节 | 日志系统 | 热重载 |
| `log_backup_count` | 日志备份数量 | 保留的日志文件切割备份数量 | [1, 100] | [5, 10] | 个 | 日志系统 | 热重载 |

### 3.10 业务规则配置

| 配置 Key | 中文名称 | 中文用途说明 | 取值范围 | 推荐范围 | 单位 | 影响组件 | 重载方式 |
|---------|---------|-------------|---------|---------|------|---------|---------|
| `rule_metadata_development_domains` | 发展领域列表 | 儿童发展评估的领域标签列表 | - | ["粗大动作", "精细动作", "认知能力", "语言发展", "社交情感", "感觉统合"] | - | 规则引擎 | 热重载 |
| `rule_metadata_age_patterns` | 年龄匹配模式 | 用于从文本中提取年龄的正则表达式列表 | - | 见代码默认值 | - | 规则引擎 | 热重载 |
| `rule_metadata_difficulty_easy_threshold` | 简单难度阈值 | 内容长度低于此值判定为简单难度 | [50, 1000] | [200, 400] | 字符 | 规则引擎 | 热重载 |
| `rule_metadata_difficulty_hard_threshold` | 困难难度阈值 | 内容长度高于此值判定为困难难度 | [500, 5000] | [800, 1200] | 字符 | 规则引擎 | 热重载 |

### 3.11 应用配置

| 配置 Key | 中文名称 | 中文用途说明 | 取值范围 | 推荐范围 | 单位 | 影响组件 | 重载方式 |
|---------|---------|-------------|---------|---------|------|---------|---------|
| `app_name` | 应用名称 | 系统显示名称 | - | 儿童发展评估 Agent | - | 应用入口 | 冷重启 |
| `app_version` | 应用版本 | 系统版本号 | - | 1.0.0 | - | 应用入口 | 冷重启 |
| `host` | 服务主机 | FastAPI 服务绑定的主机地址 | - | 0.0.0.0 | - | 应用入口 | 冷重启 |
| `port` | 服务端口 | FastAPI 服务绑定的端口号 | [1, 65535] | 8000 | - | 应用入口 | 冷重启 |
| `debug` | 调试模式 | 是否启用调试模式（开启后显示详细错误信息） | true/false | false | - | 应用入口 | 冷重启 |

---

## 4. 配置元数据初始化

### 4.1 初始化策略

系统启动时，自动从代码中的 `ConfigFieldMetadata` 生成完整元数据：
- 通过映射表填充中文名称（name_zh）
- 通过映射表填充中文用途说明（description_zh）
- 通过映射表填充取值范围（min_value, max_value, recommended_range）

映射关系维护在配置管理模块中，与 §3 的完整清单保持一致。

---

## 5. 验收标准

| 验收项 | 标准 |
|--------|------|
| **中文名称** | 所有配置项都有 `name_zh`，无空值 |
| **中文说明** | 所有配置项都有 `description_zh`，无空值 |
| **取值范围** | 数值型配置都有 `min_value` 和 `max_value` |
| **推荐范围** | 关键配置都有 `recommended_range` |
| **影响组件** | 所有配置项都有 `affected_components` 列表 |
| **重载方式** | 所有配置项都正确标注 `hot_reloadable` |

---

**文档索引**: 
- 上一节: [08-config-management-overview.md](./08-config-management-overview.md) — 配置管理优化概览
- 下一节: [08b-config-frontend-pages.md](./08b-config-frontend-pages.md) — 前端配置页重构
