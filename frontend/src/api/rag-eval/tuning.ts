/** 调优建议与配置版本 API */

import { apiClient } from './client';
import type { TuningSuggestion } from '@entities/rag-eval';

/** 获取运行的调优建议列表 */
export async function getTuningSuggestions(runId: string): Promise<TuningSuggestion[]> {
  const res = await apiClient.get<TuningSuggestion[]>(`/api/v1/rag/eval/runs/${runId}/suggestions`);
  return res.data;
}

/** 采纳调优建议 */
export async function adoptSuggestion(id: string): Promise<TuningSuggestion> {
  const res = await apiClient.post<TuningSuggestion>(`/api/v1/rag/eval/suggestions/${id}/adopt`);
  return res.data;
}

/** 驳回调优建议 */
export async function rejectSuggestion(
  id: string,
  reason?: string,
): Promise<TuningSuggestion> {
  const res = await apiClient.post<TuningSuggestion>(`/api/v1/rag/eval/suggestions/${id}/reject`, { reason });
  return res.data;
}

/** 忽略调优建议 */
export async function ignoreSuggestion(id: string): Promise<TuningSuggestion> {
  const res = await apiClient.post<TuningSuggestion>(`/api/v1/rag/eval/suggestions/${id}/ignore`);
  return res.data;
}

/** 获取配置版本列表 */
export async function getConfigVersions(): Promise<{ id: string; version: string; created_at: string; description: string | null }[]> {
  const res = await apiClient.get<{ items: { id: string; version: string; created_at: string; description: string | null }[] }>('/api/v1/rag/eval/config/versions');
  return res.data.items;
}

/** 回滚到指定配置版本 */
export async function rollbackConfigVersion(versionId: string): Promise<{ version_id: string }> {
  const res = await apiClient.post<{ version_id: string }>('/api/v1/rag/eval/config/rollback', { version_id: versionId });
  return res.data;
}
