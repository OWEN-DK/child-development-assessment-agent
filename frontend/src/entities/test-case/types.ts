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
  passed: boolean;
  results: TestResultItem[];
  executed_at: string;
  execution_time_ms: number;
}

export interface TestRun {
  id: string;
  name: string;
  description: string;
  test_set_id?: string;
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
  age_stages: string[];                     // 替代 age_range
  drafts_per_combination: number;           // 替代 count
  query_types: string[];                    // 新增
  difficulty_levels: string[];              // 替代 difficulty
  llm_model: string;
  temperature: number;
  mode: 'append' | 'overwrite';             // 新增
}

export interface TestCaseDraft {
  id: string;
  source_document_id: string;
  source_document_name?: string;
  query: string;
  age: number;
  domain: string;
  age_stage_label: string;      // 年龄段标签
  draft_index: number;          // 组合内草稿索引
  batch_id: string | null;      // 生成批次 ID
  version: number;              // 乐观锁
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

// SSE 事件类型
export interface DraftSseEventStarted {
  event: 'draft_generation_started';
  total_combinations: number;
  total_drafts: number;
  mode: string;
}

export interface DraftSseEventProgress {
  event: 'draft_combination_progress';
  current_combination: number;
  total_combinations: number;
  domain: string;
  age_stage: string;
  generated: number;
  deduplicated: number;
}

export interface DraftSseEventDeduplication {
  event: 'draft_deduplication';
  domain: string;
  age_stage: string;
  before: number;
  after: number;
  removed: number;
  threshold: number;
}

export interface DraftSseEventCompleted {
  event: 'draft_generation_completed';
  total: number;
  deduplicated: number;
  duration: string;
}

export interface DraftSseEventFailed {
  event: 'draft_generation_failed';
  error: string;
  combination: string;
}

export interface DraftSseEventCancelled {
  event: 'draft_generation_cancelled';
  total: number;
  reason: string;
}

export type DraftSseEvent =
  | DraftSseEventStarted
  | DraftSseEventProgress
  | DraftSseEventDeduplication
  | DraftSseEventCompleted
  | DraftSseEventFailed
  | DraftSseEventCancelled;

// 草稿生成进度
export interface DraftGenerationProgress {
  visible: boolean;
  current: number;
  total: number;
  message: string;
  taskType: string;
  taskId: string;
  generated?: number;
  deduplicated?: number;
}

// 预估结果
export interface EstimateResult {
  combinations: number;
  total_drafts: number;
  domains: string[];
  age_stages: string[];
  drafts_per_combination: number;
  estimated_cost?: number;
}
