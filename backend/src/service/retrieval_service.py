import jieba
import re
import difflib
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from llama_index.core.retrievers import BaseRetriever
from llama_index.retrievers.bm25 import BM25Retriever
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate
from src.config import settings
from src.utils.logger import logger
from src.core.hybrid_retrieval import HybridRetrievalMerger
from src.core.reranker import CrossEncoderReranker
from src.model.schemas import KnowledgeItem
from src.core.prompts import QUERY_REWRITE_PROMPT, SYNONYM_EXPANSION_PROMPT
from src.service.index_manager_service import IndexManagerService
from src.service.cache_service import CacheService
from src.core.child_development_engine import child_development_engine
from src.service.content_audit_service import content_audit_service
from src.core.ab_test_framework import ab_test_framework
from src.core.prompt_injection_guard import prompt_injection_guard
from src.service.monitoring_service import monitoring_service
from src.core.llm.factory import LLMServiceFactory, LLMFramework
from src.core.llm.base import LLMRequest, LLMMessage


# Define Pydantic model for structured synonym output
class SynonymExpansionResult(BaseModel):
    synonyms: List[str] = Field(
        description="List of synonyms/related terms for the query"
    )


class RetrievalService:
    """检索服务，处理所有检索相关逻辑"""

    def __init__(self, index_manager: IndexManagerService, cache_service: CacheService):
        self.index_manager = index_manager
        self.cache_service = cache_service
        self.bm25_retriever: Optional[BaseRetriever] = None
        self.vector_retriever: Optional[BaseRetriever] = None
        self.bm25_weight = 0.5
        self.vector_weight = 0.5
        self.merge_mode = "OR"

        # 初始化 Cross-Encoder 重排序器
        self.reranker = CrossEncoderReranker(
            model_name=settings.rag_reranker_model,
            initial_k=settings.rag_reranker_initial_k,
            final_k=settings.rag_reranker_final_k,
        )

        # 加载 jieba 自定义词典
        import os
        from src.config import BASE_DIR

        custom_dict_path = os.path.join(
            BASE_DIR, "src", "data", "jieba_custom_dict.txt"
        )
        if os.path.exists(custom_dict_path):
            jieba.load_userdict(custom_dict_path)
            logger.info(f"Loaded jieba custom dictionary from {custom_dict_path}")

        self.dashscope_available = bool(settings.dashscope_api_key)
        self._initialize_retrievers()

    def _initialize_retrievers(self):
        """初始化BM25和向量检索器"""
        index = self.index_manager.get_index()
        if not index:
            return

        rag_config = settings.rag_config["hybrid_retrieval"]
        corpus_size = self.index_manager.get_corpus_size()

        if corpus_size == 0:
            logger.warning("Index is empty. Skipping retriever initialization.")
            self.bm25_retriever = None
            self.vector_retriever = None
            return

        # 动态调整top_k
        bm25_top_k = min(rag_config["bm25_top_k"], max(1, corpus_size))
        vector_top_k = min(rag_config["vector_top_k"], max(1, corpus_size))

        # 初始化向量检索器（优先初始化，作为回退）
        try:
            self.vector_retriever = index.as_retriever(similarity_top_k=vector_top_k)
            logger.info(f"Vector retriever initialized: top_k={vector_top_k}")
        except Exception as e:
            logger.error(f"Failed to initialize vector retriever: {e}")
            self.vector_retriever = None
            return

        # 检查 docstore 是否有内容（BM25 需要 docstore，而不仅仅是向量存储）
        has_docstore_docs = False
        if hasattr(index, "docstore") and index.docstore:
            has_docstore_docs = len(index.docstore.docs) > 0
            logger.info(f"Docstore contains {len(index.docstore.docs)} documents")

        if not has_docstore_docs:
            logger.warning(
                "Docstore is empty. BM25 retriever cannot be initialized. Using vector-only retrieval."
            )
            self.bm25_retriever = None
            return

        # 初始化BM25检索器（使用jieba分词）
        try:
            self.bm25_retriever = BM25Retriever.from_defaults(
                index=index, similarity_top_k=bm25_top_k, tokenizer=jieba.lcut
            )
            logger.info(f"BM25 retriever initialized: top_k={bm25_top_k}")
        except Exception as e:
            logger.error(
                f"Failed to initialize BM25 retriever: {e}. Falling back to vector-only retrieval."
            )
            self.bm25_retriever = None
            return

        # 设置混合检索权重
        self.bm25_weight = rag_config["bm25_weight"]
        self.vector_weight = rag_config["vector_weight"]
        self.merge_mode = rag_config["merge_mode"]
        logger.info(
            f"Hybrid retrieval enabled: BM25 weight={self.bm25_weight}, Vector weight={self.vector_weight}"
        )

    def reload_retrievers(self):
        """重新加载检索器（索引更新后调用）"""
        self._initialize_retrievers()
        self.cache_service.clear()
        logger.info("Retrievers reloaded")

    async def retrieve_knowledge(
        self, query: str, age: int, limit: int = 3, user_id: str = None
    ) -> List[KnowledgeItem]:
        """
        根据查询和年龄检索相关知识点
        :param user_id: 用户 ID，用于 A/B 测试分配
        """
        import time

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
        rewritten_query = await self._rewrite_query(query, age)
        expanded_query = await self._expand_synonyms(rewritten_query)

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
                use_hybrid=self.bm25_retriever is not None
                and self.vector_retriever is not None,
                age=age,
                retrieval_variant=retrieval_variant,
                user_id=user_id,
            )

            # # 内容审核：在检索后审核每个结果（暂时禁用）
            # audited_results = []
            # for node_with_score in results:
            #     content = node_with_score.node.get_content()
            #     audit_passed, audit_reason = await content_audit_service.audit_content(
            #         content, stage="retrieval"
            #     )
            #     if audit_passed:
            #         audited_results.append(node_with_score)
            #     else:
            #         logger.info(f"Filtered content during retrieval: {audit_reason}")

            # logger.info(f"Content audit filtered {len(results) - len(audited_results)} items")

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
            logger.warning("Index not available, returning empty results.")
            return {"total": 0, "results": []}

        bm25_nodes = []
        vector_nodes = []

        try:
            # 同义词扩展
            expanded_query = await self._expand_synonyms(query)

            # 执行检索（获取更多结果以支持分页）
            fetch_limit = offset + limit
            if self.bm25_retriever and self.vector_retriever:
                # 并行检索
                bm25_nodes = await self.bm25_retriever.aretrieve(expanded_query)
                vector_nodes = await self.vector_retriever.aretrieve(expanded_query)

                # 使用搜索专用的合并逻辑
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
                corpus_size = self.index_manager.get_corpus_size()
                adjusted_limit = min(fetch_limit, max(1, corpus_size))
                retriever = self.index_manager.get_index().as_retriever(
                    similarity_top_k=adjusted_limit
                )
                nodes = await retriever.aretrieve(expanded_query)

            logger.info(
                f"Raw retrieval results: {len(nodes)} nodes found before filtering"
            )
            if nodes:
                logger.info(f"Top raw score: {nodes[0].score or 0.0:.3f}")

            # 处理和过滤结果
            processed_results = self._process_search_results(
                nodes, query, expanded_query, bm25_nodes
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
            logger.error(f"Error during content search: {e}", exc_info=True)
            return {"total": 0, "results": []}

    def _build_age_filters(self, age: int):
        """构建弹性年龄过滤器"""
        if age <= 0 or settings.rag_age_filter_strictness == 0:
            return None

        from llama_index.core.vector_stores import (
            MetadataFilter,
            MetadataFilters,
            FilterOperator,
        )

        tolerance = settings.rag_age_filter_tolerance
        min_age = max(0, age - tolerance)
        max_age = age + tolerance

        # 宽松过滤：只要年龄范围有重叠就返回
        filters = [
            # 目标最小年龄 ≤ 最大容忍年龄
            MetadataFilter(
                key="target_age_min", value=max_age, operator=FilterOperator.LTE
            ),
            # 目标最大年龄 ≥ 最小容忍年龄
            MetadataFilter(
                key="target_age_max", value=min_age, operator=FilterOperator.GTE
            ),
        ]

        return MetadataFilters(filters=filters)

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
        import time

        start_time = time.time()

        if use_hybrid:
            # 设置过滤器
            self.bm25_retriever.filters = filters
            self.vector_retriever.filters = filters

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
                    query, age
                )

            # 并行检索
            bm25_nodes = await self.bm25_retriever.aretrieve(query)
            vector_nodes = await self.vector_retriever.aretrieve(query)

            # 合并结果（先不限制数量，留给重排序器处理）
            nodes = HybridRetrievalMerger.merge_results(
                bm25_nodes,
                vector_nodes,
                bm25_weight=bm25_weight,
                vector_weight=vector_weight,
                merge_mode=self.merge_mode,
                limit=self.reranker.initial_k if self.reranker.model else limit,
            )

            # 应用 Cross-Encoder 重排序
            if self.reranker.model and nodes:
                nodes = self.reranker.rerank(query, nodes)
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
            import json

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

            # 计算最终得分：基础相关性得分 * (1 - 年龄权重) + 年龄适配度 * 年龄权重
            final_score = base_score
            age_fit_score = 1.0
            if user_age is not None:
                # 使用儿童发展引擎计算更精准的年龄适配度
                age_fit_score = child_development_engine.calculate_age_appropriateness(
                    content, user_age
                )
                # 同时考虑元数据中的年龄范围
                metadata_age_fit = self._calculate_age_fit_score(
                    user_age, target_age_min, target_age_max
                )
                # 综合两种评分，儿童发展引擎权重更高
                age_fit_score = 0.7 * age_fit_score + 0.3 * metadata_age_fit

                age_weight = settings.rag_age_fit_weight
                final_score = base_score * (1 - age_weight) + age_fit_score * age_weight

            # 检查重复内容
            is_duplicate = False
            for existing_item in results:
                if self._is_content_duplicate(content, existing_item.content):
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
                relevance_score=float(final_score),
            )
            results.append(item)

        # 按最终得分重新排序
        results.sort(key=lambda x: x.relevance_score, reverse=True)

        return results

    @staticmethod
    def _is_content_duplicate(content1: str, content2: str) -> bool:
        """
        判断内容是否重复

        Args:
            content1: 待检测内容
            content2: 已存在内容

        Returns:
            bool: 是否重复
        """
        # 移除空白字符后比较
        c1 = "".join(content1.split())
        c2 = "".join(content2.split())

        # 完全相同
        if c1 == c2:
            return True

        l1, l2 = len(c1), len(c2)
        if l1 == 0 or l2 == 0:
            return False

        # 包含关系（较短的是较长的子集，且长度占比超过80%）
        if l1 < l2:
            if c1 in c2 and l1 / l2 > 0.8:
                return True
        else:
            if c2 in c1 and l2 / l1 > 0.8:
                return True

        # 相似度比较 (针对只有少量字符差异的情况，如标点符号差异)
        # 只有长度接近时才计算，提高性能
        if abs(l1 - l2) / max(l1, l2) < 0.2:
            # 快速检查前缀和后缀是否大部分相同
            min_len = min(l1, l2)
            check_len = min(50, min_len)
            if c1[:check_len] == c2[:check_len] and c1[-check_len:] == c2[-check_len:]:
                # 如果首尾都相同，则大概率是重复内容，进行完整比对
                ratio = difflib.SequenceMatcher(None, c1, c2).ratio()
                if ratio > 0.9:
                    return True

        return False

    def _process_search_results(
        self, nodes, original_query: str, expanded_query: str, bm25_nodes: List = None
    ) -> List[dict]:
        """处理搜索结果，包括过滤、评分调整等"""
        if not nodes:
            logger.debug("_process_search_results: 无搜索结果，返回空列表")
            return []

        # 阈值设置
        is_hybrid = (
            self.bm25_retriever is not None and self.vector_retriever is not None
        )
        # 当 BM25 无结果时，即使是混合模式也使用向量阈值（说明语义匹配优先）
        has_bm25_results = len(bm25_nodes) > 0 if is_hybrid else False
        if is_hybrid and has_bm25_results:
            threshold = settings.rag_search_score_threshold_hybrid
            logger.info(
                f"_process_search_results: 混合检索模式，阈值={threshold}, BM25 结果数={len(bm25_nodes)}"
            )
        else:
            threshold = settings.rag_search_score_threshold_vector
            logger.info(f"_process_search_results: 向量检索模式，阈值={threshold}")

        # 动态截断：如果最高分低于阈值，直接返回空
        top_score = nodes[0].score or 0.0
        logger.info(
            f"_process_search_results: 最高分={top_score:.4f}, 阈值={threshold}, 相对截断比例={settings.rag_search_relative_cutoff_ratio}"
        )
        if top_score < threshold:
            logger.warning(
                f"_process_search_results: 最高分 {top_score:.4f} 低于阈值 {threshold}, 返回空结果"
            )
            return []

        # 相对分数截断：当只有向量结果时使用更宽松的相对截断比例
        if is_hybrid and not has_bm25_results:
            # 纯向量结果使用 0.3 的相对截断（与语义检索保持一致）
            relative_cutoff = top_score * 0.3
            logger.debug(
                f"_process_search_results: 纯向量结果，相对截断={relative_cutoff:.4f}"
            )
        else:
            relative_cutoff = top_score * settings.rag_search_relative_cutoff_ratio
            logger.debug(
                f"_process_search_results: 混合结果，相对截断={relative_cutoff:.4f}"
            )

        # 关键词匹配检查
        original_keywords = set(jieba.lcut(original_query.lower()))
        expanded_keywords = set(jieba.lcut(expanded_query.lower()))
        stop_words = {
            "的",
            "了",
            "是",
            "我",
            "你",
            "他",
            "我们",
            "你们",
            "他们",
            "什么",
            "怎么",
            "如何",
            "为什么",
            "吗",
            "呢",
        }
        original_keywords = {
            kw for kw in original_keywords if len(kw) > 1 and kw not in stop_words
        }
        all_keywords = original_keywords.union(expanded_keywords)
        all_keywords = {
            kw for kw in all_keywords if len(kw) > 1 and kw not in stop_words
        }

        results = []
        from src.service.document_manager import document_manager

        logger.info(f"_process_search_results: 开始处理 {len(nodes)} 个搜索结果")
        for i, node_with_score in enumerate(nodes):
            node = node_with_score.node
            metadata = node.metadata or {}
            content = node.get_content()
            raw_score = float(node_with_score.score or 0.0)
            logger.debug(
                f"Processing result {i}: 原始分数={raw_score:.4f}, 内容长度={len(content)}, 来源={metadata.get('file_name', 'Unknown')}"
            )

            # 过滤无效内容
            if (
                not content
                or content.startswith("[General Information]")
                or "书名=" in content
                or "SS 号=" in content
                or (
                    "参考文献" in content and len(content) < 100
                )  # 只有短内容的参考文献才过滤，避免误杀正文
            ):
                logger.debug(f"Filtered result {i}: 无效内容，分数={raw_score:.4f}")
                continue

            # 阈值过滤
            if raw_score < threshold or raw_score < relative_cutoff:
                logger.debug(
                    f"Filtered result {i}: 分数 {raw_score:.4f} 低于阈值 {threshold} 或相对截断 {relative_cutoff:.4f}"
                )
                continue

            # 关键词匹配检查 (改为加分项，而非硬过滤)
            # if all_keywords:
            #     content_lower = content.lower()
            #     has_keyword = any(kw in content_lower for kw in all_keywords)
            #     if not has_keyword:
            #         continue

            # 原始关键词匹配加成
            keyword_bonus = 0.0
            if original_keywords:
                content_lower = content.lower()
                matched_original = sum(
                    1 for kw in original_keywords if kw in content_lower
                )
                original_match_ratio = (
                    matched_original / len(original_keywords)
                    if original_keywords
                    else 0
                )
                keyword_bonus = original_match_ratio * 0.2
                logger.debug(
                    f"Processing result {i}: 关键词匹配={matched_original}/{len(original_keywords)}, 加成={keyword_bonus:.4f}"
                )

            final_score = min(raw_score + keyword_bonus, 1.0)
            logger.debug(
                f"Processing result {i}: 内部绝对分数={final_score:.4f} (原始={raw_score:.4f} + 加成={keyword_bonus:.4f})"
            )

            # 将内部绝对分数映射为人类友好的展示分数 (60% - 98%)
            # 内部绝对分数通常在 0.25 (阈值) 到 0.65 之间
            max_expected_score = 0.65
            base_display_score = 0.60
            max_display_score = 0.98

            if final_score >= max_expected_score:
                display_score = max_display_score
            else:
                # 线性映射: [threshold, max_expected_score] -> [base_display_score, max_display_score]
                score_range = max_expected_score - threshold
                if score_range > 0:
                    ratio = (final_score - threshold) / score_range
                    display_score = base_display_score + ratio * (
                        max_display_score - base_display_score
                    )
                else:
                    display_score = base_display_score

            display_score = min(
                max(display_score, base_display_score), max_display_score
            )
            logger.debug(f"Processing result {i}: 展示分数={display_score:.4f}")

            # 获取源书名
            file_hash = metadata.get("file_hash")
            source_book = metadata.get("file_name", "Unknown Source")
            if file_hash:
                doc = document_manager.get_document(file_hash)
                if doc:
                    source_book = doc.file_name

            # 处理页码显示
            page_label = metadata.get("page_label")
            if page_label:
                if "index_split" in str(page_label) or ".html" in str(page_label):
                    page_label = metadata.get("chapter_title") or "Section"
                elif len(str(page_label)) > 10 and not str(page_label).isdigit():
                    page_label = f"章节: {page_label}"

            # 检查重复内容
            is_duplicate = False
            for existing_item in results:
                # 优先检查file_hash是否相同（如果是同一文件的同一部分，hash相同则大概率重复）
                # 但这里的需求主要是内容去重，不同文件如果内容完全一致也应该去重
                if self._is_content_duplicate(content, existing_item["content"]):
                    is_duplicate = True
                    # 如果当前结果分数更高（理论上已按分数排序，不会发生），或者元数据更完整，可以考虑替换
                    # 这里简单起见，保留已存在的（分数更高的）结果
                    break

            if is_duplicate:
                logger.debug(f"Filtered result {i}: 重复内容，分数={final_score:.4f}")
                continue

            results.append(
                {
                    "id": node.node_id,
                    "content": content,
                    "score": display_score,
                    "raw_score": final_score,
                    "source_book": source_book,
                    "chapter_title": metadata.get("chapter_title"),
                    "page_label": page_label,
                    "target_age_min": metadata.get("target_age_min", 0),
                    "target_age_max": metadata.get("target_age_max", 18),
                    "brain_regions": metadata.get("brain_regions", []),
                    "topics": metadata.get("topics", []),
                    "file_hash": metadata.get("file_hash"),
                }
            )
            logger.debug(
                f"Added result {i}: 分数={final_score:.4f}, 来源={source_book}, 章节={metadata.get('chapter_title', 'N/A')}"
            )

        logger.info(f"_process_search_results: 处理完成，返回 {len(results)} 个结果")
        if results:
            top_scores = [f"{r['score']:.4f}" for r in results[:3]]
            logger.info(f"_process_search_results: Top 3 结果分数：{top_scores}")
        return results

    async def _rewrite_query(self, query: str, age: int) -> str:
        """重写查询以提高检索准确率"""
        if not settings.rag_config["query_rewrite"]["enabled"]:
            return query

        if not self.dashscope_available:
            return self._local_rewrite_query(query, age)

        try:
            # Prompt 注入检测
            injected, reason = prompt_injection_guard.detect_injection(query)
            if injected:
                logger.warning(f"Prompt injection detected in query rewrite: {reason}")
                query = prompt_injection_guard.sanitize_content(query)

            # 使用工厂创建 LLM 实例
            llm = LLMServiceFactory.create(
                framework=LLMFramework.LANGCHAIN,
                model_name=settings.llm_models["query_rewrite"],
                scenario="query_rewrite",
                temperature=0.6,
            )

            # 构建提示词
            messages = [
                LLMMessage(
                    role="system",
                    content="你是一个查询优化专家，负责将用户的自然语言查询重写为更适合检索的关键词组合。",
                ),
                LLMMessage(
                    role="user",
                    content=QUERY_REWRITE_PROMPT.format(age=age, query=query),
                ),
            ]

            # 调用 LLM
            response = await llm.chat(
                LLMRequest(
                    messages=messages,
                    model_name=settings.llm_models["query_rewrite"],
                    temperature=0.6,
                    max_tokens=256,
                    scenario="query_rewrite",
                    prompt_key="query_rewrite",
                )
            )
            rewritten_query = response.content.strip()
            logger.info(f"Query rewritten: '{query}' -> '{rewritten_query}'")
            return rewritten_query if rewritten_query else query
        except Exception as e:
            logger.warning(f"Query rewrite failed: {e}, using local fallback")
            return self._local_rewrite_query(query, age)

    def _local_rewrite_query(self, query: str, age: int) -> str:
        """本地查询重写兜底逻辑"""
        # 移除常见无意义词和标点
        query = re.sub(r"[?？!！.。，,]", " ", query)
        # 针对年龄添加关键词
        if age > 0:
            if age < 3:
                query += " 婴幼儿 早期教育"
            elif age < 6:
                query += " 幼儿园 学前教育"
            else:
                query += " 学龄儿童"
        return query.strip()

    def _validate_expansion(self, expansion_text: str, original_query: str) -> bool:
        """
        验证同义词扩展质量

        验证规则：
        1. 长度检查：不应超过 200 字符
        2. 格式检查：不应包含完整句子（句号、感叹号、问号、冒号）
        3. 必须包含原查询
        4. 不应包含敏感词或无关内容

        Args:
            expansion_text: 扩展后的文本
            original_query: 原始查询

        Returns:
            是否通过验证
        """
        # 长度检查
        if len(expansion_text) > 200:
            return False

        # 格式检查（不应包含完整句子）
        if any(punct in expansion_text for punct in ["。", "！", "？", "：", "\n"]):
            return False

        # 必须包含原查询
        if original_query not in expansion_text:
            return False

        # 检查是否包含明显的无关内容
        irrelevant_patterns = ["抱歉", "无法", "不知道", "请提供", "问题"]
        if any(pattern in expansion_text for pattern in irrelevant_patterns):
            return False

        return True

    async def _expand_synonyms(self, query: str) -> str:
        """同义词扩展以提高召回率，增加质量验证"""
        if not self.dashscope_available:
            return self._local_expand_synonyms(query)

        try:
            # Prompt 注入检测
            injected, reason = prompt_injection_guard.detect_injection(query)
            if injected:
                logger.warning(
                    f"Prompt injection detected in synonym expansion: {reason}"
                )
                query = prompt_injection_guard.sanitize_content(query)

            # Use LangChain structured output parser to enforce JSON format
            parser = PydanticOutputParser(pydantic_object=SynonymExpansionResult)

            # Create prompt template with format instructions
            prompt = PromptTemplate(
                template=SYNONYM_EXPANSION_PROMPT + "\n{format_instructions}\n",
                input_variables=["query"],
                partial_variables={
                    "format_instructions": parser.get_format_instructions()
                },
            )

            # Format prompt with query
            formatted_prompt = prompt.format(query=query)

            # 使用安全包装的提示词
            safe_prompt = formatted_prompt

            # 使用工厂创建 LLM 实例
            llm = LLMServiceFactory.create(
                framework=LLMFramework.LANGCHAIN,
                model_name=settings.llm_models["query_rewrite"],
                scenario="synonym_expansion",
                temperature=0.8,
            )

            # 构建提示词
            messages = [
                LLMMessage(
                    role="system",
                    content="你是一个同义词扩展专家，负责为用户的查询生成相关的同义词和相关术语，以提高检索召回率。",
                ),
                LLMMessage(role="user", content=safe_prompt),
            ]

            # 调用 LLM
            response = await llm.chat(
                LLMRequest(
                    messages=messages,
                    model_name=settings.llm_models["query_rewrite"],
                    temperature=0.8,
                    max_tokens=256,
                    scenario="synonym_expansion",
                    prompt_key="synonym_expansion",
                )
            )
            result_text = response.content.strip()

            # Clean response to remove markdown code block markers
            result_text = re.sub(
                r"^```(?:json)?\s*", "", result_text, flags=re.IGNORECASE
            )
            result_text = re.sub(r"\s*```$", "", result_text)
            result_text = result_text.strip()

            # Parse using structured parser
            try:
                result = parser.parse(result_text)
                synonym_list = [
                    str(s).strip() for s in result.synonyms if str(s).strip()
                ]
            except Exception as e:
                logger.warning(
                    f"同义词扩展JSON解析失败: {e}, 原始内容: {result_text[:100]}"
                )
                synonym_list = re.split(r"[\n、,，\s\"']+", result_text)
                synonym_list = [
                    s.strip() for s in synonym_list if s.strip() and len(s) < 20
                ]

            # 必须包含原词，否则回退
            if query not in synonym_list:
                synonym_list.insert(0, query)

            # 去重后拼接
            all_terms = list(dict.fromkeys(synonym_list))
            expanded_query = " ".join(all_terms)

            # 质量验证
            if not self._validate_expansion(expanded_query, query):
                logger.warning(f"同义词扩展质量验证失败，使用本地扩展")
                return self._local_expand_synonyms(query)

            logger.info(f"同义词扩展成功：'{query}' -> '{expanded_query}'")
            return expanded_query

        except Exception as e:
            logger.warning(f"同义词扩展失败：{e}, 使用本地扩展")
            return self._local_expand_synonyms(query)

    def _local_expand_synonyms(self, query: str) -> str:
        """本地同义词扩展兜底逻辑"""
        synonyms_dict = {
            "大运动": ["粗大动作", "运动能力", "平衡能力"],
            "精细动作": ["手眼协调", "手指灵活性"],
            "语言": ["表达能力", "沟通能力", "词汇量"],
            "认知": ["思维能力", "逻辑推理", "注意力"],
            "社交": ["人际交往", "情绪管理", "同伴关系"],
            "专注力": ["注意力", "集中力"],
            "感统": ["感觉统合", "前庭觉", "触觉"],
            "家长": ["父母", "家长教育", "家庭教育", "亲子", "育儿"],
        }

        expanded_terms = [query]
        for word, syns in synonyms_dict.items():
            if word in query:
                expanded_terms.extend(syns)

        return " ".join(list(dict.fromkeys(expanded_terms)))

    def _get_cache_key(self, query: str, age: int, limit: int) -> tuple:
        """生成包含索引版本和配置指纹的缓存键"""
        return (
            query.strip().lower(),
            age,
            limit,
            self.index_manager.index_version,
            self.index_manager.config_fingerprint,
        )
