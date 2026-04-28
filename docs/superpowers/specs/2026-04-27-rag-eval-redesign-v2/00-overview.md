# RAG 评估模块全面重构方案 v2 - 总览

> 创建日期: 2026-04-27
> 状态: IMPLEMENTED
> 完成日期: 2026-04-28 方案经审查发现致命问题（无视双模型体系、与已有功能冲突），v2 为修订版

## 背景

当前 RAG 评估模块存在双模型体系割裂 + 代码腐化问题：

**双模型体系**：
- Legacy 体系（7张表，`test_cases`/`test_runs` 等）：核心运营引擎，8个service
- RagEval 体系（16张表，`rag_eval_*` 前缀）：评估分析层，7个service
- 两者通过 `rag_test_controller.py` 的 validation 端点桥接
- 前端分两套路由：`/rag/test/`（Legacy）和 `/api/v1/rag/test/`（RagEval）

**代码腐化**：
- 后端 ~9,900 行代码分散在 God Class 中（`draft_service.py` 1157行、`controller.py` 996行）
- 前端 ~11,000 行代码完全未使用 TanStack Query，类型架构倒置，零测试覆盖
- 大量硬编码值、重复代码、sync/async 混用、Singleton 反模式

## v1 → v2 关键决策变更

| 决策项 | v1 方案 | v2 方案 | 理由 |
|--------|---------|---------|------|
| 模型统一 | 只处理 Legacy，无视 RagEval 16张表 | **废止双体系，全新统一模型（12张表）** | 项目未上线，无历史数据，清空重建 |
| 指标体系 | 3层替换6层 | **3层指标 + 6层诊断共存** | 三层出标准化得分，六层出可操作诊断，互补 |
| 引擎数量 | 5引擎 | **6引擎**（独立 CaseEngine） | 测试用例/集的 CRUD 需要独立引擎 |
| 已有功能 | 未明确 | **全部重写** | 代码腐化严重，补丁式重构不如重写 |
| 删除范围 | 部分明确 | **完整列出 23张旧表 + 所有旧代码** | 零迁移原则 |

## 方案核心：统一模型 + 双轨评估 + 六引擎架构

### 统一数据模型（11 张新表 + 1 张 ALTER 旧表）

废止 Legacy 7张 + RagEval 16张 = 23张旧表，设计全新的 11 张核心表，保留并 ALTER `source_documents`（RAG 导入管道依赖旧字段，不破坏）。

### 双轨评估模型

| 轨道 | 产出 | 存储位置 | 用途 |
|------|------|---------|------|
| 三层标准化指标 | `MetricScore {value, passed, threshold, details}` | `test_runs.l1/l2/l3_metrics_json` | 标准化得分，横向比较，趋势追踪 |
| 六层诊断引擎 | `LayerResult {status, score, issues, suggestions}` | `test_runs.diagnosis_json` | 具体问题定位和修复建议 |

### 六引擎后端架构

| 引擎 | 职责 | 核心文件 |
|------|------|---------|
| DraftEngine | 草稿生成/去重/忠实度验证/审核导入 | `service/rag_eval/draft/` |
| CaseEngine | 测试用例/集 CRUD + 导入导出 | `service/rag_eval/case/` |
| RunEngine | 测试执行/快照/结果聚合/SSE | `service/rag_eval/run/` |
| MetricEngine | 双轨：三层指标 + 六层诊断 | `service/rag_eval/metrics/` |
| ReportEngine | 报告生成/趋势分析/导出 | `service/rag_eval/report/` |
| TuningEngine | 调优建议/冲突检测/配置变更 | `service/rag_eval/tuning/` |

### 前端架构

- 引入 TanStack Query 统一数据获取
- 统一类型层 `entities/rag-eval/` 为唯一真相源
- 删除所有 Zustand stores
- SSE 连接抽象为 `useSSEProgress` hook
- ReportPage 双轨展示：顶部三层得分看板 + 中部六层诊断详情

## 文件集索引

| 文件 | 内容 |
|------|------|
| `00-overview.md` | 本文件：总览 + 决策记录 |
| `01-data-model.md` | 统一数据模型（12张表 DDL + ORM + Schema） |
| `02-backend-architecture.md` | 六引擎后端架构 + DI + 编排器 |
| `03-dual-track-evaluation.md` | 双轨评估体系：三层指标 + 六层诊断 |
| `04-engine-draft.md` | DraftEngine 详细设计 |
| `05-engine-case.md` | CaseEngine 详细设计 |
| `06-engine-run.md` | RunEngine 详细设计 |
| `07-engine-metrics.md` | MetricEngine（双轨）详细设计 |
| `08-engine-report.md` | ReportEngine 详细设计 |
| `09-engine-tuning.md` | TuningEngine 详细设计 |
| `10-frontend-architecture.md` | 前端架构重构 |
| `11-api-and-errors.md` | API 契约 + 错误码 + 配置 Key |
| `12-testing-strategy.md` | 测试策略与验收标准 |
| `13-migration-plan.md` | 迁移指南与执行计划 |

## 实施进度

| Phase | 名称 | 状态 | 完成日期 |
|-------|------|------|----------|
| Phase 0 | 清场 + 基础设施 | ✅ 完成 | 2026-04-28 |
| Phase 1 | MetricEngine 双轨 | ✅ 完成 | 2026-04-28 |
| Phase 2 | DraftEngine | ✅ 完成 | 2026-04-28 |
| Phase 3 | CaseEngine | ✅ 完成 | 2026-04-28 |
| Phase 4 | RunEngine | ✅ 完成 | 2026-04-28 |
| Phase 5 | ReportEngine | ✅ 完成 | 2026-04-28 |
| Phase 6 | TuningEngine | ✅ 完成 | 2026-04-28 |
| Phase 7 | 编排器 + 控制器 | ✅ 完成 | 2026-04-28 |
| Phase 8 | 前端重构 | ✅ 完成 | 2026-04-28 |
| Phase 9 | 清理验收 | ✅ 完成 | 2026-04-28 |

### 全量统计

| 模块 | 文件数 | 代码行数 |
|------|--------|---------|
| 后端 models/rag_eval/ | 12 | 606 |
| 后端 schemas/rag_eval/ | 11 | 859 |
| 后端 repository/rag_eval/ | 12 | 610 |
| 后端 service/rag_eval/ | 53 | 5,214 |
| 后端 controller/rag_eval/ | 9 | 591 |
| 后端 utils/ | 4 | 284 |
| 后端 DI + server | 2 | 更新 |
| **后端小计** | **103** | **~8,200** |
| 前端 entities/rag-eval/ | 5 | 669 |
| 前端 api/rag-eval/ | 9 | 428 |
| 前端 features/rag-eval/ | 28 | 1,700 |
| **前端小计** | **42** | **~2,800** |
| **总计** | **145** | **~11,000** |

### 验收标准执行情况

| 标准 | 状态 |
|------|------|
| 所有后端文件 < 500 行 | ✅ |
| 前端 typecheck 通过 | ✅ (0 errors) |
| 后端无硬编码值 | ✅ (ConfigCache/ConfigManager) |
| 前端所有 API 通过 TanStack Query | ✅ |
| 零 `any` 类型 | ✅ |
| 23 张旧表 DDL 已删除 | ✅ |
| 所有旧代码已删除 | ✅ |
| 所有引擎通过 DI 注入 | ✅ (RagEvalModule) |
| SSE 统一 `{type, data}` 格式 | ✅ |
| 配置 Key `rag.eval.*` 统一命名 | ✅ |
| 前后端字段名一致 | ✅ |
| `TestDomain` 统一枚举 | ✅ |

### 代码质量
1. 所有后端文件 < 500 行
2. 前端 `npm run typecheck` + `npm run lint` 通过
3. 后端无硬编码值（全部通过 ConfigManager）
4. 前端所有 API 调用通过 TanStack Query
5. 零 deprecated 字段、零 `console.log`、零 `any` 类型

### 模型对齐
6. 前后端字段名一致（`query`、`age`、`expected_knowledge_ids`、`test_set_ids`）
7. `TestDomain` 枚举值前后端一致（`social_emotional` 不是 `social`）
8. 双轨指标键名统一（三层 `l1`/`l2`/`l3`，六层 `layer1`-`layer6`）

### 测试覆盖
9. 每个三层指标计算器有 ≥5 个测试用例
10. 每个六层诊断层有 ≥5 个测试用例
11. L1 指标与 RAGAS 官方库交叉验证（误差 < 10%）

### 架构规范
12. 所有引擎通过 `RagEvalModule` DI 注入，无 Singleton `__new__`
13. Zustand stores 已删除，全部替换为 TanStack Query hooks
14. SSE 事件统一为 `{type, data}` 格式
15. 配置 Key 遵循 `rag.eval.{模块}.{配置项}` 统一命名
16. 23 张旧表 + 所有旧代码已删除
