/**
 * RAG 评估 API 客户端
 *
 * 提供测试用例、测试集、草稿、测试运行、报告等 API 调用
 */
import apiClient from '@/shared/api/client'
import type {
  TestCase,
  TestCaseListResponse,
  CreateTestCaseReq,
  TestSet,
  TestSetListResponse,
  CreateTestSetReq,
  TestCaseDraft,
  DraftListResponse,
  CreateDraftReq,
  GenerateDraftReq,
  TestRun,
  TestRunListResponse,
  CreateTestRunReq,
  TestRunResult,
  RunMetrics,
  EvalReport,
  ReportListResponse,
  TuningSuggestion,
  ConfigVersion,
  KnowledgeSnapshot,
  DifficultyLevel,
  DraftStatus,
  TestRunStatus,
} from '@/entities/rag-eval/types'

const BASE = '/rag/eval'

// ==================== 测试用例 ====================

/** 获取测试用例列表 */
export async function getTestCases(params?: {
  page?: number
  page_size?: number
  source?: string
  difficulty?: DifficultyLevel
  search?: string
}): Promise<TestCaseListResponse> {
  const response = await apiClient.get(`${BASE}/test-cases`, { params })
  return response.data ?? response
}

/** 获取测试用例详情 */
export async function getTestCase(caseId: string): Promise<TestCase> {
  const response = await apiClient.get(`${BASE}/test-cases/${caseId}`)
  return response.data ?? response
}

/** 创建测试用例 */
export async function createTestCase(data: CreateTestCaseReq): Promise<TestCase> {
  const response = await apiClient.post(`${BASE}/test-cases`, data)
  return response.data ?? response
}

/** 更新测试用例 */
export async function updateTestCase(caseId: string, data: Partial<CreateTestCaseReq>): Promise<TestCase> {
  const response = await apiClient.put(`${BASE}/test-cases/${caseId}`, data)
  return response.data ?? response
}

/** 删除测试用例 */
export async function deleteTestCase(caseId: string): Promise<void> {
  await apiClient.delete(`${BASE}/test-cases/${caseId}`)
}

/** 批量删除用例 */
export async function batchDeleteTestCases(caseIds: string[]): Promise<void> {
  await apiClient.post(`${BASE}/test-cases/batch-delete`, { case_ids: caseIds })
}

/** 批量导入用例 */
export async function importTestCases(cases: CreateTestCaseReq[]): Promise<TestCase[]> {
  const response = await apiClient.post(`${BASE}/test-cases/import`, { cases })
  return response.data ?? response
}

// ==================== 测试集 ====================

/** 获取测试集列表 */
export async function getTestSets(params?: {
  page?: number
  page_size?: number
}): Promise<TestSetListResponse> {
  const response = await apiClient.get(`${BASE}/test-sets`, { params })
  return response.data ?? response
}

/** 获取测试集详情 */
export async function getTestSet(setId: string): Promise<TestSet> {
  const response = await apiClient.get(`${BASE}/test-sets/${setId}`)
  return response.data ?? response
}

/** 创建测试集 */
export async function createTestSet(data: CreateTestSetReq): Promise<TestSet> {
  const response = await apiClient.post(`${BASE}/test-sets`, data)
  return response.data ?? response
}

/** 更新测试集 */
export async function updateTestSet(setId: string, data: Partial<CreateTestSetReq>): Promise<TestSet> {
  const response = await apiClient.put(`${BASE}/test-sets/${setId}`, data)
  return response.data ?? response
}

/** 删除测试集 */
export async function deleteTestSet(setId: string): Promise<void> {
  await apiClient.delete(`${BASE}/test-sets/${setId}`)
}

/** 添加用例到测试集 */
export async function addCasesToSet(setId: string, caseIds: string[]): Promise<void> {
  await apiClient.post(`${BASE}/test-sets/${setId}/cases`, { case_ids: caseIds })
}

/** 从测试集移除用例 */
export async function removeCasesFromSet(setId: string, caseIds: string[]): Promise<void> {
  await apiClient.delete(`${BASE}/test-sets/${setId}/cases`, { data: { case_ids: caseIds } })
}

// ==================== 草稿 ====================

/** 获取草稿列表 */
export async function getDrafts(params?: {
  page?: number
  page_size?: number
  status?: DraftStatus
  search?: string
}): Promise<DraftListResponse> {
  const response = await apiClient.get(`${BASE}/drafts`, { params })
  return response.data ?? response
}

/** 创建草稿 */
export async function createDraft(data: CreateDraftReq): Promise<TestCaseDraft> {
  const response = await apiClient.post(`${BASE}/drafts`, data)
  return response.data ?? response
}

/** 更新草稿 */
export async function updateDraft(draftId: string, data: Partial<CreateDraftReq>): Promise<TestCaseDraft> {
  const response = await apiClient.put(`${BASE}/drafts/${draftId}`, data)
  return response.data ?? response
}

/** 删除草稿 */
export async function deleteDraft(draftId: string): Promise<void> {
  await apiClient.delete(`${BASE}/drafts/${draftId}`)
}

/** 审核草稿 */
export async function reviewDraft(draftId: string, action: 'approve' | 'reject'): Promise<TestCaseDraft> {
  const response = await apiClient.post(`${BASE}/drafts/${draftId}/review`, { action })
  return response.data ?? response
}

/** 导入草稿为正式用例 */
export async function importDraft(draftId: string): Promise<TestCase> {
  const response = await apiClient.post(`${BASE}/drafts/${draftId}/import`)
  return response.data ?? response
}

/** 生成草稿 */
export async function generateDrafts(data: GenerateDraftReq): Promise<TestCaseDraft[]> {
  const response = await apiClient.post(`${BASE}/drafts/generate`, data)
  return response.data ?? response
}

// ==================== 测试运行 ====================

/** 获取测试运行列表 */
export async function getTestRuns(params?: {
  page?: number
  page_size?: number
  pipeline_id?: string
  status?: TestRunStatus
}): Promise<TestRunListResponse> {
  const response = await apiClient.get(`${BASE}/runs`, { params })
  return response.data ?? response
}

/** 获取运行详情 */
export async function getTestRun(runId: string): Promise<TestRun> {
  const response = await apiClient.get(`${BASE}/runs/${runId}`)
  return response.data ?? response
}

/** 创建测试运行 */
export async function createTestRun(data: CreateTestRunReq): Promise<TestRun> {
  const response = await apiClient.post(`${BASE}/runs`, data)
  return response.data ?? response
}

/** 删除测试运行 */
export async function deleteTestRun(runId: string): Promise<void> {
  await apiClient.delete(`${BASE}/runs/${runId}`)
}

/** 执行测试运行 */
export async function executeTestRun(runId: string): Promise<void> {
  await apiClient.post(`${BASE}/runs/${runId}/execute`)
}

/** 取消测试运行 */
export async function cancelTestRun(runId: string): Promise<void> {
  await apiClient.post(`${BASE}/runs/${runId}/cancel`)
}

/** 获取运行指标 */
export async function getRunMetrics(runId: string): Promise<RunMetrics> {
  const response = await apiClient.get(`${BASE}/runs/${runId}/metrics`)
  return response.data ?? response
}

/** 获取运行结果列表 */
export async function getRunResults(runId: string): Promise<TestRunResult[]> {
  const response = await apiClient.get(`${BASE}/runs/${runId}/results`)
  return (response.data ?? response).items ?? response.data ?? response
}

// ==================== 报告 ====================

/** 获取报告列表 */
export async function getReports(params?: {
  page?: number
  page_size?: number
}): Promise<ReportListResponse> {
  const response = await apiClient.get(`${BASE}/reports`, { params })
  return response.data ?? response
}

/** 获取报告详情 */
export async function getReport(reportId: string): Promise<EvalReport> {
  const response = await apiClient.get(`${BASE}/reports/${reportId}`)
  return response.data ?? response
}

/** 生成报告 */
export async function createReport(runId: string, force = false): Promise<EvalReport> {
  const response = await apiClient.post(`${BASE}/reports`, { run_id: runId, force })
  return response.data ?? response
}

/** 导出报告 */
export async function exportReport(reportId: string, format: string = 'json'): Promise<unknown> {
  const response = await apiClient.get(`${BASE}/reports/${reportId}/export`, { params: { format } })
  return response.data ?? response
}

// ==================== 调优 ====================

/** 获取调优建议 */
export async function getTuningSuggestions(runId: string): Promise<TuningSuggestion[]> {
  const response = await apiClient.get(`${BASE}/runs/${runId}/tuning`)
  return (response.data ?? response).items ?? response.data ?? response
}

/** 采纳建议 */
export async function adoptSuggestion(suggestionId: string): Promise<void> {
  await apiClient.post(`${BASE}/tuning/${suggestionId}/adopt`)
}

/** 拒绝建议 */
export async function rejectSuggestion(suggestionId: string): Promise<void> {
  await apiClient.post(`${BASE}/tuning/${suggestionId}/reject`)
}

/** 忽略建议 */
export async function ignoreSuggestion(suggestionId: string): Promise<void> {
  await apiClient.post(`${BASE}/tuning/${suggestionId}/ignore`)
}

/** 获取配置版本列表 */
export async function getConfigVersions(): Promise<ConfigVersion[]> {
  const response = await apiClient.get(`${BASE}/config-versions`)
  return (response.data ?? response).items ?? response.data ?? response
}

// ==================== 快照 ====================

/** 创建快照 */
export async function createSnapshot(kbId: string, name?: string): Promise<KnowledgeSnapshot> {
  const response = await apiClient.post(`${BASE}/snapshots`, { kb_id: kbId, name })
  return response.data ?? response
}

/** 获取快照列表 */
export async function getSnapshots(kbId?: string): Promise<KnowledgeSnapshot[]> {
  const response = await apiClient.get(`${BASE}/snapshots`, { params: kbId ? { kb_id: kbId } : undefined })
  return (response.data ?? response).items ?? response.data ?? response
}

// ==================== 趋势 ====================

/** 获取趋势数据 */
export async function getTrends(params?: {
  metric?: string
  pipeline_id?: string
}): Promise<unknown> {
  const response = await apiClient.get(`${BASE}/trends`, { params })
  return response.data ?? response
}
