import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as runsApi from '@/api/rag-eval/runs';

/** 运行列表筛选参数 */
export interface RunFilters {
  status?: string;
  page?: number;
  page_size?: number;
}

/** 获取评估运行列表 */
export function useTestRuns(filters?: RunFilters) {
  return useQuery({
    queryKey: ['rag-eval', 'runs', filters],
    queryFn: () => runsApi.getRuns(filters),
    staleTime: 30_000,
  });
}

/** 获取单个运行详情 */
export function useTestRun(id: string) {
  return useQuery({
    queryKey: ['rag-eval', 'runs', id],
    queryFn: () => runsApi.getRun(id),
    staleTime: 30_000,
    enabled: !!id,
  });
}

/** 创建评估运行 */
export function useCreateRun() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { name: string; testSetId: string; config?: Record<string, unknown> }) =>
      runsApi.createRun(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['rag-eval', 'runs'] });
    },
  });
}

/** 删除单个运行 */
export function useDeleteRun() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => runsApi.deleteRun(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['rag-eval', 'runs'] });
    },
  });
}

/** 批量删除运行 */
export function useBatchDeleteRuns() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (ids: string[]) => runsApi.batchDeleteRuns(ids),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['rag-eval', 'runs'] });
    },
  });
}

/** 对比两次运行的指标差异 */
export function useCompareRuns(id1: string, id2: string) {
  return useQuery({
    queryKey: ['rag-eval', 'runs', 'compare', id1, id2],
    queryFn: () => runsApi.compareRuns(id1, id2),
    staleTime: 60_000,
    enabled: !!id1 && !!id2,
  });
}
