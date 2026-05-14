/** 提示词管理 Hooks */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as promptsApi from '@/api/rag-eval/prompts';
import type { PromptFilters } from '@entities/rag-eval';

/** 提示词列表查询 */
export function usePrompts(filters?: PromptFilters) {
  return useQuery({
    queryKey: ['rag-eval', 'prompts', filters],
    queryFn: () => promptsApi.getPrompts({
      category: filters?.category,
      is_active: filters?.is_active,
    }),
    staleTime: 30_000,
  });
}

/** 提示词详情查询 */
export function usePromptDetail(promptKey: string) {
  return useQuery({
    queryKey: ['rag-eval', 'prompts', promptKey],
    queryFn: () => promptsApi.getPromptDetail(promptKey),
    staleTime: 30_000,
    enabled: !!promptKey,
  });
}

/** 更新提示词 mutation */
export function useUpdatePrompt() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (params: {
      promptKey: string;
      content: string;
      change_summary?: string;
      created_by?: string;
    }) => promptsApi.updatePrompt(params.promptKey, {
      content: params.content,
      change_summary: params.change_summary,
      created_by: params.created_by,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['rag-eval', 'prompts'] });
    },
  });
}

/** 分析提示词修改影响 mutation */
export function useAnalyzeImpact() {
  return useMutation({
    mutationFn: (params: { promptKey: string; content: string }) =>
      promptsApi.analyzePromptImpact(params.promptKey, { content: params.content }),
  });
}

/** 测试提示词渲染 mutation */
export function useTestPrompt() {
  return useMutation({
    mutationFn: (params: {
      prompt_key: string;
      version?: string;
      variables: Record<string, string>;
    }) => promptsApi.testPrompt(params),
  });
}

/** 版本对比查询 */
export function useCompareVersions(promptKey: string, version1: string, version2: string) {
  return useQuery({
    queryKey: ['rag-eval', 'prompts', promptKey, 'compare', version1, version2],
    queryFn: () => promptsApi.comparePromptVersions(promptKey, version1, version2),
    staleTime: 60_000,
    enabled: !!promptKey && !!version1 && !!version2,
  });
}
