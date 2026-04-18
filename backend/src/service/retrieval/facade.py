from typing import List, Optional

from src.schemas import KnowledgeItem
from src.service.cache_service import CacheService
from src.service.index_manager_service import IndexManagerService
from src.service.retrieval.knowledge_retriever import KnowledgeRetriever
from src.service.retrieval.query_rewriter import QueryRewriter
from src.service.retrieval.result_processor import ResultProcessor
from src.service.retrieval.retriever_manager import RetrieverManager


class RetrievalFacade:
    """检索服务门面类，协调所有子服务，保持与原 RetrievalService 相同的 API"""

    def __init__(self, index_manager: IndexManagerService, cache_service: CacheService):
        self.index_manager = index_manager
        self.cache_service = cache_service

        # 初始化检索器管理
        self.retriever_manager = RetrieverManager(index_manager, cache_service)

        # 初始化查询重写器依赖
        from src.core.rag.local_synonym_expander import LocalSynonymExpander
        from src.core.rag.query_analyzer import QueryAnalyzer
        from src.core.rag.synonym_validator import SynonymValidator

        query_analyzer = QueryAnalyzer()
        synonym_validator = SynonymValidator()
        local_expander = LocalSynonymExpander()

        # 初始化查询重写器
        self.query_rewriter = QueryRewriter(
            dashscope_available=self.retriever_manager.dashscope_available,
            query_analyzer=query_analyzer,
            synonym_validator=synonym_validator,
            local_expander=local_expander,
        )

        # 初始化结果处理器
        self.result_processor = ResultProcessor()

        # 初始化知识检索器
        self.knowledge_retriever = KnowledgeRetriever(
            index_manager=index_manager,
            cache_service=cache_service,
            retriever_manager=self.retriever_manager,
            query_rewriter=self.query_rewriter,
            result_processor=self.result_processor,
        )

    # 向后兼容：暴露内部检索器属性
    @property
    def bm25_retriever(self):
        return self.retriever_manager.bm25_retriever

    @bm25_retriever.setter
    def bm25_retriever(self, value):
        self.retriever_manager.bm25_retriever = value

    @property
    def vector_retriever(self):
        return self.retriever_manager.vector_retriever

    @vector_retriever.setter
    def vector_retriever(self, value):
        self.retriever_manager.vector_retriever = value

    # 向后兼容：转发内部方法
    async def _rewrite_query(self, query: str, age: int) -> str:
        return await self.query_rewriter._rewrite_query(query, age)

    async def _expand_synonyms(self, query: str) -> str:
        return await self.query_rewriter._expand_synonyms(query)

    def _get_cache_key(self, query: str, age: int, limit: int) -> tuple:
        return self.knowledge_retriever._get_cache_key(query, age, limit)

    def _convert_to_knowledge_items(self, nodes, user_age: int = None):
        return self.knowledge_retriever._convert_to_knowledge_items(nodes, user_age)

    def _process_search_results(self, nodes, original_query: str, expanded_query: str, bm25_nodes: list = None):
        return self.result_processor._process_search_results(
            nodes, original_query, expanded_query, bm25_nodes,
            bm25_retriever=self.retriever_manager.bm25_retriever,
            vector_retriever=self.retriever_manager.vector_retriever,
        )

    def reload_retrievers(self) -> None:
        """重新加载检索器（索引更新后调用）"""
        self.retriever_manager.reload_retrievers()

    async def retrieve_knowledge(
        self, query: str, age: int, limit: int = 3, user_id: str = None
    ) -> List[KnowledgeItem]:
        """
        根据查询和年龄检索相关知识点
        :param user_id: 用户 ID，用于 A/B 测试分配
        """
        return await self.knowledge_retriever.retrieve_knowledge(
            query=query, age=age, limit=limit, user_id=user_id
        )

    async def search_content(
        self, query: str, limit: int = 20, offset: int = 0
    ) -> dict:
        """
        搜索知识库内容，返回匹配的片段和元数据（支持分页）

        Args:
            query: 搜索关键词
            limit: 每页数量
            offset: 偏移量

        Returns:
            dict: 包含 total（总数）和 results（当前页结果）
        """
        if not self.index_manager.is_index_available():
            from src.utils.logger import logger

            logger.warning("Index not available, returning empty results.")
            return {"total": 0, "results": []}

        bm25_nodes = []
        vector_nodes = []

        try:
            # 同义词扩展
            expanded_query = await self.query_rewriter._expand_synonyms(query)

            # 执行检索（获取更多结果以支持分页）
            fetch_limit = offset + limit
            if (
                self.retriever_manager.bm25_retriever
                and self.retriever_manager.vector_retriever
            ):
                # 并行检索
                bm25_nodes = await self.retriever_manager.bm25_retriever.aretrieve(
                    expanded_query
                )
                vector_nodes = await self.retriever_manager.vector_retriever.aretrieve(
                    expanded_query
                )

                # 使用搜索专用的合并逻辑
                from src.config import settings
                from src.core.hybrid_retrieval import HybridRetrievalMerger

                nodes = HybridRetrievalMerger.merge_for_search(
                    bm25_nodes,
                    vector_nodes,
                    bm25_weight=settings.rag_search_bm25_weight,
                    vector_weight=settings.rag_search_vector_weight,
                    no_match_vector_penalty=settings.rag_search_no_match_vector_penalty,
                    limit=fetch_limit,
                )
            else:
                # 回退到单一向量检索
                from src.config import settings

                corpus_size = self.index_manager.get_corpus_size()
                adjusted_limit = min(fetch_limit, max(1, corpus_size))
                retriever = self.index_manager.get_index().as_retriever(
                    similarity_top_k=adjusted_limit
                )
                nodes = await retriever.aretrieve(expanded_query)

            from src.utils.logger import logger

            logger.info(
                f"Raw retrieval results: {len(nodes)} nodes found before filtering"
            )
            if nodes:
                logger.info(f"Top raw score: {nodes[0].score or 0.0:.3f}")

            # 处理和过滤结果
            processed_results = self.result_processor._process_search_results(
                nodes,
                query,
                expanded_query,
                bm25_nodes,
                bm25_retriever=self.retriever_manager.bm25_retriever,
                vector_retriever=self.retriever_manager.vector_retriever,
            )

            total = len(processed_results)
            # 应用分页
            paginated_results = processed_results[offset : offset + limit]

            logger.info(
                f"Search completed: query='{query}', total={total}, returned={len(paginated_results)} results"
            )
            if paginated_results:
                logger.debug(
                    f"Top result score: {paginated_results[0]['score']:.3f}, source: {paginated_results[0]['source_book']}"
                )
            return {"total": total, "results": paginated_results}

        except Exception as e:
            from src.utils.logger import logger

            logger.error(f"Error during content search: {e}", exc_info=True)
            return {"total": 0, "results": []}


# 单例工厂
_retrieval_facade_instance: Optional[RetrievalFacade] = None


def get_retrieval_facade(
    index_manager: IndexManagerService, cache_service: CacheService
) -> RetrievalFacade:
    """获取检索服务门面单例"""
    global _retrieval_facade_instance
    if _retrieval_facade_instance is None:
        _retrieval_facade_instance = RetrievalFacade(index_manager, cache_service)
    return _retrieval_facade_instance
