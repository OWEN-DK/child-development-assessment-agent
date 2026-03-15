from typing import List, Any
from src.config.settings import settings
from src.service.index_manager_service import IndexManagerService
from src.service.cache_service import CacheService
from src.service.retrieval_service import RetrievalService
from src.service.document_ingestion_service import DocumentIngestionService
from src.utils.logger import logger

# 兼容原有导出
STORAGE_DIR = settings.rag_storage_dir

# 单例实例
index_manager = IndexManagerService()
cache_service = CacheService()
retrieval_service = RetrievalService(index_manager, cache_service)
document_ingestion_service = DocumentIngestionService(index_manager, retrieval_service)


class RagService:
    """
    RAG服务门面类，保持原有接口不变，内部委托给各个子服务
    用于向后兼容，新代码建议直接使用各个子服务
    """

    def __init__(self):
        self.index_manager = index_manager
        self.cache_service = cache_service
        self.retrieval_service = retrieval_service
        self.document_ingestion_service = document_ingestion_service
        logger.info("RagService initialized with split architecture")

    @property
    def index(self):
        """兼容原有代码对index的直接访问"""
        return self.index_manager.get_index()

    async def retrieve_knowledge(self, query: str, age: int, limit: int = 3):
        """检索知识点（原有接口）"""
        return await self.retrieval_service.retrieve_knowledge(query, age, limit)

    async def ingest_book(
        self, file_path: str, original_filename: str = None, progress_callback=None
    ):
        """导入书籍（原有接口）"""
        return await self.document_ingestion_service.ingest_book(
            file_path, original_filename, progress_callback
        )

    def delete_document(self, file_name: str) -> bool:
        """删除文档（原有接口）"""
        success = self.index_manager.delete_document(file_name)
        if success:
            self.retrieval_service.reload_retrievers()
        return success

    async def search_content(self, query: str, limit: int = 20) -> List[dict]:
        """搜索内容（原有接口）"""
        return await self.retrieval_service.search_content(query, limit)

    def _initialize_index(self):
        """兼容原有初始化方法"""
        logger.warning(
            "_initialize_index is deprecated, index is managed by IndexManagerService"
        )

    def _initialize_retrievers(self):
        """兼容原有检索器初始化方法"""
        logger.warning(
            "_initialize_retrievers is deprecated, retrievers are managed by RetrievalService"
        )
        self.retrieval_service.reload_retrievers()

    def _clear_cache(self):
        """兼容原有缓存清除方法"""
        logger.warning("_clear_cache is deprecated, cache is managed by CacheService")
        self.cache_service.clear()

    async def _rewrite_query(self, query: str, age: int) -> str:
        """兼容原有查询重写方法"""
        logger.warning(
            "_rewrite_query is deprecated, use retrieval_service._rewrite_query instead"
        )
        return await self.retrieval_service._rewrite_query(query, age)

    async def _expand_synonyms(self, query: str) -> str:
        """兼容原有同义词扩展方法"""
        logger.warning(
            "_expand_synonyms is deprecated, use retrieval_service._expand_synonyms instead"
        )
        return await self.retrieval_service._expand_synonyms(query)

    def _get_cache_key(self, query: str, age: int, limit: int) -> tuple[str, int, int]:
        """兼容原有缓存键生成方法"""
        logger.warning(
            "_get_cache_key is deprecated, use retrieval_service._get_cache_key instead"
        )
        return self.retrieval_service._get_cache_key(query, age, limit)

    def _get_from_cache(self, key: tuple[str, int, int]) -> Any:
        """兼容原有缓存获取方法"""
        logger.warning("_get_from_cache is deprecated, use cache_service.get instead")
        return self.cache_service.get(key)

    def _save_to_cache(self, key: tuple[str, int, int], value: Any):
        """兼容原有缓存保存方法"""
        logger.warning("_save_to_cache is deprecated, use cache_service.set instead")
        self.cache_service.set(key, value)


# 保持原有单例接口不变
rag_service = RagService()
