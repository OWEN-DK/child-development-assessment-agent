import { useCallback, useRef } from 'react';
import { apiClient } from '@shared/api/client';
import { useKnowledgeQAStore } from '../stores/knowledgeQAStore';

/** SSE 最大重连次数 */
const MAX_SSE_RETRIES = 3;
/** 重连基础延迟（ms），指数退避 */
const RETRY_BASE_DELAY = 2000;

export function useKnowledgeQA() {
  const store = useKnowledgeQAStore();
  const eventSourceRef = useRef<EventSource | null>(null);
  const retryCountRef = useRef(0);
  const taskIdRef = useRef<string | null>(null);

  const ask = useCallback(
    async (question: string, bookIds?: string[]) => {
      store.reset();
      store.setStatus('submitting');
      retryCountRef.current = 0;

      try {
        const { data } = await apiClient.post('/api/v1/knowledge-qa', {
          question,
          book_ids: bookIds || null,
          options: { stream: true, language: 'zh-CN' },
        });

        // apiClient 拦截器已解包 {code, message, data}，data 直接是 {task_id: ...}
        const taskId = data.task_id;
        taskIdRef.current = taskId;
        store.setTaskId(taskId);
        store.setStatus('streaming');

        connectSSE(taskId);
      } catch (err: any) {
        const errorData = err?.response?.data;
        store.setError(errorData?.message || '提交失败，请重试');
      }
    },
    [store],
  );

  /** 建立 SSE 连接，支持失败后指数退避重连 */
  const connectSSE = useCallback(
    (taskId: string) => {
      const sseUrl = `/api/v1/knowledge-qa/stream/${taskId}`;
      const es = new EventSource(sseUrl);
      eventSourceRef.current = es;

      es.addEventListener('message', (event) => {
        try {
          const msg = JSON.parse(event.data);
          const eventType = msg.type || msg.event;
          const eventData = msg.data || msg;

          switch (eventType) {
            case 'qa_started':
            case 'qa_progress':
            case 'qa_books_matched':
            case 'qa_section_done':
            case 'qa_verify_citations':
            case 'progress':
              store.setProgress({
                step: eventData.step ?? 'unknown',
                message: eventData.message,
                status: eventData.status || 'running',
                metadata: eventData.metadata,
              });
              // 逐节完成事件：增量追加到 store
              if (
                eventData.step?.endsWith('_done') &&
                eventData.metadata?.section
              ) {
                store.addSection(eventData.metadata.section);
              }
              // 收到有效数据，重置重连计数
              retryCountRef.current = 0;
              break;

            case 'qa_completed':
            case 'complete':
              es.close();
              if (eventData.result) {
                store.setResult(eventData.result);
              } else {
                fetchResult(taskId);
              }
              break;

            case 'qa_timeout':
              es.close();
              if (eventData.result) {
                store.setResult(eventData.result);
              } else {
                fetchResult(taskId);
              }
              break;

            case 'qa_failed':
            case 'error':
              es.close();
              store.setError(eventData.message || '生成失败');
              break;

            case 'heartbeat':
              retryCountRef.current = 0;
              break;

            default:
              break;
          }
        } catch {
          // SSE 事件解析失败，忽略
        }
      });

      es.addEventListener('error', () => {
        es.close();
        eventSourceRef.current = null;

        // 任务已完成时 EventSource 会因服务端关闭而触发 error
        // 此时尝试轮询最终结果，而非盲目重连
        if (taskIdRef.current) {
          pollFinalResult(taskIdRef.current);
        }
      });
    },
    [store],
  );

  /** SSE 断线后：先尝试轮询最终结果，若任务仍在运行则指数退避重连 */
  const pollFinalResult = useCallback(
    async (taskId: string) => {
      try {
        const { data } = await apiClient.get(
          `/api/v1/knowledge-qa/status/${taskId}`,
        );
        // apiClient 拦截器已解包，data 直接是任务状态对象
        if (data?.result) {
          // 任务已完成，直接设置结果
          store.setResult(data.result);
          return;
        }
        if (data?.status === 'failed') {
          store.setError(data.error || '任务执行失败');
          return;
        }

        // 任务仍在运行，尝试重连 SSE
        if (retryCountRef.current < MAX_SSE_RETRIES) {
          retryCountRef.current += 1;
          const delay = RETRY_BASE_DELAY * Math.pow(2, retryCountRef.current - 1);
          setTimeout(() => {
            if (taskIdRef.current === taskId && store.status === 'streaming') {
              connectSSE(taskId);
            }
          }, delay);
        } else {
          // 超过重连上限，降级为轮询模式
          store.setError('SSE 连接不稳定，正在通过轮询获取结果…');
          startPolling(taskId);
        }
      } catch {
        // 轮询状态也失败，尝试重连
        if (retryCountRef.current < MAX_SSE_RETRIES) {
          retryCountRef.current += 1;
          const delay = RETRY_BASE_DELAY * Math.pow(2, retryCountRef.current - 1);
          setTimeout(() => {
            if (taskIdRef.current === taskId && store.status === 'streaming') {
              connectSSE(taskId);
            }
          }, delay);
        } else {
          store.setError('获取结果失败，请刷新页面重试');
        }
      }
    },
    [store, connectSSE],
  );

  /** 降级轮询：每 5s 查一次任务状态，直到完成或失败 */
  const startPolling = useCallback(
    (taskId: string) => {
      const poll = async () => {
        if (store.status !== 'streaming') return;
        try {
          const { data } = await apiClient.get(
            `/api/v1/knowledge-qa/status/${taskId}`,
          );
          // apiClient 拦截器已解包，data 直接是任务状态对象
          if (data?.result) {
            store.setResult(data.result);
            return;
          }
          if (data?.status === 'failed') {
            store.setError(data.error || '任务执行失败');
            return;
          }
          // 仍在运行，继续轮询
          setTimeout(poll, 5000);
        } catch {
          store.setError('获取结果失败');
        }
      };
      setTimeout(poll, 5000);
    },
    [store],
  );

  const fetchResult = async (taskId: string) => {
    try {
      const { data } = await apiClient.get(
        `/api/v1/knowledge-qa/status/${taskId}`,
      );
      if (data?.result) {
        store.setResult(data.result);
      } else if (data?.status === 'failed') {
        store.setError(data?.error || '任务执行失败');
      }
    } catch {
      store.setError('获取结果失败');
    }
  };

  const cancel = useCallback(() => {
    eventSourceRef.current?.close();
    eventSourceRef.current = null;
    taskIdRef.current = null;
    retryCountRef.current = 0;
    store.reset();
  }, [store]);

  return {
    ask,
    cancel,
    status: store.status,
    progress: store.progress,
    result: store.result,
    error: store.error,
  };
}
