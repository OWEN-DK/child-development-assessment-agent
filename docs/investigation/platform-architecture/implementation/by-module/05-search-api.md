# 05 — 管道发布与搜索 API：实现规范

> **定位**：管道配置完成后的对外暴露层。实现三种搜索方式（发布 URL / 通用端点 / SSE 流式）、管道发布 URL 管理、动态路由注册、管道级速率限制。
> **上层需求**：[05-pipeline-publishing-and-search-api.md](../requirements/05-pipeline-publishing-and-search-api.md)
> **依赖模块**：[01-pipeline-engine](./01-pipeline-engine.md)（PipelineCompiler）、[04-permission](./04-permission.md)（JWT 解析、双层 Pre-filter）、[07-infrastructure](./07-infrastructure.md)（Tracing、Prometheus、SSE 基础设施）

---

## 1. API 契约

所有端点遵循统一响应格式 `{code, message, data}`。成功 `code=0`，错误 `code=4xx/5xx`，业务错误码见 `error_code` 字段。

### 1.1 通用 Header（所有搜索端点）

| Header | 类型 | 必填 | 说明 |
|--------|------|------|------|
| `Authorization` | `string` | 是（JWT）/ 是（API Key） | `Bearer <token>` 或 `ApiKey <key>` |
| `Content-Type` | `string` | 是 | `application/json` |
| `X-Request-ID` | `string` | 否 | 幂等键，用于客户端去重。不传则服务端生成 |

---

### 1.2 POST /search/{custom-path} — 发布 URL 搜索

根据 URL 路径查找管道 → 认证 → 限流 → 权限注入 → 执行 → 返回同步 JSON。

#### 请求体

| 字段 | 类型 | 必填 | 约束 | 说明 |
|------|------|------|------|------|
| `query` | `string` | 是 | 1-2000 字符 | 用户搜索查询文本 |
| `params` | `object` | 否 | — | 管道参数覆盖（仅白名单参数生效） |
| `params.top_k` | `integer` | 否 | 1-100 | 覆盖检索节点的 `top_k` |
| `params.temperature` | `float` | 否 | 0-1 | 覆盖答案合成节点的 `temperature` |
| `params.filters` | `object` | 否 | — | 额外过滤条件（日期范围、文档类型等） |
| `params.max_domains` | `integer` | 否 | 1-10 | 最大激活域数 |
| `params.response_top_k` | `integer` | 否 | 1-20，≤ `top_k` | 响应中每个域的 `top_chunks` 数组长度 |

**请求示例**：

```json
{
  "query": "高血压合并糖尿病老年患者如何用药",
  "params": {
    "top_k": 20,
    "temperature": 0.5,
    "filters": {"date_range": "2020-2025"},
    "response_top_k": 5
  }
}
```

#### 响应体（成功）

| 字段 | 类型 | 说明 |
|------|------|------|
| `code` | `integer` | 0 |
| `message` | `string` | `"success"` |
| `data.run_id` | `string` | 本次运行的唯一 ID |
| `data.answer` | `string` | 合成的统一答案（Markdown） |
| `data.shortcut_activated` | `boolean` | 是否触发单域快捷路径 |
| `data.filtered_domains` | `string|null` | 因权限被裁剪的域数说明（如 `"1 个域因权限未激活"`） |
| `data.domain_results` | `object[]` | 各域检索结果 |
| `data.domain_results[].domain_id` | `string` | 域 ID |
| `data.domain_results[].domain_name` | `string` | 域名称 |
| `data.domain_results[].candidates` | `integer` | 该域候选文档数 |
| `data.domain_results[].top_chunks` | `object[]` | 该域 Top-K 分块 |
| `data.domain_results[].top_chunks[].chunk_id` | `string` | 分块 ID |
| `data.domain_results[].top_chunks[].doc_name` | `string` | 文档名称 |
| `data.domain_results[].top_chunks[].text` | `string` | 分块文本（截断到 200 字；特大响应截断到 100 字） |
| `data.domain_results[].top_chunks[].score` | `float` | 相关性分数 |
| `data.domain_results[].contributed_to_answer` | `boolean` | 该域是否参与了最终答案合成 |
| `data.conflicts` | `object[]` | 跨域冲突检测结果 |
| `data.conflicts[].type` | `string` | 冲突类型（如 `"contradiction"`、`"discrepancy"`） |
| `data.conflicts[].statement_a` | `string` | 源 A 的表述 |
| `data.conflicts[].source_a` | `string` | 源 A 的出处 |
| `data.conflicts[].statement_b` | `string` | 源 B 的表述 |
| `data.conflicts[].source_b` | `string` | 源 B 的出处 |
| `data.conflicts[].resolution` | `string|null` | 冲突解决状态 |
| `data.pipeline_trace` | `object` | 管道执行追踪摘要 |
| `data.pipeline_trace.pipeline_id` | `string` | 管道 ID |
| `data.pipeline_trace.pipeline_version` | `integer` | 管道版本号 |
| `data.pipeline_trace.total_latency_ms` | `integer` | 总耗时（毫秒） |
| `data.pipeline_trace.domain_parallel_latency_ms` | `integer` | 域并行执行耗时 |
| `data.pipeline_trace.aggregation_latency_ms` | `integer` | 聚合层耗时 |
| `data.degradation_events` | `object[]` | 降级事件列表 |
| `data.degradation_events[].node_id` | `string` | 降级节点 ID |
| `data.degradation_events[].node_type` | `string` | 降级节点类型标识 |
| `data.degradation_events[].domain_id` | `string|null` | 所属域 ID（聚合节点为 null） |
| `data.degradation_events[].strategy` | `string` | 降级策略：`skip_node` / `reroute` / `degrade_cache` / `abort` |
| `data.degradation_events[].reason` | `string` | 降级原因 |
| `data.truncated` | `boolean` | 响应体是否因超过 2MB 而被截断 |

**成功响应示例**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "run_id": "run_20260514_a1b2c3d4",
    "answer": "## 用药建议\n\n高血压合并糖尿病...",
    "shortcut_activated": false,
    "filtered_domains": "1 个域因权限未激活",
    "domain_results": [
      {
        "domain_id": "domain_cardio",
        "domain_name": "心血管内科",
        "candidates": 15,
        "top_chunks": [
          {
            "chunk_id": "chunk_001",
            "doc_name": "高血压诊疗指南2024.pdf",
            "text": "对于合并糖尿病的老年高血压患者，建议...",
            "score": 0.92
          }
        ],
        "contributed_to_answer": true
      }
    ],
    "conflicts": [],
    "pipeline_trace": {
      "pipeline_id": "pipeline_cross_domain_medical",
      "pipeline_version": 3,
      "total_latency_ms": 1850,
      "domain_parallel_latency_ms": 450,
      "aggregation_latency_ms": 1400
    },
    "degradation_events": [],
    "truncated": false
  }
}
```

#### 错误响应

| 场景 | HTTP 状态码 | code | error_code | message |
|------|------------|------|------------|---------|
| URL 路径不存在 | 404 | 404 | `ENDPOINT_NOT_FOUND` | 搜索端点不存在 |
| 端点已停用 | 404 | 404 | `ENDPOINT_DISABLED` | 该搜索端点已停用 |
| 认证失败 | 401 | 401 | `AUTH_FAILED` | 认证失败 |
| 速率限制 | 429 | 429 | `RATE_LIMITED` | 请求过于频繁，请稍后重试 |
| 参数校验失败 | 400 | 400 | `INVALID_PARAMS` | 请求参数校验失败 |
| 管道配置无效 | 400 | 400 | `PIPELINE_CONFIG_INVALID` | 管道配置无效 |
| 查询为空 | 400 | 400 | `QUERY_EMPTY` | 查询文本不能为空 |
| 查询过长 | 400 | 400 | `QUERY_TOO_LONG` | 查询文本超过 2000 字符限制 |
| 内部错误 | 500 | 500 | `INTERNAL_ERROR` | 内部服务错误 |

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

```json
{
  "code": 404,
  "message": "搜索端点不存在",
  "error_code": "ENDPOINT_NOT_FOUND"
}
```

```json
{
  "code": 400,
  "message": "管道配置无效",
  "error_code": "PIPELINE_CONFIG_INVALID",
  "details": {
    "errors": [
      {"node_id": "c2", "field": "top_k", "issue": "top_k 必须在 1-100 之间，当前值: 0"}
    ]
  }
}
```

---

### 1.3 POST /api/v1/search — 通用端点搜索

与发布 URL 搜索功能一致，但 `pipeline_id` 由调用方在请求体中显式指定。不含 URL 路径映射、不含发布特有的启停校验。

#### 请求体

| 字段 | 类型 | 必填 | 约束 | 说明 |
|------|------|------|------|------|
| `pipeline_id` | `string` | 是 | — | 管道 ID |
| `pipeline_version` | `integer` | 否 | ≥1 | 管道版本号，不传使用当前活动版本 |
| `query` | `string` | 是 | 1-2000 字符 | 用户搜索查询文本 |
| `params` | `object` | 否 | — | 管道参数覆盖（所有 L3 参数直接生效，无白名单过滤） |
| `params.top_k` | `integer` | 否 | 1-100 | 覆盖检索节点的 `top_k` |
| `params.temperature` | `float` | 否 | 0-1 | 覆盖答案合成节点的 `temperature` |
| `params.filters` | `object` | 否 | — | 额外过滤条件 |
| `params.max_domains` | `integer` | 否 | 1-10 | 最大激活域数 |
| `params.response_top_k` | `integer` | 否 | 1-20 | 响应中每个域的 `top_chunks` 数组长度 |

**请求示例**：

```json
{
  "pipeline_id": "pipeline_cross_domain_medical",
  "pipeline_version": 3,
  "query": "高血压合并糖尿病老年患者如何用药",
  "params": {
    "top_k": 20,
    "max_domains": 5,
    "filters": {"tenant_id": "customer_a"}
  }
}
```

**响应**：与发布 URL 搜索完全一致（见 §1.2 响应体）。

**错误响应**：在发布 URL 搜索错误基础上，增加管道不存在的错误：

```json
{
  "code": 404,
  "message": "管道不存在",
  "error_code": "PIPELINE_NOT_FOUND"
}
```

---

### 1.4 POST /api/v1/search/stream — SSE 流式搜索

同步请求体，响应为 SSE 事件流（`text/event-stream`），按管道执行阶段逐事件推送。不支持 `response_top_k` 参数（流式模式下逐 chunk 推送，无截断）。

#### 请求体

| 字段 | 类型 | 必填 | 约束 | 说明 |
|------|------|------|------|------|
| `pipeline_id` | `string` | 是 | — | 管道 ID |
| `pipeline_version` | `integer` | 否 | ≥1 | 管道版本号，不传使用当前活动版本 |
| `query` | `string` | 是 | 1-2000 字符 | 用户搜索查询文本 |
| `params` | `object` | 否 | — | 管道参数覆盖。SSE 下不支持 `response_top_k` |
| `params.top_k` | `integer` | 否 | 1-100 | 覆盖检索节点的 `top_k` |
| `params.temperature` | `float` | 否 | 0-1 | 覆盖答案合成节点的 `temperature` |
| `params.filters` | `object` | 否 | — | 额外过滤条件 |
| `params.max_domains` | `integer` | 否 | 1-10 | 最大激活域数 |

**请求示例**：

```json
{
  "pipeline_id": "pipeline_cross_domain_medical",
  "query": "高血压合并糖尿病老年患者如何用药"
}
```

**响应**：SSE 事件流，HTTP `Content-Type: text/event-stream`。事件协议详见 §2。

---

### 1.5 发布管理 API

#### 1.5.1 PUT /api/v1/pipelines/{id}/publish — 配置/更新发布 URL

**请求体**：

| 字段 | 类型 | 必填 | 默认值 | 约束 | 说明 |
|------|------|------|--------|------|------|
| `url_path` | `string` | 是 | — | 4-50 字符，字母/数字/连字符/下划线，全局唯一 | 发布 URL 路径段 |
| `bound_version` | `integer` | 否 | 当前活动版本 | ≥1 | 绑定管道版本号 |
| `http_method` | `string` | 否 | `"POST"` | `POST` / `GET` | HTTP 方法 |
| `auth_type` | `string` | 否 | `"jwt"` | `jwt` / `api_key` / `none` | 认证方式 |
| `rate_limit` | `integer` | 否 | 0 | ≥0 | QPS 限制，0=不限 |
| `enabled` | `boolean` | 否 | `true` | — | 启用状态 |
| `allowed_params` | `string[]` | 否 | `[]` | 仅允许 `top_k`, `temperature`, `filters`, `max_domains`, `response_top_k` | API 参数白名单 |
| `response_format` | `string` | 否 | `"json"` | `json` / `sse` / `custom` | 响应格式 |

**请求示例**：

```json
{
  "url_path": "medical-consultation",
  "bound_version": 3,
  "http_method": "POST",
  "auth_type": "jwt",
  "rate_limit": 100,
  "enabled": true,
  "allowed_params": ["top_k", "temperature"],
  "response_format": "json"
}
```

**响应体（成功）**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "pipeline_id": "pipeline_cross_domain_medical",
    "endpoint_id": "ep_20260514_abcdef",
    "url_path": "medical-consultation",
    "full_url": "/search/medical-consultation",
    "bound_version": 3,
    "http_method": "POST",
    "auth_type": "jwt",
    "rate_limit": 100,
    "enabled": true,
    "allowed_params": ["top_k", "temperature"],
    "response_format": "json",
    "created_at": "2026-05-14T10:30:00Z",
    "updated_at": "2026-05-14T10:30:00Z"
  }
}
```

**错误响应**：

```json
{
  "code": 409,
  "message": "URL 路径已被占用",
  "error_code": "URL_PATH_CONFLICT",
  "details": {
    "conflict_path": "medical-consultation",
    "conflict_tenant": "tenant_renhe",
    "hint": "路径 'medical-consultation' 已被其他管道使用，请选择其他路径"
  }
}
```

#### 1.5.2 POST /api/v1/pipelines/{id}/unpublish — 停用发布 URL

无请求体。停用后端点返回 404，管道本身不受影响。

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "pipeline_id": "pipeline_cross_domain_medical",
    "url_path": "medical-consultation",
    "unpublished_at": "2026-05-14T11:00:00Z"
  }
}
```

**幂等性**：对已停用的管道再次调用仍返回成功（不重复停用）。

#### 1.5.3 GET /api/v1/pipelines/{id}/publish — 查询发布状态

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "pipeline_id": "pipeline_cross_domain_medical",
    "published": true,
    "endpoint_id": "ep_20260514_abcdef",
    "url_path": "medical-consultation",
    "full_url": "/search/medical-consultation",
    "bound_version": 3,
    "active_version": 5,
    "version_behind": true,
    "http_method": "POST",
    "auth_type": "jwt",
    "rate_limit": 100,
    "enabled": true,
    "allowed_params": ["top_k", "temperature"],
    "response_format": "json",
    "created_at": "2026-05-14T10:30:00Z",
    "updated_at": "2026-05-14T10:30:00Z"
  }
}
```

**未发布**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "pipeline_id": "pipeline_cross_domain_medical",
    "published": false
  }
}
```

#### 1.5.4 GET /api/v1/published-endpoints — 当前租户已发布端点列表

**查询参数**：

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `page` | `integer` | 否 | 1 | 页码 |
| `page_size` | `integer` | 否 | 20 | 每页条数（最大 100） |
| `status` | `string` | 否 | — | 筛选：`enabled` / `disabled` |
| `search` | `string` | 否 | — | URL 路径或管道名称搜索 |

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "total": 5,
    "page": 1,
    "page_size": 20,
    "items": [
      {
        "endpoint_id": "ep_20260514_abcdef",
        "pipeline_id": "pipeline_cross_domain_medical",
        "pipeline_name": "跨学科综合问诊管道",
        "url_path": "medical-consultation",
        "full_url": "/search/medical-consultation",
        "bound_version": 3,
        "http_method": "POST",
        "auth_type": "jwt",
        "rate_limit": 100,
        "enabled": true,
        "allowed_params": ["top_k", "temperature"],
        "call_count_24h": 1523,
        "avg_latency_ms_24h": 1850,
        "created_at": "2026-05-14T10:30:00Z",
        "updated_at": "2026-05-14T10:30:00Z"
      }
    ]
  }
}
```

---

## 2. SSE 事件协议

### 2.1 公共规范（继承自 requirements.md）

继承全局 SSE 公共规范的以下部分：

| 项目 | 规则 | 实现位置 |
|------|------|---------|
| **心跳** | 服务端每 15 秒发送 `event: heartbeat` | `src/api/sse.py`：`HEARTBEAT_INTERVAL = 15` |
| **幂等** | 每个事件携带 `id` 字段，客户端可据此去重 | 递增序号 |
| **缓冲** | 服务端为每个会话缓冲事件，超出容量旧事件丢弃 | 队列 `maxsize` |
| **基础设施** | `SSEPublisher` + `AsyncTaskManager` | `src/api/sse.py` |

### 2.2 搜索 SSE 差异化配置

| 差异项 | 搜索 SSE | 说明 |
|--------|---------|------|
| **连接超时** | 5 分钟 | 超时后服务端关闭连接，推送 `event: close` |
| **缓冲容量** | 100 条事件 | `MAX_QUEUE_SIZE = 100` |
| **断线重连** | **不支持** | 搜索 SSE 是短连接（通常 < 30 秒），断线后搜索结果已丢失，调用方应重新发起搜索请求 |
| **事件 ID 格式** | 递增序号 | `0`, `1`, `2`, ... |
| **完成后保持** | 立即关闭 | 搜索结束不再保持连接 |

### 2.3 搜索 SSE 事件类型定义

#### 事件总览

| 事件类型 | 方向 | 触发时机 | 数据体 |
|---------|------|---------|--------|
| `heartbeat` | S→C | 每 15 秒 | `{"type":"heartbeat","timestamp":"..."}` |
| `run_started` | S→C | 管道开始执行 | `{run_id, pipeline_name, activated_domains, shortcut_activated, filtered_domain_count}` |
| `domain_started` | S→C | 每个域管道开始 | `{domain_name, node_count}` |
| `domain_progress` | S→C | 域管道内节点执行时 | `{domain_name, current_node, progress_pct}` |
| `domain_completed` | S→C | 每个域管道完成 | `{domain_name, candidate_count, duration_ms}` |
| `fusion_complete` | S→C | 跨域融合/去重/冲突检测完成 | `{merged_count, dedup_removed, conflict_count}` |
| `answer_streaming` | S→C | 统一答案逐 token 生成 | `{delta_text}` |
| `citation` | S→C | 答案引用源文档 | `{chunk_id, doc_name, domain, score}` |
| `run_completed` | S→C | 管道执行成功完成 | `{run_id, total_latency_ms, shortcut_activated}` |
| `run_failed` | S→C | 管道执行失败 | `{run_id, error_message, failed_node}` |
| `degradation_event` | S→C | 节点降级触发 | `{node_id, node_type, strategy, reason}` |
| `close` | S→C | 服务端关闭连接 | `{code, reason}` |

#### 详细数据 Schema

##### 2.3.1 `run_started`

```json
{
  "run_id": "string (本次运行唯一ID)",
  "pipeline_id": "string (管道ID)",
  "pipeline_version": "integer (管道版本号)",
  "pipeline_name": "string (管道名称)",
  "activated_domains": [
    {"name": "心血管内科", "kb_name": "心血管诊疗指南库"}
  ],
  "shortcut_activated": false,
  "filtered_domain_count": 1
}
```

##### 2.3.2 `domain_started`

```json
{
  "domain_name": "string (域名称)",
  "domain_id": "string (域ID)",
  "node_count": 5
}
```

##### 2.3.3 `domain_progress`

```json
{
  "domain_name": "string",
  "domain_id": "string",
  "current_node": "string (当前正在执行的节点名称)",
  "current_node_type": "string (节点类型标识)",
  "progress_pct": 40
}
```

##### 2.3.4 `domain_completed`

```json
{
  "domain_name": "string",
  "domain_id": "string",
  "candidate_count": 15,
  "duration_ms": 450
}
```

##### 2.3.5 `fusion_complete`

```json
{
  "merged_count": 42,
  "dedup_removed": 8,
  "conflict_count": 2
}
```

##### 2.3.6 `answer_streaming`

```json
{
  "delta_text": "string (增量答案文本)",
  "sequence": "integer (token序号)"
}
```

LLM 生成答案时逐 token 推送。前端累积 `delta_text` 字段形成完整答案。`sequence` 用于前端检测乱序（生产环境依赖 HTTP/TCP 顺序递送，几乎不会发生）。

##### 2.3.7 `citation`

```json
{
  "chunk_id": "string",
  "doc_name": "string",
  "domain": "string (域名称)",
  "domain_id": "string",
  "score": 0.92
}
```

推送时机：LLM 生成答案时，每完成一句话涉及对源文档的引用，即推送一条 `citation` 事件。

##### 2.3.8 `run_completed`

```json
{
  "run_id": "string",
  "total_latency_ms": 1850,
  "shortcut_activated": false,
  "answer_length": 450,
  "citation_count": 12
}
```

##### 2.3.9 `run_failed`

```json
{
  "run_id": "string",
  "error_message": "string (人类可读错误信息)",
  "error_code": "string (错误码)",
  "failed_node": "string (失败的节点ID，可为null)",
  "failed_domain": "string (失败的域名称，可为null)"
}
```

##### 2.3.10 `degradation_event`

```json
{
  "node_id": "string",
  "node_type": "string (节点类型标识)",
  "domain_id": "string|null",
  "strategy": "string (skip_node | reroute | degrade_cache | abort)",
  "reason": "string (人类可读降级原因)"
}
```

##### 2.3.11 `close`

```json
{
  "code": 1000,
  "reason": "run_completed"
}
```

`reason` 枚举值：`run_completed`（正常完成）、`timeout`（超时关闭）、`error`（服务端错误关闭）。

##### 2.3.12 `heartbeat`

```json
{
  "type": "heartbeat",
  "timestamp": "2026-05-14T10:30:15Z"
}
```

### 2.4 SSE 连接生命周期

```
客户端发起 POST /api/v1/search/stream
    │
    ▼
服务端返回 200 + text/event-stream
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  event: heartbeat (每 15 秒)                         │
│  id: 0                                              │
│                                                      │
│  event: run_started                                  │
│  id: 1                                              │
│  data: {...}                                        │
│                                                      │
│  event: domain_started (各域并行，可按不固定顺序推送)  │
│  id: 2, 3, ...                                      │
│                                                      │
│  event: domain_progress (节点间穿插)                  │
│  id: 4, 5, ...                                      │
│                                                      │
│  event: domain_completed                             │
│  id: 6, 7, ...                                      │
│                                                      │
│  event: fusion_complete                              │
│  id: ...                                            │
│                                                      │
│  event: answer_streaming (逐token)                   │
│  ...                                                │
│  event: citation (穿插在 answer_streaming 中)         │
│                                                      │
│  event: run_completed                                │
│  id: N                                              │
│                                                      │
│  event: close                                       │
│  id: N+1                                            │
└─────────────────────────────────────────────────────┘
    │
    ▼
服务端关闭 TCP 连接
```

### 2.5 搜索 SSE 连线格式

```
event: run_started
id: 1
data: {"run_id":"run_xyz","pipeline_id":"...","activated_domains":[...]}

event: answer_streaming
id: 25
data: {"delta_text":"高血压","sequence":1}

event: answer_streaming
id: 26
data: {"delta_text":"合并","sequence":2}
```

### 2.6 超时与错误处理

| 场景 | 行为 |
|------|------|
| 管道执行超过 5 分钟 | 服务端发送 `event: close`（reason=timeout），关闭连接 |
| 中间节点失败 | 发送 `event: run_failed` → `event: close`（reason=error）→ 关闭连接 |
| 客户端断开连接 | 服务端检测到连接断开后取消未完成的任务（通过 SSE 流的 `CancelledError` 捕获） |
| Redis 不可用 | SSEPublisher 自动降级到内存队列（单实例模式），功能不受影响 |

---

## 3. 数据库 DDL

### 3.1 `published_endpoints` 表

```sql
-- 管道发布端点表
CREATE TABLE IF NOT EXISTS `published_endpoints` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '自增主键',
    `endpoint_id` VARCHAR(64) NOT NULL COMMENT '端点唯一ID，形如 ep_YYYYMMDD_xxxxx',
    `pipeline_id` VARCHAR(64) NOT NULL COMMENT '关联的管道ID',
    `tenant_id` VARCHAR(64) NOT NULL COMMENT '租户ID',
    `url_path` VARCHAR(64) NOT NULL COMMENT '发布URL路径段，如 medical-consultation',
    `bound_version` INT UNSIGNED NOT NULL COMMENT '绑定的管道版本号',
    `http_method` VARCHAR(10) NOT NULL DEFAULT 'POST' COMMENT 'HTTP方法：POST/GET',
    `auth_type` VARCHAR(20) NOT NULL DEFAULT 'jwt' COMMENT '认证方式：jwt/api_key/none',
    `rate_limit` INT UNSIGNED NOT NULL DEFAULT 0 COMMENT 'QPS限制，0=不限',
    `enabled` TINYINT(1) NOT NULL DEFAULT 1 COMMENT '启用状态：1=启用，0=停用',
    `allowed_params` JSON DEFAULT NULL COMMENT 'API参数白名单，如 ["top_k","temperature"]',
    `response_format` VARCHAR(20) NOT NULL DEFAULT 'json' COMMENT '响应格式：json/sse/custom',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_endpoint_id` (`endpoint_id`),
    UNIQUE KEY `uk_url_path` (`url_path`),
    KEY `idx_pipeline_id` (`pipeline_id`),
    KEY `idx_tenant_id` (`tenant_id`),
    KEY `idx_enabled` (`enabled`),
    KEY `idx_tenant_enabled` (`tenant_id`, `enabled`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='管道发布端点配置表';
```

**设计说明**：
- `url_path` 全局唯一（`uk_url_path`），跨租户不可重复
- `tenant_id` 由 Repository 基类自动注入（`filter(tenant_id=...)` 自动添加）
- `allowed_params` 为 JSON 数组，存储允许调用方覆盖的参数名白名单
- `bound_version` 引用 `pipeline_versions.version_number`（非外键约束，逻辑关联）
- `enabled=0` 时端点返回 404，管道数据保留不删除

### 3.2 版本切换更新

发布版本切换时，仅更新此表 `bound_version` 字段，不修改 `pipeline_versions` 和其他表：

```sql
-- 版本切换（在 Service 层执行，此处仅说明）
UPDATE `published_endpoints`
SET `bound_version` = ?, `updated_at` = NOW()
WHERE `endpoint_id` = ? AND `tenant_id` = ?;
```

---

## 4. 服务层接口

### 4.1 SearchService

```python
# rag-platform/backend/src/service/search/search_service.py

from src.core.pipeline.compiler import PipelineCompiler
from src.service.permission import PermissionService

class SearchService:
    """搜索服务——同步搜索与 SSE 流式搜索的门面。

    职责：
        1. 接收搜索请求（来自发布 URL 或通用端点）
        2. 调用权限服务注入双层 Pre-filter
        3. 调用 PipelineCompiler 执行管道
        4. 格式化同步响应（含截断逻辑）
        5. 对 SSE 流式搜索，通过回调推送到 SSEPublisher
    """

    def __init__(
        self,
        compiler: PipelineCompiler,
        permission_service: PermissionService,
        rate_limit_service: RateLimitService,
        trace_service: TraceService,
    ):
        ...

    async def sync_search(
        self,
        pipeline_id: str,
        query: str,
        tenant_id: str,
        user_id: str,
        roles: list[str],
        pipeline_version: int | None = None,
        params: dict | None = None,
        allowed_param_whitelist: list[str] | None = None,
    ) -> SearchResponse:
        """同步搜索——管道执行完成后返回完整 JSON 响应。

        Args:
            pipeline_id: 管道 ID
            query: 用户查询文本（1-2000 字符）
            tenant_id: 当前租户 ID（从 JWT 解析）
            user_id: 当前用户 ID（从 JWT 解析）
            roles: 当前用户角色列表（从 JWT 解析）
            pipeline_version: 管道版本号，None = 使用活动版本
            params: API 参数覆盖字典（top_k, temperature, filters 等）
            allowed_param_whitelist: 参数白名单，None = 全部允许（通用端点）;
                                     非 None = 仅白名单内参数生效（发布 URL）

        Returns:
            SearchResponse: 完整搜索响应

        Raises:
            PipelineNotFoundError: 管道不存在
            PipelineConfigInvalidError: 管道配置无效
            RateLimitedError: 速率限制
            PermissionDeniedError: 权限不足
            QueryEmptyError: 查询为空
            QueryTooLongError: 查询超过 2000 字符
        """
        ...

    async def stream_search(
        self,
        pipeline_id: str,
        query: str,
        tenant_id: str,
        user_id: str,
        roles: list[str],
        publish_channel: str,
        pipeline_version: int | None = None,
        params: dict | None = None,
    ) -> None:
        """SSE 流式搜索——执行过程中通过 SSEPublisher 推送事件。

        Args:
            pipeline_id: 管道 ID
            query: 用户查询文本
            tenant_id: 当前租户 ID
            user_id: 当前用户 ID
            roles: 当前用户角色列表
            publish_channel: SSE 发布频道名，格式：search:{run_id}
            pipeline_version: 管道版本号
            params: API 参数覆盖字典

        本方法通过回调钩子将管道执行过程事件推送到 SSEPublisher:
            - 域开始/进度/完成 → SSEPublisher.publish_event
            - 答案逐 token → SSEPublisher.publish_event (answer_streaming)
            - 引用 → SSEPublisher.publish_event (citation)
            - 降级事件 → SSEPublisher.publish_event (degradation_event)
            - 完成/失败 → SSEPublisher.publish_event + 关闭信号
        """
        ...

    def _should_truncate_response(self, response: SearchResponse) -> bool:
        """检查响应体是否超过 2MB。"""
        ...

    def _enforce_response_size_limit(self, response: SearchResponse) -> SearchResponse:
        """超过 2MB 时截断 top_chunks.text 到 100 字并标注 truncated=true。"""
        ...
```

### 4.2 PublishService

```python
# rag-platform/backend/src/service/search/publish_service.py

class PublishService:
    """管道发布管理服务。

    职责：
        1. 发布管道为自定义 URL（写入 published_endpoints 表）
        2. 停用发布 URL（enabled=0）
        3. 查询发布状态
        4. 列出当前租户所有已发布端点
        5. 更新发布绑定的管道版本
    """

    def __init__(
        self,
        endpoint_repo: PublishedEndpointRepository,
        pipeline_repo: PipelineRepository,
        dynamic_router: DynamicSearchRouter,
    ):
        ...

    async def publish(
        self,
        pipeline_id: str,
        tenant_id: str,
        url_path: str,
        bound_version: int | None = None,
        http_method: str = "POST",
        auth_type: str = "jwt",
        rate_limit: int = 0,
        enabled: bool = True,
        allowed_params: list[str] | None = None,
        response_format: str = "json",
    ) -> PublishResult:
        """发布或更新管道的发布 URL 配置。

        如果已存在发布配置（endpoint_id），执行更新；
        否则创建新的发布记录并注册动态路由。

        Args:
            pipeline_id: 管道 ID
            tenant_id: 租户 ID
            url_path: 自定义 URL 路径段
            bound_version: 绑定版本号，None = 当前活动版本
            http_method: POST / GET
            auth_type: jwt / api_key / none
            rate_limit: QPS 限制
            enabled: 是否启用
            allowed_params: 参数白名单
            response_format: json / sse / custom

        Returns:
            PublishResult: 发布结果

        Raises:
            PipelineNotFoundError: 管道不存在
            UrlPathConflictError: URL 路径已被其他端点占用
            InvalidUrlPathError: URL 路径格式不合法
            InvalidBoundVersionError: 绑定的版本号不存在
        """
        ...

    async def unpublish(self, pipeline_id: str, tenant_id: str) -> UnpublishResult:
        """停用管道的发布 URL。

        设置 enabled=0，移除动态路由。幂等操作。

        Args:
            pipeline_id: 管道 ID
            tenant_id: 租户 ID

        Returns:
            UnpublishResult: 停用结果
        """
        ...

    async def get_status(self, pipeline_id: str, tenant_id: str) -> PublishStatus:
        """查询管道的发布状态和 URL 配置。

        返回字段含：
            - published (bool): 是否已发布
            - endpoint_id / url_path / full_url / bound_version
            - active_version / version_behind (发布版本是否落后于当前活动版本)
            - 认证、限流、白名单等配置

        Args:
            pipeline_id: 管道 ID
            tenant_id: 租户 ID

        Returns:
            PublishStatus: 发布状态
        """
        ...

    async def list_endpoints(
        self,
        tenant_id: str,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
        search: str | None = None,
    ) -> PaginatedEndpoints:
        """列出当前租户所有已发布端点。

        返回字段含调用统计（24h 调用量、平均延迟）。

        Args:
            tenant_id: 租户 ID
            page: 页码
            page_size: 每页条数
            status: 筛选状态 enabled/disabled
            search: URL 路径或管道名称搜索关键词

        Returns:
            PaginatedEndpoints: 分页端点列表
        """
        ...

    async def update_version(
        self,
        endpoint_id: str,
        tenant_id: str,
        bound_version: int,
    ) -> PublishResult:
        """更新发布 URL 绑定的管道版本号。

        仅更新时间字段，URL 路径不变。版本切换后自动重新注册路由
        （指向新的管道版本 JSON 配置）。

        Args:
            endpoint_id: 端点 ID
            tenant_id: 租户 ID
            bound_version: 新版本号

        Returns:
            PublishResult: 更新结果
        """
        ...

    async def _validate_url_path(self, url_path: str) -> None:
        """校验 URL 路径格式：

        - 长度 4-50 字符
        - 仅允许 [a-zA-Z0-9_-]
        - 不与已存在的 url_path 冲突（无租户限制，全局唯一）
        """
        ...

    async def _get_active_version(self, pipeline_id: str) -> int:
        """获取管道的当前活动版本号。"""
        ...
```

### 4.3 RateLimitService

```python
# rag-platform/backend/src/service/search/rate_limit_service.py

from collections import defaultdict
import time
import asyncio

class RateLimitService:
    """管道级速率限制服务。

    使用滑动窗口算法（Sliding Window Log），基于 Redis 实现分布式限流。
    Redis 不可用时降级为内存限流（单实例有效）。

    限流粒度：按端点 + 用户 + 窗口。
    """

    def __init__(self, redis_client: RedisClient | None = None):
        """初始化。

        Args:
            redis_client: Redis 客户端，None 时降级为内存限流。
        """
        ...

    async def check_and_consume(
        self,
        endpoint_id: str,
        max_qps: int,
        tenant_id: str,
        user_id: str,
    ) -> RateLimitResult:
        """检查并消耗一次请求配额。

        Args:
            endpoint_id: 端点 ID
            max_qps: 最大 QPS，0 = 不限
            tenant_id: 租户 ID
            user_id: 用户 ID

        Returns:
            RateLimitResult:
                - allowed (bool): 是否允许
                - remaining (int): 剩余配额
                - reset_after_ms (int): 配额重置还需的毫秒数
                - limit_type (str): "pipeline"

        算法（滑动窗口）：
            1. 生成 Key: search:rate_limit:{endpoint_id}:{timestamp_window}
            2. INCR key → 当前窗口计数
            3. 设置 key 过期时间 = 窗口大小
            4. 计数 > max_qps → 返回拒绝
        """
        ...

    async def _redis_sliding_window(
        self, key: str, max_qps: int, window_ms: int
    ) -> tuple[bool, int, int]:
        """基于 Redis 排序集合实现的滑动窗口限流。

        使用 Sorted Set 存储每个请求的时间戳，过期清理旧记录。
        """
        ...

    def _memory_sliding_window(
        self, endpoint_id: str, max_qps: int, window_ms: int
    ) -> tuple[bool, int, int]:
        """基于内存的滑动窗口限流（Redis 降级时使用）。

        使用 deque 存储时间戳。
        """
        ...

    def get_stats(self, endpoint_id: str) -> dict:
        """获取端点的限流统计信息。

        Returns:
            {
                "current_qps": 45,
                "throttled_count_5min": 12,
                "max_qps": 100
            }
        """
        ...
```

### 4.4 SearchAuthService

```python
# rag-platform/backend/src/service/search/search_auth_service.py

class SearchAuthService:
    """搜索认证服务——验证发布 URL 的认证要求。

    职责：
        1. 从请求中提取认证凭据（JWT 或 API Key）
        2. 根据端点配置的 auth_type 验证凭据有效性
        3. 从 JWT 解析 user_id、tenant_id、roles
        4. 从 API Key 查找关联的租户和角色
    """

    def __init__(
        self,
        jwt_service: JWTService,
        api_key_service: ApiKeyService,
    ):
        ...

    async def authenticate(
        self,
        request: Request,
        endpoint: PublishedEndpoint,
    ) -> AuthContext:
        """验证搜索请求的认证凭据。

        Args:
            request: FastAPI Request 对象
            endpoint: 发布端点配置

        Returns:
            AuthContext:
                - authenticated (bool)
                - user_id (str)
                - tenant_id (str)
                - roles (list[str])
                - auth_method (str): "jwt" / "api_key" / "none"

        Raises:
            AuthFailedError: 认证失败
        """
        ...

    async def _authenticate_jwt(self, request: Request) -> AuthContext:
        """从 Authorization: Bearer <token> 解析 JWT。
        
        JWT claims → user_id, tenant_id, roles。
        """
        ...

    async def _authenticate_api_key(self, request: Request) -> AuthContext:
        """从 Authorization: ApiKey <key> 或 X-Api-Key header 验证 API Key。
        
        API Key → 查找关联租户和角色 → AuthContext。
        """
        ...

    async def _no_auth_context(self, tenant_id: str) -> AuthContext:
        """auth_type=none 时的匿名上下文。
        
        不推荐：所有请求以匿名角色执行，权限过滤后可能无结果。
        """
        ...
```

### 4.5 DynamicSearchRouter

```python
# rag-platform/backend/src/service/search/dynamic_search_router.py

from fastapi import APIRouter, Request
from fastapi.routing import APIRoute

class DynamicSearchRoute(APIRoute):
    """自定义路由类，支持动态添加/移除。

    封装路由 handler，包含完整的认证→限流→权限注入→编译→执行流程。
    """

    def __init__(self, path: str, endpoint: PublishedEndpoint, search_service: SearchService, ...):
        ...

    async def handle(self, request: Request) -> APIResponse:
        """路由处理函数：

        1. 从 request.path_params 获取 custom_path
        2. 通过 SearchAuthService 验证认证
        3. 通过 RateLimitService 检查限流
        4. 注入权限上下文（user_id, tenant_id, roles）
        5. 调用 SearchService.sync_search 执行
        6. 调用 _format_response 格式化
        """
        ...


class DynamicSearchRouter:
    """动态搜索路由管理器。

    职责：
        1. 系统启动时加载所有 enabled 端点并注册 FastAPI 路由
        2. 发布新端点时动态注册路由
        3. 停用端点时动态移除路由

    与 APIRouter 的关系：
        本类维护一个 APIRouter 实例，通过 APIRouter.add_api_route 动态增删路由。
        主应用在启动时通过 app.include_router(search_router.router) 挂载。
    """

    def __init__(
        self,
        search_service: SearchService,
        endpoint_repo: PublishedEndpointRepository,
        auth_service: SearchAuthService,
        rate_limit_service: RateLimitService,
    ):
        self._router = APIRouter()
        self._search_service = search_service
        self._endpoint_repo = endpoint_repo
        self._auth_service = auth_service
        self._rate_limit_service = rate_limit_service
        self._routes: dict[str, str] = {}  # url_path → route_id 映射

    @property
    def router(self) -> APIRouter:
        """对外暴露的 APIRouter 实例，供主应用挂载。"""
        return self._router

    async def load_all_on_startup(self):
        """启动时从数据库加载所有 enabled 端点并注册路由。

        执行时机：FastAPI 的 startup 事件中调用。
        异常处理：单条路由注册失败不影响其他路由。
        """
        ...

    async def register_route(self, endpoint: PublishedEndpoint):
        """动态注册一条搜索路由。

        POST /search/{url_path} → handler

        Args:
            endpoint: 发布端点配置

        注册检查：
            - endpoint.enabled 为 True
            - url_path 未被其他路由占用
            - 注册后在 self._routes 中记录映射
        """
        ...

    async def unregister_route(self, url_path: str):
        """动态移除一条搜索路由。

        Args:
            url_path: 要移除的 URL 路径段
        """
        ...

    async def reload_route(self, endpoint: PublishedEndpoint):
        """重新加载路由（版本切换时调用）。

        先移除旧路由，再注册新路由（保证新旧管道配置切换）。

        Args:
            endpoint: 更新后的发布端点配置
        """
        ...

    def list_registered_routes(self) -> list[dict]:
        """列出当前所有已注册的搜索路由信息。"""
        ...

    def _build_handler(self, endpoint: PublishedEndpoint):
        """构建路由处理函数闭包。

        为每个端点创建独立的 async handler 函数，捕获 endpoint 配置。
        handler 内部调用 SearchService.sync_search 并格式化响应。
        """
        ...
```

---

## 5. 动态路由实现

### 5.1 总体架构

```
┌─────────────────────────────────────────────────────────┐
│                    FastAPI 主应用                         │
│                                                          │
│  app.include_router(search_router.router, prefix="")     │
│       │                                                  │
│       ▼                                                  │
│  ┌─────────────────────────────────────────────┐        │
│  │     APIRouter (search_router.router)         │        │
│  │                                              │        │
│  │  POST /search/medical-consultation           │        │
│  │       → _handler_for_ep_001(request)         │        │
│  │                                              │        │
│  │  POST /search/legal-due-diligence            │        │
│  │       → _handler_for_ep_002(request)         │        │
│  │                                              │        │
│  │  POST /search/finance-compliance             │        │
│  │       → _handler_for_ep_003(request)         │        │
│  │                                              │        │
│  │  ... (动态增删)                               │        │
│  └─────────────────────────────────────────────┘        │
│                                                          │
│  POST /api/v1/search         → SearchController         │
│  POST /api/v1/search/stream  → SearchStreamController   │
└─────────────────────────────────────────────────────────┘
```

### 5.2 路由注册流程

#### 启动时批量注册

```
FastAPI Startup Event
       │
       ▼
DynamicSearchRouter.load_all_on_startup()
       │
       ▼
SELECT * FROM published_endpoints WHERE enabled = 1
       │
       ▼
for each endpoint:
    ┌─────────────────────────────────────────────┐
    │  1. 构建路由 handler 函数                   │
    │     - 通过闭包捕获 endpoint 对象             │
    │     - handler 内执行认证→限流→权限→搜索      │
    │                                              │
    │  2. self._router.add_api_route(             │
    │       path=f"/search/{endpoint.url_path}",   │
    │       endpoint=handler,                      │
    │       methods=[endpoint.http_method]         │
    │     )                                        │
    │                                              │
    │  3. self._routes[url_path] = route_id       │
    └─────────────────────────────────────────────┘
       │
       ▼
路由注册完成，主应用开始接受请求
```

#### 发布时动态注册

```
POST /api/v1/pipelines/{id}/publish
       │
       ▼
PublishService.publish()
       │
       ▼
写入 published_endpoints 表
       │
       ▼
DynamicSearchRouter.register_route(endpoint)
       │
       ├── self._router.add_api_route(path="/search/{url_path}", ...)
       ├── self._routes[url_path] = route_id
       └── 路由立即生效（无需重启）
```

#### 停用时动态移除

```
POST /api/v1/pipelines/{id}/unpublish
       │
       ▼
PublishService.unpublish()
       │
       ├── 更新 enabled=0
       │
       ▼
DynamicSearchRouter.unregister_route(url_path)
       │
       ├── 从 self._router.routes 中匹配并移除 APIRoute
       ├── del self._routes[url_path]
       └── 路由立即失效
```

### 5.3 路由 Handler 完整执行流程

```python
async def _handler_for_endpoint(request: Request):
    """单个发布 URL 的请求处理闭包。

    通过闭包捕获 endpoint 对象，每个 URL 有独立 handler。
    """
    try:
        # Step 1: 读取并校验请求体
        body = await request.json()
        query = body.get("query")
        if not query or not isinstance(query, str) or not query.strip():
            raise QueryEmptyError()
        if len(query) > 2000:
            raise QueryTooLongError()

        # Step 2: 认证
        auth_ctx = await auth_service.authenticate(request, endpoint)

        # Step 3: 速率限制
        rate_result = await rate_limit_service.check_and_consume(
            endpoint_id=endpoint.endpoint_id,
            max_qps=endpoint.rate_limit,
            tenant_id=auth_ctx.tenant_id,
            user_id=auth_ctx.user_id,
        )
        if not rate_result.allowed:
            raise RateLimitedError(
                limit_type="pipeline",
                max_qps=endpoint.rate_limit,
                retry_after_ms=rate_result.reset_after_ms,
            )

        # Step 4: 注入权限上下文 → 调用搜索
        params = body.get("params") or {}
        result = await search_service.sync_search(
            pipeline_id=endpoint.pipeline_id,
            query=query,
            tenant_id=auth_ctx.tenant_id,
            user_id=auth_ctx.user_id,
            roles=auth_ctx.roles,
            pipeline_version=endpoint.bound_version,
            params=params,
            allowed_param_whitelist=endpoint.allowed_params,
        )

        # Step 5: 格式化响应
        return APIResponse.success(data=result)

    except AppException as e:
        return APIResponse.error(code=e.code, message=e.message, error_code=e.error_code, details=e.details)
    except Exception as e:
        logger.error(f"搜索路由异常 handler={endpoint.url_path}: {e}")
        return APIResponse.error(code=500, message="内部服务错误", error_code="INTERNAL_ERROR")
```

### 5.4 路由注册的技术细节

**FastAPI `add_api_route` 的使用**：

```python
from fastapi import APIRouter

# 方式：为每个端点动态注册
self._router.add_api_route(
    path=f"/search/{endpoint.url_path}",
    endpoint=handler,
    methods=[endpoint.http_method],
    response_model=SearchResponse,  # 同步搜索统一响应模型
    response_model_exclude_none=True,
    summary=f"搜索端点: {endpoint.url_path}",
    tags=["动态搜索路由"],
)
```

**路由移除的实现**：

FastAPI 的 `APIRouter.routes` 是启动后不可变的列表。动态移除路由需要通过以下方式：

```python
async def unregister_route(self, url_path: str):
    """移除路由——重建路由列表。

    FastAPI 不原生支持运行时移除路由。实现策略：
    1. 从 self._routes 字典标记为已移除
    2. 请求到达时，handler 首先检查 self._routes 是否有该路径的活跃记录
    3. 如路径已移除 → 返回 404 ENDPOINT_NOT_FOUND
    """
    if url_path in self._routes:
        # 从活跃路由记录中移除
        del self._routes[url_path]
        logger.info(f"搜索路由已移除: /search/{url_path}")
```

**注意**：FastAPI/Starlette 原生不支持运行时移除已注册的 `Route` 对象。因此动态路由卸载采用"逻辑移除"策略——从内存路由表 `self._routes` 中删除映射，handler 入口检查映射是否仍存在。已注册到 Starlette 路由器中的 Route 对象虽未物理移除，但 handler 内部执行检查后返回 404，对外行为等价。

---

## 6. 数据流

### 6.1 同步搜索数据流（发布 URL）

```
客户端
  │
  ▼ POST /search/medical-consultation
  │    Body: {"query":"高血压...","params":{"top_k":20}}
  │    Header: Authorization: Bearer <JWT>
  │
  ▼
┌──────────────────────────────────────────────────────┐
│ DynamicSearchRoute.handler                          │
│                                                      │
│  1. 解析 request.path_params["custom_path"]          │
│     → "medical-consultation"                        │
│                                                      │
│  2. 从 self._routes 查找端点配置                     │
│     SELECT * FROM published_endpoints               │
│     WHERE url_path = "medical-consultation"         │
│       AND enabled = 1                                │
│     → endpoint = {pipeline_id:"...", auth_type: ...} │
│                                                      │
│  3. SearchAuthService.authenticate(request, endpoint)│
│     - JWT 解析 → user_id, tenant_id, roles          │
│     - 校验 endpoint.auth_type 匹配                  │
│     → AuthContext{user_id, tenant_id, roles}        │
│                                                      │
│  4. RateLimitService.check_and_consume(...)          │
│     - Key: search:rate_limit:{endpoint_id}:{window}  │
│     - INCR + EXPIRE                                  │
│     → allowed=True / False (429)                    │
│                                                      │
│  5. PermissionService.inject_filters(roles)          │
│     - 库级别过滤：裁剪无权限的知识库 → 域              │
│     - 文档级别过滤：向量存储的 where/filter 条件       │
│     → PermissionContext                            │
│                                                      │
│  6. SearchService.sync_search(...)                  │
│     → PipelineCompiler.execute(config, permission)  │
│       ├── 查询分析（域路由）                         │
│       ├── 域分发（并行域管道）                       │
│       │   ├── 域1：查询理解 → 检索 → 安全 → 质量    │
│       │   ├── 域2：查询理解 → 检索 → 安全 → 质量    │
│       │   └── 域3：查询理解 → 检索 → 安全 → 质量    │
│       ├── 跨域融合（加权 RRF）                       │
│       ├── 跨域去重（MinHash）                        │
│       ├── 冲突检测（LLM）                            │
│       └── 统一答案合成（LLM）                        │
│     → SearchResponse                               │
│                                                      │
│  7. _enforce_response_size_limit(response)           │
│     - 检查序列化大小                                 │
│     - > 2MB → 截断 top_chunks.text + truncated=true │
│                                                      │
│  8. 返回 APIResponse.success(data=response)         │
└──────────────────────────────────────────────────────┘
  │
  ▼
200 OK
{
  "code": 0,
  "message": "success",
  "data": {...}
}
```

### 6.2 SSE 流式搜索数据流

```
客户端
  │ POST /api/v1/search/stream
  │ Body: {"pipeline_id":"...", "query":"..."}
  │
  ▼
SearchStreamController.stream_search()
  │
  ├── 生成 run_id = "run_{timestamp}_{random}"
  ├── 创建 SSE 频道: search:{run_id}
  │
  ├── 创建后台任务（不 await，放入 AsyncTaskManager）:
  │     SearchService.stream_search(
  │       pipeline_id, query, tenant_id, ...
  │       publish_channel="search:{run_id}"
  │     )
  │
  └── 返回 StreamingResponse(SSEPublisher.subscribe("search:{run_id}"))
       │
       ▼ (SSE 事件流)
  ┌─────────────────────────────────────────────┐
  │ event: heartbeat (每15秒)                    │
  │                                              │
  │ event: run_started                          │
  │ data: {"run_id":"...","activated_domains":...}│
  │                                              │
  │ event: domain_started                       │
  │ data: {"domain_name":"心血管内科",...}       │
  │                                              │
  │ event: domain_progress (节点间穿插)          │
  │ data: {"domain_name":"心血管内科","progress_pct":40} │
  │                                              │
  │ event: domain_completed                     │
  │ data: {"domain_name":"心血管内科",...}       │
  │                                              │
  │ ... (更多域事件交错推送)                     │
  │                                              │
  │ event: fusion_complete                      │
  │ data: {"merged_count":42,...}               │
  │                                              │
  │ event: answer_streaming (逐token)            │
  │ data: {"delta_text":"高血压","sequence":1}   │
  │ event: answer_streaming                     │
  │ data: {"delta_text":"合并","sequence":2}    │
  │                                              │
  │ event: citation (穿插在 answer_streaming 中) │
  │ data: {"chunk_id":"...","doc_name":"..."}    │
  │                                              │
  │ event: run_completed                        │
  │ data: {"run_id":"...","total_latency_ms":1850}│
  │                                              │
  │ event: close                                │
  │ data: {"code":1000,"reason":"run_completed"} │
  └─────────────────────────────────────────────┘
       │
       ▼
服务端关闭 TCP 连接
```

### 6.3 速率限制执行流

```
请求到达
  │
  ▼
max_qps == 0 ?
  │
  ├── YES → 放行（不限流）
  │
  └── NO
       │
       ▼
生成限流 Key: rate_limit:{endpoint_id}:{current_window_sec}
       │
       ▼
Redis 可用？
  │
  ├── YES → 滑动窗口（Sorted Set）:
  │         1. ZREMRANGEBYSCORE 清理过期记录
  │         2. ZADD 添加当前请求时间戳
  │         3. ZCOUNT 计算窗口内请求数
  │         4. 计数 > max_qps → 429
  │
  └── NO → 内存滑动窗口（deque）:
            1. while deque[0] < now - window: popleft
            2. deque.append(now)
            3. len(deque) > max_qps → 429
       │
       ▼
┌─ 放行 ────────────────────┐   ┌─ 拒绝 (429) ──────────────┐
│ 返回 allowed=True          │   │ 返回 allowed=False         │
│ remaining = max_qps - count│   │ retry_after_ms = 窗口结束 - now│
│ reset_after_ms = 窗口结束-now│  │ limit_type = "pipeline"    │
│ 继续执行搜索               │   │ Retry-After header = 1秒   │
└───────────────────────────┘   └─────────────────────────────┘
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

Response Headers:
```
Retry-After: 1
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1715686200
```

### 6.4 参数白名单过滤流

```
请求到达（发布 URL）
  │
  ▼
提取 body.params = {"top_k": 20, "temperature": 0.5, "dangerous_param": true}
  │
  ▼
端点配置 allowed_params = ["top_k", "temperature"]
  │
  ▼
白名单过滤:
  for key in body.params:
      if key in allowed_params:
          effective_params[key] = body.params[key]
      else:
          pass  # 忽略，不报错
  │
  ▼
effective_params = {"top_k": 20, "temperature": 0.5}
  │
  ▼
注入管道执行: PipelineCompiler 使用 effective_params 覆盖节点配置
```

**通用端点特殊行为**：`allowed_param_whitelist=None` → 所有参数直接生效（无白名单过滤），因为调用方是信任的内部调用。

---

## 7. 测试策略

### 7.1 单元测试

#### 7.1.1 RateLimitService 算法测试

`tests/unit/search/test_rate_limit_service.py`

| 测试用例 | 测试内容 | 预期结果 |
|---------|---------|---------|
| `test_exact_qps_limit` | 在 1 秒内连续发送 `max_qps` 次请求 | 前 `max_qps` 次 `allowed=True`，第 `max_qps+1` 次 `allowed=False` |
| `test_sliding_window_reset` | 等待一个窗口时间后再次发送 | 配额自动重置，`allowed=True` |
| `test_max_qps_zero` | `max_qps=0` | 所有请求 `allowed=True` |
| `test_concurrent_requests` | 100 并发请求 | 通过计数 ≤ `max_qps` |
| `test_redis_unavailable_fallback` | Redis 不可用时 | 降级到内存限流，功能正常 |
| `test_different_endpoints_independent` | 两个端点各自限流 | 互不影响 |
| `test_retry_after_calculation` | 被限流后 | `retry_after_ms` > 0 且 ≤ 窗口大小 |

#### 7.1.2 SearchAuthService 认证验证测试

`tests/unit/search/test_search_auth_service.py`

| 测试用例 | 测试内容 | 预期结果 |
|---------|---------|---------|
| `test_jwt_auth_valid` | 有效 JWT token | 返回 AuthContext，含 user_id/tenant_id/roles |
| `test_jwt_auth_expired` | 过期 JWT token | `AuthFailedError`，error_code=`AUTH_FAILED` |
| `test_jwt_auth_missing` | 无 Authorization header | `AuthFailedError` |
| `test_api_key_valid` | 有效 API Key | 返回 AuthContext |
| `test_api_key_invalid` | 无效 API Key | `AuthFailedError` |
| `test_auth_type_none` | auth_type=none | 返回匿名 AuthContext，roles=[] |
| `test_auth_type_mismatch` | endpoint 要求 api_key 但发送 JWT | `AuthFailedError` |

#### 7.1.3 PublishService 发布管理测试

`tests/unit/search/test_publish_service.py`

| 测试用例 | 测试内容 | 预期结果 |
|---------|---------|---------|
| `test_publish_new_endpoint` | 首次发布管道 | 端点创建成功，动态路由已注册 |
| `test_publish_update_existing` | 更新已发布管道的配置 | 配置更新成功 |
| `test_publish_url_path_conflict` | URL 路径已被占用 | `UrlPathConflictError` |
| `test_publish_invalid_url_path_format` | URL 路径格式不合法 | `InvalidUrlPathError` |
| `test_publish_invalid_version` | 绑定不存在的版本号 | `InvalidBoundVersionError` |
| `test_publish_pipeline_not_found` | 管道不存在 | `PipelineNotFoundError` |
| `test_unpublish_sets_disabled` | 停用端点 | `enabled=0`，路由已移除 |
| `test_unpublish_idempotent` | 重复停用 | 仍返回成功 |
| `test_get_status_published` | 查询已发布状态 | 返回完整配置 + version_behind |
| `test_get_status_not_published` | 查询未发布状态 | `published=false` |
| `test_list_endpoints_pagination` | 分页查询端点列表 | 正确分页，合计 24h 统计 |
| `test_update_version` | 切换绑定版本 | `bound_version` 更新，路由重载 |
| `test_url_path_validation_globally_unique` | 租户 A 占用路径后租户 B 尝试 | `UrlPathConflictError` |

#### 7.1.4 DynamicSearchRouter 路由管理测试

`tests/unit/search/test_dynamic_search_router.py`

| 测试用例 | 测试内容 | 预期结果 |
|---------|---------|---------|
| `test_register_route` | 注册新搜索路由 | `self._routes` 含新映射 |
| `test_register_duplicate_path` | 重复注册同一路径 | 覆盖旧路由 |
| `test_unregister_route` | 移除路由 | `self._routes` 不含该映射 |
| `test_unregister_nonexistent` | 移不存在的路由 | 无异常 |
| `test_handler_checks_enabled` | 请求已停用端点 | 返回 404 `ENDPOINT_DISABLED` |
| `test_handler_checks_route_exists` | 路由已移除后再请求 | 返回 404 `ENDPOINT_NOT_FOUND` |

### 7.2 集成测试

#### 7.2.1 端到端搜索测试

`tests/integration/search/test_search_e2e.py`

| 测试用例 | 测试内容 | 预期结果 |
|---------|---------|---------|
| `test_search_via_published_url` | POST /search/medical-consultation 完整搜索 | 200, 含 answer/domain_results/conflicts/pipeline_trace |
| `test_search_via_generic_endpoint` | POST /api/v1/search 完整搜索 | 同上 |
| `test_search_pipeline_not_found` | pipeline_id 不存在 | 404 `PIPELINE_NOT_FOUND` |
| `test_search_empty_query` | query="" | 400 `QUERY_EMPTY` |
| `test_search_query_too_long` | query 超过 2000 字符 | 400 `QUERY_TOO_LONG` |
| `test_search_param_whitelist_enforcement` | 发布 URL allowed_params=["top_k"] 但传 temperature | temperature 被忽略（使用管道配置值） |
| `test_search_param_all_allowed_generic` | 通用端点传任意参数 | 所有参数生效（无白名单过滤） |
| `test_search_shortcut_activated` | 查询只涉及单域 | `shortcut_activated: true`，跳过 4 个聚合节点 |
| `test_search_permission_domain_filtered` | 用户无某知识库权限 | `filtered_domains` 标注裁剪域数 |
| `test_search_response_truncation` | 响应体超过 2MB | `truncated: true`，chunk.text 截断到 100 字 |
| `test_search_response_top_k` | params.response_top_k=3 | 每个域 top_chunks 数组长度 ≤ 3 |
| `test_search_rate_limit_enforcement` | 超过 QPS 限制 | 429 `RATE_LIMITED` |
| `test_search_rate_limit_retry_after` | 429 响应 | Retry-After header 正确 |
| `test_search_tracing_spans` | 搜索执行后查询 Trace | Tracing 含 pipeline/domain/node 三级 Span |
| `test_search_cross_domain_conflicts` | 含矛盾文档的多域搜索 | `conflicts` 数组非空 |

#### 7.2.2 SSE 流式搜索测试

`tests/integration/search/test_search_sse.py`

| 测试用例 | 测试内容 | 预期结果 |
|---------|---------|---------|
| `test_sse_complete_event_sequence` | 完整 SSE 搜索 | 按序收到 `run_started → domain_* → fusion_complete → answer_streaming* → run_completed → close` |
| `test_sse_answer_streaming_full_text` | 累积 delta_text | 完整答案 = 累积全部 delta_text |
| `test_sse_citation_events` | 答案含引用 | 收到 citation 事件 |
| `test_sse_heartbeat` | 空闲时心跳 | 15 秒内收到 heartbeat |
| `test_sse_run_failed_event` | 管道执行失败 | 收到 `run_failed` → `close`（reason=error） |
| `test_sse_timeout_disconnect` | 执行超过 5 分钟 | 收到 `close`（reason=timeout） |
| `test_sse_no_reconnect` | 客户端断开 | 服务端不主动重连推送 |
| `test_sse_event_ids_incremental` | 事件 ID 格式 | ID 从 0 开始递增 |

#### 7.2.3 发布管理集成测试

`tests/integration/search/test_publish_api.py`

| 测试用例 | 测试内容 | 预期结果 |
|---------|---------|---------|
| `test_publish_then_search` | 发布管道后立即搜索 | 200，搜索成功 |
| `test_unpublish_then_search_404` | 停用后搜索 | 404 `ENDPOINT_DISABLED` |
| `test_publish_version_switch` | 切换版本后搜索 | 使用新版本配置，URL 不变 |
| `test_publish_version_switch_atomic` | 切换版本过程中搜索 | 旧版本持续服务直到保存完成 |
| `test_publish_url_path_validation_special_chars` | URL 含特殊字符 | 400 `INVALID_URL_PATH` |
| `test_publish_url_path_validation_length` | URL < 4 或 > 50 | 400 `INVALID_URL_PATH` |

### 7.3 测试数据与 Fixture

**搜索测试 fixture 基本结构**：

```python
@pytest.fixture
async def published_endpoint(db_session, pipeline_fixture):
    """创建已发布的端点 fixture"""
    endpoint = PublishedEndpoint(
        endpoint_id="ep_test_001",
        pipeline_id=pipeline_fixture.id,
        tenant_id="tenant_test",
        url_path="test-medical",
        bound_version=1,
        http_method="POST",
        auth_type="jwt",
        rate_limit=100,
        enabled=True,
        allowed_params=["top_k", "temperature"],
        response_format="json",
    )
    db_session.add(endpoint)
    await db_session.commit()
    return endpoint

@pytest.fixture
def valid_jwt_token():
    """生成有效 JWT token fixture"""
    return jwt_service.create_token(
        user_id="user_test",
        tenant_id="tenant_test",
        roles=["editor"],
    )

@pytest.fixture
def search_request_body():
    return {"query": "高血压合并糖尿病如何用药", "params": {"top_k": 10}}
```

### 7.4 关键测试场景（≥10）

| # | 场景 | 验收标准关联 | 测试类型 |
|---|------|------------|---------|
| S1 | 管道发布为自定义 URL 后，外部系统通过该 URL 执行搜索并获取完整答案 | AC-5.1 | 集成 |
| S2 | 尝试使用已被占用的 URL 路径发布 → 返回 409 冲突错误 | AC-5.2 | 集成 |
| S3 | 使用有效 JWT token 通过发布 URL 搜索 → 成功；使用过期 token → 401 | AC-5.3 | 集成 |
| S4 | 停用 URL 后再次搜索 → 404；管道本身数据仍存在且可编辑 | AC-5.4 | 集成 |
| S5 | 分别通过发布 URL、通用端点、SSE 流式三种方式执行搜索，验证结果一致性 | AC-5.5 | 集成 |
| S6 | 订阅 SSE 流，验证事件序列完整（run_started → domain_* → fusion → answer → completed） | AC-5.6 | 集成 |
| S7 | 设置 max_qps=5，7 次并发请求 → 5 次 200 + 2 次 429 | AC-5.7 | 集成 |
| S8 | 发布 URL allowed_params=["top_k"]，调用方传 temperature=0.9 → 参数被忽略，使用管道配置中的 temperature | AC-5.8 | 单元 |
| S9 | 用户有 editor 角色但无"药学科"库权限 → 搜索结果中 filtered_domains 标注药学域被裁剪 | AC-5.9 | 集成 |
| S10 | 搜索完成后查询 Tracing → 验证 pipeline/domain/node 三级 Span 完整 | AC-5.10 | 集成 |
| S11 | 查看已发布端点列表 → 验证状态、QPS、版本、24h 统计正确 | AC-5.11 | 集成 |
| S12 | 发布 URL 版本从 v3 切换到 v5 → URL 路径不变，搜索使用 v5 配置 | AC-5.12 | 集成 |
| S13 | 提交空 query → 400 提示查询文本不能为空 | AC-5.13 | 单元 |
| S14 | SSE 搜索中途客户端断开连接 → 服务端不尝试重连推送（无重连机制） | AC-5.14 | 集成 |
| S15 | 设置 response_top_k=3，top_k=10 → 每个域 top_chunks 数组长度为 3 | AC-5.15 | 集成 |
| S16 | 模拟超大搜索结果（> 2MB） → 响应 truncated=true，chunk.text 截断到 100 字 | AC-5.16 | 集成 |

---

## 8. 验收标准映射

将 [需求文档 §5](../requirements/05-pipeline-publishing-and-search-api.md#5-验收标准) 的 AC-5.1 至 AC-5.16 映射到 §7 的测试场景：

| 验收标准 | 测试场景 | 实现关键点 |
|---------|---------|-----------|
| AC-5.1：管道可发布为自定义 URL，外部系统可通过该 URL 搜索 | S1 | `PublishService.publish()` + `DynamicSearchRouter.register_route()` |
| AC-5.2：URL 路径全局唯一，重复时提示错误 | S2 | `PublishService._validate_url_path()` 中 `uk_url_path` 唯一约束 + 跨租户检查 |
| AC-5.3：支持 JWT 和 API Key 两种认证方式 | S3 | `SearchAuthService.authenticate()` 分派到 `_authenticate_jwt` / `_authenticate_api_key` |
| AC-5.4：停用 URL 后返回 404，管道不受影响 | S4 | `PublishService.unpublish()` 仅设 `enabled=0`，不删管道 |
| AC-5.5：三种搜索方式全部正常返回结果 | S5 | `SearchService.sync_search()` + `SearchService.stream_search()` + 发布 URL handler |
| AC-5.6：SSE 流式实时推送各阶段事件，答案逐 token 推送 | S6 | `SearchService.stream_search()` 通过回调钩子调用 `SSEPublisher.publish_event()` |
| AC-5.7：速率限制生效，超过 QPS 返回 429 | S7 | `RateLimitService.check_and_consume()` 滑动窗口算法 |
| AC-5.8：参数白名单生效，不在名单的参数被忽略 | S8 | `SearchService.sync_search()` 中 `allowed_param_whitelist` 过滤逻辑 |
| AC-5.9：认证与权限叠加，无权限用户看不到受限内容 | S9 | `PermissionService.inject_filters()` → 库级别裁剪 + 文档级别 Pre-filter |
| AC-5.10：Tracing 正确记录全链路 Span | S10 | `PipelineCompiler` 执行时注入 `TraceContext` + `TraceWriter` |
| AC-5.11：已发布端点列表正确展示状态/版本/统计 | S11 | `PublishService.list_endpoints()` + Prometheus 指标的 24h 聚合 |
| AC-5.12：发布 URL 管道版本可切换，URL 路径不变 | S12 | `PublishService.update_version()` → `DynamicSearchRouter.reload_route()` |
| AC-5.13：query 为空返回 400 | S13 | Handler 入口处 `if not query.strip()` |
| AC-5.14：搜索 SSE 断线后不重连，客户端重新发起 | S14 | 搜索 SSE `close` 事件后服务端关闭 TCP；无 `Last-Event-ID` 重连逻辑 |
| AC-5.15：response_top_k 参数生效 | S15 | `SearchService.sync_search()` 后处理：`domain.top_chunks = domain.top_chunks[:response_top_k]` |
| AC-5.16：响应体超过 2MB 自动截断并标注 truncated | S16 | `SearchService._enforce_response_size_limit()` |

---

## 附录 A：错误码汇总

| error_code | HTTP 状态码 | message | 触发条件 |
|-----------|------------|---------|---------|
| `ENDPOINT_NOT_FOUND` | 404 | 搜索端点不存在 | URL 路径无匹配的发布端点 |
| `ENDPOINT_DISABLED` | 404 | 该搜索端点已停用 | 端点 `enabled=0` |
| `AUTH_FAILED` | 401 | 认证失败 | JWT 过期/无效，API Key 无效，或其他认证凭据错误 |
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

## 附录 B：Pydantic 实体类位置

按强制规范，所有 `class Xxx(BaseModel)` 必须在 `schemas/` 目录下：

```
schemas/
├── search/
│   ├── __init__.py            # 统一导出
│   ├── request.py             # SearchRequest, StreamSearchRequest
│   ├── response.py            # SearchResponse, DomainResult, TopChunk, Conflict, PipelineTrace, DegradationEvent
│   ├── publish.py             # PublishRequest, PublishResult, PublishStatus, PaginatedEndpoints, UnpublishResult, EndpointItem
│   ├── auth.py                # AuthContext
│   └── rate_limit.py          # RateLimitResult
```

**实体类摘要**（仅列出，不完整定义）：

```python
# schemas/search/request.py

class SearchParams(BaseModel):
    """搜索参数覆盖（仅白名单生效）"""
    top_k: int | None = Field(None, ge=1, le=100)
    temperature: float | None = Field(None, ge=0, le=1)
    filters: dict | None = None
    max_domains: int | None = Field(None, ge=1, le=10)
    response_top_k: int | None = Field(None, ge=1, le=20)

class PublishedUrlSearchRequest(BaseModel):
    """发布 URL 搜索请求（不含 pipeline_id）"""
    query: str = Field(..., min_length=1, max_length=2000)
    params: SearchParams | None = None

class GenericSearchRequest(BaseModel):
    """通用端点搜索请求"""
    pipeline_id: str = Field(...)
    pipeline_version: int | None = Field(None, ge=1)
    query: str = Field(..., min_length=1, max_length=2000)
    params: SearchParams | None = None

class StreamSearchRequest(BaseModel):
    """SSE 流式搜索请求"""
    pipeline_id: str = Field(...)
    pipeline_version: int | None = Field(None, ge=1)
    query: str = Field(..., min_length=1, max_length=2000)
    params: SearchParams | None = None
```

---

## 附录 C：文件清单

| 文件 | 说明 |
|------|------|
| `src/service/search/search_service.py` | `SearchService`——同步搜索 + SSE 流式搜索门面 |
| `src/service/search/publish_service.py` | `PublishService`——发布/停用/状态/端点列表管理 |
| `src/service/search/rate_limit_service.py` | `RateLimitService`——管道级滑动窗口限流 |
| `src/service/search/search_auth_service.py` | `SearchAuthService`——JWT/API Key 认证校验 |
| `src/service/search/dynamic_search_router.py` | `DynamicSearchRouter`——动态路由注册/移除 |
| `src/controller/search_controller.py` | `SearchController`——通用端点 + SSE 入口 |
| `src/repository/published_endpoint_repository.py` | `PublishedEndpointRepository`——发布端点数据访问 |
| `src/schemas/search/request.py` | 搜索请求实体类 |
| `src/schemas/search/response.py` | 搜索响应实体类 |
| `src/schemas/search/publish.py` | 发布管理实体类 |
| `src/schemas/search/auth.py` | 认证上下文实体类 |
| `src/schemas/search/rate_limit.py` | 限流结果实体类 |
| `tests/unit/search/` | 单元测试目录 |
| `tests/integration/search/` | 集成测试目录 |

---

> *本文档为模块 5（管道发布与搜索 API）的完整实现规范。其他模块见 [by-module/](./) 目录。*
