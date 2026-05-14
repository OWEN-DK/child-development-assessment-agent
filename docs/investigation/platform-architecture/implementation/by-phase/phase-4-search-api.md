# Phase 4 — 搜索 API 与发布：阶段实施文档

> **阶段**：Phase 4 / 10
> **上层需求**：[05-pipeline-publishing-and-search-api.md](../requirements/05-pipeline-publishing-and-search-api.md)
> **依赖**：Phase 1（权限与多租户）、Phase 3（管道引擎）
> **实施参照**：[by-module/05-search-api.md](../by-module/05-search-api.md)、[implementation-plan-detail.md §四](../implementation-plan-detail.md)
> **相关模型**：published_endpoints 表 DDL 在 Phase 0.3 已创建

---

## 1. 阶段目标

构建管道对外暴露层，实现：

- **三种搜索方式**：发布 URL 搜索（`POST /search/{custom-path}`）、通用端点搜索（`POST /api/v1/search`）、SSE 流式搜索（`POST /api/v1/search/stream`）
- **管道发布管理**：发布/停用 URL、查询发布状态、列出已发布端点
- **动态路由注册**：FastAPI 启动加载全部 enabled 端点 → 运行时动态增删路由，无需重启
- **管道级速率限制**：滑动窗口算法（Redis + 内存降级），返回 429 + 标准限流 headers
- **搜索认证叠加**：JWT 验证 + API Key 双模式，叠加角色权限做双 Pre-filter（AND 逻辑）
- **API 参数白名单**：仅白名单内参数透传到管道，其余忽略不报错
- **响应大小控制**：> 2MB 自动截断，支持 `response_top_k` 控制展示条目数

---

## 2. 任务清单

### 4.1 数据模型

- [ ] 实现 `models/published_endpoint.py`
  - ORM 模型：`PublishedEndpoint`
  - 字段：`id`, `endpoint_id`, `pipeline_id`, `tenant_id`, `url_path`, `bound_version`, `http_method`, `auth_type`, `rate_limit`, `enabled`, `allowed_params` (JSON), `response_format`, `created_at`, `updated_at`
  - 唯一约束：`uk_endpoint_id`、`uk_url_path`（全局唯一，跨租户不可重复）
  - 索引：`idx_pipeline_id`、`idx_tenant_id`、`idx_enabled`、`idx_tenant_enabled`

### 4.2 Schemas

- [ ] 实现 `schemas/search/__init__.py`（统一导出）
- [ ] 实现 `schemas/search/request.py`
  - `SearchParams`：`top_k` (int 1-100), `temperature` (float 0-1), `filters` (dict), `max_domains` (int 1-10), `response_top_k` (int 1-20)
  - `PublishedUrlSearchRequest`：`query` (str 1-2000), `params` (SearchParams)
  - `GenericSearchRequest`：`pipeline_id` (str), `pipeline_version` (int), `query` (str 1-2000), `params` (SearchParams)
  - `StreamSearchRequest`：`pipeline_id` (str), `pipeline_version` (int), `query` (str 1-2000), `params` (SearchParams) — SSE 模式不支持 `response_top_k`

- [ ] 实现 `schemas/search/response.py`
  - `TopChunk`：`chunk_id`, `doc_name`, `text`, `score`
  - `DomainResult`：`domain_id`, `domain_name`, `candidates`, `top_chunks`, `contributed_to_answer`
  - `ConflictInfo`：`type`, `statement_a`, `source_a`, `statement_b`, `source_b`, `resolution`
  - `PipelineTrace`：`pipeline_id`, `pipeline_version`, `total_latency_ms`, `domain_parallel_latency_ms`, `aggregation_latency_ms`
  - `DegradationEvent`：`node_id`, `node_type`, `domain_id`, `strategy` (skip_node/reroute/degrade_cache/abort), `reason`
  - `SearchResponse`：`run_id`, `answer`, `shortcut_activated`, `filtered_domains`, `domain_results`, `conflicts`, `pipeline_trace`, `degradation_events`, `truncated`

- [ ] 实现 `schemas/search/publish.py`
  - `PublishConfig`（输入）：`url_path` (regex `^[a-zA-Z0-9_-]+$` 4-50 字符), `bound_version`, `http_method` (POST/GET), `auth_type` (jwt/api_key/none), `rate_limit` (≥0), `enabled`, `allowed_params` (list[str]), `response_format` (json/sse/custom)
  - `PublishResult`（输出）：含 `endpoint_id`, `full_url`, `created_at`, `updated_at` 等完整字段
  - `PublishStatus`：`published` (bool), 含 `active_version`, `version_behind` 差异标记
  - `EndpointItem`：发布端点列表项，含 `pipeline_name`, `call_count_24h`, `avg_latency_ms_24h`
  - `PaginatedEndpoints`：`total`, `page`, `page_size`, `items`
  - `UnpublishResult`：`pipeline_id`, `url_path`, `unpublished_at`

- [ ] 实现 `schemas/search/auth.py`
  - `AuthContext`：`authenticated`, `user_id`, `tenant_id`, `roles`, `auth_method`

- [ ] 实现 `schemas/search/rate_limit.py`
  - `RateLimitResult`：`allowed`, `remaining`, `reset_after_ms`, `limit_type`

### 4.3 Repository

- [ ] 实现 `repository/search/publish_repo.py`
  - `PublishedEndpointRepository(BaseRepository[PublishedEndpoint])`
  - `get_by_url_path(url_path: str)` → PublishedEndpoint | None
  - `get_by_pipeline_id(pipeline_id: str, tenant_id: str)` → PublishedEndpoint | None
  - `list_enabled()` → list[PublishedEndpoint]（启动时加载全部 enabled 端点，无租户过滤——全局加载）
  - `list_by_tenant(tenant_id, page, page_size, status_filter, search_keyword)` → PaginatedEndpoints
  - `check_url_path_conflict(url_path: str)` → bool（全局唯一校验）
  - 继承 BaseRepository 的 `create`, `update`, `delete` 方法

### 4.4 服务层

- [ ] 实现 `service/search/search_service.py`
  - `SearchService`（门面类）
    - 构造注入：`PipelineCompiler`, `PermissionService`, `RateLimitService`, `TraceService`
    - `sync_search(pipeline_id, query, tenant_id, user_id, roles, pipeline_version, params, allowed_param_whitelist)` → `SearchResponse`
      - 白名单过滤：`allowed_param_whitelist=None` 全部生效（通用端点）；非 None 仅白名单内生效（发布 URL）
      - 权限注入 → `PermissionService.inject_filters()`
      - 编译 + 执行管道 → `PipelineCompiler.execute()`
      - 后处理：`_enforce_response_size_limit()` 截断 > 2MB 响应；`_apply_response_top_k()` 控制展示条目
    - `stream_search(pipeline_id, query, tenant_id, user_id, roles, publish_channel, pipeline_version, params)` → None
      - 通过回调钩子推送 SSE 事件：`run_started`, `domain_started`, `domain_progress`, `domain_completed`, `fusion_complete`, `answer_streaming`, `citation`, `run_completed`, `run_failed`, `degradation_event`
      - 调用 `SSEPublisher.publish_event(channel, event)` 逐事件推送
    - `_filter_params(params, whitelist)` → `dict`：白名单过滤逻辑
    - `_should_truncate_response(response)` → `bool`：检查序列化大小是否 > 2MB
    - `_enforce_response_size_limit(response)` → `SearchResponse`：截断 + `truncated=true`
    - `_apply_response_top_k(response, top_k)` → `SearchResponse`：每个域 `top_chunks[:top_k]`

- [ ] 实现 `service/search/publish_service.py`
  - `PublishService`
    - 构造注入：`PublishedEndpointRepository`, `PipelineRepository`, `DynamicSearchRouter`
    - `publish(pipeline_id, tenant_id, url_path, bound_version, http_method, auth_type, rate_limit, enabled, allowed_params, response_format)` → `PublishResult`
      - 若已存在端点 → 更新；否则新建
      - 校验 URL 路径格式（`_validate_url_path`）
      - 全局唯一性校验（`check_url_path_conflict`）
      - 写入 DB → 调用 `DynamicSearchRouter.register_route()`
    - `unpublish(pipeline_id, tenant_id)` → `UnpublishResult`
      - 设 `enabled=0`（管道数据保留），移除动态路由
      - 幂等：已停用再次调用仍返回成功
    - `get_status(pipeline_id, tenant_id)` → `PublishStatus`
      - 返回 `version_behind` 标记（bound_version 是否落后于 active_version）
    - `list_endpoints(tenant_id, page, page_size, status, search)` → `PaginatedEndpoints`
      - 含 24h 调用统计（`call_count_24h`, `avg_latency_ms_24h`）
    - `update_version(endpoint_id, tenant_id, bound_version)` → `PublishResult`
      - 仅更新 `bound_version` 字段 + 路由重载
    - `_validate_url_path(url_path: str)`：长度 4-50、仅 `[a-zA-Z0-9_-]`、全局唯一
    - `_get_active_version(pipeline_id)` → `int`：查询管道当前活动版本

- [ ] 实现 `service/search/rate_limit_service.py`
  - `RateLimitService`
    - 构造注入：`redis_client` (RedisClient | None)
    - `check_and_consume(endpoint_id, max_qps, tenant_id, user_id)` → `RateLimitResult`
    - `_redis_sliding_window(key, max_qps, window_ms)` → `(allowed, remaining, reset_after_ms)`：基于 Redis Sorted Set
      - `ZREMRANGEBYSCORE` 清理过期 → `ZADD` 添加 → `ZCOUNT` 计数
    - `_memory_sliding_window(endpoint_id, max_qps, window_ms)` → `(allowed, remaining, reset_after_ms)`：基于 `collections.deque`，Redis 不可用时降级
    - `get_stats(endpoint_id)` → `dict`：`current_qps`, `throttled_count_5min`, `max_qps`
  - 算法：滑动窗口日志（Sliding Window Log），窗口大小 = 1 秒
  - Key 格式：`search:rate_limit:{endpoint_id}:{tenant_id}:{user_id}`
  - 429 响应含 headers：`Retry-After`, `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`

- [ ] 实现 `service/search/search_auth_service.py`
  - `SearchAuthService`
    - 构造注入：`JWTService`, `ApiKeyService`
    - `authenticate(request: Request, endpoint: PublishedEndpoint)` → `AuthContext`
      - 根据 `endpoint.auth_type` 分派：`jwt` → `_authenticate_jwt`，`api_key` → `_authenticate_api_key`，`none` → `_no_auth_context`
    - `_authenticate_jwt(request)` → `AuthContext`：解析 `Authorization: Bearer <token>` → JWT claims → user_id/tenant_id/roles
    - `_authenticate_api_key(request)` → `AuthContext`：解析 `Authorization: ApiKey <key>` 或 `X-Api-Key` → 查询关联租户和角色
    - `_no_auth_context(tenant_id)` → `AuthContext`：匿名上下文（roles=[]，不推荐）
  - 认证方式不匹配时抛出 `AuthFailedError`（error_code=`AUTH_TYPE_MISMATCH`）

- [ ] 实现 `service/search/dynamic_search_router.py`
  - `DynamicSearchRoute(APIRoute)`：自定义路由类，封装 handler 逻辑
    - `handle(request)` → `APIResponse`：认证 → 限流 → 权限注入 → 执行搜索 → 格式化
  - `DynamicSearchRouter`：路由管理器
    - 构造注入：`SearchService`, `PublishedEndpointRepository`, `SearchAuthService`, `RateLimitService`
    - 内部维护：`self._router` (APIRouter)、`self._routes: dict[str, str]` (url_path → endpoint_id)
    - `load_all_on_startup()`：查询全部 enabled 端点 → 逐个注册路由（单条失败不影响其他）
    - `register_route(endpoint)`：`self._router.add_api_route(path="/search/{url_path}", ...)` → 写入 `self._routes`
    - `unregister_route(url_path)`：从 `self._routes` 移除 → handler 入口检查路由是否存在（逻辑移除策略）
    - `reload_route(endpoint)`：先 `unregister_route` 再 `register_route`（版本切换用）
    - `list_registered_routes()` → `list[dict]`：当前活跃路由信息
    - `_build_handler(endpoint)` → async callable：闭包构建每个端点独立的 handler
  - 注意：FastAPI/Starlette 不原生支持运行时物理移除 Route 对象，采用"逻辑移除"策略——从 `self._routes` 删除映射，handler 入口检查映射是否仍存在并返回 404

### 4.5 控制器

- [ ] 实现 `controller/search/search_controller.py`
  - `POST /api/v1/search`：通用端点同步搜索
    - 请求体：`GenericSearchRequest`
    - 响应：`APIResponse.success(data=SearchResponse)`
    - 认证：从 JWT 中间件获取 `AuthContext`
    - 调用：`SearchService.sync_search()` → 无白名单过滤（`allowed_param_whitelist=None`）

- [ ] 实现 `controller/search/stream_controller.py`
  - `POST /api/v1/search/stream`：SSE 流式搜索
    - 请求体：`StreamSearchRequest`
    - 生成 `run_id` + SSE 频道 `search:{run_id}`
    - 创建后台任务：`AsyncTaskManager.start_task(search_service.stream_search, ...)`
    - 返回：`StreamingResponse(SSEPublisher.subscribe(channel), media_type="text/event-stream")`
    - 超时：300 秒（5 分钟）
    - SSE 配置：心跳 15 秒、缓冲 100 条、不支持断线重连

- [ ] 实现 `controller/search/publish_controller.py`
  - `PUT /api/v1/pipelines/{id}/publish`：配置/更新发布 URL
  - `POST /api/v1/pipelines/{id}/unpublish`：停用发布 URL
  - `GET /api/v1/pipelines/{id}/publish`：查询发布状态
  - `GET /api/v1/published-endpoints`：列出当前租户已发布端点（分页 + 筛选）

- [ ] 实现 `controller/search/dynamic_search_router.py`（控制器层的 DynamicSearchRouter 模块入口）
  - ⚠️ 实际的 `DynamicSearchRouter` 实现在 `service/search/` 层，控制器层仅做挂载和 startup 事件注册
  - 在 `server.py` 中：`app.include_router(search_router.router, prefix="")` 挂载动态路由
  - 在 `startup` 事件中调用 `search_router.load_all_on_startup()`

---

## 3. 关键实现细节

### 3.1 动态路由

**架构**：

```
FastAPI 主应用
  ├── /search/{custom-path} → DynamicSearchRouter.router (APIRouter)
  │     ├── POST /search/medical-consultation → _handler_for_ep_001
  │     ├── POST /search/legal-due-diligence → _handler_for_ep_002
  │     └── ... (运行时动态增删)
  │
  ├── POST /api/v1/search         → SearchController
  └── POST /api/v1/search/stream  → StreamController
```

**路由注册时机**：

| 时机 | 触发条件 | 操作 |
|------|---------|------|
| **启动时** | `FastAPI startup event` | `load_all_on_startup()` → `SELECT * FROM published_endpoints WHERE enabled=1` → 逐个 `register_route` |
| **发布时** | `PUT /api/v1/pipelines/{id}/publish` | 写入 DB 后 → `register_route(endpoint)`，路由立即生效无需重启 |
| **停用时** | `POST /api/v1/pipelines/{id}/unpublish` | 设 `enabled=0` 后 → `unregister_route(url_path)`，路由立即失效 |
| **版本切换** | `PublishService.update_version()` | 更新 `bound_version` 后 → `reload_route(endpoint)`，新旧配置切换 |

**路由移除实现（逻辑移除）**：

FastAPI 的 `APIRouter.routes` 是启动后不可变列表，不支持运行时物理删除 Route 对象。采用"逻辑移除"策略：

```python
async def unregister_route(self, url_path: str):
    # 从内存路由表删除映射
    if url_path in self._routes:
        del self._routes[url_path]
    # handler 入口检查：if url_path not in self._routes: return 404
```

已注册到 Starlette 路由器中的 Route 对象虽未物理移除，但 handler 内部执行检查后返回 404 `ENDPOINT_NOT_FOUND`，对外行为等价。

**Handler 完整执行流程**：

```
请求 POST /search/medical-consultation
  │
  ├── Step 1: 解析路径 → 查找 self._routes[url_path] → 获取 endpoint_id
  ├── Step 2: 查询 DB → 验证 endpoint 存在 + enabled=1
  ├── Step 3: SearchAuthService.authenticate(request, endpoint) → AuthContext
  ├── Step 4: RateLimitService.check_and_consume(endpoint_id, max_qps, ...)
  │          → 触发限流则返回 429
  ├── Step 5: PermissionService.inject_filters(roles) → 权限上下文
  ├── Step 6: SearchService.sync_search(pipeline_id, query, ..., allowed_param_whitelist)
  ├── Step 7: _enforce_response_size_limit() → 2MB 截断检查
  └── Step 8: APIResponse.success(data=result)
```

### 3.2 SSE 流式搜索

**事件类型全集（12 种）**：

| 事件 | 数据体关键字段 | 触发时机 | 方向 |
|------|-------------|---------|------|
| `heartbeat` | `{type, timestamp}` | 每 15 秒空闲时 | S→C |
| `run_started` | `{run_id, pipeline_name, activated_domains, shortcut_activated, filtered_domain_count}` | 管道开始执行 | S→C |
| `domain_started` | `{domain_name, domain_id, node_count}` | 每个域管道开始 | S→C |
| `domain_progress` | `{domain_name, domain_id, current_node, current_node_type, progress_pct}` | 域管道内节点执行时 | S→C |
| `domain_completed` | `{domain_name, domain_id, candidate_count, duration_ms}` | 每个域管道完成 | S→C |
| `fusion_complete` | `{merged_count, dedup_removed, conflict_count}` | 跨域融合/去重/冲突检测完成 | S→C |
| `answer_streaming` | `{delta_text, sequence}` | 答案逐 token 生成 | S→C |
| `citation` | `{chunk_id, doc_name, domain, domain_id, score}` | 答案引用源文档 | S→C |
| `run_completed` | `{run_id, total_latency_ms, shortcut_activated, answer_length, citation_count}` | 管道执行成功完成 | S→C |
| `run_failed` | `{run_id, error_message, error_code, failed_node, failed_domain}` | 管道执行失败 | S→C |
| `degradation_event` | `{node_id, node_type, domain_id, strategy, reason}` | 节点降级触发 | S→C |
| `close` | `{code, reason}` | 服务端关闭连接 | S→C |

**连接生命周期**：

```
客户端 POST /api/v1/search/stream
  │
  ▼ 200 + text/event-stream
  │
  ├── event: heartbeat (每15秒, id递增)
  ├── event: run_started (id=N)
  ├── event: domain_started / domain_progress / domain_completed (并行推送，顺序不固定)
  ├── event: fusion_complete
  ├── event: answer_streaming + citation (交替推送)
  ├── event: run_completed
  ├── event: close (id=最后)
  │
  ▼ 服务端关闭 TCP 连接
```

**搜索 SSE 差异化配置**（与公共 SSE 规范的差异）：

| 配置项 | 搜索 SSE | 公共 SSE |
|--------|---------|---------|
| 连接超时 | 5 分钟 | 按场景定义 |
| 缓冲容量 | 100 条事件 | 按场景定义 |
| 断线重连 | **不支持** | 按场景定义 |
| 事件 ID | 递增序号 (0, 1, 2, ...) | 递增序号 |
| 完成后行为 | 立即关闭连接 | 按场景定义 |

**心跳机制**：继承公共 SSE 基础设施（`api/sse.py`），`HEARTBEAT_INTERVAL = 15` 秒。

**断线处理**：搜索 SSE 是短连接（通常 < 30 秒），不支持重连。客户端断开 → 服务端检测到 `CancelledError` → 取消后台任务。断线后搜索结果已丢失，调用方应重新发起搜索请求。

**超时处理**：
- 管道执行 > 5 分钟 → 推送 `event: close` (reason=timeout) → 关闭连接
- 中间节点失败 → 推送 `event: run_failed` → `event: close` (reason=error) → 关闭连接

**Redis 不可用时**：`SSEPublisher` 自动降级到内存队列（单实例模式），功能不受影响。

### 3.3 速率限制

**算法**：滑动窗口日志（Sliding Window Log），窗口大小 1 秒。

**两层独立限流**：
| 层级 | 配置位置 | 触发方式 |
|------|---------|---------|
| **管道级** | 发布 URL 配置 `published_endpoints.rate_limit` | 请求到达时 `RateLimitService.check_and_consume()` < 管道执行前 |
| **节点级** | 管道 JSON 中 `rate_limiter` 节点配置 | 管道执行中，节点执行前 `RateLimiterExecutor` |

两层独立计算，任一触发即返回限流错误。

**Redis 模式**（默认）：

```python
# Key: search:rate_limit:{endpoint_id}:{tenant_id}:{user_id}
# 使用 Sorted Set:
#   1. ZREMRANGEBYSCORE key 0 {now - window_ms/1000}  # 清理过期
#   2. ZADD key {now_timestamp} {now_timestamp}        # 添加当前请求
#   3. ZCOUNT key {now - window_ms/1000} {now}         # 计数
#   4. count > max_qps → 拒绝
#   5. EXPIRE key {window_ms/1000 * 2}                  # 自动过期
```

**内存降级模式**（Redis 不可用时）：

```python
# 使用 collections.deque:
#   1. while deque[0] < now - window_ms/1000: popleft  # 清理过期
#   2. deque.append(now)                                 # 添加当前请求
#   3. len(deque) > max_qps → 拒绝
```

**429 响应格式**：

```json
{
  "code": 429,
  "message": "请求过于频繁，请稍后重试",
  "error_code": "RATE_LIMITED",
  "details": {
    "limit_type": "pipeline",
    "max_qps": 100,
    "retry_after_ms": 1000
  }
}
```

**响应 Headers**：
```
Retry-After: 1
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1715686200
```

### 3.4 认证叠加

**双模式认证**：

| 模式 | 凭据来源 | 解析方式 |
|------|---------|---------|
| **JWT** | `Authorization: Bearer <token>` | 解析 JWT claims → `user_id`, `tenant_id`, `roles` |
| **API Key** | `Authorization: ApiKey <key>` 或 `X-Api-Key` | 查 DB 关联 → `user_id`, `tenant_id`, `roles` |

**AND 逻辑叠加**：

```
认证层（验证身份）
  ├── JWT 有效 → user_id, tenant_id, roles
  └── API Key 有效 → user_id, tenant_id, roles
        │
        ▼
权限层（裁剪结果）
  ├── 库级别：裁剪无权限的知识库 → 对应域不激活
  └── 文档级别：向量存储 where/filter 条件注入 ACL
```

**认证方式不匹配处理**：端点要求 `jwt` 但发送 API Key → 401 `AUTH_TYPE_MISMATCH`。

**匿名模式**：`auth_type=none` 返回匿名 `AuthContext` (roles=[])，权限过滤后可能无结果。不推荐生产使用。

### 3.5 参数白名单

**发布 URL 模式**（`allowed_param_whitelist` 非 None）：

```
请求 params = {"top_k": 20, "temperature": 0.5, "dangerous_param": true}
allowed_params = ["top_k", "temperature"]
  →
effective_params = {"top_k": 20, "temperature": 0.5}  // dangerous_param 被忽略
 中
未在白名单的参数 → 使用管道配置中的默认值
不在白名单中但调用方传了 → 忽略，不报错
```

**通用端点模式**（`allowed_param_whitelist=None`）：

所有参数直接生效，无白名单过滤（信任内部调用）。

**白名单允许的参数名**（硬编码枚举）：

```python
ALLOWED_PARAM_NAMES = {"top_k", "temperature", "filters", "max_domains", "response_top_k"}
```

发布配置中 `allowed_params` 只能包含上述集合中的值，其余参数名在后台校验时拒绝。

---

## 4. 测试策略

### 4.1 单元测试

#### RateLimitService 算法测试 (`tests/unit/search/test_rate_limit_service.py`)

| 测试用例 | 测试内容 | 预期结果 |
|---------|---------|---------|
| `test_exact_qps_limit` | 1 秒内连续发送 `max_qps` 次请求 | 前 `max_qps` 次 `allowed=True`，第 `max_qps+1` 次 `allowed=False` |
| `test_sliding_window_reset` | 等待窗口时间后再次发送 | 配额自动重置，`allowed=True` |
| `test_max_qps_zero` | `max_qps=0` | 所有请求 `allowed=True` |
| `test_concurrent_requests` | 100 并发请求 | 通过计数 ≤ `max_qps` |
| `test_redis_unavailable_fallback` | Redis 不可用 | 降级到内存限流，功能正常 |
| `test_different_endpoints_independent` | 两个端点各自限流 | 互不影响 |
| `test_retry_after_calculation` | 被限流后 | `retry_after_ms` > 0 且 ≤ 窗口大小 |

#### SearchAuthService 认证验证测试 (`tests/unit/search/test_search_auth_service.py`)

| 测试用例 | 测试内容 | 预期结果 |
|---------|---------|---------|
| `test_jwt_auth_valid` | 有效 JWT token | 返回 AuthContext，含 user_id/tenant_id/roles |
| `test_jwt_auth_expired` | 过期 JWT token | `AuthFailedError`，error_code=`AUTH_FAILED` |
| `test_jwt_auth_missing` | 无 Authorization header | `AuthFailedError` |
| `test_api_key_valid` | 有效 API Key | 返回 AuthContext |
| `test_api_key_invalid` | 无效 API Key | `AuthFailedError` |
| `test_auth_type_none` | auth_type=none | 返回匿名 AuthContext，roles=[] |
| `test_auth_type_mismatch` | endpoint 要求 api_key 但发送 JWT | `AuthFailedError`，error_code=`AUTH_TYPE_MISMATCH` |

#### PublishService 发布管理测试 (`tests/unit/search/test_publish_service.py`)

| 测试用例 | 测试内容 | 预期结果 |
|---------|---------|---------|
| `test_publish_new_endpoint` | 首次发布管道 | 端点创建成功，动态路由已注册 |
| `test_publish_update_existing` | 更新已发布管道的配置 | 配置更新成功 |
| `test_publish_url_path_conflict` | URL 路径已被占用 | `UrlPathConflictError` (409) |
| `test_publish_invalid_url_path_format` | URL 路径格式不合法（特殊字符） | `InvalidUrlPathError` (400) |
| `test_publish_invalid_url_path_length` | URL < 4 或 > 50 字符 | `InvalidUrlPathError` (400) |
| `test_publish_invalid_version` | 绑定不存在的版本号 | `InvalidBoundVersionError` (400) |
| `test_publish_pipeline_not_found` | 管道不存在 | `PipelineNotFoundError` (404) |
| `test_unpublish_sets_disabled` | 停用端点 | `enabled=0`，路由已移除 |
| `test_unpublish_idempotent` | 重复停用 | 仍返回成功 |
| `test_get_status_published` | 查询已发布状态 | 返回完整配置 + version_behind |
| `test_get_status_not_published` | 查询未发布状态 | `published=false` |
| `test_list_endpoints_pagination` | 分页查询端点列表 | 正确分页，含 24h 统计 |
| `test_update_version` | 切换绑定版本 | `bound_version` 更新，路由重载 |
| `test_url_path_validation_globally_unique` | 租户 A 占用路径后租户 B 尝试 | `UrlPathConflictError` (409) |

#### DynamicSearchRouter 路由管理测试 (`tests/unit/search/test_dynamic_search_router.py`)

| 测试用例 | 测试内容 | 预期结果 |
|---------|---------|---------|
| `test_register_route` | 注册新搜索路由 | `self._routes` 含新映射 |
| `test_register_duplicate_path` | 重复注册同一路径 | 覆盖旧路由 |
| `test_unregister_route` | 移除路由 | `self._routes` 不含该映射 |
| `test_unregister_nonexistent` | 移除不存在的路由 | 无异常 |
| `test_handler_checks_enabled` | 请求已停用端点 | 返回 404 `ENDPOINT_DISABLED` |
| `test_handler_checks_route_exists` | 路由已移除后再请求 | 返回 404 `ENDPOINT_NOT_FOUND` |

### 4.2 集成测试

#### E2E 搜索测试 (`tests/integration/search/test_search_e2e.py`)

| 测试用例 | 测试内容 | 预期结果 |
|---------|---------|---------|
| `test_search_via_published_url` | POST /search/medical-consultation 完整搜索 | 200，含 answer/domain_results/conflicts/pipeline_trace |
| `test_search_via_generic_endpoint` | POST /api/v1/search 完整搜索 | 同上 |
| `test_search_pipeline_not_found` | pipeline_id 不存在 | 404 `PIPELINE_NOT_FOUND` |
| `test_search_empty_query` | query="" | 400 `QUERY_EMPTY` |
| `test_search_query_too_long` | query 超过 2000 字符 | 400 `QUERY_TOO_LONG` |
| `test_search_param_whitelist_enforcement` | allowed_params=["top_k"]，但传 temperature | temperature 被忽略，使用管道默认值 |
| `test_search_param_all_allowed_generic` | 通用端点传任意参数 | 所有参数生效（无白名单过滤） |
| `test_search_shortcut_activated` | 查询只涉及单域 | `shortcut_activated: true` |
| `test_search_permission_domain_filtered` | 用户无某知识库权限 | `filtered_domains` 标注裁剪域数 |
| `test_search_response_truncation` | 响应体超过 2MB | `truncated: true`，chunk.text 截断到 100 字 |
| `test_search_response_top_k` | params.response_top_k=3 | 每个域 top_chunks 数组长度 ≤ 3 |
| `test_search_rate_limit_enforcement` | 超过 QPS 限制 | 429 `RATE_LIMITED` |
| `test_search_rate_limit_retry_after` | 429 响应 | Retry-After header 正确 + 响应体含 retry_after_ms |
| `test_search_tracing_spans` | 搜索执行后查询 Trace | Tracing 含 pipeline/domain/node 三级 Span |
| `test_search_cross_domain_conflicts` | 含矛盾文档的多域搜索 | `conflicts` 数组非空 |

#### SSE 流式搜索测试 (`tests/integration/search/test_search_sse.py`)

| 测试用例 | 测试内容 | 预期结果 |
|---------|---------|---------|
| `test_sse_complete_event_sequence` | 完整 SSE 搜索 | 按序收到 run_started → domain_* → fusion_complete → answer_streaming* → run_completed → close |
| `test_sse_answer_streaming_full_text` | 累积 delta_text | 完整答案 = 累积全部 delta_text |
| `test_sse_citation_events` | 答案含引用 | 收到 citation 事件 |
| `test_sse_heartbeat` | 空闲时心跳 | 15 秒内收到 heartbeat |
| `test_sse_run_failed_event` | 管道执行失败 | 收到 run_failed → close (reason=error) |
| `test_sse_timeout_disconnect` | 执行超过 5 分钟 | 收到 close (reason=timeout) |
| `test_sse_no_reconnect` | 客户端断开 | 服务端不主动重连推送 |
| `test_sse_event_ids_incremental` | 事件 ID 格式 | ID 从 0 开始递增 |

#### 发布管理集成测试 (`tests/integration/search/test_publish_api.py`)

| 测试用例 | 测试内容 | 预期结果 |
|---------|---------|---------|
| `test_publish_then_search` | 发布管道后立即搜索 | 200，搜索成功 |
| `test_unpublish_then_search_404` | 停用后搜索 | 404 `ENDPOINT_DISABLED` |
| `test_publish_version_switch` | 切换版本后搜索 | 使用新版本配置，URL 不变 |
| `test_publish_version_switch_atomic` | 切换版本过程中搜索 | 旧版本持续服务直到保存完成 |
| `test_publish_url_path_validation_special_chars` | URL 含特殊字符 | 400 `INVALID_URL_PATH` |
| `test_publish_url_path_validation_length` | URL < 4 或 > 50 | 400 `INVALID_URL_PATH` |

### 4.3 关键测试场景（≥16）

| # | 场景描述 | 验收标准 | 测试类型 |
|---|---------|---------|---------|
| S1 | 管道发布为自定义 URL 后，外部系统通过该 URL 执行搜索并获取完整答案（含 domain_results/conflicts/pipeline_trace） | AC-5.1 | 集成 |
| S2 | 尝试使用已被占用的 URL 路径发布 → 返回 409 UrlPathConflictError | AC-5.2 | 集成 |
| S3 | 使用有效 JWT token 搜索成功；使用过期 token → 401 AuthFailedError | AC-5.3 | 集成 |
| S4 | 停用 URL 后再次搜索 → 404；管道本身数据仍存在且可编辑 | AC-5.4 | 集成 |
| S5 | 分别通过发布 URL、通用端点、SSE 流式三种方式执行搜索，验证结果一致性（同步 vs 流式仅传输方式不同） | AC-5.5 | 集成 |
| S6 | 订阅 SSE 流，验证事件序列完整：run_started → domain_* → fusion → answer_streaming → run_completed → close | AC-5.6 | 集成 |
| S7 | 设置 max_qps=5，7 次并发请求 → 5 次 200 + 2 次 429 | AC-5.7 | 集成 |
| S8 | 发布 URL allowed_params=["top_k"]，调用方传 temperature=0.9 → 参数被忽略，使用管道配置值 | AC-5.8 | 单元 |
| S9 | 用户有 editor 角色但无"药学科"库权限 → 搜索结果中 filtered_domains 标注药学域被裁剪 | AC-5.9 | 集成 |
| S10 | 搜索完成后查询 Tracing → 验证 pipeline/domain/node 三级 Span 完整 | AC-5.10 | 集成 |
| S11 | 查看已发布端点列表 → 验证状态、QPS、版本、24h 统计正确 | AC-5.11 | 集成 |
| S12 | 发布 URL 版本从 v3 切换到 v5 → URL 路径不变，搜索使用 v5 配置 | AC-5.12 | 集成 |
| S13 | 提交空 query → 400 提示查询文本不能为空 | AC-5.13 | 单元 |
| S14 | SSE 搜索中途客户端断开连接 → 服务端不尝试重连推送（无重连机制），任务取消 | AC-5.14 | 集成 |
| S15 | 设置 response_top_k=3，top_k=10 → 每个域 top_chunks 数组长度为 3 | AC-5.15 | 集成 |
| S16 | 模拟超大搜索结果（> 2MB） → 响应 truncated=true，chunk.text 截断到 100 字 | AC-5.16 | 集成 |

---

## 5. 验收检查点

按 [需求文档 §5 验收标准](../requirements/05-pipeline-publishing-and-search-api.md#5-验收标准) 逐项检查：

- [ ] **AC-5.1**：管道可发布为自定义 URL，发布后外部系统可通过该 URL 执行搜索
  - 验证：`PUT /api/v1/pipelines/{id}/publish` → `POST /search/{url_path}` 返回 200 + SearchResponse
- [ ] **AC-5.2**：URL 路径全局唯一，重复时提示错误
  - 验证：重复发布同一 url_path → 409 `URL_PATH_CONFLICT` + 冲突信息
- [ ] **AC-5.3**：发布 URL 支持 JWT 和 API Key 两种认证方式
  - 验证：分别用 JWT 和 API Key 搜索均成功；用错误方式 → 401 `AUTH_TYPE_MISMATCH`
- [ ] **AC-5.4**：停用 URL 后该端点返回 404，管道本身不受影响
  - 验证：`POST /api/v1/pipelines/{id}/unpublish` → 搜索返回 404 → 管道仍可编辑
- [ ] **AC-5.5**：三种搜索方式（发布 URL / 通用端点 / SSE 流式）全部正常返回结果
  - 验证：三种方式各有至少 1 个测试通过
- [ ] **AC-5.6**：SSE 流式搜索实时推送各阶段事件，答案逐 token 推送
  - 验证：`test_sse_complete_event_sequence` + `test_sse_citation_events` 通过
- [ ] **AC-5.7**：速率限制生效——超过 max_qps 时返回 429
  - 验证：`test_exact_qps_limit`（单元）+ `test_search_rate_limit_enforcement`（集成）通过
- [ ] **AC-5.8**：请求参数白名单生效——不在白名单的参数被忽略
  - 验证：`test_search_param_whitelist_enforcement` 通过
- [ ] **AC-5.9**：搜索认证与角色权限叠加验证——正确认证但无权限的用户看不到受限内容
  - 验证：`test_search_permission_domain_filtered` 通过
- [ ] **AC-5.10**：搜索 Tracing 正确记录全链路 Span（管道级 + 域级 + 节点级）
  - 验证：`test_search_tracing_spans` 通过
- [ ] **AC-5.11**：已发布端点列表正确展示状态、QPS、版本、24h 统计
  - 验证：`test_list_endpoints_pagination` 通过
- [ ] **AC-5.12**：发布 URL 的管道版本可切换，URL 路径不变
  - 验证：`test_publish_version_switch` + `test_publish_version_switch_atomic` 通过
- [ ] **AC-5.13**：查询文本为空时返回 400 并提示
  - 验证：`test_search_empty_query` 通过
- [ ] **AC-5.14**：搜索 SSE 断线后不重连，客户端重新发起搜索
  - 验证：`test_sse_no_reconnect` 通过
- [ ] **AC-5.15**：response_top_k 参数生效——响应 top_chunks 数组长度不超过 response_top_k
  - 验证：`test_search_response_top_k` 通过
- [ ] **AC-5.16**：响应体超过 2MB 时自动截断 top_chunks.text 并标注 truncated=true
  - 验证：`test_search_response_truncation` 通过

---

## 6. 文件清单

| # | 文件路径 | 说明 | 类型 |
|---|---------|------|------|
| 1 | `rag-platform/backend/src/models/published_endpoint.py` | SQLAlchemy ORM 模型 `PublishedEndpoint` | 新建 |
| 2 | `rag-platform/backend/src/schemas/search/__init__.py` | 统一导出 | 新建 |
| 3 | `rag-platform/backend/src/schemas/search/request.py` | SearchParams, PublishedUrlSearchRequest, GenericSearchRequest, StreamSearchRequest | 新建 |
| 4 | `rag-platform/backend/src/schemas/search/response.py` | SearchResponse, DomainResult, TopChunk, ConflictInfo, PipelineTrace, DegradationEvent | 新建 |
| 5 | `rag-platform/backend/src/schemas/search/publish.py` | PublishConfig, PublishResult, PublishStatus, PaginatedEndpoints, UnpublishResult, EndpointItem | 新建 |
| 6 | `rag-platform/backend/src/schemas/search/auth.py` | AuthContext | 新建 |
| 7 | `rag-platform/backend/src/schemas/search/rate_limit.py` | RateLimitResult | 新建 |
| 8 | `rag-platform/backend/src/repository/search/publish_repo.py` | PublishedEndpointRepository | 新建 |
| 9 | `rag-platform/backend/src/service/search/search_service.py` | SearchService（同步 + SSE 流式门面） | 新建 |
| 10 | `rag-platform/backend/src/service/search/publish_service.py` | PublishService（发布/停用/状态/列表） | 新建 |
| 11 | `rag-platform/backend/src/service/search/rate_limit_service.py` | RateLimitService（滑动窗口限流） | 新建 |
| 12 | `rag-platform/backend/src/service/search/search_auth_service.py` | SearchAuthService（JWT + API Key） | 新建 |
| 13 | `rag-platform/backend/src/service/search/dynamic_search_router.py` | DynamicSearchRouter（动态路由管理） | 新建 |
| 14 | `rag-platform/backend/src/controller/search/search_controller.py` | SearchController（通用端点） | 新建 |
| 15 | `rag-platform/backend/src/controller/search/stream_controller.py` | StreamController（SSE 入口） | 新建 |
| 16 | `rag-platform/backend/src/controller/search/publish_controller.py` | PublishController（发布管理 API） | 新建 |
| 17 | `rag-platform/backend/tests/unit/search/test_rate_limit_service.py` | 限流单元测试 | 新建 |
| 18 | `rag-platform/backend/tests/unit/search/test_search_auth_service.py` | 认证单元测试 | 新建 |
| 19 | `rag-platform/backend/tests/unit/search/test_publish_service.py` | 发布管理单元测试 | 新建 |
| 20 | `rag-platform/backend/tests/unit/search/test_dynamic_search_router.py` | 路由管理单元测试 | 新建 |
| 21 | `rag-platform/backend/tests/integration/search/test_search_e2e.py` | E2E 搜索集成测试 | 新建 |
| 22 | `rag-platform/backend/tests/integration/search/test_search_sse.py` | SSE 集成测试 | 新建 |
| 23 | `rag-platform/backend/tests/integration/search/test_publish_api.py` | 发布管理集成测试 | 新建 |

**统计**：新建文件 23 个，改造文件 0 个。

---

## 7. 错误码汇总

| error_code | HTTP 状态码 | message | 触发条件 |
|-----------|------------|---------|---------|
| `ENDPOINT_NOT_FOUND` | 404 | 搜索端点不存在 | URL 路径无匹配的发布端点，或路由已移除 |
| `ENDPOINT_DISABLED` | 404 | 该搜索端点已停用 | 端点 `enabled=0` |
| `AUTH_FAILED` | 401 | 认证失败 | JWT 过期/无效，或 API Key 无效，或凭据错误 |
| `AUTH_TYPE_MISMATCH` | 401 | 认证方式不匹配 | 端点要求 api_key 但发送 JWT（或反之） |
| `RATE_LIMITED` | 429 | 请求过于频繁，请稍后重试 | 超过管道级 QPS 限制 |
| `QUERY_EMPTY` | 400 | 查询文本不能为空 | `query` 为 null/空字符串/仅空白 |
| `QUERY_TOO_LONG` | 400 | 查询文本超过 2000 字符限制 | `len(query) > 2000` |
| `INVALID_PARAMS` | 400 | 请求参数校验失败 | 参数类型/范围不合规 |
| `PIPELINE_NOT_FOUND` | 404 | 管道不存在 | 通用端点 `pipeline_id` 无效 |
| `PIPELINE_CONFIG_INVALID` | 400 | 管道配置无效 | PipelineCompiler 编译失败 |
| `URL_PATH_CONFLICT` | 409 | URL 路径已被占用 | 发布时 `url_path` 全局重复 |
| `INVALID_URL_PATH` | 400 | URL 路径格式不合法 | 含特殊字符、长度越界 |
| `INVALID_BOUND_VERSION` | 400 | 绑定的版本号不存在 | `bound_version` 不是管道的有效版本号 |
| `INTERNAL_ERROR` | 500 | 内部服务错误 | 未捕获异常兜底 |

---

> **下一阶段**：[Phase 5 — 管道编辑器前端](./phase-5-pipeline-editor.md)
> **关联模块实现规范**：[by-module/05-search-api.md](../by-module/05-search-api.md)
