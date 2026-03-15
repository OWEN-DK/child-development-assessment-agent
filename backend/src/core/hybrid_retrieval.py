from typing import List, Dict, Any, Tuple
from llama_index.core.schema import NodeWithScore
from src.config.settings import settings
from src.utils.logger import logger


class HybridRetrievalMerger:
    """混合检索结果融合器，统一处理BM25和向量检索结果的分数融合"""

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
        合并BM25和向量检索结果
        Args:
            bm25_nodes: BM25检索结果
            vector_nodes: 向量检索结果
            bm25_weight: BM25分数权重
            vector_weight: 向量分数权重
            merge_mode: 合并模式 ("OR" - 并集, "AND" - 交集)
            limit: 返回结果数量限制
            normalize_scores: 是否归一化分数到0-1范围
        Returns:
            合并排序后的结果
        """
        if not bm25_nodes and not vector_nodes:
            return []

        # 归一化分数
        if normalize_scores:
            bm25_nodes = HybridRetrievalMerger._normalize_scores(bm25_nodes)
            vector_nodes = HybridRetrievalMerger._normalize_scores(vector_nodes)

        node_map: Dict[str, NodeWithScore] = {}

        # 处理BM25结果
        for node in bm25_nodes:
            node_id = node.node.node_id
            node.score = (node.score or 0.0) * bm25_weight
            node_map[node_id] = node

        # 处理向量结果
        for node in vector_nodes:
            node_id = node.node.node_id
            vector_score = (node.score or 0.0) * vector_weight

            if node_id in node_map:
                # 合并分数
                existing_node = node_map[node_id]
                existing_node.score = (existing_node.score or 0.0) + vector_score
            else:
                if merge_mode == "OR":
                    # 并集模式下添加仅在向量结果中的节点
                    node.score = vector_score
                    node_map[node_id] = node

        # 转换为列表并排序
        merged_nodes = sorted(
            node_map.values(), key=lambda x: x.score or 0.0, reverse=True
        )[:limit]

        logger.debug(
            f"Merged {len(bm25_nodes)} BM25 nodes and {len(vector_nodes)} vector nodes into {len(merged_nodes)} results"
        )
        return merged_nodes

    @staticmethod
    def _normalize_scores(nodes: List[NodeWithScore]) -> List[NodeWithScore]:
        """将分数归一化到0-1范围"""
        if not nodes:
            return nodes

        scores = [node.score or 0.0 for node in nodes]
        max_score = max(scores)
        min_score = min(scores)

        if max_score == min_score:
            # 所有分数相同，归一化为1.0
            for node in nodes:
                node.score = 1.0
            return nodes

        # 线性归一化
        for node in nodes:
            node.score = ((node.score or 0.0) - min_score) / (max_score - min_score)

        return nodes

    @staticmethod
    def merge_for_search(
        bm25_nodes: List[NodeWithScore],
        vector_nodes: List[NodeWithScore],
        bm25_weight: float = 0.7,
        vector_weight: float = 0.3,
        no_match_vector_penalty: float = 0.3,
        limit: int = 20,
    ) -> List[NodeWithScore]:
        """
        专为搜索页面设计的合并逻辑，包含关键词匹配惩罚机制
        """
        if not bm25_nodes and not vector_nodes:
            return []

        # 归一化BM25分数
        max_bm25 = 0.0
        if bm25_nodes:
            max_bm25 = max(n.score for n in bm25_nodes) if bm25_nodes[0].score else 1.0
            if max_bm25 > 0:
                for n in bm25_nodes:
                    n.score = (n.score or 0.0) / max_bm25

        # 向量检索惩罚：如果没有BM25匹配，降低向量结果权重
        vector_penalty = 1.0 if max_bm25 > 0 else no_match_vector_penalty

        node_map: Dict[str, NodeWithScore] = {}

        # 处理BM25结果
        for node in bm25_nodes:
            node_id = node.node.node_id
            node.score = (node.score or 0.0) * bm25_weight
            node_map[node_id] = node

        # 处理向量结果
        for node in vector_nodes:
            node_id = node.node.node_id
            vector_score = (node.score or 0.0) * vector_weight * vector_penalty

            if node_id in node_map:
                node_map[node_id].score = (
                    node_map[node_id].score or 0.0
                ) + vector_score
            else:
                node.score = vector_score
                node_map[node_id] = node

        # 排序并返回
        merged_nodes = sorted(
            node_map.values(), key=lambda x: x.score or 0.0, reverse=True
        )[:limit]

        return merged_nodes
