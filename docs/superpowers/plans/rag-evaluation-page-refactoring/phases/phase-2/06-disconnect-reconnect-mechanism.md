# 06 - 断线重连机制 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 06 - 断线重连机制

**Architecture:** 参考下方原文档的实现方案和数据模型

**Tech Stack:** Python, FastAPI, TypeScript, React

---

### Task 1: 实现核心逻辑与测试

**Files:**
- Test: `tests/test_placeholder.py`

- [ ] **Step 1: Write the failing test**
  - 根据下方的验收标准和测试方案，编写对应的测试用例
- [ ] **Step 2: Run test to verify it fails**
  - 执行测试并确保看到预期失败信息 (Red)
- [ ] **Step 3: Write minimal implementation**
  - 根据下方"实现方案"中的步骤，编写或修改业务代码
- [ ] **Step 4: Run test to verify it passes**
  - 执行测试确保通过 (Green)
- [ ] **Step 5: Commit**
  - `git add` 相关文件并提交 commit

---

## 原始需求与设计细节 (供参考)

## 目标

当 SSE 连接断开时，前端能够自动恢复连接并续传进度，用户无感知或最小感知。

## 5 步恢复流程

```
步骤 1: 检测断线
  ↓ (心跳超时 45 秒 或 EventSource onerror)
步骤 2: 关闭旧连接，清理资源
  ↓
步骤 3: 查询进度恢复 API (GET /api/runs/{run_id}/progress)
  ↓
步骤 4: 根据恢复的进度更新前端状态
  ↓
步骤 5: 重新建立 SSE 连接，从断点续传
```

## 详细实现

### 步骤 1：检测断线

两种方式触发：
- **心跳超时**：前端 45 秒未收到 `heartbeat` 事件
- **EventSource 错误**：网络断开、服务端重启等触发 `onerror`

### 步骤 2：关闭旧连接

```typescript
private cleanup(): void {
  if (this.heartbeatTimer) {
    clearTimeout(this.heartbeatTimer);
    this.heartbeatTimer = null;
  }
  this.eventSource?.close();
  this.eventSource = null;
}
```

### 步骤 3：查询进度恢复 API

在重连前，先调用进度恢复 API 获取当前服务端状态：

```typescript
async function recoverProgress(runId: string): Promise<RecoveryState | null> {
  try {
    const response = await fetch(`/api/runs/${runId}/progress`);
    if (!response.ok) return null;
    return await response.json();
  } catch {
    return null;
  }
}

interface RecoveryState {
  run_id: string;
  status: 'running' | 'completed' | 'failed';
  current: number;       // 已执行用例数
  total: number;         // 总用例数
  last_case_result?: {   // 最后一个用例的结果（仅running状态有）
    case_id: string;
    hit_at_1: boolean;
    // ...
  };
  metrics?: Record<string, number>;  // 如果已完成，包含集合指标
  validation_results?: unknown[];    // 仅completed状态包含
}
```

### 步骤 4：更新前端状态

```typescript
async function handleReconnect(runId: string, state: RecoveryState) {
  // 1. 更新进度条
  setProgress({ current: state.current, total: state.total });

  // 2. 如果运行已完成，直接跳转到报告页
  if (state.status === 'completed') {
    setMetrics(state.metrics);
    if (state.validation_results) {
      setValidationResults(state.validation_results);
    }
    navigate(`/rag-eval/reports/${runId}`);
    return;
  }

  // 3. 如果运行失败，显示错误
  if (state.status === 'failed') {
    setError('测试运行失败，请查看运行详情');
    return;
  }

  // 4. 如果仍在运行，恢复 SSE 连接
  // （由 scheduleReconnect 处理）
}
```

### 步骤 5：重新建立 SSE 连接

```typescript
private scheduleReconnect(runId: string): void {
  // 先尝试恢复进度
  recoverProgress(runId).then(state => {
    if (state) {
      handleReconnect(runId, state);
      // 如果运行已完成或失败，不需要重连SSE
      if (state.status === 'completed' || state.status === 'failed') {
        return;
      }
    }
    // 仍在运行，建立新连接
    this.reconnectAttempts++;
    this.createEventSource(runId);
  });
}
```

## Redis 进度缓存

### 写入时机

后端在以下时机将进度写入 Redis：

```python
# 每个用例执行完成后
await redis_client.setex(
    f"rag_eval:run_progress:{run_id}",
    ttl=3600,  # 1小时过期
    value=json.dumps({
        "run_id": run_id,
        "status": "running",
        "current": current,
        "total": total,
        "last_case_result": case_result
    })
)

# 运行完成时
await redis_client.setex(
    f"rag_eval:run_progress:{run_id}",
    ttl=3600,
    value=json.dumps({
        "run_id": run_id,
        "status": "completed",
        "current": total,
        "total": total,
        "metrics": metrics,
        "validation_results": validation_results
    })
)
```

### 降级策略

当 Redis 不可用时，降级到数据库查询：

```python
async def get_run_progress(run_id: str) -> dict:
    # 1. 优先读 Redis
    try:
        cached = await redis_client.get(f"rag_eval:run_progress:{run_id}")
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    # 2. 降级到数据库
    run = await get_test_run(run_id)
    results = await get_test_run_results(run_id)
    return {
        "run_id": run_id,
        "status": run.status,
        "current": len([r for r in results if r.status == 'completed']),
        "total": run.total_cases,
    }
```

## 验收标准

- [ ] 断线后 5 秒内自动重连（首次）
- [ ] 重连后前端状态与服务端一致
- [ ] Redis 缓存命中时，恢复延迟 < 100ms
- [ ] Redis 不可用时，降级到数据库查询正常
- [ ] 运行已完成时，重连后直接跳转报告页
- [ ] 运行失败时，重连后显示错误信息
