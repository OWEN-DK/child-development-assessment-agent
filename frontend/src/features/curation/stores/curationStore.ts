import { create } from 'zustand';
import type {
  CurationBook,
  DraftDetail,
  EntityItem,
  KGData,
  PendingItem,
} from '../types';
import { curationApi } from '../api/curationApi';

interface CurationState {
  /* ===== 书籍 ===== */
  books: CurationBook[];
  booksLoading: boolean;
  loadBooks: () => Promise<void>;

  /* ===== 草稿 ===== */
  currentDraft: DraftDetail | null;
  draftContent: string;
  draftLoading: boolean;
  draftSaving: boolean;
  loadDraft: (bookId: string) => Promise<void>;
  setDraftContent: (content: string) => void;
  saveDraft: () => Promise<void>;
  markReviewed: () => Promise<void>;
  publishToNeo4j: () => Promise<void>;

  /* ===== 实体 ===== */
  entities: EntityItem[];
  confirmedEntities: Set<string>;
  activeEntity: string | null;
  setActiveEntity: (name: string | null) => void;
  toggleConfirm: (name: string) => void;

  /* ===== 图谱 ===== */
  kgData: KGData | null;
  kgLoading: boolean;
  kgError: string;
  loadGraph: (bookId?: string) => Promise<void>;

  /* ===== 队列 ===== */
  pendingItems: PendingItem[];
  pendingLoading: boolean;
  loadPendingQueue: (params?: { status?: string; book_id?: string }) => Promise<void>;

  /* ===== 生成 ===== */
  generating: boolean;
  generateProgress: number;
  generateStatus: 'idle' | 'generating' | 'completed' | 'failed';
  generateError: string;
  generateBookTitle: string;
  generateChapters: { title: string; status: 'pending' | 'generating' | 'completed' | 'failed' }[];
  generatePhase: string;
  generatePhaseLabel: string;
  startGeneration: (bookId: string) => Promise<void>;
  resumeGeneration: (bookId: string) => void;
  _connectSSE: (bookId: string, onNotFound?: () => void) => void;
  cancelGeneration: (bookId: string) => Promise<void>;
}

export const useCurationStore = create<CurationState>((set, get) => ({
  /* ===== 书籍 ===== */
  books: [],
  booksLoading: false,
  loadBooks: async () => {
    set({ booksLoading: true });
    try {
      const res = await curationApi.listBooks({ page: 1, page_size: 100 });
      set({ books: res.books || [] });
    } catch {
      // handled by caller
    } finally {
      set({ booksLoading: false });
    }
  },

  /* ===== 草稿 ===== */
  currentDraft: null,
  draftContent: '',
  draftLoading: false,
  draftSaving: false,
  loadDraft: async (bookId: string) => {
    set({ draftLoading: true });
    try {
      const res = await curationApi.listDrafts({ book_id: bookId });
      if (res.drafts && res.drafts.length > 0) {
        const detail = await curationApi.getDraft(res.drafts[0].id);
        set({ currentDraft: detail, draftContent: detail.content || '' });
      } else {
        set({ currentDraft: null, draftContent: '' });
      }
    } catch {
      set({ currentDraft: null, draftContent: '' });
    } finally {
      set({ draftLoading: false });
    }
  },
  setDraftContent: (content: string) => set({ draftContent: content }),
  saveDraft: async () => {
    const { currentDraft, draftContent } = get();
    if (!currentDraft) return;
    set({ draftSaving: true });
    try {
      await curationApi.updateDraft(currentDraft.id, draftContent);
    } finally {
      set({ draftSaving: false });
    }
  },
  markReviewed: async () => {
    const { currentDraft } = get();
    if (!currentDraft) return;
    await curationApi.markReviewed(currentDraft.id, 'admin');
    // reload
    const detail = await curationApi.getDraft(currentDraft.id);
    set({ currentDraft: detail, draftContent: detail.content || '' });
  },
  publishToNeo4j: async () => {
    const { currentDraft } = get();
    if (!currentDraft) return;
    await curationApi.publishToNeo4j(currentDraft.id);
    const detail = await curationApi.getDraft(currentDraft.id);
    set({ currentDraft: detail, draftContent: detail.content || '' });
  },

  /* ===== 实体 ===== */
  entities: [],
  confirmedEntities: new Set<string>(),
  activeEntity: null,
  setActiveEntity: (name) => set({ activeEntity: name }),
  toggleConfirm: (name) => {
    const { confirmedEntities } = get();
    const next = new Set(confirmedEntities);
    if (next.has(name)) next.delete(name);
    else next.add(name);
    set({ confirmedEntities: next });
  },

  /* ===== 图谱 ===== */
  kgData: null,
  kgLoading: false,
  kgError: '',
  loadGraph: async (bookId?: string) => {
    set({ kgLoading: true, kgError: '' });
    try {
      const data = await curationApi.getGraph(bookId);
      set({ kgData: data, kgError: '' });
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e?.message || '加载图谱数据失败';
      set({ kgData: null, kgError: msg });
    } finally {
      set({ kgLoading: false });
    }
  },

  /* ===== 队列 ===== */
  pendingItems: [],
  pendingLoading: false,
  loadPendingQueue: async (params) => {
    set({ pendingLoading: true });
    try {
      const res = await curationApi.getPendingQueue(params);
      set({ pendingItems: res.items || [] });
    } catch {
      // handled by caller
    } finally {
      set({ pendingLoading: false });
    }
  },

  /* ===== 生成 ===== */
  generating: false,
  generateProgress: 0,
  generateStatus: 'idle',
  generateError: '',
  generateBookTitle: '',
  generateChapters: [],
  generatePhase: '',
  generatePhaseLabel: '',
  /** 内部：建立 SSE 连接，绑定消息/错误处理 */
  _connectSSE: (bookId: string, onNotFound?: () => void) => {
    const url = curationApi.getGenerationProgressUrl(bookId);
    const eventSource = new EventSource(url);

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        // 如果后端返回未找到，执行回调（用于判断是否需要启动生成）
        if (data.status === 'not_found') {
          eventSource.close();
          onNotFound?.();
          return;
        }
        const updates: any = { generating: true };
        if (data.progress !== undefined) updates.generateProgress = data.progress;
        if (data.book_title) updates.generateBookTitle = data.book_title;
        if (data.chapters && Array.isArray(data.chapters)) updates.generateChapters = data.chapters;
        if (data.phase !== undefined) updates.generatePhase = data.phase;
        if (data.phase_label !== undefined) updates.generatePhaseLabel = data.phase_label;
        if (data.status === 'generating') {
          updates.generateStatus = 'generating';
        }
        if (data.status === 'completed') {
          updates.generateStatus = 'completed';
          updates.generating = false;
          updates.generateProgress = 100;
          eventSource.close();
          get().loadDraft(bookId);
        }
        if (data.status === 'failed') {
          updates.generateStatus = 'failed';
          updates.generateError = data.error || '生成失败';
          updates.generating = false;
          eventSource.close();
        }
        set(updates);
      } catch { /* ignore */ }
    };

    eventSource.onerror = () => {
      eventSource.close();
      if (get().generating) {
        const { generateProgress } = get();
        if (generateProgress >= 100) {
          set({ generateStatus: 'completed', generating: false });
        } else {
          set({ generateStatus: 'failed', generateError: 'SSE 连接中断，生成可能未完成', generating: false });
        }
      }
    };
  },

  /** 页面挂载时恢复已有任务的 SSE 连接（不清空已有进度） */
  resumeGeneration: (bookId: string) => {
    get()._connectSSE(bookId, () => {
      // SSE 返回 not_found，说明没有运行中的任务，重置为 idle
      set({ generating: false, generateStatus: 'idle' });
    });
  },

  /** 启动新生成任务并连接 SSE */
  startGeneration: async (bookId: string) => {
    set({ generating: true, generateProgress: 0, generateStatus: 'generating', generateError: '', generateBookTitle: '', generateChapters: [], generatePhase: '', generatePhaseLabel: '' });

    try {
      await curationApi.startGeneration(bookId);
    } catch {
      set({ generateStatus: 'failed', generateError: '启动生成失败', generating: false });
      return;
    }

    get()._connectSSE(bookId);
  },
  cancelGeneration: async (bookId: string) => {
    try {
      await curationApi.cancelGeneration(bookId);
    } catch {
      // ignore cancel errors
    }
    const { generating } = get();
    if (generating) {
      set({ generating: false, generateStatus: 'failed', generateError: '用户取消' });
    }
  },
}));
