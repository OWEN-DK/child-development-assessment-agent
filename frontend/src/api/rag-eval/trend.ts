/**
 * 趋势数据 API 客户端
 */

import apiClient from '../client';

export interface TrendRun {
  run_id: string;
  value: number;
  started_at: string | null;
}

export interface ConfigChange {
  change_set_id: string;
  change_set_label: string;
  status: string;
  rollback_reason: string | null;
  created_at: string | null;
}

export interface TrendDataPoint {
  version_id: string;
  version_label: string;
  created_at: string | null;
  run_count: number;
  mean: number;
  min: number;
  max: number;
  runs: TrendRun[];
  config_changes: ConfigChange[];
}

export interface TrendResponse {
  status: string;
  test_set_id: string;
  metric: string;
  days: number;
  data: TrendDataPoint[];
}

export interface MultiMetricTrendResponse {
  status: string;
  test_set_id: string;
  metrics: string[];
  days: number;
  data: Record<string, TrendDataPoint[]>;
}

/**
 * 获取单指标趋势数据
 */
export const getTrendData = async (
  testSetId: string,
  metric: string = 'f1',
  days: number = 30
): Promise<TrendResponse> => {
  const response = await apiClient.get<TrendResponse>(
    `/api/v1/rag/test/trends/${testSetId}`,
    { params: { metric, days } }
  );
  return response.data;
};

/**
 * 获取多指标趋势数据
 */
export const getMultiMetricTrend = async (
  testSetId: string,
  metrics: string[] = ['f1', 'precision', 'recall'],
  days: number = 30
): Promise<MultiMetricTrendResponse> => {
  const response = await apiClient.get<MultiMetricTrendResponse>(
    `/api/v1/rag/test/trends/${testSetId}/multi`,
    { params: { metrics: metrics.join(','), days } }
  );
  return response.data;
};
