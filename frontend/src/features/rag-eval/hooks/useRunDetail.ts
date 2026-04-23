import { useState, useEffect, useMemo } from 'react';
import { getTestRun } from '@/api/rag-test';
import { useSSE } from '@shared/hooks/useSSE';
import type { TestRun, TestResult } from '@/api/rag-test';
import { handleApiCall, notification } from '@shared/lib/notification';

export function useRunDetail(id: string | undefined) {
  const [run, setRun] = useState<TestRun | null>(null);
  const [caseResults, setCaseResults] = useState<TestResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [progress, setProgress] = useState({ current: 0, total: 0 });
  const [filter, setFilter] = useState<string>('all');
  const [keyword, setKeyword] = useState('');
  const [sseUrl, setSseUrl] = useState<string | null>(null);

  useSSE({
    url: sseUrl || '',
    enabled: !!sseUrl,
    onMessage: (eventType, event: any) => {
      if (eventType === 'progress') {
        setProgress({ current: event.current_case || 0, total: event.total_cases || 0 });
      } else if (eventType === 'case_result') {
        setCaseResults(prev => [...prev, {
          test_case_id: event.case_id,
          query: event.query,
          age: 0,
          precision: event.hit_at_1 ? 1 : 0,
          recall: event.hit_at_5 ? 1 : 0,
          f1_score: event.hit_at_1 ? 1 : 0,
          mrr: event.hit_at_1 ? 1 : 0,
          ndcg_at_k: 0,
          passed: event.passed || false,
          results: [],
          executed_at: event.timestamp,
          execution_time_ms: 0,
        }]);
      } else if (eventType === 'test_completed') {
        setRun(prev => prev ? {
          ...prev,
          status: 'completed',
          overall_precision: event.overall_metrics?.precision || 0,
          overall_recall: event.overall_metrics?.recall || 0,
          overall_f1: event.overall_metrics?.f1 || 0,
          overall_mrr: event.overall_metrics?.mrr || 0,
          overall_ndcg: event.overall_metrics?.ndcg || 0,
          total_test_cases: event.total_cases,
          passed_test_cases: event.passed_cases,
        } : null);
        setProgress({ current: event.passed_cases, total: event.total_cases });
        setSseUrl(null); // 结束SSE
      } else if (eventType === 'run_failed') {
        setRun(prev => prev ? { ...prev, status: 'failed' } : null);
        notification.error(`运行失败: ${event.error_message}`);
        setSseUrl(null); // 结束SSE
      }
    }
  });

  useEffect(() => {
    if (!id) return;
    loadData();
    return () => setSseUrl(null);
  }, [id]);

  const loadData = async () => {
    if (!id) return;
    setLoading(true);
    await handleApiCall(async () => {
      const data = await getTestRun(id);
      setRun(data);
      setCaseResults(data.test_results || []);
      setProgress({ current: data.passed_test_cases || 0, total: data.total_test_cases || 0 });

      if (data.status === 'running') {
        setSseUrl(`/api/v1/tasks/test_run/${id}/stream`);
      }
    }, {
      errorMsg: '加载失败',
    });
    setLoading(false);
  };

  const filteredResults = useMemo(() => {
    return caseResults.filter(r => {
      if (keyword && !r.query.toLowerCase().includes(keyword.toLowerCase())) return false;
      if (filter === 'hit1' && r.precision !== 1) return false;
      if (filter === 'miss' && r.precision > 0) return false;
      return true;
    });
  }, [caseResults, keyword, filter]);

  return {
    run,
    caseResults: filteredResults,
    loading,
    progress,
    filters: {
      filter,
      setFilter,
      keyword,
      setKeyword,
    }
  };
}