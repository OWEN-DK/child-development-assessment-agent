import json
import time
from typing import List, Optional

from src.config import settings
from src.core.ab_test_framework import ab_test_framework
from src.core.hybrid_retrieval import HybridRetrievalMerger
from src.schemas import KnowledgeItem
from src.service.cache_service import CacheService
from src.service.index_manager_service import IndexManagerService
from src.utils.logger import logger


class KnowledgeRetriever:
    """知识检索服务，负责执行检索和结果转换"""

    def __init__(
        self,
        index_manager: IndexManagerService,
        cache_service: CacheService,
        retriever_manager,
        query_rewriter,
        result_processor,
    ):
        self.index_manager = index_manager
        self.cache_service = cache_service
        self.retriever_manager = retriever_manager
        self.query_rewriter = query_rewriter
        self.result_processor = result_processor

        # 初始化 QueryAnalyzer
        from src.core.rag.query_analyzer import QueryAnalyzer

        self._query_analyzer = QueryAnalyzer()

    async def _execute_retrieval(
        self,
        query: str,
        limit: int,
        use_hybrid: bool,
        retrieval_variant: str = "control",
        user_id: str = None,
    ):
        """执行检索逻辑"""
        start_time = time.time()

        if use_hybrid:
            # 根据 A/B 测试变体选择权重
            if retrieval_variant == "variant1":
                bm25_weight, vector_weight = 0.6, 0.4
                logger.info(
                    f"Using A/B test variant1 weights: BM25={bm25_weight}, Vector={vector_weight}"
                )
            elif retrieval_variant == "variant2":
                bm25_weight, vector_weight = 0.4, 0.6
                logger.info(
                    f"Using A/B test variant2 weights: BM25={bm25_weight}, Vector={vector_weight}"
                )
            else:
                # control 或默认：使用动态权重
                bm25_weight, vector_weight = HybridRetrievalMerger.get_dynamic_weights(
                    query,
                    query_analyzer=self._query_analyzer,
                    strategy=settings.rag_weight_strategy,
                )

            # 并行检索
            bm25_nodes = await self.retriever_manager.bm25_retriever.aretrieve(query)
            vector_nodes = await self.retriever_manager.vector_retriever.aretrieve(query)

            # 合并结果（先不限制数量，留给重排序器处理）
            nodes = HybridRetrievalMerger.merge_results(
                bm25_nodes,
                vector_nodes,
                bm25_weight=bm25_weight,
                vector_weight=vector_weight,
                merge_mode=self.retriever_manager.merge_mode,
                limit=self.retriever_manager.reranker.initial_k if self.retriever_manager.reranker.model else limit,
            )

            # 应用 Cross-Encoder 重排序
            if self.retriever_manager.reranker.model and nodes:
                nodes = self.retriever_manager.reranker.rerank(query, nodes)
        else:
            # 回退到单一向量检索
            corpus_size = self.index_manager.get_corpus_size()
            adjusted_limit = min(limit, max(1, corpus_size))
            retriever = self.index_manager.get_index().as_retriever(
                similarity_top_k=adjusted_limit
            )
            nodes = await retriever.aretrieve(query)

        return nodes

    def _convert_to_knowledge_items(
        self, nodes
    ) -> List[KnowledgeItem]:
        """将检索节点转换为KnowledgeItem"""
        results = []
        for node_with_score in nodes:
            node = node_with_score.node
            content = node.metadata.get("content", node.get_content())

            # 过滤无效内容
            if (
                not content
                or content.startswith("[General Information]")
                or "书名=" in content
                or "SS 号=" in content
            ):
                continue

            # 最低相似度阈值过滤
            base_score = node_with_score.score or 0.0
            if base_score < settings.rag_search_min_similarity_threshold:
                continue

            metadata = node.metadata or {}
            source = metadata.get("file_name", "Unknown Source")
            node_id = metadata.get("node_id") or getattr(node, 'node_id', None)

            # 提取元数据字段
            brain_regions = metadata.get("brain_regions", "[]")
            if isinstance(brain_regions, str):
                try:
                    brain_regions = json.loads(brain_regions)
                except:
                    brain_regions = []
            topics = metadata.get("topics", "[]")
            if isinstance(topics, str):
                try:
                    topics = json.loads(topics)
                except:
                    topics = []
            benefits = metadata.get("benefits", [])
            activity_type = metadata.get("activity_type", "Theory")
            chapter_title = metadata.get("chapter_title")
            page_label = metadata.get("page_label")

            relevance_score = base_score

            # 检查重复内容
            is_duplicate = False
            for existing_item in results:
                if self.result_processor._is_content_duplicate(content, existing_item.content):
                    is_duplicate = True
                    break

            if is_duplicate:
                continue

            item = KnowledgeItem(
                id=node_id,
                content=content.strip(),
                source_book=source,
                chapter_title=chapter_title,
                page_label=page_label,
                topics=topics,
                brain_regions=brain_regions,
                benefits=benefits,
                risk_level="Low",
                activity_type=activity_type,
                relevance_score=float(relevance_score),  # 检索相关性
            )
            results.append(item)

        # 按 relevance_score 排序（仅基于检索相关性）
        results.sort(key=lambda x: x.relevance_score, reverse=True)

        return results

    @staticmethod
    def _ensure_knowledge_items(items: list) -> List[KnowledgeItem]:
        """将缓存返回的 dict 列表转换为 KnowledgeItem 列表（防御性处理）"""
        if not items:
            return []
        result = []
        for item in items:
            if isinstance(item, KnowledgeItem):
                result.append(item)
            elif isinstance(item, dict):
                try:
                    result.append(KnowledgeItem(**item))
                except Exception:
                    logger.warning(f"无法将 dict 转换为 KnowledgeItem: {str(item)[:100]}")
            else:
                logger.warning(f"缓存中存在非预期类型: {type(item).__name__}")
        return result

    async def retrieve_knowledge(
        self, query: str, limit: int = 3, user_id: str = None
    ) -> List[KnowledgeItem]:
        """
        根据查询检索相关知识点
        :param user_id: 用户 ID，用于 A/B 测试分配
        """
        logger.info(
            f"Retrieving knowledge for query: '{query}', user_id: {user_id}"
        )
        start_time = time.time()

        # 检查缓存
        cache_key = self._get_cache_key(query, limit)
        cached_result = await self.cache_service.get(cache_key)
        if cached_result:
            return self._ensure_knowledge_items(cached_result)

        # A/B 测试：根据变体选择不同的检索策略
        retrieval_variant = "control"
        if user_id:
            retrieval_variant = ab_test_framework.get_variant(
                user_id, "retrieval_strategy"
            )
            logger.info(f"A/B test variant for retrieval: {retrieval_variant}")

        # 查询重写和同义词扩展
        rewritten_query = await self.query_rewriter._rewrite_query(query)
        expanded_query = await self.query_rewriter._expand_synonyms(rewritten_query)

        index = self.index_manager.get_index()
        if not index:
            logger.warning("Index not available, returning empty results.")
            return []

        try:
            results = await self._execute_retrieval(
                query=expanded_query,
                limit=limit,
                use_hybrid=self.retriever_manager.bm25_retriever is not None
                and self.retriever_manager.vector_retriever is not None,
                retrieval_variant=retrieval_variant,
                user_id=user_id,
            )

            # 转换为 KnowledgeItem
            knowledge_items = self._convert_to_knowledge_items(results)

            # 保存到缓存
            await self.cache_service.set(cache_key, knowledge_items)

            # A/B 测试：记录指标
            if user_id:
                latency = time.time() - start_time
                ab_test_framework.track_metric(
                    "retrieval_strategy", retrieval_variant, "latency", latency
                )
                ab_test_framework.track_metric(
                    "retrieval_strategy",
                    retrieval_variant,
                    "result_count",
                    len(knowledge_items),
                )
                logger.info(
                    f"A/B test metrics recorded: variant={retrieval_variant}, "
                    f"latency={latency:.3f}s, results={len(knowledge_items)}"
                )

            # 监控埋点：检索响应时间和召回数量
            from src.core.monitoring import monitoring_service

            elapsed_ms = (time.time() - start_time) * 1000
            monitoring_service.record_metric(
                "retrieval_response_time_ms",
                elapsed_ms,
                tags={"limit": str(limit)},
            )
            monitoring_service.record_metric(
                "retrieval_result_count", len(knowledge_items), tags={}
            )

            return knowledge_items

        except Exception as e:
            logger.error(f"Error during retrieval: {e}", exc_info=True)
            return []

    def _get_cache_key(self, query: str, limit: int) -> tuple:
        """生成包含索引版本和配置指纹的缓存键"""
        return (
            query.strip().lower(),
            limit,
            self.index_manager.index_version,
            self.index_manager.config_fingerprint,
        )
