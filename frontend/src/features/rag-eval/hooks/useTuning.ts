import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as tuningApi from '@/api/rag-eval/tuning';

/** 获取某次运行的调优建议列表 */
export function useTuningSuggestions(runId: string) {
  return useQuery({
    queryKey: ['rag-eval', 'tuning', 'suggestions', runId],
    queryFn: () => tuningApi.getTuningSuggestions(runId),
    staleTime: 60_000,
    enabled: !!runId,
  });
}

/** 采纳调优建议 */
export function useAdoptSuggestion() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (params: { suggestionId: string; runId: string }) =>
      tuningApi.adoptSuggestion(params.suggestionId),
    onSuccess: (_data, params) => {
      qc.invalidateQueries({ queryKey: ['rag-eval', 'tuning', 'suggestions', params.runId] });
      qc.invalidateQueries({ queryKey: ['rag-eval', 'tuning', 'versions'] });
    },
  });
}

/** 驳回调优建议 */
export function useRejectSuggestion() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (params: { suggestionId: string; runId: string; reason?: string }) =>
      tuningApi.rejectSuggestion(params.suggestionId, params.reason),
    onSuccess: (_data, params) => {
      qc.invalidateQueries({ queryKey: ['rag-eval', 'tuning', 'suggestions', params.runId] });
    },
  });
}

/** 忽略调优建议（标记为无需处理） */
export function useIgnoreSuggestion() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (params: { suggestionId: string; runId: string }) =>
      tuningApi.ignoreSuggestion(params.suggestionId),
    onSuccess: (_data, params) => {
      qc.invalidateQueries({ queryKey: ['rag-eval', 'tuning', 'suggestions', params.runId] });
    },
  });
}

/** 获取历史配置版本列表 */
export function useConfigVersions() {
  return useQuery({
    queryKey: ['rag-eval', 'tuning', 'versions'],
    queryFn: () => tuningApi.getConfigVersions(),
    staleTime: 60_000,
  });
}

/** 回滚到指定配置版本 */
export function useRollbackConfig() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (versionId: string) => tuningApi.rollbackConfigVersion(versionId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['rag-eval', 'tuning', 'versions'] });
    },
  });
}
