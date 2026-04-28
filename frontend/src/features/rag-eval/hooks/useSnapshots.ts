import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as snapshotsApi from '@/api/rag-eval/snapshots';

/** 快照列表筛选参数 */
export interface SnapshotFilters {
  page?: number;
  page_size?: number;
}

/** 获取快照列表 */
export function useSnapshots(filters?: SnapshotFilters) {
  return useQuery({
    queryKey: ['rag-eval', 'snapshots', filters],
    queryFn: () => snapshotsApi.getSnapshots(),
    staleTime: 30_000,
  });
}

/** 获取单个快照详情 */
export function useSnapshot(id: string) {
  return useQuery({
    queryKey: ['rag-eval', 'snapshots', id],
    queryFn: () => snapshotsApi.getSnapshot(id),
    staleTime: 60_000,
    enabled: !!id,
  });
}

/** 创建配置快照 */
export function useCreateSnapshot() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { name: string; description?: string }) =>
      snapshotsApi.createSnapshot(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['rag-eval', 'snapshots'] });
    },
  });
}

/** 从快照还原配置 */
export function useRestoreSnapshot() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => snapshotsApi.restoreSnapshot(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['rag-eval', 'snapshots'] });
    },
  });
}
