import { useState, useEffect, useRef, useCallback } from 'react';
import { createSSEConnection } from '../utils/sse';

/** SSE 事件类型 */
export interface SSEEvent {
  type: string;
  data: Record<string, unknown>;
}

/** SSE 连接状态 */
export type SSEStatus = 'connecting' | 'connected' | 'done' | 'error';

/** 终结 SSE 流的关键事件类型集合 */
const TERMINAL_EVENTS = new Set([
  'run_completed',
  'run_failed',
  'generation_completed',
  'generation_failed',
  'evaluation_completed',
  'evaluation_failed',
]);

/**
 * SSE 进度监听 Hook
 *
 * 基于 fetch API 实现，支持自定义请求头（如 Authorization token），
 * 替代不支持自定义 Header 的原生 EventSource。
 *
 * @param url - SSE 端点 URL，传入 null 时不会发起连接
 * @returns events - 接收到的全部 SSE 事件，status - 当前连接状态
 */
export function useSSEProgress(url: string | null) {
  const [events, setEvents] = useState<SSEEvent[]>([]);
  const [status, setStatus] = useState<SSEStatus>('connecting');
  const eventsRef = useRef<SSEEvent[]>([]);

  const handleMessage = useCallback((raw: string) => {
    try {
      const event: SSEEvent = JSON.parse(raw);
      eventsRef.current = [...eventsRef.current, event];
      setEvents(eventsRef.current);
      if (TERMINAL_EVENTS.has(event.type)) {
        setStatus('done');
      }
    } catch {
      // 非 JSON 格式数据忽略
    }
  }, []);

  useEffect(() => {
    if (!url) {
      setStatus('connecting');
      return;
    }

    const abortController = new AbortController();
    setStatus('connecting');
    eventsRef.current = [];
    setEvents([]);

    createSSEConnection(url, abortController.signal, {
      onOpen: () => setStatus('connected'),
      onMessage: handleMessage,
      onError: () => {
        setStatus('error');
      },
    });

    return () => {
      abortController.abort();
    };
  }, [url, handleMessage]);

  return { events, status };
}
