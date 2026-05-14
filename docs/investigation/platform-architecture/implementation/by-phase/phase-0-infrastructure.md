# Phase 0：基础设施搭建 · 实施文档

> **对应源文档**：[07-infrastructure.md (by-module)](../by-module/07-infrastructure.md) §1-§8
> **上游依赖**：无（第一阶段）
> **下游被依赖**：Phase 1-10 全部
> **预估文件量**：~15 新建 + ~5 改造 + ~25 继承 = ~45 文件
> **产出**：Docker Compose 可启动、DB Schema 创建完毕、项目骨架就绪

---

## 1. 阶段目标

搭建 `rag-platform/` 的完整可运行项目骨架，使其**不依赖 `backend/`** 即可启动。从 `backend/` 继承全部基础设施（统一响应、追踪、中间件、LLM 工厂、配置热重载、提示词管理框架），剥离儿童评估专用代码。

### 退出标准（Exit Criteria）

1. `docker compose up -d` 启动后三个核心容器 `healthy`
2. `GET /health` 返回 `200 {"data":{"status":"healthy"}}`，含 MySQL、Redis 连通性
3. `GET /metrics` 返回 Prometheus 文本指标
4. 非 API 路径（如 `/pipelines`）由 SPA 回退路由返回 `index.html`
5. MySQL 中 31 张表全部创建成功（9 权限 + 3 管道 + 4 知识库 + 11 评估 + 1 搜索 + 3 基础设施改造）
6. 所有继承模块可正常 import，无 `backend/` 依赖
7. 前端 `npm run dev` 可启动，代理到 51002 正常

---

## 2. 任务清单

### 2.1 项目骨架（0.1）

- [ ] 0.1.1 创建 `rag-platform/CLAUDE.md`（AI 上下文规则，从根目录 CLAUDE.md 派生，去除 backend/ 引用）
- [ ] 0.1.2 创建 `rag-platform/backend/src/` 完整目录结构（按 §7.2.1 目录树）
  ```
  backend/src/
  ├── api/           # 统一响应、SSE
  ├── config/core/   # 配置基础设施
  ├── config/modules/ # 配置模块
  ├── config/rules/  # 业务规则
  ├── controller/    # 控制器层
  ├── core/          # 核心业务
  │   ├── config/
  │   ├── llm/adapters/
  │   ├── tracing/
  │   ├── pipeline/        # Phase 3 占位
  │   ├── knowledge_base/  # Phase 2 占位
  │   ├── auth/            # Phase 1 占位
  │   ├── metadata/
  │   └── prompt_impl/
  ├── middleware/     # 中间件
  ├── models/        # SQLAlchemy 模型
  ├── repository/    # 数据访问层
  ├── schemas/       # Pydantic 实体
  ├── service/       # 业务服务层
  ├── utils/         # 工具函数
  └── tests/         # 测试
  ```
- [ ] 0.1.3 创建 `rag-platform/frontend/src/` 完整目录结构
  ```
  frontend/src/
  ├── api/           # API 客户端
  ├── app/           # 根组件
  │   └── layouts/   # Phase 9 占位
  ├── components/    # 通用组件
  │   ├── monitoring/
  │   ├── config/
  │   └── layout/
  ├── entities/      # 业务实体类型
  ├── features/      # 业务特性
  │   ├── pipeline/        # Phase 5 占位
  │   ├── knowledgeBase/   # Phase 6 占位
  │   ├── search/          # Phase 4 占位
  │   ├── auth/            # Phase 9 占位
  │   ├── admin/           # Phase 9 占位
  │   ├── monitoring/
  │   ├── rag-eval/
  │   └── config/
  ├── pages/         # 独立页面
  ├── router/        # 路由配置
  └── shared/        # 共享层
      ├── api/
      ├── hooks/
      ├── lib/
      └── types/
  ```
- [ ] 0.1.4 创建 `rag-platform/storage/` 目录结构
  ```
  storage/
  ├── chroma/        # Chroma 向量库持久化
  ├── bm25/          # BM25 独立索引
  └── documents/     # 上传文档文件
  ```

### 2.2 后端基础设施（0.2）

- [ ] 0.2.1 创建 `backend/pyproject.toml`——从 `backend/pyproject.toml` 继承，改动：
  - **移除依赖**：`xgboost`, `shap`, `scikit-learn`（ML 评分不再需要）
  - **新增依赖**：`elasticsearch[async]>=8.15`, `pymilvus>=2.3`
  - **保留所有继承依赖**：`fastapi`, `sqlalchemy[asyncio]`, `langgraph`, `langchain`, `llama-index`, `chromadb`, `redis`, `pydantic`, `prometheus-client`, `injector` 等
  - 修改项目名 → `rag-platform`
- [ ] 0.2.2 创建 `backend/.env`——环境变量（仅基础设施凭证，不使用 MySQL 兜底值）
  ```bash
  # 基础设施
  APP_PORT=51002
  DATABASE_URL=mysql+asyncmy://raguser:ragpass@localhost:3306/rag_platform
  REDIS_URL=redis://:ragredis@localhost:6379/0
  JWT_SECRET=change-me-in-production-min-32-chars

  # LLM 凭证兜底（MySQL 配置优先）
  DASHSCOPE_API_KEY=
  OPENAI_API_KEY=
  ANTHROPIC_API_KEY=
  DEEPSEEK_API_KEY=

  # 可选：ES/Milvus（不配置则不初始化对应客户端）
  ES_URL=
  MILVUS_HOST=
  MILVUS_PORT=19530

  # 数据目录
  DATA_DIR=./app_data/data
  RAG_STORAGE_DIR=./app_data/storage
  RAG_TEMP_UPLOAD_DIR=./app_data/temp_uploads
  LOG_FILE=./logs/app.log
  ```
- [ ] 0.2.3 创建 `backend/src/server.py`——改造自 `backend/src/server.py`：
  - FastAPI app 工厂函数 `create_app()`
  - 中间件注册顺序：TraceMiddleware → ResponseWrapperMiddleware → (AuthMiddleware 占位) → (RateLimitMiddleware 占位) → CORSMiddleware
  - 挂载 `/metrics`（`prometheus_client.make_asgi_app()`）
  - 注册 `/health` 路由
  - SPA 回退路由（最后注册的 catch-all，排除 `api/`/`docs`/`openapi.json`/`metrics`/`health`/`search/`）
  - **移除**：`task_controller`、原始 `rag_controller` 评估部分、报告生成路由
  - lifespan 优雅关闭逻辑（含 TraceWriter 刷盘、ConfigCache 关闭、异步任务取消）
- [ ] 0.2.4 继承 `api/json_response.py`——完整复制，无改动。`APIResponse.success()` 和 `UtcJsonResponse`。
- [ ] 0.2.5 继承 `api/sse.py`——完整复制，无改动。`SSEPublisher` 和 `AsyncTaskManager`。
- [ ] 0.2.6 继承 `middleware/exception_handler.py`——完整复制，无改动。全局异常处理，`AppException` → 统一格式。
- [ ] 0.2.7 继承 `middleware/response_wrapper.py`——完整复制，无改动。自动包装 `APIResponse.success()`。
- [ ] 0.2.8 继承 `middleware/trace_middleware.py`——完整复制，无改动。自动注入 `X-Trace-ID`。
- [ ] 0.2.9 继承 `core/tracing/`——完整复制 `context.py`（TraceContext + Span 生命周期）、`writer.py`（异步队列 + 批量写入）、`cost.py`（CostCalculator + 多模型定价）、`cleanup.py`（过期清理）、`truncation.py`（截断策略）。
- [ ] 0.2.10 继承 `core/llm/`——完整复制 `factory.py`（LLMServiceFactory）、`embedding_factory.py`（EmbeddingFactory）、`base.py`（ILLMService 接口）、`adapters/`（langchain.py、llamaindex.py、dashscope_multimodal.py）、`log_collector.py`。
- [ ] 0.2.11 继承 `core/config/cache.py`——改造为多租户感知。新增 `get_tenant_config(tenant_id)` 和 `get_tenant_value(tenant_id, key, default)` 方法。ConfigCache 单例 + Redis Pub/Sub 热重载 + 轮询降级备份。移除儿童评估配置键。
- [ ] 0.2.12 继承 `core/prompt_impl/`——`facade.py`（PromptManager 门面）、`prompt_storage.py`（提示词持久化）、`ab_test_manager.py`（A/B 测试管理）完整复制。`initializer.py` 移除评估提示词模板初始化，保留基础设施。
- [ ] 0.2.13 继承 `utils/`——完整复制全部工具函数（`logger.py`、`exceptions.py`、`helpers.py` 等）。`exceptions.py` 移除儿童评估专用异常，新增权限异常基类。
- [ ] 0.2.14 继承 `service/monitoring_service.py`——完整复制。
- [ ] 0.2.15 继承 `service/alert_service.py`——完整复制。
- [ ] 0.2.16 继承 `service/trace_service.py`——完整复制。
- [ ] 0.2.17 继承 `service/config_validation_engine.py`——完整复制。
- [ ] 0.2.18 继承 `service/config_conflict_detector.py`——完整复制。
- [ ] 0.2.19 继承 `service/config_health_service.py`——完整复制。
- [ ] 0.2.20 继承 `service/task_state_service.py`——完整复制。
- [ ] 0.2.21 继承 `service/task_sse_publisher.py`——完整复制。
- [ ] 0.2.22 继承 `service/export_notification.py`——完整复制。
- [ ] 0.2.23 继承 `service/cache/`——完整复制 `facade.py`（三级缓存门面）、`memory.py`（cachetools LRU）、`redis_cache.py`、`disk_cache.py`。
- [ ] 0.2.24 继承 `core/parsers.py` → 放入 `core/knowledge_base/parser.py`，移除业务配置引用，通用化。
- [ ] 0.2.25 继承 `core/embedding.py` → 改造为 `core/knowledge_base/embedding/engine.py`，通用化 EmbeddingEngine。

### 2.3 数据库 Schema（0.3）

单个 `init.sql` 文件，放在 `rag-platform/init.sql`，MySQL 容器首次启动时由 `docker-entrypoint-initdb.d` 自动执行。

**DDL 总表数**：31 张（9 权限 + 3 管道 + 4 知识库 + 11 评估 + 1 搜索 + 3 基础设施改造）

#### 2.3.1 权限与多租户（9 新建）

- [ ] 0.3.1 `tenants`——id(varchar(36)), name, slug(UNIQUE), status(active/disabled/archived/deleted), resource_limits(JSON), deleted_at, created_at, updated_at
- [ ] 0.3.2 `users`——id(varchar(36)), tenant_id(INDEX, NULL=超管), username, email(UNIQUE+tenant_id), password_hash, status(active/disabled), deleted_at, created_at
- [ ] 0.3.3 `roles`——id(varchar(36)), tenant_id(INDEX), name, slug(UNIQUE+tenant_id), permissions(JSON: list[str]), is_builtin(BOOL), created_at
- [ ] 0.3.4 `user_roles`——user_id(varchar(36)), role_id(varchar(36)) (复合 PK)
- [ ] 0.3.5 `user_invitations`——id(varchar(36)), tenant_id(INDEX), email, roles(JSON), token(UNIQUE), expires_at, accepted_at, created_by, created_at
- [ ] 0.3.6 `god_mode_audit_log`——id(varchar(36)), tenant_id(INDEX), actor_id, action(enter/exit/read/write/extend), target_type, target_id, details(TEXT), session_started_at, created_at
- [ ] 0.3.7 `tenant_deletion_snapshots`——id(varchar(36)), tenant_id, snapshot_path, status(pending/ready/expired), expires_at, created_at
- [ ] 0.3.8 `permission_audit_log`——id(varchar(36)), tenant_id, actor_id, action, target_type, target_id, old_value(JSON), new_value(JSON), created_at
- [ ] 0.3.9 `tenant_audit_log`——id(varchar(36)), tenant_id, actor_id, action, details(TEXT), created_at

#### 2.3.2 管道引擎（3 新建）

- [ ] 0.3.10 `pipelines`——id(varchar(64)), tenant_id(INDEX), name, type(varchar(32) DEFAULT 'aggregation'), active_version(INT DEFAULT 1), created_at, updated_at
- [ ] 0.3.11 `pipeline_versions`——id(varchar(64)), pipeline_id(INDEX), tenant_id(INDEX, 冗余), version_number(INT, UNIQUE+pipeline_id), change_log(TEXT), config_snapshot(JSON), created_at
- [ ] 0.3.12 `compound_nodes`——id(varchar(64)), tenant_id(INDEX, 冗余), owner_id(INDEX), name, config_snapshot(JSON, 含 expanded_nodes/internal_edges/exposed_ports), created_at

#### 2.3.3 知识库管理（4 新建）

- [ ] 0.3.13 `knowledge_bases`——id(varchar(24) 雪花ID), tenant_id(INDEX), name, description, vector_backend(chroma/es/milvus), chunk_strategy(JSON), embedding_config(JSON), visibility(public/role_scoped/private), visible_roles(JSON), owner_id, status(ready/rebuilding/indexing/error), document_count(INT), chunk_count(INT), storage_size_bytes(BIGINT), created_at, updated_at
- [ ] 0.3.14 `kb_documents`——id(varchar(24)), kb_id(INDEX), tenant_id(INDEX), filename, file_type(pdf/txt/markdown/html/epub), file_size(INT), page_count(INT), md5_hash(INDEX), parse_status(pending/parsing/parsed/error), error_message, text_content(MEDIUMTEXT), metadata(JSON), access_level(inherit/restricted), doc_acl(JSON), owner_id, chunk_count(INT), uploaded_at
- [ ] 0.3.15 `kb_chunks`——id(varchar(24)), kb_id(INDEX), doc_id(INDEX), tenant_id(INDEX), chunk_index(INT), content(MEDIUMTEXT), token_count(INT), metadata(JSON), vector_id
- [ ] 0.3.16 `kb_rebuild_tasks`——id(varchar(24)), kb_id(INDEX), tenant_id(INDEX), trigger(chunk_change/embedding_change/backend_migration), status(running/completed/failed), progress_pct(TINYINT), progress_message, started_at, completed_at, error_message

#### 2.3.4 RAG 评估（11 新建/改造，见 06-rag-evaluation §2）

- [ ] 0.3.17 `test_cases`——**改造**，新增 `relevant_domains`(JSON)、`expected_conflicts`(JSON)、`tenant_id`(varchar(64)) 字段
- [ ] 0.3.18 `test_sets`——**改造**，新增 `visibility`、`owner_id`、`tenant_id`(varchar(64)) 字段
- [ ] 0.3.19 `test_set_cases`——**改造**，类型不变
- [ ] 0.3.20 `test_runs`——**改造**，新增 `pipeline_id`、`pipeline_version`、`run_as_user_id`、`simulated_role_id`、`cross_domain_metrics_json`、`domain_results_json`、`tenant_id`(varchar(64)) 字段
- [ ] 0.3.21 `test_run_results`——**改造**，新增 `domain_results_json`(JSON) 字段
- [ ] 0.3.22 `eval_reports`——**改造**，新增 `cross_domain_score`、`cross_domain_json`、`tenant_id`(varchar(64)) 字段
- [ ] 0.3.23 `knowledge_snapshots`——**改造**，新增 `kb_id`、`vector_backend_type`、`doc_ids_json`、`chunk_strategy_json`、`embedding_config_json`、`status`、`expires_at`、`tenant_id`(varchar(64)) 字段
- [ ] 0.3.24 `tuning_suggestions`——**改造**，新增 `tenant_id`(varchar(64)，`conflict_with` 从 VARCHAR 改为 JSON 数组
- [ ] 0.3.25 `eval_config_versions`——**改造**，新增 `change_set_id`、`tenant_id`(varchar(64)) 字段
- [ ] 0.3.26 `eval_config_change_sets`——**改造**，新增 `previous_version_id`、`tenant_id`(varchar(64)) 字段
- [ ] 0.3.27 `test_case_drafts`——**改造**，类型不变（现有表新增字段见完整 DDL）

#### 2.3.5 搜索与发布（1 新建）

- [ ] 0.3.28 `published_endpoints`——id(BIGINT AUTO_INCREMENT), endpoint_id(varchar(64) UNIQUE), pipeline_id(INDEX), tenant_id(INDEX), url_path(UNIQUE), bound_version(INT), http_method(POST/GET), auth_type(jwt/api_key/none), rate_limit(INT), enabled(BOOL), allowed_params(JSON), response_format(json/sse/custom), created_at, updated_at

#### 2.3.6 基础设施表改造（3 改造）

- [ ] 0.3.29 `trace_spans`——**改造**，新增 `pipeline_id`、`pipeline_version`、`domain_id`、`degraded`(BOOL) 字段
- [ ] 0.3.30 `configs`——**改造**，新增 `tenant_id` 字段
- [ ] 0.3.31 `prompts`——**改造**，新增 `tenant_id` 字段

> **DDL 编写规范**：无外键约束（弱关联，业务层保证），全表 `ENGINE=InnoDB DEFAULT CHARSET=utf8mb4`。**主键宽度按模块区分**：权限模块 `varchar(36)`（UUID）、管道/评估模块 `varchar(64)`（UUID）、知识库模块 `varchar(24)`（雪花ID）、`published_endpoints` 用 `BIGINT AUTO_INCREMENT` + `endpoint_id VARCHAR(64) UNIQUE`。时间字段用 `DATETIME`（自动 + 更新自动）。

### 2.4 Docker Compose（0.4）

- [ ] 0.4.1 创建 `rag-platform/docker-compose.yml`——完整 Compose 配置
  - **rag-platform** 服务：build `./backend`，端口 51002，mem_limit 4GB，cpus 2，depends_on mysql + redis（含 healthy 条件），healthcheck 调 `/health/`
  - **mysql** 服务：`mysql:5.7`，端口 3306，volume 挂载 `./init.sql`，`character-set-server=utf8mb4`
  - **redis** 服务：`redis:7.0-alpine`，端口 6379，`requirepass` 认证，`maxmemory-policy allkeys-lru`
  - **elasticsearch** 服务（可选 profile）：`docker.elastic.co/elasticsearch/elasticsearch:8.15.0`，端口 9200，`discovery.type=single-node`
  - **milvus + etcd + minio**（可选 profile milvus）：`milvusdb/milvus:v2.3.4` standalone + `quay.io/coreos/etcd:v3.5.5` + `minio/minio`
  - 命名 volumes：`rag-platform-data`, `rag-platform-logs`, `rag-platform-mysql`, `rag-platform-redis`, `rag-platform-es`, `rag-platform-etcd`, `rag-platform-minio`, `rag-platform-milvus`
- [ ] 0.4.2 创建 `backend/Dockerfile`——从 `backend/Dockerfile` 继承改造
  - 两阶段构建（uv 构建 + python:3.13-slim 运行时）
  - 工作目录 `/app/backend`
  - 新增 ES/Milvus 客户端库的 pip 安装（如 `pyproject.toml` 声明则自动安装）
  - CMD：`uvicorn src.server:create_app --host 0.0.0.0 --port 51002 --factory`
- [ ] 0.4.3 创建 `docker-compose.dev.yml`——开发覆盖文件
  - 挂载 `./backend/src` 到 `/app/backend/src`（热重载）
  - `APP_RELOAD=True`
  - 暴露 MySQL 和 Redis 端口给宿主机

### 2.5 前端基础设施（0.5）

- [ ] 0.5.1 创建 `frontend/package.json`——从 `frontend/package.json` 继承，改动：
  - **新增依赖**：`@xyflow/react`（React Flow 管道画布）
  - **保留**：`react`, `react-dom`, `react-router-dom`, `antd`, `@ant-design/pro-components`, `@ant-design/charts`, `zustand`, `@tanstack/react-query`, `vite`, `typescript`
  - 修改项目名 → `rag-platform-frontend`
- [ ] 0.5.2 创建 `frontend/vite.config.ts`——从 `frontend/vite.config.ts` 继承改造
  - 代理目标调整为 `http://127.0.0.1:51002`
  - 代理路径：`/api`、`/health`、`/metrics`
  - 保留路径别名：`@` → `src/`，`@app` → `src/app/`，`@pages` → `src/pages/`，`@features` → `src/features/`，`@entities` → `src/entities/`，`@shared` → `src/shared/`
- [ ] 0.5.3 创建 `frontend/tsconfig.json`——从 `frontend/tsconfig.json` 继承，保留 strict 模式。
- [ ] 0.5.4 创建 `frontend/src/app/App.tsx`——根组件，包含 `<Suspense><RouterProvider /></Suspense>` 结构。
- [ ] 0.5.5 创建 `frontend/src/router/index.tsx`——路由配置骨架
  - 预留 Phase 5/6/9 路由占位（先用占位组件）
  - 当前可用路由：`/` → 首页（dashboard 占位），`/system-config` → 系统配置，`/monitoring` → 监控，`/rag-eval` → 评估（继承），`*` → 404
- [ ] 0.5.6 创建 `frontend/src/shared/` 共享层骨架
  - `api/client.ts`——Axios/fetch 封装（继承）
  - `hooks/useAuth.ts`——认证 Hook 占位
  - `lib/constants.ts`——全局常量
  - `types/common.ts`——通用类型定义

---

## 3. 关键文件清单

| 文件路径 | 来源 | 说明 |
|---------|------|------|
| `rag-platform/CLAUDE.md` | **新增** | AI 上下文规则，从根 CLAUDE.md 派生去 backend/ 引用 |
| `rag-platform/init.sql` | **新增** | 31 张表完整 DDL，MySQL 容器自动初始化 |
| `rag-platform/docker-compose.yml` | **新增** | 完整 Compose，rag-platform + mysql + redis + ES/Milvus profiles |
| `rag-platform/docker-compose.dev.yml` | **新增** | 开发环境覆盖：热重载 + 端口暴露 |
| `backend/Dockerfile` | **改造** | 从 backend/Dockerfile 继承，适配 rag-platform 目录 |
| `backend/pyproject.toml` | **改造** | 从 backend/pyproject.toml 继承，移除 ML 依赖，新增 ES/Milvus |
| `backend/.env` | **改造** | 从 backend/.env 继承，移除评估专用凭证 |
| `backend/src/server.py` | **改造** | 移除评估路由，新增管道/权限路由占位，SPA 回退 |
| `backend/src/api/json_response.py` | **继承** | UtcJsonResponse、APIResponse.success() |
| `backend/src/api/sse.py` | **继承** | SSEPublisher、AsyncTaskManager |
| `backend/src/middleware/exception_handler.py` | **继承** | 全局异常处理 → 统一格式 |
| `backend/src/middleware/response_wrapper.py` | **继承** | 响应包装中间件 |
| `backend/src/middleware/trace_middleware.py` | **继承** | X-Trace-ID 自动注入 |
| `backend/src/core/tracing/context.py` | **继承** | TraceContext + Span 生命周期 |
| `backend/src/core/tracing/writer.py` | **继承+改造** | 异步队列写入器，新增 degraded 字段 |
| `backend/src/core/tracing/cost.py` | **继承** | CostCalculator 多模型定价 |
| `backend/src/core/tracing/cleanup.py` | **继承** | 过期 Trace TTL 清理 |
| `backend/src/core/tracing/truncation.py` | **继承** | prompt/completion 截断 |
| `backend/src/core/llm/factory.py` | **继承** | LLMServiceFactory |
| `backend/src/core/llm/embedding_factory.py` | **继承** | EmbeddingFactory |
| `backend/src/core/llm/adapters/langchain.py` | **继承** | LangChain LLM 适配器 |
| `backend/src/core/llm/adapters/llamaindex.py` | **继承** | LlamaIndex LLM 适配器 |
| `backend/src/core/llm/adapters/dashscope_multimodal.py` | **继承** | SafeDashScopeEmbedding 包装器 |
| `backend/src/core/llm/base.py` | **继承** | ILLMService 接口 |
| `backend/src/core/llm/log_collector.py` | **继承** | LLM 调用日志收集器 |
| `backend/src/core/config/cache.py` | **改造** | ConfigCache 去业务化，支持多租户 |
| `backend/src/core/prompt_impl/facade.py` | **继承** | PromptManager 门面 |
| `backend/src/core/prompt_impl/prompt_storage.py` | **继承** | 提示词持久化存储 |
| `backend/src/core/prompt_impl/ab_test_manager.py` | **继承** | 提示词 A/B 测试管理 |
| `backend/src/core/prompt_impl/initializer.py` | **改造** | 移除评估提示词模板 |
| `backend/src/core/knowledge_base/parser.py` | **改造** | 从 core/parsers.py 继承，通用化 |
| `backend/src/core/knowledge_base/embedding/engine.py` | **改造** | 从 core/embedding.py 继承，通用化 |
| `backend/src/service/monitoring_service.py` | **继承** | 监控服务 |
| `backend/src/service/alert_service.py` | **继承** | 告警服务 |
| `backend/src/service/trace_service.py` | **继承** | 追踪查询服务 |
| `backend/src/service/config_validation_engine.py` | **继承** | 配置校验引擎 |
| `backend/src/service/config_conflict_detector.py` | **继承** | 配置冲突检测 |
| `backend/src/service/config_health_service.py` | **继承** | 配置健康检查 |
| `backend/src/service/task_state_service.py` | **继承** | 异步任务状态管理 |
| `backend/src/service/task_sse_publisher.py` | **继承** | SSE 任务推送 |
| `backend/src/service/export_notification.py` | **继承** | 导出通知 |
| `backend/src/service/cache/facade.py` | **继承** | 三级缓存门面 |
| `backend/src/service/cache/memory.py` | **继承** | cachetools LRU |
| `backend/src/service/cache/redis_cache.py` | **继承** | Redis 缓存 |
| `backend/src/service/cache/disk_cache.py` | **继承** | 磁盘持久化缓存 |
| `backend/src/utils/logger.py` | **继承** | Loguru 结构化日志 |
| `backend/src/utils/exceptions.py` | **改造** | 移除评估异常，新增权限异常基类 |
| `backend/src/utils/helpers.py` | **继承** | 通用工具函数 |
| `backend/src/config/core/database.py` | **继承** | async_session_factory |
| `backend/src/config/core/redis_config.py` | **继承** | Redis 客户端配置 |
| `backend/src/config/core/settings.py` | **改造** | 移除儿童评估键，添加管道/权限键 |
| `backend/src/config/modules/database.py` | **继承** | 数据库连接池配置 |
| `backend/src/config/modules/redis.py` | **继承** | Redis 连接/缓存/锁配置 |
| `backend/src/config/modules/llm.py` | **改造** | 通用化 LLM 配置 |
| `backend/src/config/modules/rag.py` | **改造** | 适配管道模型配置 |
| `backend/src/config/rules/business_rules.py` | **改造** | 移除评估规则，添加管道/权限规则 |
| `frontend/Dockerfile` | **新增** | 两阶段构建（node 构建 + nginx 托管），Phase 0 内可选 |
| `frontend/package.json` | **改造** | 新增 @xyflow/react，移除无用依赖 |
| `frontend/vite.config.ts` | **改造** | 代理目标 51002，路径别名保留 |
| `frontend/tsconfig.json` | **继承** | TypeScript 严格模式配置 |
| `frontend/src/app/App.tsx` | **改造** | 根组件，路由调整 |
| `frontend/src/router/index.tsx` | **改造** | 路由骨架，预留 Phase 5/6/9 占位 |
| `frontend/src/shared/api/client.ts` | **继承** | Axios/fetch 封装 |
| `frontend/index.html` | **改造** | 标题改为 "RAG Platform" |
| `rag-platform/storage/` | **新增** | chroma + bm25 + documents 持久化目录 |

---

## 4. 测试策略

### 4.1 冒烟测试（Smoke Tests）

**测试 A：Docker Compose 启动与健康检查**

```
场景：验证 docker compose up 一键启动后所有核心服务可用
  1. 执行 docker compose up -d（等待 healthy）
  2. 验证 3 个容器 running + healthy：rag-platform-app, rag-platform-mysql, rag-platform-redis
  3. GET /health → 200, status=healthy, mysql.connected, redis.connected
  4. GET /metrics → 200, 返回 Prometheus 文本指标
  5. 执行 docker compose down
```

**测试 B：SPA 回退路由**

```
场景：验证非 API 路径刷新返回 index.html
  1. 构建前端 dist/（可为空占位 index.html）
  2. 启动后端
  3. GET / → 200, 返回 index.html
  4. GET /pipelines → 200, 返回 index.html（SPA 回退）
  5. GET /knowledge → 200, 返回 index.html（SPA 回退）
  6. GET /api/v1/health → 非 SPA 回退（走 API 路由）
  7. GET /metrics → 非 SPA 回退（走 Prometheus）
  8. 删除 dist/index.html → GET / → 404
```

**测试 C：Schema 初始化**

```
场景：验证 init.sql 无错误执行，31 张表全部创建
  1. 启动 docker compose up -d
  2. 等待 MySQL healthy
  3. 进入 MySQL 容器：docker compose exec mysql mysql -u raguser -pragpass rag_platform
  4. 执行 SHOW TABLES; → 返回 31 条记录
  5. 验证关键表存在：tenants, users, roles, knowledge_bases, kb_documents, pipelines, pipeline_versions, published_endpoints, test_cases, test_runs, knowledge_snapshots
```

### 4.2 基础设施测试（Infrastructure Tests）

**测试 D：继承模块导入**

```python
# tests/test_phase0_imports.py
async def test_inherited_modules_import():
    """验证所有继承模块可正常导入，不依赖 backend/"""
    from api.json_response import APIResponse
    from api.sse import SSEPublisher, AsyncTaskManager
    from middleware.exception_handler import global_exception_handler
    from middleware.response_wrapper import ResponseWrapperMiddleware
    from middleware.trace_middleware import TraceMiddleware
    from core.tracing.context import trace_context, create_span
    from core.tracing.writer import TraceWriter
    from core.tracing.cost import calculate_cost
    from core.llm.factory import LLMServiceFactory
    from core.llm.embedding_factory import EmbeddingFactory
    from core.config.cache import ConfigCache
    from core.prompt_impl.facade import PromptManager
    from utils.logger import logger
    from utils.exceptions import AppException
    # 所有导入不抛 ImportError 即通过
```

**测试 E：Endpoint 可访问性**

```python
# tests/test_phase0_endpoints.py
async def test_health_endpoint(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert data["data"]["status"] == "healthy"

async def test_metrics_endpoint(client):
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    assert "http_request_duration_seconds" in resp.text

async def test_spa_fallback(client):
    resp = await client.get("/pipelines")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
```

**测试 F：优雅关闭（Graceful Shutdown）**

```
场景：验证 SIGTERM 后 inflight 请求完成 + TraceWriter 刷盘
  1. 启动后端
  2. 启动一个慢请求（sleep 5s → 返回结果）
  3. 在慢请求执行中发送 SIGTERM
  4. 验证慢请求返回 200（未被中断）
  5. 验证进程在 30s 内退出
  6. 验证所有 Trace 记录 end_time 非空（无孤儿记录）
```

---

## 5. 验收检查点

完成以下全部检查项后，Phase 0 视为完成：

### 5.1 项目骨架

- [x] `rag-platform/CLAUDE.md` 存在，引用 `.ai/` 目录且不引用 `backend/`
- [x] `rag-platform/backend/src/` 目录结构完整（含所有占位 `__init__.py`）
- [x] `rag-platform/frontend/src/` 目录结构完整
- [x] `rag-platform/storage/` 目录存在，包含 chroma/、bm25/、documents/ 子目录

### 5.2 后端基础设施

- [x] `pyproject.toml` 不含 `xgboost`、`shap`、`scikit-learn` 依赖
- [x] `pyproject.toml` 含 `elasticsearch[async]`、`pymilvus` 依赖
- [x] `.env` 文件存在，不含儿童评估专用凭证
- [x] `server.py` 中 `create_app()` 可无错误启动
- [x] 所有继承模块可 import，无 `ModuleNotFoundError`
- [x] `core/config/cache.py` 含 `get_tenant_config()` 和 `get_tenant_value()` 方法（占位即可）
- [x] `core/prompt_impl/initializer.py` 不含评估提示词模板
- [x] `core/knowledge_base/parser.py` 存在且不引用 `backend/` 业务配置
- [x] `core/knowledge_base/embedding/engine.py` 存在且通用化

### 5.3 数据库 Schema

- [x] `init.sql` 语法正确（MySQL 5.7 兼容）
- [x] 31 张表 DDL 完整，无遗漏
- [x] 所有表含 `DEFAULT CHARSET=utf8mb4`
- [x] 主键宽度按模块区分：权限 `varchar(36)`、管道/评估 `varchar(64)`、知识库 `varchar(24)`、`published_endpoints` 用 `BIGINT AUTO_INCREMENT`
- [x] 无外键约束（弱关联设计）
- [x] `tenants` 表含 `slug UNIQUE` 约束
- [x] `trace_spans` 表新增 `degraded` BOOL 字段
- [x] `configs` 和 `prompts` 表新增 `tenant_id` 字段

### 5.4 Docker Compose

- [x] `docker-compose.yml` 含 rag-platform、mysql、redis 三个核心服务
- [x] ES 和 Milvus 服务配置在 profiles 下（`profiles: [elasticsearch]`、`profiles: [milvus]`）
- [x] rag-platform 服务 `mem_limit: 4g`、`cpus: 2`
- [x] `depends_on` 含 `condition: service_healthy`（mysql + redis）
- [x] healthcheck 调 `/health/`
- [x] mysql 服务挂载 `./init.sql:/docker-entrypoint-initdb.d/init.sql:ro`
- [x] `docker-compose.dev.yml` 存在且正确挂载源码卷

### 5.5 前端基础设施

- [x] `package.json` 含 `@xyflow/react` 依赖
- [x] `vite.config.ts` 代理目标 `http://127.0.0.1:51002`
- [x] `tsconfig.json` strict 模式启用
- [ ] `npm run dev` 可启动（无编译错误）——需要 npm install
- [x] `src/router/index.tsx` 含路由骨架
- [x] `src/shared/` 子目录结构完整

### 5.6 运行验证

- [ ] `docker compose up -d` 所有核心容器 `healthy`——需要 Docker 环境
- [ ] `curl http://localhost:51002/health` → 200——需要启动服务
- [ ] `curl http://localhost:51002/metrics` → 200（Prometheus 格式）——需要启动服务
- [ ] `curl http://localhost:51002/pipelines` → 200（SPA 回退，返回 index.html）——需要启动服务
- [ ] `curl http://localhost:51002/api/v1/nonexistent` → 404（非 SPA 回退，返回 JSON 错误）——需要启动服务
- [ ] MySQL 中 `SHOW TABLES;` 返回 31 条记录——需要 Docker 环境
- [ ] 后端日志中无 `ImportError` 或 `ModuleNotFoundError`——需要启动服务
- [ ] `docker compose down` 正常退出，无孤儿容器——需要 Docker 环境
- [ ] 前端 `npm run dev` 代理到 51002 正常——需要 npm install

---

## 附录 A：去业务化操作清单

Phase 0 中需要对继承模块执行的去业务化操作：

| 文件 | 操作 | 细节 |
|------|------|------|
| `pyproject.toml` | 移除依赖 | `xgboost`, `shap`, `scikit-learn` |
| `server.py` | 移除路由 | `task_controller`、`rag_controller` 评估部分 |
| `core/nodes/` | 整体移除 | 不继承 Agent 节点（PreNode~ReportNode） |
| `schemas/assessment.py` | 移除 | 儿童发展评估实体 |
| `schemas/ml.py` | 移除 | ML 评分模型 |
| `service/rag_eval/metrics/scoring/qwen_scorer.py` | 移除 | 通用 ML 评分器 |
| `core/prompt_impl/initializer.py` | 移除评估初始化 | 保留提示词管理基础设施 |
| `config/modules/` 配置键 | 移除儿童发展相关 | `child_development_*` 开头的所有键 |
| `config/rules/business_rules.py` | 移除评估规则 | 添加管道/权限规则 |
| `frontend/src/features/assessment/` | 整体移除 | 评估特性 |
| `frontend/src/pages/` 评估页面 | 移除 | 评估首页路由 |
| `init.sql` | 移除评估表 | `child_assessments` 等评估专用表 |

## 附录 B：与后续 Phase 的接口预留

Phase 0 需要为后续 Phase 预留以下接口占位（不实现业务逻辑）：

| 预留位置 | 用途 | 使用 Phase |
|---------|------|-----------|
| `server.py` 路由注册区 | `include_router(auth_router)` 等 | Phase 1 |
| `core/auth/` 目录 | JWT 签发/验证、密码哈希 | Phase 1 |
| `middleware/auth_middleware.py` | JWT 认证中间件（占位，注册到 middleware 链） | Phase 1 |
| `middleware/rate_limit_middleware.py` | QPS 限流中间件（占位） | Phase 4 |
| `core/pipeline/` 目录 | PipelineCompiler、NodeRegistry | Phase 3 |
| `core/knowledge_base/` 目录 | 向量存储适配器、分块引擎 | Phase 2 |
| `models/tenant.py` 等 | 权限数据模型 | Phase 1 |
| `repository/base.py` | 含 `_get_session(tenant_id)` 签名 | Phase 1 |
| `frontend/src/features/pipeline/` | 管道编辑器 | Phase 5 |
| `frontend/src/features/knowledgeBase/` | 知识库管理 | Phase 6 |
| `frontend/src/features/auth/` | 认证/租户管理 | Phase 9 |
| `frontend/src/router/` | 路由守卫 + 新路由 | Phase 5/6/9 |

---

*本文档基于 [implementation-checklist.md](../../implementation-checklist.md) Phase 0 和 [07-infrastructure.md](../by-module/07-infrastructure.md) 编写。实施时与本 checklist 逐项对齐。*
