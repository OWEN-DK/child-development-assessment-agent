import { create } from 'zustand';
import type {
  CurationBook,
  DraftDetail,
  EntityItem,
  KGData,
  PendingItem,
} from '../types';
import { curationApi } from '../api/curationApi';
import { createSSEConnection } from '../../rag-eval/utils/sse';
import { API_BASE_URL } from '@shared/lib/constants';

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
  loadGraph: (bookId?: string, limit?: number) => Promise<void>;

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
  _sseController: AbortController | null;
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
  loadGraph: async (bookId?: string, limit?: number) => {
    set({ kgLoading: true, kgError: '' });
    try {
      const data = await curationApi.getGraph(bookId, limit);
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
  _sseController: null,
  generating: false,
  generateProgress: 0,
  generateStatus: 'idle',
  generateError: '',
  generateBookTitle: '',
  generateChapters: [],
  generatePhase: '',
  generatePhaseLabel: '',
  /** 内部：建立 SSE 连接（fetch-based，与知识问答/上传相同的机制） */
  _connectSSE: (bookId: string, onNotFound?: () => void) => {
    // 先断开旧连接
    if (get()._sseController) {
      get()._sseController!.abort();
      set({ _sseController: null });
    }

    const controller = new AbortController();
    set({ _sseController: controller });

    const base = API_BASE_URL.replace(/\/$/, '');
    const url = `${base}/api/v2/curation/books/${bookId}/generate/progress`;

    createSSEConnection(url, controller.signal, {
      onOpen: () => {},
      onMessage: (raw) => {
        try {
          const data = JSON.parse(raw);

          // 忽略 SSEPublisher 系统事件
          if (data.type === 'connected' || data.type === 'heartbeat') return;

          // not_found → 通知调用方
          if (data.status === 'not_found') {
            controller.abort();
            set({ _sseController: null });
            onNotFound?.();
            return;
          }

          const updates: Record<string, unknown> = {};
          if (data.progress !== undefined) updates.generateProgress = data.progress;
          if (data.book_title) updates.generateBookTitle = data.book_title;
          if (data.chapters && Array.isArray(data.chapters)) updates.generateChapters = data.chapters;
          if (data.phase !== undefined) updates.generatePhase = data.phase;
          if (data.phase_label !== undefined) updates.generatePhaseLabel = data.phase_label;

          if (data.status === 'generating') {
            updates.generating = true;
            updates.generateStatus = 'generating';
          } else if (data.status === 'completed') {
            updates.generating = false;
            updates.generateStatus = 'completed';
            updates.generateProgress = 100;
            set(updates);
            controller.abort();
            set({ _sseController: null });
            get().loadDraft(bookId);
            return;
          } else if (data.status === 'failed') {
            updates.generating = false;
            updates.generateStatus = 'failed';
            updates.generateError = data.error || '生成失败';
            set(updates);
            controller.abort();
            set({ _sseController: null });
            return;
          }

          if (Object.keys(updates).length > 0) {
            set(updates);
          }
        } catch { /* ignore parse errors */ }
      },
      onError: () => {
        if (!get().generating) return;
        const { generateProgress } = get();
        if (generateProgress >= 100) {
          set({ generateStatus: 'completed', generating: false });
        } else {
          set({ generateStatus: 'failed', generateError: 'SSE 连接中断，生成可能未完成', generating: false });
        }
        set({ _sseController: null });
      },
    });
  },

  /** 页面挂载时恢复已有任务的 SSE 连接（不清空已有进度） */
  resumeGeneration: (bookId: string) => {
    // 先断开旧连接并重置状态
    if (get()._sseController) {
      get()._sseController!.abort();
    }
    set({ generating: false, generateStatus: 'idle', generateProgress: 0, generateError: '', generateBookTitle: '', generateChapters: [], generatePhase: '', generatePhaseLabel: '', _sseController: null });
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
    // 断开 SSE 连接
    if (get()._sseController) {
      get()._sseController!.abort();
      set({ _sseController: null });
    }
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
