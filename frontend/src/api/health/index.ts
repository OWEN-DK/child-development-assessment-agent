import apiClient from '../client';

export interface HealthResponse {
  status: 'healthy' | 'degraded';
  llm_configured: boolean;
  missing_vars: string[];
}

export async function checkHealth(): Promise<HealthResponse> {
  const { data } = await apiClient.get<HealthResponse>('/health/');
  return data;
}
