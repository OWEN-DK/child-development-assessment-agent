# 10 - 测试策略与验收标准

## 需求

定义后端和前端的测试策略，确保重构后的 RAG 评估模块质量可控。

## 后端测试

### 框架与工具

- **pytest** + **pytest-asyncio**：测试运行器
- **unittest.mock**：Mock 外部依赖
- **factory_boy** 或手写 fixture：测试数据工厂

### 测试分层

#### 1. 单元测试 - 指标计算器（最高优先级）

每个 `MetricCalculator` 实现需 ≥5 个测试用例。

| 计算器 | 测试用例 |
|---|---|
| `PrecisionAtK` | 空结果、全相关、全不相关、部分相关、单个结果 |
| `ContextRecall` | 空声明、全支持、全不支持、部分支持、单声明 |
| `MeanReciprocalRank` | 第一命中、第五命中、无命中、空排名、重复ID |
| `NormalizedDCG` | 完美排序、逆序、空结果、单个结果、多级相关度 |
| `FaithfulnessCalculator` | 完全忠实、完全不忠实、部分忠实、空答案、无上下文 |
| `GroundednessCalculator` | 全溯源、无溯源、部分溯源、单句、长文本 |
| `RuleComplianceCalculator` | 全通过、全失败、部分通过、空结果、无效数据 |
| `RegressionScoreCalculator` | 相同基线、提升、退化、空基线、部分退化 |

文件位置：`backend/tests/unit/metrics/`

```python
# 示例: backend/tests/unit/metrics/test_mrr.py
import pytest
from src.service.rag_eval.metrics.calculators.mrr_ndcg import MeanReciprocalRank, MRRInput

@pytest.fixture
def mrr():
    return MeanReciproralRank(config_manager=mock_config)

@pytest.mark.asyncio
async def test_first_hit(mrr):
    result = await mrr.calculate(MRRInput(
        expected_doc_ids=["doc_a"],
        ranked_doc_ids=["doc_a", "doc_b", "doc_c"],
    ))
    assert result.score == 1.0

@pytest.mark.asyncio
async def test_fifth_hit(mrr):
    result = await mrr.calculate(MRRInput(
        expected_doc_ids=["doc_a"],
        ranked_doc_ids=["doc_b", "doc_c", "doc_d", "doc_e", "doc_a"],
    ))
    assert result.score == pytest.approx(0.2, abs=0.01)

@pytest.mark.asyncio
async def test_no_hit(mrr):
    result = await mrr.calculate(MRRInput(
        expected_doc_ids=["doc_x"],
        ranked_doc_ids=["doc_a", "doc_b"],
    ))
    assert result.score == 0.0
```

#### 2. 集成测试 - 引擎 Facade

每个引擎 Facade 的 CRUD 完整测试，Mock 数据库和 LLM 依赖。

| 引擎 | 测试内容 |
|---|---|
| `DraftEngineFacade` | 生成任务启动/进度/完成、列表/过滤、审核/导入、批量删除 |
| `MetricEngineFacade` | 三层指标并行计算、单层计算、阈值判断、配置获取 |
| `RunEngineFacade` | 批量执行/单用例执行、快照创建/恢复、运行对比 |
| `ReportEngineFacade` | 报告生成/获取/导出、趋势数据 |
| `TuningEngineFacade` | 建议生成/采纳/拒绝、冲突检测 |

文件位置：`backend/tests/integration/rag_eval/`

#### 3. 交叉验证测试

L1 指标与 RAGAS 官方 Python 库交叉验证。

```python
# backend/tests/integration/metrics/test_ragas_cross_validation.py
import pytest
from ragas.metrics import ContextPrecision, Faithfulness

@pytest.mark.asyncio
async def test_context_precision_matches_ragas():
    """自研 Context Precision 与 RAGAS 库结果误差 < 5%"""
    # 准备测试数据
    test_data = prepare_standard_test_data()
    
    # 自研计算
    our_result = await our_calculator.calculate(test_data.our_input)
    
    # RAGAS 计算
    ragas_result = await ragas_calculator.ascore(
        user_input=test_data.question,
        response=test_data.response,
        retrieved_contexts=test_data.contexts,
    )
    
    assert abs(our_result.score - ragas_result) < 0.05
```

### 前端测试

### 框架与工具

- **Vitest**：测试运行器
- **React Testing Library**：组件测试
- **msw** (Mock Service Worker)：API Mock
- **@tanstack/react-query** 的测试工具

### 测试分层

#### 1. Hook 测试

每个 TanStack Query hook 的 loading/success/error 状态。

```typescript
// frontend/src/features/rag-eval/hooks/__tests__/useTestRuns.test.ts
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useTestRuns } from '../useTestRuns';
import { server } from '@/mocks/server';
import { rest } from 'msw';

describe('useTestRuns', () => {
  it('should return runs on success', async () => {
    server.use(
      rest.get('/rag/eval/runs', (_, res, ctx) => 
        res(ctx.json({ code: 0, data: mockRuns }))
      )
    );
    
    const { result } = renderHook(() => useTestRuns(), {
      wrapper: ({ children }) => (
        <QueryClientProvider client={new QueryClient()}>
          {children}
        </QueryClientProvider>
      ),
    });
    
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(mockRuns);
  });
});
```

#### 2. 组件测试

共享组件的渲染和交互测试。

| 组件 | 测试内容 |
|---|---|
| `DomainTag` | 各领域标签渲染、颜色映射 |
| `AgeStageTag` | 各年龄段渲染 |
| `MetricScoreCard` | 分数显示、通过/失败状态、阈值展示 |
| `MetricGauge` | 仪表盘渲染、低分高亮 |
| `GenerationConfigForm` | 表单交互、验证 |

#### 3. 工具函数测试

```typescript
// entities/rag-eval/__tests__/mappers.test.ts
import { formatAge, formatDomain } from '../mappers';

describe('formatAge', () => {
  it('should format age stages correctly', () => {
    expect(formatAge('0-6m')).toBe('0-6个月');
    expect(formatAge('6-12y')).toBe('6-12岁');
  });
});

describe('formatDomain', () => {
  it('should format domains correctly', () => {
    expect(formatDomain('sensory_integration')).toBe('感统训练');
  });
});
```

## 总体验收标准

### 代码质量

| 标准 | 验证方式 |
|---|---|
| 所有后端文件 < 500 行 | `find backend/src -name "*.py" -exec wc -l {} \;` |
| 零 deprecated 字段 | grep "deprecated" schemas/ |
| 零硬编码值 | grep 检查阈值、prompt、并发数 |
| 零 `console.log` | grep 前端代码 |
| 零 `any` 类型 | `npm run typecheck` |
| 代码规范通过 | `npm run lint` |

### 测试覆盖

| 标准 | 验证方式 |
|---|---|
| 每个指标计算器 ≥5 个测试 | pytest 收集计数 |
| 每个引擎 Facade 有 CRUD 测试 | pytest 收集计数 |
| L1 指标与 RAGAS 交叉验证误差 < 5% | 交叉验证测试 |
| 前端所有 hook 有测试 | Vitest 收集计数 |
| 前端共享组件有测试 | Vitest 收集计数 |

### 功能完整性

| 标准 | 验证方式 |
|---|---|
| TanStack Query 管理所有 API 调用 | grep useState+useEffect+fetch |
| 类型依赖方向正确 | 依赖分析工具 |
| 所有 API 返回统一响应格式 | API 测试 |
| 所有异常使用 AppException | grep HTTPException |
| SSE 连接统一管理 | useSSEProgress 覆盖 |

### 配置化

| 标准 | 验证方式 |
|---|---|
| 所有阈值通过 ConfigManager | grep 硬编码数值 |
| 所有 Prompt 通过 PromptManager | grep 硬编码 prompt 字符串 |
| 所有并发数/超时通过配置 | grep 硬编码数字 |
