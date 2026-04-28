import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as casesApi from '@/api/rag-eval/cases';
import type { TestCase } from '@entities/rag-eval';

/** 用例列表筛选参数 */
export interface TestCaseFilters {
  domain?: string;
  source?: string;
  age_stage?: string;
  search?: string;
  page?: number;
  page_size?: number;
}

/** 获取用例列表 */
export function useTestCases(filters?: TestCaseFilters) {
  return useQuery({
    queryKey: ['rag-eval', 'test-cases', filters],
    queryFn: () => casesApi.getTestCases(filters),
    staleTime: 30_000,
  });
}

/** 获取单个用例详情 */
export function useTestCase(id: string) {
  return useQuery({
    queryKey: ['rag-eval', 'test-cases', id],
    queryFn: () => casesApi.getTestCase(id),
    staleTime: 30_000,
    enabled: !!id,
  });
}

/** 手动创建用例 */
export function useCreateTestCase() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Pick<TestCase, 'query' | 'age' | 'domain' | 'expected_knowledge_ids' | 'expected_keywords' | 'difficulty_level'> &
      Partial<Pick<TestCase, 'age_stage_label' | 'description' | 'answer_points_summary'>>) =>
      casesApi.createTestCase(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['rag-eval', 'test-cases'] });
    },
  });
}

/** 更新用例 */
export function useUpdateTestCase() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (params: { id: string; data: Partial<TestCase> }) =>
      casesApi.updateTestCase(params.id, params.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['rag-eval', 'test-cases'] });
    },
  });
}

/** 删除单个用例 */
export function useDeleteTestCase() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => casesApi.deleteTestCase(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['rag-eval', 'test-cases'] });
    },
  });
}

/** 批量删除用例 */
export function useBatchDeleteTestCases() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (ids: string[]) => casesApi.batchDeleteTestCases(ids),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['rag-eval', 'test-cases'] });
    },
  });
}

/** 从外部导入用例（JSON/CSV 文件或草稿转入） */
export function useImportTestCases() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (params: { testSetId?: string; caseIds?: string[]; file?: File }) =>
      casesApi.importTestCases(params.caseIds || []),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['rag-eval', 'test-cases'] });
    },
  });
}
