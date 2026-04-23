from injector import Injector, Module, provider, singleton

from src.config import settings
from src.core.database import async_session_factory
from src.core.interfaces import (ICacheService, IDocumentIngestionService,
                                 IIndexManager, IRetrievalService)
from src.repository import (ABTestMetricRepository, ConfigAuditLogRepository,
                            ConfigVersionRepository, DocumentRecordRepository,
                            LLMCallLogRepository, SourceDocumentRepository,
                            TestCaseDraftRepository, TestCaseRepository,
                            TestRunRepository, TestRunResultRepository,
                            TestSetCaseRepository, TestSetRepository)
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
    """

    @provider
    @singleton
    def provide_config_version_repository(self) -> ConfigVersionRepository:
        return ConfigVersionRepository(async_session_factory)

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
    def provide_test_case_repository(self) -> TestCaseRepository:
        return TestCaseRepository(async_session_factory)

    @provider
    @singleton
    def provide_test_case_draft_repository(self) -> TestCaseDraftRepository:
        return TestCaseDraftRepository(async_session_factory)

    @provider
    @singleton
    def provide_test_set_repository(self) -> TestSetRepository:
        return TestSetRepository(async_session_factory)

    @provider
    @singleton
    def provide_test_set_case_repository(self) -> TestSetCaseRepository:
        return TestSetCaseRepository(async_session_factory)

    @provider
    @singleton
    def provide_test_run_repository(self) -> TestRunRepository:
        return TestRunRepository(async_session_factory)

    @provider
    @singleton
    def provide_test_run_result_repository(self) -> TestRunResultRepository:
        return TestRunResultRepository(async_session_factory)

    @provider
    @singleton
    def provide_llm_call_log_repository(self) -> LLMCallLogRepository:
        return LLMCallLogRepository(async_session_factory)

    @provider
    @singleton
    def provide_ab_test_metric_repository(self) -> ABTestMetricRepository:
        return ABTestMetricRepository(async_session_factory)


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
injector = Injector([CoreModule(), RepositoryModule(), TaskModule()])
