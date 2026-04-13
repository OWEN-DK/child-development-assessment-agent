import { useState, useCallback } from 'react';
import {
  getTestCases,
  createTestCase,
  updateTestCase,
  deleteTestCase,
  batchDeleteTestCases,
  runAllTests,
  runSingleTest,
  getTestRuns,
  compareTestRuns,
  createSnapshot,
  getSnapshots,
  getDrafts,
  reviewDraft,
  updateDraft,
  importDrafts,
  deleteDraft,
  batchDeleteDrafts,
  batchDeleteTestRuns,
  getSourceDocuments,
  generateDrafts,
} from '@/api/rag-test';
import type { TestCase, TestRun, KnowledgeSnapshot, TestCaseDraft, SourceDocument, GenerationParams } from '@/api/rag-test/types';

export function useRagEvaluation() {
  const [testCases, setTestCases] = useState<TestCase[]>([]);
  const [testRuns, setTestRuns] = useState<TestRun[]>([]);
  const [snapshots, setSnapshots] = useState<KnowledgeSnapshot[]>([]);
  const [drafts, setDrafts] = useState<TestCaseDraft[]>([]);
  const [sourceDocuments, setSourceDocuments] = useState<SourceDocument[]>([]);
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

  const handleBatchDeleteTestCases = useCallback(async (caseIds: string[]) => {
    setLoading(true);
    try {
      const result = await batchDeleteTestCases(caseIds);
      await loadTestCases();
      return result;
    } catch (err) {
      setError(err instanceof Error ? err.message : '批量删除测试用例失败');
      throw err;
    } finally {
      setLoading(false);
    }
  }, [loadTestCases]);

  const handleBatchDeleteTestRuns = useCallback(async (runIds: string[]) => {
    setLoading(true);
    try {
      const result = await batchDeleteTestRuns(runIds);
      await loadTestRuns();
      return result;
    } catch (err) {
      setError(err instanceof Error ? err.message : '批量删除评估报告失败');
      throw err;
    } finally {
      setLoading(false);
    }
  }, [loadTestRuns]);

  const loadDrafts = useCallback(async (sourceDocumentId?: string) => {
    setLoading(true);
    try {
      console.log('[loadDrafts] 开始加载草稿, sourceDocumentId:', sourceDocumentId);
      const data = await getDrafts(sourceDocumentId);
      console.log('[loadDrafts] 加载到草稿数据:', data.length, '条');
      setDrafts(data);
      setError(null);
    } catch (err) {
      console.error('[loadDrafts] 加载草稿失败:', err);
      setError(err instanceof Error ? err.message : '加载草稿失败');
    } finally {
      setLoading(false);
    }
  }, []);

  const handleDeleteDraft = useCallback(async (draftId: string) => {
    setLoading(true);
    try {
      await deleteDraft(draftId);
      await loadDrafts();
    } catch (err) {
      setError(err instanceof Error ? err.message : '删除草稿失败');
      throw err;
    } finally {
      setLoading(false);
    }
  }, [loadDrafts]);

  const handleBatchDeleteDrafts = useCallback(async (draftIds: string[]) => {
    setLoading(true);
    try {
      const result = await batchDeleteDrafts(draftIds);
      await loadDrafts();
      return result;
    } catch (err) {
      setError(err instanceof Error ? err.message : '批量删除草稿失败');
      throw err;
    } finally {
      setLoading(false);
    }
  }, [loadDrafts]);

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

  const loadSourceDocuments = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getSourceDocuments();
      setSourceDocuments(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载源文档失败');
    } finally {
      setLoading(false);
    }
  }, []);

  const handleReviewDraft = useCallback(async (draftId: string, action: 'reviewed' | 'rejected') => {
    try {
      await reviewDraft(draftId, action);
      await loadDrafts();
    } catch (err) {
      setError(err instanceof Error ? err.message : '审核草稿失败');
      throw err;
    }
  }, [loadDrafts]);

  const handleUpdateDraft = useCallback(async (draftId: string, data: Partial<TestCaseDraft>) => {
    try {
      await updateDraft(draftId, data);
      await loadDrafts();
    } catch (err) {
      setError(err instanceof Error ? err.message : '更新草稿失败');
      throw err;
    }
  }, [loadDrafts]);

  const handleImportDrafts = useCallback(async (draftIds: string[]) => {
    try {
      const result = await importDrafts(draftIds);
      await loadDrafts();
      await loadTestCases();
      return result;
    } catch (err) {
      setError(err instanceof Error ? err.message : '导入草稿失败');
      throw err;
    }
  }, [loadDrafts, loadTestCases]);

  const handleGenerateDrafts = useCallback(async (docId: string, params: GenerationParams) => {
    try {
      await generateDrafts(docId, params);
      await loadDrafts();
    } catch (err) {
      setError(err instanceof Error ? err.message : '生成草稿失败');
      throw err;
    }
  }, [loadDrafts]);

  return {
    testCases,
    testRuns,
    snapshots,
    drafts,
    sourceDocuments,
    loading,
    error,
    loadTestCases,
    loadTestRuns,
    loadSnapshots,
    loadDrafts,
    loadSourceDocuments,
    runAllTests: handleRunAllTests,
    runSingleTest: handleRunSingleTest,
    createTestCase: handleCreateTestCase,
    updateTestCase: handleUpdateTestCase,
    deleteTestCase: handleDeleteTestCase,
    batchDeleteTestCases: handleBatchDeleteTestCases,
    batchDeleteTestRuns: handleBatchDeleteTestRuns,
    deleteDraft: handleDeleteDraft,
    batchDeleteDrafts: handleBatchDeleteDrafts,
    compareTestRuns: handleCompareRuns,
    createSnapshot: handleCreateSnapshot,
    reviewDraft: handleReviewDraft,
    updateDraft: handleUpdateDraft,
    importDrafts: handleImportDrafts,
    generateDrafts: handleGenerateDrafts,
  };
}
