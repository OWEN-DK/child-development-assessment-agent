/** 提示词管理 API */

import { apiClient } from './client';
import type {
  PromptListResponse,
  PromptDetail,
  PromptTestResult,
  PromptComparison,
  ImpactAnalysis,
} from '@entities/rag-eval';

/** 获取提示词列表 */
export async function getPrompts(params?: {
  category?: string;
  is_active?: boolean;
}): Promise<PromptListResponse> {
  const res = await apiClient.get<PromptListResponse>('/api/v1/rag/prompts', { params });
  return res.data;
}

/** 获取提示词详情（含版本列表） */
export async function getPromptDetail(promptKey: string): Promise<PromptDetail> {
  const res = await apiClient.get<PromptDetail>(`/api/v1/rag/prompts/${promptKey}`);
  return res.data;
}

/** 更新提示词（创建新版本） */
export async function updatePrompt(
  promptKey: string,
  data: { content: string; change_summary?: string; created_by?: string },
): Promise<{ message: string; version: string; impact: ImpactAnalysis }> {
  const res = await apiClient.post(`/api/v1/rag/prompts/${promptKey}/update`, data);
  return res.data;
}

/** 分析提示词修改影响（不保存） */
export async function analyzePromptImpact(
  promptKey: string,
  data: { content: string },
): Promise<ImpactAnalysis> {
  const res = await apiClient.post<ImpactAnalysis>(`/api/v1/rag/prompts/${promptKey}/analyze`, data);
  return res.data;
}

/** 测试提示词渲染 */
export async function testPrompt(data: {
  prompt_key: string;
  version?: string;
  variables: Record<string, string>;
}): Promise<PromptTestResult> {
  const res = await apiClient.post<PromptTestResult>('/api/v1/rag/prompts/test', data);
  return res.data;
}

/** 对比两个提示词版本 */
export async function comparePromptVersions(
  promptKey: string,
  version1: string,
  version2: string,
): Promise<PromptComparison> {
  const res = await apiClient.get<PromptComparison>(`/api/v1/rag/prompts/${promptKey}/compare`, {
    params: { version_1: version1, version_2: version2 },
  });
  return res.data;
}
