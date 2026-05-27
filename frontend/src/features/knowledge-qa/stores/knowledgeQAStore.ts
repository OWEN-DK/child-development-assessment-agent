import { create } from 'zustand';
import type {
  KnowledgeQAResponse,
  ProgressState,
  QAStatus,
  SectionOutput,
} from '../types';

interface KnowledgeQAStore {
  status: QAStatus;
  taskId: string | null;
  progress: ProgressState | null;
  result: KnowledgeQAResponse | null;
  /** 流式过程中增量收集已完成节（按 index 排序） */
  completedSections: SectionOutput[];
  error: string | null;
  viewMode: 'markdown' | 'json';

  setStatus: (status: QAStatus) => void;
  setTaskId: (taskId: string) => void;
  setProgress: (progress: ProgressState) => void;
  setResult: (result: KnowledgeQAResponse) => void;
  /** 增量追加已完成节，自动按 index 去重排序 */
  addSection: (section: SectionOutput) => void;
  setError: (error: string) => void;
  setViewMode: (mode: 'markdown' | 'json') => void;
  reset: () => void;
}

export const useKnowledgeQAStore = create<KnowledgeQAStore>((set) => ({
  status: 'idle',
  taskId: null,
  progress: null,
  result: null,
  completedSections: [],
  error: null,
  viewMode: 'markdown',

  setStatus: (status) => set({ status }),
  setTaskId: (taskId) => set({ taskId }),
  setProgress: (progress) => set({ progress }),
  setResult: (result) => set({ result, completedSections: result.sections, status: 'done' }),
  addSection: (section) =>
    set((state) => {
      const existing = state.completedSections.filter(
        (s) => s.index !== section.index,
      );
      const updated = [...existing, section].sort((a, b) => a.index - b.index);
      return { completedSections: updated };
    }),
  setError: (error) => set({ error, status: 'error' }),
  setViewMode: (viewMode) => set({ viewMode }),
  reset: () =>
    set({
      status: 'idle',
      taskId: null,
      progress: null,
      result: null,
      completedSections: [],
      error: null,
      viewMode: 'markdown',
    }),
}));
