import time
from typing import Any, List, Optional

from src.config import settings
from src.core.di_container import injector
from src.core.interfaces import (ICacheService, IDocumentIngestionService,
                                 IIndexManager, IRetrievalService)
from src.service.monitoring_service import monitoring_service
from src.utils.logger import logger


class RagService:
    """
    RAG服务门面类，内部委托给各个子服务
    """

    def __init__(self, injector_instance=None):
        self.injector = injector_instance or injector
        self.index_manager = self.injector.get(IIndexManager)
        self.cache_service = self.injector.get(ICacheService)
        self.retrieval_service = self.injector.get(IRetrievalService)
        self.document_ingestion_service = self.injector.get(IDocumentIngestionService)

        # Initialize PageIndex hybrid architecture components
        from src.core.pageindex_wrapper import PageIndexWrapper
        from src.core.query_router import QueryRouter, QueryType
        from src.core.result_fusion import ResultFusion

        self.query_router = QueryRouter()
        self.pageindex_wrapper = PageIndexWrapper()
        self.result_fusion = ResultFusion()
        self.QueryType = QueryType

        logger.info(
            "RagService initialized with dependency injection and PageIndex components"
        )

    @property
    def index(self):
        """获取索引"""
        return self.index_manager.get_index()

    async def retrieve_knowledge(
        self, query: str, age: int, limit: int = 3, user_id: str = None
    ):
        """检索知识点（增强：支持 PageIndex 混合架构）"""
        start_time = time.time()

        # 1. 意图分类
        classification = await self.query_router.classify_async(query)
        logger.info(
            f"Query classified as {classification.query_type.value}, confidence: {classification.confidence:.2f}"
        )

        # 2. 并行获取检索结果
        import asyncio

        hybrid_task = self.retrieval_service.retrieve_knowledge(
            query, age, limit, user_id
        )

        if (
            classification.query_type == self.QueryType.COMPLEX
            and settings.pageindex_enabled
        ):
            # 复杂查询：并行执行混合检索和 PageIndex
            pageindex_task = self.pageindex_wrapper.query(query)
            hybrid_results, pageindex_results = await asyncio.gather(
                hybrid_task, pageindex_task
            )

            # 融合结果
            fused_results = self.result_fusion.fuse(
                hybrid_results=hybrid_results,
                pageindex_results=pageindex_results,
                query_type="complex",
                limit=limit,
            )

            elapsed_ms = (time.time() - start_time) * 1000
            monitoring_service.record_metric(
                "rag_response_time_ms",
                elapsed_ms,
                tags={"query_type": "complex", "endpoint": "retrieve_knowledge"},
            )
            monitoring_service.record_metric(
                "rag_retrieval_count",
                len(fused_results),
                tags={"query_type": "complex"},
            )

            return fused_results
        else:
            # 简单查询：仅使用现有的混合检索
            results = await hybrid_task

            elapsed_ms = (time.time() - start_time) * 1000
            monitoring_service.record_metric(
                "rag_response_time_ms",
                elapsed_ms,
                tags={"query_type": "simple", "endpoint": "retrieve_knowledge"},
            )
            monitoring_service.record_metric(
                "rag_retrieval_count", len(results), tags={"query_type": "simple"}
            )

            return results

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

    async def search_content(
        self, query: str, limit: int = 20, offset: int = 0
    ) -> dict:
        """搜索内容（支持分页）"""
        return await self.retrieval_service.search_content(query, limit, offset)

    def get_document_chunks(
        self, file_hash: str, page: int = 1, page_size: int = 20
    ) -> dict:
        """获取指定文档的分块列表（支持分页）"""
        return self.index_manager.get_document_chunks(file_hash, page, page_size)

    def get_chunk_detail(self, chunk_id: str) -> Optional[dict]:
        """获取指定分块的详细信息"""
        return self.index_manager.get_chunk_detail(chunk_id)


# 全局RAG服务实例
rag_service = RagService()


# 对外暴露接口
__all__ = ["RagService", "rag_service"]
