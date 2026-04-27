# 03 - 前端架构重构

## 需求

重构 RAG 评估前端模块（~11,000行），引入 TanStack Query、统一类型层、消除代码重复。

## 当前问题

1. 零 TanStack Query 使用，所有 API 调用手动管理 loading/error 状态
2. API 层导入组件类型（依赖方向倒置）
3. `DOMAIN_MAP`、`formatAge` 等常量/函数在 6+ 文件中重复
4. `DraftGenerationPanel` 与 `UploadWithGeneration` 80% 代码重复
5. `DraftManagementPage` 524行违反 500 行限制
6. 零测试覆盖
7. `console.log` 调试语句残留
8. 部分组件使用 `any` 类型
9. `WizardMode` 和 `ExpertMode` 为空壳

## 目录结构

```
frontend/src/
├── entities/
│   └── rag-eval/                        # 统一类型层（单一真相源）
│       ├── index.ts
│       ├── types.ts                      # 所有接口/类型定义
│       ├── constants.ts                  # DOMAIN_MAP, STATUS_MAP, AGE_STAGES
│       ├── enums.ts                      # TestStatus, Domain, AgeStage 等
│       └── mappers.ts                    # formatAge, formatDomain 等映射工具
│
├── api/
│   └── rag-eval/                        # API层（只依赖 entities 层）
│       ├── index.ts                      # 统一导出
│       ├── client.ts                     # 基础 HTTP 客户端配置
│       ├── test-cases.ts                 # 测试用例 CRUD
│       ├── test-runs.ts                  # 测试运行 API
│       ├── drafts.ts                     # 草稿 API
│       ├── reports.ts                    # 报告 API
│       ├── snapshots.ts                  # 快照 API
│       ├── tuning.ts                     # 调优 API
│       └── metrics.ts                    # 指标 API
│
├── features/
│   └── rag-eval/
│       ├── index.ts
│       │
│       ├── pages/                        # 路由页面（轻量，只做组合）
│       │   ├── RagEvalMainPage.tsx       # Tab 布局 (~80行，保持)
│       │   ├── DraftPage.tsx             # 替代 DraftManagementPage (~200行)
│       │   ├── TestCasePage.tsx          # 替代 TestCaseManagementPage (~150行)
│       │   ├── TestSetPage.tsx           # 合并 TestSetList+Detail (~180行)
│       │   ├── RunPage.tsx               # 合并 RunList+Detail (~180行)
│       │   ├── ReportPage.tsx            # 报告页面 (~250行)
│       │   └── TuningPage.tsx            # 调优页面 (~150行)
│       │
│       ├── hooks/                        # TanStack Query hooks
│       │   ├── useTestCases.ts           # CRUD hooks (~60行)
│       │   ├── useTestRuns.ts            # 运行管理 hooks (~80行)
│       │   ├── useDrafts.ts              # 草稿 hooks (~60行)
│       │   ├── useReports.ts             # 报告 hooks (~50行)
│       │   ├── useSnapshots.ts           # 快照 hooks (~40行)
│       │   ├── useTuning.ts              # 调优 hooks (~50行)
│       │   ├── useMetrics.ts             # 指标查询 hooks (~40行)
│       │   └── useSSEProgress.ts         # SSE连接抽象 (~80行)
│       │
│       ├── components/                   # UI组件
│       │   ├── common/                   # 共享基础组件
│       │   │   ├── DomainTag.tsx         # 领域标签 (~25行)
│       │   │   ├── AgeStageTag.tsx       # 年龄段标签 (~20行)
│       │   │   ├── StatusBadge.tsx       # 状态徽章 (~20行)
│       │   │   ├── MetricScoreCard.tsx   # 指标评分卡 (~40行)
│       │   │   └── MetricGauge.tsx       # 指标仪表盘 (~35行)
│       │   │
│       │   ├── draft/                    # 草稿相关组件
│       │   │   ├── DraftTable.tsx        # 草稿列表表格 (~120行)
│       │   │   ├── DraftDetailModal.tsx  # 草稿详情弹窗 (~150行)
│       │   │   ├── DraftReviewPanel.tsx  # 审核面板 (~100行)
│       │   │   └── GenerationConfigForm.tsx  # 合并后的配置表单 (~200行)
│       │   │
│       │   ├── test/                     # 测试用例/集组件
│       │   │   ├── TestCaseTable.tsx     # 用例表格 (~100行)
│       │   │   ├── TestCaseForm.tsx      # 用例表单 (~80行)
│       │   │   ├── TestSetCard.tsx       # 测试集卡片 (~60行)
│       │   │   └── CaseTransferModal.tsx # 用例选择穿梭框 (~120行)
│       │   │
│       │   ├── run/                      # 运行相关组件
│       │   │   ├── RunProgressList.tsx   # SSE进度列表 (~100行)
│       │   │   ├── RunResultTable.tsx    # 结果表格 (~80行)
│       │   │   └── RunComparisonView.tsx # 运行对比 (~120行)
│       │   │
│       │   ├── report/                   # 报告组件
│       │   │   ├── MetricsDashboard.tsx  # 三层指标仪表盘 (~180行)
│       │   │   ├── TrendChart.tsx        # 趋势图 (~120行)
│       │   │   ├── BadCaseTable.tsx      # 坏案表 (~80行)
│       │   │   └── ReportExportPanel.tsx # 导出面板 (~60行)
│       │   │
│       │   ├── tuning/                   # 调优组件
│       │   │   ├── RecommendationPanel.tsx  # 建议面板 (~150行)
│       │   │   ├── ImpactPreview.tsx     # 影响预览 (~80行)
│       │   │   └── ConfigDiffView.tsx    # 配置差异 (~100行)
│       │   │
│       │   └── validation/               # 校验报告组件
│       │       └── ValidationReport.tsx  # 三层校验结果 (~150行)
│       │
│       └── utils/
│           ├── export.ts                 # 导出工具 (~80行)
│           └── sse.ts                    # SSE工具函数 (~40行)
│
└── router/
    └── index.tsx                         # 路由配置更新
```

## TanStack Query 集成

### Hook 模式

```typescript
// hooks/useTestRuns.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { testRunApi } from '@/api/rag-eval';

export function useTestRuns(filters?: RunFilters) {
  return useQuery({
    queryKey: ['rag-eval', 'runs', filters],
    queryFn: () => testRunApi.list(filters),
    staleTime: 30_000,
  });
}

export function useTestRun(runId: string) {
  return useQuery({
    queryKey: ['rag-eval', 'runs', runId],
    queryFn: () => testRunApi.get(runId),
    enabled: !!runId,
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

### SSE Hook

```typescript
// hooks/useSSEProgress.ts
export function useSSEProgress(url: string | null, options?: SSEOptions) {
  const [events, setEvents] = useState<SSEEvent[]>([]);
  const [status, setStatus] = useState<'connecting' | 'connected' | 'done' | 'error'>('connecting');

  useEffect(() => {
    if (!url) return;
    const eventSource = new EventSource(url);
    
    eventSource.onopen = () => setStatus('connected');
    eventSource.onmessage = (e) => {
      const event = JSON.parse(e.data);
      setEvents(prev => [...prev, event]);
      if (event.type === 'complete') setStatus('done');
    };
    eventSource.onerror = () => {
      setStatus('error');
      eventSource.close();
    };
    
    return () => eventSource.close();
  }, [url]);

  return { events, status };
}
```

## 类型层设计

```typescript
// entities/rag-eval/types.ts

// === 测试用例 ===
export interface TestCase {
  id: string;
  question: string;
  expected_answer: string;
  expected_doc_ids: string[];
  domain: TestDomain;
  age_stage: AgeStage;
  difficulty: DifficultyLevel;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

// === 测试运行 ===
export interface TestRun {
  id: string;
  test_set_id: string;
  snapshot_id: string;
  config_version: string;
  status: RunStatus;
  total_cases: number;
  completed_cases: number;
  metrics: RunMetrics | null;
  created_at: string;
  completed_at: string | null;
}

// === 三层指标 ===
export interface RunMetrics {
  l1_retrieval: Layer1Metrics;
  l2_generation: Layer2Metrics;
  l3_system: Layer3Metrics;
  overall_score: number;
}

export interface Layer1Metrics {
  context_precision: MetricScore;
  context_recall: MetricScore;
  noise_sensitivity: MetricScore;
  mrr: MetricScore;
  ndcg: MetricScore;
}

export interface Layer2Metrics {
  faithfulness: MetricScore;
  answer_relevancy: MetricScore;
  groundedness: MetricScore;
}

export interface Layer3Metrics {
  rule_compliance: MetricScore;
  regression_score: MetricScore;
  cost_efficiency: MetricScore;
  config_stability: MetricScore;
}

export interface MetricScore {
  value: number;        // 0-1
  passed: boolean;
  threshold: number;
  details: Record<string, unknown>;
}
```

```typescript
// entities/rag-eval/constants.ts
export const DOMAIN_MAP: Record<TestDomain, string> = {
  sensory_integration: '感统训练',
  gross_motor: '大运动',
  fine_motor: '精细运动',
  language: '语言发展',
  social: '社交能力',
  cognitive: '认知发展',
} as const;

export const DOMAIN_COLORS: Record<TestDomain, string> = {
  sensory_integration: '#1890ff',
  gross_motor: '#52c41a',
  fine_motor: '#faad14',
  language: '#722ed1',
  social: '#eb2f96',
  cognitive: '#13c2c2',
} as const;

export const AGE_STAGES = [
  { value: '0-6m', label: '0-6个月' },
  { value: '6-12m', label: '6-12个月' },
  { value: '1-2y', label: '1-2岁' },
  { value: '2-3y', label: '2-3岁' },
  { value: '3-4y', label: '3-4岁' },
  { value: '4-6y', label: '4-6岁' },
  { value: '6-12y', label: '6-12岁' },
] as const;
```

## 合并重复组件

`DraftGenerationPanel` + `UploadWithGeneration` → `GenerationConfigForm`:

```
GenerationConfigForm (共享基础)
├── UploadWithGeneration    # 包含文件上传功能
└── DraftGenerationPanel    # 仅配置表单，复用 GenerationConfigForm
```

共享逻辑提取到 hook：
```typescript
// hooks/useDraftConfig.ts
export function useDraftConfig() {
  const { data: config } = useQuery({
    queryKey: ['rag-eval', 'draft-config'],
    queryFn: () => draftApi.getConfig(),
  });
  const { data: models } = useQuery({
    queryKey: ['rag-eval', 'available-models'],
    queryFn: () => draftApi.getAvailableModels(),
  });
  return { config, models };
}
```

## 删除的文件/代码

以下内容在重构完成后删除：
- `frontend/src/api/rag-test/` 整个旧目录
- `frontend/src/api/rag-eval/` 旧文件（重新编写）
- `frontend/src/features/rag-eval/pages/DraftManagementPage.tsx`（拆分为 DraftPage + 子组件）
- `frontend/src/features/rag-eval/components/DraftGenerationPanel.tsx`（合并到 GenerationConfigForm）
- `frontend/src/features/rag-eval/components/UploadWithGeneration.tsx`（合并到 GenerationConfigForm）
- `frontend/src/features/rag-eval/components/RecommendationPanel/WizardMode.tsx`（空壳删除）
- `frontend/src/features/rag-eval/components/RecommendationPanel/ExpertMode.tsx`（空壳删除）
- `frontend/src/features/rag-eval/components/TrendChart/VersionTooltip.tsx`（未使用，删除）
- `frontend/src/features/rag-eval/components/TrendChart/ErrorBar.tsx`（未使用，删除）
- `frontend/src/features/rag-eval/components/ImpactPreview/index.tsx`（顶层，未使用，删除）

## 路由更新

```typescript
// router/index.tsx 路由配置
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

## 验收标准

1. 所有 API 调用通过 TanStack Query hooks，零 `useState` + `useEffect` 手动管理
2. 类型依赖方向正确：`entities/` → `api/` → `features/`，无反向依赖
3. 所有组件 < 200 行，所有页面 < 300 行
4. `npm run typecheck` 通过，零 `any` 类型
5. `npm run lint` 通过
6. 零 `console.log` 语句
7. 零空壳组件（WizardMode、ExpertMode 等已删除）
8. 共享常量只在 `entities/rag-eval/constants.ts` 定义一次
9. `formatAge`、`formatDomain` 等工具函数只在 `entities/rag-eval/mappers.ts` 定义一次
