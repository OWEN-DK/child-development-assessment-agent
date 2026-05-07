/**
 * 报告生成进度全局 store
 *
 * 解决问题：页面切换后 reportProgress 丢失。
 * 将进度状态和活跃任务 ID 提升到 Zustand store，
 * 页面重新挂载时自动重连 SSE。
 */

import { create } from 'zustand';
import { createSSEConnection } from '../utils/sse';

const REPORT_STAGE_MAP: Record<string, ReportProgressEntry> = {
  metrics_computing: { label: '计算指标', percent: 20 },
  metrics_done: { label: '指标完成', percent: 40 },
  building_report: { label: '构建报告', percent: 60 },
  rendering: { label: '渲染报告', percent: 80 },
  saving: { label: '保存中', percent: 90 },
  report_completed: { label: '完成', percent: 100 },
  report_failed: { label: '失败', percent: 0 },
};

const REPORT_TERMINAL_EVENTS = new Set(['report_completed', 'report_failed']);

interface ReportProgressEntry {
  label: string;
  percent: number;
}

/** runId → task_id，用于断线重连 */
interface ActiveTask {
  runId: string;
  taskId: string;
}

interface ReportProgressState {
  /** runId → 进度条状态 */
  reportProgress: Record<string, ReportProgressEntry>;
  /** 当前活跃的报告生成任务 */
  activeTasks: Record<string, ActiveTask>;
  /** 每个任务独立的 SSE 连接控制器 */
  _sseControllers: Record<string, AbortController>;

  /** 设置某个 run 的进度 */
  setProgress: (runId: string, entry: ReportProgressEntry) => void;
  /** 移除某个 run 的进度（任务完成/失败时调用） */
  removeProgress: (runId: string) => void;
  /** 注册活跃任务并启动 SSE 监听 */
  startReport: (runId: string, taskId: string, onDone?: () => void) => void;
  /** 页面挂载时重连所有活跃任务的 SSE */
  reconnectActive: (onDone?: () => void) => void;
  /** 取消所有 SSE 连接 */
  abortAll: () => void;
  /** 内部：为单个任务建立 SSE 连接 */
  subscribeSSE: (runId: string, taskId: string, onDone?: () => void) => void;
}

export const useReportProgressStore = create<ReportProgressState>((set, get) => ({
  reportProgress: {},
  activeTasks: {},
  _sseControllers: {},

  setProgress: (runId, entry) =>
    set((s) => ({ reportProgress: { ...s.reportProgress, [runId]: entry } })),

  removeProgress: (runId) =>
    set((s) => {
      const next = { ...s.reportProgress };
      delete next[runId];
      const nextTasks = { ...s.activeTasks };
      delete nextTasks[runId];
      const nextControllers = { ...s._sseControllers };
      nextControllers[runId]?.abort();
      delete nextControllers[runId];
      return { reportProgress: next, activeTasks: nextTasks, _sseControllers: nextControllers };
    }),

  startReport: (runId, taskId, onDone) => {
    set((s) => ({
      activeTasks: { ...s.activeTasks, [runId]: { runId, taskId } },
      reportProgress: { ...s.reportProgress, [runId]: { label: '开始生成', percent: 5 } },
    }));
    get().subscribeSSE(runId, taskId, onDone);
  },

  reconnectActive: (onDone) => {
    const { activeTasks } = get();
    const entries = Object.values(activeTasks);
    if (entries.length === 0) return;
    for (const { runId, taskId } of entries) {
      get().subscribeSSE(runId, taskId, onDone);
    }
  },

  abortAll: () => {
    const { _sseControllers } = get();
    Object.values(_sseControllers).forEach((c) => c.abort());
    set({ _sseControllers: {} });
  },

  subscribeSSE: (runId, taskId, onDone) => {
    // 先取消该任务的旧连接（如有），再创建新的
    const existing = get()._sseControllers[runId];
    if (existing) existing.abort();
    const controller = new AbortController();
    set((s) => ({ _sseControllers: { ...s._sseControllers, [runId]: controller } }));

    createSSEConnection(
      `/api/v1/rag/eval/reports/generation/${taskId}/stream`,
      controller.signal,
      {
        onOpen: () => {},
        onMessage: (raw: string) => {
          try {
            const event = JSON.parse(raw);
            if (event.type === 'heartbeat') return;
            const stage = REPORT_STAGE_MAP[event.type];
            if (stage) {
              get().setProgress(runId, stage);
            }
            if (REPORT_TERMINAL_EVENTS.has(event.type)) {
              get().removeProgress(runId);
              onDone?.();
            }
          } catch {
            // ignore
          }
        },
        onError: () => {
          get().removeProgress(runId);
        },
      },
    );
  },
}));
