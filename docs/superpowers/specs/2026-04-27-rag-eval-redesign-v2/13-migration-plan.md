# 13 - 迁移指南与执行计划

## 迁移原则

1. **零兼容层**：旧代码直接删除，不保留向后兼容层
2. **先设计完再动手**：完整 spec 审核通过后才开始实现
3. **逐引擎迁移**：每次迁移一个引擎
4. **前端跟随**：后端引擎完成后前端同步更新
5. **测试先行**：每个引擎先写测试再写实现
6. **一刀切**：项目未上线，Phase 0 一开始就 DROP 旧表 + DROP 旧代码，不存在新旧共存期

## 分阶段执行计划

### Phase 0: 清场 + 基础设施（3天）

**目标**：彻底清除旧代码/旧表，建立新基础设施。

> **零迁移原则**：项目未上线，无历史数据。Phase 0 一开始就删除所有旧代码和旧表，不存在新旧共存过渡期。新代码从 Phase 1 开始逐引擎实现。

**清场任务（第 1 天）**：

1. 删除 23 张旧表的 DDL 定义（Legacy 7张 + RagEval 16张）
2. `ALTER TABLE source_documents` 新增字段（保留旧表结构，不 DROP）
3. 删除所有旧后端代码（一次性）：
   - `service/rag_test/` 整个目录（17文件）
   - `controller/rag_test_controller.py`
   - `models/test_case.py`（旧 ORM）
   - `models/rag_eval/` 旧 ORM 目录（21文件，重写为新目录）
   - `schemas/test_case.py`、`schemas/rag_eval.py`、`schemas/tuning.py`（旧 Schema）
   - `repository/test_case_repository.py`（旧 Repository）
   - `core/validation/` 整个目录（19文件）
   - `core/tuning/` 整个目录（6文件）
   - `service/rag_report_service.py`、`service/report/`、`service/trend_service.py`、`service/export_service.py`
   - `service/tuning_suggestion_service.py`、`service/ignored_suggestion_service.py`、`service/config_change_set_service.py`、`service/config_rollback_service.py`
   - `controller/tuning_controller.py`、`controller/tuning_suggestion_controller.py`、`controller/report_controller.py`、`controller/trend_controller.py`、`controller/export_controller.py`、`controller/rollback_controller.py`、`controller/intent_annotation_controller.py`、`controller/audit_log_controller.py`
4. 删除所有旧前端代码（一次性）：
   - `api/rag-test/`、`api/rag-eval/` 旧文件
   - `entities/test-case/`
   - `features/rag-eval/pages/DraftManagementPage.tsx`、`DraftGenerationPanel.tsx`、`UploadWithGeneration.tsx`
   - `features/rag-eval/components/RecommendationPanel/WizardMode.tsx`、`ExpertMode.tsx`
   - `store/recommendationPanelStore.ts` 或其他 Zustand stores
5. 从 `RepositoryModule` 和 `core/di_container.py` 中移除 `ConfigVersionRepository`（将由 `RagEvalModule` 提供）。同时将 `config/core/manager.py` 中的直接实例化改为通过 injector 注入。

**建设任务（第 2-3 天）**：

1. **先删除旧 `models/rag_eval/`**（21 个文件全部删除），**然后创建新 `models/rag_eval/`** 目录并写入 11 个新 ORM 文件 + `enums.py`（共 12 个文件）
2. 创建 `schemas/rag_eval/` 目录及所有 Schema 文件（12 个文件，含 `__init__.py` 统一导出）
3. 实现 `utils/orm_mapper.py`、`utils/embedding_helper.py`、`utils/similarity.py`
4. 创建 `repository/rag_eval/` 目录（11 个 Repository）
5. 创建 `RagEvalModule` DI 模块并注册到 `injector`
6. 配置 Key 迁移：将所有 RAG 评估相关配置统一为 `rag.eval.*` 格式
7. 前端：创建 `entities/rag-eval/` 类型层 + `api/rag-eval/` API 层骨架

**验收**：
- 旧代码目录全部不存在（`find` 确认）
- 旧表 DDL 全部移除，新表可查询
- `source_documents` ALTER 已执行
- 新 ORM 模型和 Repository 可正常 CRUD
- `RagEvalModule` 已注册到 injector
- Schema 文件零 deprecated 字段

### Phase 1: MetricEngine 双轨（4天）

**目标**：实现三层指标计算 + 六层诊断引擎。

**三层指标**：
1. `metrics/scoring/base.py` — MetricCalculator 接口
2. `metrics/scoring/registry.py` — MetricRegistry
3. `metrics/scoring/calculators/` — 12 个原子计算器
4. `metrics/scoring/retrieval.py` — L1 门面
5. `metrics/scoring/generation.py` — L2 门面
6. `metrics/scoring/system.py` — L3 门面
7. `metrics/scoring/facade.py` — ScoringFacade
8. 编写所有计算器单元测试（≥5 个/计算器）
9. 编写 RAGAS 交叉验证测试

**六层诊断**：
1. `metrics/diagnosis/orchestrator.py` — 诊断编排器
2. `metrics/diagnosis/layer1_rules.py` — 规则引擎
3. `metrics/diagnosis/layer2_history.py` — 历史对比
4. `metrics/diagnosis/layer3_llm.py` — LLM 诊断
5. `metrics/diagnosis/layer4_data_quality.py` — 数据质量
6. `metrics/diagnosis/layer5_effect.py` — 效果评估
7. `metrics/diagnosis/layer6_regression.py` — 回归检测
8. 编写所有诊断层单元测试（≥5 个/层）

**门面**：
1. `metrics/facade.py` — MetricEngineFacade（双轨统一）

**验收**：
- 所有计算器和诊断层测试通过
- RAGAS 交叉验证误差 < 10%
- 所有阈值通过 ConfigManager

### Phase 2: DraftEngine（3天）

**目标**：实现草稿引擎（替代已删除的 `draft_service.py` 1157行）。

1. `draft/generator.py` — DraftGenerator
2. `draft/faithfulness_checker.py` — FaithfulnessChecker
3. `draft/deduplicator.py` — DraftDeduplicator
4. `draft/book_analyzer.py` — BookMetadataAnalyzer
5. `draft/facade.py` — DraftEngineFacade
6. 编写引擎集成测试

### Phase 3: CaseEngine（2天）

**目标**：实现测试用例/集 CRUD 引擎。

1. `case/case_service.py` — TestCase CRUD + 导入
2. `case/set_service.py` — TestSet CRUD + 管理
3. `case/facade.py` — CaseEngineFacade
4. 编写引擎集成测试

### Phase 4: RunEngine（3天）

**目标**：实现测试执行引擎。

1. `run/executor.py` — TestCaseExecutor（统一执行入口）
2. `run/batch_runner.py` — BatchTestRunner
3. `run/result_processor.py` — ResultProcessor
4. `run/snapshot_manager.py` — SnapshotManager
5. `run/facade.py` — RunEngineFacade
6. SSE 统一 `{type, data}` 格式
7. 编写引擎集成测试

### Phase 5: ReportEngine（3天）

**目标**：统一双轨报告。

1. `report/builder.py` — ReportBuilder（双轨整合）
2. `report/markdown_renderer.py` — MarkdownRenderer
3. `report/trend_analyzer.py` — TrendAnalyzer
4. `report/exporter.py` — ReportExporter
5. `report/facade.py` — ReportEngineFacade
6. 编写引擎集成测试

### Phase 6: TuningEngine（2天）

**目标**：实现调优引擎。

1. `tuning/advisor.py` — TuningAdvisor
2. `tuning/conflict_detector.py` — ConflictDetector
3. `tuning/config_changer.py` — ConfigChanger（含回滚）
4. `tuning/facade.py` — TuningEngineFacade
5. 编写引擎集成测试

### Phase 7: 编排器 + 控制器（2天）

**目标**：统一入口。

1. `orchestrator.py` — RagEvalOrchestrator
2. `controller/rag_eval/` — 7 个子控制器 + 注册器
3. 更新路由注册
4. 编写端到端测试

### Phase 8: 前端重构（5天）

**目标**：TanStack Query + 统一类型层 + 双轨报告。

1. 实现 `entities/rag-eval/` 完整类型层
2. 实现 `api/rag-eval/` 完整 API 层
3. 实现 `useSSEProgress.ts`
4. 实现各 TanStack Query hooks
5. 实现共享组件
6. 实现三层指标组件（ScoringDashboard 等）
7. 实现六层诊断组件（DiagnosisPanel 等）
8. 重构 ReportPage（双轨展示）
9. 重构其他页面
10. 更新路由配置
11. 编写 Hook 测试 + 组件测试

### Phase 9: 清理验收（2天）

**目标**：最终清理和全量验收。

1. 确认旧代码全部删除（`find` 检查旧目录不存在）
2. 确认 23 张旧表 DDL 已移除
3. 运行 `npm run typecheck` + `npm run lint`
4. 运行后端全量测试
5. 运行前端全量测试
6. 手动测试完整工作流
7. 更新 `.ai/` 目录文档：
   - `.ai/architecture.md`：替换所有旧模块名称
   - `.ai/rag_pipeline.md`：更新路由前缀和 API 端点
   - `.ai/business_logic_map.md`：更新文件入口映射
   - `.ai/infrastructure.md`：更新 RAG 测试与评估数据模型描述
8. 更新 CLAUDE.md 中的相关引用
9. 删除 v1 方案文件

## 时间线

```
Week 1: Phase 0 (4天) + Phase 1 (5天)
Week 2: Phase 2 (4天) + Phase 3 (3天)
Week 3: Phase 3 (1天) + Phase 4 (4天) + Phase 5 (2天)
Week 4: Phase 5 (2天) + Phase 6 (3天) + Phase 7 (2天)
Week 5: Phase 7 (1天) + Phase 8 (6天)
Week 6: Phase 8 (1天) + Phase 9 (3天) + buffer (1天)
```

**预计总工期：~35 天（约 7 周）** — 每个 Phase 各增加 1 天 buffer，应对 LLM 调优、交叉验证环境搭建、prompt 调试等不确定性。

## 风险与缓解

| 风险 | 缓解措施 |
|------|---------|
| L1 指标与 RAGAS 不一致 | 只验证不依赖 LLM 的指标，容差 10% |
| LLM 依赖型指标成本高 | 配置化开关，可禁用 L2 指标 |
| 快照恢复影响索引 | 恢复前自动创建当前索引备份 |
| 前端大规模重构功能回归 | 逐页面迁移，每页迁移后手动测试 |
| Phase 0 清场后系统暂时不可用 | 预期行为——项目未上线，无外部用户影响；逐引擎恢复功能 |
| `source_documents` ALTER 影响旧 ORM | ALTER 仅新增字段，旧字段不变；旧 ORM 模型在 Phase 0 重写 |
| `config/core/manager.py` 注入化改造阻塞全局配置 | Phase 0 最高优先级处理，改造完成后立即集成测试验证 |
| Phase 0 删除全部旧代码导致无法跑集成对比 | 接受——项目无历史数据无兼容需求；Phase 0 前手动记录核心流程的 API 响应作为验收参考 |
