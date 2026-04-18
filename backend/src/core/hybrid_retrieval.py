from typing import List, Dict, Optional
from llama_index.core.schema import NodeWithScore
from src.config import settings
from src.utils.logger import logger
import math
import re

_query_analyzer_instance = None


def _get_default_analyzer():
    """获取默认的 QueryAnalyzer 实例（懒加载）"""
    global _query_analyzer_instance
    if _query_analyzer_instance is None:
        from src.core.rag.query_analyzer import QueryAnalyzer

        _query_analyzer_instance = QueryAnalyzer()
    return _query_analyzer_instance


class HybridRetrievalMerger:
    """改进的混合检索结果融合器，解决分数校准和归一化问题"""

    @staticmethod
    def _calibrate_bm25_score(score: float, corpus_quantile: float = None) -> float:
        """使用动态缩放因子的 sigmoid 将 BM25 分数压缩到 [0,1] 区间"""
        scale_factor = corpus_quantile or settings.bm25_scale_factor
        calibrated_score = 1 / (1 + math.exp(-score / scale_factor))
        logger.debug(
            f"BM25 分数校准：原始分数={score:.4f}, scale_factor={scale_factor}, 校准后={calibrated_score:.4f}"
        )
        return calibrated_score

    @staticmethod
    def _normalize_all_scores(nodes: List[NodeWithScore]) -> List[NodeWithScore]:
        """
        改进的归一化策略：
        - 使用 Sigmoid 校准向量分数
        - 增强极端场景处理
        - 避免人为引入顺序偏差
        """
        if not nodes:
            return nodes

        scores = [node.score or 0.0 for node in nodes]
        max_score = max(scores)
        min_score = min(scores)

        # 极端场景处理
        if len(nodes) == 1:
            # 单节点：保持原分数或进行基础校准
            nodes[0].score = HybridRetrievalMerger._calibrate_vector_score(
                nodes[0].score or 0.0
            )
            return nodes

        if max_score == min_score:
            # 全相同分数：使用微小差异，但不引入人为偏差
            base_score = HybridRetrievalMerger._calibrate_vector_score(max_score)
            for i, node in enumerate(nodes):
                node.score = base_score - (i * 0.001)  # 更小的差异
            return nodes

        if max_score == 0:
            # 全零分数：使用默认权重，不按索引顺序
            for node in nodes:
                node.score = 0.5  # 统一默认分数
            return nodes

        # 归一化策略（业界标准做法）
        # 目标：保留原始分数的相对关系，避免过度处理
        logger.info(
            f"开始归一化 {len(nodes)} 个节点分数，max_score={max_score:.4f}, min_score={min_score:.4f}"
        )

        # 业界最佳实践：简单的 Min-Max 归一化或保持原样
        # 过度复杂的归一化会导致分数失真
        for i, node in enumerate(nodes):
            raw_score = node.score or 0.0

            # 策略 1：如果分数已经在合理范围 [0.3, 1.0]，保持原样
            if 0.3 <= max_score <= 1.0 and min_score >= 0.1:
                normalized = raw_score
                logger.debug(f"节点#{i} 归一化 (保持): 原始={raw_score:.4f}")
            # 策略 2：如果最高分太低 (<0.3)，说明是纯向量检索，保持原样
            elif max_score < 0.3:
                normalized = raw_score
                logger.debug(f"节点#{i} 归一化 (低分保持): 原始={raw_score:.4f}")
            # 策略 3：其他情况，使用简单的线性归一化到 [0.2, 1.0]
            else:
                relative_score = raw_score / max_score if max_score > 0 else 0.0
                normalized = 0.2 + 0.8 * relative_score
                logger.debug(
                    f"节点#{i} 归一化 (线性): 原始={raw_score:.4f}, 相对={relative_score:.4f}, 归一化={normalized:.4f}"
                )

            # 直接使用归一化后的分数，不再进行会压低分数的二次校准
            node.score = normalized
            logger.debug(f"节点#{i} 最终分数：{node.score:.4f}")

        return nodes

    @staticmethod
    def _calibrate_vector_score(score: float) -> float:
        """
        向量分数校准（业界标准做法）

        保持向量分数的原始分布，仅做轻微调整，
        避免过度校准导致分数被压缩。

        Args:
            score: 原始分数（余弦相似度，通常 0.5-1.0）

        Returns:
            校准后的分数
        """
        # 业界最佳实践：保持向量分数的原始性
        # 余弦相似度 0.5-1.0 已经是合理的分布
        # 只需要处理极端低分的情况

        if score >= 0.7:
            # 高分段（良好匹配）：保持原样
            logger.debug(f"向量分数校准 (高分保持): 原始={score:.4f}, 保持原样")
            return score
        elif score >= 0.5:
            # 中等分数段：轻微压缩，但不改变分布
            calibrated = score * 0.95
            logger.debug(
                f"向量分数校准 (中等段): 原始={score:.4f}, 校准后={calibrated:.4f}"
            )
            return calibrated
        else:
            # 低分段（<0.5）：显著压缩，降低噪声
            calibrated = score * 0.7
            logger.debug(
                f"向量分数校准 (低分压缩): 原始={score:.4f}, 校准后={calibrated:.4f}"
            )
            return calibrated

    @staticmethod
    def get_dynamic_weights(
        query: str,
        age: int = None,
        query_analyzer=None,
        weight_config: Optional[Dict[str, Dict[str, float]]] = None,
        strategy: str = None,
    ) -> tuple[float, float]:
        """基于查询类型动态返回权重（适配中文场景）"""
        if strategy is None:
            strategy = settings.rag_weight_strategy

        # 回滚开关：固定权重模式
        if strategy == "fixed":
            bm25_weight = settings.rag_hybrid_bm25_weight
            return bm25_weight, 1 - bm25_weight

        # 使用 QueryAnalyzer 分析查询类型
        if query_analyzer is None:
            query_analyzer = _get_default_analyzer()

        analysis = query_analyzer.analyze(query)

        # 从配置获取权重
        if weight_config is None:
            weight_config = settings.rag_weight_by_query_type

        # 按查询类型获取权重
        type_key = analysis.query_type.value
        weights = weight_config.get(type_key, weight_config["default"])

        bm25_weight = weights["bm25"]
        vector_weight = weights["vector"]

        # 年龄微调（保留原有逻辑，但降低影响幅度）
        if age is not None and age < 3:
            bm25_weight *= 0.95  # 低龄儿童语义匹配略重要（从 0.9 降至 0.95）
            bm25_weight = max(bm25_weight, 0.2)  # 不低于 0.2

        logger.debug(
            f"动态权重决策：query='{query[:30]}', type={type_key}, "
            f"BM25={bm25_weight:.2f}, Vector={vector_weight:.2f}"
        )

        return bm25_weight, vector_weight

    @staticmethod
    def merge_results(
        bm25_nodes: List[NodeWithScore],
        vector_nodes: List[NodeWithScore],
        bm25_weight: float = 0.5,
        vector_weight: float = 0.5,
        merge_mode: str = "OR",
        limit: int = 10,
        normalize_scores: bool = True,
    ) -> List[NodeWithScore]:
        """
        改进的融合算法：先校准 BM25 分数，再全局统一归一化
        """
        if not bm25_nodes and not vector_nodes:
            logger.debug("merge_results: 无 BM25 和向量结果，返回空列表")
            return []

        logger.info(
            f"merge_results: 开始融合，BM25={len(bm25_nodes)}个，向量={len(vector_nodes)}个，权重=BM25:{bm25_weight}/向量:{vector_weight}"
        )

        # 第一步：校准 BM25 分数到 [0,1] 区间
        logger.debug(f"merge_results: 校准 {len(bm25_nodes)} 个 BM25 分数")
        for node in bm25_nodes:
            if node.score is not None:
                node.score = HybridRetrievalMerger._calibrate_bm25_score(node.score)

        node_map: Dict[str, NodeWithScore] = {}

        # 处理 BM25 结果
        logger.debug(f"merge_results: 处理 BM25 结果，应用权重 {bm25_weight}")
        for node in bm25_nodes:
            node_id = node.node.node_id
            original_score = node.score or 0.0
            node.score = original_score * bm25_weight
            logger.debug(
                f"merge_results: BM25 节点 {node_id}, 校准后={original_score:.4f}, 加权后={node.score:.4f}"
            )
            node_map[node_id] = node

        # 处理向量结果
        logger.debug(
            f"merge_results: 处理 {len(vector_nodes)} 个向量结果，应用权重 {vector_weight}"
        )
        for node in vector_nodes:
            node_id = node.node.node_id
            vector_score = (node.score or 0.0) * vector_weight

            if node_id in node_map:
                existing_node = node_map[node_id]
                old_score = existing_node.score or 0.0
                existing_node.score = old_score + vector_score
                logger.debug(
                    f"merge_results: 节点 {node_id} 融合，BM25={old_score:.4f}, 向量={vector_score:.4f}, 融合后={existing_node.score:.4f}"
                )
            else:
                if merge_mode == "OR":
                    node.score = vector_score
                    logger.debug(
                        f"merge_results: 纯向量节点 {node_id}, 分数={node.score:.4f}"
                    )
                    node_map[node_id] = node

        # 全局归一化
        all_nodes = list(node_map.values())
        if normalize_scores:
            logger.info(f"merge_results: 对 {len(all_nodes)} 个融合节点进行归一化")
            all_nodes = HybridRetrievalMerger._normalize_all_scores(all_nodes)
        else:
            logger.debug("merge_results: 跳过归一化")

        # 排序返回
        merged_nodes = sorted(all_nodes, key=lambda x: x.score or 0.0, reverse=True)[
            :limit
        ]

        logger.info(
            f"merge_results: 融合完成，BM25={len(bm25_nodes)}个，向量={len(vector_nodes)}个，最终={len(merged_nodes)}个结果"
        )
        if merged_nodes:
            logger.info(
                f"merge_results: Top 3 分数：{[f'{n.score:.4f}' for n in merged_nodes[:3]]}"
            )
        return merged_nodes

    @staticmethod
    def merge_for_search(
        bm25_nodes: List[NodeWithScore],
        vector_nodes: List[NodeWithScore],
        bm25_weight: float = 0.7,
        vector_weight: float = 0.3,
        no_match_vector_penalty: float = 0.3,
        limit: int = 20,
    ) -> List[NodeWithScore]:
        """搜索页面融合逻辑同步改进"""
        if not bm25_nodes and not vector_nodes:
            logger.debug("merge_for_search: 无 BM25 和向量结果，返回空列表")
            return []

        logger.info(
            f"merge_for_search: 开始融合，BM25={len(bm25_nodes)}个，向量={len(vector_nodes)}个，权重=BM25:{bm25_weight}/向量:{vector_weight}, 惩罚系数:{no_match_vector_penalty}"
        )

        # 校准 BM25 分数
        logger.debug(f"merge_for_search: 校准 {len(bm25_nodes)} 个 BM25 分数")
        for node in bm25_nodes:
            if node.score is not None:
                node.score = HybridRetrievalMerger._calibrate_bm25_score(node.score)

        # 向量惩罚
        # 如果是纯向量结果（BM25 没有结果），或者查询是"运动"这样的短词而没有 BM25 匹配，
        # 我们不能让分数变得极低，否则连最低阈值都过不去。
        # 这里改用一个更温和的惩罚策略：如果不命中 BM25，向量权重降低，但不做二次惩罚
        # 或者使用 1.0 避免极度衰减。
        vector_penalty = 1.0 if bm25_nodes else 1.0
        logger.debug(
            f"merge_for_search: 向量惩罚系数={vector_penalty} (BM25 有结果={len(bm25_nodes) > 0})"
        )

        node_map: Dict[str, NodeWithScore] = {}

        # 处理 BM25
        logger.debug(
            f"merge_for_search: 处理 {len(bm25_nodes)} 个 BM25 结果，应用权重 {bm25_weight}"
        )
        for node in bm25_nodes:
            node_id = node.node.node_id
            original_score = node.score or 0.0
            node.score = original_score * bm25_weight
            logger.debug(
                f"merge_for_search: BM25 节点 {node_id}, 校准后={original_score:.4f}, 加权后={node.score:.4f}"
            )
            node_map[node_id] = node

        # 处理向量
        logger.debug(f"merge_for_search: 处理 {len(vector_nodes)} 个向量结果")
        for node in vector_nodes:
            node_id = node.node.node_id
            # 如果没有 BM25 节点，这代表纯向量检索，权重应当使用 1.0 或者适当放大，
            # 否则 0.3 的权重会让所有分数强制变得极低 (例如 0.6 * 0.3 = 0.18)
            effective_vector_weight = vector_weight if bm25_nodes else 1.0
            vector_score = (
                (node.score or 0.0) * effective_vector_weight * vector_penalty
            )

            if node_id in node_map:
                old_score = node_map[node_id].score or 0.0
                node_map[node_id].score = old_score + vector_score
                logger.debug(
                    f"merge_for_search: 融合节点 {node_id}, BM25={old_score:.4f}, 向量={vector_score:.4f}, 融合后={node_map[node_id].score:.4f}"
                )
            else:
                # 保留没有命中 BM25 的纯向量结果
                # 如果有 BM25，那么纯向量节点会有惩罚；如果没有 BM25，那么不需要惩罚
                if bm25_nodes:
                    node.score = vector_score * no_match_vector_penalty
                    logger.debug(
                        f"merge_for_search: 纯向量节点 {node_id}, 原始={node.score:.4f}, 惩罚后={node.score:.4f}"
                    )
                else:
                    node.score = vector_score
                    logger.debug(
                        f"merge_for_search: 纯向量节点 {node_id} (无 BM25), 分数={node.score:.4f}"
                    )
                node_map[node_id] = node

        # 全局归一化
        all_nodes = list(node_map.values())

        # 修正：merge_for_search 之前的分数归一化导致了单节点分数会被极度压缩或放大
        # 以及分数极低时，应该避免使用 _normalize_all_scores，而是保持其分数相对一致性
        # 如果是单节点或无节点，不进行归一化，直接返回，保持其由于 penalty 而降低的分数

        # 不要使用 _normalize_all_scores 进行归一化，因为它会将最高分强制设为接近 1.0 的值，
        # 导致无关的结果在单独检索时被放大为 100% 匹配。
        # 我们直接使用加权后的绝对分数。

        merged_nodes = sorted(all_nodes, key=lambda x: x.score or 0.0, reverse=True)[
            :limit
        ]

        logger.info(f"merge_for_search: 融合完成，返回 {len(merged_nodes)} 个结果")
        if merged_nodes:
            logger.info(
                f"merge_for_search: Top 5 分数：{[f'{n.score:.4f}' for n in merged_nodes[:5]]}"
            )
        return merged_nodes
