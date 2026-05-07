/**
 * 运行页面进度全局 store
 *
 * 解决问题：页面切换后运行进度（用例执行 + 报告生成）完全丢失。
 * 将三个 useState 提升到 Zustand store，组件卸载时仅断开 SSE，
 * task 状态保留在 store 中；重挂载时自动重连非终态 run 的 SSE。
 */

import { create } from 'zustand';
import { createSSEConnection } from '../utils/sse';

const TERMINAL_EVENTS = new Set([
  'run_completed', 'run_failed', 'run_cancelled', 'complete', 'error',
  'report_completed', 'report_failed',
]);

interface SseProgress {
  current: number;
  total: number;
}

interface ReportProgress {
  percent: number;
  label: string;
}

interface RunProgressState {
  /** runId → 用例执行进度 */
  sseProgress: Record<string, SseProgress>;
  /** runId → 报告生成进度 */
  reportProgress: Record<string, ReportProgress>;
  /** runId → reportId 映射 */
  reportIdMap: Record<string, string>;
  /** 正在追踪的 runId 集合（用 Record 代替 Set，保证 Zustand shallow equality 正确工作） */
  activeRunIds: Record<string, boolean>;
  /** 每个 run 的 SSE 连接控制器 */
  _sseControllers: Record<string, AbortController>;
  /** 标记组件是否已挂载 */
  _mounted: boolean;

  /** 更新用例执行进度 */
  setSseProgress: (runId: string, progress: SseProgress) => void;
  /** 移除用例执行进度 */
  removeSseProgress: (runId: string) => void;
  /** 更新报告生成进度 */
  setReportProgress: (runId: string, progress: ReportProgress) => void;
  /** 移除报告生成进度 */
  removeReportProgress: (runId: string) => void;
  /** 设置 reportId 映射 */
  setReportId: (runId: string, reportId: string) => void;
  /** 移除 reportId 映射 */
  removeReportId: (runId: string) => void;
  /** 启动 SSE 追踪 */
  startSSE: (runId: string, onRefetch?: () => void) => void;
  /** 停止追踪并清理 */
  stopSSE: (runId: string) => void;
  /** 页面挂载：重连非终态 run 的 SSE */
  onMount: (onRefetch?: () => void) => void;
  /** 页面卸载：断开所有 SSE，保留状态 */
  onUnmount: () => void;
  /** 内部：建立 SSE 连接 */
  _subscribeSSE: (runId: string, onRefetch?: () => void) => void;
}

export const useRunProgressStore = create<RunProgressState>((set, get) => ({
  sseProgress: {},
  reportProgress: {},
  reportIdMap: {},
  activeRunIds: {},
  _sseControllers: {},
  _mounted: false,

  setSseProgress: (runId, progress) =>
    set(s => ({ sseProgress: { ...s.sseProgress, [runId]: progress } })),

  removeSseProgress: (runId) =>
    set(s => {
      const next = { ...s.sseProgress };
      delete next[runId];
      return { sseProgress: next };
    }),

  setReportProgress: (runId, progress) =>
    set(s => ({ reportProgress: { ...s.reportProgress, [runId]: progress } })),

  removeReportProgress: (runId) =>
    set(s => {
      const next = { ...s.reportProgress };
      delete next[runId];
      return { reportProgress: next };
    }),

  setReportId: (runId, reportId) =>
    set(s => ({ reportIdMap: { ...s.reportIdMap, [runId]: reportId } })),

  removeReportId: (runId) =>
    set(s => {
      const next = { ...s.reportIdMap };
      delete next[runId];
      return { reportIdMap: next };
    }),

  startSSE: (runId, onRefetch) => {
    const { activeRunIds } = get();
    if (activeRunIds[runId]) return;
    set({ activeRunIds: { ...activeRunIds, [runId]: true } });
    get()._subscribeSSE(runId, onRefetch);
  },

  stopSSE: (runId) => {
    const { _sseControllers, activeRunIds } = get();
    _sseControllers[runId]?.abort();
    const nextControllers = { ..._sseControllers };
    delete nextControllers[runId];
    const nextActive = { ...activeRunIds };
    delete nextActive[runId];
    set({ _sseControllers: nextControllers, activeRunIds: nextActive });
  },

  onMount: (onRefetch) => {
    set({ _mounted: true });
    const { activeRunIds, sseProgress, reportProgress } = get();
    for (const runId of Object.keys(activeRunIds)) {
      // 只重连仍有进度或报告未完成的 run
      const hasProgress = sseProgress[runId] || reportProgress[runId];
      if (hasProgress) {
        get()._subscribeSSE(runId, onRefetch);
      }
    }
  },

  onUnmount: () => {
    const { _sseControllers } = get();
    Object.values(_sseControllers).forEach(c => c.abort());
    set({ _sseControllers: {}, _mounted: false });
  },

  _subscribeSSE: (runId, onRefetch) => {
    const existing = get()._sseControllers[runId];
    if (existing) existing.abort();

    const controller = new AbortController();
    set(s => ({ _sseControllers: { ...s._sseControllers, [runId]: controller } }));

    createSSEConnection(`/api/v1/rag/eval/runs/${runId}/stream`, controller.signal, {
      onOpen: () => {
        onRefetch?.();
      },
      onMessage: (raw: string) => {
        try {
          const event = JSON.parse(raw);
          if (event.type === 'heartbeat') return;
          const data = event.data;
          const { sseProgress } = get();

          // 用例执行进度
          if (event.type === 'run_started' && data) {
            const total = data.total_cases ?? 0;
            const prev = sseProgress[runId];
            get().setSseProgress(runId, { current: prev?.current ?? 0, total });
            get().removeReportProgress(runId);
            get().removeReportId(runId);
          }

          if ((event.type === 'case_completed' || event.type === 'case_failed') && data) {
            const completedCount = data.completed_count ?? 0;
            const total = data.total ?? sseProgress[runId]?.total ?? 0;
            get().setSseProgress(runId, { current: completedCount, total });
          }

          // 报告生成进度
          if (event.type === 'metrics_computing') {
            get().setReportProgress(runId, { percent: 10, label: '计算指标中...' });
          }
          if (event.type === 'metrics_done') {
            get().setReportProgress(runId, { percent: 40, label: '指标完成' });
          }
          if (event.type === 'report_generating' && data) {
            const stageLabels: Record<string, string> = {
              building: '构建报告数据...', rendering: '渲染报告...', saving: '保存报告...',
            };
            const stagePct: Record<string, number> = { building: 55, rendering: 75, saving: 90 };
            const stage = data.stage ?? '';
            get().setReportProgress(runId, {
              percent: stagePct[stage] ?? 60,
              label: stageLabels[stage] ?? '生成报告中...',
            });
          }
          if (event.type === 'report_completed' && data) {
            get().removeReportProgress(runId);
            if (data.report_id) {
              get().setReportId(runId, data.report_id);
            }
            onRefetch?.();
          }
          if (event.type === 'report_failed') {
            get().removeReportProgress(runId);
            onRefetch?.();
          }

          // 终态事件：清理执行进度
          if (TERMINAL_EVENTS.has(event.type)) {
            get().removeSseProgress(runId);
            onRefetch?.();
          }
        } catch {
          // ignore
        }
      },
      onError: () => {
        if (!get()._mounted) return;
        get().removeSseProgress(runId);
      },
    });
  },
}));
