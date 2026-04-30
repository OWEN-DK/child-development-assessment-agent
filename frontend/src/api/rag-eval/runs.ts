/** 测试运行 API */

import { apiClient } from './client';
import type { TestRun, TestRunResult, RunComparison, PaginatedResponse } from '@entities/rag-eval';

/* ==================== 运行 CRUD ==================== */

/** 获取运行列表 */
export async function getRuns(params?: {
  page?: number;
  page_size?: number;
  status?: string;
}): Promise<PaginatedResponse<TestRun>> {
  const res = await apiClient.get<PaginatedResponse<TestRun>>('/api/v1/rag/eval/runs', { params });
  return res.data;
}

/** 创建运行 */
export async function createRun(data: {
  name: string;
  description?: string;
  test_set_ids?: string[];
  custom_case_ids?: string[];
  snapshot_id?: string;
  config_version_id?: string;
}): Promise<TestRun> {
  const res = await apiClient.post<TestRun>('/api/v1/rag/eval/runs', data);
  return res.data;
}

/** 获取单个运行 */
export async function getRun(id: string): Promise<TestRun> {
  const res = await apiClient.get<TestRun>(`/api/v1/rag/eval/runs/${id}`);
  return res.data;
}

/** 执行运行（启动后台任务） */
export async function executeRun(id: string): Promise<{ task_id: string }> {
  const res = await apiClient.post<{ task_id: string }>(`/api/v1/rag/eval/runs/${id}/execute`);
  return res.data;
}

/** 删除运行 */
export async function deleteRun(id: string): Promise<void> {
  await apiClient.delete(`/api/v1/rag/eval/runs/${id}`);
}

/** 批量删除运行 */
export async function batchDeleteRuns(ids: string[]): Promise<void> {
  await apiClient.delete('/api/v1/rag/eval/runs', { data: { ids } });
}

/** 单条用例执行 */
export async function executeSingleCase(runId: string, caseId: string): Promise<TestRunResult> {
  const res = await apiClient.post<TestRunResult>(`/api/v1/rag/eval/runs/${runId}/execute/${caseId}`);
  return res.data;
}

/** 获取运行 SSE 进度流的 URL（由调用方通过 fetch SSE 连接） */
export function getRunStreamUrl(runId: string): string {
  return `${apiClient.defaults.baseURL}/api/v1/rag/eval/runs/${runId}/stream`;
}

/** 对比两次运行 */
export async function compareRuns(runId1: string, runId2: string): Promise<RunComparison> {
  const res = await apiClient.get<RunComparison>('/api/v1/rag/eval/runs/compare', {
    params: { run1: runId1, run2: runId2 },
  });
  return res.data;
}
