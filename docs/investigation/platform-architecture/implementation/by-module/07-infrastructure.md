# 07 — 系统基础设施与部署 · 实现规格

> **定位**：rag-platform 的运行环境、非功能性需求、运维能力的完整实现规格。
> **与核心目标的关系**：实现 [核心目标 §〇](../../core-objectives.md#〇战略决策专攻-rag-platform弃用旧-backend) 的继承策略和独立部署。
> **来源**：本规格基于 [requirements/07-infrastructure-and-deployment.md](../requirements/07-infrastructure-and-deployment.md) 编写，补充完整实现细节。

---

## 1. Docker Compose 完整配置

### 1.1 完整 docker-compose.yml

```yaml
# ============================================
# rag-platform — Docker Compose 完整部署
#
# 使用方式：
#   一键启动：     docker compose up -d
#   含 ES 启动：   docker compose --profile elasticsearch up -d
#   含 Milvus 启动：docker compose --profile milvus up -d
#   完全体启动：   docker compose --profile elasticsearch --profile milvus up -d
#   开发环境：     docker compose -f docker-compose.yml -f docker-compose.dev.yml up
#
# 端口映射：
#   rag-platform : 51002  (API + SPA 静态文件)
#   mysql        : 3306   (暴露给宿主机调试)
#   redis        : 6379   (暴露给宿主机调试)
#   elasticsearch: 9200   (仅 profile elasticsearch)
#   milvus       : 19530  (仅 profile milvus)
#   minio        : 9000/9001 (仅 profile milvus)
# ============================================

version: "3.8"

services:
  # ─── rag-platform 后端 + 前端 ───
  rag-platform:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: rag-platform-app
    restart: unless-stopped
    mem_limit: 4g
    cpus: 2
    pids_limit: 4096
    shm_size: "1g"
    security_opt:
      - seccomp:unconfined
    ports:
      - "${APP_PORT:-51002}:51002"
    env_file: ${ENV_FILE:-.env}
    environment:
      APP_HOST: "0.0.0.0"
      APP_PORT: "51002"
      APP_RELOAD: "False"
      DATABASE_URL: "mysql+asyncmy://${MYSQL_USER:-raguser}:${MYSQL_PASSWORD:-ragpass}@mysql:3306/${MYSQL_DATABASE:-rag_platform}"
      REDIS_URL: "redis://:${REDIS_PASSWORD:-ragredis}@redis:6379/0"
      DATA_DIR: "/app/app_data/data"
      RAG_STORAGE_DIR: "/app/app_data/storage"
      RAG_TEMP_UPLOAD_DIR: "/app/app_data/temp_uploads"
      LOG_FILE: "/app/backend/logs/app.log"
      PATH: "/app/backend/.venv/bin:/usr/local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
      PYTHONPATH: "/app/backend"
      PYTHONUNBUFFERED: "1"
      PYTHONDONTWRITEBYTECODE: "1"
      OPENBLAS_NUM_THREADS: "1"
      OMP_NUM_THREADS: "1"
      MKL_NUM_THREADS: "1"
      # 可选：ES / Milvus 地址（仅当对应 profile 启用时生效）
      ES_URL: "http://elasticsearch:9200"
      MILVUS_HOST: "milvus-standalone"
      MILVUS_PORT: "19530"
    volumes:
      - rag_data:/app/app_data
      - rag_logs:/app/backend/logs
    command: ["/app/backend/.venv/bin/uvicorn", "src.server:create_app", "--host", "0.0.0.0", "--port", "51002", "--factory"]
    depends_on:
      mysql:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:51002/health/')"]
      interval: 30s
      timeout: 10s
      start_period: 120s
      retries: 3
    stop_grace_period: 35s

  # ─── MySQL 5.7 ───
  mysql:
    image: mysql:5.7
    container_name: rag-platform-mysql
    restart: unless-stopped
    environment:
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD:-root_ragpass}
      MYSQL_DATABASE: ${MYSQL_DATABASE:-rag_platform}
      MYSQL_USER: ${MYSQL_USER:-raguser}
      MYSQL_PASSWORD: ${MYSQL_PASSWORD:-ragpass}
    ports:
      - "${MYSQL_PORT:-3306}:3306"
    volumes:
      - mysql_data:/var/lib/mysql
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql:ro
    command:
      - --character-set-server=utf8mb4
      - --collation-server=utf8mb4_unicode_ci
      - --max_connections=200
      - --innodb_buffer_pool_size=512M
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost", "-u", "root", "-p${MYSQL_ROOT_PASSWORD:-root_ragpass}"]
      interval: 10s
      timeout: 5s
      start_period: 60s
      retries: 5

  # ─── Redis 7.0 ───
  redis:
    image: redis:7.0-alpine
    container_name: rag-platform-redis
    restart: unless-stopped
    command: redis-server --requirepass ${REDIS_PASSWORD:-ragredis} --maxmemory 512mb --maxmemory-policy allkeys-lru
    ports:
      - "${REDIS_PORT:-6379}:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD:-ragredis}", "ping"]
      interval: 10s
      timeout: 5s
      start_period: 10s
      retries: 5

  # ─── Elasticsearch 8.x (可选，profile: elasticsearch) ───
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.15.0
    container_name: rag-platform-es
    restart: unless-stopped
    profiles:
      - elasticsearch
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
      - "ES_JAVA_OPTS=-Xms1g -Xmx2g"
      - bootstrap.memory_lock=true
      - network.host=0.0.0.0
    ports:
      - "9200:9200"
    volumes:
      - es_data:/usr/share/elasticsearch/data
    ulimits:
      memlock:
        soft: -1
        hard: -1
    healthcheck:
      test: ["CMD-SHELL", "curl -s http://localhost:9200/_cluster/health | grep -q 'green\\|yellow'"]
      interval: 30s
      timeout: 10s
      start_period: 90s
      retries: 5

  # ─── Milvus 2.3 单机版 (可选，profile: milvus) ───
  etcd:
    image: quay.io/coreos/etcd:v3.5.5
    container_name: rag-platform-etcd
    restart: unless-stopped
    profiles:
      - milvus
    environment:
      - ETCD_AUTO_COMPACTION_MODE=revision
      - ETCD_AUTO_COMPACTION_RETENTION=1000
      - ETCD_QUOTA_BACKEND_BYTES=4294967296
      - ETCD_SNAPSHOT_COUNT=50000
    volumes:
      - etcd_data:/etcd
    command: etcd -advertise-client-urls=http://127.0.0.1:2379 -listen-client-urls http://0.0.0.0:2379 --data-dir /etcd
    healthcheck:
      test: ["CMD", "etcdctl", "endpoint", "health"]
      interval: 30s
      timeout: 20s
      retries: 3

  minio:
    image: minio/minio:RELEASE.2024-01-16T16-07-38Z
    container_name: rag-platform-minio
    restart: unless-stopped
    profiles:
      - milvus
    environment:
      MINIO_ROOT_USER: ${MINIO_ACCESS_KEY:-minioadmin}
      MINIO_ROOT_PASSWORD: ${MINIO_SECRET_KEY:-minioadmin}
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - minio_data:/minio_data
    command: minio server /minio_data --console-address ":9001"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 30s
      timeout: 20s
      retries: 3

  milvus-standalone:
    container_name: rag-platform-milvus
    image: milvusdb/milvus:v2.3.4
    restart: unless-stopped
    profiles:
      - milvus
    command: ["milvus", "run", "standalone"]
    security_opt:
      - seccomp:unconfined
    environment:
      ETCD_ENDPOINTS: etcd:2379
      MINIO_ADDRESS: minio:9000
      MINIO_ACCESS_KEY_ID: ${MINIO_ACCESS_KEY:-minioadmin}
      MINIO_SECRET_ACCESS_KEY: ${MINIO_SECRET_KEY:-minioadmin}
    volumes:
      - milvus_data:/var/lib/milvus
    ports:
      - "19530:19530"
      - "9091:9091"
    depends_on:
      - etcd
      - minio
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9091/healthz"]
      interval: 30s
      timeout: 20s
      start_period: 180s
      retries: 5

# ─── 命名 volumes ───
volumes:
  rag_data:
    name: rag-platform-data
  rag_logs:
    name: rag-platform-logs
  mysql_data:
    name: rag-platform-mysql
  redis_data:
    name: rag-platform-redis
  es_data:
    name: rag-platform-es
  etcd_data:
    name: rag-platform-etcd
  minio_data:
    name: rag-platform-minio
  milvus_data:
    name: rag-platform-milvus
```

### 1.2 开发覆盖文件 docker-compose.dev.yml

```yaml
# 开发环境覆盖：挂载源码卷，启用热重载
version: "3.8"
services:
  rag-platform:
    volumes:
      - ./backend/src:/app/backend/src
      - ./backend/pyproject.toml:/app/backend/pyproject.toml
      - rag_data:/app/app_data
      - rag_logs:/app/backend/logs
    environment:
      APP_RELOAD: "True"
    command: ["/app/backend/.venv/bin/uvicorn", "src.server:create_app", "--host", "0.0.0.0", "--port", "51002", "--factory", "--reload"]

  mysql:
    ports:
      - "3306:3306"

  redis:
    ports:
      - "6379:6379"
```

### 1.3 环境变量文件 .env

```bash
# ─── 基础设施凭证（仅存在于 .env，不写入 MySQL） ───
APP_PORT=51002
MYSQL_ROOT_PASSWORD=root_ragpass
MYSQL_DATABASE=rag_platform
MYSQL_USER=raguser
MYSQL_PASSWORD=ragpass
REDIS_PASSWORD=ragredis
JWT_SECRET=change-me-in-production-min-32-chars

# ─── 可选：Elasticsearch / Milvus 凭证 ───
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin

# ─── LLM 凭证兜底（API Key 可在此定义，MySQL 配置优先） ───
DASHSCOPE_API_KEY=
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
DEEPSEEK_API_KEY=
```

---

## 2. 项目目录结构

### 2.1 rag-platform/ 完整目录树及来源标注

每个文件标注来源：**【继承】**（从 backend/ 直接复制并去业务化）、**【改造】**（继承后修改）、**【新增】**（全新编写）。

```
rag-platform/
├── CLAUDE.md                              # 【新增】rag-platform 的 AI 上下文规则
│
├── backend/                               # 【继承+改造】从 backend/ 继承并去业务化
│   ├── Dockerfile                         # 【继承】两阶段构建（uv 构建 + python slim 运行时）
│   ├── pyproject.toml                     # 【改造】继承依赖清单，移除儿童评估相关依赖
│   ├── uv.lock                            # 【改造】重新生成锁文件
│   ├── .env                               # 【改造】移除评估专用凭证，保留基础设施凭证
│   ├── .env.test                          # 【改造】添加测试数据库/Redis 连接信息
│   ├── config/                            # 【继承】配置目录
│   │   └── logging_config.yaml            # 【继承】Loguru → YAML 日志配置
│   ├── src/
│   │   ├── server.py                      # 【改造】移除评估路由注册；添加管道/权限/租户路由
│   │   ├── api/
│   │   │   ├── json_response.py           # 【继承】UtcJsonResponse 类
│   │   │   └── sse.py                     # 【继承】SSEPublisher、AsyncTaskManager
│   │   ├── config/
│   │   │   ├── core/                      # 【继承】配置基础设施
│   │   │   │   ├── database.py            # 【继承】async_session_factory
│   │   │   │   ├── redis_config.py        # 【继承】Redis 客户端配置
│   │   │   │   └── settings.py            # 【改造】移除儿童评估键，添加管道/权限键
│   │   │   ├── modules/
│   │   │   │   ├── database.py            # 【继承】数据库连接池配置
│   │   │   │   ├── redis.py               # 【继承】Redis 连接/缓存/锁配置
│   │   │   │   ├── llm.py                 # 【改造】移除评估专用模型，保留通用 LLM 配置
│   │   │   │   └── rag.py                 # 【改造】适配管道模型配置
│   │   │   └── rules/
│   │   │       └── business_rules.py      # 【改造】移除评估规则，添加管道/权限规则
│   │   ├── controller/
│   │   │   ├── health_controller.py       # 【改造】增强健康检查，添加 MySQL/Redis/ES 连通性
│   │   │   ├── config_controller.py       # 【继承】配置管理 CRUD
│   │   │   ├── monitoring_controller.py   # 【继承】监控指标暴露
│   │   │   ├── alert_controller.py        # 【新增】告警规则配置 API
│   │   │   ├── rag_controller.py          # 【新增】管道执行/搜索 API
│   │   │   ├── pipeline_controller.py     # 【新增】管道 CRUD + 发布 API
│   │   │   ├── knowledge_base_controller.py # 【新增】知识库 CRUD + 索引 API
│   │   │   ├── auth_controller.py         # 【新增】登录/注册/刷新 token
│   │   │   ├── admin_controller.py        # 【新增】超管：租户管理/配额/系统状态
│   │   │   ├── search_controller.py       # 【新增】搜索 API（05 模块）
│   │   │   ├── rag_eval/
│   │   │   │   └── registry.py            # 【继承】RAG 评估控制器注册
│   │   │   └── prompt_management_controller.py # 【改造】移除评估提示词，保留基础设施
│   │   ├── core/
│   │   │   ├── database.py                # 【继承】异步引擎 + session factory
│   │   │   ├── redis_client.py            # 【继承】Redis 异步客户端单例
│   │   │   ├── di_container.py            # 【改造】移除评估专用模块注册，添加管道/权限模块
│   │   │   ├── scheduler.py               # 【改造】移除评估定时任务，保留 trace 清理
│   │   │   ├── config/
│   │   │   │   ├── __init__.py            # 【继承】
│   │   │   │   └── cache.py              # 【继承】ConfigCache 单例 + Redis Pub/Sub 热重载
│   │   │   ├── llm/
│   │   │   │   ├── factory.py             # 【继承】LLMServiceFactory
│   │   │   │   ├── embedding_factory.py   # 【继承】EmbeddingFactory
│   │   │   │   ├── log_collector.py       # 【继承】LLM 调用日志收集器
│   │   │   │   ├── base.py                # 【继承】ILLMService 接口定义
│   │   │   │   └── adapters/
│   │   │   │       ├── langchain.py           # 【继承】
│   │   │   │       ├── llamaindex.py          # 【继承】
│   │   │   │       └── dashscope_multimodal.py  # 【继承】SafeDashScopeEmbedding 包装器
│   │   │   ├── tracing/
│   │   │   │   ├── __init__.py            # 【继承】
│   │   │   │   ├── context.py             # 【继承】trace_context / create_span / contextvars
│   │   │   │   ├── writer.py              # 【改造】新增 degraded 字段支持
│   │   │   │   ├── cost.py                # 【继承】calculate_cost 多模型定价
│   │   │   │   ├── cleanup.py             # 【继承】过期 Trace TTL 清理
│   │   │   │   ├── truncation.py          # 【继承】prompt/completion 截断策略
│   │   │   │   └── langgraph_middleware.py # 【继承】TracingMiddleware
│   │   │   ├── pipeline/                  # 【新增】管道编译与执行引擎
│   │   │   │   ├── compiler.py            # 【新增】管道 JSON → 可执行 DAG
│   │   │   │   ├── executor.py            # 【新增】DAG 拓扑排序执行
│   │   │   │   ├── defaults.py            # 【新增】NODE_DEFAULTS 出厂值
│   │   │   │   ├── validator.py           # 【新增】管道配置校验
│   │   │   │   └── degrade.py             # 【新增】节点降级策略执行器
│   │   │   ├── rag/
│   │   │   │   ├── retriever.py           # 【改造】适配管道模型检索接口
│   │   │   │   ├── hybrid_search.py       # 【改造】BM25+向量混合检索
│   │   │   │   ├── reranker.py            # 【改造】重排序适配管道模型
│   │   │   │   └── dedup_engine.py        # 【继承】MinHash 去重
│   │   │   ├── knowledge_base/            # 【新增】知识库索引与同步
│   │   │   │   ├── indexer.py             # 【新增】增量/全量索引
│   │   │   │   ├── defaults.py            # 【新增】CHUNK_DEFAULTS + EMBEDDING_DEFAULTS
│   │   │   │   └── vector_store.py        # 【新增】Chroma/Milvus 向量库适配
│   │   │   ├── auth/                      # 【新增】认证授权核心
│   │   │   │   ├── jwt.py                 # 【新增】JWT 签发/验证
│   │   │   │   ├── password.py            # 【新增】密码哈希
│   │   │   │   ├── defaults.py            # 【新增】默认角色定义
│   │   │   │   └── tenant.py              # 【新增】租户上下文中间件
│   │   │   ├── metadata/                  # 【继承】文档元数据处理
│   │   │   └── prompt_impl/               # 【改造】提示词管理基础设施
│   │   │       ├── facade.py              # 【继承】PromptManager 门面
│   │   │       ├── manager.py             # 【继承】提示词版本管理
│   │   │       └── initializer.py         # 【改造】移除评估提示词模板
│   │   ├── middleware/
│   │   │   ├── trace_middleware.py         # 【继承】自动注入 TRACE_ID
│   │   │   ├── response_wrapper.py        # 【继承】统一响应包装
│   │   │   ├── exception_handler.py       # 【继承】全局异常处理
│   │   │   ├── auth_middleware.py          # 【新增】JWT 认证 + 租户隔离
│   │   │   ├── rate_limit_middleware.py    # 【新增】QPS 限流
│   │   │   └── cors_middleware.py          # 【新增】CORS 配置化
│   │   ├── models/
│   │   │   ├── base.py                    # 【继承】Base + UUID 主键 Mixin
│   │   │   ├── trace.py                   # 【继承】Trace + TraceStatus
│   │   │   ├── monitor.py                 # 【继承】LLMCallLog + CallLevel
│   │   │   ├── config.py                  # 【继承】ConfigVersion + ConfigAuditLog
│   │   │   ├── prompt_metadata.py         # 【继承】PromptMetadata
│   │   │   ├── prompt_version.py          # 【继承】PromptVersion
│   │   │   ├── document.py                # 【继承】SourceDocument + DocumentRecord
│   │   │   ├── pipeline.py                # 【新增】Pipeline + PipelineVersion + PipelineNode
│   │   │   ├── domain.py                  # 【新增】Domain（领域定义）
│   │   │   ├── knowledge_base.py          # 【新增】KnowledgeBase + KBChunk + KBIndex
│   │   │   ├── tenant.py                  # 【新增】Tenant + TenantQuota + TenantDeletionSnapshot
│   │   │   ├── user.py                    # 【新增】User + Role + Permission
│   │   │   ├── search.py                  # 【新增】SearchLog（搜索日志）
│   │   │   ├── alert.py                   # 【新增】AlertRule + AlertLog
│   │   │   └── rag_eval/                  # 【继承】RAG 评估 8 张表
│   │   │       ├── test_case.py           # 【继承】
│   │   │       ├── draft.py               # 【继承】
│   │   │       ├── test_set.py            # 【继承】
│   │   │       ├── test_set_case.py       # 【继承】
│   │   │       ├── test_run.py            # 【继承】
│   │   │       ├── test_run_result.py     # 【继承】
│   │   │       ├── report.py              # 【继承】
│   │   │       └── snapshot.py            # 【继承】
│   │   ├── repository/
│   │   │   ├── base.py                    # 【继承】BaseRepository 泛型基类
│   │   │   ├── config_repository.py       # 【继承】
│   │   │   ├── document_repository.py     # 【继承】
│   │   │   ├── monitor_repository.py      # 【继承】
│   │   │   ├── pipeline_repository.py     # 【新增】管道 CRUD
│   │   │   ├── knowledge_base_repository.py # 【新增】知识库 CRUD
│   │   │   ├── tenant_repository.py       # 【新增】租户 CRUD
│   │   │   ├── user_repository.py         # 【新增】用户 CRUD
│   │   │   ├── search_repository.py       # 【新增】搜索日志
│   │   │   ├── alert_repository.py        # 【新增】告警规则/日志
│   │   │   └── rag_eval/                  # 【继承】12 个评估 Repository
│   │   │       ├── draft_repository.py    # 【继承】
│   │   │       ├── test_case_repository.py # 【继承】
│   │   │       ├── test_set_repository.py # 【继承】
│   │   │       ├── test_set_case_repository.py # 【继承】
│   │   │       ├── test_run_repository.py # 【继承】
│   │   │       ├── test_run_result_repository.py # 【继承】
│   │   │       ├── snapshot_repository.py # 【继承】
│   │   │       ├── report_repository.py   # 【继承】
│   │   │       ├── tuning_suggestion_repository.py # 【继承】
│   │   │       ├── config_version_repository.py    # 【继承】
│   │   │       └── config_change_set_repository.py # 【继承】
│   │   ├── schemas/
│   │   │   ├── __init__.py                # 【改造】统一导出
│   │   │   ├── common.py                  # 【继承】APIResponse / PaginatedResponse / HealthResponse
│   │   │   ├── trace.py                   # 【新增】TraceMetadata 强化版
│   │   │   ├── health.py                  # 【改造】扩展 HealthResponse 增加 db_status/redis_status
│   │   │   ├── pipeline.py                # 【新增】管道实体（Pydantic）
│   │   │   ├── domain.py                  # 【新增】领域实体
│   │   │   ├── knowledge_base.py          # 【新增】知识库实体
│   │   │   ├── search.py                  # 【新增】搜索请求/响应实体
│   │   │   ├── auth.py                    # 【新增】Token/Login/Register 实体
│   │   │   ├── tenant.py                  # 【新增】租户/配额 实体
│   │   │   ├── alert.py                   # 【新增】告警规则/日志 实体
│   │   │   ├── config.py                  # 【继承】配置版本实体
│   │   │   └── rag_eval/                  # 【继承】RAG 评估实体
│   │   │       ├── __init__.py            # 【继承】统一导出
│   │   │       ├── draft.py               # 【继承】
│   │   │       ├── test_case.py           # 【继承】
│   │   │       ├── test_run.py            # 【继承】
│   │   │       ├── report.py              # 【继承】
│   │   │       └── metrics.py             # 【继承】
│   │   ├── service/
│   │   │   ├── pipeline_service.py        # 【新增】管道 CRUD + 编译 + 发布
│   │   │   ├── search_service.py          # 【新增】搜索门面服务
│   │   │   ├── knowledge_base_service.py  # 【新增】知识库索引管理
│   │   │   ├── auth_service.py            # 【新增】认证/租户服务
│   │   │   ├── alert_service.py           # 【继承+改造】告警服务
│   │   │   ├── config_service.py          # 【继承】
│   │   │   ├── monitoring_service.py      # 【继承】
│   │   │   ├── trace_service.py           # 【继承】
│   │   │   ├── task_state_service.py      # 【继承】
│   │   │   ├── task_sse_publisher.py      # 【继承】
│   │   │   ├── export_notification.py     # 【继承】
│   │   │   ├── cache/
│   │   │   │   ├── facade.py              # 【继承】三级缓存门面
│   │   │   │   ├── memory.py              # 【继承】cachetools LRU
│   │   │   │   ├── redis_cache.py         # 【继承】Redis 缓存
│   │   │   │   └── disk_cache.py          # 【继承】磁盘持久化缓存
│   │   │   ├── retrieval/                 # 【新增】检索服务簇
│   │   │   │   ├── facade.py              # 【新增】RetrievalFacade
│   │   │   │   ├── retriever.py           # 【新增】混合检索器
│   │   │   │   └── result_processor.py    # 【新增】结果后处理
│   │   │   ├── document_ingestion/        # 【继承】文档导入服务
│   │   │   │   ├── facade.py              # 【继承】DocumentIngestionFacade
│   │   │   │   ├── parser.py              # 【继承】PDF/EPUB/TXT 解析
│   │   │   │   └── chunker.py             # 【继承】分块器
│   │   │   ├── index_manager/             # 【继承】索引管理
│   │   │   │   └── facade.py              # 【继承】IndexManagerFacade
│   │   │   ├── rag_eval/                  # 【继承】RAG 评估 6 子引擎
│   │   │   │   ├── orchestrator.py        # 【继承】RagEvalOrchestrator
│   │   │   │   ├── draft/                 # 【继承】草稿引擎
│   │   │   │   ├── case/                  # 【继承】用例引擎
│   │   │   │   ├── run/                   # 【继承】运行引擎
│   │   │   │   ├── metrics/               # 【继承】评分引擎
│   │   │   │   ├── report/                # 【继承】报告引擎
│   │   │   │   └── tuning/                # 【继承】调优引擎
│   │   │   └── tenant/                    # 【新增】租户生命周期服务
│   │   │       ├── provisioning.py        # 【新增】租户创建自动化流程
│   │   │       └── deletion.py            # 【新增】软删除/归档/物理清理
│   │   └── utils/
│   │       ├── logger.py                  # 【继承】Loguru 结构化日志
│   │       ├── exceptions.py              # 【改造】移除评估异常，添加权限异常
│   │       └── helpers.py                 # 【继承】通用工具函数
│   └── tests/                             # 【改造+新增】
│       ├── conftest.py                    # 【改造】扩展 fixture：tenant/user/session
│       ├── test_health.py                 # 【新增】健康检查测试
│       ├── test_tracing.py                # 【新增】追踪系统测试
│       ├── test_config_hot_reload.py      # 【新增】配置热重载测试
│       ├── test_shutdown.py               # 【新增】优雅关闭测试
│       └── ...                            # 各模块测试文件
│
├── frontend/                              # 【改造】从 frontend/ 继承并去业务化
│   ├── Dockerfile                         # 【新增】两阶段构建（node 构建 + nginx 托管）
│   ├── package.json                       # 【改造】移除评估专用依赖（无变动）
│   ├── vite.config.ts                     # 【改造】调整代理目标为 51002
│   ├── tsconfig.json                      # 【继承】
│   ├── index.html                         # 【改造】更新标题
│   ├── public/                            # 【继承】favicon 等静态资源
│   ├── src/
│   │   ├── app/                           # 【改造】根组件调整路由
│   │   ├── api/
│   │   │   ├── client.ts                  # 【继承】Axios/fetch 封装
│   │   │   ├── auth.ts                    # 【新增】登录/注册/refresh 接口
│   │   │   ├── pipeline.ts                # 【新增】管道 CRUD 接口
│   │   │   ├── knowledgeBase.ts           # 【新增】知识库接口
│   │   │   ├── search.ts                  # 【新增】搜索接口
│   │   │   ├── config.ts                  # 【继承】配置接口
│   │   │   ├── monitoring.ts              # 【继承】监控接口
│   │   │   ├── tracing.ts                 # 【继承】追踪接口
│   │   │   ├── admin.ts                   # 【新增】租户管理接口
│   │   │   └── rag-eval/                  # 【继承】评估接口
│   │   ├── components/                    # 【继承+改造】
│   │   │   ├── monitoring/                # 【继承】TraceListView 等
│   │   │   ├── config/                    # 【继承】配置组件
│   │   │   └── layout/                    # 【新增】布局组件（含租户切换）
│   │   ├── entities/
│   │   │   ├── pipeline.ts                # 【新增】管道类型定义
│   │   │   ├── knowledgeBase.ts           # 【新增】知识库类型
│   │   │   ├── search.ts                  # 【新增】搜索类型
│   │   │   ├── auth.ts                    # 【新增】认证类型
│   │   │   ├── tenant.ts                  # 【新增】租户类型
│   │   │   ├── tracing/                   # 【继承】追踪实体
│   │   │   └── rag-eval/                  # 【继承】评估实体
│   │   ├── features/
│   │   │   ├── pipeline/                  # 【新增】管道管理特性
│   │   │   ├── knowledgeBase/             # 【新增】知识库特性
│   │   │   ├── search/                    # 【新增】搜索特性
│   │   │   ├── auth/                      # 【新增】登录/注册特性
│   │   │   ├── admin/                     # 【新增】超管特性
│   │   │   ├── monitoring/                # 【继承】LLM 监控
│   │   │   ├── rag-eval/                  # 【继承】RAG 评估
│   │   │   └── config/                    # 【继承】系统配置
│   │   ├── pages/
│   │   │   ├── LoginPage.tsx              # 【新增】
│   │   │   └── NotFoundPage.tsx           # 【新增】
│   │   ├── router/
│   │   │   └── index.tsx                  # 【改造】添加管道/搜索/租户路由
│   │   └── shared/
│   │       ├── api/                       # 【继承】通用 API 工具
│   │       ├── hooks/                     # 【继承】通用 Hooks
│   │       ├── lib/                       # 【继承】通用库
│   │       └── types/                     # 【继承】通用类型
│   └── tests/                             # 【继承+改造】
│
├── init.sql                               # 【新增】MySQL 初始化 DDL（从 .ai/full_init_script_mysql57.sql 派生）
│
├── storage/                               # 【新增】持久化存储（宿主机挂载目录）
│   ├── chroma/                            # 【新增】Chroma 向量库数据
│   ├── bm25/                              # 【新增】BM25 独立索引
│   └── documents/                         # 【新增】上传文档文件
│
└── docker-compose.yml                     # 【新增】完整 Docker Compose 配置
```

### 2.2 关键去业务化操作清单

| 文件 | 操作 | 细节 |
|------|------|------|
| `pyproject.toml` | 移除依赖 | 删除 xgboost, shap, scikit-learn（ML 评分不再需要） |
| `server.py` | 移除路由 | 删除 task_controller（评估任务）、原始 rag_controller 评估部分 |
| `src/core/nodes/` | 整体移除 | 不继承 Agent 节点（PreNode~ReportNode） |
| `src/schemas/ml.py` | 移除 | 不继承 ML 评分模型 |
| `src/schemas/assessment.py` | 移除 | 儿童发展评估实体 |
| `src/service/rag_eval/metrics/scoring/` | 删除 `qwen_scorer.py` | 不继承通用 ML 评分器 |
| `src/core/prompt_impl/initializer.py` | 移除评估提示词初始化 | 保留提示词管理基础设施 |
| `config/modules/` 配置键 | 移除儿童发展相关 | 如 `child_development_*` 开头的所有键 |
| `frontend/src/features/assessment/` | 整体移除 | 评估特性 |
| `frontend/src/pages/` | 移除评估页面 | 移除评估首页路由 |
| `init.sql` | 移除评估表 | 移除 `child_assessments` 等评估专用表 |

---

## 3. 配置热重载

### 3.1 ConfigCache 单例设计

**来源**：【继承】`backend/src/core/config/cache.py`，改造为多租户感知。

```
┌──────────────────────────────────────────────────────┐
│                    ConfigCache 单例                    │
├──────────────────────────────────────────────────────┤
│ - _instance: ConfigCache | None                      │
│ - _cache: dict[str, dict[str, Any]]                  │
│     key: config_version_id                           │
│     value: { config_snapshot, loaded_at, expires_at }│
│ - _lock: asyncio.Lock                                │
│ - _latest_config_id: str | None                      │
│ - _cache_ttl_minutes: int = 5                        │
│ - _redis_client: Redis                               │
│ - _pubsub: Redis PubSub                              │
│ - _listen_task: asyncio.Task                         │
│ - _polling_task: asyncio.Task   (pubsub降级备份)      │
│ - _cleanup_task: asyncio.Task                        │
│                                                      │
│ + get_instance() -> ConfigCache                      │
│ + initialize(redis_client) -> None                   │
│ + reload() -> None                                   │
│ + get_config(config_version_id) -> dict | None       │
│ + get_latest_config() -> dict | None                 │
│ + get_value(key, default) -> Any                     │
│ + get_int(key, default) -> int                       │
│ + get_str(key, default) -> str                       │
│ + shutdown() -> None                                 │
│                                                      │
│ # 多租户扩展                                           │
│ + get_tenant_config(tenant_id) -> dict | None         │
│ + get_tenant_value(tenant_id, key, default) -> Any    │
│ - _listen_config_changes() (Redis Pub/Sub)            │
│ - _periodic_polling() (轮询降级备份, 60s 间隔)         │
│ - _cleanup_expired() (过期条目清理)                    │
└──────────────────────────────────────────────────────┘
```

**关键实现约束**：

- 单例模式通过 `__new__` + `_instance` 实现
- `initialize()` 幂等：`_ever_initialized` 标志防止 uvicorn reload 重复初始化
- `reload()` 使用 `asyncio.Lock` 防止并发刷新
- 缓存条目 TTL 为 5 分钟，超时后由 `_periodic_cleanup()` 每分钟清理
- 多租户感知：扩展 `get_tenant_config(tenant_id)` 和 `get_tenant_value(tenant_id, key, default)` 方法，支持从租户级别配置表中读取

### 3.2 Redis Pub/Sub Channel 设计

```
频道名称格式：
  config_changed:{scope}

scope 取值：
  - "global"    → 全局配置变更（所有实例刷新）
  - "tenant:{tenant_id}" → 租户级配置变更（仅该租户实例刷新）

消息格式（JSON）：
{
  "type": "config_changed",
  "scope": "global",
  "config_version_id": "uuid-v4",
  "changed_by": "user_id",
  "timestamp": "2025-01-01T00:00:00Z",
  "changed_keys": ["llm.default_model", "rag.search_top_k"]
}
```

**发布方**（配置写入后立即发布）：
```python
# 在 ConfigController 的 update_config() 方法中
await redis_client.publish(
    "config_changed:global",
    json.dumps({
        "type": "config_changed",
        "scope": "global",
        "config_version_id": new_version_id,
        "changed_by": current_user_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "changed_keys": list(changed_config_keys),
    })
)
```

**订阅方**（ConfigCache 后台监听）：
```python
# 在 ConfigCache._listen_config_changes() 中
self._pubsub = self._redis_client.pubsub()
await self._pubsub.subscribe("config_changed:global")
async for message in self._pubsub.listen():
    if message["type"] == "message":
        await self.reload()
```

**降级备份**：
- 当 Redis Pub/Sub 连接异常（超时 3 次）时，自动切换到纯轮询模式
- 轮询间隔：60 秒，通过 `_periodic_polling()` 任务执行

### 3.3 配置 Key 命名规范

```
命名格式：{domain}.{sub_domain}.{key_name}

示例：
  llm.default_model                    # LLM 默认模型
  llm.model_pricing.qwen3_plus         # 模型定价
  rag.search_top_k                     # 搜索 top_k
  rag.hybrid_weight_vector             # 混合检索向量权重
  pipeline.max_nodes                   # 管道最大节点数
  pipeline.timeout_ms                  # 管道执行超时
  knowledge_base.default_chunk_size    # 默认分块大小
  auth.jwt_expire_minutes              # JWT 过期时间
  auth.password_min_length             # 密码最小长度
  rate_limit.search_qps                # 搜索 QPS 限流
  alert.degrade_threshold              # 降级告警阈值
```

### 3.4 配置热重载流程图

```
 ┌──────────┐    PUT /api/v1/config     ┌──────────┐
 │ 前端/API  │ ─────────────────────────▶│ Controller│
 └──────────┘                           └────┬─────┘
                                             │
                                    ┌────────▼────────┐
                                    │ ConfigService    │
                                    │ - 写入 MySQL      │
                                    │ - 创建新版本       │
                                    │ - 记录审计日志     │
                                    └────────┬────────┘
                                             │
                              ┌──────────────▼──────────────┐
                              │ Redis PUBLISH                │
                              │ CHANNEL: config_changed:global│
                              │ MSG: {version_id, keys...}   │
                              └──────────────┬──────────────┘
                                             │
                    ┌────────────────────────┼────────────────────────┐
                    ▼                        ▼                        ▼
           ┌──────────────┐         ┌──────────────┐         ┌──────────────┐
           │ 实例 A        │         │ 实例 B        │         │ 实例 C        │
           │ ConfigCache   │         │ ConfigCache   │         │ ConfigCache   │
           │ (Pub/Sub)     │         │ (Pub/Sub)     │         │ (Pub/Sub)     │
           └──────┬───────┘         └──────┬───────┘         └──────┬───────┘
                  │                        │                        │
                  ▼                        ▼                        ▼
           ┌──────────────┐         ┌──────────────┐         ┌──────────────┐
           │ reload()      │         │ reload()      │         │ reload()      │
           │ 从 MySQL 读取  │         │ 从 MySQL 读取  │         │ 从 MySQL 读取  │
           │ 最新配置       │         │ 最新配置       │         │ 最新配置       │
           └──────────────┘         └──────────────┘         └──────────────┘
```

**目标延迟**：
- 配置写入到所有实例刷新：< 5 秒（AC-7.11）
- Pub/Sub 传播延迟：< 100ms（Redis 内部）
- MySQL 读取 + 缓存更新：< 200ms
- 轮询降级模式下的最大延迟：60 秒

---

## 4. 全链路 Tracing

### 4.1 TraceWriter 异步队列设计

**来源**：【继承】`backend/src/core/tracing/writer.py`，扩展管道执行字段。

```
┌──────────────────────────────────────────────────────────────┐
│                      TraceWriter 架构                         │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────┐                                        │
│  │ 应用代码         │                                        │
│  │ (Controller/    │  await writer.record_*()               │
│  │  Service/Node)  │──────────────┐                         │
│  └─────────────────┘              │                         │
│                                   ▼                         │
│  ┌─────────────────────────────────────────┐                │
│  │         asyncio.Queue (max 10,000)       │                │
│  │  ┌──────┐ ┌──────┐ ┌──────┐     ┌──────┐│                │
│  │  │trace_│ │span  │ │llm_  │ ... │trace_││                │
│  │  │start │ │      │ │start │     │update││                │
│  │  └──────┘ └──────┘ └──────┘     └──────┘│                │
│  └────────────────────┬────────────────────┘                │
│                       │                                     │
│                       ▼                                     │
│  ┌─────────────────────────────────────────┐                │
│  │         _consumer() 后台协程              │                │
│  │  - 每 1.0s 或 batch_size=100 时 flush   │                │
│  │  - 合并 llm_start/llm_complete/llm_error │                │
│  │  - 批量 INSERT + UPDATE                  │                │
│  └────────────────────┬────────────────────┘                │
│                       │                                     │
│  ┌────────────────────▼────────────────────┐                │
│  │  队列满降级：_write_sync() 同步写入       │                │
│  └─────────────────────────────────────────┘                │
│                       │                                     │
│                       ▼                                     │
│              ┌───────────────┐                              │
│              │  MySQL (async) │                              │
│              │  traces +      │                              │
│              │  llm_call_logs │                              │
│              └───────────────┘                              │
└──────────────────────────────────────────────────────────────┘
```

**核心参数**：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `max_queue_size` | 10000 | 队列最大容量 |
| `sample_rate` | 1.0 | 正常请求采样率（100% 采样） |
| `error_sample_rate` | 1.0 | 错误请求采样率（100% 保留） |
| `batch_size` | 100 | 批量写入阈值 |
| `flush_interval` | 1.0s | 定时刷新间隔 |

**API 接口**：

| 方法 | 用途 | 采样 |
|------|------|------|
| `record_trace_start(trace_id, name, metadata, start_time)` | Trace 开始 | 不受采样影响 |
| `record_trace_end(trace_id, end_time)` | Trace 结束（自动计算总耗时 + 聚合 tokens/cost） | 不受采样影响 |
| `record_span(trace_id, span_id, parent_id, name, duration_ms, is_error)` | 节点级 Span | 受采样率影响 |
| `record_llm_start(...)` | LLM 调用开始（含 prompt_messages） | 受采样率影响 |
| `record_llm_complete(...)` | LLM 调用完成（含 completion/tokens/ttft） | 受采样率影响 |
| `record_llm_error(...)` | LLM 调用错误 | 全量保留 |
| `update_trace(trace_id, status, total_tokens, total_cost)` | 更新 Trace 状态 | 不受采样影响 |

**写入优化**：
- LLM start/complete/error 按 `span_id` 归并 → 一条 `LLMCallLog` 记录
- 一次查询获取已有记录 → 批量 INSERT 新增 + 批量 UPDATE 已有
- 所有非 LLM 类型的记录按类型依次处理

### 4.2 TraceContext Span 生命周期

**来源**：【继承】`backend/src/core/tracing/context.py`。

```
┌──────────────────────────────────────────────────────────┐
│                    Span 生命周期                           │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  1. Trace 创建 (trace_context)                            │
│     ├── 生成 UUID trace_id                                │
│     ├── 初始化 span_stack = []                            │
│     ├── 写入 TraceStart → TraceWriter 队列                │
│     └── 设置 contextvars: trace_id, span_stack            │
│                                                          │
│  2. Span 开始 (create_span)                               │
│     ├── 生成 UUID span_id                                 │
│     ├── 记录 start_time                                   │
│     ├── push span_id 到 span_stack                        │
│     └── 更新 contextvar span_stack                        │
│                                                          │
│  3. Span 结束 (create_span 的 finally)                     │
│     ├── 计算 duration_ms = (now - start_time) * 1000      │
│     ├── pop span_id 从 span_stack                         │
│     ├── 恢复 contextvar span_stack                        │
│     └── 提交 Span 到 TraceWriter 队列                     │
│                                                          │
│  4. Trace 结束 (trace_context 的 finally)                 │
│     ├── 写入 TraceEnd → TraceWriter 队列                  │
│     └── 重置 contextvars: trace_id=None, span_stack=None  │
│                                                          │
│  父子关系：                                               │
│  get_current_span_id() → span_stack[-1]                  │
│  get_parent_span_id()  → span_stack[-2]                  │
│                                                          │
│  Span 命名约定：                                           │
│  API Layer:   "{METHOD} {path}"   (如 "POST /api/v1/search")│
│  Pipeline:    "pipeline:{pipeline_id}"                    │
│  Domain:      "domain:{domain_id}"                        │
│  Node:        "node:{node_id}"                            │
│  LLM Call:    "llm:{scene}"       (如 "llm:rewrite")      │
│  Retrieval:   "retrieval:{index}" (如 "retrieval:chroma") │
└──────────────────────────────────────────────────────────┘
```

### 4.3 CostCalculator 模型定价

**来源**：【继承】`backend/src/core/tracing/cost.py`。

```
┌──────────────────────────────────────────────────────┐
│              CostCalculator 定价机制                  │
├──────────────────────────────────────────────────────┤
│                                                      │
│  公式：                                               │
│  cost = (input_tokens / 1,000,000) * input_price     │
│       + (output_tokens / 1,000,000) * output_price   │
│                                                      │
│  定价来源：                                           │
│  settings.model_pricing (从 .env 加载，MySQL 可覆盖)  │
│                                                      │
│  model_pricing:                                      │
│    qwen3-plus:                                       │
│      input_per_million: 2.0     # ¥2.0 / 1M tokens   │
│      output_per_million: 8.0    # ¥8.0 / 1M tokens   │
│    qwen3-max:                                        │
│      input_per_million: 20.0                          │
│      output_per_million: 80.0                         │
│    gpt-4o:                                           │
│      input_per_million: 37.5                          │
│      output_per_million: 150.0                        │
│    ...                                               │
│                                                      │
│  未配置定价的模型 → calculate_cost() 返回 None        │
│                                                      │
└──────────────────────────────────────────────────────┘
```

### 4.4 Pipeline Tracing Span Schema

管道执行的完整 Span 层次结构：

```
Trace: "POST /api/v1/search"                     # trace_id
├── Span: "auth:verify_jwt"                       # span_id_1, parent=None
│   └── duration_ms: 1
├── Span: "pipeline:{pipeline_id}"                # span_id_2, parent=span_id_1
│   ├── pipeline_id: "uuid"
│   ├── pipeline_version_id: "uuid"
│   └── pipeline_name: "default_rag_v2"
│   ├── Span: "domain:{domain_id_1}"             # span_id_3, parent=span_id_2
│   │   ├── domain_id: "uuid"
│   │   └── domain_name: "semantic_search"
│   │   ├── Span: "node:{node_id_a}"             # span_id_4, parent=span_id_3
│   │   │   ├── node_id: "uuid"
│   │   │   ├── node_type: "query_rewrite"
│   │   │   ├── duration_ms: 120
│   │   │   ├── degraded: false
│   │   │   └── Span: "llm:rewrite"              # span_id_5, parent=span_id_4
│   │   │       ├── model: "qwen3-plus"
│   │   │       ├── input_tokens: 120
│   │   │       ├── output_tokens: 80
│   │   │       ├── cost: 0.00088
│   │   │       └── ttft: 350
│   │   ├── Span: "node:{node_id_b}"             # span_id_6, parent=span_id_3
│   │   │   ├── node_id: "uuid"
│   │   │   ├── node_type: "hybrid_search"
│   │   │   ├── duration_ms: 45
│   │   │   ├── degraded: false
│   │   │   └── span_metadata: { "hits": 15, "index": "chroma" }
│   │   └── Span: "node:{node_id_c}"             # span_id_7, parent=span_id_3
│   │       ├── node_type: "rerank"
│   │       ├── duration_ms: 0
│   │       ├── degraded: true                    # 节点已降级
│   │       └── degrade_reason: "llm_timeout"
│   └── Span: "domain:{domain_id_2}"             # span_id_8, parent=span_id_2
│       └── domain_name: "keyword_search"
│       └── ...
└── total_duration_ms: 523
└── total_tokens: 200
└── total_cost: 0.00088
└── status: "success"  # 有降级但整体成功 → "partial"
```

**degraded 字段**：
- `degraded: false` → 节点正常执行
- `degraded: true` → 节点降级，跳过实际执行
- `degrade_reason` → 降级原因（如 `llm_timeout` / `model_unavailable` / `node_disabled`）

**span_metadata 扩展**（JSON 自由字段）：
```json
{
  "pipeline_id": "uuid",
  "domain_id": "uuid",
  "node_id": "uuid",
  "node_type": "hybrid_search",
  "degraded": false,
  "degrade_reason": null,
  "hits": 15,
  "index": "chroma",
  "search_time_ms": 42,
  "extra": {}
}
```

### 4.5 TraceMiddleware 集成

**来源**：【继承】`backend/src/middleware/trace_middleware.py`。

```
┌──────────────────────────────────────────────────────┐
│              TraceMiddleware 工作机制                  │
├──────────────────────────────────────────────────────┤
│                                                      │
│  请求进入：                                            │
│    1. 读取请求头 X-Trace-ID（前端可传递）               │
│    2. 进入 trace_context(name=METHOD path)            │
│    3. 生成/复用 trace_id                              │
│    4. 设置日志 TRACE_ID                               │
│    5. 执行下游中间件 + 控制器                           │
│                                                      │
│  请求返回：                                            │
│    6. 响应头注入 X-Trace-ID                            │
│    7. 退出 trace_context → 写入 TraceEnd              │
│    8. 清空日志 TRACE_ID                               │
│                                                      │
│  中间件顺序（server.py 中 add_middleware 的注册顺序）：  │
│    ① TraceMiddleware        (最外层优先)              │
│    ② ResponseWrapperMiddleware                       │
│    ③ AuthMiddleware          (新增)                  │
│    ④ RateLimitMiddleware     (新增)                  │
│    ⑤ CORSMiddleware                                 │
│                                                      │
└──────────────────────────────────────────────────────┘
```

---

## 5. Prometheus 指标

### 5.1 指标定义总览

**来源**：【继承】`prometheus_client` + FastAPI ASGI app 挂载。

所有指标通过 `/metrics` 端点暴露（`make_asgi_app()` 挂载）。

```
┌─────────────────────────────────────────────────────────────────┐
│                    Prometheus 指标全集                            │
├───────┬──────────────────────────┬────────┬──────────────────────┤
│ 序号   │ 指标名称                   │ 类型    │ 标签 (Labels)         │
├───────┼──────────────────────────┼────────┼──────────────────────┤
│  1    │ http_request_duration_   │ Hist   │ method, endpoint,     │
│       │   seconds                │        │ status_code           │
│  2    │ http_requests_total      │ Counter│ method, endpoint,     │
│       │                          │        │ status_code           │
│  3    │ llm_call_duration_ms     │ Hist   │ model, scene,         │
│       │                          │        │ status                │
│  4    │ llm_call_tokens_total    │ Counter│ model, scene,         │
│       │                          │        │ type (input/output)   │
│  5    │ llm_call_errors_total    │ Counter│ model, scene          │
│  6    │ cache_hit_ratio          │ Gauge  │ cache_layer           │
│       │                          │        │ (L1/L2/L3)            │
│  7    │ pipeline_execution_      │ Hist   │ pipeline_id,          │
│       │   duration_ms            │        │ pipeline_version_id   │
│  8    │ node_degradation_total   │ Counter│ pipeline_id, node_id, │
│       │                          │        │ reason                │
│  9    │ search_requests_total    │ Counter│ endpoint (search/     │
│       │                          │        │ hybrid_search)        │
│ 10    │ search_qps               │ Gauge  │ endpoint              │
│ 11    │ knowledge_base_index_    │ Gauge  │ kb_id, status         │
│       │   status                 │        │ (0=idle,1=indexing,   │
│       │                          │        │  2=ready,3=error)     │
│ 12    │ knowledge_base_chunk_    │ Gauge  │ kb_id                 │
│       │   count                  │        │                       │
│ 13    │ active_async_tasks       │ Gauge  │ task_type             │
│ 14    │ db_connection_pool_used  │ Gauge  │                       │
│ 15    │ redis_connection_pool_   │ Gauge  │                       │
│       │   used                   │        │                       │
│ 16    │ tenant_active_total      │ Gauge  │                       │
└───────┴──────────────────────────┴────────┴──────────────────────┘
```

### 5.2 指标详细定义

```
指标 1: http_request_duration_seconds
  Type: Histogram
  Description: HTTP 请求耗时分布
  Labels: method (GET/POST/...), endpoint (/api/v1/search),
          status_code (200/400/500)
  Buckets: [0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0]

指标 2: http_requests_total
  Type: Counter
  Description: HTTP 请求总数
  Labels: method, endpoint, status_code

指标 3: llm_call_duration_ms
  Type: Histogram
  Description: LLM 调用延迟分布
  Labels: model (qwen3-plus/...), scene (rewrite/rerank/generate),
          status (success/error/timeout)
  Buckets: [100, 200, 500, 1000, 2000, 5000, 10000, 30000, 60000]

指标 4: llm_call_tokens_total
  Type: Counter
  Description: LLM 调用 Token 消耗总量
  Labels: model, scene, type (input/output)

指标 5: llm_call_errors_total
  Type: Counter
  Description: LLM 调用失败总数
  Labels: model, scene

指标 6: cache_hit_ratio
  Type: Gauge
  Description: 各级缓存命中率（0.0 ~ 1.0）
  Labels: cache_layer (L1/L2/L3)
  计算方式：滑动窗口（最近 1000 次请求）

指标 7: pipeline_execution_duration_ms
  Type: Histogram
  Description: 管道执行耗时分布
  Labels: pipeline_id, pipeline_version_id
  Buckets: [50, 100, 250, 500, 1000, 3000, 5000, 10000, 30000]

指标 8: node_degradation_total
  Type: Counter
  Description: 节点降级次数
  Labels: pipeline_id, node_id, reason (llm_timeout/model_unavailable/...)

指标 9: search_requests_total
  Type: Counter
  Description: 搜索请求总数
  Labels: endpoint (search/hybrid_search)

指标 10: search_qps
  Type: Gauge
  Description: 搜索 QPS（滑动窗口 1 秒）
  Labels: endpoint

指标 11: knowledge_base_index_status
  Type: Gauge
  Description: 知识库索引状态
  Labels: kb_id, status
  值: 0=idle, 1=indexing, 2=ready, 3=error

指标 12: knowledge_base_chunk_count
  Type: Gauge
  Description: 知识库分块数量
  Labels: kb_id

指标 13: active_async_tasks
  Type: Gauge
  Description: 当前活跃异步任务数
  Labels: task_type (indexing/eval_run/export/cleanup)

指标 14: db_connection_pool_used
  Type: Gauge
  Description: 数据库连接池使用数

指标 15: redis_connection_pool_used
  Type: Gauge
  Description: Redis 连接池使用数

指标 16: tenant_active_total
  Type: Gauge
  Description: 活跃租户数
```

### 5.3 指标收集实现模式

```python
# 示例：在 SearchService 中埋点
from prometheus_client import Histogram, Counter, Gauge

PIPELINE_DURATION = Histogram(
    "pipeline_execution_duration_ms",
    "Pipeline execution duration in milliseconds",
    ["pipeline_id", "pipeline_version_id"],
    buckets=[50, 100, 250, 500, 1000, 3000, 5000, 10000, 30000],
)

NODE_DEGRADATION = Counter(
    "node_degradation_total",
    "Node degradation count",
    ["pipeline_id", "node_id", "reason"],
)

SEARCH_QPS_GAUGE = Gauge(
    "search_qps",
    "Search QPS (1s sliding window)",
    ["endpoint"],
)

@PIPELINE_DURATION.labels(
    pipeline_id=pipe_id,
    pipeline_version_id=version_id,
).time()
async def execute_pipeline(pipeline_id: str, query: str) -> SearchResult:
    for node_result in execute_dag():
        if node_result.degraded:
            NODE_DEGRADATION.labels(
                pipeline_id=pipeline_id,
                node_id=node_result.node_id,
                reason=node_result.degrade_reason,
            ).inc()
```

### 5.4 指标端点注册

```python
# server.py 中
from prometheus_client import make_asgi_app

metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)
```

**注意**：`/metrics` 端点**不经过 TraceMiddleware 和 AuthMiddleware**，因为它是 ASGI 子应用挂载，由 `prometheus_client` 直接处理。

---

## 6. 健康检查

### 6.1 GET /health 端点

**来源**：【改造】`backend/src/controller/health_controller.py`。

**路由**：`GET /health/`

**增强后的响应格式**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "status": "healthy",
    "timestamp": "2025-01-01T00:00:00Z",
    "version": "1.0.0",
    "uptime_seconds": 123456,
    "services": {
      "mysql": {
        "status": "connected",
        "latency_ms": 2
      },
      "redis": {
        "status": "connected",
        "latency_ms": 1,
        "pubsub_active": true
      },
      "elasticsearch": {
        "status": "connected",
        "cluster_health": "green"
      },
      "milvus": {
        "status": "connected",
        "collection_count": 5
      }
    },
    "component_status": {
      "config_cache": "initialized",
      "trace_writer": "running",
      "scheduler": "running",
      "llm_providers": {
        "dashscope": "configured",
        "openai": "not_configured"
      }
    },
    "resources": {
      "db_pool_used": 3,
      "db_pool_max": 20,
      "redis_pool_used": 1,
      "queue_size": 0,
      "active_tasks": 2
    }
  }
}
```

**状态码语义**：
| HTTP Status | status 值 | 含义 |
|-------------|----------|------|
| 200 | `healthy` | 所有必需服务连通 |
| 200 | `degraded` | 某个可选服务不可用（如 ES/Milvus），核心功能仍正常 |
| 503 | `unhealthy` | MySQL 或 Redis 不可用 |

### 6.2 连通性检查实现

```python
async def _check_mysql(session_factory) -> dict:
    """MySQL 连通性检查"""
    start = time.time()
    try:
        async with session_factory() as session:
            await session.execute(text("SELECT 1"))
        latency = (time.time() - start) * 1000
        return {"status": "connected", "latency_ms": round(latency, 1)}
    except Exception as e:
        return {"status": "disconnected", "error": str(e)}

async def _check_redis(redis_client) -> dict:
    """Redis 连通性检查"""
    start = time.time()
    try:
        await redis_client.ping()
        latency = (time.time() - start) * 1000
        pubsub_active = await _check_pubsub(redis_client)
        return {"status": "connected", "latency_ms": round(latency, 1), "pubsub_active": pubsub_active}
    except Exception as e:
        return {"status": "disconnected", "error": str(e)}

async def _check_elasticsearch() -> dict | None:
    """Elasticsearch 连通性检查（可选）"""
    try:
        es_url = os.getenv("ES_URL")
        if not es_url:
            return None
        # ... HTTP GET /_cluster/health
    except Exception:
        return {"status": "disconnected"}

async def _check_milvus() -> dict | None:
    """Milvus 连通性检查（可选）"""
    try:
        milvus_host = os.getenv("MILVUS_HOST")
        if not milvus_host:
            return None
        # ... Milvus health check
    except Exception:
        return {"status": "disconnected"}
```

### 6.3 HealthResponse Schema

```python
# schemas/health.py
class ServiceStatus(BaseModel):
    status: str           # "connected" | "disconnected"
    latency_ms: float | None = None
    error: str | None = None

class RedisServiceStatus(ServiceStatus):
    pubsub_active: bool = False

class ComponentStatus(BaseModel):
    config_cache: str     # "initialized" | "not_initialized"
    trace_writer: str     # "running" | "stopped"
    scheduler: str        # "running" | "stopped"

class HealthData(BaseModel):
    status: str                    # "healthy" | "degraded" | "unhealthy"
    timestamp: datetime
    version: str
    uptime_seconds: float
    services: dict[str, ServiceStatus | RedisServiceStatus | None]
    component_status: ComponentStatus
    resources: dict[str, int]
```

---

## 7. 优雅关闭

### 7.1 SIGTERM 处理流程

**来源**：【继承+扩展】`backend/src/server.py` 的 `lifespan()` 函数。

```
┌─────────────────────────────────────────────────────────────┐
│                    优雅关闭流程 (Graceful Shutdown)            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  SIGTERM 信号到达                                            │
│       │                                                     │
│       ▼                                                     │
│  ┌─────────────────────────────────────────┐                │
│  │ Phase 1: 停止接收新请求 (0s)              │                │
│  │ - uvicorn 自动处理：停止 accept 新连接     │                │
│  └────────────────────┬────────────────────┘                │
│                       │                                     │
│                       ▼                                     │
│  ┌─────────────────────────────────────────┐                │
│  │ Phase 2: 等待 inflight 请求完成 (≤ 30s)   │                │
│  │ - FastAPI lifespan shutdown 开始         │                │
│  │ - uvicorn 等待现有连接关闭                 │                │
│  │ - 超时后强制中断（uvicorn timeout_graceful_shutdown=30）  │
│  └────────────────────┬────────────────────┘                │
│                       │                                     │
│                       ▼                                     │
│  ┌─────────────────────────────────────────┐                │
│  │ Phase 3: 取消定时任务 (0.1s)              │                │
│  │ - stop_scheduler() → APScheduler 优雅关闭 │                │
│  └────────────────────┬────────────────────┘                │
│                       │                                     │
│                       ▼                                     │
│  ┌─────────────────────────────────────────┐                │
│  │ Phase 4: ConfigCache 关闭 (0.5s)         │                │
│  │ - 取消 _listen_task / _polling_task      │                │
│  │ - 取消 _cleanup_task                     │                │
│  │ - 关闭 PubSub 连接                        │                │
│  └────────────────────┬────────────────────┘                │
│                       │                                     │
│                       ▼                                     │
│  ┌─────────────────────────────────────────┐                │
│  │ Phase 5: TraceWriter 刷盘 (≤ 5s)         │                │
│  │ - 等待队列排空 (queue.join())             │                │
│  │ - 超时 5s 后强制放弃                      │                │
│  │ - 取消 _task consumer                    │                │
│  └────────────────────┬────────────────────┘                │
│                       │                                     │
│                       ▼                                     │
│  ┌─────────────────────────────────────────┐                │
│  │ Phase 6: 异步任务取消排序 (2s)            │                │
│  │ - 取消所有进行中的 AsyncTaskManager 任务   │                │
│  │ - 顺序：先取消 SSW 推送 → 再取消计算任务    │                │
│  │ - 每个任务 CancelledError 后处置资源       │                │
│  └────────────────────┬────────────────────┘                │
│                       │                                     │
│                       ▼                                     │
│  ┌─────────────────────────────────────────┐                │
│  │ Phase 7: 释放外部资源 (1s)                │                │
│  │ - LLMLogCollector.stop()                 │                │
│  │ - IndexManagerService.shutdown()         │                │
│  │ - DiskCache.shutdown()                   │                │
│  │ - 关闭数据库连接池                         │                │
│  │ - 关闭 Redis 连接                         │                │
│  └────────────────────┬────────────────────┘                │
│                       │                                     │
│                       ▼                                     │
│  ┌─────────────────────────────────────────┐                │
│  │ Phase 8: 日志退出 (0s)                    │                │
│  │ - logger.info("Application shutdown ...")│                │
│  │ - Loguru 日志自动刷盘                      │                │
│  └────────────────────┬────────────────────┘                │
│                       │                                     │
│                       ▼                                     │
│  进程退出 (exit code 0)                                      │
│                                                             │
│  总目标：≤ 30 秒完成全部清理                                   │
└─────────────────────────────────────────────────────────────┘
```

### 7.2 Docker Compose 停止配置

```yaml
# docker-compose.yml 中
rag-platform:
  stop_grace_period: 35s   # 比内部 30s 多 5s 冗余

# uvicorn 启动参数中
# timeout_graceful_shutdown=30  (uvicorn 默认值)
```

### 7.3 异常退出处理

```
SIGKILL (kill -9) 或 进程崩溃：
  - 不触发任何清理流程
  - 数据库中 Trace 记录可能处于孤儿状态（有 start 无 end）
  - 清理策略：定时任务 (scheduler) 每 5 分钟检查并关闭超过 10 分钟的孤儿 Trace
  - 队列中的追踪数据可能丢失（可接受，追踪数据为可丢失数据）

OOM Kill：
  - Docker 内存限制 4GB
  - 超过限制时 Docker 发出 SIGKILL
  - 方案：Grafana + Prometheus 监控内存使用 → 触发告警
```

---

## 8. 前端部署

### 8.1 SPA 回退路由配置

**来源**：【继承+改造】`backend/src/server.py` 中的 `spa_fallback` 路由。

```python
# server.py 中
frontend_dist_dir = os.path.join(os.path.dirname(__file__), "../../frontend/dist")
spa_enabled = os.path.isfile(os.path.join(frontend_dist_dir, "index.html"))

@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    """SPA回退路由：将所有非API路径的请求返回index.html"""
    if not spa_enabled:
        raise ResourceNotFoundException(message="页面不存在")

    # 跳过 API / 系统路由
    if full_path.startswith(
        ("api/", "docs", "openapi.json", "metrics", "health", "admin/")
    ):
        raise ResourceNotFoundException(message="页面不存在")

    # 静态文件直接返回
    file_path = os.path.join(frontend_dist_dir, full_path)
    if os.path.isfile(file_path):
        return FileResponse(file_path)

    # 回退到 index.html
    index_path = os.path.join(frontend_dist_dir, "index.html")
    if os.path.isfile(index_path):
        return FileResponse(index_path)

    raise ResourceNotFoundException(message="页面不存在")
```

**关键约束**：
- **最后注册**的 catch-all 路由（在所有 API 路由之后），避免拦截 API 请求
- 通过路径前缀白名单排除系统路由
- `spa_enabled` 检查：没有 `index.html` 时返回 404（开发环境不挂载前端时）

### 8.2 Vite 开发代理配置

**来源**：【改造】`frontend/vite.config.ts`。

```typescript
// vite.config.ts
server: {
  host: env.VITE_DEV_SERVER_HOST || '0.0.0.0',
  port: Number(env.VITE_DEV_SERVER_PORT) || 5173,
  proxy: {
    '/api': {
      target: env.VITE_API_BASE_URL || 'http://127.0.0.1:51002',
      changeOrigin: true,
    },
    '/health': {
      target: env.VITE_API_BASE_URL || 'http://127.0.0.1:51002',
      changeOrigin: true,
    },
    '/metrics': {
      target: env.VITE_API_BASE_URL || 'http://127.0.0.1:51002',
      changeOrigin: true,
    },
  },
},
```

**环境变量**：
```bash
# frontend/.env.development
VITE_API_BASE_URL=http://127.0.0.1:51002
VITE_DEV_SERVER_HOST=0.0.0.0
VITE_DEV_SERVER_PORT=5173
```

### 8.3 前端 Dockerfile（两阶段构建）

```dockerfile
# ─── Stage 1: 构建前端 ───
FROM node:20-alpine AS builder

WORKDIR /app/frontend

COPY package.json package-lock.json ./
RUN npm ci --production=false

COPY . .
RUN npm run build

# ─── Stage 2: Nginx 托管 ───
FROM nginx:1.25-alpine

COPY --from=builder /app/frontend/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
```

**nginx.conf（SPA 回退配置）**：
```nginx
server {
    listen 80;
    server_name _;

    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    # 静态资源缓存
    location /assets/ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

### 8.4 部署模式选择

| 模式 | 说明 | 适用场景 |
|------|------|---------|
| **FastAPI 直接托管** | `spa_fallback` 路由返回 `index.html` | 单容器部署，简单 |
| **Nginx 独立托管** | 独立的 `frontend` 容器 + Nginx | 生产环境，可独立扩缩容 |

**一期默认**：FastAPI 直接托管（`spa_fallback` 路由），简化部署。

**二期可选**：Nginx 独立托管，支持 CDN 缓存。

---

## 9. 测试策略

### 9.1 基础设施测试

#### 测试 1: Docker Compose 启动测试
```
场景: 验证 docker compose up 一键启动
  1. 执行 docker compose up -d
  2. 等待所有容器 healthy
  3. 验证 rag-platform 响应 GET /health
  4. 验证 MySQL 连接可用
  5. 验证 Redis 连接可用
  6. 验证 Prometheus /metrics 端点可访问
  7. 执行 docker compose down
```

#### 测试 2: 健康检查测试
```
场景: 验证健康检查返回完整状态
  1. 正常启动所有服务
  2. GET /health 返回 200, status=healthy, mysql=connected, redis=connected
  3. 停止 MySQL 容器
  4. GET /health 返回 503, status=unhealthy, mysql=disconnected
  5. 重启 MySQL 容器
  6. GET /health 返回 200, status=healthy
```

#### 测试 3: 配置热重载测试
```
场景: 验证 MySQL 配置更新后 5 秒内所有实例刷新
  1. 启动 2 个后端实例
  2. 通过 API 修改配置（如 search_top_k=5 → 10）
  3. 记录修改时间戳 t0
  4. 轮询两个实例的 GET /api/v1/config 确认新值
  5. 断言两个实例在 t0 + 5s 内都返回新值
  6. 验证 ConfigCache reload 日志出现
```

#### 测试 4: 配置 Pub/Sub 降级测试
```
场景: 验证 Redis Pub/Sub 异常时的轮询降级
  1. 启动后端，确认 ConfigCache Pub/Sub 监听中
  2. 模拟 Redis Pub/Sub 异常（断开连接）
  3. 验证 ConfigCache 3 次重试后放弃 Pub/Sub
  4. 验证 _periodic_polling 任务继续运行
  5. 修改 MySQL 配置
  6. 验证 60 秒内配置生效（轮询模式）
```

### 9.2 追踪测试

#### 测试 5: Span 生命周期测试
```
场景: 验证完整的 Trace → Span → LLM 调用链
  1. 发送搜索请求 POST /api/v1/search
  2. 提取响应头 X-Trace-ID
  3. 查询数据库 traces 表：验证 Trace 记录存在，status=success
  4. 查询数据库 llm_call_logs 表：验证 Span 记录存在
  5. 验证父子关系：parent_span_id 形成完整树
  6. 验证 tokens 和 cost 字段非空
  7. 验证 total_duration_ms > 0
```

#### 测试 6: TraceWriter 刷盘测试
```
场景: 验证优雅关闭时队列数据不丢失
  1. 启动后端
  2. 发送 50 个并发搜索请求（生成大量追踪数据）
  3. 发送 SIGTERM
  4. 等待进程退出
  5. 查询数据库：验证所有 Trace 记录的 end_time 非空
  6. 验证所有 Span 记录完整写入
  7. 验证无 orphan Trace（有 start 无 end）
```

#### 测试 7: 降级 Span 测试
```
场景: 验证节点降级时的 Span 记录
  1. 配置管道中某个节点 LLM 超时 100ms（故意触发降级）
  2. 发送搜索请求
  3. 查询 Span 记录：验证 degraded=true
  4. 验证 degrade_reason 字段记录降级原因
  5. 验证 NODE_DEGRADATION 指标 +1
```

#### 测试 8: 采样率测试
```
场景: 验证采样率配置生效
  1. 配置 trace_sample_rate=0.5
  2. 发送 1000 个搜索请求
  3. 查询数据库：验证 Span 记录数 ≈ 500（范围 400-600）
  4. 验证 Trace 记录 = 1000（Trace 不受采样影响）
```

### 9.3 优雅关闭测试

#### 测试 9: Graceful Shutdown 测试
```
场景: 验证 SIGTERM 后 inflight 请求完成 + 追踪数据刷盘
  1. 启动后端
  2. 启动一个慢请求（sleep 5s → 返回结果）
  3. 在慢请求执行中发送 SIGTERM
  4. 验证慢请求返回 200（未被中断）
  5. 验证慢请求的 Trace 记录完整
  6. 验证进程在 30s 内退出
```

#### 测试 10: 异步任务取消测试
```
场景: 验证关闭时异步任务正确取消
  1. 启动一个知识库重建任务（AsyncTaskManager）
  2. 任务运行到一半时发送 SIGTERM
  3. 验证任务被取消（CancelledError）
  4. 验证任务状态更新为 cancelled
  5. 验证 SSE 推送 channel_cleanup 消息
```

### 9.4 前端部署测试

#### 测试 11: SPA 回退路由测试
```
场景: 验证非 API 路径刷新返回 index.html
  1. 构建前端 npm run build
  2. 启动后端（挂载 dist/）
  3. GET / → 200, 返回 index.html
  4. GET /pipeline → 200, 返回 index.html
  5. GET /knowledge-base → 200, 返回 index.html
  6. GET /api/v1/search → 200, 返回 JSON（非 SPA 回退）
  7. GET /health → 200, 返回 JSON（非 SPA 回退）
  8. GET /metrics → 200, 返回 Prometheus 文本（非 SPA 回退）
  9. 删除 dist/index.html
  10. GET / → 404, 返回 ResourceNotFoundException
```

#### 测试 12: Vite 代理测试
```
场景: 验证开发环境代理配置正确
  1. 启动后端: uvicorn (51002)
  2. 配置 VITE_API_BASE_URL=http://127.0.0.1:51002
  3. 启动前端: npm run dev (5173)
  4. GET http://127.0.0.1:5173/api/v1/config → 代理到 51002, 返回配置 JSON
  5. GET http://127.0.0.1:5173/health → 代理到 51002, 返回健康检查 JSON
```

### 9.5 Prometheus 指标测试

#### 测试 13: 指标暴露测试
```
场景: 验证 /metrics 端点暴露所有必要指标
  1. 启动后端，发送若干搜索请求
  2. GET /metrics
  3. 验证包含 http_request_duration_seconds 指标
  4. 验证包含 llm_call_duration_ms 指标
  5. 验证包含 cache_hit_ratio 指标
  6. 验证包含 pipeline_execution_duration_ms 指标
  7. 验证包含 node_degradation_total 指标
  8. 验证包含 search_qps 指标
  9. 验证包含 knowledge_base_index_status 指标
```

### 9.6 安全测试

#### 测试 14: JWT 认证测试
```
场景: 验证 JWT 认证中间件
  1. 无 Token 请求 GET /api/v1/pipelines → 401
  2. 无效 Token 请求 GET /api/v1/pipelines → 401
  3. 过期 Token 请求 GET /api/v1/pipelines → 401
  4. 有效 Token 请求 GET /api/v1/pipelines → 200
  5. 停用租户的 Token 请求 → 403, error_code=TENANT_DISABLED
```

#### 测试 15: CORS 测试
```
场景: 验证 CORS 头正确返回
  1. 发送 OPTIONS 预检请求
  2. 验证 Access-Control-Allow-Origin 头存在
  3. 验证 Access-Control-Allow-Methods 包含 POST/GET/PUT/DELETE
  4. 验证 Access-Control-Allow-Headers 包含 Authorization/Content-Type/X-Trace-ID
```

---

## 10. 验收标准映射

### 10.1 验收标准 ↔ 测试场景映射表

| AC | 验收标准 | 对应测试 | 预期结果 |
|----|---------|---------|---------|
| AC-7.1 | 超管创建租户后自动初始化 DB 空间、存储目录、默认角色、初始管理员 | `test_tenant_provisioning`（见 04-permission 规格） | 事务性创建，任一失败全部回滚 |
| AC-7.2 | 创建流程任一步骤失败则全部回滚 | `test_tenant_provisioning_rollback` | slug 重复/存储创建失败 → 数据库无残留记录 |
| AC-7.3 | 配额上限时返回对应错误码 | `test_quota_enforcement` | 429 QUOTA_EXCEEDED / 413 STORAGE_QUOTA_EXCEEDED |
| AC-7.4 | 超管可调整租户配额 | `test_quota_update` | PUT 后 GET 验证生效 |
| AC-7.5 | 停用租户后登录/搜索不可用 | `test_tenant_disable` | 停用 Token → 403；搜索 API → 403 |
| AC-7.5a | 归档租户不计入活跃配额 | `test_tenant_archive` | 归档后超管可创建新租户（不超配额限制） |
| AC-7.5b | 软删除 30 天可恢复 | `test_tenant_soft_delete` | 30 天内 PUT restore → 成功；超期 → 404 |
| AC-7.6 | docker compose up 一键启动 | **测试 1** | 所有容器 healthy，health 端点 200 |
| AC-7.7 | rag-platform 不依赖 backend/ | **测试 1** | 无需 backend/ 代码即可启动 |
| AC-7.8 | health 端点返回 MySQL/Redis 连通性 | **测试 2** | status 含 mysql.connected, redis.connected |
| AC-7.9 | /metrics 端点暴露指标 | **测试 13** | 含 HTTP/LVM/缓存/QPS 指标 |
| AC-7.10 | 全链路 Tracing：管道→域→节点 Span | **测试 5** | Span 层级树正确，含耗时和成本 |
| AC-7.11 | 配置热重载 5 秒内生效 | **测试 3** | 2 实例在 t0+5s 内均返回新值 |
| AC-7.12 | JWT 认证 — 401/403 正确 | **测试 14** | 无 Token→401；无效→401；过期→401；停用→403 |
| AC-7.13 | CORS 配置正确 | **测试 15** | 预检响应头正确 |
| AC-7.14 | 容器资源限制 4GB/2CPU | **测试 1 验证阶段** | `docker inspect` 确认内存/CPU 限制 |
| AC-7.15 | 优雅关闭—inflight 完成 + TraceWriter 刷盘 | **测试 9, 测试 6** | 慢请求返回 200；Trace 无孤儿记录 |
| AC-7.16 | qwen_scorer 不在继承清单 | 代码审查（非测试） | `rag-platform/` 中不存在 `qwen_scorer*` |
| AC-7.17 | 节点降级超阈值告警 | **测试 7** + AlertService 测试 | 降级次数超阈值 → 告警通知生成 |
| AC-7.18 | SPA 回退路由—刷新非根路径不 404 | **测试 11** | `/pipeline` 返回 index.html |
| AC-7.19 | 异常统一格式化 | 异常测试（servertest） | 所有异常返回 `{code, message, error_code, details}` |
| AC-7.20 | 日志为结构化 JSON + TRACE_ID | 日志格式测试 | 日志行含 `trace_id` 字段 |

### 10.2 测试环境要求

| 需求 | 配置 |
|------|------|
| 测试框架 | pytest + pytest-asyncio |
| 数据库 | 独立测试 MySQL 数据库（`rag_platform_test`），测试前后自动创建/销毁表 |
| Redis | 独立测试 Redis DB（DB 1），测试后 flushdb |
| Docker | CI 环境需要 Docker，用于启动容器集成测试 |
| 模拟 | `unittest.mock` 模拟外部 LLM 调用（加速测试） |
| Fixture | 预置 fixture：`async_session`, `redis_client`, `auth_headers`, `test_tenant` |

### 10.3 测试执行命令

```bash
# 单元测试（不需要 Docker）
cd rag-platform/backend && uv run pytest tests/ -m "not integration" -v

# 集成测试（需要 Docker）
cd rag-platform/backend && uv run pytest tests/ -m integration -v

# 基础设施集成测试（需要 Docker）
cd rag-platform/backend && uv run pytest tests/test_health.py tests/test_tracing.py tests/test_shutdown.py -v

# 全量测试
cd rag-platform/backend && uv run pytest tests/ -v
```

---

## 附录 A：与其他模块的接口契约

### A.1 提供给各模块的能力

| 提供给 | 能力 | 契约说明 |
|--------|------|---------|
| **01-管道** | 管道 DAG 编译与执行 | `PipelineExecutor.execute(pipeline_id, query) -> ExecutionResult`；每个节点 Span 自动生成 |
| **02-域** | 域服务注册 | `DomainRegistry.get(domain_id) -> DomainService`；由 DI 容器自动注入 |
| **03-知识库** | 向量存储 + 索引管理 | `VectorStoreAdapter` 接口（Chroma/Milvus 实现）；`IndexManagerFacade` 门面 |
| **04-权限** | JWT 签发/验证、租户上下文 | `AuthMiddleware` 自动注入 `current_user`、`current_tenant`；`require_role()` 装饰器 |
| **05-搜索** | 全链路追踪、SSE 推送 | `TraceMiddleware` 自动注入 TRACE_ID；`SSEPublisher` 推送搜索进度 |
| **06-评估** | 异步任务管理、配置热重载 | `AsyncTaskManager` 管理评估任务生命周期；`ConfigCache` 提供配置快照 |

### A.2 基础设施模块自身依赖

| 依赖项 | 用途 | 配置位置 |
|--------|------|---------|
| MySQL 5.7 | 持久化存储 | `.env` → `DATABASE_URL` |
| Redis 7.0 | 缓存/锁/PubSub/Session | `.env` → `REDIS_URL` |
| Chroma (本地) | 默认向量存储（L0） | 文件系统，无需网络 |
| Elasticsearch 8.x | 可选：ES 向量检索/BM25 | `.env` → `ES_URL`（可选 profile） |
| Milvus 2.3 | 可选：分布式向量检索 | `.env` → `MILVUS_HOST`/`MILVUS_PORT`（可选 profile） |
| Prometheus | 指标抓取（外部系统） | `/metrics` 端点暴露，无需后端主动连接 |
| Docker | 容器运行时 | Docker Engine 24+ |

---

## 附录 B：关键设计决策 (ADR)

### ADR-007-01: 一期不启用容器级别的多实例

**决策**：一期 docker-compose 中 `rag-platform` 服务仅运行单实例。
**理由**：多实例需要同步状态（ConfigCache Pub/Sub 已就绪，但 session 共享、限流全局计数器等需额外基础设施）。二期可通过 `docker compose up --scale rag-platform=3` 扩容。
**影响**：ConfigCache 的 Redis Pub/Sub 机制已预留，无需代码变更即可支持多实例。

### ADR-007-02: 前端托管方式

**决策**：一期使用 FastAPI 直接托管（`spa_fallback` 路由），二期可选 Nginx 独立容器。
**理由**：简化初始部署，减少配置文件数量。FastAPI 的 `FileResponse` 在生产环境性能足够。
**影响**：前端构建产物 `dist/` 需放置在 Docker 镜像内（由 `backend/Dockerfile` 的 COPY 负责）。

### ADR-007-03: 弹性搜索 (ES) 和 Milvus 作为可选 profile

**决策**：ES 和 Milvus 通过 Docker Compose `profiles` 实现可选启用，默认不启动。
**理由**：一期以 Chroma（本地）为默认向量存储，降低部署门槛。用户需要时通过 `--profile` 按需启用高级向量存储。
**影响**：所有 ES/Milvus 相关代码必须向后兼容，未配置时优雅降级（返回 `not_configured` 而非报错）。

### ADR-007-04: 追踪数据为可丢失数据

**决策**：追踪数据（Traces, Spans, LLMCallLogs）标记为"可丢失"数据，优雅关闭时尽力写入，超时后放弃。
**理由**：追踪数据量大，不应阻塞核心业务流程。Tracing 是观测能力，不是事务数据。
**影响**：极端情况下（进程崩溃）少量追踪数据可能丢失。通过 30 天 TTL 自动清理 + 孤儿 Trace 定时修复保证数据整洁。
