# 前端 API 无超时 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 前端 API 无超时

**Architecture:** 参考下方原文档的实现方案和数据模型

**Tech Stack:** Python, FastAPI, TypeScript, React

---

### Task 1: 实现核心逻辑与测试

**Files:**
- Modify: `frontend/src/api/rag-test/index.ts`
- Modify: `frontend/src/lib/constants.ts`
- Test: `frontend/src/__tests__/placeholder.test.ts`

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

> **需求来源**: spec 文档 `01-phase-0-bug-fixes.md` 中 `2.0.2` 节
> **所属 Phase**: Phase 0
> **根因**: 前端发起批量测试后设置了 30 秒 HTTP 超时，但批量测试通常远超 30 秒

---

## 需求定义

当前前端 axios 客户端默认超时为 30 秒（`API_TIMEOUT = 30000`）。批量测试 API 调用使用此默认值，导致 30 秒后前端报超时错误，即使后端仍在执行。

**修复要求**：
1. 发起批量测试的 API 调用不得设置 HTTP 超时（或设置足够长的超时）
2. 前端依赖 SSE 进度事件判断任务状态，而非 HTTP 响应
3. 其他 API 调用的超时设置保持不变

---

## 验收标准

- [ ] 批量测试超过 30 秒不触发前端超时错误
- [ ] 批量测试 API 在 10 秒内返回 202 Accepted
- [ ] 其他 API 调用的 30 秒超时不受影响

---

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `frontend/src/api/rag-test/index.ts` | 修改 | `runBatchTests` 设置合理超时 |
| `frontend/src/lib/constants.ts` | 检查 | 确认 `API_TIMEOUT` 常量 |

---

## 实现方案

### 前端实现

**步骤 1：修改 `runBatchTests` 的超时设置**

```typescript
// frontend/src/api/rag-test/index.ts

import { apiClient } from '@/api/client';

export interface RunBatchTestsRequest {
  testSetId: string;
  concurrency?: number;
}

export interface RunBatchTestsResponse {
  task_id: string;
  run_id: string;
  channel: string;
}

/**
 * 发起批量测试
 * 
 * 后端返回 202 Accepted，包含 task_id 和 SSE channel。
 * 此 API 应在几秒内返回，因此 10 秒超时足够。
 * 实际进度通过 SSE 监听，不依赖 HTTP 响应超时。
 */
export async function runBatchTests(
  request: RunBatchTestsRequest
): Promise<RunBatchTestsResponse> {
  const { data } = await apiClient.post<RunBatchTestsResponse>(
    '/rag/test/run',
    {
      test_set_id: request.testSetId,
      concurrency: request.concurrency || 5,
    },
    {
      // 此 API 应立即返回 202，10 秒足够
      // 不依赖此超时判断任务是否完成
      timeout: 10000,
    }
  );
  return data;
}
```

**步骤 2：确认其他长时间操作 API 的超时设置**

检查其他可能超过 30 秒的 API 调用：

```typescript
// frontend/src/api/rag-test/index.ts

// 文档上传（解析 + embedding 可能较慢）
export async function uploadSourceDocument(
  file: File,
  title?: string,
  autoGenerate = true
): Promise<{ task_id: string }> {
  const formData = new FormData();
  formData.append('file', file);
  if (title) formData.append('title', title);
  formData.append('auto_generate', String(autoGenerate));
  
  const { data } = await apiClient.post('/rag/test/documents/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    // 上传 + 解析可能超过 30 秒，设为 2 分钟
    timeout: 120000,
  });
  return data;
}

// 草稿生成（LLM 调用可能较慢）
export async function generateDrafts(testSetId: string): Promise<{ task_id: string }> {
  const { data } = await apiClient.post(`/rag/test/drafts/generate/${testSetId}`, null, {
    // LLM 生成可能超过 30 秒，设为 3 分钟
    timeout: 180000,
  });
  return data;
}
```

**步骤 3：确认全局默认超时不影响 SSE**

SSE 使用 `EventSource` 或 `fetch`，不受 axios 超时影响：

```typescript
// SSE 使用 EventSource，无超时配置
const es = new EventSource(url);
// EventSource 由浏览器管理，无 axios timeout

// 或使用 fetch + ReadableStream（assessment SSE）
const response = await fetch('/assess', { ... });
// fetch 默认无超时，除非设置 signal
```

如果需要为 `fetch` 添加超时保护，使用 `AbortController`：

```typescript
// frontend/src/api/assessment/index.ts

const controller = new AbortController();
// 可选：设置超时（当前不设置，依赖浏览器默认行为）
// const timeoutId = setTimeout(() => controller.abort(), 300000); // 5 分钟

const response = await fetch('/assess', {
  method: 'POST',
  body: JSON.stringify(payload),
  headers: { 'Content-Type': 'application/json' },
  signal: controller.signal,
});

// 在 finally 中清理
// clearTimeout(timeoutId);
```

---

## 测试方案

### 手动测试

1. 创建一个包含 50+ 用例的测试集
2. 发起批量测试
3. 等待超过 30 秒
4. 确认前端不报超时错误
5. 确认进度条通过 SSE 正常更新
6. 等待所有用例完成，确认结果正确

### 异常测试

1. 在批量测试进行中关闭后端服务
2. 确认 SSE 连接断开，前端显示错误提示
3. 确认不是因为 axios 超时导致的错误

---

## 注意事项

1. **202 Accepted 语义**：后端应在几秒内返回 202，表示"已接受请求，正在处理"。如果后端处理时间过长（如同步执行所有用例），需改为异步模式。
2. **SSE 是进度来源**：前端不依赖 HTTP 响应判断任务是否完成，而是通过 SSE 的 `complete` 事件。HTTP 响应仅用于获取 `task_id` 和 `channel`。
3. **其他 API 超时**：文档上传、草稿生成等可能超过 30 秒的 API 已单独设置超时。全局默认 30 秒对大多数 CRUD 操作足够。
4. **fetch 超时**：如果使用 `fetch` 而非 `EventSource`，需通过 `AbortController` 设置超时。当前 assessment SSE 使用 `fetch` + `ReadableStream`，无超时设置。

---

**返回索引：** [Phase 0 总览](../00-overview.md)
