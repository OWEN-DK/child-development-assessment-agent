import apiClient from '@shared/api/client';
import type { TestCase, TestRun, KnowledgeSnapshot, TestResult, ImportPreviewResult, BatchImportRequest, BatchImportResult, SourceDocument, TestCaseDraft, TestSet, GenerationParams } from './types';

export type { TestCase, TestRun, KnowledgeSnapshot, TestResult, ImportPreviewResult, BatchImportRequest, BatchImportResult, SourceDocument, TestCaseDraft, TestSet, GenerationParams } from './types';

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

export const batchDeleteTestCases = async (ids: string[]): Promise<{ status: string; message: string; deleted_count: number }> => {
  const response = await apiClient.post('/rag/test/cases/batch/delete', { ids });
  return response.data;
};

export const batchDeleteTestRuns = async (ids: string[]): Promise<{ status: string; message: string; deleted_count: number }> => {
  const response = await apiClient.post('/rag/test/runs/batch/delete', { ids });
  return response.data;
};

export const cancelTestRun = async (runId: string): Promise<{ status: string }> => {
  const response = await apiClient.post(`/api/v1/tasks/test_run/${runId}/cancel`);
  return response.data;
};

export const deleteDraft = async (draftId: string): Promise<{ status: string; message: string }> => {
  const response = await apiClient.post(`/rag/test/drafts/${draftId}/delete`);
  return response.data;
};

export const batchDeleteDrafts = async (ids: string[]): Promise<{ status: string; message: string; deleted_count: number }> => {
  const response = await apiClient.post('/rag/test/drafts/batch/delete', { ids });
  return response.data;
};

export const runAllTests = async (data?: { name?: string; description?: string; limit?: number; test_set_ids?: string[] }): Promise<{ run_id: string; status: string; message: string }> => {
  const response = await apiClient.post('/rag/test/run', data || {}, {
    timeout: 300000, // 5 分钟超时，批量测试通常远超 10 秒
  });
  return response.data;
};

export const runSingleTest = async (caseId: string, limit: number = 10): Promise<{ status: string; result: TestResult }> => {
  const response = await apiClient.post(`/rag/test/run/${caseId}?limit=${limit}`, undefined, {
    timeout: 120000,
  });
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

export const uploadSourceDocument = async (file: File, title?: string): Promise<{ status: string; document: SourceDocument; auto_generate_started?: boolean; task_id?: string; message?: string }> => {
  const formData = new FormData();
  formData.append('file', file);
  if (title) formData.append('title', title);
  formData.append('auto_generate', 'false');
  const response = await apiClient.post('/rag/test/documents/upload', formData, {
    timeout: 120000,
  });
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

export const generateDrafts = async (docId: string, params: GenerationParams): Promise<{ task_id: string; combinations: number; estimated_drafts: number; message: string }> => {
  const response = await apiClient.post(`/rag/test/documents/${docId}/generate-drafts`, { params }, {
    timeout: 180000,
  });
  return response.data;
};

export const estimateDraftGeneration = async (
  docId: string,
  params: GenerationParams,
): Promise<{ combinations: number; total_drafts: number; domains: string[]; age_stages: string[]; drafts_per_combination: number }> => {
  const response = await apiClient.post(`/rag/test/documents/${docId}/generate-drafts/estimate`, { params });
  return response.data;
};

export const getDraftConfig = async (): Promise<{
    default_domains: string[];
    default_age_stages: string[];
    default_drafts_per_combination: number;
    default_query_types: string[];
    default_difficulty_levels: string[];
    default_model: string;
    deduplication_threshold: number;
    batch_size: number;
    combination_interval_seconds: number;
    max_concurrent_tasks: number;
    max_tokens_per_generation: number;
    max_memory_mb: number;
    max_llm_retries: number;
    supported_domains: string[];
    age_stages: Array<{ label: string; age_min_months: number; age_max_months: number }>;
    query_types: Array<{ name: string; description: string }>;
    difficulty_levels: Array<{ name: string; description: string }>;
}> => {
    const response = await apiClient.get('/api/v1/config?category=rag.testing');
    return response.data;
};

export const getAvailableModels = async (): Promise<Array<{ key: string; name: string; cost_input: number; cost_output: number }>> => {
    const response = await apiClient.get('/api/v1/config?category=models.llm');
  const config = response.data;
  const models: Array<{ key: string; name: string; cost_input: number; cost_output: number }> = [];
  
  if (config?.llm_providers) {
    for (const provider of config.llm_providers) {
      if (provider.models && Array.isArray(provider.models)) {
        for (const model of provider.models) {
          // 显示所有模型，即使价格为 0（后端已配置的模型都应该显示）
          models.push({
            key: model.key || model.name,
            name: model.name,
            cost_input: model.cost_input || 0,
            cost_output: model.cost_output || 0,
          });
        }
      }
    }
  }
  
  // 去重（同一模型可能在多个 provider 中）
  const uniqueModels = models.filter(
    (model, index, self) => index === self.findIndex(m => m.key === model.key)
  );
  
  return uniqueModels;
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

export const createDraft = async (data: {
  source_document_id: string;
  query: string;
  age: number;
  domain: string;
  expected_knowledge_ids?: string[];
  expected_keywords?: string[];
  description?: string;
  answer_points?: string[];
  professional_terms?: string[];
  age_requirement?: string;
}): Promise<TestCaseDraft> => {
  const response = await apiClient.post<TestCaseDraft>('/rag/test/drafts', data);
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

export const batchDeleteTestSets = async (ids: string[]): Promise<{ status: string; message: string; deleted_count: number }> => {
  const response = await apiClient.post('/rag/test/sets/batch/delete', { ids });
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
