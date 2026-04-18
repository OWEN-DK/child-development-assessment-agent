/**
 * SSE客户端 React Hook
 * 
 * 封装SseClient类，提供React组件友好的使用方式。
 * 在组件卸载时自动断开连接。
 */

import { useEffect, useRef, useCallback } from 'react';
import { SseClient, SseClientOptions } from '@/services/sse-client';
import type { SseEvent } from '@/types/sse-events';

/**
 * 测试运行SSE Hook
 * 用于监听测试运行的实时进度
 */
export function useTestRunSse(runId: string | null, options?: SseClientOptions) {
  const clientRef = useRef<SseClient | null>(null);

  const connect = useCallback(() => {
    if (!runId) return;
    const client = new SseClient({ heartbeatTimeout: 45000, ...options });
    client.connect(runId);
    clientRef.current = client;
    return client;
  }, [runId, options]);

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

/**
 * 导出SSE Hook
 * 用于监听导出任务的完成通知（全局连接）
 */
export function useExportSse(userId: string | null, options?: SseClientOptions) {
  const clientRef = useRef<SseClient | null>(null);

  const connect = useCallback(() => {
    if (!userId) return;
    const client = new SseClient(options);
    client.connectExports(userId);
    clientRef.current = client;
    return client;
  }, [userId, options]);

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
    if (userId) {
      connect();
    }
    return () => {
      disconnect();
    };
  }, [userId, connect, disconnect]);

  return { connect, disconnect, on, client: clientRef.current };
}
