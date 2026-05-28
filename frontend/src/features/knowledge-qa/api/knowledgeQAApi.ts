import { apiClient } from '@shared/api/client';
import type { KnowledgeQAResponse } from '../types';

export type HistoryStatus = 'completed' | 'partial' | 'cancelled' | 'timeout' | 'error';

export interface HistoryItem {
  task_id: string;
  question: string;
  status: HistoryStatus;
  created_at: string | null;
  matched_books: any;
  is_partial?: boolean;
}

export interface HistoryListResponse {
  items: HistoryItem[];
  total: number;
  page: number;
  page_size: number;
}

export const knowledgeQAApi = {
  /** 获取历史记录列表 */
  getHistoryList: async (
    page: number = 1,
    pageSize: number = 20,
  ): Promise<HistoryListResponse> => {
    const res = await apiClient.get('/api/v1/knowledge-qa/history', {
      params: { page, page_size: pageSize },
    });
    return res.data as HistoryListResponse;
  },

  /** 获取历史记录详情 */
  getHistoryDetail: async (
    taskId: string,
  ): Promise<
    KnowledgeQAResponse & { task_id: string; question: string; created_at: string }
  > => {
    const res = await apiClient.get(`/api/v1/knowledge-qa/history/${taskId}`);
    return res.data as any;
  },

  /** 删除历史记录 */
  deleteHistory: async (taskId: string): Promise<void> => {
    await apiClient.delete(`/api/v1/knowledge-qa/history/${taskId}`);
  },
};

/** 状态 → 中文标签 + 颜色 */
export const STATUS_CONFIG: Record<HistoryStatus, { label: string; color: string }> = {
  completed: { label: '已完成', color: '#52c41a' },
  partial: { label: '部分', color: '#faad14' },
  cancelled: { label: '已中断', color: '#ff7a45' },
  timeout: { label: '超时', color: '#ff4d4f' },
  error: { label: '失败', color: '#ff4d4f' },
};
