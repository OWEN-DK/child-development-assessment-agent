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
