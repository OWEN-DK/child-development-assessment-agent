from injector import Injector, Module, provider, singleton
from src.config import settings
from src.core.interfaces import (
    IIndexManager,
    ICacheService,
    IRetrievalService,
    IDocumentIngestionService
)

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
    def provide_retrieval_service(self, index_manager: IIndexManager, cache_service: ICacheService) -> IRetrievalService:
        from src.service.retrieval_service import RetrievalService
        return RetrievalService(index_manager, cache_service)
    
    @provider
    @singleton
    def provide_document_ingestion_service(self, index_manager: IIndexManager) -> IDocumentIngestionService:
        from src.service.document_ingestion_service import DocumentIngestionService
        return DocumentIngestionService(index_manager)

# 全局注入器实例
injector = Injector([CoreModule()])
