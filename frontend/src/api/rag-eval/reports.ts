/** 评估报告 API */

import { apiClient } from './client';
import type { EvalReport, TrendData, PaginatedResponse } from '@entities/rag-eval';

/** 获取报告列表 */
export async function getReports(params?: {
  page?: number;
  page_size?: number;
  run_id?: string;
}): Promise<PaginatedResponse<EvalReport>> {
  const res = await apiClient.get<PaginatedResponse<EvalReport>>('/api/v1/rag/eval/reports', { params });
  return res.data;
}

/** 获取单个报告 */
export async function getReport(id: string): Promise<EvalReport> {
  const res = await apiClient.get<EvalReport>(`/api/v1/rag/eval/reports/${id}`);
  return res.data;
}

/** 生成报告 */
export async function generateReport(runId: string): Promise<EvalReport> {
  const res = await apiClient.post<EvalReport>('/api/v1/rag/eval/reports', { run_id: runId });
  return res.data;
}

/** 删除单个报告 */
export async function deleteReport(id: string): Promise<void> {
  await apiClient.delete(`/api/v1/rag/eval/reports/${id}`);
}

/** 批量删除报告 */
export async function batchDeleteReports(ids: string[]): Promise<void> {
  await apiClient.delete('/api/v1/rag/eval/reports/batch', { data: { ids } });
}

/** 导出报告 */
export async function exportReport(
  id: string,
  format: 'json' | 'csv' | 'pdf' = 'json',
): Promise<Blob> {
  const res = await apiClient.get(`/api/v1/rag/eval/reports/${id}/export`, {
    params: { format },
    responseType: 'blob',
  });
  return res.data;
}

/** 获取趋势数据 */
export async function getTrends(params?: {
  test_set_id?: string;
  limit?: number;
}): Promise<TrendData[]> {
  const res = await apiClient.get<TrendData[]>('/api/v1/rag/eval/trends', { params });
  return res.data;
}
