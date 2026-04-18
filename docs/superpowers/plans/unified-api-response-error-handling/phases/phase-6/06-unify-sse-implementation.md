# Phase 6-6: 统一 SSE 实现

> **需求来源**: spec 文档 `unified-api-response-and-error-handling.md` 中 `7.5.4` 节
> **所属 Phase**: Phase 6

## 需求定义

统一 2 个 SSE hook + 1 个 Service 为单一 hook 实现，消除重复的 SSE 连接代码。

## 验收标准

- [ ] 统一为单一 `useSSE` hook
- [ ] 删除旧的 `useSSE.ts`、`useSseClient.ts`、`SseClient`
- [ ] 断线重连机制正常
- [ ] 功能回归测试通过

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `frontend/src/shared/hooks/useSSE.ts` | 新增 | 统一 SSE hook |
| `frontend/src/shared/hooks/useSseClient.ts` | 删除 | 旧实现 |
| `frontend/src/features/rag-eval/hooks/useSSE.ts` | 删除 | 旧实现 |
| `frontend/src/shared/lib/SseClient.ts` | 删除 | 旧实现 |

## 实现方案

### shared/hooks/useSSE.ts

```typescript
/**
 * 统一 SSE Hook
 * 
 * 提供 SSE 连接、断线重连、事件处理功能。
 * 替代旧的 useSSE.ts、useSseClient.ts、SseClient。
 */

import { useEffect, useRef, useCallback, useState } from 'react';

interface UseSSEOptions {
  url: string;
  enabled?: boolean;
  onMessage?: (event: string, data: unknown) => void;
  onError?: (error: Event) => void;
  onOpen?: () => void;
  reconnectAttempts?: number;
  reconnectInterval?: number;
}

export function useSSE(options: UseSSEOptions) {
  const {
    url,
    enabled = true,
    onMessage,
    onError,
    onOpen,
    reconnectAttempts = 5,
    reconnectInterval = 3000,
  } = options;

  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectCountRef = useRef(0);
  const [isConnected, setIsConnected] = useState(false);

  const connect = useCallback(() => {
    if (!enabled) return;

    const es = new EventSource(url);
    eventSourceRef.current = es;

    es.onopen = () => {
      setIsConnected(true);
      reconnectCountRef.current = 0;
      onOpen?.();
    };

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        const eventType = data.event || data.type;
        onMessage?.(eventType, data);
      } catch (e) {
        console.error('SSE 消息解析失败:', e);
      }
    };

    es.onerror = (error) => {
      setIsConnected(false);
      onError?.(error);

      // 断线重连（指数退避）
      if (reconnectCountRef.current < reconnectAttempts) {
        const delay = reconnectInterval * Math.pow(2, reconnectCountRef.current);
        setTimeout(() => {
          reconnectCountRef.current++;
          connect();
        }, delay);
      }
    };
  }, [url, enabled, onMessage, onError, onOpen, reconnectAttempts, reconnectInterval]);

  const disconnect = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    setIsConnected(false);
  }, []);

  useEffect(() => {
    if (enabled) {
      connect();
    }
    return () => {
      disconnect();
    };
  }, [enabled, connect, disconnect]);

  return { isConnected, connect, disconnect };
}
```

## 测试方案

1. SSE 连接成功
2. 消息解析正确
3. 断线重连机制工作
4. 组件卸载时断开连接

## 注意事项

- 断线重连使用指数退避（3s → 6s → 12s → ...）
- 最大重连次数可配置
- 组件卸载时自动断开，防止内存泄漏
