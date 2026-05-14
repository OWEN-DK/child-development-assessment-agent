# 07 — 系统基础设施与部署

> **定位**：定义 rag-platform 的运行环境、非功能性需求和运维能力。从 backend/ 继承全部基础设施，去业务化后独立部署。
> **与核心目标的关系**：实现 [核心目标 §〇](./core-objectives.md#〇战略决策专攻-rag-platform弃用旧-backend) 的继承策略和 [核心目标 §七、§八](./core-objectives.md#七模块化改造范围仅限-rag-模块调用方不限制技术)。

---

## 配置层级总览（全平台）

这是所有模块配置层级的统一视图。各模块文档中出现的层级标注（[L0]/[L1]/[L2]/[L3]）以此为基准。

```
┌─────────────────────────────────────────────────────────┐
│ L0: 平台默认                                             │
│   配置者: 超管 + 系统内置                                  │
│   存储: 代码常量 + .env 兜底                               │
│   范围: 所有租户共享                                       │
│   示例: 节点出厂默认值、系统提示词、默认色块大小 512、超时 30s  │
├─────────────────────────────────────────────────────────┤
│ L1: 租户覆盖                                             │
│   配置者: 租户 admin                                      │
│   存储: MySQL 全局配置表 (per tenant)                      │
│   范围: 单个租户内所有资源                                  │
│   示例: LLM 模型选择、默认指标阈值、默认分块参数、提示词模板    │
├─────────────────────────────────────────────────────────┤
│ L2: 资源配置                                             │
│   配置者: 租户 editor / admin                             │
│   存储: MySQL 各资源表 (pipeline_versions / knowledge_bases)│
│   范围: 单个管道 / 单个知识库 / 单个评估运行                 │
│   示例: 节点参数、域权重、分块策略、Embedding 模型、文档 ACL  │
├─────────────────────────────────────────────────────────┤
│ L3: API 参数                                             │
│   配置者: API 调用方                                      │
│   存储: 请求体 params，仅白名单参数允许覆盖                  │
│   范围: 单次请求                                          │
│   示例: top_k、temperature、filters                       │
└─────────────────────────────────────────────────────────┘
```

**覆盖规则**：L3 > L2 > L1 > L0。高层级未设时 fallback 到低层级。

**各模块的 L0 值来源**：

| 模块 | L0 来源 |
|------|--------|
| 01-管道 | `backend/src/core/pipeline/defaults.py` 中的 `NODE_DEFAULTS` dict |
| 03-知识库 | `backend/src/core/knowledge_base/defaults.py` 中的 `CHUNK_DEFAULTS`、`EMBEDDING_DEFAULTS` |
| 04-权限 | 内置角色定义（admin/editor/viewer）+ `backend/src/core/auth/defaults.py` |
| 05-搜索 | `MAX_QUERY_LENGTH=2000`、`MAX_BODY_SIZE=1MB` 等常量 |
| 06-评估 | `_DEFAULT_THRESHOLDS` dict + `DEFAULT_WEIGHTS = {L1:0.4, L2:0.4, L3:0.2}` |
| 07-基础设施 | `.env` 中的 DATABASE_URL、REDIS_URL、JWT_SECRET 等 |

---

## 1. backend/ 继承清单

### 1.1 完整继承

| 类别 | 继承项 | 来源文件/目录 |
|------|--------|-------------|
| **基础设施配置** | HTTP 端口 51002、分解式 DB 字段、数据库连接池、Redis 全套（密码/连接池/缓存/PubSub/锁/Session）、JWT 认证、CORS、Prometheus、健康检查、Docker 资源限制 4GB/2CPU | `backend/.env`, `backend/Dockerfile`, `docker-compose.yml` |
| **统一响应** | `APIResponse` 类、`AppException` 体系、全局异常处理器 | `backend/src/api/json_response.py`, `backend/src/middleware/exception_handler.py` |
| **响应包装** | 中间件自动包装成功响应为 `{code, message, data}` 格式 | `backend/src/middleware/response_wrapper.py` |
| **全链路追踪** | `TraceWriter`（异步队列写入+优雅关闭）、`TraceContext`（Span 嵌套+父子关系）、`CostCalculator`（多模型定价） | `backend/src/core/tracing/` |
| **追踪中间件** | 自动注入 TRACE_ID | `backend/src/middleware/trace_middleware.py` |
| **LLM 适配器** | LangChain/LlamaIndex/DashScope 适配器 | `backend/src/core/llm/adapters/` |
| **LLM 工厂** | `LLMServiceFactory`, `EmbeddingFactory` | `backend/src/core/llm/factory.py`, `embedding_factory.py` |
| **配置系统** | `ConfigCache` 单例 + Redis Pub/Sub 热重载 | `backend/src/core/config/` |
| **DI 容器** | Injector 框架 + Repository/Service 模块注册 | `backend/src/config/core/` |
| **监控** | Prometheus 指标端点 `/metrics`，HTTP 耗时、LLM 延迟、缓存命中率 | Prometheus 集成 |
| **Service 层** | `monitoring_service.py`, `alert_service.py`, `config_validation_engine.py`, `config_conflict_detector.py`, `config_health_service.py`, `trace_service.py`, `task_state_service.py`, `task_sse_publisher.py`, `test_run_task_adapter.py`, `export_notification.py` | `backend/src/service/` |
| **SSE 推送** | `SSEPublisher`, `AsyncTaskManager` | `backend/src/api/sse.py` |
| **ML 评分** | 不继承。评估系统（06）已有独立的指标计算体系，无需通用 ML 评分框架 | — |

### 1.2 明确不继承

| 不继承项 | 原因 |
|---------|------|
| WeasyPrint PDF 报告生成 | 核心目标 §〇 明确排除 |
| 儿童发展评估业务逻辑 | 领域特定，rag-platform 不涉及 |
| 原 backend/ 的 RAG 查询流水线 | 由新的管道模型（01-pipeline-model）替代 |

### 1.3 继承后的去业务化

继承的模块中需去业务化的项：

| 模块 | 去业务化操作 |
|------|------------|
| `qwen_scorer.py` | 不继承。rag-platform 评估系统自建指标计算体系，不需要通用 ML 评分器 |
| 提示词管理 | 移除原评估相关的提示词模板，保留提示词管理基础设施（CRUD、版本管理、热重载） |
| 配置模块 | 移除儿童发展相关配置键，保留配置基础设施 |

---

## 2. 租户 Provisioning

### 2.1 创建租户自动化流程

超管在 `/admin/tenants` 点击"创建租户"后，后端自动执行：

```
POST /api/v1/admin/tenants
  { name: "仁和医院", slug: "renhe", admin_user: {...}, quotas: {...} }
        │
        ▼
  1. 插入 tenants 表记录
        │
        ▼
  2. 初始化租户数据空间
        │
        ├── 确保 tenant_id 行级过滤就绪 (共享库模式，一期选定方案)
        │
        ├── 创建存储目录结构:
        │   storage/{slug}/
        │   ├── documents/     # 文档文件
        │   ├── chroma/        # Chroma 向量库
        │   ├── bm25/          # BM25 独立索引
        │   └── exports/       # 导出文件
        │
        ├── 初始化默认角色:
        │   admin (全部权限)
        │   editor (kb:rw, pipeline:rw, eval:rw, search:execute)
        │   viewer (kb:r, pipeline:r, search:execute)
        │
        ├── 创建初始管理员用户
        │
        └── 记录配额限制到 tenant_quotas 表
        │
        ▼
  3. 返回 { tenant_id, admin_user_id, admin_login_url }
```

**约束**：
- 创建过程是同步事务——任一步骤失败则全部回滚
- 租户 slug 全局唯一，创建前校验
- 初始管理员密码为临时密码，首次登录强制修改

### 2.2 资源配额

| 配额项 | 默认值 | 说明 |
|--------|--------|------|
| `max_knowledge_bases` | 10 | 知识库数量上限 |
| `max_documents` | 1,000,000 | 文档总量上限 |
| `max_users` | 100 | 用户数量上限 |
| `max_storage_gb` | 50 | 存储空间上限 (GB) |
| `max_search_qps` | 50 | 搜索 API 全局 QPS 上限 |
| `max_concurrent_eval_runs` | 2 | 并发评估运行上限 |

**超配额行为**：
- 知识库/文档/用户达到上限 → 创建/上传/邀请时返回 429 `QUOTA_EXCEEDED`
- 存储达到上限 → 文档上传时返回 413 `STORAGE_QUOTA_EXCEEDED`
- 搜索 QPS 超过上限 → 返回 429 `RATE_LIMITED`

**配额调整**：超管在租户详情页 → 配额选项卡 → 修改数值 → 立即生效。

### 2.3 停用/归档/删除租户

| 操作 | 行为 |
|------|------|
| **停用** | 禁止该租户所有用户登录（JWT 验证时检查租户状态）；搜索 API 返回 403；数据保留；计入配额 |
| **重新启用** | 恢复登录和 API 访问 |
| **归档** | 禁止登录和 API 访问；数据保留但不计入活跃配额；可随时恢复为 active |
| **删除（软删除）** | `deleted_at` 标记 → 30 天保留期（可恢复）→ 自动生成数据导出快照 → 30 天后定时任务物理清理 MySQL/存储/向量/缓存 → 快照 90 天后清理 |

---

## 3. 部署架构

### 3.1 Docker Compose 一键部署

```yaml
services:
  rag-platform:
    build:
      context: ./rag-platform/backend
      dockerfile: Dockerfile
    ports:
      - "51002:51002"
    resources:
      limits:
        memory: 4GB
        cpus: 2
    depends_on:
      - mysql
      - redis
    environment:
      - DATABASE_URL=mysql+asyncmy://...
      - REDIS_URL=redis://:password@redis:6379/0

  mysql:
    image: mysql:5.7
    volumes:
      - mysql_data:/var/lib/mysql

  redis:
    image: redis:7.0
    command: redis-server --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data:/data

volumes:
  mysql_data:
  redis_data:
```

### 3.2 项目结构

```
rag-platform/
├── backend/                   # 从 backend/ 继承并去业务化
│   ├── src/
│   │   ├── api/               # 统一响应、SSE、异常处理
│   │   ├── config/            # 配置系统
│   │   ├── controller/        # API 控制器
│   │   ├── core/              # 核心业务逻辑
│   │   │   ├── llm/           # LLM 工厂与适配器
│   │   │   ├── tracing/       # 全链路追踪
│   │   │   ├── rag/           # RAG 核心（管道执行引擎）
│   │   │   ├── metadata/      # 文档元数据
│   │   │   ├── pipeline/      # 管道编译与执行
│   │   │   └── config/        # 配置缓存
│   │   ├── middleware/        # 中间件
│   │   ├── models/            # 数据模型
│   │   ├── repository/        # 数据访问层
│   │   ├── schemas/           # Pydantic 实体类
│   │   ├── service/           # 业务服务层
│   │   └── utils/             # 工具函数
│   ├── Dockerfile             # 两阶段构建
│   └── pyproject.toml         # uv 依赖管理
├── frontend/                  # 前端 SPA
│   ├── src/
│   │   ├── app/               # 应用根组件
│   │   ├── api/               # API 客户端
│   │   ├── components/        # 通用组件
│   │   ├── entities/          # 业务实体
│   │   ├── features/          # 业务特性层
│   │   ├── pages/             # 独立页面
│   │   ├── router/            # 路由配置
│   │   └── shared/            # 共享层
│   ├── Dockerfile
│   └── package.json
├── storage/                   # 持久化存储
│   ├── chroma/                # Chroma 向量库
│   ├── bm25/                  # BM25 独立索引
│   └── documents/             # 上传的文档文件
├── docker-compose.yml
└── CLAUDE.md
```

### 3.3 独立运行约束

- `rag-platform/` 必须能独立运行，不依赖 `backend/` 的任何代码或服务
- `backend/` 代码保留在仓库中作为参考，不再维护、不再部署、不再集成
- 所有外部服务（MySQL、Redis）在 docker-compose 中一并启动
- 无需外部基础设施（不依赖 Kafka、RabbitMQ 等）

---

## 4. 非功能需求

### 4.1 性能

| 指标 | 目标 | 测量方式 |
|------|------|---------|
| 搜索 API P95 延迟 | < 3 秒（单域）、< 5 秒（3 域） | Prometheus + Tracing |
| 管道编译耗时 | < 100ms | Tracing |
| 并发搜索 | 50 QPS（单实例） | k6 / Locust 压测 |
| 知识库索引吞吐 | > 100 chunk/秒 | 内部指标 |
| 评估运行（100 条用例） | < 5 分钟 | Tracing |

### 4.2 可靠性

| 指标 | 目标 |
|------|------|
| 搜索可用性 | 99.9%（月度） |
| 节点降级覆盖率 | 所有可降级节点配置降级路径后，单节点失败不影响整体搜索 |
| 数据持久性 | MySQL 主从（一期单机，二期考虑）；向量存储定期备份 |
| 优雅关闭 | SIGTERM 后 30 秒内完成 inflight 请求 + TraceWriter 刷盘 |

### 4.3 安全

| 要求 | 说明 |
|------|------|
| JWT 认证 | 所有 API（除健康检查）强制认证 |
| 租户隔离 | 详见 [04-permission](./04-permission-and-multi-tenancy.md) |
| 敏感信息脱敏 | 密码/API Key 不在日志中输出；PII 脱敏节点可选 |
| HTTPS | 生产环境强制 HTTPS（反向代理层处理） |
| SQL 注入防护 | SQLAlchemy 参数化查询（ORM 层保证） |

### 4.4 可观测性

| 维度 | 工具 | 暴露内容 |
|------|------|---------|
| **指标** | Prometheus (`/metrics`) | HTTP 请求耗时/状态码、LLM 调用延迟/成功率、缓存命中率、管道执行耗时分布、节点降级次数、搜索 QPS、知识库索引状态 |
| **追踪** | Tracing (`core/tracing/`) | 每个请求的全链路 Span：API → 管道 → 域 → 节点，含耗时和成本 |
| **日志** | 结构化 JSON 日志 | 请求日志（含 TRACE_ID）、错误日志（含堆栈）、降级事件日志 |
| **告警** | `alert_service` | 节点降级频率超阈值、搜索延迟 P95 超标、知识库重建失败、LLM 调用失败率超标 |
| **健康检查** | `GET /health` | 服务存活 + MySQL/Redis 连通性 |

---

## 5. 配置管理

### 5.1 配置优先级

```
MySQL 数据库（主） > .env 文件（兜底）
```

### 5.2 配置分类

| 类别 | 存储位置 | 示例 |
|------|---------|------|
| 基础设施 | `.env` only | DATABASE_URL, REDIS_URL, JWT_SECRET |
| 凭证 | `.env` 兜底 + MySQL 覆盖 | API_KEY, EMBEDDING_API_KEY |
| 业务配置 | MySQL（主）+ `.env` 兜底 | LLM 模型选择、指标阈值、并发数 |
| 管道配置 | MySQL | 管道 JSON 配置、节点参数 |
| 提示词 | MySQL | 各节点的 prompt_template |

### 5.3 热重载

- `ConfigCache` 单例 + Redis Pub/Sub 实现
- 修改 MySQL 配置 → 发布 Redis 消息 → 所有实例 `ConfigCache` 刷新
- 无需重启服务
- 提示词变更同理

---

## 6. 数据库

### 6.1 数据库要求

- MySQL 5.7+（兼容现有 DDL）
- 字符集：utf8mb4
- 连接池：SQLAlchemy asyncmy，默认 pool_size=20, max_overflow=40

### 6.2 DDL 管理

- 所有建表语句集中在 `.ai/full_init_script_mysql57.sql`
- **零迁移原则**：直接修改 DDL，不编写 Alembic 迁移脚本
- 新增表追加到 DDL 文件末尾
- 列变更直接修改 CREATE TABLE 语句

### 6.3 数据清理

- 软删除：所有表使用 `deleted_at` 字段标记删除，不物理删除
- 硬删除：快照过期自动清理、重建任务历史 90 天后清理
- 无外键约束：保持与现有系统一致（弱关联设计）

**租户删除的特殊处理**（详见 [04-permission §2.3](./04-permission-and-multi-tenancy.md)）：

| 阶段 | 时限 | 行为 |
|------|------|------|
| 软删除 | 立即 | `tenants.deleted_at` 标记，禁止登录和 API 访问 |
| 数据导出快照 | 软删除时自动生成 | MySQL dump + 向量存储元数据 + 文件列表，存入 `tenant_deletion_snapshots` |
| 保留期 | 30 天 | 可通过 `PUT /admin/tenants/{id}/restore` 恢复 |
| 物理清理 | 30 天后定时任务 | 清理 MySQL 数据、存储文件、向量索引、缓存 |
| 快照过期 | 物理清理后 90 天 | 导出快照自动清理 |

---

## 7. 前端部署

### 7.1 构建与部署

- 构建：`npm run build` → 产出 `frontend/dist/`
- 后端托管：FastAPI 挂载静态文件目录，配置 SPA 回退路由
- SPA 回退：非 API 路径的 404 请求返回 `index.html`
- Docker：`frontend/Dockerfile` 两阶段构建（node 构建 + nginx 托管），或由后端 FastAPI 直接托管（简化部署）

### 7.2 开发环境

- 前端：`npm run dev` → Vite 开发服务器（端口 5173），API 代理到后端 51002
- 后端：`uv run start` → FastAPI 开发服务器（端口 51002）
- 热重载：前端 Vite HMR + 后端 uvicorn --reload

---

## 8. 验收标准

### 租户 Provisioning
- [ ] AC-7.1：超管创建租户后自动初始化 DB 空间、存储目录、默认角色、初始管理员
- [ ] AC-7.2：创建流程任一步骤失败则全部回滚，租户 slug 全局唯一
- [ ] AC-7.3：知识库/文档/用户/存储达到配额上限时返回对应错误码
- [ ] AC-7.4：超管可调整租户配额，立即生效
- [ ] AC-7.5：停用租户后该租户所有用户无法登录，搜索 API 返回 403
- [ ] AC-7.5a：归档租户后不计入活跃配额，可随时恢复
- [ ] AC-7.5b：软删除租户后 30 天保留期内可恢复；物理清理前自动生成数据导出快照

### 部署与运行
- [ ] AC-7.6：`docker compose up` 一键启动完整系统（MySQL + Redis + 后端 + 前端），无额外依赖
- [ ] AC-7.7：rag-platform 不依赖 backend/ 的任何代码或服务
- [ ] AC-7.8：健康检查端点 `GET /health` 返回 MySQL/Redis 连通性状态

### 监控与追踪
- [ ] AC-7.9：Prometheus `/metrics` 端点暴露 HTTP 耗时、LLM 延迟、缓存命中率、搜索 QPS
- [ ] AC-7.10：全链路 Tracing 正确记录请求的管道 → 域 → 节点级 Span，含耗时和成本
- [ ] AC-7.11：配置热重载生效——修改 MySQL 配置后 5 秒内所有实例刷新

### 安全与可靠性
- [ ] AC-7.12：JWT 认证中间件工作正常——未认证请求返回 401（超管和租户用户分别验证）
- [ ] AC-7.13：CORS 配置正确——允许前端域名跨域请求
- [ ] AC-7.14：Docker 资源限制生效（4GB/2CPU）
- [ ] AC-7.15：优雅关闭——SIGTERM 后 inflight 请求处理完毕，TraceWriter 刷盘
- [ ] AC-7.16：确认 qwen_scorer 不在继承清单——评估系统自建指标计算体系（见 ADR-001）
- [ ] AC-7.17：节点降级频率超阈值时触发告警通知
- [ ] AC-7.18：前端 SPA 回退路由正确——刷新非根路径不 404
- [ ] AC-7.19：所有异常通过全局异常处理器统一格式化
- [ ] AC-7.20：日志为结构化 JSON 格式，含 TRACE_ID 关联

---

## 9. 与其他模块的接口

本模块为所有其他模块提供运行基础：

| 提供给 | 能力 |
|--------|------|
| 所有后端模块 | 数据库连接池、Redis、JWT 认证、DI 容器、配置热重载、统一响应格式 |
| 所有前端模块 | API 代理、SPA 路由、静态资源托管 |
| [05-search-api](./05-pipeline-publishing-and-search-api.md) | Tracing Span 记录、Prometheus 指标、SSE 推送、健康检查 |
| [06-rag-evaluation](./06-rag-evaluation.md) | 异步任务管理、SSE 进度推送、配置版本管理 |
