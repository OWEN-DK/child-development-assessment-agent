import apiClient from '@shared/api/client';
import {
  ConfigResponse,
  ConfigVersion,
  ConfigUpdateRequest,
  ConfigUpdateResponse,
  ConfigResetRequest,
  HealthDiagnosticRequest,
  HealthDiagnosticResponse,
} from './types';

export const configApi = {
  getConfig: async (): Promise<ConfigResponse> => {
    const res = await apiClient.get<ConfigResponse>('/api/v1/config/current');
    return res.data;
  },

  updateConfig: async (
    request: ConfigUpdateRequest
  ): Promise<ConfigUpdateResponse> => {
    const res = await apiClient.post<ConfigUpdateResponse>('/api/v1/config/save', {
      config_snapshot: request.config_snapshot,
      description: request.description
    });
    return res.data;
  },

  listVersions: async (limit = 50): Promise<ConfigVersion[]> => {
    const res = await apiClient.get<{ items: ConfigVersion[] }>(`/api/v1/config/versions?limit=${limit}`);
    return res.data.items;
  },

  rollbackToVersion: async (versionId: string): Promise<{ version_id: string }> => {
    const res = await apiClient.post('/api/v1/config/rollback', { version_id: versionId });
    return res.data;
  },

  resetToFactory: async (request: ConfigResetRequest): Promise<{ message: string }> => {
    const res = await apiClient.post('/api/v1/config/reset', {
      confirm: request.confirm,
      reason: request.reason
    });
    return res.data;
  },

  runHealthDiagnostic: async (
    request: HealthDiagnosticRequest
  ): Promise<HealthDiagnosticResponse> => {
    const res = await apiClient.post<HealthDiagnosticResponse>('/api/v1/config/health', {
      config: request.config
    });
    return res.data;
  },
};
