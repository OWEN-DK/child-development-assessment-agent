export interface TestCase {
  id: string;
  query: string;
  age: number;
  expected_knowledge_ids: string[];
  expected_keywords: string[];
  description: string;
  domain: string;
  answer_points: string[];
  professional_terms: string[];
  age_requirement: string;
  relevance_scores: Record<string, number>;
  source_document_id: string;
  test_set_id: string;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface ImportPreviewResult {
  valid_cases: Array<{ index: number; data: Record<string, any> }>;
  invalid_cases: Array<{ index: number; data: Record<string, any>; error: string }>;
  duplicates: Array<{ index: number; data: Record<string, any>; existing_id: string }>;
}

export interface BatchImportRequest {
  cases: Record<string, any>[];
  test_set_id?: string;
}

export interface BatchImportResult {
  imported_count: number;
  failed_count: number;
  test_case_ids: string[];
  errors: string[];
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
  ndcg_at_k: number;
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
  overall_ndcg: number;
  total_test_cases: number;
  passed_test_cases: number;
  status: string;
  created_at: string;
  completed_at?: string;
  snapshot_id?: string;
  config_version_id?: string;
  previous_config_version_id?: string;
  config_snapshot?: Record<string, any>;
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

export interface ChapterInfo {
  title: string;
  page_start: number;
  page_end: number;
  level: number;
}

export interface QualityReport {
  content_completeness: number;
  text_extractability: number;
  chapter_clarity: number;
  suggested_domains: string[];
  warnings: string[];
  raw_text_length: number;
}

export interface SourceDocument {
  id: string;
  title: string;
  file_type: string;
  file_path: string;
  file_hash: string;
  content_summary: string;
  page_count: number;
  chapter_structure: ChapterInfo[];
  quality_report: QualityReport | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface GenerationParams {
  target_domains: string[];
  age_range: [number, number];
  count: number;
  difficulty: string;
  llm_model: string;
  temperature: number;
}

export interface TestCaseDraft {
  id: string;
  source_document_id: string;
  query: string;
  age: number;
  domain: string;
  expected_knowledge_ids: string[];
  expected_keywords: string[];
  description: string;
  answer_points: string[];
  professional_terms: string[];
  age_requirement: string;
  generation_params: GenerationParams | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface TestSet {
  id: string;
  name: string;
  description: string;
  source_type: string;
  test_case_ids: string[];
  created_at: string;
  updated_at: string;
}
