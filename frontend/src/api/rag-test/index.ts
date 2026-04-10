import apiClient from '../client';
import type { TestCase, TestRun, KnowledgeSnapshot, TestResult, ImportPreviewResult, BatchImportRequest, BatchImportResult, SourceDocument, TestCaseDraft, TestSet, GenerationParams } from './types';

export const createTestCase = async (data: Omit<TestCase, 'id' | 'created_at' | 'updated_at'>): Promise<TestCase> => {
  const response = await apiClient.post<TestCase>('/rag/test/cases', data);
  return response.data;
};

export const getTestCases = async (): Promise<TestCase[]> => {
  const response = await apiClient.get<TestCase[]>('/rag/test/cases');
  return response.data;
};

export const getTestCase = async (caseId: string): Promise<TestCase> => {
  const response = await apiClient.get<TestCase>(`/rag/test/cases/${caseId}`);
  return response.data;
};

export const updateTestCase = async (caseId: string, data: Partial<TestCase>): Promise<TestCase> => {
  const response = await apiClient.put<TestCase>(`/rag/test/cases/${caseId}`, data);
  return response.data;
};

export const deleteTestCase = async (caseId: string): Promise<{ status: string; message: string }> => {
  const response = await apiClient.delete(`/rag/test/cases/${caseId}`);
  return response.data;
};

export const runAllTests = async (data?: { name?: string; description?: string; limit?: number }): Promise<{ status: string; test_run: TestRun }> => {
  const response = await apiClient.post('/rag/test/run', data || {});
  return response.data;
};

export const runSingleTest = async (caseId: string, limit: number = 10): Promise<{ status: string; result: TestResult }> => {
  const response = await apiClient.post(`/rag/test/run/${caseId}?limit=${limit}`);
  return response.data;
};

export const getTestRuns = async (): Promise<TestRun[]> => {
  const response = await apiClient.get<TestRun[]>('/rag/test/runs');
  return response.data;
};

export const getTestRun = async (runId: string): Promise<TestRun> => {
  const response = await apiClient.get<TestRun>(`/rag/test/runs/${runId}`);
  return response.data;
};

export const compareTestRuns = async (runId1: string, runId2: string): Promise<{ status: string; comparison: any }> => {
  const response = await apiClient.get(`/rag/test/compare?run_id1=${runId1}&runId2=${runId2}`);
  return response.data;
};

export const createSnapshot = async (data?: { name?: string; description?: string }): Promise<{ status: string; snapshot: KnowledgeSnapshot }> => {
  const response = await apiClient.post('/rag/test/snapshots', data || {});
  return response.data;
};

export const getSnapshots = async (): Promise<KnowledgeSnapshot[]> => {
  const response = await apiClient.get<KnowledgeSnapshot[]>('/rag/test/snapshots');
  return response.data;
};

export const getSnapshot = async (snapshotId: string): Promise<KnowledgeSnapshot> => {
  const response = await apiClient.get<KnowledgeSnapshot>(`/rag/test/snapshots/${snapshotId}`);
  return response.data;
};

export const restoreSnapshot = async (snapshotId: string): Promise<{ status: string; message: string }> => {
  const response = await apiClient.post(`/rag/test/snapshots/${snapshotId}/restore`);
  return response.data;
};

export const previewImportCases = async (file: File): Promise<ImportPreviewResult> => {
  const formData = new FormData();
  formData.append('file', file);
  const response = await apiClient.post<ImportPreviewResult>('/rag/test/cases/import/preview', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
};

export const batchImportCases = async (data: BatchImportRequest): Promise<BatchImportResult> => {
  const response = await apiClient.post<BatchImportResult>('/rag/test/cases/batch', data);
  return response.data;
};

export const uploadSourceDocument = async (file: File, title?: string): Promise<{ status: string; document: SourceDocument }> => {
  const formData = new FormData();
  formData.append('file', file);
  if (title) formData.append('title', title);
  formData.append('auto_generate', 'true');
  const response = await apiClient.post('/rag/test/documents/upload', formData);
  return response.data;
};

export const getSourceDocuments = async (): Promise<SourceDocument[]> => {
  const response = await apiClient.get<SourceDocument[]>('/rag/test/documents');
  return response.data;
};

export const getSourceDocument = async (docId: string): Promise<SourceDocument> => {
  const response = await apiClient.get<SourceDocument>(`/rag/test/documents/${docId}`);
  return response.data;
};

export const deleteSourceDocument = async (docId: string): Promise<{ status: string; message: string }> => {
  const response = await apiClient.delete(`/rag/test/documents/${docId}`);
  return response.data;
};

export const generateDrafts = async (docId: string, params: GenerationParams): Promise<{ status: string; drafts: TestCaseDraft[] }> => {
  const response = await apiClient.post(`/rag/test/documents/${docId}/generate-drafts`, { params });
  return response.data;
};

export const getDrafts = async (sourceDocumentId?: string): Promise<TestCaseDraft[]> => {
  const url = sourceDocumentId ? `/rag/test/drafts?source_document_id=${sourceDocumentId}` : '/rag/test/drafts';
  const response = await apiClient.get<TestCaseDraft[]>(url);
  return response.data;
};

export const getDraft = async (draftId: string): Promise<TestCaseDraft> => {
  const response = await apiClient.get<TestCaseDraft>(`/rag/test/drafts/${draftId}`);
  return response.data;
};

export const updateDraft = async (draftId: string, data: Partial<TestCaseDraft>): Promise<TestCaseDraft> => {
  const response = await apiClient.put<TestCaseDraft>(`/rag/test/drafts/${draftId}`, data);
  return response.data;
};

export const reviewDraft = async (draftId: string, action: 'reviewed' | 'rejected'): Promise<{ status: string; draft: TestCaseDraft }> => {
  const response = await apiClient.post(`/rag/test/drafts/${draftId}/review?action=${action}`);
  return response.data;
};

export const importDrafts = async (draftIds: string[]): Promise<BatchImportResult> => {
  const response = await apiClient.post('/rag/test/drafts/import', { draft_ids: draftIds });
  return response.data;
};

export const createTestSet = async (data: { name: string; description?: string; source_type?: string }): Promise<{ status: string; test_set: TestSet }> => {
  const response = await apiClient.post('/rag/test/sets', data);
  return response.data;
};

export const getTestSets = async (): Promise<TestSet[]> => {
  const response = await apiClient.get<TestSet[]>('/rag/test/sets');
  return response.data;
};

export const getTestSet = async (setId: string): Promise<TestSet> => {
  const response = await apiClient.get<TestSet>(`/rag/test/sets/${setId}`);
  return response.data;
};

export const updateTestSet = async (setId: string, data: Partial<TestSet>): Promise<TestSet> => {
  const response = await apiClient.put<TestSet>(`/rag/test/sets/${setId}`, data);
  return response.data;
};

export const deleteTestSet = async (setId: string): Promise<{ status: string; message: string }> => {
  const response = await apiClient.delete(`/rag/test/sets/${setId}`);
  return response.data;
};

export const addCasesToSet = async (setId: string, caseIds: string[]): Promise<TestSet> => {
  const response = await apiClient.post(`/rag/test/sets/${setId}/cases`, { case_ids: caseIds });
  return response.data;
};

export const removeCasesFromSet = async (setId: string, caseIds: string[]): Promise<TestSet> => {
  const response = await apiClient.delete(`/rag/test/sets/${setId}/cases`, { params: { case_ids: caseIds } });
  return response.data;
};

export const exportTestSet = async (setId: string): Promise<TestCase[]> => {
  const response = await apiClient.get<TestCase[]>(`/rag/test/sets/${setId}/export`);
  return response.data;
};
