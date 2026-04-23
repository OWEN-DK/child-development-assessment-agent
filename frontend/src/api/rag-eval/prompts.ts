/**
 * 提示词管理 API 客户端
 */

import apiClient from '@shared/api/client';

export interface PromptMetadata {
  id: string;
  prompt_key: string;
  name_zh: string;
  purpose: string;
  category: string;
  subcategory?: string;
  is_active: boolean;
  is_system: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface PromptVersion {
  id: string;
  prompt_key: string;
  version_label: string;
  version_number: number;
  content: string;
  variables_extracted?: string[];
  change_impact?: Record<string, any>;
  change_summary?: string;
  created_at?: string;
  created_by?: string;
}

export interface PromptDetail {
  metadata: PromptMetadata;
  current_version?: PromptVersion;
  versions: PromptVersion[];
}

export interface ImpactAnalysis {
  code_references: Array<{ file: string; line: number; function?: string }>;
  variable_changes: {
    added: string[];
    removed: string[];
    modified: string[];
  };
  config_dependencies: Array<{
    param: string;
    category: string;
    description: string;
    current_value?: string;
  }>;
  affected_files: string[];
  risk_level: 'low' | 'medium' | 'high';
}

export interface PromptTestResult {
  rendered_prompt: string;
  variables_used: string[];
  variables_missing: string[];
}

export interface PromptComparison {
  version_1: PromptVersion;
  version_2: PromptVersion;
  diff: {
    added_chars: number;
    version_1_length: number;
    version_2_length: number;
  };
}

/**
 * 获取提示词列表
 */
export const getPromptList = async (
  category?: string,
  isActive?: boolean
): Promise<{ items: PromptMetadata[]; total: number }> => {
  const params: Record<string, any> = {};
  if (category) params.category = category;
  if (isActive !== undefined) params.is_active = isActive;

  const response = await apiClient.get('/api/v1/rag/prompts', { params });
  return response.data;
};

/**
 * 获取提示词详情
 */
export const getPromptDetail = async (promptKey: string): Promise<PromptDetail> => {
  const response = await apiClient.get(`/api/v1/rag/prompts/${promptKey}`);
  return response.data;
};

/**
 * 更新提示词
 */
export const updatePrompt = async (
  promptKey: string,
  data: {
    content: string;
    change_summary?: string;
    created_by?: string;
  }
): Promise<{ message: string; version: string; impact: ImpactAnalysis }> => {
  const response = await apiClient.post(`/api/v1/rag/prompts/${promptKey}/update`, data);
  return response.data;
};

/**
 * 分析提示词影响
 */
export const analyzePromptImpact = async (
  promptKey: string,
  content: string
): Promise<ImpactAnalysis> => {
  const response = await apiClient.post(`/api/v1/rag/prompts/${promptKey}/analyze`, {
    content,
  });
  return response.data;
};

/**
 * 测试提示词渲染
 */
export const testPrompt = async (
  promptKey: string,
  variables: Record<string, any>,
  version?: string
): Promise<PromptTestResult> => {
  const response = await apiClient.post('/api/v1/rag/prompts/test', {
    prompt_key: promptKey,
    version,
    variables,
  });
  return response.data;
};

/**
 * 对比提示词版本
 */
export const comparePromptVersions = async (
  promptKey: string,
  version1: string,
  version2: string
): Promise<PromptComparison> => {
  const response = await apiClient.get(`/api/v1/rag/prompts/${promptKey}/compare`, {
    params: { version_1: version1, version_2: version2 },
  });
  return response.data;
};
