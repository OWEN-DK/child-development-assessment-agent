import { useState, useEffect, useCallback } from 'react';
import { App } from 'antd';
import {
  getTestCases,
  createTestCase,
  updateTestCase,
  deleteTestCase,
  runAllTests,
  runSingleTest,
  getTestRuns,
  createSnapshot,
  getSnapshots,
  restoreSnapshot,
} from '../../../api/rag-test';
import type { TestCase, TestRun, KnowledgeSnapshot, TestResult } from '../../../api/rag-test/types';

interface UseRagTestReturn {
  testCases: TestCase[];
  testRuns: TestRun[];
  snapshots: KnowledgeSnapshot[];
  loading: boolean;
  testRunning: boolean;
  loadTestCases: () => Promise<void>;
  loadTestRuns: () => Promise<void>;
  loadSnapshots: () => Promise<void>;
  handleAddCase: (caseData: Omit<TestCase, 'id' | 'created_at' | 'updated_at'>) => Promise<void>;
  handleUpdateCase: (caseId: string, caseData: Partial<TestCase>) => Promise<void>;
  handleDeleteCase: (id: string) => Promise<void>;
  handleRunSingleCase: (caseId: string) => Promise<TestResult>;
  handleRunAllTests: () => Promise<void>;
  handleCreateSnapshot: () => Promise<void>;
  handleRestoreSnapshot: (snapshotId: string) => Promise<void>;
}

export const useRagTest = (): UseRagTestReturn => {
  const { message } = App.useApp();
  const [testCases, setTestCases] = useState<TestCase[]>([]);
  const [testRuns, setTestRuns] = useState<TestRun[]>([]);
  const [snapshots, setSnapshots] = useState<KnowledgeSnapshot[]>([]);
  const [loading, setLoading] = useState(false);
  const [testRunning, setTestRunning] = useState(false);

  const loadTestCases = useCallback(async () => {
    try {
      setLoading(true);
      const data = await getTestCases();
      setTestCases(data);
    } catch (e) {
      message.error('加载测试用例失败');
      console.error('Load test cases failed:', e);
      throw e;
    } finally {
      setLoading(false);
    }
  }, [message]);

  const loadTestRuns = useCallback(async () => {
    try {
      setLoading(true);
      const data = await getTestRuns();
      setTestRuns(data);
    } catch (e) {
      message.error('加载测试运行记录失败');
      console.error('Load test runs failed:', e);
      throw e;
    } finally {
      setLoading(false);
    }
  }, [message]);

  const loadSnapshots = useCallback(async () => {
    try {
      setLoading(true);
      const data = await getSnapshots();
      setSnapshots(data);
    } catch (e) {
      message.error('加载快照列表失败');
      console.error('Load snapshots failed:', e);
      throw e;
    } finally {
      setLoading(false);
    }
  }, [message]);

  const handleAddCase = useCallback(async (caseData: Omit<TestCase, 'id' | 'created_at' | 'updated_at'>) => {
    await createTestCase(caseData);
    await loadTestCases();
  }, [loadTestCases]);

  const handleUpdateCase = useCallback(async (caseId: string, caseData: Partial<TestCase>) => {
    await updateTestCase(caseId, caseData);
    await loadTestCases();
  }, [loadTestCases]);

  const handleDeleteCase = useCallback(async (id: string) => {
    await deleteTestCase(id);
    await loadTestCases();
  }, [loadTestCases]);

  const handleRunSingleCase = useCallback(async (caseId: string): Promise<TestResult> => {
    try {
      setTestRunning(true);
      const result = await runSingleTest(caseId);
      return result.result;
    } finally {
      setTestRunning(false);
    }
  }, []);

  const handleRunAllTests = useCallback(async () => {
    try {
      setTestRunning(true);
      await runAllTests({
        name: `手动运行 - ${new Date().toLocaleString()}`,
        limit: 10
      });
      await loadTestRuns();
    } finally {
      setTestRunning(false);
    }
  }, [loadTestRuns]);

  const handleCreateSnapshot = useCallback(async () => {
    await createSnapshot({
      name: `快照 - ${new Date().toLocaleString()}`,
      description: '手动创建的快照'
    });
    await loadSnapshots();
  }, [loadSnapshots]);

  const handleRestoreSnapshot = useCallback(async (snapshotId: string) => {
    await restoreSnapshot(snapshotId);
    setTimeout(() => {
      loadTestCases();
      loadTestRuns();
      loadSnapshots();
    }, 2000);
  }, [loadTestCases, loadTestRuns, loadSnapshots]);

  useEffect(() => {
    loadTestCases();
    loadTestRuns();
    loadSnapshots();
  }, [loadTestCases, loadTestRuns, loadSnapshots]);

  return {
    testCases,
    testRuns,
    snapshots,
    loading,
    testRunning,
    loadTestCases,
    loadTestRuns,
    loadSnapshots,
    handleAddCase,
    handleUpdateCase,
    handleDeleteCase,
    handleRunSingleCase,
    handleRunAllTests,
    handleCreateSnapshot,
    handleRestoreSnapshot,
  };
};
