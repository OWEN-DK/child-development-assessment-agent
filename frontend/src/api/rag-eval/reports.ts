import apiClient from '@shared/api/client';

export interface ValidationLayerResult {
  layer: number;
  key?: string;
  status: string;
  data: Record<string, unknown>;
  duration_ms?: number;
}

export interface TuningSuggestion {
  id: string;
  report_id: string;
  param_name: string;
  current_value: Record<string, unknown> | null;
  suggested_value: Record<string, unknown> | null;
  action: string | null;
  reason: string | null;
  expected_effect: Record<string, unknown> | null;
  priority: string | null;
  source: string | null;
  safe_range: Record<string, unknown> | null;
  applied: boolean;
  applied_config_version_id: string | null;
  created_at: string | null;
}

export interface ReportDetail {
  id: string;
  run_id: string;
  test_set_id: string;
  config_version_id: string | null;
  status: string;
  overall_score: number | null;
  precision: number | null;
  recall: number | null;
  f1: number | null;
  mrr: number | null;
  ndcg: number | null;
  validation_results: ValidationLayerResult[] | null;
  tuning_suggestion_summary: Record<string, unknown> | null;
  created_by: string | null;
  created_at: string | null;
}

export interface SuggestionStats {
  total: number;
  pending: number;
  applied: number;
  ignored: number;
}

export interface ReportCompareResult {
  report_1: { id: string; created_at: string | null; config_version_id: string | null };
  report_2: { id: string; created_at: string | null; config_version_id: string | null };
  metrics_diff: Record<string, { report_1: number | null; report_2: number | null; delta: number }>;
  config_diff: Record<string, { report_1: unknown; report_2: unknown }>;
  suggestions_diff: { report_1_count: number; report_2_count: number };
}

export const getReportByRunId = async (runId: string): Promise<ReportDetail> => {
  const response = await apiClient.get<ReportDetail>(`/api/v1/rag/test/reports/by-run/${runId}`);
  return response.data;
};

export const getReport = async (reportId: string): Promise<ReportDetail> => {
  const response = await apiClient.get<ReportDetail>(`/api/v1/rag/test/reports/${reportId}`);
  return response.data;
};

export const getValidationLayer = async (reportId: string, layer: string): Promise<ValidationLayerResult> => {
  const response = await apiClient.get<ValidationLayerResult>(
    `/api/v1/rag/test/reports/${reportId}/validation/${layer}`
  );
  return response.data;
};

export const compareReports = async (reportId1: string, reportId2: string): Promise<ReportCompareResult> => {
  const response = await apiClient.get<ReportCompareResult>(
    `/api/v1/rag/test/reports/compare?report_id_1=${reportId1}&report_id_2=${reportId2}`
  );
  return response.data;
};

export const getSuggestions = async (reportId: string, status?: string): Promise<TuningSuggestion[]> => {
  const params = status ? `?status=${status}` : '';
  const response = await apiClient.get<TuningSuggestion[]>(
    `/api/v1/rag/test/reports/${reportId}/suggestions${params}`
  );
  return response.data;
};

export const getSuggestionStats = async (reportId: string): Promise<SuggestionStats> => {
  const response = await apiClient.get<SuggestionStats>(
    `/api/v1/rag/test/reports/${reportId}/suggestions/stats`
  );
  return response.data;
};

export const updateSuggestion = async (
  suggestionId: string,
  data: { applied: boolean; applied_config_version_id?: string }
): Promise<TuningSuggestion> => {
  const response = await apiClient.patch<TuningSuggestion>(
    `/api/v1/rag/test/suggestions/${suggestionId}`,
    data
  );
  return response.data;
};

export const batchUpdateSuggestions = async (
  ids: string[],
  data: { applied: boolean; applied_config_version_id?: string }
): Promise<{ updated_count: number }> => {
  const response = await apiClient.post<{ updated_count: number }>(
    `/api/v1/rag/test/suggestions/batch-update`,
    { ids, ...data }
  );
  return response.data;
};
