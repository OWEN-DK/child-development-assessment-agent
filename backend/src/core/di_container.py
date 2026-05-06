from collections.abc import Callable
from injector import Injector, Module, provider, singleton

from src.config import settings
from src.config.core.manager import ConfigManager
from src.core.database import async_session_factory
from src.core.interfaces import (ICacheService, IDocumentIngestionService,
                                 IIndexManager, IRetrievalService)
from src.core.llm.factory import LLMServiceFactory
from src.core.llm.provider_registry import ProviderRegistry
from src.repository import (ABTestMetricRepository, ConfigAuditLogRepository,
                            DocumentRecordRepository, LLMCallLogRepository,
                            SourceDocumentRepository)
from src.repository.rag_eval import (
    ConfigChangeSetRepository, ConfigVersionRepository, DraftRepository,
    ReportRepository, SnapshotRepository, TestCaseRepository,
    TestRunRepository, TestRunResultRepository, TestSetCaseRepository,
    TestSetRepository, TuningSuggestionRepository,
)
from src.utils.embedding_helper import EmbeddingHelper
from src.utils.orm_mapper import OrmMapper
from src.service.rag_eval.metrics.scoring.calculators.answer_relevancy_calc import \
    AnswerRelevancyCalculator
from src.service.rag_eval.metrics.scoring.calculators.faithfulness_calc import \
    FaithfulnessCalculator
from src.service.rag_eval.metrics.scoring.calculators.groundedness_calc import \
    GroundednessCalculator
from src.service.rag_eval.metrics.scoring.calculators.mrr_ndcg import MRR, NDCG
from src.service.rag_eval.metrics.scoring.calculators.precision_recall import (
    ContextRecall, NoiseSensitivity, PrecisionAtK, RuleComplianceCalculator,
)
from src.service.rag_eval.metrics.scoring.system import (
    ConfigStabilityCalculator, CostEfficiencyCalculator, RegressionScoreCalculator,
)
from src.service.rag_eval.metrics.scoring.facade import ScoringFacade
from src.service.rag_eval.metrics.scoring.generation import GenerationScorer
from src.service.rag_eval.metrics.scoring.registry import MetricRegistry
from src.service.rag_eval.metrics.scoring.retrieval import RetrievalScorer
from src.service.rag_eval.metrics.scoring.system import SystemScorer
from src.service.rag_eval.metrics.diagnosis.layer1_rules import Layer1Rules
from src.service.rag_eval.metrics.diagnosis.layer2_history import Layer2History
from src.service.rag_eval.metrics.diagnosis.layer3_llm import Layer3LLM
from src.service.rag_eval.metrics.diagnosis.layer4_data_quality import Layer4DataQuality
from src.service.rag_eval.metrics.diagnosis.layer5_effect import Layer5Effect
from src.service.rag_eval.metrics.diagnosis.layer6_regression import Layer6Regression
from src.service.rag_eval.metrics.diagnosis.orchestrator import DiagnosisOrchestrator
from src.service.rag_eval.metrics.facade import MetricEngineFacade
from src.service.rag_eval.draft.book_analyzer import BookMetadataAnalyzer
from src.service.rag_eval.draft.deduplicator import DraftDeduplicator
from src.service.rag_eval.draft.facade import DraftEngineFacade
from src.service.rag_eval.draft.faithfulness_checker import FaithfulnessChecker
from src.service.rag_eval.draft.generator import DraftGenerator
from src.service.rag_eval.case.case_service import CaseService
from src.service.rag_eval.case.facade import CaseEngineFacade
from src.service.rag_eval.case.set_service import SetService
from src.service.rag_eval.run.batch_runner import BatchTestRunner
from src.service.rag_eval.run.executor import TestCaseExecutor
from src.service.rag_eval.run.facade import RunEngineFacade
from src.service.rag_eval.run.result_processor import ResultProcessor
from src.service.rag_eval.run.snapshot_manager import SnapshotManager
from src.service.rag_eval.report.builder import ReportBuilder
from src.service.rag_eval.report.exporter import ReportExporter
from src.service.rag_eval.report.facade import ReportEngineFacade
from src.service.rag_eval.report.markdown_renderer import MarkdownRenderer
from src.service.rag_eval.report.trend_analyzer import TrendAnalyzer
from src.service.rag_eval.tuning.advisor import TuningAdvisor
from src.service.rag_eval.tuning.conflict_detector import ConflictDetector
from src.service.rag_eval.tuning.config_changer import ConfigChanger
from src.service.rag_eval.tuning.facade import TuningEngineFacade
from src.service.rag_eval.orchestrator import RagEvalOrchestrator
from src.controller.rag_eval.case_controller import CaseController
from src.controller.rag_eval.draft_controller import DraftController
from src.controller.rag_eval.metric_controller import MetricController
from src.controller.rag_eval.registry import RagEvalControllerRegistry
from src.controller.rag_eval.report_controller import ReportController
from src.controller.rag_eval.run_controller import RunController
from src.controller.rag_eval.snapshot_controller import SnapshotController
from src.controller.rag_eval.tuning_controller import TuningController
from src.service.task_state_service import TaskStateService


class CoreModule(Module):
    @provider
    @singleton
    def provide_index_manager(self) -> IIndexManager:
        from src.service.index_manager_service import IndexManagerService

        return IndexManagerService()

    @provider
    @singleton
    def provide_cache_service(self) -> ICacheService:
        from src.service.cache_service import CacheService

        return CacheService()

    @provider
    @singleton
    def provide_retrieval_service(
        self, index_manager: IIndexManager, cache_service: ICacheService
    ) -> IRetrievalService:
        from src.service.retrieval_service import get_retrieval_service

        return get_retrieval_service(index_manager, cache_service)

    @provider
    @singleton
    def provide_document_ingestion_service(
        self, index_manager: IIndexManager
    ) -> IDocumentIngestionService:
        from src.service.document_ingestion_service import \
            DocumentIngestionService

        return DocumentIngestionService(index_manager)


class RepositoryModule(Module):
    """Repository依赖注入模块

    所有Repository共享同一个session_factory实例，
    每个方法内部独立创建session，保证并发安全。
    注意：旧 test case 相关 Repository 已迁移至 RagEvalModule。
    """

    @provider
    @singleton
    def provide_config_audit_log_repository(self) -> ConfigAuditLogRepository:
        return ConfigAuditLogRepository(async_session_factory)

    @provider
    @singleton
    def provide_source_document_repository(self) -> SourceDocumentRepository:
        return SourceDocumentRepository(async_session_factory)

    @provider
    @singleton
    def provide_document_record_repository(self) -> DocumentRecordRepository:
        return DocumentRecordRepository(async_session_factory)

    @provider
    @singleton
    def provide_llm_call_log_repository(self) -> LLMCallLogRepository:
        return LLMCallLogRepository(async_session_factory)

    @provider
    @singleton
    def provide_ab_test_metric_repository(self) -> ABTestMetricRepository:
        return ABTestMetricRepository(async_session_factory)


class RagEvalModule(Module):
    """RAG 评估引擎依赖注入模块

    负责所有 RAG Eval 专用 Repository 和共享工具。
    引擎 Facade 和控制器在 Phase 1-7 逐步添加。
    """

    # ── Repository 层 ───────────────────────────────

    @singleton
    @provider
    def provide_draft_repository(self) -> DraftRepository:
        return DraftRepository(async_session_factory)

    @singleton
    @provider
    def provide_test_case_repository(self) -> TestCaseRepository:
        return TestCaseRepository(async_session_factory)

    @singleton
    @provider
    def provide_test_set_repository(self) -> TestSetRepository:
        return TestSetRepository(async_session_factory)

    @singleton
    @provider
    def provide_test_set_case_repository(self) -> TestSetCaseRepository:
        return TestSetCaseRepository(async_session_factory)

    @singleton
    @provider
    def provide_test_run_repository(self) -> TestRunRepository:
        return TestRunRepository(async_session_factory)

    @singleton
    @provider
    def provide_test_run_result_repository(self) -> TestRunResultRepository:
        return TestRunResultRepository(async_session_factory)

    @singleton
    @provider
    def provide_snapshot_repository(self) -> SnapshotRepository:
        return SnapshotRepository(async_session_factory)

    @singleton
    @provider
    def provide_report_repository(self) -> ReportRepository:
        return ReportRepository(async_session_factory)

    @singleton
    @provider
    def provide_tuning_suggestion_repository(self) -> TuningSuggestionRepository:
        return TuningSuggestionRepository(async_session_factory)

    @singleton
    @provider
    def provide_config_version_repository(self) -> ConfigVersionRepository:
        return ConfigVersionRepository(async_session_factory)

    @singleton
    @provider
    def provide_config_change_set_repository(self) -> ConfigChangeSetRepository:
        return ConfigChangeSetRepository(async_session_factory)

    # ── 共享工具 ────────────────────────────────────

    @singleton
    @provider
    def provide_orm_mapper(self) -> OrmMapper:
        return OrmMapper()

    @singleton
    @provider
    def provide_embedding_helper(self) -> EmbeddingHelper:
        return EmbeddingHelper(
            model_name=settings.embedding_model_name,
            api_key=settings.dashscope_api_key,
            embed_batch_size=settings.embedding_batch_size,
        )

    # ── 年龄工具 ────────────────────────────────────

    # ── Phase 1: MetricEngine 三层指标计算器 ─────────

    @singleton
    @provider
    def provide_precision_at_k(self) -> PrecisionAtK:
        return PrecisionAtK()

    @singleton
    @provider
    def provide_context_recall(self) -> ContextRecall:
        return ContextRecall()

    @singleton
    @provider
    def provide_noise_sensitivity(self) -> NoiseSensitivity:
        return NoiseSensitivity()

    @singleton
    @provider
    def provide_mrr(self) -> MRR:
        return MRR()

    @singleton
    @provider
    def provide_ndcg(self) -> NDCG:
        return NDCG()

    @singleton
    @provider
    def provide_llm_factory(self) -> LLMServiceFactory:
        return LLMServiceFactory(
            config_manager=ConfigManager(),
            provider_registry=ProviderRegistry(),
        )

    @singleton
    @provider
    def provide_faithfulness_calculator(self, llm_factory: LLMServiceFactory) -> FaithfulnessCalculator:
        return FaithfulnessCalculator(llm_factory=llm_factory)

    @singleton
    @provider
    def provide_answer_relevancy_calculator(self, llm_factory: LLMServiceFactory) -> AnswerRelevancyCalculator:
        return AnswerRelevancyCalculator(llm_factory=llm_factory)

    @singleton
    @provider
    def provide_groundedness_calculator(self, llm_factory: LLMServiceFactory) -> GroundednessCalculator:
        return GroundednessCalculator(llm_factory=llm_factory)

    @singleton
    @provider
    def provide_rule_compliance_calculator(self) -> RuleComplianceCalculator:
        return RuleComplianceCalculator()

    @singleton
    @provider
    def provide_regression_score_calculator(self) -> RegressionScoreCalculator:
        return RegressionScoreCalculator()

    @singleton
    @provider
    def provide_cost_efficiency_calculator(self) -> CostEfficiencyCalculator:
        return CostEfficiencyCalculator()

    @singleton
    @provider
    def provide_config_stability_calculator(self) -> ConfigStabilityCalculator:
        return ConfigStabilityCalculator()

    @singleton
    @provider
    def provide_metric_registry(
        self,
        precision_at_k: PrecisionAtK,
        context_recall: ContextRecall,
        noise_sensitivity: NoiseSensitivity,
        mrr: MRR,
        ndcg: NDCG,
        faithfulness_calculator: FaithfulnessCalculator,
        answer_relevancy_calculator: AnswerRelevancyCalculator,
        groundedness_calculator: GroundednessCalculator,
        rule_compliance_calculator: RuleComplianceCalculator,
        regression_score_calculator: RegressionScoreCalculator,
        cost_efficiency_calculator: CostEfficiencyCalculator,
        config_stability_calculator: ConfigStabilityCalculator,
    ) -> MetricRegistry:
        registry = MetricRegistry()
        registry.register(precision_at_k)
        registry.register(context_recall)
        registry.register(noise_sensitivity)
        registry.register(mrr)
        registry.register(ndcg)
        registry.register(faithfulness_calculator)
        registry.register(answer_relevancy_calculator)
        registry.register(groundedness_calculator)
        registry.register(rule_compliance_calculator)
        registry.register(regression_score_calculator)
        registry.register(cost_efficiency_calculator)
        registry.register(config_stability_calculator)
        return registry

    # ── Phase 1: MetricEngine 三层门面 ──────────────

    @singleton
    @provider
    def provide_retrieval_scorer(self, registry: MetricRegistry) -> RetrievalScorer:
        return RetrievalScorer(registry)

    @singleton
    @provider
    def provide_generation_scorer(self, registry: MetricRegistry) -> GenerationScorer:
        return GenerationScorer(registry)

    @singleton
    @provider
    def provide_system_scorer(self, registry: MetricRegistry) -> SystemScorer:
        return SystemScorer(registry)

    @singleton
    @provider
    def provide_scoring_facade(self, registry: MetricRegistry, retrieval: RetrievalScorer, generation: GenerationScorer, system: SystemScorer) -> ScoringFacade:
        return ScoringFacade(registry, retrieval, generation, system)

    # ── Phase 1: MetricEngine 六层诊断 ───────────────

    @singleton
    @provider
    def provide_layer1_rules(self) -> Layer1Rules:
        return Layer1Rules()

    @singleton
    @provider
    def provide_layer2_history(self, test_run_repository: TestRunRepository) -> Layer2History:
        return Layer2History(test_run_repository)

    @singleton
    @provider
    def provide_layer3_llm(self) -> Layer3LLM:
        return Layer3LLM()

    @singleton
    @provider
    def provide_layer4_data_quality(self) -> Layer4DataQuality:
        return Layer4DataQuality()

    @singleton
    @provider
    def provide_layer5_effect(self, embedding_helper: EmbeddingHelper) -> Layer5Effect:
        return Layer5Effect(embedding_helper)

    @singleton
    @provider
    def provide_layer6_regression(self) -> Layer6Regression:
        return Layer6Regression()

    @singleton
    @provider
    def provide_diagnosis_orchestrator(self, layer1: Layer1Rules, layer2: Layer2History, layer3: Layer3LLM, layer4: Layer4DataQuality, layer5: Layer5Effect, layer6: Layer6Regression) -> DiagnosisOrchestrator:
        layers = {
            1: layer1,
            2: layer2,
            3: layer3,
            4: layer4,
            5: layer5,
            6: layer6,
        }
        return DiagnosisOrchestrator(layers)

    # ── Phase 1: MetricEngineFacade 双轨门面 ─────────

    @singleton
    @provider
    def provide_metric_engine_facade(self, scoring_facade: ScoringFacade, diagnosis_orchestrator: DiagnosisOrchestrator) -> MetricEngineFacade:
        return MetricEngineFacade(scoring_facade, diagnosis_orchestrator)

    # ── Phase 2: DraftEngine 子组件 ───────────────────

    @singleton
    @provider
    def provide_draft_generator(self, embedding_helper: EmbeddingHelper) -> DraftGenerator:
        return DraftGenerator(embedding_helper=embedding_helper)

    @singleton
    @provider
    def provide_faithfulness_checker(self, embedding_helper: EmbeddingHelper) -> FaithfulnessChecker:
        return FaithfulnessChecker(embedding_helper=embedding_helper)

    @singleton
    @provider
    def provide_draft_deduplicator(self, embedding_helper: EmbeddingHelper, draft_repository: DraftRepository) -> DraftDeduplicator:
        return DraftDeduplicator(embedding_helper=embedding_helper, draft_repository=draft_repository)

    @singleton
    @provider
    def provide_book_analyzer(self) -> BookMetadataAnalyzer:
        return BookMetadataAnalyzer()

    # ── Phase 2: DraftEngineFacade ────────────────────

    @singleton
    @provider
    def provide_draft_engine_facade(
        self, draft_generator: DraftGenerator, faithfulness_checker: FaithfulnessChecker, draft_deduplicator: DraftDeduplicator,
        book_analyzer: BookMetadataAnalyzer, draft_repository: DraftRepository, test_case_repository: TestCaseRepository,
        source_document_repository: SourceDocumentRepository,
    ) -> DraftEngineFacade:
        return DraftEngineFacade(
            draft_generator=draft_generator,
            faithfulness_checker=faithfulness_checker,
            deduplicator=draft_deduplicator,
            book_analyzer=book_analyzer,
            draft_repository=draft_repository,
            test_case_repository=test_case_repository,
            source_document_repository=source_document_repository,
        )

    # ── Phase 3: CaseEngine 子组件 ────────────────────

    @singleton
    @provider
    def provide_case_service(self, test_case_repository: TestCaseRepository, test_set_case_repository: TestSetCaseRepository, orm_mapper: OrmMapper) -> CaseService:
        return CaseService(test_case_repository, test_set_case_repository, orm_mapper)

    @singleton
    @provider
    def provide_set_service(
        self, test_set_repository: TestSetRepository, test_set_case_repository: TestSetCaseRepository,
        test_case_repository: TestCaseRepository, orm_mapper: OrmMapper,
    ) -> SetService:
        return SetService(test_set_repository, test_set_case_repository, test_case_repository, orm_mapper)

    # ── Phase 3: CaseEngineFacade ─────────────────────

    @singleton
    @provider
    def provide_case_engine_facade(self, case_service: CaseService, set_service: SetService) -> CaseEngineFacade:
        return CaseEngineFacade(case_service, set_service)

    # ── Phase 4: RunEngine 子组件 ─────────────────────

    @singleton
    @provider
    def provide_test_case_executor(self, test_run_result_repository: TestRunResultRepository) -> TestCaseExecutor:
        return TestCaseExecutor(test_run_result_repository)

    @singleton
    @provider
    def provide_result_processor(self, test_run_repository: TestRunRepository, test_run_result_repository: TestRunResultRepository, orm_mapper: OrmMapper) -> ResultProcessor:
        return ResultProcessor(test_run_repository, test_run_result_repository, orm_mapper)

    @singleton
    @provider
    def provide_batch_runner(
        self, test_case_executor: TestCaseExecutor, result_processor: ResultProcessor,
        test_run_repository: TestRunRepository, test_run_result_repository: TestRunResultRepository,
    ) -> BatchTestRunner:
        from src.api.sse import SSEPublisher
        return BatchTestRunner(
            executor=test_case_executor,
            result_processor=result_processor,
            test_run_repository=test_run_repository,
            test_run_result_repository=test_run_result_repository,
            sse_publisher=SSEPublisher,
        )

    @singleton
    @provider
    def provide_snapshot_manager(self, snapshot_repository: SnapshotRepository) -> SnapshotManager:
        return SnapshotManager(snapshot_repository=snapshot_repository)

    # ── Phase 4: RunEngineFacade ──────────────────────

    @singleton
    @provider
    def provide_run_engine_facade(
        self, test_case_executor: TestCaseExecutor, batch_runner: BatchTestRunner, result_processor: ResultProcessor,
        snapshot_manager: SnapshotManager, test_run_repository: TestRunRepository, test_run_result_repository: TestRunResultRepository,
        case_engine_facade: CaseEngineFacade, retrieval_service: IRetrievalService,
    ) -> RunEngineFacade:
        from src.core.llm.factory import LLMServiceFactoryCompat
        generation_llm = LLMServiceFactoryCompat.create(model_name="qwen-plus")
        facade = RunEngineFacade(
            executor=test_case_executor,
            batch_runner=batch_runner,
            result_processor=result_processor,
            snapshot_manager=snapshot_manager,
            test_run_repository=test_run_repository,
            test_run_result_repository=test_run_result_repository,
            case_engine=case_engine_facade,
            retrieval_service=retrieval_service,
            generation_service=generation_llm,
        )
        # batch_runner 通过 facade 引用获取检索/生成函数
        batch_runner._facade = facade
        return facade

    # ── Phase 5: ReportEngine 子组件 ──────────────────

    @singleton
    @provider
    def provide_report_builder(
        self, test_run_repository: TestRunRepository, test_run_result_repository: TestRunResultRepository,
        tuning_suggestion_repository: TuningSuggestionRepository, orm_mapper: OrmMapper,
    ) -> ReportBuilder:
        return ReportBuilder(
            test_run_repository=test_run_repository,
            test_run_result_repository=test_run_result_repository,
            tuning_suggestion_repository=tuning_suggestion_repository,
            orm_mapper=orm_mapper,
        )

    @singleton
    @provider
    def provide_markdown_renderer(self) -> MarkdownRenderer:
        return MarkdownRenderer()

    @singleton
    @provider
    def provide_trend_analyzer(
        self, report_repository: ReportRepository, test_run_repository: TestRunRepository, config_version_repository: ConfigVersionRepository,
    ) -> TrendAnalyzer:
        return TrendAnalyzer(report_repository, test_run_repository, config_version_repository)

    @singleton
    @provider
    def provide_report_exporter(self) -> ReportExporter:
        return ReportExporter()

    # ── Phase 5: ReportEngineFacade ───────────────────

    @singleton
    @provider
    def provide_report_engine_facade(
        self, report_builder: ReportBuilder, markdown_renderer: MarkdownRenderer, trend_analyzer: TrendAnalyzer,
        report_exporter: ReportExporter, report_repository: ReportRepository, test_run_repository: TestRunRepository, orm_mapper: OrmMapper,
        metric_engine_facade: MetricEngineFacade, run_engine_facade: RunEngineFacade,
    ) -> ReportEngineFacade:
        return ReportEngineFacade(
            builder=report_builder,
            markdown_renderer=markdown_renderer,
            trend_analyzer=trend_analyzer,
            exporter=report_exporter,
            report_repository=report_repository,
            test_run_repository=test_run_repository,
            orm_mapper=orm_mapper,
            metric_engine=metric_engine_facade,
            run_engine=run_engine_facade,
        )

    # ── Phase 6: TuningEngine 子组件 ──────────────────

    @singleton
    @provider
    def provide_tuning_advisor(self) -> TuningAdvisor:
        return TuningAdvisor()

    @singleton
    @provider
    def provide_conflict_detector(self) -> ConflictDetector:
        return ConflictDetector()

    @singleton
    @provider
    def provide_config_changer(
        self, config_version_repository: ConfigVersionRepository, config_change_set_repository: ConfigChangeSetRepository, orm_mapper: OrmMapper,
    ) -> ConfigChanger:
        return ConfigChanger(
            config_version_repo=config_version_repository,
            change_set_repo=config_change_set_repository,
            orm_mapper=orm_mapper,
        )

    # ── Phase 6: TuningEngineFacade ───────────────────

    @singleton
    @provider
    def provide_tuning_engine_facade(
        self, tuning_advisor: TuningAdvisor, conflict_detector: ConflictDetector, config_changer: ConfigChanger,
        tuning_suggestion_repository: TuningSuggestionRepository,
    ) -> TuningEngineFacade:
        return TuningEngineFacade(
            advisor=tuning_advisor,
            conflict_detector=conflict_detector,
            config_changer=config_changer,
            suggestion_repo=tuning_suggestion_repository,
        )

    # ── Phase 7: RagEvalOrchestrator ──────────────────

    @singleton
    @provider
    def provide_rag_eval_orchestrator(
        self, draft_engine_facade: DraftEngineFacade, case_engine_facade: CaseEngineFacade, run_engine_facade: RunEngineFacade,
        metric_engine_facade: MetricEngineFacade, report_engine_facade: ReportEngineFacade, tuning_engine_facade: TuningEngineFacade,
        batch_runner: BatchTestRunner,
    ) -> RagEvalOrchestrator:
        orchestrator = RagEvalOrchestrator(
            draft_engine=draft_engine_facade,
            case_engine=case_engine_facade,
            run_engine=run_engine_facade,
            metric_engine=metric_engine_facade,
            report_engine=report_engine_facade,
            tuning_engine=tuning_engine_facade,
        )
        # 延迟绑定：运行完成后自动触发评估+报告流水线
        batch_runner._on_complete = orchestrator.post_run_pipeline
        return orchestrator

    # ── Phase 7: 子控制器 ─────────────────────────────

    @singleton
    @provider
    def provide_draft_controller(self, draft_engine_facade: DraftEngineFacade, source_document_repository: SourceDocumentRepository) -> DraftController:
        return DraftController(draft_engine_facade, source_document_repository)

    @singleton
    @provider
    def provide_case_controller(self, case_engine_facade: CaseEngineFacade) -> CaseController:
        return CaseController(case_engine_facade)

    @singleton
    @provider
    def provide_run_controller(self, run_engine_facade: RunEngineFacade) -> RunController:
        return RunController(run_engine_facade)

    @singleton
    @provider
    def provide_metric_controller(self, metric_engine_facade: MetricEngineFacade, run_engine_facade: RunEngineFacade) -> MetricController:
        return MetricController(metric_engine_facade, run_engine_facade)

    @singleton
    @provider
    def provide_report_controller(self, report_engine_facade: ReportEngineFacade) -> ReportController:
        return ReportController(report_engine_facade)

    @singleton
    @provider
    def provide_tuning_controller(self, tuning_engine_facade: TuningEngineFacade, config_changer: ConfigChanger) -> TuningController:
        return TuningController(tuning_engine_facade, config_changer)

    @singleton
    @provider
    def provide_snapshot_controller(self, snapshot_manager: SnapshotManager) -> SnapshotController:
        return SnapshotController(snapshot_manager)

    # ── Phase 7: 控制器注册器 ─────────────────────────

    @singleton
    @provider
    def provide_controller_registry(
        self, draft_controller: DraftController, case_controller: CaseController, run_controller: RunController,
        metric_controller: MetricController, report_controller: ReportController, tuning_controller: TuningController,
        snapshot_controller: SnapshotController,
    ) -> RagEvalControllerRegistry:
        return RagEvalControllerRegistry(
            draft_ctrl=draft_controller,
            case_ctrl=case_controller,
            run_ctrl=run_controller,
            metric_ctrl=metric_controller,
            report_ctrl=report_controller,
            tuning_ctrl=tuning_controller,
            snapshot_ctrl=snapshot_controller,
        )


class TaskModule(Module):
    """任务状态管理模块"""

    @provider
    @singleton
    def provide_task_state_service(self) -> TaskStateService:
        from src.service.task_state_service import TaskStateService

        return TaskStateService(
            multi_instance=settings.multi_instance_deployment,
        )


# 全局注入器实例
injector = Injector([CoreModule(), RepositoryModule(), TaskModule(), RagEvalModule()])
