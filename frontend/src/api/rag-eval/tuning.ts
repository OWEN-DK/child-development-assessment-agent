/**
 * 调优建议 API 客户端
 */

import apiClient from '@shared/api/client';
import type { TuningSuggestion, IgnoreSuggestionRequest, IgnoreSuggestionResponse } from '@/features/rag-eval/components/RecommendationPanel/types';
import type { SaveVersionRequest, SaveVersionResponse } from '@/features/rag-eval/components/ReviewPanel/types';
import type { IgnoredSuggestionResponse, RestoreIgnoredSuggestionResponse } from '@/features/rag-eval/components/IgnoredSuggestionsList/types';
import type { ConfigComparison } from '@/features/rag-eval/components/ConfigComparison/types';
import type { PromptComparison } from '@/features/rag-eval/components/PromptComparison/types';

/**
 * 获取报告的调优建议
 */
export const getSuggestions = async (
  reportId: string,
  _testSetId: string
): Promise<TuningSuggestion[]> => {
  const response = await apiClient.get<TuningSuggestion[]>(
    `/api/v1/rag/test/reports/${reportId}/suggestions`
  );
  return response.data;
};

/**
 * 忽略调优建议
 */
export const ignoreSuggestion = async (
  suggestionId: string,
  data: IgnoreSuggestionRequest
): Promise<IgnoreSuggestionResponse> => {
  const response = await apiClient.patch<IgnoreSuggestionResponse>(
    `/api/v1/rag/test/suggestions/${suggestionId}`,
    { applied: false, ...data }
  );
  return response.data;
};

/**
 * 保存采纳建议为新版本
 */
export const saveAdoptedAsVersion = async (
  data: SaveVersionRequest
): Promise<SaveVersionResponse> => {
  const response = await apiClient.post<SaveVersionResponse>(
    '/rag/test/suggestions/save-version',
    data
  );
  return response.data;
};

/**
 * 获取已忽略建议列表
 */
export const getIgnoredSuggestions = async (
  testSetId: string,
  reportId?: string
): Promise<IgnoredSuggestionResponse> => {
  const response = await apiClient.get<IgnoredSuggestionResponse>(
    '/rag/test/ignored-suggestions',
    { params: { test_set_id: testSetId, report_id: reportId } }
  );
  return response.data;
};

/**
 * 恢复已忽略建议
 */
export const restoreIgnoredSuggestion = async (
  id: string
): Promise<RestoreIgnoredSuggestionResponse> => {
  const response = await apiClient.post<RestoreIgnoredSuggestionResponse>(
    `/rag/test/ignored-suggestions/${id}/restore`
  );
  return response.data;
};

/**
 * 删除已忽略建议
 */
export const deleteIgnoredSuggestion = async (
  id: string
): Promise<void> => {
  await apiClient.delete(`/rag/test/ignored-suggestions/${id}`);
};

/**
 * 获取配置对比数据
 */
export const getConfigComparison = async (
  paramName: string,
  currentVersion?: string
): Promise<ConfigComparison> => {
  const response = await apiClient.get<ConfigComparison>(
    `/rag/test/config-comparison/${paramName}`,
    { params: { current_version: currentVersion } }
  );
  return response.data;
};

/**
 * 获取提示词对比数据
 */
export const getPromptComparison = async (
  promptKey: string,
  currentVersion?: string,
  targetVersion?: string
): Promise<PromptComparison> => {
  const response = await apiClient.get<PromptComparison>(
    `/rag/test/prompt-comparison/${promptKey}`,
    { params: { current_version: currentVersion, target_version: targetVersion } }
  );
  return response.data;
};
