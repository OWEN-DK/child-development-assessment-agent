import { apiClient } from '../client';
import {
  ConfigResponse,
  ConfigVersion,
  ConfigUpdateRequest,
  ConfigUpdateResponse,
} from './types';

export const configApi = {
  getConfig: async (): Promise<ConfigResponse> => {
    return apiClient.get('/api/v1/config/current').then((r) => r.data);
  },

  updateConfig: async (
    request: ConfigUpdateRequest
  ): Promise<ConfigUpdateResponse> => {
    return apiClient.post('/api/v1/config/save', {
      config_snapshot: request.config,
      description: request.description
    }).then((r) => r.data);
  },

  listVersions: async (limit = 50): Promise<ConfigVersion[]> => {
    return apiClient.get(`/api/v1/config/versions?limit=${limit}`).then((r) => r.data);
  },

  rollbackToVersion: async (versionId: string): Promise<any> => {
    return apiClient.post(`/api/v1/config/rollback`, {
      version_id: versionId
    }).then((r) => r.data);
  },

  resetToFactory: async (): Promise<any> => {
    return apiClient.post('/api/v1/config/reset').then((r) => r.data);
  },
};
