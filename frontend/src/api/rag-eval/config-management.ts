/**
 * 配置管理 API 客户端 - Phase 8
 */

import apiClient from '../client';

export interface ConfigMetadata {
  id: string;
  config_key: string;
  name_zh: string;
  description_zh: string;
  category: string;
  value_type: 'string' | 'number' | 'boolean' | 'json';
  min_value?: number;
  max_value?: number;
  recommended_min?: number;
  recommended_max?: number;
  unit?: string;
  affected_components?: string[];
  reload_type: 'hot' | 'cold';
  is_system: boolean;
}

export interface ValidationResult {
  valid: boolean;
  errors: string[];
  warnings: string[];
}

export interface Conflict {
  level: 'error' | 'warning';
  rule: string;
  message: string;
  affected_configs: string[];
}

export interface ConfigGroup {
  name: string;
  key: string;
  description: string;
  configs: ConfigMetadata[];
}

/**
 * 获取配置元数据列表
 */
export const getConfigMetadata = async (
  category?: string
): Promise<{ items: ConfigMetadata[]; total: number }> => {
  const params: Record<string, any> = {};
  if (category) params.category = category;

  const response = await apiClient.get('/rag/config/metadata', { params });
  return response.data;
};

/**
 * 校验配置
 */
export const validateConfig = async (
  configUpdates: Record<string, any>
): Promise<ValidationResult> => {
  const response = await apiClient.post('/rag/config/validate', {
    config_updates: configUpdates,
  });
  return response.data;
};

/**
 * 检测配置冲突
 */
export const detectConfigConflicts = async (
  configUpdates: Record<string, any>,
  currentConfig: Record<string, any>
): Promise<Conflict[]> => {
  const response = await apiClient.post('/rag/config/conflicts', {
    config_updates: configUpdates,
    current_config: currentConfig,
  });
  return response.data;
};

/**
 * 获取配置分组
 */
export const getConfigGroups = async (): Promise<ConfigGroup[]> => {
  const response = await apiClient.get('/rag/config/groups');
  return response.data;
};
