/** 知识库快照 API */

import { apiClient } from './client';
import type { KnowledgeSnapshot } from '@entities/rag-eval';

/** 获取快照列表 */
export async function getSnapshots(): Promise<KnowledgeSnapshot[]> {
  const res = await apiClient.get<KnowledgeSnapshot[]>('/api/v1/rag/eval/snapshots');
  return res.data;
}

/** 创建快照 */
export async function createSnapshot(data: {
  name: string;
  description?: string;
  config_version_id?: string;
}): Promise<KnowledgeSnapshot> {
  const res = await apiClient.post<KnowledgeSnapshot>('/api/v1/rag/eval/snapshots', data);
  return res.data;
}

/** 获取单个快照 */
export async function getSnapshot(id: string): Promise<KnowledgeSnapshot> {
  const res = await apiClient.get<KnowledgeSnapshot>(`/api/v1/rag/eval/snapshots/${id}`);
  return res.data;
}

/** 恢复快照 */
export async function restoreSnapshot(id: string): Promise<{ message: string }> {
  const res = await apiClient.post<{ message: string }>(`/api/v1/rag/eval/snapshots/${id}/restore`);
  return res.data;
}
