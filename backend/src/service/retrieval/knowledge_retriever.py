import json
import time
from typing import List, Optional

from src.config import settings
from src.core.ab_test_framework import ab_test_framework
from src.core.child_development_engine import child_development_engine
from src.core.hybrid_retrieval import HybridRetrievalMerger
from src.schemas import KnowledgeItem
from src.service.cache_service import CacheService
from src.service.index_manager_service import IndexManagerService
from src.utils.logger import logger


class KnowledgeRetriever:
    """知识检索服务，负责执行检索、年龄过滤和结果转换"""

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

    def _build_age_filters(self, age: int):
        """构建年龄过滤器（使用新的 AgeFilter 类）"""
        if age <= 0:
            return None

        from src.core.age_filter import AgeFilter, AgeFilterMode

        # 从配置读取过滤模式
        mode_str = getattr(settings, "rag_age_filter_mode", "strict")
        mode = AgeFilterMode.STRICT if mode_str == "strict" else AgeFilterMode.LOOSE

        # 构建 MetadataFilter（用于向量检索阶段的基础过滤）
        return AgeFilter.build_metadata_filters(age, mode)

    def _calculate_age_fit_score(
        self, age: int, target_min: int, target_max: int
    ) -> float:
        """计算年龄适配度得分，范围0-1，1表示完全适配"""
        if target_min <= age <= target_max:
            return 1.0  # 完全适配

        # 超出范围的情况，根据距离计算适配度
        strictness = settings.rag_age_filter_strictness
        if age < target_min:
            diff = target_min - age
            base_score = max(0.5, 1 - diff * 0.1 * strictness)
        else:  # age > target_max
            diff = age - target_max
            base_score = max(0.5, 1 - diff * 0.1 * strictness)

        return base_score

    async def _execute_retrieval(
        self,
        query: str,
        filters,
        limit: int,
        use_hybrid: bool,
        age: int = None,
        retrieval_variant: str = "control",
        user_id: str = None,
    ):
        """执行检索逻辑"""
        start_time = time.time()

        if use_hybrid:
            # 设置过滤器
            self.retriever_manager.bm25_retriever.filters = filters
            self.retriever_manager.vector_retriever.filters = filters

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
                    age,
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
                similarity_top_k=adjusted_limit, filters=filters
            )
            nodes = await retriever.aretrieve(query)

        return nodes

    def _convert_to_knowledge_items(
        self, nodes, user_age: int = None
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

            # 使用儿童发展引擎过滤不适宜内容
            if user_age is not None:
                is_suitable, reason = (
                    child_development_engine.filter_unsuitable_content(
                        content, user_age
                    )
                )
                if not is_suitable:
                    logger.info(
                        f"Filtered unsuitable content for age {user_age}: {reason}"
                    )
                    continue

            # 最低相似度阈值过滤
            base_score = node_with_score.score or 0.0
            if base_score < settings.rag_search_min_similarity_threshold:
                continue

            metadata = node.metadata or {}
            source = metadata.get("file_name", "Unknown Source")

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
            target_age_min = metadata.get("target_age_min", 0)
            target_age_max = metadata.get("target_age_max", 18)
            activity_type = metadata.get("activity_type", "Theory")
            chapter_title = metadata.get("chapter_title")
            page_label = metadata.get("page_label")

            # relevance_score 直接使用 base_score（来自 Cross-Encoder 重排序后的分数）
            relevance_score = base_score

            # age_fit_score 独立计算（不混合到 relevance_score）
            age_fit_score = 1.0  # 默认值（无年龄时）
            if user_age is not None:
                # 使用儿童发展引擎计算年龄适配度
                age_fit_score = child_development_engine.calculate_age_appropriateness(
                    content, user_age
                )
                # 同时考虑元数据中的年龄范围
                metadata_age_fit = self._calculate_age_fit_score(
                    user_age, target_age_min, target_age_max
                )
                # 综合两种评分
                age_fit_score = 0.7 * age_fit_score + 0.3 * metadata_age_fit

            # 检查重复内容
            is_duplicate = False
            for existing_item in results:
                if self.result_processor._is_content_duplicate(content, existing_item.content):
                    is_duplicate = True
                    break

            if is_duplicate:
                continue

            item = KnowledgeItem(
                content=content.strip(),
                source_book=source,
                chapter_title=chapter_title,
                page_label=page_label,
                topics=topics,
                brain_regions=brain_regions,
                benefits=benefits,
                risk_level="Low",
                target_age_min=target_age_min,
                target_age_max=target_age_max,
                activity_type=activity_type,
                relevance_score=float(relevance_score),  # 仅检索相关性
                age_fit_score=float(age_fit_score),  # 独立年龄适配度
            )
            results.append(item)

        # 按 relevance_score 排序（仅基于检索相关性）
        results.sort(key=lambda x: x.relevance_score, reverse=True)

        return results

    async def retrieve_knowledge(
        self, query: str, age: int, limit: int = 3, user_id: str = None
    ) -> List[KnowledgeItem]:
        """
        根据查询和年龄检索相关知识点
        :param user_id: 用户 ID，用于 A/B 测试分配
        """
        logger.info(
            f"Retrieving knowledge for query: '{query}', age: {age}, user_id: {user_id}"
        )
        start_time = time.time()

        # 检查缓存
        cache_key = self._get_cache_key(query, age, limit)
        cached_result = await self.cache_service.get(cache_key)
        if cached_result:
            return cached_result

        # A/B 测试：根据变体选择不同的检索策略
        retrieval_variant = "control"
        if user_id:
            retrieval_variant = ab_test_framework.get_variant(
                user_id, "retrieval_strategy"
            )
            logger.info(f"A/B test variant for retrieval: {retrieval_variant}")

        # 查询重写和同义词扩展
        rewritten_query = await self.query_rewriter._rewrite_query(query, age)
        expanded_query = await self.query_rewriter._expand_synonyms(rewritten_query)

        index = self.index_manager.get_index()
        if not index:
            logger.warning("Index not available, returning empty results.")
            return []

        try:
            # 构建年龄过滤器
            filters = self._build_age_filters(age)
            results = await self._execute_retrieval(
                query=expanded_query,
                filters=filters,
                limit=limit,
                use_hybrid=self.retriever_manager.bm25_retriever is not None
                and self.retriever_manager.vector_retriever is not None,
                age=age,
                retrieval_variant=retrieval_variant,
                user_id=user_id,
            )

            # 精确年龄过滤（二次过滤）
            if age > 0 and results:
                from src.core.age_filter import AgeFilter, AgeFilterMode

                mode_str = getattr(settings, "rag_age_filter_mode", "strict")
                mode = (
                    AgeFilterMode.STRICT
                    if mode_str == "strict"
                    else AgeFilterMode.LOOSE
                )

                filtered_nodes = []
                for node_with_score in results:
                    metadata = node_with_score.node.metadata or {}
                    target_min = metadata.get("target_age_min", 0)
                    target_max = metadata.get("target_age_max", 18)

                    if not AgeFilter.should_filter(target_min, target_max, age, mode):
                        filtered_nodes.append(node_with_score)
                    else:
                        logger.info(
                            f"精确年龄过滤：用户 {age} 岁，内容年龄 [{target_min}, {target_max}]，"
                            f"模式 {mode}，分数 {node_with_score.score:.4f}"
                        )

                logger.info(f"年龄过滤：{len(results)} -> {len(filtered_nodes)} 个结果")
                results = filtered_nodes

            # 转换为 KnowledgeItem，传入用户年龄计算适配度并排序
            knowledge_items = self._convert_to_knowledge_items(results, user_age=age)

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
                tags={"age": str(age), "limit": str(limit)},
            )
            monitoring_service.record_metric(
                "retrieval_result_count", len(knowledge_items), tags={"age": str(age)}
            )

            return knowledge_items

        except Exception as e:
            logger.error(f"Error during retrieval: {e}", exc_info=True)
            return []

    def _get_cache_key(self, query: str, age: int, limit: int) -> tuple:
        """生成包含索引版本和配置指纹的缓存键"""
        return (
            query.strip().lower(),
            age,
            limit,
            self.index_manager.index_version,
            self.index_manager.config_fingerprint,
        )
