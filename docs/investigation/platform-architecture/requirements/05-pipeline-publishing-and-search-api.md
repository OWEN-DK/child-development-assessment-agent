# 05 — 管道发布与搜索 API

> **定位**：管道配置完成后的对外暴露层——发布为自定义 URL、管理端点生命周期、提供三种搜索方式。调用方无需感知管道内部结构。
> **与核心目标的关系**：实现 [核心目标 §四（发布部分）](./core-objectives.md#42-管道发布配置输出-url) 和 [核心目标 §六](./core-objectives.md#六搜索-api对外统一接口)。

---

## 配置层级

| 层级 | 谁配置 | 存储位置 | 示例 |
|------|--------|---------|------|
| **L3: API 参数** | 调用方 | 请求体 `params` | `top_k`、`temperature`、`filters`（仅白名单内参数允许覆盖） |
| **L2: 发布 URL 配置** | 租户 admin | MySQL 管道发布配置表 | URL 路径、认证要求、QPS 限制、参数白名单、绑定版本 |
| **L1: 租户覆盖** | 租户 admin | MySQL 全局配置表 | 租户级默认 QPS 上限 |
| **L0: 平台默认** | 超管 / 系统内置 | 代码常量 | 请求大小上限 (1MB)、查询文本长度上限 (2000 字符) |

**API 参数白名单机制**：L2 发布时配置 `allowed_params` 列表。调用方传入不在白名单内的参数 → 忽略，不报错。白名单外的参数以 L2 管道配置中的值为准。

---

## 1. 功能清单

### 1.1 管道发布

管道的发布配置在编辑器工具栏的"发布"面板中完成。

| 配置项 | 说明 | 可选值 |
|--------|------|--------|
| **URL 路径** | 自定义路径段，全局唯一 | 如 `/search/medical-consultation`。系统校验全局唯一性（含租户间不冲突） |
| **管道版本** | 绑定哪个管道版本 | 默认使用当前最新版本 |
| **请求方式** | HTTP 方法 | POST（默认）/ GET |
| **认证要求** | 访问此 URL 需要哪种认证 | JWT / API Key / 无认证（不推荐） |
| **速率限制** | 该端点的最大 QPS | 可设任意正整数，0 表示不限 |
| **启用/停用** | 暂时关闭端点而不删除管道 | enabled / disabled |
| **请求参数白名单** | 允许调用方覆盖哪些管道参数 | 如 `["top_k", "filters", "temperature"]` |
| **响应格式** | 返回格式 | 标准 JSON / SSE 流式 / 自定义模板 |

**URL 路径规则**：
- 格式：`/search/{custom-path}`，其中 `{custom-path}` 由用户自定义
- 全局唯一（跨租户唯一——URL 路径相同但 tenant 不同时，通过 JWT tenant_id 区分，技术上可行但推荐全局唯一避免混淆）
- 仅允许字母、数字、连字符、下划线
- 长度限制：4-50 字符

**发布 URL 管理 API**：

| 方法 | 路径 | 描述 |
|------|------|------|
| `PUT` | `/api/v1/pipelines/{id}/publish` | 配置/更新管道的发布 URL |
| `POST` | `/api/v1/pipelines/{id}/unpublish` | 停用管道的发布 URL（管道保留） |
| `GET` | `/api/v1/pipelines/{id}/publish` | 查询管道的发布状态和 URL 配置 |
| `GET` | `/api/v1/published-endpoints` | 列出当前租户所有已发布的端点 |

### 1.2 三种搜索方式

| 方式 | URL 格式 | 适用场景 | 响应模式 |
|------|---------|---------|---------|
| **发布 URL** | `POST /search/{custom-path}` | 生产环境对外暴露 | 同步 JSON |
| **通用端点** | `POST /api/v1/search` | 测试、内部调用、动态切换管道 ID | 同步 JSON |
| **SSE 流式** | `POST /api/v1/search/stream` | 大模型生成答案时实时推送 | SSE 事件流 |

### 1.3 发布 URL 搜索

```
POST /search/medical-consultation
Authorization: Bearer <JWT>
Content-Type: application/json

{
  "query": "高血压合并糖尿病老年患者如何用药",
  "params": {
    "top_k": 20,
    "filters": {"date_range": "2020-2025"}
  }
}
```

**行为**：
1. 根据 URL 路径查找对应的管道 ID 和版本
2. 校验认证（JWT/API Key）
3. 应用速率限制
4. 注入权限上下文（tenant_id、user_id、roles 从 JWT 提取）
5. 调用 PipelineCompiler 执行管道
6. 返回统一响应格式

### 1.4 通用端点搜索

```
POST /api/v1/search
Authorization: Bearer <JWT>
Content-Type: application/json

{
  "pipeline_id": "pipeline_cross_domain_medical",
  "pipeline_version": 3,
  "query": "高血压合并糖尿病老年患者如何用药",
  "params": {
    "max_domains": 5,
    "filters": {"tenant_id": "customer_a"}
  }
}
```

**与发布 URL 的区别**：
- `pipeline_id` 必填（发布 URL 由路径映射管道 ID）
- `pipeline_version` 可选（不传使用最新版本）
- 适用于测试和内部调用场景

### 1.5 SSE 流式搜索

```
POST /api/v1/search/stream
Authorization: Bearer <JWT>
Content-Type: application/json

{
  "pipeline_id": "pipeline_cross_domain_medical",
  "query": "高血压合并糖尿病老年患者如何用药"
}
```

**SSE 事件类型**：

| 事件 | 数据 | 触发时机 |
|------|------|---------|
| `run_started` | `{run_id, pipeline_name, activated_domains: [{name, kb_name}], shortcut_activated, filtered_domain_count}` | 管道开始执行 |
| `domain_started` | `{domain_name, node_count}` | 每个域管道开始 |
| `domain_progress` | `{domain_name, current_node, progress_pct}` | 域管道内节点执行时 |
| `domain_completed` | `{domain_name, candidate_count, duration_ms}` | 每个域管道完成 |
| `fusion_complete` | `{merged_count, dedup_removed, conflict_count}` | 跨域融合/去重/冲突检测完成 |
| `answer_streaming` | `{delta_text}` | 统一答案生成时逐 token 推送 |
| `citation` | `{chunk_id, doc_name, domain, score}` | 答案引用某个源文档时 |
| `run_completed` | `{run_id, total_latency_ms, shortcut_activated}` | 管道执行完成 |
| `run_failed` | `{run_id, error_message, failed_node}` | 管道执行失败 |
| `degradation_event` | `{node_id, node_type, strategy, reason}` | 节点降级触发 |

推送内容与同步搜索结构一致，仅传输方式不同。

**SSE 连接生命周期**：继承公共 SSE 规范（心跳/缓冲/幂等，见 [需求索引](../requirements.md#sse-连接生命周期公共规范)）。搜索 SSE 的差异化配置：

| 差异项 | 搜索 SSE |
|--------|---------|
| **连接超时** | 最长 5 分钟。超时后服务端关闭连接，推送 `event: close` |
| **缓冲容量** | 最近 100 条事件 |
| **断线重连** | **不支持**。搜索 SSE 是短连接（通常 < 30 秒），断线后搜索结果已丢失，调用方应重新发起搜索请求 |
| **事件 ID 格式** | 递增序号 |

---

## 2. 搜索 API 通用特性

### 2.1 认证叠加

三种搜索方式均支持 JWT 和 API Key 两种认证方式。URL 的认证要求与角色权限是**叠加关系**（AND 逻辑）：
- 认证层验证身份（JWT 或 API Key 有效）
- 权限层按角色裁剪结果（双层 Pre-filter）

### 2.2 速率限制

管道发布配置中的速率限制与性能优化节点的速率限制是**两层独立限流**：
- **管道级**（发布 URL 配置）：限制该 URL 的访问频率
- **节点级**（`rate_limiter` 节点）：限制管道内部某个节点或域的执行频率

两层限流独立计算，任一触发即返回限流错误。

**限流响应**：
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

### 2.3 权限过滤

见 [04-permission](./04-permission-and-multi-tenancy.md)。所有搜索方式强制启用双层权限，不可绕过。

### 2.4 请求参数白名单

发布 URL 配置中指定的参数白名单允许调用方覆盖以下管道参数：

- `top_k`：覆盖检索节点的返回数量
- `filters`：注入额外过滤条件（如日期范围、文档类型）
- `temperature`：覆盖答案合成节点的 LLM temperature
- 其他白名单参数

**不在白名单中的参数** → 使用管道配置中的值，调用方传了也忽略（不报错）。

### 2.5 搜索执行追踪

每次搜索执行产生完整追踪数据，写入 Tracing 系统（见 [07-infrastructure](./07-infrastructure-and-deployment.md)）：
- 管道级 Span（总耗时、激活域数、快捷路径是否触发、裁剪域数）
- 每个域管道的 Span（域名称、节点数、耗时）
- 每个节点的 Span（类型、输入摘要、输出摘要、耗时、降级事件）

---

## 3. 请求/响应格式

### 3.1 同步搜索请求

```json
{
  "pipeline_id": "string (通用端点必填，发布URL由路径映射)",
  "pipeline_version": "int|null (不传使用最新版本)",
  "query": "string (必填，1-2000字符)",
  "params": {
    "max_domains": "int (1-10)",
    "top_k": "int",
    "temperature": "float (0-1)",
    "filters": {}
  }
}
```

### 3.2 同步搜索响应

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "run_id": "string",
    "answer": "string",
    "shortcut_activated": false,
    "filtered_domains": "1 个域因权限未激活",
    "domain_results": [
      {
        "domain_id": "string",
        "domain_name": "string",
        "candidates": 15,
        "top_chunks": [
          {
            "chunk_id": "string",
            "doc_name": "string",
            "text": "string (截断到200字)",
            "score": 0.92
          }
        ],
        "contributed_to_answer": true
      }
    ],
    "conflicts": [
      {
        "type": "string",
        "statement_a": "string",
        "source_a": "string",
        "statement_b": "string",
        "source_b": "string",
        "resolution": "string|null"
      }
    ],
    "pipeline_trace": {
      "pipeline_id": "string",
      "pipeline_version": 3,
      "total_latency_ms": 1850,
      "domain_parallel_latency_ms": 450,
      "aggregation_latency_ms": 1400
    },
    "degradation_events": [
      {
        "node_id": "string",
        "node_type": "string",
        "domain_id": "string|null",
        "strategy": "string",
        "reason": "string"
      }
    ]
  }
}
```

### 3.3 错误响应示例

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

### 3.4 搜索结果大小控制

搜索 API 不使用传统分页（offset/limit），而是通过 `top_k` 控制结果数量——这是 RAG 搜索的自然语义（返回最相关的 K 条结果）。

| 控制维度 | 参数 | 默认值 | 上限 | 说明 |
|---------|------|--------|------|------|
| **每域返回 chunk 数** | `top_k`（API 参数或管道节点配置） | 10 | 100 | 控制每个域管道输出的候选 chunk 数 |
| **响应中每域展示 chunk 数** | `response_top_k`（API 参数） | 5 | 20 | 控制响应 `top_chunks` 数组长度（≤ 实际检索的 `top_k`） |
| **域结果数** | `max_domains`（API 参数） | 管道配置 | 10 | 控制响应 `domain_results` 数组长度 |
| **响应体大小上限** | — | — | 2 MB | 超过时截断 `top_chunks.text` 到 100 字，并在响应中标注 `"truncated": true` |

**请求参数扩展**（`params` 字段）：

```json
{
  "params": {
    "top_k": 20,
    "response_top_k": 5,
    "max_domains": 5
  }
}
```

**不可妥协**：
- `response_top_k` ≤ `top_k`，否则忽略 `response_top_k`，使用 `top_k`
- `top_k` 超过管道节点配置上限时，使用节点配置上限
- SSE 流式搜索不支持 `response_top_k`——流式模式下逐 chunk 推送，无截断

## 4. 发布视图 `/pipelines/:id/publish`

发布是管道工作台的第三个视图（见 [02-工作台](./02-pipeline-editor.md)）。从编辑或评估视图点击"发布"即可切换到发布视图。

```
┌─ ← 管道列表  │  综合问诊管道 v3  │  [编辑] [评估] [发布]  ─────────────┐
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ● 已发布  (2026-05-12, v3)                                          │
│                                                                     │
│  URL 路径    /search/[medical-consultation                  ]        │
│              (4-50 字符，字母/数字/连字符/下划线，全局唯一)               │
│                                                                     │
│  绑定版本    [v3 (当前) ▾]                                            │
│  请求方式    [POST ▾]                                                 │
│                                                                     │
│  ── 认证 ──────────────────────────────────────────────────────      │
│  认证要求    [☑ JWT]  [☐ API Key]                                    │
│                                                                     │
│  ── 限流 ──────────────────────────────────────────────────────      │
│  速率限制    [100    ] QPS  (0 = 不限)                                 │
│                                                                     │
│  ── 参数白名单 ────────────────────────────────────────────────      │
│  [☑ top_k]  [☑ temperature]  [☐ filters]  [☐ max_domains]           │
│                                                                     │
│  ── 响应格式 ──────────────────────────────────────────────────      │
│  [☑ 标准 JSON]  [☐ SSE 流式]                                         │
│                                                                     │
│  ── 调用示例 ──────────────────────────────────────────────────      │
│  curl -X POST https://rag.example.com/search/medical-consultation \  │
│    -H "Authorization: Bearer $TOKEN" \                               │
│    -H "Content-Type: application/json" \                             │
│    -d '{"query": "高血压合并糖尿病如何用药"}'                           │
│                                                                     │
│  [保存发布配置] [停用] [取消发布]                                         │
└─────────────────────────────────────────────────────────────────────┘
```

所有配置在页内完成，不弹模态框。发布后调用示例实时更新。

**版本切换行为**：
- "绑定版本"下拉列出该管道的全部版本，当前生效版本高亮标记
- 切换下拉选项**不即时生效**——需点击"保存发布配置"按钮后才更新 `published_endpoints.bound_version`
- 保存前，已发布的 URL 继续使用旧版本服务请求，无中断
- 保存后，所有新请求立即使用新版本。版本切换不影响 URL 路径
- 历史评估运行记录的是运行时的管道版本，即使发布版本切换也不会改变历史记录

已发布端点的全局列表可在管道列表页查看（每张管道卡片显示发布状态），也可通过 API `/api/v1/published-endpoints` 获取。

---

## 5. 验收标准

- [ ] AC-5.1：管道可发布为自定义 URL，发布后外部系统可通过该 URL 执行搜索
- [ ] AC-5.2：URL 路径全局唯一，重复时提示错误
- [ ] AC-5.3：发布 URL 支持 JWT 和 API Key 两种认证方式
- [ ] AC-5.4：停用 URL 后该端点返回 404，管道本身不受影响
- [ ] AC-5.5：三种搜索方式（发布 URL / 通用端点 / SSE 流式）全部正常返回结果
- [ ] AC-5.6：SSE 流式搜索实时推送各阶段事件，答案逐 token 推送
- [ ] AC-5.7：速率限制生效——超过 max_qps 时返回 429
- [ ] AC-5.8：请求参数白名单生效——不在白名单的参数被忽略
- [ ] AC-5.9：搜索认证与角色权限叠加验证——正确认证但无权限的用户看不到受限内容
- [ ] AC-5.10：搜索 Tracing 正确记录全链路 Span（管道级 + 域级 + 节点级）
- [ ] AC-5.11：已发布端点列表正确展示状态、QPS、版本等统计信息
- [ ] AC-5.12：发布 URL 的管道版本可切换，URL 路径不变
- [ ] AC-5.13：查询文本为空时返回 400 并提示
- [ ] AC-5.14：搜索 SSE 断线后不重连，客户端重新发起搜索请求（搜索 SSE 不支持重连，见 SSE 公共规范）
- [ ] AC-5.15：response_top_k 参数生效——响应 top_chunks 数组长度不超过 response_top_k
- [ ] AC-5.16：响应体超过 2MB 时自动截断 top_chunks.text 并标注 truncated=true

---

## 6. 与其他模块的接口

| 被依赖 | 接口 |
|--------|------|
| [01-pipeline-model](./01-pipeline-model-and-engine.md) | 调用 PipelineCompiler 执行管道 |
| [04-permission](./04-permission-and-multi-tenancy.md) | JWT 解析 → 权限上下文注入 |
| [07-infrastructure](./07-infrastructure-and-deployment.md) | Tracing、Prometheus 指标、SSE 推送基础设施 |
