import { useEffect, useRef, useCallback, useState } from 'react';
import { API_BASE_URL } from '@shared/lib/constants';

export interface UseSSEOptions {
  url: string;
  enabled?: boolean;
  onMessage?: (event: string, data: any) => void;
  onError?: (error: Event) => void;
  onOpen?: () => void;
  reconnectAttempts?: number;
  reconnectInterval?: number;
}

function buildAbsoluteUrl(url: string): string {
  if (url.startsWith('http://') || url.startsWith('https://')) {
    return url;
  }
  const base = API_BASE_URL.replace(/\/$/, '');
  const path = url.startsWith('/') ? url : `/${url}`;
  return `${base}${path}`;
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
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const [isConnected, setIsConnected] = useState(false);

  const disconnect = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    setIsConnected(false);
  }, []);

  const connect = useCallback(() => {
    if (!enabled) return;

    disconnect(); // Ensure any existing connection is closed

    try {
      const absoluteUrl = buildAbsoluteUrl(url);
      const es = new EventSource(absoluteUrl);
      eventSourceRef.current = es;

      es.onopen = () => {
        setIsConnected(true);
        reconnectCountRef.current = 0;
        onOpen?.();
      };

      es.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          const eventType = data.event || data.type || 'message';
          onMessage?.(eventType, data);
        } catch (e) {
          console.error('SSE 消息解析失败:', e);
        }
      };

      es.addEventListener('error', (error) => {
        setIsConnected(false);
        onError?.(error);
        es.close();

        // 断线重连（指数退避）
        if (reconnectCountRef.current < reconnectAttempts) {
          const delay = reconnectInterval * Math.pow(2, reconnectCountRef.current);
          reconnectTimeoutRef.current = setTimeout(() => {
            reconnectCountRef.current++;
            connect();
          }, delay);
        }
      });
    } catch (err) {
      console.error('Failed to create EventSource:', err);
    }
  }, [url, enabled, onMessage, onError, onOpen, reconnectAttempts, reconnectInterval, disconnect]);

  useEffect(() => {
    if (enabled) {
      connect();
    } else {
      disconnect();
    }
    return () => {
      disconnect();
    };
  }, [enabled, connect, disconnect]);

  return { isConnected, connect, disconnect };
}