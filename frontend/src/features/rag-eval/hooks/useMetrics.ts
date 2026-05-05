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

/** 触发评估计算（异步，轮询等待完成后刷新） */
export function useTriggerEvaluation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (runId: string) => metricsApi.triggerEvaluation(runId),
    onMutate: async (runId) => {
      // 乐观更新：将该 run 的状态改为 running
      await qc.cancelQueries({ queryKey: ['rag-eval', 'runs'] });
      const queries = qc.getQueriesData<any>({ queryKey: ['rag-eval', 'runs'] });
      for (const [key, data] of queries) {
        if (!data?.items) continue;
        qc.setQueryData(key, {
          ...data,
          items: data.items.map((r: any) =>
            r.id === runId ? { ...r, status: 'running' } : r,
          ),
        });
      }
      return { queries };
    },
    onError: (_err, _runId, context) => {
      // 回滚乐观更新
      if (context?.queries) {
        for (const [key, data] of context.queries) {
          qc.setQueryData(key, data);
        }
      }
    },
    onSuccess: (_data, runId) => {
      // 轮询指标，等待后台评估完成
      const poll = setInterval(async () => {
        try {
          const metrics = await metricsApi.getRunMetrics(runId);
          if (metrics?.overall_score != null && metrics.overall_score > 0) {
            clearInterval(poll);
            qc.invalidateQueries({ queryKey: ['rag-eval', 'metrics', runId] });
            qc.invalidateQueries({ queryKey: ['rag-eval', 'diagnosis', runId] });
            qc.invalidateQueries({ queryKey: ['rag-eval', 'runs'] });
          }
        } catch {
          // 忽略轮询错误
        }
      }, 3000);
      // 最多轮询 2 分钟
      setTimeout(() => clearInterval(poll), 120_000);
    },
  });
}
