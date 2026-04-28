import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as metricsApi from '@/api/rag-eval/metrics';

/** 获取某次运行的三层指标得分 */
export function useRunMetrics(runId: string) {
  return useQuery({
    queryKey: ['rag-eval', 'metrics', runId],
    queryFn: () => metricsApi.getRunMetrics(runId),
    staleTime: 60_000,
    enabled: !!runId,
  });
}

/** 获取某次运行的六层诊断结果 */
export function useRunDiagnosis(runId: string) {
  return useQuery({
    queryKey: ['rag-eval', 'diagnosis', runId],
    queryFn: () => metricsApi.getRunDiagnosis(runId),
    staleTime: 60_000,
    enabled: !!runId,
  });
}

/** 触发评估计算（异步，配合 SSE 监听进度） */
export function useTriggerEvaluation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (runId: string) => metricsApi.triggerEvaluation(runId),
    onSuccess: (_data, runId) => {
      qc.invalidateQueries({ queryKey: ['rag-eval', 'metrics', runId] });
      qc.invalidateQueries({ queryKey: ['rag-eval', 'diagnosis', runId] });
      qc.invalidateQueries({ queryKey: ['rag-eval', 'runs'] });
    },
  });
}
