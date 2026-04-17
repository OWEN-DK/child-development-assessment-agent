# 05 - 前端 SSE 客户端 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 05 - 前端 SSE 客户端

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

实现前端 SSE 客户端模块，负责连接后端 SSE 端点、解析事件、分发给各页面组件，并处理断线重连。

## 实施文件

`frontend/src/services/sse-client.ts`

## 核心设计

### TypeScript 类型定义

```typescript
// 10 种 SSE 事件联合类型，提供编译时检查
type SseEvent = 
  | { type: 'run_started'; run_id: string; test_set_id: string; total_cases: number; config_version: string; timestamp: string }
  | { type: 'progress'; run_id: string; current_case: number; total_cases: number; current_query: string; elapsed_seconds: number; timestamp: string }
  | { type: 'case_result'; run_id: string; case_id: string; query: string; hit_at_1: boolean; hit_at_3: boolean; hit_at_5: boolean; matched_doc_ids: string[]; matched_doc_scores: number[]; status: 'passed' | 'failed'; timestamp: string }
  | { type: 'test_completed'; run_id: string; total_cases: number; passed_cases: number; overall_metrics: { precision: number; recall: number; f1: number; mrr: number; ndcg: number }; timestamp: string }
  | { type: 'validation_started'; run_id: string; layer: number; timestamp: string }
  | { type: 'validation_completed'; run_id: string; layer: number; duration_ms: number; suggestion_count: number; timestamp: string }
  | { type: 'report_ready'; run_id: string; report_id: string; overall_metrics: { precision: number; recall: number; f1: number; mrr: number; ndcg: number }; total_duration_seconds: number; validation_summary: Record<string, { status: string; suggestion_count?: number }>; timestamp: string }
  | { type: 'run_failed'; run_id: string; error_code: string; error_message: string; failed_at_case_id: string; timestamp: string }
  | { type: 'heartbeat'; run_id: string; timestamp: string }
  | { type: 'export_ready'; task_id: string; report_id: string; download_url: string; file_size_bytes: number; timestamp: string }
  | { type: 'export_failed'; task_id: string; report_id: string; error: string; timestamp: string }
  | { type: 'reconnect_failed' };  // 客户端内部事件

type SseEventHandler = (event: SseEvent) => void;
```

### 类定义

```typescript
type SseEventHandler = (event: SseEvent) => void;

interface SseEvent {
  type: string;
  [key: string]: unknown;
}

interface SseClientOptions {
  baseUrl?: string;
  heartbeatTimeout?: number;  // 心跳超时阈值（毫秒），默认45000
  reconnectBaseDelay?: number; // 重连基础延迟（毫秒），默认1000
  reconnectMaxDelay?: number;  // 重连最大延迟（毫秒），默认30000
  maxReconnectAttempts?: number; // 最大重连次数，默认0（无限）
}

class SseClient {
  private eventSource: EventSource | null = null;
  private handlers: Map<string, Set<SseEventHandler>> = new Map();
  private heartbeatTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectAttempts = 0;
  private isManualClose = false;

  constructor(private options: SseClientOptions = {}) {}

  // 连接
  connect(runId: string): void;

  // 注册事件处理器
  on(eventType: string, handler: SseEventHandler): () => void;

  // 断开连接
  disconnect(): void;

  // 内部方法
  private resetHeartbeat(): void;
  private handleHeartbeatTimeout(): void;
  private scheduleReconnect(runId: string): void;
  private calculateReconnectDelay(): number;
}
```

### 连接逻辑

```typescript
connect(runId: string): void {
  this.isManualClose = false;
  this.reconnectAttempts = 0;
  this.createEventSource(runId);
}

private createEventSource(runId: string): void {
  const url = `${this.options.baseUrl || ''}/api/runs/${runId}/sse`;
  this.eventSource = new EventSource(url);

  this.eventSource.onmessage = (event: MessageEvent) => {
    try {
      const data: SseEvent = JSON.parse(event.data);
      this.resetHeartbeat();
      this.dispatch(data);
    } catch (e) {
      console.error('SSE事件解析失败:', e, event.data);
    }
  };

  this.eventSource.onerror = () => {
    this.cleanup();
    if (!this.isManualClose) {
      this.scheduleReconnect(runId);
    }
  };

  this.resetHeartbeat();
}
```

### 心跳检测

```typescript
private resetHeartbeat(): void {
  if (this.heartbeatTimer) {
    clearTimeout(this.heartbeatTimer);
  }
  this.heartbeatTimer = setTimeout(
    () => this.handleHeartbeatTimeout(),
    this.options.heartbeatTimeout || 45000
  );
}

private handleHeartbeatTimeout(): void {
  console.warn('SSE心跳超时，判定断线');
  this.eventSource?.close();
  this.eventSource = null;
  // 触发重连（由onerror回调处理）
}
```

### 指数退避重连

```typescript
private scheduleReconnect(runId: string): void {
  const maxAttempts = this.options.maxReconnectAttempts || 0;
  if (maxAttempts > 0 && this.reconnectAttempts >= maxAttempts) {
    console.error('SSE重连次数已达上限，停止重连');
    this.dispatch({ type: 'reconnect_failed' });
    return;
  }

  const delay = this.calculateReconnectDelay();
  console.log(`SSE将在${delay}ms后重连（第${this.reconnectAttempts + 1}次）`);

  setTimeout(() => {
    this.reconnectAttempts++;
    this.createEventSource(runId);
  }, delay);
}

private calculateReconnectDelay(): number {
  const base = this.options.reconnectBaseDelay || 1000;
  const max = this.options.reconnectMaxDelay || 30000;
  // 指数退避：1s, 2s, 4s, 8s, 16s, 30s, 30s...
  return Math.min(base * Math.pow(2, this.reconnectAttempts), max);
}
```

### 事件分发

```typescript
on(eventType: string, handler: SseEventHandler): () => void {
  if (!this.handlers.has(eventType)) {
    this.handlers.set(eventType, new Set());
  }
  this.handlers.get(eventType)!.add(handler);

  // 返回取消订阅函数
  return () => {
    this.handlers.get(eventType)?.delete(handler);
  };
}

private dispatch(event: SseEvent): void {
  const typeHandlers = this.handlers.get(event.type);
  if (typeHandlers) {
    typeHandlers.forEach(handler => {
      try {
        handler(event);
      } catch (e) {
        console.error(`SSE事件处理器异常 [${event.type}]:`, e);
      }
    });
  }
}
```

### 清理

```typescript
disconnect(): void {
  this.isManualClose = true;
  this.cleanup();
}

private cleanup(): void {
  if (this.heartbeatTimer) {
    clearTimeout(this.heartbeatTimer);
    this.heartbeatTimer = null;
  }
  this.eventSource?.close();
  this.eventSource = null;
}
```

## React Hook 封装

`frontend/src/hooks/useSseClient.ts`

```typescript
import { useEffect, useRef, useCallback } from 'react';
import { SseClient, SseEvent } from '@/services/sse-client';

export function useTestRunSse(runId: string | null) {
  const clientRef = useRef<SseClient | null>(null);

  const connect = useCallback(() => {
    if (!runId) return;
    const client = new SseClient({ heartbeatTimeout: 45000 });
    client.connect(runId);
    clientRef.current = client;
    return client;
  }, [runId]);

  const disconnect = useCallback(() => {
    clientRef.current?.disconnect();
    clientRef.current = null;
  }, []);

  const on = useCallback(<T extends SseEvent>(
    eventType: string,
    handler: (event: T) => void
  ) => {
    return clientRef.current?.on(eventType, handler as (event: SseEvent) => void);
  }, []);

  useEffect(() => {
    if (runId) {
      connect();
    }
    return () => {
      disconnect();
    };
  }, [runId, connect, disconnect]);

  return { connect, disconnect, on, client: clientRef.current };
}
```

## 验收标准

- [ ] EventSource 连接成功，能接收事件
- [ ] 心跳超时 45 秒后触发断线判定
- [ ] 断线后指数退避重连（1s → 2s → 4s → ... → 30s）
- [ ] 手动断开后不再重连
- [ ] 事件处理器异常不影响其他处理器
- [ ] React Hook 在组件卸载时自动断开
