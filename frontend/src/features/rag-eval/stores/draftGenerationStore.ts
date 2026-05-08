/**
 * 草稿生成进度全局 store
 *
 * 解决问题：页面切换后草稿生成进度丢失 / 重置为"等待中"。
 * 将进度状态和 SSE 连接提升到 Zustand store，
 * 组件卸载时仅断开 SSE，task 状态保留；重挂载时自动重连。
 */

import { create } from 'zustand';
import { createSSEConnection } from '../utils/sse';
import { API_BASE_URL } from '@shared/lib/constants';
import type { DraftGenerationTask } from '../../../components/progress/configs/draftGeneration';

/** SSE 各阶段对应进度百分比 */
const STAGE_PROGRESS: Record<string, number> = {
  loading_document: 2,
  generation_started: 5,
  metadata_analyzed: 15,
  pipeline_running: 20,
  drafts_generated: 85,
  faithfulness_checked: 88,
  deduplication_completed: 90,
};

interface DraftGenerationState {
  /** 所有活跃/近期完成的 task */
  tasks: DraftGenerationTask[];
  /** 每个任务的 SSE 连接控制器 */
  _sseControllers: Record<string, AbortController>;
  /** 标记组件是否已挂载（防止未挂载时重连） */
  _mounted: boolean;

  /** 注册新 task 并启动 SSE */
  startTracking: (taskId: string, documentName?: string) => void;
  /** 移除 task 并断开 SSE */
  removeTask: (taskId: string) => void;
  /** 更新单个 task */
  _updateTask: (taskId: string, patch: Partial<DraftGenerationTask>) => void;
  /** 页面挂载时调用：标记已挂载 + 重连所有非终态 task 的 SSE */
  onMount: () => void;
  /** 页面卸载时调用：断开所有 SSE，但保留 task 状态 */
  onUnmount: () => void;
  /** 内部：为单个 task 建立 SSE 连接 */
  _subscribeSSE: (taskId: string) => void;
}

export const useDraftGenerationStore = create<DraftGenerationState>((set, get) => ({
  tasks: [],
  _sseControllers: {},
  _mounted: false,

  startTracking: (taskId, documentName) => {
    const { tasks } = get();
    // 避免重复跟踪
    if (tasks.some(t => t.taskId === taskId)) return;

    const task: DraftGenerationTask = {
      taskId,
      status: 'pending',
      progress: 0,
      message: '等待开始...',
      createdAt: Date.now(),
      documentName,
    };

    set({ tasks: [...tasks, task] });
    get()._subscribeSSE(taskId);
  },

  removeTask: (taskId) => {
    const { _sseControllers } = get();
    _sseControllers[taskId]?.abort();
    const nextControllers = { ..._sseControllers };
    delete nextControllers[taskId];

    set((s) => ({
      tasks: s.tasks.filter(t => t.taskId !== taskId),
      _sseControllers: nextControllers,
    }));
  },

  _updateTask: (taskId, patch) => {
    set((s) => ({
      tasks: s.tasks.map(t => t.taskId === taskId ? { ...t, ...patch } : t),
    }));
  },

  onMount: () => {
    set({ _mounted: true });
    const { tasks } = get();
    // 重连所有非终态 task
    for (const task of tasks) {
      if (task.status === 'running' || task.status === 'pending') {
        get()._subscribeSSE(task.taskId);
      }
    }
  },

  onUnmount: () => {
    // 仅断开 SSE，不清除 task 状态
    const { _sseControllers } = get();
    Object.values(_sseControllers).forEach(c => c.abort());
    set({ _sseControllers: {}, _mounted: false });
  },

  _subscribeSSE: (taskId) => {
    // 先取消旧连接
    const existing = get()._sseControllers[taskId];
    if (existing) existing.abort();

    const controller = new AbortController();
    set((s) => ({ _sseControllers: { ...s._sseControllers, [taskId]: controller } }));

    const base = API_BASE_URL.replace(/\/$/, '');
    createSSEConnection(
      `${base}/api/v1/rag/eval/drafts/generation/${taskId}/stream`,
      controller.signal,
      {
        onOpen: () => {
          get()._updateTask(taskId, { status: 'running', message: '已连接' });
        },
        onMessage: (raw) => {
          try {
            const evt = JSON.parse(raw);
            const { tasks } = get();
            const task = tasks.find(t => t.taskId === taskId);
            if (!task) return;

            if (evt.type === 'progress') {
              const stage = evt.stage as string | undefined;
              const message = (evt.message as string) ?? stage ?? task.message;
              let progress: number;

              if (stage === 'pipeline_running' && typeof evt.metadata?.pct === 'number') {
                progress = evt.metadata.pct;
              } else {
                progress = stage ? (STAGE_PROGRESS[stage] ?? task.progress) : task.progress;
              }

              get()._updateTask(taskId, { status: 'running', progress, message });
            }

            if (evt.type === 'complete') {
              const result = evt.result as { saved_count?: number; skipped?: number } | undefined;
              get()._updateTask(taskId, {
                status: 'completed',
                progress: 100,
                message: (evt.message as string) ?? '生成完成',
                generated: result?.saved_count,
                skipped: result?.skipped,
              });
            }

            if (evt.type === 'error') {
              get()._updateTask(taskId, {
                status: 'failed',
                error: (evt.error as string) ?? '生成失败',
                message: (evt.message as string) ?? '生成失败',
              });
            }
          } catch {
            // 忽略解析异常
          }
        },
        onError: () => {
          if (!get()._mounted) return;
          get()._updateTask(taskId, { status: 'failed', error: 'SSE 连接异常' });
        },
      },
    );
  },
}));
