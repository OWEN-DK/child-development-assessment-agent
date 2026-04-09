import { useState, useCallback } from 'react';
import {
  getTestCases,
  createTestCase,
  updateTestCase,
  deleteTestCase,
  runAllTests,
  runSingleTest,
  getTestRuns,
  compareTestRuns,
  createSnapshot,
  getSnapshots,
} from '@/api/rag-test';
import type { TestCase, TestRun, KnowledgeSnapshot } from '@/api/rag-test/types';

export function useRagEvaluation() {
  const [testCases, setTestCases] = useState<TestCase[]>([]);
  const [testRuns, setTestRuns] = useState<TestRun[]>([]);
  const [snapshots, setSnapshots] = useState<KnowledgeSnapshot[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadTestCases = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getTestCases();
      setTestCases(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载测试用例失败');
    } finally {
      setLoading(false);
    }
  }, []);

  const loadTestRuns = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getTestRuns();
      setTestRuns(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载测试运行失败');
    } finally {
      setLoading(false);
    }
  }, []);

  const loadSnapshots = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getSnapshots();
      setSnapshots(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载快照失败');
    } finally {
      setLoading(false);
    }
  }, []);

  const handleRunAllTests = useCallback(async (name?: string, description?: string) => {
    setLoading(true);
    try {
      const result = await runAllTests({ name, description });
      await loadTestRuns();
      return result;
    } catch (err) {
      setError(err instanceof Error ? err.message : '运行测试失败');
      throw err;
    } finally {
      setLoading(false);
    }
  }, [loadTestRuns]);

  const handleRunSingleTest = useCallback(async (caseId: string, limit: number = 10) => {
    setLoading(true);
    try {
      const result = await runSingleTest(caseId, limit);
      return result;
    } catch (err) {
      setError(err instanceof Error ? err.message : '运行单个测试失败');
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  const handleCreateTestCase = useCallback(async (data: Omit<TestCase, 'id' | 'created_at' | 'updated_at'>) => {
    setLoading(true);
    try {
      const newCase = await createTestCase(data);
      await loadTestCases();
      return newCase;
    } catch (err) {
      setError(err instanceof Error ? err.message : '创建测试用例失败');
      throw err;
    } finally {
      setLoading(false);
    }
  }, [loadTestCases]);

  const handleUpdateTestCase = useCallback(async (caseId: string, data: Partial<TestCase>) => {
    setLoading(true);
    try {
      const updated = await updateTestCase(caseId, data);
      await loadTestCases();
      return updated;
    } catch (err) {
      setError(err instanceof Error ? err.message : '更新测试用例失败');
      throw err;
    } finally {
      setLoading(false);
    }
  }, [loadTestCases]);

  const handleDeleteTestCase = useCallback(async (caseId: string) => {
    setLoading(true);
    try {
      await deleteTestCase(caseId);
      await loadTestCases();
    } catch (err) {
      setError(err instanceof Error ? err.message : '删除测试用例失败');
      throw err;
    } finally {
      setLoading(false);
    }
  }, [loadTestCases]);

  const handleCompareRuns = useCallback(async (runId1: string, runId2: string) => {
    setLoading(true);
    try {
      const result = await compareTestRuns(runId1, runId2);
      return result;
    } catch (err) {
      setError(err instanceof Error ? err.message : '对比测试运行失败');
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  const handleCreateSnapshot = useCallback(async (name?: string, description?: string) => {
    setLoading(true);
    try {
      const result = await createSnapshot({ name, description });
      await loadSnapshots();
      return result;
    } catch (err) {
      setError(err instanceof Error ? err.message : '创建快照失败');
      throw err;
    } finally {
      setLoading(false);
    }
  }, [loadSnapshots]);

  return {
    testCases,
    testRuns,
    snapshots,
    loading,
    error,
    loadTestCases,
    loadTestRuns,
    loadSnapshots,
    runAllTests: handleRunAllTests,
    runSingleTest: handleRunSingleTest,
    createTestCase: handleCreateTestCase,
    updateTestCase: handleUpdateTestCase,
    deleteTestCase: handleDeleteTestCase,
    compareTestRuns: handleCompareRuns,
    createSnapshot: handleCreateSnapshot,
  };
}
