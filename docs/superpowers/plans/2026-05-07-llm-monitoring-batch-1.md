# LLM 监控改造 — 批次 1: 后端核心数据流

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 后端 API 只返回真正的 LLM 调用记录（过滤 node span），保存完整输入输出，使用真实 token 数，修复 trace 聚合和 async bug。

**Architecture:** 在 TraceService 查询层增加 LLM 调用过滤条件（`model_name != 'unknown'`），在 TraceWriter 中去掉截断逻辑直接存完整内容，在 adapter 中从 API 响应提取真实 token，在 context.py 中修复 sync 版本的 async 调用问题。

**Tech Stack:** Python 3.13, SQLAlchemy 2.0 (async), FastAPI, DashScope SDK

---

## Task 1: 监控 API 过滤 Node Span

**Files:**
- Modify: `backend/src/service/trace_service.py`
- Modify: `backend/src/controller/monitoring_controller.py`

**区分逻辑:** Node span 的 `model_name` 为 `'unknown'`（`_write_span` 方法不设置 model），LLM 调用的 `model_name` 为实际模型名（如 `qwen-plus`）。使用 `model_name != 'unknown'` 作为过滤条件。

### Step 1: TraceService.list_llm_call_logs 增加 LLM-only 过滤

在 `list_llm_call_logs` 方法的基础查询中增加过滤条件：

```python
# trace_service.py:132 — 在 query = select(LLMCallLog) 之后
query = query.where(LLMCallLog.model_name != 'unknown')
```

### Step 2: TraceService.get_trace_detail 过滤 spans

在 `get_trace_detail` 方法的 spans 查询中增加过滤：

```python
# trace_service.py:65-67
spans_result = await session.execute(
    select(LLMCallLog).where(
        LLMCallLog.trace_id == trace_id,
        LLMCallLog.model_name != 'unknown',
    )
)
```

### Step 3: Controller 聚合查询增加过滤

在 `list_traces` 端点的两个聚合查询中增加 `model_name != 'unknown'` 条件：

```python
# monitoring_controller.py:170-178 — agg_result 查询
agg_result = await db.execute(
    sa_select(
        LLMCallLog.trace_id,
        sa_func.sum(LLMCallLog.total_tokens).label("tokens"),
        sa_func.sum(LLMCallLog.cost).label("cost"),
    )
    .where(
        LLMCallLog.trace_id.in_(trace_ids),
        LLMCallLog.model_name != 'unknown',
    )
    .group_by(LLMCallLog.trace_id)
)

# monitoring_controller.py:181-185 — model_result 查询
model_result = await db.execute(
    sa_select(LLMCallLog.trace_id, LLMCallLog.model_name)
    .where(
        LLMCallLog.trace_id.in_(trace_ids),
        LLMCallLog.model_name != 'unknown',
    )
    .distinct()
)
```

### Step 4: 同步过滤统计/成本/错误分析接口

`get_cost_analysis`、`get_error_analysis` 也查全表，需同步增加过滤。

### Step 5: 验证

启动后端，触发一次 LLM 调用，检查:
- `GET /monitoring/logs` 不返回 node span
- `GET /monitoring/traces/{id}` 的 spans 只含 LLM 调用
- 统计数据不含 node span 膨胀

---

## Task 2: 启用全量 Prompt/Completion 保存

**Files:**
- Modify: `backend/src/core/tracing/writer.py`
- Modify: `backend/src/core/tracing/truncation.py`

**方案:** 直接在数据库存完整内容，去掉截断。理由: 当前数据量不大，MySQL TEXT 类型足够（最大 64KB），且 `full_prompt_path`/`full_completion_path` 从未被使用。

### Step 1: 去掉 _record_success 中的截断调用

adapter 的 `_record_success` 中调用了 `truncate_messages` 和 `truncate_content`，改为直接传完整内容。

### Step 2: 确认 MySQL 列类型

`prompt_messages` 是 JSON 类型（最大 1GB），`completion_message` 是 Text 类型（最大 64KB）。如果 completion 超过 64KB 的概率很低，直接存即可。

### Step 3: 清理 truncation.py 中未使用的代码

保留 `save_full_content` 函数（后续可能用于文件存储），但移除 writer 中对 `truncate_messages`/`truncate_content` 的调用。

---

## Task 3: 使用模型返回的真实 Token 用量

**Files:**
- Modify: `backend/src/core/llm/adapters/dashscope_multimodal.py`
- Modify: `backend/src/core/llm/adapters/langchain.py`

### Step 1: DashScope adapter — 从 API 响应提取 usage

DashScope API 响应对象有 `usage` 字段：`response.usage.input_tokens`, `response.usage.output_tokens`。在 `_call_sync` 或 `_call_with_timeout` 中提取并返回。

### Step 2: LangChain adapter — 从 response 提取 usage

LangChain 的 `LLMResponse` 有 `usage_metadata` 或 `response_metadata` 字段。在 `chat()` 方法中提取。

### Step 3: 移除 len(content) // 4 估算

在两个 adapter 的 `_record_success` 和 `chat()` 方法中，用真实 token 替代估算。

---

## Task 4: 修复 Trace 聚合字段失效

**Files:**
- Modify: `backend/src/core/tracing/writer.py` — `_flush_batch` 或 `_finalize_trace`

**方案:** 在 `_finalize_trace` 中，查询关联的 LLMCallLog 记录并聚合 tokens/cost/status，更新到 Trace 记录。

---

## Task 5: 修复 trace_context_sync 异步调用 Bug

**Files:**
- Modify: `backend/src/core/tracing/context.py` — `trace_context_sync` 函数

**问题:** `writer.record_trace_start(...)` 是 async，同步调用返回 coroutine 但未 await。

**方案:** 使用 `asyncio.get_event_loop().create_task()` 提交到事件循环。
