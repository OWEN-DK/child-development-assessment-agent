import { useState, useCallback } from 'react';
import { knowledgeQAApi, type HistoryItem } from '../api/knowledgeQAApi';
import type { KnowledgeQAResponse } from '../types';

export function useHistory() {
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchList = useCallback(async (page: number = 1, pageSize: number = 20) => {
    setLoading(true);
    setError(null);
    try {
      const data = await knowledgeQAApi.getHistoryList(page, pageSize);
      setItems(data.items);
      setTotal(data.total);
    } catch (err: any) {
      setError(err.message || '加载历史记录失败');
    } finally {
      setLoading(false);
    }
  }, []);

  /** 加载并打开历史详情 */
  const loadDetail = useCallback(
    async (taskId: string): Promise<KnowledgeQAResponse | null> => {
      try {
        return await knowledgeQAApi.getHistoryDetail(taskId);
      } catch (err: any) {
        setError(err.message || '加载历史详情失败');
        return null;
      }
    },
    [],
  );

  // Auto refresh on mount
  const refresh = useCallback(() => fetchList(), [fetchList]);

  return { items, total, loading, error, fetchList, loadDetail, refresh };
}
