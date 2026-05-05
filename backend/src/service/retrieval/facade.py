import asyncio
import hashlib
from typing import List, Optional

from src.config import settings
from src.core.query_decomposer import QueryDecomposer
from src.core.query_router import QueryRouter
from src.schemas import KnowledgeItem
from src.service.cache_service import CacheService
from src.service.index_manager_service import IndexManagerService
from src.service.retrieval.knowledge_retriever import KnowledgeRetriever
from src.service.retrieval.query_rewriter import QueryRewriter
from src.service.retrieval.result_processor import ResultProcessor
from src.service.retrieval.retriever_manager import RetrieverManager
from src.utils.logger import logger


class RetrievalFacade:
    """检索服务门面类，协调所有子服务，保持与原 RetrievalService 相同的 API"""

    _pipeline_ever_logged = False

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

        # 初始化 PipelineOrchestrator（声明式流水线）
        self._pipeline_orchestrator = None
        self._init_pipeline_orchestrator()

        # 查询路由与分解器
        self.query_router = QueryRouter()
        self.query_decomposer = QueryDecomposer(
            llm_enabled=settings.query_router_llm_enabled,
        )

    def _init_pipeline_orchestrator(self):
        """初始化 PipelineOrchestrator（失败时不阻塞启动）"""
        try:
            from src.core.pipeline.orchestrator import PipelineOrchestrator

            config_path = str(
                __import__("pathlib").Path(__file__).parent.parent.parent.parent
                / "config"
                / "rag_pipeline.yaml"
            )
            self._pipeline_orchestrator = PipelineOrchestrator(config_path=config_path)
            if not RetrievalFacade._pipeline_ever_logged:
                RetrievalFacade._pipeline_ever_logged = True
                logger.info("PipelineOrchestrator 初始化成功")
        except Exception as e:
            logger.warning(f"PipelineOrchestrator 初始化失败，将使用硬编码链路: {e}")
            self._pipeline_orchestrator = None

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
    async def _rewrite_query(self, query: str) -> str:
        return await self.query_rewriter._rewrite_query(query)

    async def _expand_synonyms(self, query: str) -> str:
        return await self.query_rewriter._expand_synonyms(query)

    def _get_cache_key(self, query: str, limit: int) -> tuple:
        return self.knowledge_retriever._get_cache_key(query, limit)

    def _convert_to_knowledge_items(self, nodes):
        return self.knowledge_retriever._convert_to_knowledge_items(nodes)

    async def _process_search_results(self, nodes, original_query: str, expanded_query: str, bm25_nodes: list = None):
        return await self.result_processor._process_search_results(
            nodes, original_query, expanded_query, bm25_nodes,
            bm25_retriever=self.retriever_manager.bm25_retriever,
            vector_retriever=self.retriever_manager.vector_retriever,
        )

    def reload_retrievers(self) -> None:
        """重新加载检索器（索引更新后调用）"""
        self.retriever_manager.reload_retrievers()

    async def bm25_search(self, query: str, top_k: int = 10) -> list:
        """BM25 检索（top_k 已在初始化时固定，此处仅做兼容调用）"""
        if self.retriever_manager.bm25_retriever:
            return await self.retriever_manager.bm25_retriever.aretrieve(query)
        return []

    async def vector_search(self, query: str, top_k: int = 10) -> list:
        """向量检索"""
        if self.retriever_manager.vector_retriever:
            return await self.retriever_manager.vector_retriever.aretrieve(query)
        return []

    async def retrieve_knowledge(
        self, query: str, limit: int = 3, user_id: str = None
    ) -> List[KnowledgeItem]:
        """检索知识。复杂查询自动拆解为子查询分别检索后归并。"""
        classification = await self.query_router.classify_async(query)

        if classification.query_type.value != "complex":
            return await self._single_retrieve(query, limit, user_id)

        # 复杂查询：拆解子查询
        sub_queries = await self.query_decomposer.decompose(query)

        if len(sub_queries) <= 1:
            return await self._single_retrieve(query, limit, user_id)

        # 各子查询并行检索
        all_results = []
        tasks = [
            self._single_retrieve(sq.text, limit, user_id) for sq in sub_queries
        ]
        per_query_results = await asyncio.gather(*tasks, return_exceptions=True)

        for sq, result in zip(sub_queries, per_query_results):
            if isinstance(result, Exception):
                logger.warning(f"子查询 '{sq.text}' 检索失败: {result}")
                continue
            for item in result:
                item.metadata["sub_query"] = sq.text
                item.metadata["sub_focus"] = sq.focus
            all_results.extend(result)

        return self._merge_and_rerank(query, all_results, limit)

    async def _single_retrieve(
        self, query: str, limit: int, user_id: str = None
    ) -> List[KnowledgeItem]:
        """单次检索：走现有 RRF pipeline 或 knowledge_retriever"""
        use_pipeline = (
            settings.rag_query_pipeline_enabled
            and self._pipeline_orchestrator is not None
        )
        if use_pipeline:
            return await self._retrieve_via_pipeline(query, limit)
        else:
            return await self.knowledge_retriever.retrieve_knowledge(
                query=query, limit=limit, user_id=user_id
            )

    def _merge_and_rerank(
        self,
        original_query: str,
        results: List[KnowledgeItem],
        limit: int,
    ) -> List[KnowledgeItem]:
        """子查询结果归并：内容去重 → reranker 精排 → 截断"""
        from llama_index.core.schema import NodeWithScore, TextNode

        # 去重：基于内容 hash
        seen = set()
        deduped = []
        for item in results:
            h = hashlib.sha256(item.content.encode()).hexdigest()
            if h not in seen:
                seen.add(h)
                deduped.append(item)

        if not deduped:
            return []

        # 如果有 reranker，对去重结果精排
        try:
            from src.core.reranker import create_reranker

            reranker = create_reranker()
            nodes = [
                NodeWithScore(
                    node=TextNode(
                        text=item.content, metadata={"knowledge_item": item}
                    ),
                    score=item.relevance_score,
                )
                for item in deduped
            ]
            ranked = reranker.rerank(query=original_query, nodes=nodes)
            deduped = [
                n.node.metadata["knowledge_item"]
                for n in ranked
                if "knowledge_item" in n.node.metadata
            ]
        except Exception as e:
            logger.warning(f"合并后重排失败: {e}")

        return deduped[:limit]

    async def _retrieve_via_pipeline(
        self, query: str, limit: int
    ) -> List[KnowledgeItem]:
        """通过声明式流水线执行检索（带缓存）"""
        cache_key = ("pipeline", query.strip().lower(), limit)

        # 缓存检查
        try:
            cached = await self.cache_service.get(cache_key)
            if cached:
                logger.debug(f"Pipeline 检索命中缓存: {query[:30]}")
                return self.knowledge_retriever._ensure_knowledge_items(cached)
        except Exception:
            pass  # 缓存查询失败不阻塞检索

        try:
            raw_results = await self._pipeline_orchestrator.execute(
                query=query,
                limit=limit,
            )
            results = self.knowledge_retriever._convert_to_knowledge_items(
                raw_results
            )
        except Exception as e:
            logger.error(f"Pipeline 检索失败，抛出异常: {e}")
            raise

        # 缓存写入
        try:
            await self.cache_service.set(cache_key, results)
        except Exception:
            pass  # 缓存写入失败不阻塞返回

        return results

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
            processed_results = await self.result_processor._process_search_results(
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
