/**
 * 管道 API 客户端
 *
 * 提供管道 CRUD、版本管理、校验、干运行等 API 调用
 */
import apiClient from '@/shared/api/client'
import type {
  PipelineListItem,
  PipelineDetail,
  PipelineCreate,
  PipelineUpdate,
  PipelineImport,
  PipelineSaveRequest,
  PipelineVersion,
  ValidationResult,
  DryRunResult,
  VersionCompareResult,
  CompoundNodeRead,
  CompoundNodeConfig,
} from '@/entities/pipeline/types'

// ==================== 管道 CRUD ====================

/** 获取管道列表 */
export async function getPipelines(params?: {
  page?: number
  pageSize?: number
  status?: string
  keyword?: string
}): Promise<{ items: PipelineListItem[]; total: number }> {
  const response = await apiClient.get('/pipelines', { params })
  return response.data
}

/** 获取管道详情 */
export async function getPipeline(id: string): Promise<PipelineDetail> {
  const response = await apiClient.get(`/pipelines/${id}`)
  return response.data
}

/** 创建管道 */
export async function createPipeline(data: PipelineCreate): Promise<PipelineDetail> {
  const response = await apiClient.post('/pipelines', data)
  return response.data
}

/** 更新管道 */
export async function updatePipeline(id: string, data: PipelineUpdate): Promise<PipelineDetail> {
  const response = await apiClient.put(`/pipelines/${id}`, data)
  return response.data
}

/** 删除管道 */
export async function deletePipeline(id: string): Promise<void> {
  await apiClient.delete(`/pipelines/${id}`)
}

/** 导入管道 */
export async function importPipeline(data: PipelineImport): Promise<PipelineDetail> {
  const response = await apiClient.post('/pipelines/import', data)
  return response.data
}

// ==================== 版本管理 ====================

/** 获取版本历史 */
export async function getVersions(pipelineId: string): Promise<PipelineVersion[]> {
  const response = await apiClient.get(`/pipelines/${pipelineId}/versions`)
  return response.data
}

/** 获取指定版本 */
export async function getVersion(pipelineId: string, version: number): Promise<PipelineDetail> {
  const response = await apiClient.get(`/pipelines/${pipelineId}/versions/${version}`)
  return response.data
}

/** 回滚到指定版本 */
export async function rollbackVersion(pipelineId: string, version: number): Promise<PipelineDetail> {
  const response = await apiClient.post(`/pipelines/${pipelineId}/versions/${version}/rollback`)
  return response.data
}

/** 对比两个版本 */
export async function compareVersions(
  pipelineId: string,
  v1: number,
  v2: number
): Promise<VersionCompareResult> {
  const response = await apiClient.get(`/pipelines/${pipelineId}/versions/compare`, {
    params: { v1, v2 },
  })
  return response.data
}

// ==================== 保存（自动自增版本） ====================

/** 保存管道（自动自增版本） */
export async function savePipeline(
  id: string,
  data: PipelineSaveRequest
): Promise<PipelineDetail> {
  const response = await apiClient.put(`/pipelines/${id}/save`, data)
  return response.data
}

// ==================== 校验与干运行 ====================

/** 校验管道配置 */
export async function validatePipeline(
  id: string,
  config: unknown
): Promise<ValidationResult> {
  const response = await apiClient.post(`/pipelines/${id}/validate`, { config })
  return response.data
}

/** 干运行管道 */
export async function dryRunPipeline(
  id: string,
  config: unknown,
  input: { query: string; params?: Record<string, unknown> }
): Promise<DryRunResult> {
  const response = await apiClient.post(`/pipelines/${id}/dry-run`, { config, ...input })
  return response.data
}

// ==================== 复合节点 ====================

/** 获取复合节点库 */
export async function getCompoundNodes(): Promise<CompoundNodeRead[]> {
  const response = await apiClient.get('/compound-nodes')
  return response.data
}

/** 创建复合节点 */
export async function createCompoundNode(data: CompoundNodeConfig): Promise<CompoundNodeRead> {
  const response = await apiClient.post('/compound-nodes', data)
  return response.data
}

/** 删除复合节点 */
export async function deleteCompoundNode(id: string): Promise<void> {
  await apiClient.delete(`/compound-nodes/${id}`)
}

/** 导入复合节点 */
export async function importCompoundNode(data: CompoundNodeConfig): Promise<CompoundNodeRead> {
  const response = await apiClient.post('/compound-nodes/import', data)
  return response.data
}

/** 导出复合节点 */
export async function exportCompoundNode(id: string): Promise<CompoundNodeConfig> {
  const response = await apiClient.get(`/compound-nodes/${id}/export`)
  return response.data
}
