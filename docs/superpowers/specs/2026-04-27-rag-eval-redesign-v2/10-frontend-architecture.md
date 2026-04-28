# 10 - 前端架构重构

## 需求

重构 RAG 评估前端模块（~11,000行），引入 TanStack Query、统一类型层、双轨报告展示、消除代码重复。

## 当前问题

| 问题 | 影响 |
|------|------|
| 零 TanStack Query | 所有 API 调用手动管理 loading/error 状态 |
| API 层导入组件类型 | 依赖方向倒置 |
| `DOMAIN_MAP` 在 4 个文件重复定义，`formatAge` 在 2 个文件重复 | 修改需改多处 |
| `DraftGenerationPanel` 与 `UploadWithGeneration` 80% 重复 | 维护成本翻倍 |
| `DraftManagementPage` 524行 | 违反 500 行限制 |
| 零测试覆盖 | 无法防止回归 |
| `console.log` 残留 | 生产日志泄露 |
| 部分 `any` 类型 | 类型安全缺失 |
| `WizardMode`/`ExpertMode` 空壳 | 死代码 |

## 目录结构

```
frontend/src/
├── entities/
│   └── rag-eval/                        # 唯一真相源
│       ├── index.ts
│       ├── types.ts                      # 所有接口/类型
│       ├── constants.ts                  # DOMAIN_MAP, STATUS_MAP, AGE_STAGES
│       ├── enums.ts                      # TestDomain, TestRunStatus 等
│       └── mappers.ts                    # formatAge, formatDomain
│
├── api/
│   └── rag-eval/                        # API层（只依赖 entities）
│       ├── index.ts                      # 统一导出
│       ├── client.ts                     # 基础 HTTP 客户端
│       ├── drafts.ts                     # 草稿 API
│       ├── cases.ts                      # 用例/集 API
│       ├── runs.ts                       # 运行 API
│       ├── metrics.ts                    # 三层指标 + 六层诊断 API
│       ├── reports.ts                    # 报告 API
│       ├── tuning.ts                     # 调优 API
│       └── snapshots.ts                  # 快照 API
│
├── features/
│   └── rag-eval/
│       ├── pages/                        # 路由页面（轻量组合，< 300行）
│       │   ├── RagEvalMainPage.tsx       # Tab 布局 (~80行)
│       │   ├── DraftPage.tsx             # 草稿管理 (~200行)
│       │   ├── TestCasePage.tsx          # 用例管理 (~150行)
│       │   ├── TestSetPage.tsx           # 测试集 (~180行)
│       │   ├── RunPage.tsx               # 运行管理 (~180行)
│       │   ├── ReportPage.tsx            # 双轨报告 (~250行)
│       │   └── TuningPage.tsx            # 调优 (~150行)
│       │
│       ├── hooks/                        # TanStack Query hooks
│       │   ├── useDrafts.ts              # 草稿 CRUD hooks (~60行)
│       │   ├── useTestCases.ts           # 用例 CRUD hooks (~60行)
│       │   ├── useTestSets.ts            # 测试集 hooks (~50行)
│       │   ├── useTestRuns.ts            # 运行管理 hooks (~80行)
│       │   ├── useMetrics.ts             # 三层指标 hooks (~40行)
│       │   ├── useDiagnosis.ts           # 六层诊断 hooks (~40行)
│       │   ├── useReports.ts             # 报告 hooks (~50行)
│       │   ├── useTuning.ts              # 调优 hooks (~50行)
│       │   ├── useSnapshots.ts           # 快照 hooks (~40行)
│       │   └── useSSEProgress.ts         # SSE 统一 hook (~80行)
│       │
│       ├── components/
│       │   ├── common/                   # 共享基础组件
│       │   │   ├── DomainTag.tsx         # 领域标签 (~25行)
│       │   │   ├── AgeStageTag.tsx       # 年龄段标签 (~20行)
│       │   │   ├── StatusBadge.tsx       # 状态徽章 (~20行)
│       │   │   ├── MetricScoreCard.tsx   # 三层指标评分卡 (~40行)
│       │   │   ├── MetricGauge.tsx       # 指标仪表盘 (~35行)
│       │   │   └── LayerStatusBadge.tsx  # 六层诊断状态徽章 (~20行)
│       │   │
│       │   ├── draft/                    # 草稿组件
│       │   │   ├── DraftTable.tsx        # 草稿列表 (~120行)
│       │   │   ├── DraftDetailModal.tsx  # 详情弹窗 (~150行)
│       │   │   ├── DraftReviewPanel.tsx  # 审核面板 (~100行)
│       │   │   └── GenerationConfigForm.tsx  # 生成配置 (~200行)
│       │   │
│       │   ├── case/                     # 用例/集组件
│       │   │   ├── TestCaseTable.tsx     # 用例表格 (~100行)
│       │   │   ├── TestCaseForm.tsx      # 用例表单 (~80行)
│       │   │   ├── TestSetCard.tsx       # 测试集卡片 (~60行)
│       │   │   └── CaseTransferModal.tsx # 用例选择穿梭框 (~120行)
│       │   │
│       │   ├── run/                      # 运行组件
│       │   │   ├── RunProgressList.tsx   # SSE 进度列表 (~100行)
│       │   │   ├── RunResultTable.tsx    # 结果表格 (~80行)
│       │   │   └── RunComparisonView.tsx # 运行对比 (~120行)
│       │   │
│       │   ├── metrics/                  # 三层指标展示
│       │   │   ├── ScoringDashboard.tsx  # 三层指标仪表盘 (~180行)
│       │   │   ├── LayerScoreCard.tsx    # 单层得分卡 (~60行)
│       │   │   └── MetricDetailPanel.tsx # 指标详情面板 (~80行)
│       │   │
│       │   ├── diagnosis/                # 六层诊断展示
│       │   │   ├── DiagnosisPanel.tsx    # 六层诊断面板 (~180行)
│       │   │   ├── LayerResultCard.tsx   # 单层结果卡 (~80行)
│       │   │   └── IssueList.tsx         # 问题列表 (~60行)
│       │   │
│       │   ├── report/                   # 报告组件
│       │   │   ├── ReportHeader.tsx      # 报告头+综合得分 (~60行)
│       │   │   ├── TrendChart.tsx        # 趋势图 (~120行)
│       │   │   ├── BadCaseTable.tsx      # 坏案表 (~80行)
│       │   │   └── ReportExportPanel.tsx # 导出面板 (~60行)
│       │   │
│       │   └── tuning/                   # 调优组件
│       │       ├── SuggestionPanel.tsx   # 建议面板 (~150行)
│       │       ├── ConflictAlert.tsx     # 冲突告警 (~60行)
│       │       └── ConfigDiffView.tsx    # 配置差异 (~100行)
│       │
│       └── utils/
│           ├── export.ts                 # 导出工具 (~80行)
│           └── sse.ts                    # SSE 工具函数 (~40行)
│
└── router/
    └── index.tsx                         # 路由配置更新
```

## TanStack Query 模式

```typescript
// hooks/useTestRuns.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

export function useTestRuns(filters?: RunFilters) {
  return useQuery({
    queryKey: ['rag-eval', 'runs', filters],
    queryFn: () => testRunApi.list(filters),
    staleTime: 30_000,
  });
}

export function useCreateRun() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: testRunApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['rag-eval', 'runs'] });
    },
  });
}
```

### SSE 工具函数（utils/sse.ts）

```typescript
// utils/sse.ts — fetch-based SSE 连接器，支持自定义 Header（如 Authorization token）
export async function createSSEConnection(
  url: string,
  opts: {
    signal: AbortSignal;
    onOpen: () => void;
    onMessage: (data: string) => void;
    onError: () => void;
  }
): Promise<void> {
  try {
    const response = await fetch(url, {
      signal: opts.signal,
      headers: {
        'Accept': 'text/event-stream',
        // Authorization header 由 HTTP 客户端中间件自动注入
      },
    });
    if (!response.ok) throw new Error(`SSE ${response.status}`);
    opts.onOpen();

    const reader = response.body!.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          opts.onMessage(line.slice(6));
        }
      }
    }
  } catch {
    opts.onError();
  }
}
```

## SSE Hook

```typescript
// hooks/useSSEProgress.ts
// ⚠️ 注意：原生 EventSource 不支持自定义 Header（如 Authorization token）
// 需要认证的 SSE 端点使用 fetch-based 实现（见 utils/sse.ts）

import { useState, useEffect } from 'react';
import { createSSEConnection } from '../utils/sse';

export function useSSEProgress(url: string | null) {
  const [events, setEvents] = useState<SSEEvent[]>([]);
  const [status, setStatus] = useState<'connecting' | 'connected' | 'done' | 'error'>('connecting');

  useEffect(() => {
    if (!url) return;

    const abortController = new AbortController();

    // 使用 fetch-based SSE（支持自定义 Header），替代原生 EventSource
    createSSEConnection(url, {
      signal: abortController.signal,
      onOpen: () => setStatus('connected'),
      onMessage: (raw) => {
        const { type, data } = JSON.parse(raw);
        setEvents(prev => [...prev, { type, data }]);
        if (type === 'run_completed' || type === 'run_failed' || type === 'generation_completed') setStatus('done');
      },
      onError: () => { setStatus('error'); abortController.abort(); },
    });

    return () => abortController.abort();
  }, [url]);

  return { events, status };
}
```

## 类型层设计

```typescript
// entities/rag-eval/types.ts
// 所有字段名与后端 ORM/Schema 保持一致

export type TestDomain =
  | 'gross_motor' | 'fine_motor' | 'language'
  | 'cognitive' | 'social_emotional' | 'sensory_integration';

export type TestRunStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';

export interface TestCase {
  id: string;
  query: string;                      // ORM: query
  age: number;                        // ORM: age (DECIMAL)
  age_stage_label: string;            // ORM: age_stage_label
  domain: TestDomain;
  description: string | null;
  expected_knowledge_ids: string[];   // ORM: expected_knowledge_ids
  expected_keywords: string[];
  answer_points_summary: string | null;
  source: 'manual' | 'draft' | 'import';
  source_draft_id: string | null;
  source_document_id: string | null;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface TestRun {
  id: string;
  name: string;
  test_set_ids: string[];             // ORM: test_set_ids (JSON 列表)
  status: TestRunStatus;
  total_test_cases: number;
  passed_test_cases: number;
  progress: number;                   // 计算: passed/total * 100
  overall_score: number | null;
  l1_metrics: Record<string, unknown> | null;
  l2_metrics: Record<string, unknown> | null;
  l3_metrics: Record<string, unknown> | null;
  diagnosis: Record<string, unknown> | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

// 三层指标
export interface RunMetrics {
  l1: Layer1Metrics;
  l2: Layer2Metrics;
  l3: Layer3Metrics;
  overall_score: number;
}

export interface MetricScore {
  value: number;
  passed: boolean;
  threshold: number;
  details: Record<string, unknown>;
}

// 六层诊断
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

export interface LayerResult {
  layer: number;
  name: string;
  status: 'pass' | 'warn' | 'fail' | 'skip' | 'error';
  score: number;
  issues: LayerIssue[];
  details: Record<string, unknown>;
}

export interface LayerIssue {
  severity: 'critical' | 'warning' | 'info';
  category: string;
  description: string;
  affected_items: string[];
  suggestion: string | null;
}
```

## ReportPage 双轨展示

```
ReportPage
├── 顶部：三层指标得分看板 (ScoringDashboard)
│   ├── L1 检索质量：Context Precision 0.78 ✓ | Recall 0.72 ✓ | MRR 0.65 ✓
│   ├── L2 生成质量：Faithfulness 0.85 ✓ | Relevancy 0.79 ✓ | Groundedness 0.81 ✓
│   └── L3 系统质量：Regression 0.94 ✓ | Cost 0.62 ⚠ | Config Stability N/A
│
├── 中部：六层诊断详情 (DiagnosisPanel，可折叠)
│   ├── Layer 1 规则引擎：✅ pass (12/12 规则通过)
│   ├── Layer 2 历史对比：⚠️ warn (3 项指标退化)
│   ├── Layer 3 LLM诊断：❌ fail (发现 2 个回答偏离)
│   ├── Layer 4 数据质量：✅ pass (Golden 覆盖 95%)
│   ├── Layer 5 效果评估：⚠️ warn (Embedding 聚类异常)
│   └── Layer 6 回归检测：✅ pass (无全局回归)
│
├── 底部左：Bad Cases 表格
├── 底部右：调优建议面板 (SuggestionPanel)
└── 操作栏：导出 (JSON/CSV/PDF)
```

## 路由更新

```typescript
// router/index.tsx
{
  path: '/rag-eval',
  element: <RagEvalMainPage />,
  children: [
    { path: 'drafts', element: <DraftPage /> },
    { path: 'cases', element: <TestCasePage /> },
    { path: 'sets', element: <TestSetPage /> },
    { path: 'runs', element: <RunPage /> },
    { path: 'reports', element: <ReportPage /> },
    { path: 'tuning', element: <TuningPage /> },
  ],
}
```

## 删除的前端文件

| 文件 | 原因 |
|------|------|
| `api/rag-test/` 整个旧目录 | 替换为 `api/rag-eval/` |
| `api/rag-eval/` 旧文件（trend.ts、export.ts、tuning.ts 等） | 重写 |
| `entities/test-case/` 旧类型文件 | 迁移到 `entities/rag-eval/` |
| `features/rag-eval/pages/DraftManagementPage.tsx` (524行) | 拆分为 DraftPage + 子组件 |
| `features/rag-eval/components/DraftGenerationPanel.tsx` | 合并到 GenerationConfigForm |
| `features/rag-eval/components/UploadWithGeneration.tsx` | 合并到 GenerationConfigForm |
| `features/rag-eval/components/RecommendationPanel/WizardMode.tsx` | 空壳删除 |
| `features/rag-eval/components/RecommendationPanel/ExpertMode.tsx` | 空壳删除 |
| `features/rag-eval/components/TrendChart/VersionTooltip.tsx` | 未使用 |
| `features/rag-eval/components/TrendChart/ErrorBar.tsx` | 未使用 |
| `features/rag-eval/components/ImpactPreview/index.tsx` (顶层) | 未使用 |
| `features/rag-eval/stores/` 或 `store/recommendationPanelStore.ts` | Zustand → TanStack Query |
| 旧 hooks（`useTestSetStore.ts`、`useRunManagement.ts` 等） | 重写为 TanStack Query |

## 验收标准

1. 所有 API 调用通过 TanStack Query hooks
2. 类型依赖方向：`entities/` → `api/` → `features/`
3. 所有组件 < 200 行，所有页面 < 300 行
4. `npm run typecheck` 通过，零 `any`
5. `npm run lint` 通过
6. 零 `console.log`、零空壳组件
7. 共享常量只在 `entities/rag-eval/constants.ts` 定义一次
8. 前端字段名与后端 ORM 完全一致
9. Zustand stores 已全部删除
10. ReportPage 同时展示三层指标和六层诊断
