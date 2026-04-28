/** 三层指标与六层诊断 API */

import { apiClient } from './client';
import type { RunMetrics, DiagnosisResult } from '@entities/rag-eval';

/** 获取运行的三层指标 */
export async function getRunMetrics(runId: string): Promise<RunMetrics> {
  const res = await apiClient.get<RunMetrics>(`/api/v1/rag/eval/runs/${runId}/metrics`);
  return res.data;
}

/** 获取运行的六层诊断结果 */
export async function getRunDiagnosis(runId: string): Promise<DiagnosisResult> {
  const res = await apiClient.get<DiagnosisResult>(`/api/v1/rag/eval/runs/${runId}/diagnosis`);
  return res.data;
}

/** 触发运行评估计算 */
export async function triggerEvaluation(runId: string): Promise<{ message: string }> {
  const res = await apiClient.post<{ message: string }>(`/api/v1/rag/eval/runs/${runId}/evaluate`);
  return res.data;
}
