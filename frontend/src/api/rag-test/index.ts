import apiClient from '../client';
import type { TestCase, TestRun, KnowledgeSnapshot, TestResult } from './types';

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
