import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as draftsApi from '@/api/rag-eval/drafts';
import type { DraftGenerationConfig } from '@entities/rag-eval';

/** 草稿列表筛选参数 */
export interface DraftFilters {
  status?: 'pending' | 'approved' | 'rejected';
  page?: number;
  page_size?: number;
  sort_by?: string;
  sort_order?: string;
}

/** 获取草稿列表 */
export function useDrafts(filters?: DraftFilters) {
  return useQuery({
    queryKey: ['rag-eval', 'drafts', filters],
    queryFn: () => draftsApi.getDrafts(filters),
    staleTime: 30_000,
  });
}

/** 获取单个草稿详情 */
export function useDraft(id: string) {
  return useQuery({
    queryKey: ['rag-eval', 'drafts', id],
    queryFn: () => draftsApi.getDraft(id),
    staleTime: 30_000,
    enabled: !!id,
  });
}

/** 从文档批量生成草稿 */
export function useCreateDrafts() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (params: { documentId: string; config?: DraftGenerationConfig }) =>
      draftsApi.startGeneration(params.documentId, params.config),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['rag-eval', 'drafts'] });
    },
  });
}

/** 审核草稿（通过/驳回） */
export function useReviewDraft() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (params: { id: string; status: 'approved' | 'rejected'; comment?: string }) =>
      draftsApi.reviewDraft(params.id, params.status === 'approved' ? 'approve' : 'reject', params.comment),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['rag-eval', 'drafts'] });
    },
  });
}

/** 批量删除草稿 */
export function useDeleteDrafts() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (ids: string[]) => draftsApi.deleteDrafts(ids),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['rag-eval', 'drafts'] });
    },
  });
}

/** 获取可用于生成草稿的源文档列表 */
export function useSourceDocuments(page: number = 1, pageSize: number = 20) {
  return useQuery({
    queryKey: ['rag-eval', 'source-documents', page, pageSize],
    queryFn: () => draftsApi.getSourceDocuments({ page, page_size: pageSize }),
    staleTime: 60_000,
  });
}
