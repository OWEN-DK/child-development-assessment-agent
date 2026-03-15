import jieba
import re
import difflib
from typing import List, Optional
from llama_index.core.retrievers import BaseRetriever
from llama_index.retrievers.bm25 import BM25Retriever
from llama_index.llms.dashscope import DashScope
from src.config.settings import settings
from src.utils.logger import logger
from src.core.hybrid_retrieval import HybridRetrievalMerger
from src.model.schemas import KnowledgeItem
from src.core.prompts import QUERY_REWRITE_PROMPT, SYNONYM_EXPANSION_PROMPT
from src.service.index_manager_service import IndexManagerService
from src.service.cache_service import CacheService


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

        # 加载jieba自定义词典
        import os
        from src.config.settings import BASE_DIR

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

        # 初始化BM25检索器（使用jieba分词）
        self.bm25_retriever = BM25Retriever.from_defaults(
            index=index, similarity_top_k=bm25_top_k, tokenizer=jieba.lcut
        )

        # 初始化向量检索器
        self.vector_retriever = index.as_retriever(similarity_top_k=vector_top_k)

        self.bm25_weight = rag_config["bm25_weight"]
        self.vector_weight = rag_config["vector_weight"]
        self.merge_mode = rag_config["merge_mode"]

        logger.info(
            f"Retrievers initialized: BM25 top_k={bm25_top_k}, Vector top_k={vector_top_k}"
        )

    def reload_retrievers(self):
        """重新加载检索器（索引更新后调用）"""
        self._initialize_retrievers()
        self.cache_service.clear()
        logger.info("Retrievers reloaded")

    async def retrieve_knowledge(
        self, query: str, age: int, limit: int = 3
    ) -> List[KnowledgeItem]:
        """
        根据查询和年龄检索相关知识点
        """
        logger.info(f"Retrieving knowledge for query: '{query}', age: {age}")

        # 检查缓存
        cache_key = self._get_cache_key(query, age, limit)
        cached_result = self.cache_service.get(cache_key)
        if cached_result:
            return cached_result

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
            )

            # 转换为KnowledgeItem，传入用户年龄计算适配度并排序
            knowledge_items = self._convert_to_knowledge_items(results, user_age=age)

            # 保存到缓存
            self.cache_service.set(cache_key, knowledge_items)

            return knowledge_items

        except Exception as e:
            logger.error(f"Error during retrieval: {e}", exc_info=True)
            return []

    async def search_content(self, query: str, limit: int = 20) -> List[dict]:
        """
        搜索知识库内容，返回匹配的片段和元数据
        """
        if not self.index_manager.is_index_available():
            logger.warning("Index not available, returning empty results.")
            return []

        try:
            # 同义词扩展
            expanded_query = await self._expand_synonyms(query)

            # 执行检索
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
                    limit=limit,
                )
            else:
                # 回退到单一向量检索
                corpus_size = self.index_manager.get_corpus_size()
                adjusted_limit = min(limit, max(1, corpus_size))
                retriever = self.index_manager.get_index().as_retriever(
                    similarity_top_k=adjusted_limit
                )
                nodes = await retriever.aretrieve(expanded_query)

            # 处理和过滤结果
            processed_results = self._process_search_results(
                nodes, query, expanded_query
            )

            return processed_results

        except Exception as e:
            logger.error(f"Error during content search: {e}", exc_info=True)
            return []

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
        self, query: str, filters, limit: int, use_hybrid: bool
    ):
        """执行检索逻辑"""
        if use_hybrid:
            # 设置过滤器
            self.bm25_retriever.filters = filters
            self.vector_retriever.filters = filters

            # 并行检索
            bm25_nodes = await self.bm25_retriever.aretrieve(query)
            vector_nodes = await self.vector_retriever.aretrieve(query)

            # 合并结果
            nodes = HybridRetrievalMerger.merge_results(
                bm25_nodes,
                vector_nodes,
                bm25_weight=self.bm25_weight,
                vector_weight=self.vector_weight,
                merge_mode=self.merge_mode,
                limit=limit,
            )
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
                or "SS号=" in content
            ):
                continue

            # 最低相似度阈值过滤
            base_score = node_with_score.score or 0.0
            if base_score < settings.rag_search_min_similarity_threshold:
                continue

            metadata = node.metadata or {}
            source = metadata.get("file_name", "Unknown Source")

            # 提取元数据字段
            brain_regions = metadata.get("brain_regions", [])
            topics = metadata.get("topics", [])
            benefits = metadata.get("benefits", topics)  # 兼容旧数据
            target_age_min = metadata.get("target_age_min", 0)
            target_age_max = metadata.get("target_age_max", 18)
            activity_type = metadata.get("activity_type", "Theory")
            chapter_title = metadata.get("chapter_title")
            page_label = metadata.get("page_label")

            # 计算最终得分：基础相关性得分 * (1 - 年龄权重) + 年龄适配度 * 年龄权重
            final_score = base_score
            age_fit_score = 1.0
            if user_age is not None:
                age_fit_score = self._calculate_age_fit_score(
                    user_age, target_age_min, target_age_max
                )
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
        self, nodes, original_query: str, expanded_query: str
    ) -> List[dict]:
        """处理搜索结果，包括过滤、评分调整等"""
        if not nodes:
            return []

        # 阈值设置
        is_hybrid = (
            self.bm25_retriever is not None and self.vector_retriever is not None
        )
        threshold = (
            settings.rag_search_score_threshold_hybrid
            if is_hybrid
            else settings.rag_search_score_threshold_vector
        )

        # 动态截断：如果最高分低于阈值，直接返回空
        top_score = nodes[0].score or 0.0
        if top_score < threshold:
            logger.debug(
                f"Top result score {top_score} below threshold {threshold}, returning empty"
            )
            return []

        # 相对分数截断
        relative_cutoff = top_score * settings.rag_search_relative_cutoff_ratio

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

        for node_with_score in nodes:
            node = node_with_score.node
            metadata = node.metadata or {}
            content = node.get_content()

            # 过滤无效内容
            if (
                not content
                or content.startswith("[General Information]")
                or "书名=" in content
                or "SS号=" in content
                or "参考文献" in content
            ):
                continue

            # 阈值过滤
            raw_score = float(node_with_score.score or 0.0)
            if raw_score < threshold or raw_score < relative_cutoff:
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

            final_score = min(raw_score + keyword_bonus, 1.0)

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
                continue

            results.append(
                {
                    "id": node.node_id,
                    "content": content,
                    "score": final_score,
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

        return results

    async def _rewrite_query(self, query: str, age: int) -> str:
        """重写查询以提高检索准确率"""
        if (
            not settings.rag_config["query_rewrite"]["enabled"]
            or not self.dashscope_available
        ):
            return query

        try:
            llm = DashScope(
                model=settings.llm_models["query_rewrite"],
                api_key=settings.dashscope_api_key,
            )
            prompt = QUERY_REWRITE_PROMPT.format(query=query, age=age)
            response = await llm.acomplete(prompt)
            rewritten_query = response.text.strip()
            logger.info(f"Query rewritten: '{query}' -> '{rewritten_query}'")
            return rewritten_query if rewritten_query else query
        except Exception as e:
            logger.warning(f"Query rewrite failed: {e}, using original query")
            return query

    async def _expand_synonyms(self, query: str) -> str:
        """同义词扩展以提高召回率"""
        if not self.dashscope_available:
            return query

        try:
            llm = DashScope(
                model=settings.llm_models["query_rewrite"],
                api_key=settings.dashscope_api_key,
            )
            prompt = SYNONYM_EXPANSION_PROMPT.format(query=query)
            response = await llm.acomplete(prompt)
            synonyms = response.text.strip()

            # 清理返回结果，移除多余的标签和说明
            synonyms = re.sub(r"^同义词[:：]\s*", "", synonyms)
            synonyms = re.sub(r"^Synonyms[:：]\s*", "", synonyms)
            synonyms = synonyms.strip("\"'`")

            # 如果返回多个同义词，用空格连接作为扩展查询
            if "\n" in synonyms or "、" in synonyms or "," in synonyms:
                # 分割多个同义词并去重
                synonym_list = re.split(r"[\n、,，\s]+", synonyms)
                synonym_list = [s.strip() for s in synonym_list if s.strip()]
                # 保留原始查询词并添加同义词
                all_terms = list(dict.fromkeys([query] + synonym_list))
                expanded_query = " ".join(all_terms)
                logger.info(
                    f"Query expanded with multiple synonyms: '{query}' -> '{expanded_query}'"
                )
                return expanded_query

            logger.info(f"Query expanded: '{query}' -> '{synonyms}'")
            return synonyms if synonyms else query
        except Exception as e:
            logger.warning(f"Synonym expansion failed: {e}, using original query")
            return query

    @staticmethod
    def _get_cache_key(query: str, age: int, limit: int) -> tuple[str, int, int]:
        """生成缓存键"""
        return (query.strip().lower(), age, limit)
