# RAG 评估模块全面重构方案 - 总览

> 创建日期: 2026-04-27
> 状态: DRAFT
> 范围: 后端 + 前端全面重构

## 背景

当前 RAG 评估模块存在严重的架构腐化问题：
- 后端 ~9,900 行代码分散在 God Class 中（`draft_service.py` 1157行、`controller.py` 996行）
- 前端 ~11,000 行代码完全未使用 TanStack Query，类型架构倒置，零测试覆盖
- 6层校验与业内 RAGAS/TruLens 标准不对齐
- 大量硬编码值、重复代码、sync/async 混用

## 方案核心：三层评估 + 五引擎架构

### 三层评估指标模型

| 层级 | 灵感来源 | 职责 |
|---|---|---|
| L1 检索质量 | RAGAS Context Precision/Recall, Noise Sensitivity, MRR, NDCG | 衡量检索本身的效果 |
| L2 生成质量 | RAGAS Faithfulness, Answer Relevancy + TruLens Groundedness | 衡量生成答案的质量 |
| L3 系统质量 | 自定义（规则合规、回归、成本效率、配置稳定性） | 系统级质量保障 |

### 五引擎后端架构

| 引擎 | 职责 | 核心文件 |
|---|---|---|
| DraftEngine | 测试用例草稿生成/审核/导入 | `service/rag_eval/draft/` |
| MetricEngine | 三层指标计算 | `service/rag_eval/metrics/` |
| RunEngine | 测试执行/快照/结果管理 | `service/rag_eval/run/` |
| ReportEngine | 报告生成/趋势分析/导出 | `service/rag_eval/report/` |
| TuningEngine | 调优建议/冲突检测/影响分析 | `service/rag_eval/tuning/` |

### 前端架构

- 引入 TanStack Query 统一数据获取
- 统一类型层 `entities/rag-eval/` 为唯一真相源
- 合并重复组件，提取共享组件
- SSE 连接抽象为 `useSSEProgress` hook

## 文件集索引

| 文件 | 需求点 |
|---|---|
| `01-metrics-system.md` | 三层评估指标体系设计 |
| `02-backend-architecture.md` | 后端五引擎架构设计 |
| `03-frontend-architecture.md` | 前端架构重构设计 |
| `04-data-models-and-api.md` | 数据模型与 API 契约 |
| `05-draft-engine.md` | 草稿引擎详细设计 |
| `06-metric-engine.md` | 指标引擎详细设计 |
| `07-run-engine.md` | 运行引擎详细设计 |
| `08-report-engine.md` | 报告引擎详细设计 |
| `09-tuning-engine.md` | 调优引擎详细设计 |
| `10-testing-strategy.md` | 测试策略与验收标准 |
| `11-migration-guide.md` | 迁移指南与执行计划 |

## 验收标准

1. 所有后端文件 < 500 行
2. 前端 `npm run typecheck` + `npm run lint` 通过
3. 后端无硬编码值（全部通过 ConfigManager）
4. 前端所有 API 调用通过 TanStack Query
5. 零 deprecated 字段、零 `console.log`
6. 每个指标计算器有 ≥5 个测试用例
7. 指标计算结果与 RAGAS 官方示例交叉验证（误差 < 5%）
