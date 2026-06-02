import { apiClient } from '@shared/api/client';
import type {
  CurationBookListResponse,
  DraftDetail,
  DraftListResponse,
  KGData,
  PendingItem,
  KBBookListResponse,
  BindBookRequest,
} from '../types';

export const curationApi = {
  /* ===== 书籍管理 ===== */

  /** 获取策管书籍列表 */
  listBooks: async (
    params: { status?: string; page?: number; page_size?: number } = {},
  ): Promise<CurationBookListResponse> => {
    const res = await apiClient.get('/api/v2/curation/books', { params });
    return res.data as CurationBookListResponse;
  },

  /** 删除策管书籍 */
  deleteBook: async (bookId: string): Promise<void> => {
    await apiClient.delete(`/api/v2/curation/books/${bookId}`);
  },

  /* ===== 绑定 ===== */

  /** 获取知识库中可绑定的 EPUB 书籍 */
  listKBBooks: async (): Promise<KBBookListResponse> => {
    const res = await apiClient.get('/api/v2/curation/kb-books');
    return res.data as KBBookListResponse;
  },

  /** 绑定知识库书籍到策管 */
  bindBook: async (data: BindBookRequest): Promise<{ book_id: string }> => {
    const res = await apiClient.post('/api/v2/curation/bind', data);
    return res.data;
  },

  /* ===== 生成 ===== */

  /** 触发 AI 生成 */
  startGeneration: async (bookId: string): Promise<void> => {
    await apiClient.post(`/api/v2/curation/books/${bookId}/generate`);
  },

  /** 获取生成进度 (SSE endpoint, 返回 URL) */
  getGenerationProgressUrl: (bookId: string): string => {
    return `/api/v2/curation/books/${bookId}/generate/progress`;
  },

  /** 取消正在进行的生成任务 */
  cancelGeneration: async (bookId: string): Promise<void> => {
    await apiClient.post(`/api/v2/curation/books/${bookId}/generate/cancel`);
  },

  /* ===== 草稿 ===== */

  /** 获取草稿列表 */
  listDrafts: async (
    params: { status?: string; book_id?: string; page?: number; page_size?: number } = {},
  ): Promise<DraftListResponse> => {
    const res = await apiClient.get('/api/v2/curation/drafts', { params });
    return res.data as DraftListResponse;
  },

  /** 获取单个草稿详情 */
  getDraft: async (draftId: string): Promise<DraftDetail> => {
    const res = await apiClient.get(`/api/v2/curation/drafts/${draftId}`);
    return res.data as DraftDetail;
  },

  /** 保存审核修改 */
  updateDraft: async (draftId: string, content: string): Promise<void> => {
    await apiClient.put(`/api/v2/curation/drafts/${draftId}`, { content });
  },

  /** 标记已审核 */
  markReviewed: async (draftId: string, reviewer: string): Promise<void> => {
    await apiClient.post(`/api/v2/curation/drafts/${draftId}/review`, { reviewer });
  },

  /** 入库 Neo4j */
  publishToNeo4j: async (draftId: string): Promise<void> => {
    await apiClient.post(`/api/v2/curation/drafts/${draftId}/publish`);
  },

  /* ===== 计数刷新 ===== */

  /** 从 Neo4j 刷新实体/主张/处方计数 */
  refreshCounts: async (bookId: string): Promise<{ total_entities: number; total_claims: number; total_prescriptions: number }> => {
    const res = await apiClient.post(`/api/v2/curation/books/${bookId}/refresh-counts`);
    return res.data;
  },

  /* ===== 知识图谱 ===== */

  /** 获取 KG 可视化数据 */
  getGraph: async (bookId?: string, limit?: number): Promise<KGData> => {
    const res = await apiClient.get('/api/v2/curation/graph', {
      params: { ...(bookId ? { book_id: bookId } : {}), ...(limit ? { limit } : {}) },
    });
    return res.data as KGData;
  },

  /* ===== 导出 ===== */

  /** 获取跨书关系对 */
  getCrossBookPairs: async (
    bookIds?: string[],
  ): Promise<{ pairs: { type: string; count: number }[]; relations: any[] }> => {
    const res = await apiClient.get('/api/v2/curation/cross-book/pairs', {
      params: bookIds ? { book_ids: bookIds.join(',') } : {},
    });
    return res.data as any;
  },

  /** 导出图谱为 Cypher */
  exportCypher: async (bookId?: string): Promise<{ statements: string[]; count: number }> => {
    const res = await apiClient.get('/api/v2/curation/graph/export-cypher', {
      params: bookId ? { book_id: bookId } : {},
    });
    return res.data;
  },

  /** 清空知识图谱 */
  clearGraph: async (bookId?: string): Promise<{ message: string; deleted_nodes: number }> => {
    const res = await apiClient.post('/api/v2/curation/graph/clear', null, {
      params: bookId ? { book_id: bookId } : {},
    });
    return res.data;
  },

  /* ===== 自定义知识 ===== */

  /** 获取自定义知识列表 */
  listCustomRules: async (params?: { page?: number; page_size?: number }) => {
    const res = await apiClient.get('/api/v1/custom-knowledge/', { params });
    return res.data;
  },

  /** 确认入库自定义规则 */
  confirmCustomRules: async (rules: any[]) => {
    const res = await apiClient.post('/api/v1/custom-knowledge/confirm', { rules });
    return res.data;
  },

  /** 更新自定义规则 */
  updateCustomRule: async (ruleId: string, data: Record<string, any>) => {
    const res = await apiClient.put(`/api/v1/custom-knowledge/${ruleId}`, data);
    return res.data;
  },

  /** 删除自定义规则 */
  deleteCustomRule: async (ruleId: string) => {
    const res = await apiClient.delete(`/api/v1/custom-knowledge/${ruleId}`);
    return res.data;
  },

  /** 测试匹配自定义知识 */
  matchCustomKnowledge: async (question: string) => {
    const res = await apiClient.post('/api/v1/custom-knowledge/match', { question });
    return res.data;
  },

  /* ===== 待提炼队列 ===== */

  /** 获取待提炼队列 */
  getPendingQueue: async (
    params: { status?: string; book_id?: string; page?: number; page_size?: number } = {},
  ): Promise<{ items: PendingItem[]; total: number }> => {
    const res = await apiClient.get('/api/v2/curation/pending', { params });
    return res.data;
  },

  /* ===== 跨书融合 (Phase 5a/5b) ===== */

  /** 获取跨书融合分析结果 */
  getCrossBookRelations: async (bookId: string): Promise<any> => {
    const res = await apiClient.get(`/api/v2/curation/cross-book/relations/${bookId}`);
    return res.data;
  },

  /** 更新单条审核者决策 */
  updateCrossBookDecision: async (
    bookId: string,
    decisionType: 'entity_match' | 'cross_relation',
    index: number,
    decision: string,
    customType?: string,
  ): Promise<void> => {
    await apiClient.post('/api/v2/curation/cross-book/decision', {
      book_id: bookId,
      decision_type: decisionType,
      index,
      decision,
      custom_type: customType,
    });
  },

  /** 批量更新审核者决策 */
  batchUpdateCrossBookDecisions: async (
    bookId: string,
    decisionType: 'entity_match' | 'cross_relation',
    indices: number[],
    decision: string,
  ): Promise<void> => {
    await apiClient.post('/api/v2/curation/cross-book/decision/batch', {
      book_id: bookId,
      decision_type: decisionType,
      indices,
      decision,
    });
  },

  /* ===== 全局跨书分析（Phase 4 新增） ===== */

  /** 对所有已入库书籍执行成对跨书分析 */
  analyzeAllBooks: async (force?: boolean): Promise<any> => {
    const res = await apiClient.post('/api/v2/curation/cross-book/analyze-all', null, {
      params: force ? { force: true } : {},
    });
    return res.data;
  },

  /** 手动重试单书的跨书分析 */
  retryCrossBookAnalysis: async (bookId: string): Promise<any> => {
    const res = await apiClient.post(
      `/api/v2/curation/books/${bookId}/cross-book/retry`,
    );
    return res.data;
  },
};
