# 前端 SSE 监听批量测试 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 前端 SSE 监听批量测试

**Architecture:** 参考下方原文档的实现方案和数据模型

**Tech Stack:** Python, FastAPI, TypeScript, React

---

### Task 1: 实现核心逻辑与测试

**Files:**
- Create: `frontend/src/hooks/useSSE.ts`
- Modify: `frontend/src/api/rag-test/index.ts`
- Modify: `frontend/src/features/rag-evaluation/components/BatchTestPanel.tsx` 或类似组件`
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
> **根因**: 前端发 POST 后等待 HTTP 响应，但批量测试远超 30 秒超时

---

## 需求定义

当前前端发起批量测试时，通过 `axios.post()` 调用后端 API，然后等待 HTTP 响应。但批量测试可能运行数分钟，远超 axios 的 30 秒超时，导致前端报超时错误。

**修复要求**：
1. 前端发起批量测试后，不得等待 HTTP 响应
2. 改为通过 SSE 监听任务进度
3. 前端实时显示进度百分比和当前处理的用例

---

## 验收标准

- [ ] 前端发起批量测试后立即返回，不等待 HTTP 响应
- [ ] 前端通过 SSE 实时接收进度事件
- [ ] 前端 UI 显示进度百分比、当前用例、已完成的用例数

---

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `frontend/src/api/rag-test/index.ts` | 修改 | `runBatchTests` 改为 202 Accepted 后返回 |
| `frontend/src/features/rag-evaluation/components/BatchTestPanel.tsx` 或类似组件 | 修改 | 新增 SSE 监听逻辑 |
| `frontend/src/hooks/useSSE.ts` | 新增 | 通用 SSE Hook |

---

## 实现方案

### 前端实现

**步骤 1：新增通用 SSE Hook**

```typescript
// frontend/src/hooks/useSSE.ts

import { useEffect, useRef, useCallback, useState } from 'react';

interface SSEEvent {
  type: string;
  [key: string]: unknown;
}

interface UseSSEOptions {
  onMessage?: (event: SSEEvent) => void;
  onProgress?: (progress: number, data: SSEEvent) => void;
  onComplete?: (data: SSEEvent) => void;
  onError?: (error: string) => void;
}

export function useSSE(options: UseSSEOptions & { userId?: string } = {}) {
  // 使用 ref 存储回调，避免闭包陷阱导致 EventSource 频繁重连
  const optionsRef = useRef(options);
  optionsRef.current = options;

  const eventSourceRef = useRef<EventSource | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [lastEvent, setLastEvent] = useState<SSEEvent | null>(null);

  const connect = useCallback((channel: string) => {
    // 关闭已有连接
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || '';
    // channel 格式为 "test_run:{run_id}" 或 "draft_generation:{task_id}"
    // 映射到后端实际 SSE 端点
    let url: string;
    if (channel.startsWith('test_run:')) {
      const runId = channel.split(':')[1];
      url = `${apiBaseUrl}/api/runs/${runId}/sse`;
    } else if (channel.startsWith('draft_generation:')) {
      const taskId = channel.split(':')[1];
      url = `${apiBaseUrl}/rag/test/drafts/generate/${taskId}/stream`;
    } else {
      // 未知频道类型，使用通用端点（Phase-2 新增）
      const userId = options.userId || '';
      url = `${apiBaseUrl}/api/sse/exports?user_id=${userId}`;
    }
    const es = new EventSource(url);

    es.onopen = () => {
      setIsConnected(true);
    };

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as SSEEvent;
        setLastEvent(data);

        // 心跳事件忽略
        if (data.type === 'heartbeat') {
          return;
        }

        // 从 ref 读取最新回调，避免闭包捕获旧值
        const { onMessage, onProgress, onComplete, onError } = optionsRef.current;

        onMessage?.(data);

        if (data.type === 'progress' && typeof data.progress === 'number') {
          onProgress?.(data.progress, data);
        } else if (data.type === 'complete') {
          onComplete?.(data);
          es.close();
          setIsConnected(false);
        } else if (data.type === 'error') {
          onError?.(data.message || '未知错误');
          es.close();
          setIsConnected(false);
        }
      } catch {
        console.error('SSE 消息解析失败:', event.data);
      }
    };

    es.onerror = () => {
      // EventSource 会自动重连，这里只记录日志
      console.warn('SSE 连接断开，尝试重连中...');
    };

    eventSourceRef.current = es;
  }, []);

  const disconnect = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
      setIsConnected(false);
    }
  }, []);

  // 组件卸载时自动断开连接，防止 EventSource 泄漏
  useEffect(() => {
    return () => {
      disconnect();
    };
  }, [disconnect]);

  return { connect, disconnect, isConnected, lastEvent };
}
```

**步骤 2：修改批量测试 API 调用**

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
 * 前端通过 SSE 监听进度，不等待 HTTP 响应。
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
      // 不设置超时，因为后端会立即返回 202
      timeout: 10000, // 10 秒足够接收 202 响应
    }
  );
  return data;
}
```

**步骤 3：在批量测试组件中使用 SSE**

```typescript
// frontend/src/features/rag-evaluation/components/BatchTestPanel.tsx

import { useState, useCallback } from 'react';
import { Progress, Button, message, Card, List } from 'antd';
import { runBatchTests } from '@/api/rag-test';
import { useSSE } from '@/hooks/useSSE';

interface BatchTestPanelProps {
  testSetId: string;
}

interface TestCaseStatus {
  caseId: string;
  query: string;
  status: 'pending' | 'running' | 'passed' | 'failed';
  result?: string;
}

export function BatchTestPanel({ testSetId }: BatchTestPanelProps) {
  const [isRunning, setIsRunning] = useState(false);
  const [progress, setProgress] = useState(0);
  const [currentCase, setCurrentCase] = useState<string>('');
  const [completedCount, setCompletedCount] = useState(0);
  const [totalCount, setTotalCount] = useState(0);
  const [caseStatuses, setCaseStatuses] = useState<TestCaseStatus[]>([]);

  const { connect, disconnect } = useSSE({
    onProgress: (percent, data) => {
      setProgress(percent);
      if (data.current_case) {
        setCurrentCase(data.current_case);
      }
      if (data.total) {
        setTotalCount(data.total);
      }
      if (data.completed) {
        setCompletedCount(data.completed);
      }
    },
    onMessage: (data) => {
      // 更新单个用例状态
      if (data.case_id && data.case_status) {
        setCaseStatuses(prev => {
          const existing = prev.find(c => c.caseId === data.case_id);
          if (existing) {
            return prev.map(c =>
              c.caseId === data.case_id
                ? { ...c, status: data.case_status, result: data.result }
                : c
            );
          }
          return [...prev, {
            caseId: data.case_id,
            query: data.query || '',
            status: data.case_status,
            result: data.result,
          }];
        });
      }
    },
    onComplete: () => {
      setIsRunning(false);
      setProgress(100);
      message.success('批量测试完成');
    },
    onError: (errorMsg) => {
      setIsRunning(false);
      message.error(`测试失败: ${errorMsg}`);
    },
  });

  const handleStartTest = useCallback(async () => {
    try {
      setIsRunning(true);
      setProgress(0);
      setCaseStatuses([]);

      // 发起批量测试，获取 task_id 和 channel
      const response = await runBatchTests({ testSetId });

      // 通过 SSE 监听进度
      connect(response.channel);
    } catch (error) {
      setIsRunning(false);
      message.error('发起批量测试失败');
    }
  }, [testSetId, connect]);

  const handleCancel = useCallback(() => {
    disconnect();
    setIsRunning(false);
    message.info('已取消测试');
  }, [disconnect]);

  return (
    <Card title="批量测试">
      <div style={{ marginBottom: 16 }}>
        <Button
          type="primary"
          onClick={handleStartTest}
          loading={isRunning}
          disabled={isRunning}
        >
          开始测试
        </Button>
        {isRunning && (
          <Button danger onClick={handleCancel} style={{ marginLeft: 8 }}>
            取消
          </Button>
        )}
      </div>

      {isRunning && (
        <div style={{ marginBottom: 16 }}>
          <Progress percent={Math.round(progress)} />
          {currentCase && (
            <p>当前用例: {currentCase}</p>
          )}
          {totalCount > 0 && (
            <p>已完成 {completedCount}/{totalCount}</p>
          )}
        </div>
      )}

      {caseStatuses.length > 0 && (
        <List
          size="small"
          dataSource={caseStatuses}
          renderItem={(item) => (
            <List.Item>
              <span>{item.query}</span>
              <span>{item.status}</span>
            </List.Item>
          )}
        />
      )}
    </Card>
  );
}
```

---

## 测试方案

### 手动测试

1. 创建一个包含多个用例的测试集
2. 点击"开始测试"按钮
3. 确认按钮立即变为"取消"（不等待 HTTP 响应）
4. 确认进度条实时更新
5. 确认能看到当前处理的用例
6. 等待所有用例完成，确认显示"批量测试完成"

### 异常测试

1. 在测试进行中刷新页面，确认 SSE 断开
2. 在测试进行中点击"取消"，确认测试停止
3. 后端服务异常时，确认前端显示错误提示

---

## 注意事项

1. **EventSource 认证**：SSE 端点如果使用认证，EventSource 无法发送 Authorization Header。需通过 cookie 或 URL 参数传递 token，或 SSE 端点免认证（通过 task_id 鉴权）。
2. **断线重连**：EventSource 内置自动重连，但重连后无法恢复错过的消息。Phase 2 会实现进度恢复 API。
3. **SSE 端点映射**：前端根据 channel 前缀映射到不同后端端点（test_run→`/api/runs/{id}/sse`，draft_generation→`/rag/test/drafts/generate/{id}/stream`）。与 Phase-2 的 `04-sse-controller-routes.md` 保持一致。
4. **组件卸载清理**：组件卸载时必须调用 `disconnect()`，否则 EventSource 连接泄漏。

---

**返回索引：** [Phase 0 总览](../00-overview.md)
