# 12 - 测试策略与验收标准

## 后端测试

### 框架

- **pytest** + **pytest-asyncio**
- **unittest.mock** Mock 外部依赖
- 手写 fixture 或 factory_boy

### 测试分层

#### 1. 单元测试 - 三层指标计算器（最高优先级）

每个 `MetricCalculator` ≥ 5 个测试用例。

| 计算器 | 测试场景 |
|--------|---------|
| `PrecisionAtK` | 空结果、全相关、全不相关、部分相关、单个结果 |
| `ContextRecall` | 空声明、全支持、全不支持、部分支持、单声明 |
| `MeanReciprocalRank` | 第一命中、第五命中、无命中、空排名、重复 ID |
| `NormalizedDCG` | 完美排序、逆序、空结果、单个结果、多级相关度 |
| `NoiseSensitivity` | 无噪音、全噪音、部分噪音、空结果、单结果 |
| `FaithfulnessCalculator` | 完全忠实、完全不忠实、部分忠实、空答案、无上下文 |
| `GroundednessCalculator` | 全溯源、无溯源、部分溯源、单句、长文本 |
| `AnswerRelevancyCalculator` | 高相关、低相关、空答案、单陈述、多陈述 |
| `RuleComplianceCalculator` | 全通过、全失败、部分通过、空结果、无效数据 |
| `RegressionScoreCalculator` | 相同基线、提升、退化、空基线、部分退化 |
| `CostEfficiencyCalculator` | 高效率、低效率、零成本、零质量、极端值 |
| `ConfigStabilityCalculator` | 无变化、轻微变化、显著变化、空基线、新增指标 |

文件位置：`backend/tests/unit/metrics/scoring/`

#### 2. 单元测试 - 六层诊断引擎

每个诊断层 ≥ 5 个测试用例。

| 层 | 测试场景 |
|----|---------|
| Layer 1 规则 | 格式合法/非法、必填缺失、数值越界、语法错误、全通过 |
| Layer 2 历史 | 无退化、单指标退化、新增失败、无历史、大幅退化 |
| Layer 3 LLM | 偏离检测、幻觉检测、相关判断、LLM 不可用降级、空输入 |
| Layer 4 数据 | Golden 全覆盖、部分覆盖、分块缺失、文档过期、空数据 |
| Layer 5 效果 | Embedding 正常、聚类异常、意图识别、错误模式、空结果 |
| Layer 6 回归 | 无回归、全局退化、交叉不一致、成本超标、基线缺失 |

文件位置：`backend/tests/unit/metrics/diagnosis/`

#### 3. 集成测试 - 引擎 Facade

每个引擎 Facade 的 CRUD + 核心流程测试。

| 引擎 | 测试内容 |
|------|---------|
| `DraftEngineFacade` | 生成任务启动/进度/完成、列表/过滤、审核/导入、批量删除 |
| `CaseEngineFacade` | 用例 CRUD、测试集 CRUD、导入导出、批量操作 |
| `RunEngineFacade` | 批量执行/单用例执行、快照创建/恢复、运行对比 |
| `MetricEngineFacade` | 三层指标计算、六层诊断执行、双轨并行、单层计算 |
| `ReportEngineFacade` | 报告生成/获取/导出、趋势数据、双轨整合 |
| `TuningEngineFacade` | 建议生成/采纳/拒绝、冲突检测、配置回滚 |

文件位置：`backend/tests/integration/rag_eval/`

#### 4. 交叉验证测试

L1 指标（不依赖 LLM 的部分）与 RAGAS 官方库交叉验证，误差 < 10%。

```python
# backend/tests/integration/metrics/test_ragas_cross_validation.py
@pytest.mark.asyncio
async def test_context_precision_matches_ragas():
    """自研 Context Precision 与 RAGAS 库结果误差 < 10%"""
    our_result = await our_calculator.calculate(test_input)
    ragas_result = await ragas_calculator.ascore(...)
    assert abs(our_result.score - ragas_result) < 0.10
```

仅验证不依赖 LLM 的指标（Precision、Recall、MRR、NDCG、NoiseSensitivity），因为 LLM 依赖型指标本身有随机性。

## 前端测试

### 框架

- **Vitest** + **React Testing Library**
- **msw** (Mock Service Worker)
- **@tanstack/react-query** 测试工具

### 测试分层

#### 1. Hook 测试

每个 TanStack Query hook 的 loading/success/error 状态。

| Hook | 测试场景 |
|------|---------|
| `useTestRuns` | 成功返回列表、空列表、加载中、错误状态、过滤器变化 |
| `useTestCases` | CRUD 操作、缓存失效 |
| `useDrafts` | 列表/审核/导入 |
| `useMetrics` | 三层指标获取 |
| `useDiagnosis` | 六层诊断获取 |
| `useSSEProgress` | 连接/事件/完成/错误/断线 |

#### 2. 共享组件测试

| 组件 | 测试内容 |
|------|---------|
| `DomainTag` | 各领域渲染、颜色映射 |
| `MetricScoreCard` | 分数显示、通过/失败状态 |
| `LayerStatusBadge` | pass/warn/fail/skip 状态渲染 |
| `GenerationConfigForm` | 表单交互、验证 |

#### 3. 工具函数测试

| 函数 | 测试内容 |
|------|---------|
| `formatAge` | 各年龄段格式化 |
| `formatDomain` | 各领域中文映射 |
| `exportJSON` / `exportCSV` | 导出功能 |

## 总体验收标准

### 代码质量

| 标准 | 验证方式 |
|------|---------|
| 所有后端文件 < 500 行 | `find backend/src -name "*.py" -exec wc -l {} \;` |
| 零 deprecated 字段 | `grep -r "deprecated" schemas/` |
| 零硬编码值 | 检查阈值、prompt、并发数 |
| 零 `console.log` | `grep -r "console.log" frontend/src/` |
| 零 `any` 类型 | `npm run typecheck` |
| 代码规范通过 | `npm run lint` |

### 测试覆盖

| 标准 | 验证方式 |
|------|---------|
| 三层计算器 ≥ 5 个测试 | pytest 收集计数 |
| 六层诊断 ≥ 5 个测试 | pytest 收集计数 |
| 每个引擎 Facade 有集成测试 | pytest 收集计数 |
| L1 指标 RAGAS 交叉验证 < 10% | 交叉验证测试 |
| 前端所有 hook 有测试 | Vitest 收集计数 |

### 架构规范

| 标准 | 验证方式 |
|------|---------|
| 23 张旧表已删除 | DDL 文件检查 |
| 所有旧代码已删除 | `find` 检查旧目录不存在 |
| 所有引擎通过 DI 注入 | 无 `__new__` 单例 |
| SSE 统一 `{type, data}` | 代码审查 |
| 配置 Key 遵循 `rag.eval.*` | 代码审查 |
| 前端字段名与后端一致 | 类型对比 |
