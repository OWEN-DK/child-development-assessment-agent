import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as testSetsApi from '@/api/rag-eval/cases';
import type { TestSet } from '@entities/rag-eval';

/** 测试集列表筛选参数 */
export interface TestSetFilters {
  page?: number;
  page_size?: number;
}

/** 获取测试集列表 */
export function useTestSets(filters?: TestSetFilters) {
  return useQuery({
    queryKey: ['rag-eval', 'test-sets', filters],
    queryFn: () => testSetsApi.getTestSets(filters),
    staleTime: 30_000,
  });
}

/** 获取单个测试集详情 */
export function useTestSet(id: string) {
  return useQuery({
    queryKey: ['rag-eval', 'test-sets', id],
    queryFn: () => testSetsApi.getTestSet(id),
    staleTime: 30_000,
    enabled: !!id,
  });
}

/** 创建测试集 */
export function useCreateTestSet() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { name: string; description?: string; case_ids?: string[] }) =>
      testSetsApi.createTestSet({ name: data.name, description: data.description ?? null, case_ids: data.case_ids || [] }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['rag-eval', 'test-sets'] });
    },
  });
}

/** 更新测试集 */
export function useUpdateTestSet() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (params: { id: string; data: Partial<TestSet> }) =>
      testSetsApi.updateTestSet(params.id, params.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['rag-eval', 'test-sets'] });
    },
  });
}

/** 删除测试集 */
export function useDeleteTestSet() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => testSetsApi.deleteTestSet(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['rag-eval', 'test-sets'] });
    },
  });
}

/** 向测试集添加用例 */
export function useAddCasesToSet() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (params: { setId: string; caseIds: string[] }) =>
      testSetsApi.addCasesToSet(params.setId, params.caseIds),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['rag-eval', 'test-sets'] });
    },
  });
}

/** 从测试集移除用例 */
export function useRemoveCasesFromSet() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (params: { setId: string; caseIds: string[] }) =>
      testSetsApi.removeCasesFromSet(params.setId, params.caseIds),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['rag-eval', 'test-sets'] });
    },
  });
}

/** 导出测试集（返回 JSON/CSV 数据流） */
export function useExportTestSet() {
  return useMutation({
    mutationFn: (id: string) => testSetsApi.exportTestSet(id),
  });
}
