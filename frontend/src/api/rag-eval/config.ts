/**
 * 配置版本对比与回滚 API 客户端
 */

import apiClient from '../client';

export interface ConfigVersionInfo {
  id: string;
  version_label: string;
  version_number: number;
  created_at: string | null;
}

export interface ConfigDiffItem {
  key: string;
  old_value: unknown;
  new_value: unknown;
}

export interface ConfigDiff {
  added: Record<string, unknown>;
  removed: Record<string, unknown>;
  changed: ConfigDiffItem[];
}

export interface ConfigComparisonResponse {
  from_version: ConfigVersionInfo;
  to_version: ConfigVersionInfo;
  diff: ConfigDiff;
}

export interface ConfigComparisonApiResponse {
  status: string;
  data: ConfigComparisonResponse;
}

export interface RollbackRequest {
  user_id: string;
  reason: string;
}

export interface RollbackResponse {
  new_version_id: string;
  new_version_label: string;
  change_set_id: string;
  change_set_label: string;
}

export interface RollbackApiResponse {
  status: string;
  data: RollbackResponse;
  message: string;
}

/**
 * 对比两个配置版本
 */
export const compareConfigVersions = async (
  fromId: string,
  toId: string
): Promise<ConfigComparisonApiResponse> => {
  const response = await apiClient.get<ConfigComparisonApiResponse>(
    '/api/v1/rag/test/config-versions/compare',
    { params: { from_version: fromId, to_version: toId } }
  );
  return response.data;
};

/**
 * 回滚到指定配置版本
 */
export const rollbackToVersion = async (
  versionId: string,
  reason: string,
  userId: string = 'anonymous'
): Promise<RollbackApiResponse> => {
  const response = await apiClient.post<RollbackApiResponse>(
    `/api/v1/rag/test/config-versions/${versionId}/rollback`,
    { user_id: userId, reason }
  );
  return response.data;
};
