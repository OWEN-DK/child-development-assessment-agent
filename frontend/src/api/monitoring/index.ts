import { apiClient } from '../client';
import type { MonitoringStatistics, MonitoringTrend, ModelDistribution } from './types';

export const monitoringApi = {
  getStatistics: async (days: number, modelFilter?: string): Promise<MonitoringStatistics> => {
    const params = new URLSearchParams();
    params.append('days', days.toString());
    if (modelFilter) params.append('model', modelFilter);
    
    const res = await apiClient.get(`/api/v1/monitoring/statistics?${params.toString()}`);
    return res.data;
  },
  
  getTrend: async (days: number, type: 'calls' | 'tokens' | 'duration'): Promise<MonitoringTrend> => {
    const res = await apiClient.get(`/api/v1/monitoring/trend?days=${days}&type=${type}`);
    return res.data;
  },
  
  getModelDistribution: async (days: number): Promise<ModelDistribution> => {
    const res = await apiClient.get(`/api/v1/monitoring/model-distribution?days=${days}`);
    return res.data;
  },
};