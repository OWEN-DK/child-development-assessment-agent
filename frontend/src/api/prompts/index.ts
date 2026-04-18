import { apiClient } from '@shared/api/client';

export interface PromptVersion {
  id: string;
  version: string;
  description: string | null;
  created_by: string | null;
  created_at: string;
  variables: string[] | null;
  tags: string[] | null;
}

export interface PromptDetail extends PromptVersion {
  prompt_key: string;
  content: string;
  fallback: string | null;
}

export interface VersionDiff {
  version_1: {
    version: string;
    content: string;
    created_at: string | null;
    description: string | null;
  };
  version_2: {
    version: string;
    content: string;
    created_at: string | null;
    description: string | null;
  };
  diff: {
    added_chars: number;
    version_1_length: number;
    version_2_length: number;
  };
}

export interface ABTest {
  id: string;
  prompt_key: string;
  name: string;
  is_active: boolean;
  variant_a_version: string;
  variant_b_version: string;
  variant_a_ratio: number;
  started_at: string | null;
  ended_at: string | null;
  created_at: string;
}

export interface CreateVersionRequest {
  content: string;
  description?: string;
  created_by?: string;
  variables?: string[];
  tags?: string[];
  fallback?: string;
}

export interface CreateABTestRequest {
  name: string;
  variant_a_version: string;
  variant_b_version: string;
  variant_a_ratio?: number;
}

export const promptsApi = {
  getPrompt: async (
    promptKey: string,
    version?: string,
    abTestId?: string
  ): Promise<{ prompt_key: string; version: string; content: string }> => {
    const params = new URLSearchParams();
    if (version) params.set('version', version);
    if (abTestId) params.set('ab_test_id', abTestId);
    const query = params.toString();
    return apiClient
      .get(`/api/v1/prompts/${promptKey}${query ? `?${query}` : ''}`)
      .then((r) => r.data);
  },

  createVersion: async (
    promptKey: string,
    request: CreateVersionRequest
  ): Promise<{ version: string; message: string }> => {
    return apiClient
      .post(`/api/v1/prompts/${promptKey}/versions`, request)
      .then((r) => r.data);
  },

  listVersions: async (promptKey: string): Promise<PromptVersion[]> => {
    return apiClient
      .get(`/api/v1/prompts/${promptKey}/versions`)
      .then((r) => r.data.versions);
  },

  getVersionDetail: async (
    promptKey: string,
    version: string
  ): Promise<PromptDetail> => {
    return apiClient
      .get(`/api/v1/prompts/${promptKey}/versions/${version}`)
      .then((r) => r.data);
  },

  compareVersions: async (
    promptKey: string,
    version1: string,
    version2: string
  ): Promise<VersionDiff> => {
    return apiClient
      .get(
        `/api/v1/prompts/${promptKey}/compare?version_1=${version1}&version_2=${version2}`
      )
      .then((r) => r.data);
  },

  createABTest: async (
    request: CreateABTestRequest
  ): Promise<{ id: string; message: string }> => {
    return apiClient.post('/api/v1/prompts/ab-tests', request).then((r) => r.data);
  },

  listABTests: async (promptKey?: string): Promise<ABTest[]> => {
    const url = promptKey
      ? `/api/v1/prompts/ab-tests?prompt_key=${promptKey}`
      : '/api/v1/prompts/ab-tests';
    return apiClient.get(url).then((r) => r.data.tests);
  },

  toggleABTest: async (
    testId: string,
    isActive: boolean
  ): Promise<{ message: string }> => {
    return apiClient
      .post(`/api/v1/prompts/ab-tests/${testId}/toggle`, { is_active: isActive })
      .then((r) => r.data);
  },
};
