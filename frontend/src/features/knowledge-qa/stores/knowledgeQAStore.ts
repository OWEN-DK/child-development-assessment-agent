/**
 * 知识问答全局 store
 *
 * SSE 管理参考 draftGenerationStore 模式：
 * - SSE 连接在 store 中管理，组件卸载时仅断开连接，状态保留
 * - 重挂载时自动重连（通过 onMount / onUnmount）
 * - 使用 fetch-based createSSEConnection 替代原生 EventSource
 * - localStorage 用于页面刷新后恢复活跃任务
 */

import { create } from 'zustand';
import { createSSEConnection } from '../../rag-eval/utils/sse';
import { API_BASE_URL } from '@shared/lib/constants';
import { apiClient } from '@shared/api/client';
import type {
  KnowledgeQAResponse,
  ProgressState,
  QAStatus,
  SectionOutput,
} from '../types';

/** localStorage key：页面刷新后恢复活跃任务 */
const LS_ACTIVE_TASK_KEY = 'knowledge_qa_active_task';
const LS_ACTIVE_QUESTION_KEY = 'knowledge_qa_active_question';

function saveActiveTask(taskId: string, question: string) {
  try {
    localStorage.setItem(LS_ACTIVE_TASK_KEY, taskId);
    localStorage.setItem(LS_ACTIVE_QUESTION_KEY, question);
  } catch { /* noop */ }
}
function clearActiveTask() {
  try {
    localStorage.removeItem(LS_ACTIVE_TASK_KEY);
    localStorage.removeItem(LS_ACTIVE_QUESTION_KEY);
  } catch { /* noop */ }
}

interface KnowledgeQAState {
  status: QAStatus;
  taskId: string | null;
  currentQuestion: string | null;
  progress: ProgressState | null;
  result: KnowledgeQAResponse | null;
  /** 流式过程中增量收集已完成节（按 index 排序） */
  completedSections: SectionOutput[];
  error: string | null;
  viewMode: 'markdown' | 'json';

  // ─── SSE 生命周期 ───
  _sseController: AbortController | null;
  _mounted: boolean;

  // ─── 操作 ───
  /** 提交问题并连接 SSE */
  ask: (question: string, bookIds?: string[]) => Promise<void>;
  /** 取消当前任务 */
  cancel: () => void;
  setViewMode: (mode: 'markdown' | 'json') => void;
  reset: () => void;

  // ─── SSE 生命周期（由组件挂载/卸载触发） ───
  onMount: () => void;
  onUnmount: () => void;
  _subscribeSSE: (taskId: string) => void;
  _disconnectSSE: () => void;
  _fetchResult: (taskId: string) => Promise<void>;
}

export const useKnowledgeQAStore = create<KnowledgeQAState>((set, get) => ({
  status: 'idle',
  taskId: null,
  currentQuestion: null,
  progress: null,
  result: null,
  completedSections: [],
  error: null,
  viewMode: 'markdown',

  _sseController: null,
  _mounted: false,

  ask: async (question, bookIds) => {
    get().reset();
    set({ status: 'submitting', currentQuestion: question });

    try {
      const { data } = await apiClient.post('/api/v1/knowledge-qa', {
        question,
        book_ids: bookIds || null,
        options: { stream: true, language: 'zh-CN' },
      });

      const taskId = data.task_id;
      set({ taskId, status: 'streaming' });
      saveActiveTask(taskId, question);
      get()._subscribeSSE(taskId);
    } catch (err: any) {
      const errorData = err?.response?.data;
      set({ error: errorData?.message || '提交失败，请重试', status: 'error' });
    }
  },

  cancel: async () => {
    const taskId = get().taskId;
    // 先断开 SSE，避免继续接收进度事件
    get()._disconnectSSE();
    // 立即清除 localStorage 并重置 UI，不等后端响应
    clearActiveTask();
    get().reset();
    // 后端取消 API 异步调用（fire-and-forget），不阻塞 UI 恢复
    if (taskId) {
      apiClient.post(`/api/v1/knowledge-qa/cancel/${taskId}`).catch(() => {
        // 取消 API 失败不影响前端状态
      });
    }
  },

  setViewMode: (viewMode) => set({ viewMode }),

  reset: () =>
    set({
      status: 'idle',
      taskId: null,
      currentQuestion: null,
      progress: null,
      result: null,
      completedSections: [],
      error: null,
    }),

  // ─── SSE 生命周期 ───

  onMount: () => {
    set({ _mounted: true });

    // 页面刷新后：检查是否有活跃任务需要恢复
    const savedTaskId = (() => {
      try { return localStorage.getItem(LS_ACTIVE_TASK_KEY); } catch { return null; }
    })();

    if (!savedTaskId || get().status !== 'idle') return;

    // 恢复当前问题文本（用于侧边栏显示）
    const savedQuestion = (() => {
      try { return localStorage.getItem(LS_ACTIVE_QUESTION_KEY); } catch { return null; }
    })();

    // 查询任务状态，如果在运行则重连 SSE
    (async () => {
      try {
        const { data } = await apiClient.get(
          `/api/v1/knowledge-qa/status/${savedTaskId}`,
        );
        if (!data || data.status === 'failed' || data.status === 'cancelled') {
          clearActiveTask();
          return;
        }
        if (data?.result) {
          set({
            result: data.result,
            completedSections: data.result.sections,
            status: 'done',
            currentQuestion: data.result.question || savedQuestion,
          });
          clearActiveTask();
          return;
        }
        // 任务正在运行
        set({
          taskId: savedTaskId,
          status: 'streaming',
          currentQuestion: savedQuestion,
        });
        if (data?.stage && data?.message) {
          set({
            progress: {
              step: data.stage,
              message: data.message,
              status: data.status || 'running',
              metadata: data.metadata || {},
            },
          });
        }
        get()._subscribeSSE(savedTaskId);
      } catch {
        clearActiveTask();
      }
    })();
  },

  onUnmount: () => {
    get()._disconnectSSE();
    set({ _mounted: false });
  },

  _disconnectSSE: () => {
    const ctrl = get()._sseController;
    if (ctrl) {
      ctrl.abort();
      set({ _sseController: null });
    }
  },

  _subscribeSSE: (taskId) => {
    // 先断开旧连接
    get()._disconnectSSE();

    const controller = new AbortController();
    set({ _sseController: controller });

    const base = API_BASE_URL.replace(/\/$/, '');
    const url = `${base}/api/v1/knowledge-qa/stream/${taskId}`;

    createSSEConnection(url, controller.signal, {
      onOpen: () => {
        set({
          progress: {
            step: '_connected',
            message: '已连接，等待服务端处理…',
            status: 'running',
          },
        });
      },
      onMessage: (raw) => {
        try {
          const msg = JSON.parse(raw);
          const eventType = msg.type || msg.event;
          const eventData = msg.data || msg;

          switch (eventType) {
            case 'connected':
              set({
                progress: {
                  step: '_connected',
                  message: '已连接，等待服务端处理…',
                  status: 'running',
                },
              });
              break;

            case 'qa_started':
            case 'qa_progress':
            case 'qa_books_matched':
            case 'qa_section_done':
            case 'qa_verify_citations':
            case 'progress':
              set({
                progress: {
                  step: eventData.step ?? 'unknown',
                  message: eventData.message,
                  status: eventData.status || 'running',
                  metadata: eventData.metadata,
                },
              });
              if (
                eventData.step?.endsWith('_done') &&
                eventData.metadata?.section
              ) {
                const sec = eventData.metadata.section as SectionOutput;
                set((s) => {
                  const existing = s.completedSections.filter(
                    (x) => x.index !== sec.index,
                  );
                  const updated = [...existing, sec].sort(
                    (a, b) => a.index - b.index,
                  );
                  return { completedSections: updated };
                });
              }
              break;

            case 'qa_completed':
            case 'complete':
              get()._disconnectSSE();
              clearActiveTask();
              if (eventData.result) {
                set({
                  result: eventData.result,
                  completedSections: eventData.result.sections,
                  status: 'done',
                });
              } else {
                get()._fetchResult(taskId);
              }
              break;

            case 'qa_timeout':
              get()._disconnectSSE();
              if (eventData.result) {
                set({
                  result: eventData.result,
                  completedSections: eventData.result.sections,
                  status: 'done',
                });
              } else {
                get()._fetchResult(taskId);
              }
              break;

            case 'qa_failed':
            case 'error':
              get()._disconnectSSE();
              clearActiveTask();
              set({
                error: eventData.message || '生成失败',
                status: 'error',
              });
              break;

            default:
              break;
          }
        } catch {
          // 忽略解析异常
        }
      },
      onError: () => {
        if (!get()._mounted) return;
        // SSE 连接异常：尝试轮询最终结果
        get()._disconnectSSE();
        const tid = get().taskId;
        if (tid) get()._fetchResult(tid);
      },
    });
  },

  _fetchResult: async (taskId) => {
    try {
      const { data } = await apiClient.get(
        `/api/v1/knowledge-qa/status/${taskId}`,
      );
      if (data?.result) {
        set({
          result: data.result,
          completedSections: data.result.sections,
          status: 'done',
        });
        clearActiveTask();
      } else if (data?.status === 'failed') {
        set({
          error: data.error || '任务执行失败',
          status: 'error',
        });
        clearActiveTask();
      }
      // 如果仍在运行且 _mounted，重连 SSE
      if (
        data?.status === 'running' &&
        get()._mounted &&
        get().status === 'streaming'
      ) {
        get()._subscribeSSE(taskId);
      }
    } catch {
      set({ error: '获取结果失败', status: 'error' });
    }
  },
}));
