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

export function useSSE(options: UseSSEOptions = {}) {
  const optionsRef = useRef(options);
  optionsRef.current = options;

  const eventSourceRef = useRef<EventSource | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [lastEvent, setLastEvent] = useState<SSEEvent | null>(null);

  const connect = useCallback((channel: string) => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || '';
    let url: string;
    const isLocalhost8000 = apiBaseUrl.startsWith('http') && apiBaseUrl.includes('localhost:8000');
    const base = isLocalhost8000 ? '' : apiBaseUrl;

    if (channel.startsWith('test_run:')) {
      const runId = channel.split(':')[1];
      url = `${base}/api/v1/rag/test/runs/${runId}/sse`;
    } else if (channel.startsWith('draft_generation:')) {
      const taskId = channel.split(':')[1];
      url = `${base}/rag/test/drafts/generate/${taskId}/stream`;
    } else if (channel.startsWith('exports:')) {
      const userId = channel.split(':')[1];
      url = `${base}/api/v1/rag/test/sse/exports?user_id=${userId}`;
    } else {
      url = `${base}${channel}`;
    }

    const es = new EventSource(url);

    es.onopen = () => {
      setIsConnected(true);
    };

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as SSEEvent;
        setLastEvent(data);

        if (data.type === 'heartbeat') {
          return;
        }

        const { onMessage, onProgress, onComplete, onError } = optionsRef.current;

        onMessage?.(data);

        if (data.type === 'progress' && typeof data.progress === 'number') {
          onProgress?.(data.progress, data);
        } else if (data.type === 'complete') {
          onComplete?.(data);
          es.close();
          setIsConnected(false);
        } else if (data.type === 'error') {
          onError?.(data.message as string || '未知错误');
          es.close();
          setIsConnected(false);
        }
      } catch {
        console.error('SSE 消息解析失败:', event.data);
      }
    };

    es.onerror = () => {
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

  useEffect(() => {
    return () => {
      disconnect();
    };
  }, [disconnect]);

  return { connect, disconnect, isConnected, lastEvent };
}
