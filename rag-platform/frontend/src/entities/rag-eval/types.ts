/**
 * RAG 评估实体类型定义
 *
 * 对齐后端 schemas/rag_eval/ 下的 Pydantic 模型
 */

// ==================== 枚举 ====================

/** 难度级别 */
export type DifficultyLevel = 'easy' | 'medium' | 'hard'

/** 草稿状态 */
export type DraftStatus = 'pending' | 'approved' | 'rejected' | 'imported'

/** 测试运行状态 */
export type TestRunStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'

/** 报告状态 */
export type ReportStatus = 'processing' | 'completed' | 'superseded'

/** 调优建议状态 */
export type SuggestionStatus = 'pending' | 'adopted' | 'rejected' | 'ignored'

/** 调优严重性 */
export type Severity = 'critical' | 'warning' | 'info'

/** 调优分类 */
export type TuningCategory = 'retrieval' | 'generation' | 'system' | 'permission'

/** 快照状态 */
export type SnapshotStatus = 'active' | 'invalid' | 'expired'

// ==================== 测试用例 ====================

/** 期望冲突项 */
export interface ExpectedConflict {
  statement_a: string
  source_a: string
  statement_b: string
  source_b: string
}

/** 测试用例 */
export interface TestCase {
  id: string
  tenant_id: string
  query: string
  description: string | null
  expected_knowledge_ids: string[] | null
  expected_keywords: string[] | null
  answer_points_summary: string | null
  difficulty_level: DifficultyLevel
  professional_terms: string[] | null
  relevance_scores: Record<string, number> | null
  relevant_domains: string[] | null
  expected_conflicts: ExpectedConflict[] | null
  source: string
  source_draft_id: string | null
  version: number
  created_at: string
  updated_at: string
}

/** 创建用例请求 */
export interface CreateTestCaseReq {
  query: string
  description?: string
  expected_knowledge_ids?: string[]
  expected_keywords?: string[]
  difficulty_level?: DifficultyLevel
  relevant_domains?: string[]
}

/** 用例列表响应 */
export interface TestCaseListResponse {
  items: TestCase[]
  total: number
}

// ==================== 测试集 ====================

/** 测试集 */
export interface TestSet {
  id: string
  tenant_id: string
  name: string
  description: string | null
  source_type: string
  case_ids: string[] | null
  case_count: number
  visibility: string
  owner_id: string
  created_at: string
}

/** 创建测试集请求 */
export interface CreateTestSetReq {
  name: string
  description?: string
  case_ids?: string[]
  visibility?: string
}

/** 测试集列表响应 */
export interface TestSetListResponse {
  items: TestSet[]
  total: number
}

// ==================== 草稿 ====================

/** 草稿 */
export interface TestCaseDraft {
  id: string
  tenant_id: string
  query: string
  description: string | null
  difficulty_level: DifficultyLevel
  expected_knowledge_ids: string[] | null
  expected_keywords: string[] | null
  answer_points: string | null
  professional_terms: string[] | null
  source_document_id: string | null
  faithfulness_score: number | null
  status: DraftStatus
  version: number
  created_at: string
}

/** 创建草稿请求 */
export interface CreateDraftReq {
  query: string
  description?: string
  difficulty_level?: DifficultyLevel
}

/** 生成草稿请求 */
export interface GenerateDraftReq {
  kb_id: string
  document_ids: string[]
  max_qa_per_chunk?: number
  min_qa_per_chunk?: number
}

/** 草稿列表响应 */
export interface DraftListResponse {
  items: TestCaseDraft[]
  total: number
}

// ==================== 测试运行 ====================

/** 测试运行 */
export interface TestRun {
  id: string
  tenant_id: string
  name: string | null
  status: TestRunStatus
  pipeline_id: string
  pipeline_version: number
  test_set_ids: string[] | null
  snapshot_id: string | null
  total_test_cases: number
  passed_test_cases: number
  overall_score: number | null
  started_at: string | null
  completed_at: string | null
  created_at: string
}

/** 创建运行请求 */
export interface CreateTestRunReq {
  pipeline_id: string
  pipeline_version?: number
  test_set_ids?: string[]
  name?: string
  auto_snapshot?: boolean
}

/** 运行结果 */
export interface TestRunResult {
  id: string
  run_id: string
  test_case_id: string
  query: string
  precision: number | null
  recall: number | null
  f1: number | null
  mrr: number | null
  ndcg: number | null
  actual_answer: string | null
  passed: boolean | null
  error_message: string | null
  execution_time_ms: number | null
}

/** 运行列表响应 */
export interface TestRunListResponse {
  items: TestRun[]
  total: number
}

// ==================== 指标 ====================

/** 单个指标得分 */
export interface MetricScore {
  name: string
  display_name: string
  score: number
  passed: boolean
  weight: number
}

/** 层级指标 */
export interface LayerMetrics {
  layer: string
  scores: MetricScore[]
  avg_score: number
}

/** 跨域指标 */
export interface CrossDomainMetrics {
  domain_activation_accuracy: number
  cross_domain_coverage: number
  conflict_detection_rate: number
  e2e_latency_p95: number
}

/** 域贡献 */
export interface DomainContribution {
  domain_id: string
  domain_name: string | null
  contribution_score: number
  activation_accuracy: number
  chunk_count: number
}

/** 运行指标 */
export interface RunMetrics {
  l1: LayerMetrics
  l2: LayerMetrics
  l3: LayerMetrics
  cross_domain: CrossDomainMetrics | null
  overall_score: number
}

// ==================== 报告 ====================

/** 评估报告 */
export interface EvalReport {
  id: string
  run_id: string
  tenant_id: string
  overall_score: number | null
  l1_score: number | null
  l2_score: number | null
  l3_score: number | null
  cross_domain_score: number | null
  status: ReportStatus
  created_at: string
}

/** 报告列表响应 */
export interface ReportListResponse {
  items: EvalReport[]
  total: number
}

// ==================== 调优 ====================

/** 调优建议 */
export interface TuningSuggestion {
  id: string
  run_id: string
  report_id: string | null
  category: TuningCategory
  severity: Severity
  title: string
  description: string | null
  current_value: string | null
  suggested_value: string | null
  expected_impact: string | null
  conflict_with: string[] | null
  status: SuggestionStatus
  created_at: string
}

/** 配置版本 */
export interface ConfigVersion {
  id: string
  tenant_id: string
  version_number: number
  version_label: string | null
  config_snapshot: Record<string, unknown>
  change_summary: string | null
  created_by: string
  created_at: string
}

// ==================== 快照 ====================

/** 知识库快照 */
export interface KnowledgeSnapshot {
  id: string
  kb_id: string
  tenant_id: string
  name: string | null
  vector_backend_type: string | null
  document_count: number
  chunk_count: number
  status: SnapshotStatus
  expires_at: string | null
  created_at: string
}
