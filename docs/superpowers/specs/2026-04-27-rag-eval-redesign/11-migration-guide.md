# 11 - 迁移指南与执行计划

## 需求

定义从当前代码到新架构的迁移策略和分阶段执行计划。遵循零迁移原则——直接删除旧代码，不保留兼容层。

## 迁移原则

1. **零兼容层**：旧代码直接删除，不保留重定向、废弃标记
2. **逐引擎迁移**：每次迁移一个引擎，降低风险
3. **前端跟随**：后端引擎迁移完成后，前端同步更新对应页面
4. **测试先行**：每个引擎先写测试，再写实现

## 分阶段执行计划

### Phase 0: 基础设施准备（预计 2 天）

**目标**：建立新目录结构、共享工具、Schema、Repository 层。

**任务**：
1. 创建 `backend/src/service/rag_eval/` 目录结构
2. 创建 `backend/src/schemas/rag_eval/` 所有 Schema 文件
3. 实现 `utils/orm_mapper.py`
4. 实现 `utils/embedding_helper.py`
5. 实现 `utils/similarity.py`
6. 创建对应的 Repository 类（如果不存在）
7. 创建 `frontend/src/entities/rag-eval/` 类型层
8. 创建 `frontend/src/api/rag-eval/` API 层骨架

**验收**：
- `typecheck` 通过
- Schema 文件无 deprecated 字段
- 类型依赖方向正确

### Phase 1: 指标引擎（预计 3 天）

**目标**：实现三层评估指标计算，这是其他引擎的基础。

**后端任务**：
1. 实现 `metrics/base.py`（MetricCalculator 接口）
2. 实现 `metrics/registry.py`（MetricRegistry）
3. 实现 `metrics/calculators/precision_recall.py`
4. 实现 `metrics/calculators/mrr_ndcg.py`
5. 实现 `metrics/calculators/faithfulness_calc.py`
6. 实现 `metrics/calculators/groundedness_calc.py`
7. 实现 `metrics/retrieval_quality.py`（L1 门面）
8. 实现 `metrics/generation_quality.py`（L2 门面）
9. 实现 `metrics/system_quality.py`（L3 门面）
10. 实现 `metrics/facade.py`（MetricEngineFacade）
11. 编写所有计算器的单元测试（≥5 个/计算器）
12. 编写 RAGAS 交叉验证测试

**验收**：
- 所有计算器测试通过
- RAGAS 交叉验证误差 < 5%
- 所有阈值通过 ConfigManager

### Phase 2: 草稿引擎（预计 3 天）

**目标**：替代 `draft_service.py`（1157行）。

**后端任务**：
1. 实现 `draft/generator.py`（DraftGenerator）
2. 实现 `draft/faithfulness_checker.py`（FaithfulnessChecker）
3. 实现 `draft/deduplicator.py`（DraftDeduplicator）
4. 实现 `draft/book_analyzer.py`（BookMetadataAnalyzer）
5. 实现 `draft/facade.py`（DraftEngineFacade）
6. 编写引擎集成测试

**删除**：
- `service/rag_test/draft_service.py`
- `service/rag_test/draft_deduplication_service.py`
- `service/rag_test/book_metadata_service.py`
- `service/rag_test/question_templates.json`

### Phase 3: 运行引擎（预计 3 天）

**目标**：替代 `test_executor.py`、`test_batch_runner.py`、`test_result_analyzer.py`、`snapshot_service.py`。

**后端任务**：
1. 实现 `run/executor.py`（TestCaseExecutor）
2. 实现 `run/batch_runner.py`（BatchTestRunner）
3. 实现 `run/result_processor.py`（ResultProcessor）
4. 实现 `run/snapshot_manager.py`（SnapshotManager）
5. 实现 `run/facade.py`（RunEngineFacade）
6. 编写引擎集成测试

**删除**：
- `service/rag_test/test_run/` 整个目录
- `service/rag_test/snapshot_service.py`
- `service/rag_test/test_case_service.py`
- `service/rag_test/test_run_service.py`
- `service/rag_test/test_set_service.py`
- `service/rag_test/source_doc_service.py`

### Phase 4: 报告引擎（预计 2 天）

**目标**：统一双报告服务。

**后端任务**：
1. 实现 `report/builder.py`（ReportBuilder）
2. 实现 `report/markdown_renderer.py`（MarkdownRenderer）
3. 实现 `report/trend_analyzer.py`（TrendAnalyzer）
4. 实现 `report/exporter.py`（ReportExporter）
5. 实现 `report/facade.py`（ReportEngineFacade）
6. 编写引擎集成测试

**删除**：
- `service/rag_report_service.py`
- `service/report/` 整个目录

### Phase 5: 调优引擎（预计 2 天）

**目标**：替代 `core/tuning/`。

**后端任务**：
1. 实现 `tuning/advisor.py`（TuningAdvisor）
2. 实现 `tuning/conflict_detector.py`（ConflictDetector）
3. 实现 `tuning/impact_analyzer.py`（ImpactAnalyzer）
4. 实现 `tuning/facade.py`（TuningEngineFacade）
5. 编写引擎集成测试

**删除**：
- `core/tuning/` 整个目录
- `core/validation/` 整个目录

### Phase 6: 编排器与控制器（预计 2 天）

**目标**：统一入口，替代双服务层。

**后端任务**：
1. 实现 `orchestrator.py`（RagEvalOrchestrator）
2. 实现 `rag_eval_controller.py`（统一控制器）
3. 更新路由注册
4. 编写端到端测试

**删除**：
- `controller/rag_test_controller.py`
- `service/rag_test/facade.py`
- `service/rag_test/types.py`
- `service/rag_test/__init__.py`
- `service/rag_test_manager.py`（如存在）
- `service/rag_test/` 目录（确认已空后删除）

### Phase 7: 前端重构（预计 5 天）

**目标**：引入 TanStack Query、统一类型层、消除重复。

**任务**：
1. 实现 `entities/rag-eval/` 完整类型层
2. 实现 `api/rag-eval/` 完整 API 层
3. 实现 `hooks/useSSEProgress.ts`
4. 实现各 TanStack Query hooks
5. 实现共享组件（DomainTag、MetricScoreCard 等）
6. 重构各页面组件
7. 合并重复组件（GenerationConfigForm）
8. 更新路由配置
9. 编写 Hook 测试
10. 编写共享组件测试

**删除**：
- `api/rag-test/` 整个旧目录
- `features/rag-eval/pages/DraftManagementPage.tsx`
- `features/rag-eval/components/DraftGenerationPanel.tsx`
- `features/rag-eval/components/UploadWithGeneration.tsx`
- `features/rag-eval/components/RecommendationPanel/WizardMode.tsx`
- `features/rag-eval/components/RecommendationPanel/ExpertMode.tsx`
- `features/rag-eval/components/TrendChart/VersionTooltip.tsx`
- `features/rag-eval/components/TrendChart/ErrorBar.tsx`
- `features/rag-eval/components/ImpactPreview/index.tsx`（顶层）
- `entities/test-case/` 旧类型文件
- 旧的 hooks（`useTestSetStore.ts` 等）

### Phase 8: 清理与验收（预计 2 天）

**目标**：最终清理和全量验收。

**任务**：
1. 确认旧代码全部删除
2. 运行 `npm run typecheck` + `npm run lint`
3. 运行后端全量测试
4. 运行前端全量测试
5. 手动测试完整工作流
6. 更新 `.ai/` 目录文档
7. 更新 CLAUDE.md 中的相关引用

## 风险与缓解

| 风险 | 缓解措施 |
|---|---|
| Phase 1 指标计算器与 RAGAS 结果不一致 | 保留 RAGAS 库作为 fallback，自研计算器可切换 |
| Phase 3 快照恢复影响生产索引 | 快照恢复前自动创建当前索引备份 |
| Phase 7 前端大规模重构导致功能回归 | 逐页面迁移，每页迁移后手动测试 |
| LLM 依赖的指标（Faithfulness等）结果不稳定 | 多次运行取均值，配置化重试次数 |

## 时间线总览

```
Week 1: Phase 0 (2天) + Phase 1 (3天)
Week 2: Phase 2 (3天) + Phase 3 (3天)  
Week 3: Phase 4 (2天) + Phase 5 (2天) + Phase 6 (2天)
Week 4: Phase 7 (5天)
Week 5: Phase 8 (2天) + buffer
```

**预计总工期：~24 天（约 5 周）**
