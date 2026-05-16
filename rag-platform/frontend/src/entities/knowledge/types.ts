/**
 * 知识库实体类型定义
 *
 * 对齐后端 schemas/knowledge/ 下的 Pydantic 模型
 */

// ==================== 枚举类型 ====================

/** 向量后端类型 */
export type VectorBackend = 'chroma' | 'elasticsearch' | 'milvus'

/** 知识库状态 */
export type KnowledgeBaseStatus = 'ready' | 'rebuilding' | 'indexing' | 'error'

/** 知识库可见性 */
export type KnowledgeBaseVisibility = 'public' | 'role_scoped' | 'private'

/** 分块策略类型 */
export type ChunkType = 'fixed_size' | 'semantic' | 'paragraph' | 'heading' | 'recursive'

/** 相似度度量 */
export type SimilarityMetric = 'cosine' | 'euclidean' | 'dot_product'

/** 文档解析状态 */
export type ParseStatus = 'pending' | 'parsing' | 'parsed' | 'error'

/** 文档权限级别 */
export type DocAccessLevel = 'inherit' | 'restricted'

/** 重建触发原因 */
export type RebuildTrigger = 'chunk_change' | 'embedding_change' | 'backend_migration'

/** 重建任务状态 */
export type RebuildTaskStatus = 'running' | 'completed' | 'failed'

/** 迁移状态 */
export type MigrationStatusEnum = 'pending' | 'running' | 'completed' | 'failed' | 'rolled_back'

// ==================== 分块策略 ====================

/** 分块策略配置 */
export interface ChunkStrategyConfig {
  type: ChunkType
  chunk_size: number
  overlap: number
  separator: string
  min_chunk_size: number
  max_chunk_size: number
}

// ==================== Embedding 配置 ====================

/** Embedding 模型配置 */
export interface EmbeddingConfig {
  model: string
  provider: string
  dimension: number
  batch_size: number
  similarity_metric: SimilarityMetric
}

// ==================== 知识库 ====================

/** 知识库列表项 */
export interface KnowledgeBaseListItem {
  id: string
  name: string
  description: string | null
  vector_backend: VectorBackend
  visibility: KnowledgeBaseVisibility
  status: KnowledgeBaseStatus
  document_count: number
  chunk_count: number
  storage_size_bytes: number
  created_at: string
  updated_at: string
}

/** 知识库详情 */
export interface KnowledgeBaseDetail {
  id: string
  tenant_id: string
  name: string
  description: string | null
  vector_backend: VectorBackend
  chunk_strategy: ChunkStrategyConfig | null
  embedding_config: EmbeddingConfig | null
  visibility: KnowledgeBaseVisibility
  visible_roles: string[] | null
  owner_id: string
  status: KnowledgeBaseStatus
  document_count: number
  chunk_count: number
  storage_size_bytes: number
  created_at: string
  updated_at: string
}

/** 知识库列表响应 */
export interface KnowledgeBaseListResponse {
  items: KnowledgeBaseListItem[]
  total: number
}

/** 创建知识库请求 */
export interface CreateKBRequest {
  name: string
  description?: string
  vector_backend: VectorBackend
  chunk_strategy?: ChunkStrategyConfig
  embedding_config?: EmbeddingConfig
  visibility: KnowledgeBaseVisibility
  visible_roles?: string[]
}

/** 更新知识库请求 */
export interface UpdateKBRequest {
  name?: string
  description?: string
  visibility?: KnowledgeBaseVisibility
  visible_roles?: string[]
}

// ==================== 文档 ====================

/** 文档摘要（列表项） */
export interface KBDocument {
  id: string
  kb_id: string
  filename: string
  file_type: string
  file_size: number
  page_count: number | null
  md5_hash: string
  parse_status: ParseStatus
  error_message: string | null
  access_level: DocAccessLevel
  owner_id: string
  chunk_count: number
  uploaded_at: string
}

/** 文档详情 */
export interface KBDocumentDetail {
  id: string
  kb_id: string
  tenant_id: string
  filename: string
  file_type: string
  file_size: number
  page_count: number | null
  md5_hash: string
  parse_status: ParseStatus
  error_message: string | null
  text_content: string | null
  metadata: Record<string, unknown> | null
  access_level: DocAccessLevel
  doc_acl: string[] | null
  owner_id: string
  chunk_count: number
  uploaded_at: string
  chunk_preview: ChunkPreviewItem[]
}

/** 文档列表响应 */
export interface DocumentListResponse {
  items: KBDocument[]
  total: number
}

/** 批量上传结果 */
export interface BatchUploadResult {
  created: KBDocument[]
  duplicates: KBDocument[]
  errors: Array<{ filename: string; error: string }>
  total_uploaded: number
  total_duplicates: number
  total_errors: number
}

// ==================== 分块 ====================

/** 分块预览项 */
export interface ChunkPreviewItem {
  chunk_index: number
  content: string
  char_count: number
  token_estimate: number
  metadata: Record<string, unknown> | null
}

/** 分块预览结果 */
export interface ChunkPreviewResult {
  total_chunks: number
  preview: ChunkPreviewItem[]
  strategy_config: Record<string, unknown>
}

// ==================== 重建 ====================

/** 重建任务摘要 */
export interface RebuildTask {
  id: string
  kb_id: string
  trigger: RebuildTrigger
  status: RebuildTaskStatus
  progress_pct: number
  progress_message: string | null
  started_at: string
  completed_at: string | null
  error_message: string | null
}

/** 重建状态响应 */
export interface RebuildStatusResponse {
  kb_id: string
  current_task: RebuildTask | null
  recent_tasks: RebuildTask[]
}

/** 重建进度 SSE 事件 */
export interface RebuildProgressEvent {
  event: 'progress' | 'complete' | 'error'
  task_id: string
  kb_id: string
  progress_pct: number
  progress_message: string
  status: RebuildTaskStatus
}

/** 重建触发响应 */
export interface RebuildTriggeredResponse {
  rebuild_task_id: string
  kb_id: string
  trigger: string
  status: string
}

// ==================== 迁移 ====================

/** 迁移请求 */
export interface MigrationRequest {
  target_backend: VectorBackend
}

/** 迁移预估 */
export interface MigrationEstimate {
  source_backend: VectorBackend
  target_backend: VectorBackend
  document_count: number
  chunk_count: number
  estimated_minutes: number
  warnings: string[]
}

// ==================== 删除检查 ====================

/** 管道引用 */
export interface PipelineReference {
  pipeline_id: string
  pipeline_name: string
  version_number: number
}

/** 知识库删除冲突 */
export interface KbDeletionConflict {
  message: string
  pipelines: PipelineReference[]
}

// ==================== 文档 ACL ====================

/** 文档 ACL 条目 */
export interface DocAclEntry {
  doc_id: string
  filename: string
  access_level: DocAccessLevel
  doc_acl: string[] | null
}

/** 更新文档 ACL 请求 */
export interface UpdateDocAclRequest {
  access_level: DocAccessLevel
  doc_acl: string[] | null
}

// ==================== 上传进度（前端本地状态） ====================

/** 上传进度项 */
export interface UploadProgressItem {
  file: File
  percentage: number
  status: 'pending' | 'uploading' | 'parsing' | 'done' | 'duplicate' | 'error'
  errorMessage?: string
  documentId?: string
}

// ==================== 筛选参数 ====================

/** 知识库列表筛选参数 */
export interface KBListParams {
  search?: string
  backend?: VectorBackend | 'all'
  status?: KnowledgeBaseStatus | 'all'
  visibility?: KnowledgeBaseVisibility | 'all'
  page?: number
  page_size?: number
}

/** 文档列表筛选参数 */
export interface DocListParams {
  search?: string
  file_type?: string
  parse_status?: ParseStatus
  page?: number
  page_size?: number
}
