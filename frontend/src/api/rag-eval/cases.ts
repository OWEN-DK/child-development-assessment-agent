/** 测试用例与测试集 API */

import { apiClient } from './client';
import type { TestCase, TestSet, PaginatedResponse } from '@entities/rag-eval';

/* ==================== 测试用例 CRUD ==================== */

/** 获取测试用例列表 */
export async function getTestCases(params?: {
  page?: number;
  page_size?: number;
  difficulty_level?: string;
  source?: string;
  keyword?: string;
}): Promise<PaginatedResponse<TestCase>> {
  const res = await apiClient.get<PaginatedResponse<TestCase>>('/api/v1/rag/eval/test-cases', { params });
  return res.data;
}

/** 获取单个测试用例 */
export async function getTestCase(id: string): Promise<TestCase> {
  const res = await apiClient.get<TestCase>(`/api/v1/rag/eval/test-cases/${id}`);
  return res.data;
}

/** 手动创建测试用例 */
export async function createTestCase(
  data: Pick<TestCase, 'query' | 'expected_knowledge_ids' | 'expected_keywords' | 'difficulty_level'> & Partial<Pick<TestCase, 'description' | 'answer_points_summary' | 'professional_terms'>>,
): Promise<TestCase> {
  const res = await apiClient.post<TestCase>('/api/v1/rag/eval/test-cases', data);
  return res.data;
}

/** 更新测试用例 */
export async function updateTestCase(
  id: string,
  data: Partial<Pick<TestCase, 'query' | 'description' | 'expected_knowledge_ids' | 'expected_keywords' | 'answer_points_summary' | 'difficulty_level' | 'professional_terms'>>,
): Promise<TestCase> {
  const res = await apiClient.put<TestCase>(`/api/v1/rag/eval/test-cases/${id}`, data);
  return res.data;
}

/** 删除单个测试用例 */
export async function deleteTestCase(id: string): Promise<void> {
  await apiClient.delete(`/api/v1/rag/eval/test-cases/${id}`);
}

/** 批量删除测试用例 */
export async function batchDeleteTestCases(ids: string[]): Promise<void> {
  await apiClient.delete('/api/v1/rag/eval/test-cases/batch', { data: { case_ids: ids } });
}

/** 从草稿导入为测试用例 */
export async function importTestCases(draftIds: string[]): Promise<TestCase[]> {
  const res = await apiClient.post<TestCase[]>('/api/v1/rag/eval/test-cases/import', { draft_ids: draftIds });
  return res.data;
}

/* ==================== 测试集 CRUD ==================== */

/** 获取测试集列表 */
export async function getTestSets(): Promise<TestSet[]> {
  const res = await apiClient.get<TestSet[]>('/api/v1/rag/eval/test-sets');
  return res.data;
}

/** 获取单个测试集 */
export async function getTestSet(id: string): Promise<TestSet> {
  const res = await apiClient.get<TestSet>(`/api/v1/rag/eval/test-sets/${id}`);
  return res.data;
}

/** 创建测试集 */
export async function createTestSet(
  data: Pick<TestSet, 'name' | 'description' | 'case_ids'>,
): Promise<TestSet> {
  const res = await apiClient.post<TestSet>('/api/v1/rag/eval/test-sets', data);
  return res.data;
}

/** 更新测试集 */
export async function updateTestSet(
  id: string,
  data: Partial<Pick<TestSet, 'name' | 'description'>>,
): Promise<TestSet> {
  const res = await apiClient.put<TestSet>(`/api/v1/rag/eval/test-sets/${id}`, data);
  return res.data;
}

/** 删除测试集 */
export async function deleteTestSet(id: string): Promise<void> {
  await apiClient.delete(`/api/v1/rag/eval/test-sets/${id}`);
}

/** 向测试集添加用例 */
export async function addCasesToSet(id: string, caseIds: string[]): Promise<TestSet> {
  const res = await apiClient.post<TestSet>(`/api/v1/rag/eval/test-sets/${id}/cases`, { case_ids: caseIds });
  return res.data;
}

/** 从测试集移除用例 */
export async function removeCasesFromSet(id: string, caseIds: string[]): Promise<TestSet> {
  const res = await apiClient.delete(`/api/v1/rag/eval/test-sets/${id}/cases`, { data: { case_ids: caseIds } });
  return res.data;
}

/** 导出测试集 */
export async function exportTestSet(id: string, format: 'json' | 'csv' = 'json'): Promise<Blob> {
  const res = await apiClient.get(`/api/v1/rag/eval/test-sets/${id}/export`, {
    params: { format },
    responseType: 'blob',
  });
  return res.data;
}
