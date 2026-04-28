/** 草稿管理 API */

import { apiClient } from './client';
import type {
  TestCaseDraft,
  SourceDocument,
  PaginatedResponse,
  DraftGenerationConfig,
} from '@entities/rag-eval';

/* ==================== 草稿 CRUD ==================== */

/** 获取草稿列表 */
export async function getDrafts(params?: {
  page?: number;
  page_size?: number;
  domain?: string;
  status?: string;
  document_id?: string;
}): Promise<PaginatedResponse<TestCaseDraft>> {
  const res = await apiClient.get<PaginatedResponse<TestCaseDraft>>('/api/v1/rag/eval/drafts', { params });
  return res.data;
}

/** 获取单个草稿 */
export async function getDraft(id: string): Promise<TestCaseDraft> {
  const res = await apiClient.get<TestCaseDraft>(`/api/v1/rag/eval/drafts/${id}`);
  return res.data;
}

/** 更新草稿 */
export async function updateDraft(
  id: string,
  data: Partial<Pick<TestCaseDraft, 'query' | 'age' | 'domain' | 'description' | 'difficulty_level' | 'expected_knowledge_ids' | 'expected_keywords' | 'answer_points' | 'professional_terms'>>,
): Promise<TestCaseDraft> {
  const res = await apiClient.put<TestCaseDraft>(`/api/v1/rag/eval/drafts/${id}`, data);
  return res.data;
}

/** 审核草稿（通过/驳回） */
export async function reviewDraft(
  id: string,
  action: 'approve' | 'reject',
  comment?: string,
): Promise<TestCaseDraft> {
  const res = await apiClient.post<TestCaseDraft>(`/api/v1/rag/eval/drafts/${id}/review`, { action, comment });
  return res.data;
}

/** 启动草稿批量生成 */
export async function startGeneration(
  documentId: string,
  config?: DraftGenerationConfig,
): Promise<{ batch_id: string }> {
  const res = await apiClient.post<{ batch_id: string }>('/api/v1/rag/eval/drafts/generate', {
    document_id: documentId,
    config,
  });
  return res.data;
}

/** 批量删除草稿 */
export async function deleteDrafts(ids: string[]): Promise<void> {
  await apiClient.delete('/api/v1/rag/eval/drafts/batch', { data: { draft_ids: ids } });
}

/* ==================== 源文档 ==================== */

/** 获取源文档列表 */
export async function getSourceDocuments(params?: {
  page?: number;
  page_size?: number;
  status?: string;
}): Promise<PaginatedResponse<SourceDocument>> {
  const res = await apiClient.get<PaginatedResponse<SourceDocument>>('/api/v1/rag/eval/source-documents', { params });
  return res.data;
}

/** 获取单个源文档 */
export async function getSourceDocument(id: string): Promise<SourceDocument> {
  const res = await apiClient.get<SourceDocument>(`/api/v1/rag/eval/source-documents/${id}`);
  return res.data;
}

/** 删除源文档 */
export async function deleteSourceDocument(id: string): Promise<void> {
  await apiClient.delete(`/api/v1/rag/eval/source-documents/${id}`);
}
