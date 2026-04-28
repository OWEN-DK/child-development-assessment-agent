import type {
  TestDomain,
  TestRunStatus,
  DraftStatus,
  LayerResultStatus,
  IssueSeverity,
  TuningActionStatus,
  TestCaseSource,
} from './enums';

// ─── 通用 ───────────────────────────────────────────

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

// ─── 源文档 ─────────────────────────────────────────

export interface SourceDocument {
  id: string;
  name: string;
  file_hash?: string;
  status: string;
  page_count?: number | null;
  created_at: string | null;
  updated_at: string | null;
}

// ─── 草稿 ───────────────────────────────────────────

export interface TestCaseDraft {
  id: string;
  query: string;
  age: number;
  age_stage_label: string;
  domain: TestDomain;
  description: string | null;
  difficulty_level: string | null;
  expected_knowledge_ids: string[];
  expected_keywords: string[];
  answer_points_summary: string | null;
  answer_points: string | null;
  professional_terms: string[];
  source_document_id: string | null;
  source_document_name: string | null;
  faithfulness_score: number | null;
  status: DraftStatus;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface DraftGenerationConfig {
  max_qa_per_chunk?: number;
  min_qa_per_chunk?: number;
  age_ranges?: string[];
  domains?: TestDomain[];
  difficulty_overrides?: Record<string, string>;
}

// 草稿筛选（本地使用）
export interface DraftFilters {
  status?: DraftStatus;
  domain?: TestDomain;
  search?: string;
  page?: number;
  page_size?: number;
}

// ─── 测试用例 ───────────────────────────────────────

export interface TestCase {
  id: string;
  query: string;
  age: number;
  age_stage_label: string;
  domain: TestDomain;
  description: string | null;
  difficulty_level: string;
  expected_knowledge_ids: string[];
  expected_keywords: string[];
  answer_points_summary: string | null;
  professional_terms: string[];
  source: TestCaseSource;
  source_draft_id: string | null;
  source_document_id: string | null;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface TestCaseFormValues
  extends Pick<TestCase, 'query' | 'age' | 'domain' | 'expected_knowledge_ids' | 'expected_keywords'>,
    Partial<Pick<TestCase, 'age_stage_label' | 'description' | 'answer_points_summary'>> {}

// ─── 测试集 ─────────────────────────────────────────

export interface TestSet {
  id: string;
  name: string;
  description: string | null;
  case_ids: string[];
  test_case_count: number;
  domains: TestDomain[];
  created_at: string;
  updated_at: string;
}

export interface TestSetFormValues {
  name: string;
  description?: string;
  case_ids: string[];
}

// ─── 运行 ───────────────────────────────────────────

export interface TestRun {
  id: string;
  name: string;
  description: string | null;
  test_set_ids: string[];
  custom_case_ids: string[];
  status: TestRunStatus;
  total_test_cases: number;
  passed_test_cases: number;
  progress: number;
  overall_score: number | null;
  l1_metrics: Record<string, unknown> | null;
  l2_metrics: Record<string, unknown> | null;
  l3_metrics: Record<string, unknown> | null;
  diagnosis: Record<string, unknown> | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface TestRunFormValues {
  name: string;
  test_set_ids: string[];
}

export interface TestRunResult {
  id: string;
  run_id: string;
  case_id: string;
  query: string;
  domain: TestDomain;
  precision: number;
  recall: number;
  f1: number;
  mrr: number;
  faithfulness: number;
  relevancy: number;
  groundedness: number;
  passed: boolean;
  error_message: string | null;
  duration_ms: number;
}

export interface RunComparison {
  run1: TestRun;
  run2: TestRun;
  metrics_diff: Record<string, { before: number; after: number; delta: number }>;
}

// ─── 三层指标 ───────────────────────────────────────

export interface MetricScore {
  value: number;
  passed: boolean;
  threshold: number;
  details: Record<string, unknown>;
}

export interface LayerMetrics {
  [metricName: string]: MetricScore;
}

export interface RunMetrics {
  l1: LayerMetrics;
  l2: LayerMetrics;
  l3: LayerMetrics;
  overall_score: number;
}

// ─── 六层诊断 ───────────────────────────────────────

export interface LayerIssue {
  severity: IssueSeverity;
  category: string;
  description: string;
  affected_items: string[];
  suggestion: string | null;
}

export interface LayerResult {
  layer: number;
  name: string;
  status: LayerResultStatus;
  score: number;
  issues: LayerIssue[];
  details: Record<string, unknown>;
}

export interface DiagnosisResult {
  layer1: LayerResult;
  layer2: LayerResult;
  layer3: LayerResult;
  layer4: LayerResult;
  layer5: LayerResult;
  layer6: LayerResult;
  overall_health: number;
  total_issues: number;
  critical_issues: number;
}

// ─── 报告 ───────────────────────────────────────────

export interface EvalReport {
  id: string;
  run_id: string;
  run_name: string;
  overall_score: number;
  status: TestRunStatus;
  metrics: RunMetrics | null;
  diagnosis: DiagnosisResult | null;
  markdown_content: string;
  total_test_cases: number;
  passed_test_cases: number;
  duration_seconds: number;
  created_at: string;
}

export interface TrendData {
  label: string;
  value: number;
  created_at: string;
  run_id: string;
  metric_name: string;
}

// ─── 调优 ───────────────────────────────────────────

export interface TuningSuggestion {
  id: string;
  run_id: string;
  category: string;
  severity: IssueSeverity;
  title: string;
  description: string;
  current_value: string | number | Record<string, unknown>;
  suggested_value: string | number | Record<string, unknown>;
  config_key: string;
  status: TuningActionStatus;
  conflict_ids: string[];
  created_at: string;
}

export interface ConfigVersion {
  id: string;
  version: string;
  created_at: string;
  description: string | null;
}

// ─── SSE 事件 ───────────────────────────────────────

export interface SSEEvent {
  type: string;
  data: Record<string, unknown>;
}

// ─── 快照 ───────────────────────────────────────────

export interface Snapshot {
  id: string;
  name: string;
  description: string | null;
  run_id: string | null;
  version: string;
  created_at: string;
}

export interface KnowledgeSnapshot {
  id: string;
  name: string;
  description: string | null;
  config_version_id: string | null;
  document_count: number;
  created_at: string;
}

// ─── 筛选 ───────────────────────────────────────────

export interface TestCaseFilters {
  domain?: TestDomain;
  age_stage_label?: string;
  source?: TestCaseSource;
  search?: string;
  page?: number;
  page_size?: number;
}

export interface RunFilters {
  status?: TestRunStatus;
  page?: number;
  page_size?: number;
}
