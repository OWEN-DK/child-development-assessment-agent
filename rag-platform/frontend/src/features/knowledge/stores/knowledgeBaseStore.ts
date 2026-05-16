/**
 * 知识库状态管理
 *
 * 管理知识库列表、详情、文档、分块配置、权限等全部状态
 */
import { create } from 'zustand'
import type {
  KnowledgeBaseListItem,
  KnowledgeBaseDetail,
  KnowledgeBaseStatus,
  KnowledgeBaseVisibility,
  VectorBackend,
  KBDocument,
  ChunkPreviewItem,
  ChunkStrategyConfig,
  EmbeddingConfig,
  DocAclEntry,
  RebuildTask,
  UploadProgressItem,
} from '@/entities/knowledge/types'
import * as kbApi from '@/api/knowledge/knowledge-base'

/** 详情页激活的选项卡 */
export type DetailTab = 'documents' | 'chunks' | 'permissions' | 'settings'

/** 知识库状态 */
interface KnowledgeBaseState {
  // ── 列表状态 ──
  knowledgeBases: KnowledgeBaseListItem[]
  total: number
  loading: boolean
  error: string | null

  // 列表筛选
  searchQuery: string
  backendFilter: VectorBackend | 'all'
  statusFilter: KnowledgeBaseStatus | 'all'
  visibilityFilter: KnowledgeBaseVisibility | 'all'
  page: number
  pageSize: number

  // ── 详情页状态 ──
  currentKB: KnowledgeBaseDetail | null
  detailLoading: boolean
  detailError: string | null
  activeTab: DetailTab

  // 文档列表
  documents: KBDocument[]
  documentsTotal: number
  documentsLoading: boolean
  documentsPage: number
  documentsPageSize: number
  documentSearch: string
  documentFileTypeFilter: string

  // 上传进度
  uploadProgress: UploadProgressItem[]

  // 分块预览
  selectedDocumentId: string | null
  chunkPreview: ChunkPreviewItem[]
  chunkPreviewLoading: boolean
  chunkTotalCount: number

  // ── 权限 Tab ──
  docAcls: DocAclEntry[]
  aclLoading: boolean

  // ── 配置状态 ──
  configDirty: boolean

  // 重建
  rebuildStatus: RebuildTask | null
  recentRebuildTasks: RebuildTask[]
  rebuildCleanup: (() => void) | null

  // ── 操作方法 ──
  loadKnowledgeBases: () => Promise<void>
  loadKnowledgeBase: (id: string) => Promise<void>
  createKnowledgeBase: (data: Parameters<typeof kbApi.createKnowledgeBase>[0]) => Promise<KnowledgeBaseDetail>
  deleteKnowledgeBase: (id: string) => Promise<void>
  updateKnowledgeBaseInfo: (id: string, data: { name?: string; description?: string }) => Promise<void>

  // 列表筛选方法
  setSearchQuery: (query: string) => void
  setBackendFilter: (filter: VectorBackend | 'all') => void
  setStatusFilter: (filter: KnowledgeBaseStatus | 'all') => void
  setVisibilityFilter: (filter: KnowledgeBaseVisibility | 'all') => void
  setPage: (page: number) => void

  // 详情页方法
  setActiveTab: (tab: DetailTab) => void
  clearCurrentKB: () => void

  // 文档方法
  loadDocuments: (kbId: string) => Promise<void>
  setDocumentSearch: (search: string) => void
  setDocumentFileTypeFilter: (filter: string) => void
  setDocumentsPage: (page: number) => void
  uploadDocuments: (kbId: string, files: File[]) => Promise<void>
  deleteDocument: (kbId: string, docId: string) => Promise<void>
  batchDeleteDocuments: (kbId: string, docIds: string[]) => Promise<void>
  reparseDocument: (kbId: string, docId: string) => Promise<void>

  // 分块预览
  previewChunks: (kbId: string, docId: string) => Promise<void>
  clearChunkPreview: () => void

  // 配置方法
  updateChunkStrategy: (kbId: string, strategy: ChunkStrategyConfig) => Promise<void>
  updateEmbeddingConfig: (kbId: string, config: EmbeddingConfig) => Promise<void>
  setConfigDirty: (dirty: boolean) => void

  // 权限方法
  loadDocAcls: (kbId: string) => Promise<void>
  updateVisibility: (kbId: string, visibility: KnowledgeBaseVisibility) => Promise<void>
  updateVisibleRoles: (kbId: string, roles: string[]) => Promise<void>
  updateDocAcl: (kbId: string, docId: string, acl: { access_level: string; doc_acl: string[] | null }) => Promise<void>

  // 重建进度
  subscribeRebuildProgress: (kbId: string) => (() => void) | null
  clearRebuildStatus: () => void
}

export const useKnowledgeBaseStore = create<KnowledgeBaseState>((set, get) => ({
  // ── 初始状态 ──
  knowledgeBases: [],
  total: 0,
  loading: false,
  error: null,
  searchQuery: '',
  backendFilter: 'all',
  statusFilter: 'all',
  visibilityFilter: 'all',
  page: 1,
  pageSize: 20,

  currentKB: null,
  detailLoading: false,
  detailError: null,
  activeTab: 'documents',

  documents: [],
  documentsTotal: 0,
  documentsLoading: false,
  documentsPage: 1,
  documentsPageSize: 20,
  documentSearch: '',
  documentFileTypeFilter: '',

  uploadProgress: [],

  selectedDocumentId: null,
  chunkPreview: [],
  chunkPreviewLoading: false,
  chunkTotalCount: 0,

  docAcls: [],
  aclLoading: false,

  configDirty: false,
  rebuildStatus: null,
  recentRebuildTasks: [],
  rebuildCleanup: null,

  // ── 列表操作 ──

  loadKnowledgeBases: async () => {
    const state = get()
    set({ loading: true, error: null })
    try {
      const result = await kbApi.getKnowledgeBases({
        search: state.searchQuery || undefined,
        backend: state.backendFilter !== 'all' ? state.backendFilter : undefined,
        status: state.statusFilter !== 'all' ? state.statusFilter : undefined,
        visibility: state.visibilityFilter !== 'all' ? state.visibilityFilter : undefined,
        page: state.page,
        page_size: state.pageSize,
      })
      set({
        knowledgeBases: result.items,
        total: result.total,
        loading: false,
      })
    } catch (error) {
      set({
        loading: false,
        error: error instanceof Error ? error.message : '加载失败',
      })
    }
  },

  loadKnowledgeBase: async (id) => {
    set({ detailLoading: true, detailError: null })
    try {
      const detail = await kbApi.getKnowledgeBase(id)
      set({ currentKB: detail, detailLoading: false })
    } catch (error) {
      set({
        detailLoading: false,
        detailError: error instanceof Error ? error.message : '加载失败',
      })
    }
  },

  createKnowledgeBase: async (data) => {
    const detail = await kbApi.createKnowledgeBase(data)
    // 创建后刷新列表
    get().loadKnowledgeBases()
    return detail
  },

  deleteKnowledgeBase: async (id) => {
    await kbApi.deleteKnowledgeBase(id)
    set((state) => ({
      knowledgeBases: state.knowledgeBases.filter((kb) => kb.id !== id),
      total: state.total - 1,
    }))
  },

  updateKnowledgeBaseInfo: async (id, data) => {
    const updated = await kbApi.updateKnowledgeBase(id, data)
    set((state) => ({
      currentKB: state.currentKB?.id === id ? updated : state.currentKB,
    }))
  },

  // ── 筛选方法 ──

  setSearchQuery: (query) => {
    set({ searchQuery: query, page: 1 })
    get().loadKnowledgeBases()
  },

  setBackendFilter: (filter) => {
    set({ backendFilter: filter, page: 1 })
    get().loadKnowledgeBases()
  },

  setStatusFilter: (filter) => {
    set({ statusFilter: filter, page: 1 })
    get().loadKnowledgeBases()
  },

  setVisibilityFilter: (filter) => {
    set({ visibilityFilter: filter, page: 1 })
    get().loadKnowledgeBases()
  },

  setPage: (page) => {
    set({ page })
    get().loadKnowledgeBases()
  },

  // ── 详情页 ──

  setActiveTab: (tab) => set({ activeTab: tab }),

  clearCurrentKB: () => {
    const cleanup = get().rebuildCleanup
    cleanup?.()
    set({
      currentKB: null,
      detailError: null,
      documents: [],
      documentsTotal: 0,
      uploadProgress: [],
      chunkPreview: [],
      selectedDocumentId: null,
      docAcls: [],
      rebuildStatus: null,
      recentRebuildTasks: [],
      rebuildCleanup: null,
      configDirty: false,
    })
  },

  // ── 文档操作 ──

  loadDocuments: async (kbId) => {
    const state = get()
    set({ documentsLoading: true })
    try {
      const result = await kbApi.getDocuments(kbId, {
        search: state.documentSearch || undefined,
        file_type: state.documentFileTypeFilter || undefined,
        page: state.documentsPage,
        page_size: state.documentsPageSize,
      })
      set({
        documents: result.items,
        documentsTotal: result.total,
        documentsLoading: false,
      })
    } catch {
      set({ documentsLoading: false })
    }
  },

  setDocumentSearch: (search) => {
    set({ documentSearch: search, documentsPage: 1 })
  },

  setDocumentFileTypeFilter: (filter) => {
    set({ documentFileTypeFilter: filter, documentsPage: 1 })
  },

  setDocumentsPage: (page) => {
    set({ documentsPage: page })
  },

  uploadDocuments: async (kbId, files) => {
    const progressItems: UploadProgressItem[] = files.map((file) => ({
      file,
      percentage: 0,
      status: 'pending' as const,
    }))
    set({ uploadProgress: progressItems })

    try {
      // 标记全部为上传中
      set({
        uploadProgress: progressItems.map((p) => ({ ...p, status: 'uploading' as const })),
      })

      const result = await kbApi.uploadDocuments(kbId, files, (progressEvent) => {
        // 整体进度更新
        const pct = progressEvent.total
          ? Math.round((progressEvent.loaded / progressEvent.total) * 100)
          : 0
        set((state) => ({
          uploadProgress: state.uploadProgress.map((p) => ({
            ...p,
            percentage: pct,
          })),
        }))
      })

      // 更新每个文件的状态
      const updatedProgress = progressItems.map((item) => {
        const created = result.created.find((d) => d.filename === item.file.name)
        const duplicate = result.duplicates.find((d) => d.filename === item.file.name)
        const errored = result.errors.find((e) => e.filename === item.file.name)

        if (created) {
          return { ...item, status: 'done' as const, percentage: 100, documentId: created.id }
        }
        if (duplicate) {
          return { ...item, status: 'duplicate' as const, percentage: 100, documentId: duplicate.id }
        }
        if (errored) {
          return { ...item, status: 'error' as const, errorMessage: errored.error }
        }
        return { ...item, status: 'done' as const, percentage: 100 }
      })

      set({ uploadProgress: updatedProgress })
      // 上传完成后刷新文档列表
      get().loadDocuments(kbId)
    } catch (error) {
      set((state) => ({
        uploadProgress: state.uploadProgress.map((p) => ({
          ...p,
          status: 'error' as const,
          errorMessage: error instanceof Error ? error.message : '上传失败',
        })),
      }))
    }
  },

  deleteDocument: async (kbId, docId) => {
    await kbApi.deleteDocument(kbId, docId)
    set((state) => ({
      documents: state.documents.filter((d) => d.id !== docId),
      documentsTotal: state.documentsTotal - 1,
    }))
  },

  batchDeleteDocuments: async (kbId, docIds) => {
    await kbApi.batchDeleteDocuments(kbId, docIds)
    set((state) => ({
      documents: state.documents.filter((d) => !docIds.includes(d.id)),
      documentsTotal: state.documentsTotal - docIds.length,
    }))
  },

  reparseDocument: async (kbId, docId) => {
    await kbApi.reparseDocument(kbId, docId)
    get().loadDocuments(kbId)
  },

  // ── 分块预览 ──

  previewChunks: async (kbId, docId) => {
    set({ chunkPreviewLoading: true, selectedDocumentId: docId })
    try {
      const result = await kbApi.previewChunks(kbId, docId)
      set({
        chunkPreview: result.preview,
        chunkTotalCount: result.total_chunks,
        chunkPreviewLoading: false,
      })
    } catch {
      set({ chunkPreviewLoading: false })
    }
  },

  clearChunkPreview: () => {
    set({ chunkPreview: [], selectedDocumentId: null, chunkTotalCount: 0 })
  },

  // ── 配置操作 ──

  updateChunkStrategy: async (kbId, strategy) => {
    set({ configDirty: false })
    await kbApi.updateChunkStrategy(kbId, strategy)
    // 触发后更新重建状态
    const status = await kbApi.getRebuildStatus(kbId)
    set({
      rebuildStatus: status.current_task,
      recentRebuildTasks: status.recent_tasks,
    })
    // 先清理旧 SSE 连接，再订阅新的
    get().rebuildCleanup?.()
    const cleanup = get().subscribeRebuildProgress(kbId)
    set({ rebuildCleanup: cleanup })
  },

  updateEmbeddingConfig: async (kbId, config) => {
    set({ configDirty: false })
    await kbApi.updateEmbeddingConfig(kbId, config)
    const status = await kbApi.getRebuildStatus(kbId)
    set({
      rebuildStatus: status.current_task,
      recentRebuildTasks: status.recent_tasks,
    })
    get().rebuildCleanup?.()
    const cleanup = get().subscribeRebuildProgress(kbId)
    set({ rebuildCleanup: cleanup })
  },

  setConfigDirty: (dirty) => set({ configDirty: dirty }),

  // ── 权限操作 ──

  loadDocAcls: async (kbId) => {
    set({ aclLoading: true })
    try {
      const docList = await kbApi.getDocuments(kbId, { page: 1, page_size: 200 })
      const acls: DocAclEntry[] = docList.items.map((doc) => ({
        doc_id: doc.id,
        filename: doc.filename,
        access_level: doc.access_level,
        doc_acl: null,
      }))
      set({ docAcls: acls, aclLoading: false })
    } catch {
      set({ aclLoading: false })
    }
  },

  updateVisibility: async (kbId, visibility) => {
    const updated = await kbApi.updateKnowledgeBase(kbId, { visibility })
    set((state) => ({
      currentKB: state.currentKB?.id === kbId ? updated : state.currentKB,
    }))
  },

  updateVisibleRoles: async (kbId, roles) => {
    const updated = await kbApi.updateKnowledgeBase(kbId, { visible_roles: roles })
    set((state) => ({
      currentKB: state.currentKB?.id === kbId ? updated : state.currentKB,
    }))
  },

  updateDocAcl: async (kbId, docId, acl) => {
    await kbApi.updateDocumentAcl(kbId, docId, {
      access_level: acl.access_level as 'inherit' | 'restricted',
      doc_acl: acl.doc_acl,
    })
    set((state) => ({
      docAcls: state.docAcls.map((entry) =>
        entry.doc_id === docId
          ? { ...entry, access_level: acl.access_level as 'inherit' | 'restricted', doc_acl: acl.doc_acl }
          : entry
      ),
    }))
  },

  // ── 重建进度 ──

  subscribeRebuildProgress: (kbId) => {
    const unsubscribe = kbApi.subscribeRebuildProgress(
      kbId,
      (event) => {
        set((state) => ({
          rebuildStatus: state.rebuildStatus
            ? {
                ...state.rebuildStatus,
                progress_pct: event.progress_pct,
                progress_message: event.progress_message,
                status: event.status,
              }
            : null,
        }))
        if (event.event === 'complete') {
          // 重建完成，刷新详情
          get().loadKnowledgeBase(kbId)
          get().clearRebuildStatus()
        } else if (event.event === 'error') {
          get().loadKnowledgeBase(kbId)
        }
      },
      () => {
        // SSE 异常时尝试刷新状态
        kbApi.getRebuildStatus(kbId).then((status) => {
          set({
            rebuildStatus: status.current_task,
            recentRebuildTasks: status.recent_tasks,
          })
        })
      }
    )
    // 存储 unsubscribe 以便后续清理
    return unsubscribe
  },

  clearRebuildStatus: () => set({ rebuildStatus: null }),
}))
