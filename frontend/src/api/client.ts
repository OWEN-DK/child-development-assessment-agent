import axios from 'axios';
import { UserInput, FinalReport, StreamingReportData } from '../models';

export interface DocumentRecord {
  file_hash: string;
  file_name: string;
  uploaded_at: string;
  total_pages: number;
}

export interface RagStatus {
  index_ready: boolean;
  storage_dir: string;
  document_count: number;
}

const client = axios.create({
  baseURL: '/', // Vite proxy will handle this
  headers: {
    'Content-Type': 'application/json',
  },
});

export const assessDevelopment = async (data: UserInput): Promise<FinalReport> => {
  const response = await client.post<FinalReport>('/assess', { ...data, is_streaming: false });
  return response.data;
};

export const assessDevelopmentStream = async (
  data: UserInput,
  onData: (data: StreamingReportData) => void,
  onMessage: (chunk: string) => void,
  onDone: () => void,
  onError: (error: string) => void
): Promise<void> => {
  try {
    const response = await fetch('/assess', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ ...data, is_streaming: true }),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: '请求失败' }));
      onError(errorData.detail || `请求失败: ${response.status}`);
      return;
    }

    const reader = response.body?.getReader();
    if (!reader) {
      onError('无法读取响应流');
      return;
    }

    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n\n');
      buffer = lines.pop() || '';

      for (const block of lines) {
        if (!block.trim()) continue;

        const blockLines = block.split('\n');
        let event = '';
        let dataStr = '';

        for (const line of blockLines) {
          if (line.startsWith('event: ')) {
            event = line.substring(7).trim();
          } else if (line.startsWith('data: ')) {
            dataStr = line.substring(6);
          }
        }

        if (!event || !dataStr) continue;

        try {
          if (event === 'data') {
            const data = JSON.parse(dataStr) as StreamingReportData;
            onData(data);
          } else if (event === 'message') {
            const chunk = JSON.parse(dataStr) as string;
            onMessage(chunk);
          } else if (event === 'done' && dataStr === '[DONE]') {
            onDone();
          }
        } catch (e) {
          console.error('解析SSE消息失败:', e, block);
        }
      }
    }
  } catch (err: any) {
    console.error('流式请求失败:', err);
    onError(err.message || '网络请求失败');
  }
};

export const uploadDocument = async (file: File): Promise<{ 
  status: string; 
  filename: string; 
  message: string;
  task_id?: string;
}> => {
  const formData = new FormData();
  formData.append('file', file);
  
  const response = await client.post('/rag/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return response.data;
};

export const getRagStatus = async (): Promise<RagStatus> => {
  const response = await client.get<RagStatus>('/rag/status');
  return response.data;
};

export const getDocuments = async (): Promise<{ documents: DocumentRecord[] }> => {
  const response = await client.get<{ documents: DocumentRecord[] }>('/rag/documents');
  return response.data;
};

export const deleteDocument = async (filename: string): Promise<{ status: string; message: string }> => {
  const response = await client.delete(`/rag/documents/${encodeURIComponent(filename)}`);
  return response.data;
};

export interface UploadTaskStatus {
  task_id: string;
  status: 'pending' | 'processing' | 'success' | 'failed' | 'cancelled';
  filename: string;
  created_at: number;
  message: string;
  error?: string;
  progress?: number;
  stage?: 'pending' | 'parsing' | 'chunking' | 'embedding' | 'indexing' | 'completed';
}

export const getUploadTaskStatus = async (taskId: string): Promise<UploadTaskStatus> => {
  const response = await client.get<UploadTaskStatus>(`/rag/tasks/${taskId}`);
  return response.data;
};

export const getUploadTasks = async (): Promise<{ tasks: UploadTaskStatus[] }> => {
  const response = await client.get<{ tasks: UploadTaskStatus[] }>('/rag/tasks');
  return response.data;
};

export const cancelUploadTask = async (taskId: string): Promise<{ status: string; message: string }> => {
  const response = await client.post<{ status: string; message: string }>(`/rag/tasks/${taskId}/cancel`);
  return response.data;
};

export interface SearchResultItem {
  id: string;
  content: string;
  score: number;
  source_book: string;
  chapter_title?: string;
  page_label?: string;
  target_age_min: number;
  target_age_max: number;
  brain_regions: string[];
  topics: string[];
  file_hash: string;
}

export const searchKnowledge = async (query: string, limit: number = 20): Promise<{ 
  status: string; 
  total: number; 
  results: SearchResultItem[] 
}> => {
  const response = await client.get('/rag/search', {
    params: { query, limit }
  });
  return response.data;
};

// ========== RAG 测试相关接口 ==========
export interface TestCase {
  id: string;
  query: string;
  age: number;
  expected_knowledge_ids: string[];
  expected_keywords: string[];
  description: string;
  created_at: string;
  updated_at: string;
}

export interface TestResultItem {
  knowledge_id: string;
  content: string;
  score: number;
  expected: boolean;
  rank: number;
}

export interface TestResult {
  test_case_id: string;
  query: string;
  age: number;
  precision: number;
  recall: number;
  f1_score: number;
  mrr: number;
  results: TestResultItem[];
  executed_at: string;
  execution_time_ms: number;
}

export interface TestRun {
  id: string;
  name: string;
  description: string;
  test_results: TestResult[];
  overall_precision: number;
  overall_recall: number;
  overall_f1: number;
  overall_mrr: number;
  total_test_cases: number;
  passed_test_cases: number;
  status: string;
  created_at: string;
  completed_at?: string;
  snapshot_id?: string;
}

export interface KnowledgeSnapshot {
  id: string;
  name: string;
  description: string;
  document_count: number;
  document_hashes: string[];
  index_size_bytes: number;
  created_at: string;
  storage_path: string;
}

// 测试用例管理
export const createTestCase = async (data: Omit<TestCase, 'id' | 'created_at' | 'updated_at'>): Promise<TestCase> => {
  const response = await client.post<TestCase>('/rag/test/cases', data);
  return response.data;
};

export const getTestCases = async (): Promise<TestCase[]> => {
  const response = await client.get<TestCase[]>('/rag/test/cases');
  return response.data;
};

export const getTestCase = async (caseId: string): Promise<TestCase> => {
  const response = await client.get<TestCase>(`/rag/test/cases/${caseId}`);
  return response.data;
};

export const updateTestCase = async (caseId: string, data: Partial<TestCase>): Promise<TestCase> => {
  const response = await client.put<TestCase>(`/rag/test/cases/${caseId}`, data);
  return response.data;
};

export const deleteTestCase = async (caseId: string): Promise<{ status: string; message: string }> => {
  const response = await client.delete(`/rag/test/cases/${caseId}`);
  return response.data;
};

// 测试执行
export const runAllTests = async (data?: { name?: string; description?: string; limit?: number }): Promise<{ status: string; test_run: TestRun }> => {
  const response = await client.post('/rag/test/run', data || {});
  return response.data;
};

export const runSingleTest = async (caseId: string, limit: number = 10): Promise<{ status: string; result: TestResult }> => {
  const response = await client.post(`/rag/test/run/${caseId}?limit=${limit}`);
  return response.data;
};

// 测试运行结果
export const getTestRuns = async (): Promise<TestRun[]> => {
  const response = await client.get<TestRun[]>('/rag/test/runs');
  return response.data;
};

export const getTestRun = async (runId: string): Promise<TestRun> => {
  const response = await client.get<TestRun>(`/rag/test/runs/${runId}`);
  return response.data;
};

export const compareTestRuns = async (runId1: string, runId2: string): Promise<{ status: string; comparison: any }> => {
  const response = await client.get(`/rag/test/compare?run_id1=${runId1}&run_id2=${runId2}`);
  return response.data;
};

// 快照管理
export const createSnapshot = async (data?: { name?: string; description?: string }): Promise<{ status: string; snapshot: KnowledgeSnapshot }> => {
  const response = await client.post('/rag/test/snapshots', data || {});
  return response.data;
};

export const getSnapshots = async (): Promise<KnowledgeSnapshot[]> => {
  const response = await client.get<KnowledgeSnapshot[]>('/rag/test/snapshots');
  return response.data;
};

export const getSnapshot = async (snapshotId: string): Promise<KnowledgeSnapshot> => {
  const response = await client.get<KnowledgeSnapshot>(`/rag/test/snapshots/${snapshotId}`);
  return response.data;
};

export const restoreSnapshot = async (snapshotId: string): Promise<{ status: string; message: string }> => {
  const response = await client.post(`/rag/test/snapshots/${snapshotId}/restore`);
  return response.data;
};
