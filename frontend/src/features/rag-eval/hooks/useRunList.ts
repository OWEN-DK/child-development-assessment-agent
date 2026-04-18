import { useState, useEffect, useMemo } from 'react';
import dayjs from 'dayjs';
import { getTestRuns, batchDeleteTestRuns, getTestSets } from '@/api/rag-test';
import type { TestRun, TestSet } from '@/api/rag-test';
import { handleApiCall } from '@shared/lib/notification';

export function useRunList() {
  const [runs, setRuns] = useState<TestRun[]>([]);
  const [testSets, setTestSets] = useState<TestSet[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string | null>(null);
  const [testSetFilter, setTestSetFilter] = useState<string | null>(null);
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs, dayjs.Dayjs] | null>(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    await handleApiCall(async () => {
      const [runsData, setsData] = await Promise.all([getTestRuns(), getTestSets()]);
      setRuns(runsData);
      setTestSets(setsData);
    }, {
      errorMsg: '加载失败',
    });
    setLoading(false);
  };

  const handleDelete = async (id: string) => {
    await handleApiCall(() => batchDeleteTestRuns([id]), {
      successMsg: '删除成功',
      errorMsg: '删除失败',
      onSuccess: () => loadData(),
    });
  };

  const filteredRuns = useMemo(() => {
    return runs.filter(r => {
      if (statusFilter && r.status !== statusFilter) return false;
      if (testSetFilter && r.test_set_id !== testSetFilter) return false;
      if (dateRange) {
        const runDate = dayjs(r.created_at);
        if (runDate.isBefore(dateRange[0]) || runDate.isAfter(dateRange[1])) return false;
      }
      return true;
    });
  }, [runs, statusFilter, testSetFilter, dateRange]);

  return {
    runs: filteredRuns,
    testSets,
    loading,
    filters: {
      statusFilter,
      setStatusFilter,
      testSetFilter,
      setTestSetFilter,
      dateRange,
      setDateRange,
    },
    actions: {
      handleDelete,
      loadData,
    }
  };
}