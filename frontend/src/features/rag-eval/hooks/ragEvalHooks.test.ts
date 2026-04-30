/**
 * RAG 评估模块 TanStack Query Hooks 测试
 *
 * 覆盖 useDrafts / useTestCases / useTestSets / useTestRuns /
 * useMetrics / useReports / useTuning / useSnapshots 的核心查询和变更逻辑。
 */

import React from 'react';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';

import * as draftsApi from '@/api/rag-eval/drafts';
import * as casesApi from '@/api/rag-eval/cases';
import * as runsApi from '@/api/rag-eval/runs';
import * as metricsApi from '@/api/rag-eval/metrics';
import * as reportsApi from '@/api/rag-eval/reports';
import * as tuningApi from '@/api/rag-eval/tuning';
import * as snapshotsApi from '@/api/rag-eval/snapshots';

import { useDrafts, useDraft, useCreateDrafts, useDeleteDrafts } from './useDrafts';
import { useTestCases, useCreateTestCase, useDeleteTestCase } from './useTestCases';
import { useTestSets, useTestSet, useCreateTestSet, useDeleteTestSet } from './useTestSets';
import { useTestRuns, useTestRun, useCreateRun, useCompareRuns } from './useTestRuns';
import { useRunMetrics, useRunDiagnosis, useTriggerEvaluation } from './useMetrics';
import { useReports, useReport, useGenerateReport, useTrends } from './useReports';
import { useTuningSuggestions, useAdoptSuggestion, useRejectSuggestion, useConfigVersions, useRollbackConfig } from './useTuning';
import { useSnapshots, useSnapshot, useCreateSnapshot, useRestoreSnapshot } from './useSnapshots';

/* ═══════════════════ Mock 数据 ═══════════════════ */

const mockDraftsResponse = {
  items: [{
    id: 'draft-1', query: '测试问题', age: 3, age_stage_label: '2-3y',
    domain: 'language' as const, description: null, difficulty_level: 'medium',
    expected_knowledge_ids: ['k1'], expected_keywords: ['关键词'],
    answer_points_summary: null, answer_points: null, professional_terms: [],
    source_document_id: 'doc-1', source_document_name: 'test.pdf',
    faithfulness_score: 0.85, status: 'pending' as const, version: 1,
    created_at: '2026-04-28T00:00:00Z', updated_at: '2026-04-28T00:00:00Z',
  }],
  total: 1, page: 1, page_size: 20,
};

const mockTestCasesResponse = {
  items: [{
    id: 'case-1', query: '用例问题', age: 2, age_stage_label: '1-2y',
    domain: 'cognitive' as const, description: null, difficulty_level: 'easy',
    expected_knowledge_ids: ['k1', 'k2'], expected_keywords: ['认知'],
    answer_points_summary: '要点', professional_terms: [],
    source: 'manual' as const, source_draft_id: null, source_document_id: null,
    version: 1, created_at: '2026-04-28T00:00:00Z', updated_at: '2026-04-28T00:00:00Z',
  }],
  total: 1, page: 1, page_size: 20,
};

const mockTestSetsResponse = [{
  id: 'set-1', name: '测试集A', description: '描述',
  source_type: 'manual', case_count: 1, case_ids: ['case-1'],
  created_at: '2026-04-28T00:00:00Z', updated_at: '2026-04-28T00:00:00Z',
}];

const mockRunsResponse = {
  items: [{
    id: 'run-1', name: '运行1', description: null,
    test_set_ids: ['set-1'], custom_case_ids: [],
    status: 'completed' as const, total_test_cases: 10, passed_test_cases: 8,
    progress: 100, overall_score: 0.82,
    l1_metrics: null, l2_metrics: null, l3_metrics: null, diagnosis: null,
    started_at: '2026-04-28T00:00:00Z', completed_at: '2026-04-28T00:01:00Z',
    created_at: '2026-04-28T00:00:00Z',
  }],
  total: 1, page: 1, page_size: 20,
};

const mockRunMetrics = {
  l1: { precision: { value: 0.85, passed: true, threshold: 0.7, details: {} } },
  l2: { faithfulness: { value: 0.9, passed: true, threshold: 0.6, details: {} } },
  l3: { rule_compliance: { value: 1.0, passed: true, threshold: 0.8, details: {} } },
  overall_score: 0.88,
};

const mockReportsResponse = {
  items: [{
    id: 'rpt-1', run_id: 'run-1', run_name: '运行1',
    overall_score: 0.82, status: 'completed' as const,
    metrics: mockRunMetrics, diagnosis: null,
    markdown_content: '# 报告', total_test_cases: 10,
    passed_test_cases: 8, duration_seconds: 60,
    created_at: '2026-04-28T00:00:00Z',
  }],
  total: 1, page: 1, page_size: 20,
};

const mockSuggestions = [{
  id: 'sug-1', run_id: 'run-1', category: 'retrieval',
  severity: 'warning' as const, title: '增加 Top-K',
  description: '建议提高检索数量', current_value: 5, suggested_value: 10,
  config_key: 'rag.retrieval.top_k', status: 'pending' as const,
  conflict_ids: [], created_at: '2026-04-28T00:00:00Z',
}];

const mockSnapshots = [{
  id: 'snap-1', name: '快照1', description: null,
  config_version_id: null, document_count: 50,
  created_at: '2026-04-28T00:00:00Z',
}];

/* ═══════════════════ 工具函数 ═══════════════════ */

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(QueryClientProvider, { client: queryClient }, children);
  };
}

/* ═══════════════════ Mock 注册 ═══════════════════ */

vi.mock('@/api/rag-eval/drafts', () => ({
  getDrafts: vi.fn(),
  getDraft: vi.fn(),
  updateDraft: vi.fn(),
  startGeneration: vi.fn(),
  reviewDraft: vi.fn(),
  deleteDrafts: vi.fn(),
  getSourceDocuments: vi.fn(),
  getSourceDocument: vi.fn(),
  deleteSourceDocument: vi.fn(),
}));

vi.mock('@/api/rag-eval/cases', () => ({
  getTestCases: vi.fn(),
  getTestCase: vi.fn(),
  createTestCase: vi.fn(),
  updateTestCase: vi.fn(),
  deleteTestCase: vi.fn(),
  batchDeleteTestCases: vi.fn(),
  importTestCases: vi.fn(),
  getTestSets: vi.fn(),
  getTestSet: vi.fn(),
  createTestSet: vi.fn(),
  updateTestSet: vi.fn(),
  deleteTestSet: vi.fn(),
  addCasesToSet: vi.fn(),
  removeCasesFromSet: vi.fn(),
  exportTestSet: vi.fn(),
}));

vi.mock('@/api/rag-eval/runs', () => ({
  getRuns: vi.fn(),
  getRun: vi.fn(),
  createRun: vi.fn(),
  deleteRun: vi.fn(),
  batchDeleteRuns: vi.fn(),
  executeSingleCase: vi.fn(),
  getRunStreamUrl: vi.fn(),
  compareRuns: vi.fn(),
}));

vi.mock('@/api/rag-eval/metrics', () => ({
  getRunMetrics: vi.fn(),
  getRunDiagnosis: vi.fn(),
  triggerEvaluation: vi.fn(),
}));

vi.mock('@/api/rag-eval/reports', () => ({
  getReports: vi.fn(),
  getReport: vi.fn(),
  generateReport: vi.fn(),
  exportReport: vi.fn(),
  getTrends: vi.fn(),
}));

vi.mock('@/api/rag-eval/tuning', () => ({
  getTuningSuggestions: vi.fn(),
  adoptSuggestion: vi.fn(),
  rejectSuggestion: vi.fn(),
  ignoreSuggestion: vi.fn(),
  getConfigVersions: vi.fn(),
  rollbackConfigVersion: vi.fn(),
}));

vi.mock('@/api/rag-eval/snapshots', () => ({
  getSnapshots: vi.fn(),
  getSnapshot: vi.fn(),
  createSnapshot: vi.fn(),
  restoreSnapshot: vi.fn(),
}));

/* ═══════════════════ useDrafts ═══════════════════ */

describe('useDrafts', () => {
  beforeEach(() => {
    vi.mocked(draftsApi.getDrafts).mockResolvedValue(mockDraftsResponse);
  });
  afterEach(() => vi.clearAllMocks());

  it('加载完成后返回草稿列表', async () => {
    const { result } = renderHook(() => useDrafts(), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.items).toHaveLength(1);
    expect(result.current.data?.items[0].query).toBe('测试问题');
  });

  it('调用 getDrafts 时传递筛选参数', async () => {
    const filters = { domain: 'language', page: 1 };
    renderHook(() => useDrafts(filters), { wrapper: createWrapper() });
    await waitFor(() => expect(draftsApi.getDrafts).toHaveBeenCalledWith(filters));
  });

  it('API 拒绝时进入错误状态', async () => {
    vi.mocked(draftsApi.getDrafts).mockRejectedValue(new Error('网络错误'));
    const { result } = renderHook(() => useDrafts(), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toBeInstanceOf(Error);
  });
});

describe('useDraft', () => {
  afterEach(() => vi.clearAllMocks());

  it('传入有效 ID 时获取草稿详情', async () => {
    vi.mocked(draftsApi.getDraft).mockResolvedValue(mockDraftsResponse.items[0]);
    const { result } = renderHook(() => useDraft('draft-1'), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.id).toBe('draft-1');
  });

  it('enabled 为 false 时不发起请求', () => {
    renderHook(() => useDraft(''), { wrapper: createWrapper() });
    expect(draftsApi.getDraft).not.toHaveBeenCalled();
  });
});

describe('useCreateDrafts', () => {
  afterEach(() => vi.clearAllMocks());

  it('mutate 时调用 startGeneration', async () => {
    vi.mocked(draftsApi.startGeneration).mockResolvedValue({ batch_id: 'batch-1' });
    const { result } = renderHook(() => useCreateDrafts(), { wrapper: createWrapper() });
    result.current.mutate({ documentId: 'doc-1' });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(draftsApi.startGeneration).toHaveBeenCalledWith('doc-1', undefined);
  });
});

describe('useDeleteDrafts', () => {
  afterEach(() => vi.clearAllMocks());

  it('mutate 时调用 deleteDrafts', async () => {
    vi.mocked(draftsApi.deleteDrafts).mockResolvedValue(undefined);
    const { result } = renderHook(() => useDeleteDrafts(), { wrapper: createWrapper() });
    result.current.mutate(['draft-1', 'draft-2']);
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(draftsApi.deleteDrafts).toHaveBeenCalledWith(['draft-1', 'draft-2']);
  });
});

/* ═══════════════════ useTestCases ═══════════════════ */

describe('useTestCases', () => {
  beforeEach(() => {
    vi.mocked(casesApi.getTestCases).mockResolvedValue(mockTestCasesResponse);
  });
  afterEach(() => vi.clearAllMocks());

  it('加载完成后返回用例列表', async () => {
    const { result } = renderHook(() => useTestCases(), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.items).toHaveLength(1);
    expect(result.current.data?.items[0].domain).toBe('cognitive');
  });

  it('传递筛选参数', async () => {
    const filters = { domain: 'cognitive', page: 1 };
    renderHook(() => useTestCases(filters), { wrapper: createWrapper() });
    await waitFor(() => expect(casesApi.getTestCases).toHaveBeenCalledWith(filters));
  });
});

describe('useCreateTestCase', () => {
  afterEach(() => vi.clearAllMocks());

  it('mutate 时调用 createTestCase', async () => {
    const newCase = mockTestCasesResponse.items[0];
    vi.mocked(casesApi.createTestCase).mockResolvedValue(newCase);
    const { result } = renderHook(() => useCreateTestCase(), { wrapper: createWrapper() });
    const input = {
      query: '用例问题', age: 2, domain: 'cognitive' as const,
      expected_knowledge_ids: ['k1'], expected_keywords: ['认知'],
      difficulty_level: 'easy' as const,
    };
    result.current.mutate(input);
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(casesApi.createTestCase).toHaveBeenCalledWith(input);
  });
});

describe('useDeleteTestCase', () => {
  afterEach(() => vi.clearAllMocks());

  it('mutate 时调用 deleteTestCase', async () => {
    vi.mocked(casesApi.deleteTestCase).mockResolvedValue(undefined);
    const { result } = renderHook(() => useDeleteTestCase(), { wrapper: createWrapper() });
    result.current.mutate('case-1');
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(casesApi.deleteTestCase).toHaveBeenCalledWith('case-1');
  });
});

/* ═══════════════════ useTestSets ═══════════════════ */

describe('useTestSets', () => {
  beforeEach(() => {
    vi.mocked(casesApi.getTestSets).mockResolvedValue(mockTestSetsResponse);
  });
  afterEach(() => vi.clearAllMocks());

  it('加载完成后返回测试集列表', async () => {
    const { result } = renderHook(() => useTestSets(), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toHaveLength(1);
    expect(result.current.data?.[0].name).toBe('测试集A');
  });
});

describe('useTestSet', () => {
  afterEach(() => vi.clearAllMocks());

  it('传入有效 ID 时获取测试集详情', async () => {
    vi.mocked(casesApi.getTestSet).mockResolvedValue(mockTestSetsResponse[0]);
    const { result } = renderHook(() => useTestSet('set-1'), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.id).toBe('set-1');
  });

  it('enabled 为 false 时不发起请求', () => {
    renderHook(() => useTestSet(''), { wrapper: createWrapper() });
    expect(casesApi.getTestSet).not.toHaveBeenCalled();
  });
});

describe('useCreateTestSet', () => {
  afterEach(() => vi.clearAllMocks());

  it('mutate 时调用 createTestSet', async () => {
    vi.mocked(casesApi.createTestSet).mockResolvedValue(mockTestSetsResponse[0]);
    const { result } = renderHook(() => useCreateTestSet(), { wrapper: createWrapper() });
    result.current.mutate({ name: '测试集A', description: '描述', case_ids: ['case-1'] });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(casesApi.createTestSet).toHaveBeenCalled();
  });
});

describe('useDeleteTestSet', () => {
  afterEach(() => vi.clearAllMocks());

  it('mutate 时调用 deleteTestSet', async () => {
    vi.mocked(casesApi.deleteTestSet).mockResolvedValue(undefined);
    const { result } = renderHook(() => useDeleteTestSet(), { wrapper: createWrapper() });
    result.current.mutate('set-1');
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(casesApi.deleteTestSet).toHaveBeenCalledWith('set-1');
  });
});

/* ═══════════════════ useTestRuns ═══════════════════ */

describe('useTestRuns', () => {
  beforeEach(() => {
    vi.mocked(runsApi.getRuns).mockResolvedValue(mockRunsResponse);
  });
  afterEach(() => vi.clearAllMocks());

  it('加载完成后返回运行列表', async () => {
    const { result } = renderHook(() => useTestRuns(), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.items).toHaveLength(1);
    expect(result.current.data?.items[0].status).toBe('completed');
  });
});

describe('useTestRun', () => {
  afterEach(() => vi.clearAllMocks());

  it('传入有效 ID 时获取运行详情', async () => {
    vi.mocked(runsApi.getRun).mockResolvedValue(mockRunsResponse.items[0]);
    const { result } = renderHook(() => useTestRun('run-1'), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.id).toBe('run-1');
  });
});

describe('useCreateRun', () => {
  afterEach(() => vi.clearAllMocks());

  it('mutate 时调用 createRun', async () => {
    vi.mocked(runsApi.createRun).mockResolvedValue(mockRunsResponse.items[0]);
    const { result } = renderHook(() => useCreateRun(), { wrapper: createWrapper() });
    result.current.mutate({ name: '运行1', test_set_ids: ['set-1'] });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(runsApi.createRun).toHaveBeenCalledWith({ name: '运行1', test_set_ids: ['set-1'] });
  });
});

describe('useCompareRuns', () => {
  afterEach(() => vi.clearAllMocks());

  it('两个 ID 均有效时发起对比请求', async () => {
    const mockComparison = {
      run1: mockRunsResponse.items[0], run2: mockRunsResponse.items[0],
      metrics_diff: {},
    };
    vi.mocked(runsApi.compareRuns).mockResolvedValue(mockComparison);
    const { result } = renderHook(() => useCompareRuns('run-1', 'run-2'), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(runsApi.compareRuns).toHaveBeenCalledWith('run-1', 'run-2');
  });

  it('任一 ID 为空时不发起请求', () => {
    renderHook(() => useCompareRuns('', 'run-2'), { wrapper: createWrapper() });
    expect(runsApi.compareRuns).not.toHaveBeenCalled();
  });
});

/* ═══════════════════ useMetrics ═══════════════════ */

describe('useRunMetrics', () => {
  afterEach(() => vi.clearAllMocks());

  it('传入有效 runId 时获取三层指标', async () => {
    vi.mocked(metricsApi.getRunMetrics).mockResolvedValue(mockRunMetrics);
    const { result } = renderHook(() => useRunMetrics('run-1'), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.overall_score).toBe(0.88);
  });

  it('runId 为空时不发起请求', () => {
    renderHook(() => useRunMetrics(''), { wrapper: createWrapper() });
    expect(metricsApi.getRunMetrics).not.toHaveBeenCalled();
  });
});

describe('useRunDiagnosis', () => {
  afterEach(() => vi.clearAllMocks());

  it('传入有效 runId 时获取六层诊断', async () => {
    const mockDiagnosis = {
      layer1: { layer: 1, name: '规则引擎', status: 'pass' as const, score: 1.0, issues: [], details: {} },
      layer2: { layer: 2, name: '历史对比', status: 'pass' as const, score: 0.9, issues: [], details: {} },
      layer3: { layer: 3, name: 'LLM 诊断', status: 'pass' as const, score: 0.85, issues: [], details: {} },
      layer4: { layer: 4, name: '数据质量', status: 'pass' as const, score: 0.95, issues: [], details: {} },
      layer5: { layer: 5, name: '效果评估', status: 'pass' as const, score: 0.88, issues: [], details: {} },
      layer6: { layer: 6, name: '回归检测', status: 'pass' as const, score: 0.92, issues: [], details: {} },
      overall_health: 0.92, total_issues: 0, critical_issues: 0,
    };
    vi.mocked(metricsApi.getRunDiagnosis).mockResolvedValue(mockDiagnosis);
    const { result } = renderHook(() => useRunDiagnosis('run-1'), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.overall_health).toBe(0.92);
  });
});

describe('useTriggerEvaluation', () => {
  afterEach(() => vi.clearAllMocks());

  it('mutate 时调用 triggerEvaluation', async () => {
    vi.mocked(metricsApi.triggerEvaluation).mockResolvedValue({ message: 'ok' });
    const { result } = renderHook(() => useTriggerEvaluation(), { wrapper: createWrapper() });
    result.current.mutate('run-1');
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(metricsApi.triggerEvaluation).toHaveBeenCalledWith('run-1');
  });
});

/* ═══════════════════ useReports ═══════════════════ */

describe('useReports', () => {
  beforeEach(() => {
    vi.mocked(reportsApi.getReports).mockResolvedValue(mockReportsResponse);
  });
  afterEach(() => vi.clearAllMocks());

  it('加载完成后返回报告列表', async () => {
    const { result } = renderHook(() => useReports(), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.items).toHaveLength(1);
    expect(result.current.data?.items[0].run_id).toBe('run-1');
  });
});

describe('useReport', () => {
  afterEach(() => vi.clearAllMocks());

  it('传入有效 ID 时获取报告详情', async () => {
    vi.mocked(reportsApi.getReport).mockResolvedValue(mockReportsResponse.items[0]);
    const { result } = renderHook(() => useReport('rpt-1'), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.id).toBe('rpt-1');
  });
});

describe('useGenerateReport', () => {
  afterEach(() => vi.clearAllMocks());

  it('mutate 时调用 generateReport', async () => {
    vi.mocked(reportsApi.generateReport).mockResolvedValue(mockReportsResponse.items[0]);
    const { result } = renderHook(() => useGenerateReport(), { wrapper: createWrapper() });
    result.current.mutate('run-1');
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(reportsApi.generateReport).toHaveBeenCalledWith('run-1');
  });
});

describe('useTrends', () => {
  afterEach(() => vi.clearAllMocks());

  it('传入有效 metric 时获取趋势数据', async () => {
    const mockTrends = [{ label: '运行1', value: 0.82, created_at: '2026-04-28', run_id: 'run-1', metric_name: 'overall' }];
    vi.mocked(reportsApi.getTrends).mockResolvedValue(mockTrends);
    const { result } = renderHook(() => useTrends('overall'), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toHaveLength(1);
  });

  it('metric 为空时不发起请求', () => {
    renderHook(() => useTrends(''), { wrapper: createWrapper() });
    expect(reportsApi.getTrends).not.toHaveBeenCalled();
  });
});

/* ═══════════════════ useTuning ═══════════════════ */

describe('useTuningSuggestions', () => {
  afterEach(() => vi.clearAllMocks());

  it('传入有效 runId 时获取调优建议', async () => {
    vi.mocked(tuningApi.getTuningSuggestions).mockResolvedValue(mockSuggestions);
    const { result } = renderHook(() => useTuningSuggestions('run-1'), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toHaveLength(1);
    expect(result.current.data?.[0].config_key).toBe('rag.retrieval.top_k');
  });

  it('runId 为空时不发起请求', () => {
    renderHook(() => useTuningSuggestions(''), { wrapper: createWrapper() });
    expect(tuningApi.getTuningSuggestions).not.toHaveBeenCalled();
  });
});

describe('useAdoptSuggestion', () => {
  afterEach(() => vi.clearAllMocks());

  it('mutate 时调用 adoptSuggestion', async () => {
    const adopted = { ...mockSuggestions[0], status: 'adopted' as const };
    vi.mocked(tuningApi.adoptSuggestion).mockResolvedValue(adopted);
    const { result } = renderHook(() => useAdoptSuggestion(), { wrapper: createWrapper() });
    result.current.mutate({ suggestionId: 'sug-1', runId: 'run-1' });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(tuningApi.adoptSuggestion).toHaveBeenCalledWith('sug-1');
  });
});

describe('useRejectSuggestion', () => {
  afterEach(() => vi.clearAllMocks());

  it('mutate 时调用 rejectSuggestion', async () => {
    const rejected = { ...mockSuggestions[0], status: 'rejected' as const };
    vi.mocked(tuningApi.rejectSuggestion).mockResolvedValue(rejected);
    const { result } = renderHook(() => useRejectSuggestion(), { wrapper: createWrapper() });
    result.current.mutate({ suggestionId: 'sug-1', runId: 'run-1', reason: '不需要' });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(tuningApi.rejectSuggestion).toHaveBeenCalledWith('sug-1', '不需要');
  });
});

describe('useConfigVersions', () => {
  afterEach(() => vi.clearAllMocks());

  it('加载完成后返回配置版本列表', async () => {
    const versions = [{ id: 'v-1', version: 'v1', created_at: '2026-04-28', description: '初始版本' }];
    vi.mocked(tuningApi.getConfigVersions).mockResolvedValue(versions);
    const { result } = renderHook(() => useConfigVersions(), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toHaveLength(1);
  });
});

describe('useRollbackConfig', () => {
  afterEach(() => vi.clearAllMocks());

  it('mutate 时调用 rollbackConfigVersion', async () => {
    vi.mocked(tuningApi.rollbackConfigVersion).mockResolvedValue({ version_id: 'v-1' });
    const { result } = renderHook(() => useRollbackConfig(), { wrapper: createWrapper() });
    result.current.mutate('v-1');
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(tuningApi.rollbackConfigVersion).toHaveBeenCalledWith('v-1');
  });
});

/* ═══════════════════ useSnapshots ═══════════════════ */

describe('useSnapshots', () => {
  afterEach(() => vi.clearAllMocks());

  it('加载完成后返回快照列表', async () => {
    vi.mocked(snapshotsApi.getSnapshots).mockResolvedValue(mockSnapshots);
    const { result } = renderHook(() => useSnapshots(), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toHaveLength(1);
    expect(result.current.data?.[0].name).toBe('快照1');
  });
});

describe('useSnapshot', () => {
  afterEach(() => vi.clearAllMocks());

  it('传入有效 ID 时获取快照详情', async () => {
    vi.mocked(snapshotsApi.getSnapshot).mockResolvedValue(mockSnapshots[0]);
    const { result } = renderHook(() => useSnapshot('snap-1'), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.id).toBe('snap-1');
  });

  it('enabled 为 false 时不发起请求', () => {
    renderHook(() => useSnapshot(''), { wrapper: createWrapper() });
    expect(snapshotsApi.getSnapshot).not.toHaveBeenCalled();
  });
});

describe('useCreateSnapshot', () => {
  afterEach(() => vi.clearAllMocks());

  it('mutate 时调用 createSnapshot', async () => {
    vi.mocked(snapshotsApi.createSnapshot).mockResolvedValue(mockSnapshots[0]);
    const { result } = renderHook(() => useCreateSnapshot(), { wrapper: createWrapper() });
    result.current.mutate({ name: '快照1' });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(snapshotsApi.createSnapshot).toHaveBeenCalledWith({ name: '快照1' });
  });
});

describe('useRestoreSnapshot', () => {
  afterEach(() => vi.clearAllMocks());

  it('mutate 时调用 restoreSnapshot', async () => {
    vi.mocked(snapshotsApi.restoreSnapshot).mockResolvedValue({ message: '已还原' });
    const { result } = renderHook(() => useRestoreSnapshot(), { wrapper: createWrapper() });
    result.current.mutate('snap-1');
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(snapshotsApi.restoreSnapshot).toHaveBeenCalledWith('snap-1');
  });
});
