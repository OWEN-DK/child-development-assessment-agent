/**
 * 知识库管理 API 客户端
 *
 * 提供知识库 CRUD、文档管理、分块配置、重建进度等 API 调用
 */
import apiClient from '@/shared/api/client'
import type {
  KnowledgeBaseListResponse,
  KnowledgeBaseDetail,
  CreateKBRequest,
  UpdateKBRequest,
  KBListParams,
  DocumentListResponse,
  KBDocumentDetail,
  BatchUploadResult,
  UpdateDocAclRequest,
  KBDocument,
  ChunkPreviewResult,
  ChunkStrategyConfig,
  EmbeddingConfig,
  RebuildStatusResponse,
  RebuildTriggeredResponse,
  RebuildProgressEvent,
  MigrationEstimate,
  KbDeletionConflict,
  DocListParams,
  VectorBackend,
} from '@/entities/knowledge/types'

// ==================== 知识库 CRUD ====================

/** 获取知识库列表 */
export async function getKnowledgeBases(params?: KBListParams): Promise<KnowledgeBaseListResponse> {
  const response = await apiClient.get('/knowledge-bases', { params })
  return response.data ?? response
}

/** 获取知识库详情 */
export async function getKnowledgeBase(id: string): Promise<KnowledgeBaseDetail> {
  const response = await apiClient.get(`/knowledge-bases/${id}`)
  return response.data ?? response
}

/** 创建知识库 */
export async function createKnowledgeBase(data: CreateKBRequest): Promise<KnowledgeBaseDetail> {
  const response = await apiClient.post('/knowledge-bases', data)
  return response.data ?? response
}

/** 更新知识库信息（名称/描述/可见性） */
export async function updateKnowledgeBase(id: string, data: UpdateKBRequest): Promise<KnowledgeBaseDetail> {
  const response = await apiClient.put(`/knowledge-bases/${id}`, data)
  return response.data ?? response
}

/** 删除知识库（含管道引用检查） */
export async function deleteKnowledgeBase(id: string): Promise<void | KbDeletionConflict> {
  const response = await apiClient.delete(`/knowledge-bases/${id}`)
  return response.data ?? response
}

// ==================== 文档管理 ====================

/** 获取文档列表 */
export async function getDocuments(kbId: string, params?: DocListParams): Promise<DocumentListResponse> {
  const response = await apiClient.get(`/knowledge-bases/${kbId}/documents`, { params })
  return response.data ?? response
}

/** 获取文档详情 */
export async function getDocument(kbId: string, docId: string): Promise<KBDocumentDetail> {
  const response = await apiClient.get(`/knowledge-bases/${kbId}/documents/${docId}`)
  return response.data ?? response
}

/** 上传文档（批量，multipart/form-data） */
export async function uploadDocuments(
  kbId: string,
  files: File[],
  onProgress?: (progressEvent: { loaded: number; total?: number }) => void
): Promise<BatchUploadResult> {
  const formData = new FormData()
  files.forEach((file) => formData.append('files', file))

  const response = await apiClient.post(`/knowledge-bases/${kbId}/documents`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: onProgress as Parameters<typeof apiClient.post>[2] extends { onUploadProgress?: infer T } ? T : never,
  })
  return response.data ?? response
}

/** 删除文档 */
export async function deleteDocument(kbId: string, docId: string): Promise<void> {
  await apiClient.delete(`/knowledge-bases/${kbId}/documents/${docId}`)
}

/** 批量删除文档 */
export async function batchDeleteDocuments(kbId: string, docIds: string[]): Promise<void> {
  await apiClient.post(`/knowledge-bases/${kbId}/documents/batch-delete`, { doc_ids: docIds })
}

/** 重新解析文档 */
export async function reparseDocument(kbId: string, docId: string): Promise<KBDocument> {
  const response = await apiClient.post(`/knowledge-bases/${kbId}/documents/${docId}/reparse`)
  return response.data ?? response
}

/** 更新文档 ACL */
export async function updateDocumentAcl(
  kbId: string,
  docId: string,
  data: UpdateDocAclRequest
): Promise<KBDocument> {
  const response = await apiClient.put(`/knowledge-bases/${kbId}/documents/${docId}/acl`, data)
  return response.data ?? response
}

// ==================== 分块与 Embedding 配置 ====================

/** 更新分块策略 */
export async function updateChunkStrategy(
  kbId: string,
  strategy: ChunkStrategyConfig
): Promise<RebuildTriggeredResponse> {
  const response = await apiClient.put(`/knowledge-bases/${kbId}/chunk-strategy`, {
    chunk_strategy: strategy,
  })
  return response.data ?? response
}

/** 更新 Embedding 配置 */
export async function updateEmbeddingConfig(
  kbId: string,
  config: EmbeddingConfig
): Promise<RebuildTriggeredResponse> {
  const response = await apiClient.put(`/knowledge-bases/${kbId}/embedding-config`, {
    embedding_config: config,
  })
  return response.data ?? response
}

/** 获取分块预览 */
export async function previewChunks(kbId: string, docId: string): Promise<ChunkPreviewResult> {
  const response = await apiClient.get(`/knowledge-bases/${kbId}/chunk-preview`, {
    params: { doc_id: docId },
  })
  return response.data ?? response
}

// ==================== 重建任务 ====================

/** 获取重建状态 */
export async function getRebuildStatus(kbId: string): Promise<RebuildStatusResponse> {
  const response = await apiClient.get(`/knowledge-bases/${kbId}/rebuild/status`)
  return response.data ?? response
}

// ==================== 后端迁移 ====================

/** 获取迁移预估 */
export async function getMigrationEstimate(
  kbId: string,
  target: VectorBackend
): Promise<MigrationEstimate> {
  const response = await apiClient.post(`/knowledge-bases/${kbId}/migrate-backend/estimate`, {
    target_backend: target,
  })
  return response.data ?? response
}

/** 执行后端迁移 */
export async function migrateBackend(kbId: string, target: VectorBackend): Promise<void> {
  await apiClient.post(`/knowledge-bases/${kbId}/migrate-backend`, {
    target_backend: target,
  })
}

// ==================== SSE 订阅 ====================

/** 订阅重建进度 SSE */
export function subscribeRebuildProgress(
  kbId: string,
  onEvent: (event: RebuildProgressEvent) => void,
  onError?: (error: Event) => void
): () => void {
  const token = localStorage.getItem('token')
  const url = `/api/v1/knowledge-bases/${kbId}/rebuild/status/stream${token ? `?token=${token}` : ''}`
  const eventSource = new EventSource(url)

  eventSource.onmessage = (e) => {
    try {
      const data: RebuildProgressEvent = JSON.parse(e.data)
      onEvent(data)
      if (data.event === 'complete' || data.event === 'error') {
        eventSource.close()
      }
    } catch {
      // 忽略解析异常
    }
  }

  eventSource.onerror = (e) => {
    onError?.(e)
    eventSource.close()
  }

  return () => eventSource.close()
}

// ==================== 角色与配置 ====================

/** 获取角色列表（用于权限设置） */
export async function getRoles(): Promise<Array<{ id: string; name: string }>> {
  const response = await apiClient.get('/roles')
  const data = response.data ?? response
  return data.items ?? data
}

/** 获取 Embedding 模型列表 */
export async function getEmbeddingModels(): Promise<
  Array<{ model: string; provider: string; dimension: number }>
> {
  const response = await apiClient.get('/config/embedding-models')
  return response.data ?? response
}
