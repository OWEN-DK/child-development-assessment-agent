# 02 - 六引擎后端架构

## 目录结构

```
backend/src/
├── controller/
│   └── rag_eval/                        # 控制器拆分为子控制器
│       ├── __init__.py
│       ├── registry.py                  # ~30行，统一注册所有子控制器到 router
│       ├── draft_controller.py          # ~80行，草稿端点
│       ├── case_controller.py           # ~80行，用例/集端点
│       ├── run_controller.py            # ~80行，运行端点
│       ├── metric_controller.py         # ~50行，指标/诊断端点
│       ├── report_controller.py         # ~50行，报告/趋势端点
│       ├── tuning_controller.py         # ~50行，调优端点
│       └── snapshot_controller.py       # ~40行，快照端点
│
├── service/
│   └── rag_eval/
│       ├── __init__.py
│       ├── orchestrator.py              # ~150行，跨引擎编排
│       │
│       ├── draft/                       # DraftEngine
│       │   ├── __init__.py
│       │   ├── facade.py                # ~120行
│       │   ├── generator.py             # ~200行
│       │   ├── faithfulness_checker.py  # ~150行
│       │   ├── deduplicator.py          # ~100行
│       │   └── book_analyzer.py         # ~120行
│       │
│       ├── case/                        # CaseEngine（新增）
│       │   ├── __init__.py
│       │   ├── facade.py                # ~150行
│       │   ├── case_service.py          # ~150行
│       │   └── set_service.py           # ~120行
│       │
│       ├── run/                         # RunEngine
│       │   ├── __init__.py
│       │   ├── facade.py                # ~120行
│       │   ├── executor.py              # ~120行
│       │   ├── batch_runner.py          # ~180行
│       │   ├── result_processor.py      # ~100行
│       │   └── snapshot_manager.py      # ~120行
│       │
│       ├── metrics/                     # MetricEngine（双轨）
│       │   ├── __init__.py
│       │   ├── facade.py                # ~120行
│       │   ├── scoring/                 # 三层标准化指标
│       │   │   ├── __init__.py
│       │   │   ├── base.py              # ~40行
│       │   │   ├── registry.py          # ~60行
│       │   │   ├── facade.py            # ~80行（ScoringFacade）
│       │   │   ├── retrieval.py         # ~200行
│       │   │   ├── generation.py        # ~180行
│       │   │   ├── system.py            # ~150行
│       │   │   └── calculators/
│       │   │       ├── __init__.py
│       │   │       ├── precision_recall.py  # ~80行
│       │   │       ├── mrr_ndcg.py          # ~100行
│       │   │       ├── faithfulness_calc.py # ~120行
│       │   │       ├── groundedness_calc.py # ~100行
│       │   │       └── answer_relevancy_calc.py # ~120行
│       │   └── diagnosis/               # 六层诊断引擎
│       │       ├── __init__.py
│       │       ├── orchestrator.py      # ~80行
│       │       ├── layer1_rules.py      # ~100行
│       │       ├── layer2_history.py    # ~100行
│       │       ├── layer3_llm.py        # ~120行
│       │       ├── layer4_data_quality.py # ~100行
│       │       ├── layer5_effect.py     # ~100行
│       │       └── layer6_regression.py # ~100行
│       │
│       ├── report/                      # ReportEngine
│       │   ├── __init__.py
│       │   ├── facade.py                # ~100行
│       │   ├── builder.py               # ~200行（双轨整合）
│       │   ├── markdown_renderer.py     # ~100行
│       │   ├── trend_analyzer.py        # ~120行
│       │   └── exporter.py              # ~100行
│       │
│       └── tuning/                      # TuningEngine
│           ├── __init__.py
│           ├── facade.py                # ~100行
│           ├── advisor.py               # ~150行
│           ├── conflict_detector.py     # ~100行
│           └── config_changer.py        # ~120行
│
├── schemas/
│   └── rag_eval/                        # 实体类集中管理
│       ├── __init__.py                  # 统一导出
│       ├── source_document.py           # SourceDocumentRead, SourceDocumentUpload
│       ├── draft.py                     # DraftCreate, DraftRead, DraftUpdate, DraftReview, DraftList, DraftGenerationConfig, BookMetadata
│       ├── test_case.py                 # TestCaseCreate, TestCaseRead, TestCaseUpdate, TestCaseList, TestCaseImportItem, TestCaseImportData
│       ├── test_set.py                  # TestSetCreate, TestSetRead, TestSetUpdate, TestSetExport
│       ├── test_run.py                  # TestRunCreate, TestRunRead, TestRunList, TestRunResultItem, RunComparison, RetrievalMetrics
│       ├── metrics.py                   # MetricScore, MetricInput, MetricOutput, Layer1Metrics, Layer2Metrics, Layer3Metrics, RunMetrics
│       ├── diagnosis.py                 # LayerIssue, LayerResult, DiagnosisResult
│       ├── report.py                    # OverallSummary, MetricCard, ScoringDashboard, DiagnosisSection, BadCaseEntry, TuningEntry, EvalReportData, EvalReportRead, TrendData
│       ├── snapshot.py                  # SnapshotRead, SnapshotCreate
│       └── tuning.py                    # TuningSuggestion, ConflictPair, ConfigVersionRead, ConfigChangeSetRead
│
├── models/
│   └── rag_eval/                        # ORM 模型（重写）
│       ├── __init__.py
│       ├── enums.py                     # 统一枚举
│       ├── draft.py
│       ├── test_case.py
│       ├── test_set.py
│       ├── test_run.py
│       ├── snapshot.py
│       ├── report.py
│       ├── tuning.py
│       └── config.py
│
│   # source_documents ORM 保留在 models/document.py（不迁移到 rag_eval/ 下）
│
├── repository/
│   └── rag_eval/                        # RAG Eval Repository（新目录）
│       ├── __init__.py
│       ├── draft_repository.py
│       ├── test_case_repository.py      # 替代旧 test_case_repository.py
│       ├── test_set_repository.py
│       ├── test_set_case_repository.py
│       ├── test_run_repository.py
│       ├── test_run_result_repository.py
│       ├── snapshot_repository.py
│       ├── report_repository.py
│       ├── tuning_suggestion_repository.py
│       └── config_version_repository.py
│
└── utils/
    ├── orm_mapper.py                    # ORM→Pydantic 统一映射
    ├── embedding_helper.py              # Embedding 缓存+计算
    ├── similarity.py                    # cosine/欧氏距离
    ├── age_stage.py                     # 年龄→年龄段标签映射（DraftEngine/CaseEngine 共用）
    └── rule_check_engine.py             # 规则检查引擎（L3 RuleCompliance + Layer1 Rules 共享）
```

## 编排器设计

```python
class RagEvalOrchestrator:
    """跨引擎协调器"""

    def __init__(
        self,
        draft_engine: DraftEngineFacade,
        case_engine: CaseEngineFacade,
        run_engine: RunEngineFacade,
        metric_engine: MetricEngineFacade,
        report_engine: ReportEngineFacade,
        tuning_engine: TuningEngineFacade,
    ): ...

    async def run_full_evaluation(self, test_set_ids: list[str], config: EvalConfig) -> str:
        """完整评估：快照→执行→双轨指标→报告→调优"""
        snapshot_id = await self.run_engine.create_snapshot()
        run_id = await self.run_engine.execute_batch(test_set_ids, snapshot_id, config)
        metrics = await self.metric_engine.calculate_all(run_id)
        diagnosis = await self.metric_engine.diagnose_all(run_id)
        report = await self.report_engine.build(run_id, metrics, diagnosis)
        suggestions = await self.tuning_engine.analyze(run_id, metrics, diagnosis)
        return run_id

    async def generate_and_review_drafts(self, doc_id: str, config: DraftConfig) -> str:
        """草稿全流程"""
        task_id = await self.draft_engine.start_generation(doc_id, config)
        return task_id
```

## 控制器设计（拆分为子控制器）

由于总端点 40+ 个，单文件超 500 行风险高，拆分为 7 个子控制器 + 1 个注册器。

```python
# controller/rag_eval/registry.py
class RagEvalControllerRegistry:
    """统一注册所有子控制器到 router"""

    def __init__(
        self,
        draft_ctrl: DraftController,
        case_ctrl: CaseController,
        run_ctrl: RunController,
        metric_ctrl: MetricController,
        report_ctrl: ReportController,
        tuning_ctrl: TuningController,
        snapshot_ctrl: SnapshotController,
    ): ...

    def register_all(self, router: APIRouter) -> None:
        """统一注册，路由前缀 /rag/eval/"""
        self._draft_ctrl.register(router)
        self._case_ctrl.register(router)
        self._run_ctrl.register(router)
        self._metric_ctrl.register(router)
        self._report_ctrl.register(router)
        self._tuning_ctrl.register(router)
        self._snapshot_ctrl.register(router)

# 每个子控制器示例（draft_controller.py ~80行）
class DraftController:
    """草稿管理端点"""

    def __init__(self, draft_engine: DraftEngineFacade): ...

    def register(self, router: APIRouter) -> None:
        router.add_api_route("/drafts", self.list_drafts, methods=["GET"])
        router.add_api_route("/drafts/{draft_id}", self.get_draft, methods=["GET"])
        # ...每个端点 ~5-8 行（参数校验 + facade 调用 + APIResponse 包装）
```

## DI 注入

### 关键设计：跨 Module 依赖

`RunEngine` 中的 `TestCaseExecutor` 依赖 `RetrievalFacade` 和 `RagService`，这两个接口由现有 `CoreModule` 提供。`RagEvalModule` 通过构造函数参数从 `injector` 自动获取跨 Module 依赖。

### 装饰器顺序说明

`injector` 库要求 `@singleton` 在 `@provider` **之上**（先 singleton 再 provider）。

```python
from injector import Module, provider, singleton

class RagEvalModule(Module):
    """RAG 评估引擎依赖注入模块
    注意：旧 RepositoryModule 中的 SourceDocumentRepository、ConfigVersionRepository
    需在 RagEvalModule 注册前从 RepositoryModule 中移除，避免同名 Provider 冲突。
    """

    # Repository 层（RagEvalModule 负责所有 RAG Eval 专用 Repository）
    @singleton
    @provider
    def provide_draft_repository(self) -> DraftRepository: ...

    @singleton
    @provider
    def provide_test_case_repository(self) -> TestCaseRepository: ...

    @singleton
    @provider
    def provide_test_set_repository(self) -> TestSetRepository: ...

    @singleton
    @provider
    def provide_test_set_case_repository(self) -> TestSetCaseRepository: ...

    @singleton
    @provider
    def provide_test_run_repository(self) -> TestRunRepository: ...

    @singleton
    @provider
    def provide_test_run_result_repository(self) -> TestRunResultRepository: ...

    @singleton
    @provider
    def provide_snapshot_repository(self) -> SnapshotRepository: ...

    @singleton
    @provider
    def provide_report_repository(self) -> ReportRepository: ...

    @singleton
    @provider
    def provide_tuning_suggestion_repository(self) -> TuningSuggestionRepository: ...

    @singleton
    @provider
    def provide_config_version_repository(self) -> ConfigVersionRepository: ...

    # 共享工具
    @singleton
    @provider
    def provide_embedding_helper(self) -> EmbeddingHelper: ...

    @singleton
    @provider
    def provide_orm_mapper(self) -> OrmMapper: ...

    # 三层指标计算器注册
    @singleton
    @provider
    def provide_metric_registry(self) -> MetricRegistry: ...

    # 六层诊断编排器
    @singleton
    @provider
    def provide_diagnosis_orchestrator(self) -> DiagnosisOrchestrator: ...

    # 引擎 Facade
    @singleton
    @provider
    def provide_draft_engine_facade(self, ...) -> DraftEngineFacade: ...

    @singleton
    @provider
    def provide_case_engine_facade(self, ...) -> CaseEngineFacade: ...

    @singleton
    @provider
    def provide_run_engine_facade(
        self,
        executor: TestCaseExecutor,
        batch_runner: BatchTestRunner,
        # RetrievalFacade 和 RagService 由 CoreModule 自动注入
        # 无需在此声明，injector 会跨 Module 解析
    ) -> RunEngineFacade: ...

    @singleton
    @provider
    def provide_metric_engine_facade(self, ...) -> MetricEngineFacade: ...

    @singleton
    @provider
    def provide_report_engine_facade(self, ...) -> ReportEngineFacade: ...

    @singleton
    @provider
    def provide_tuning_engine_facade(self, ...) -> TuningEngineFacade: ...

    # 编排器
    @singleton
    @provider
    def provide_rag_eval_orchestrator(self, ...) -> RagEvalOrchestrator: ...

    # 控制器注册器
    @singleton
    @provider
    def provide_controller_registry(self, ...) -> RagEvalControllerRegistry: ...

# 更新全局注入器
# 注意：SourceDocumentRepository 保留在 RepositoryModule（旧表保留）
# ConfigVersionRepository 从 RepositoryModule 和 di_container.py 移除，改由 RagEvalModule 提供
# 迁移前需 grep 所有 ConfigVersionRepository 的 import，确认无其他模块依赖：
#   - config/core/manager.py 直接实例化 ConfigVersionRepository → 改为通过 injector 注入
#   - core/di_container.py provide_config_version_repository → 移除，由 RagEvalModule 接管
#   - repository/__init__.py 导出 → 保留（仅导出，不影响 DI）
injector = Injector([CoreModule(), RepositoryModule(), TaskModule(), RagEvalModule()])
```

## OrmMapper 设计

统一 ORM→Pydantic 转换工具，消除各 service 中的手动序列化代码。

```python
class OrmMapper:
    """ORM 模型 → Pydantic Schema 统一映射工具

    职责：
    1. 处理 Enum 值转换（ORM Enum → Python str）
    2. 处理 JSON 字段序列化/反序列化（MySQL JSON → Python dict/list）
    3. 处理时间格式转换（datetime → ISO 8601 str）
    4. 处理 None 值默认化
    """

    def __init__(self): ...

    @staticmethod
    def to_read(orm_obj: Base, schema_cls: type[T]) -> T:
        """通用 ORM→Pydantic 转换

        自动提取 ORM 列属性，跳过 SQLAlchemy 内部属性。
        Enum 字段自动取 .value。
        datetime 字段自动转 ISO 格式字符串。
        """

    @staticmethod
    def to_read_list(orm_objs: list[Base], schema_cls: type[T]) -> list[T]:
        """批量转换"""

    @staticmethod
    def safe_enum_value(val: Any) -> Any:
        """Enum 安全取值，非 Enum 原样返回"""

    @staticmethod
    def safe_isoformat(val: datetime | None) -> str | None:
        """datetime 安全转 ISO 字符串"""
```

## 删除的旧代码

| 类型 | 文件/目录 | 行数 |
|------|----------|------|
| Legacy 服务 | `service/rag_test/` 整个目录（17文件） | ~3,900 |
| Legacy 控制器 | `controller/rag_test_controller.py` | 996 |
| Legacy ORM | `models/test_case.py` | 313 |
| Legacy Schema | `schemas/test_case.py` | 404 |
| RagEval ORM | `models/rag_eval/` 整个目录（21文件） | ~1,200 |
| RagEval Schema | `schemas/rag_eval.py`、`schemas/tuning.py` | ~220 |
| RagEval 服务 | `trend_service.py`、`export_service.py`、`tuning_suggestion_service.py` 等 7 个 | ~2,000 |
| RagEval 控制器 | `tuning_controller.py`、`report_controller.py` 等 8 个 | ~1,500 |
| 校验引擎 | `core/validation/` 整个目录（19文件） | ~2,000 |
| 调优引擎 | `core/tuning/` 整个目录（6文件） | ~800 |
| 报告服务 | `service/rag_report_service.py`、`service/report/` | ~846 |
| 旧 Repository | `repository/test_case_repository.py` | 115 |

**总计删除：~14,300 行**
