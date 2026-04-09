import { apiClient } from '../client';
import {
  ConfigResponse,
  ConfigVersion,
  ConfigUpdateRequest,
  ConfigUpdateResponse,
} from './types';

export const configApi = {
  getConfig: async (): Promise<ConfigResponse> => {
    return apiClient.get('/api/v1/config').then((r) => r.data);
  },

  updateConfig: async (
    request: ConfigUpdateRequest
  ): Promise<ConfigUpdateResponse> => {
    return apiClient.put('/api/v1/config', request).then((r) => r.data);
  },

  listVersions: async (limit = 50): Promise<ConfigVersion[]> => {
    return apiClient.get(`/api/v1/config/versions?limit=${limit}`).then((r) => r.data);
  },

  rollbackToVersion: async (versionId: string): Promise<any> => {
    return apiClient.post(`/api/v1/config/rollback/${versionId}`).then((r) => r.data);
  },

  resetToFactory: async (): Promise<any> => {
    return apiClient.post('/api/v1/config/reset').then((r) => r.data);
  },
};
