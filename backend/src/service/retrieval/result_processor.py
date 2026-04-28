import difflib
from typing import List

from src.config import settings
from src.utils.logger import logger


class ResultProcessor:
    """结果处理服务，负责处理搜索结果和去重"""

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

        # 包含关系（较短的是较长的子集，且长度占比超过阈值）
        containment_threshold = settings.rag_dedup_containment_threshold
        if l1 < l2:
            if c1 in c2 and l1 / l2 > containment_threshold:
                return True
        else:
            if c2 in c1 and l2 / l1 > containment_threshold:
                return True

        # 相似度比较 (针对只有少量字符差异的情况，如标点符号差异)
        # 只有长度接近时才计算，提高性能
        length_diff_threshold = settings.rag_dedup_length_diff_threshold
        if abs(l1 - l2) / max(l1, l2) < length_diff_threshold:
            # 快速检查前缀和后缀是否大部分相同
            min_len = min(l1, l2)
            check_len = min(settings.rag_dedup_prefix_check_length, min_len)
            if c1[:check_len] == c2[:check_len] and c1[-check_len:] == c2[-check_len:]:
                # 如果首尾都相同，则大概率是重复内容，进行完整比对
                ratio = difflib.SequenceMatcher(None, c1, c2).ratio()
                similarity_threshold = settings.rag_dedup_similarity_threshold
                if ratio > similarity_threshold:
                    return True

        return False

    async def _process_search_results(
        self,
        nodes,
        original_query: str,
        expanded_query: str,
        bm25_nodes: List = None,
        bm25_retriever=None,
        vector_retriever=None,
    ) -> List[dict]:
        """处理搜索结果，包括过滤、评分调整等"""
        import jieba

        from src.service.document_manager import document_manager

        if not nodes:
            logger.debug("_process_search_results: 无搜索结果，返回空列表")
            return []

        # 阈值设置
        is_hybrid = (
            bm25_retriever is not None and vector_retriever is not None
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

            # 关键词频次加成（对数压缩，防止同义词过多导致加成爆炸）
            import math

            keyword_bonus = 0.0
            if original_keywords:
                content_lower = content.lower()
                total_occurrences = sum(
                    content_lower.count(kw) for kw in original_keywords
                )
                log_occurrences = math.log(1 + total_occurrences)
                normalized_density = log_occurrences / max(len(content_lower) / 500, 1)
                keyword_bonus = min(
                    normalized_density * settings.rag_scoring_keyword_bonus_log_weight,
                    settings.rag_scoring_keyword_bonus_max,
                )
                logger.debug(
                    f"Processing result {i}: 关键词总出现={total_occurrences}次, 对数值={log_occurrences:.2f}, 密度={normalized_density:.2f}, 加成={keyword_bonus:.4f}"
                )

            final_score = min(raw_score + keyword_bonus, 1.0)
            logger.debug(
                f"Processing result {i}: 内部绝对分数={final_score:.4f} (原始={raw_score:.4f} + 加成={keyword_bonus:.4f})"
            )

            # 将内部绝对分数映射为人类友好的展示分数
            # 内部绝对分数通常在阈值到 max_expected_score 之间
            max_expected_score = settings.rag_scoring_max_expected_score
            base_display_score = settings.rag_scoring_base_display_score
            max_display_score = settings.rag_scoring_max_display_score

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
                doc = await document_manager.get_document(file_hash)
                if doc:
                    source_book = doc["file_name"]

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
                    "age_fit_score": None,  # 搜索页不计算年龄适配度，后续如需支持需修改 search_content 签名
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
