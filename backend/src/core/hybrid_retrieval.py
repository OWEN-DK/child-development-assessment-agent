import math
import re
from typing import Dict, List, Optional

from llama_index.core.schema import NodeWithScore

from src.config import settings
from src.utils.logger import logger

_query_analyzer_instance = None


def _get_default_analyzer():
    """获取默认的 QueryAnalyzer 实例（懒加载）"""
    global _query_analyzer_instance
    if _query_analyzer_instance is None:
        from src.core.rag.query_analyzer import QueryAnalyzer

        _query_analyzer_instance = QueryAnalyzer()
    return _query_analyzer_instance


class HybridRetrievalMerger:
    """混合检索结果融合器 — 使用 RRF (Reciprocal Rank Fusion) 替代加权线性求和"""

    @staticmethod
    def merge_rrf(
        bm25_nodes: List[NodeWithScore],
        vector_nodes: List[NodeWithScore],
        k: int = 60,
        limit: int = 10,
    ) -> List[NodeWithScore]:
        """Reciprocal Rank Fusion — 基于排名融合，无需分数归一化"""

        node_map: Dict[str, NodeWithScore] = {}
        rrf_scores: Dict[str, float] = {}

        # BM25 排名贡献（按原始分数降序）
        sorted_bm25 = sorted(bm25_nodes, key=lambda n: n.score or 0, reverse=True)
        for rank, node in enumerate(sorted_bm25):
            nid = node.node.node_id or str(id(node))
            node_map[nid] = node
            rrf_scores[nid] = rrf_scores.get(nid, 0.0) + 1.0 / (k + rank + 1)

        # 向量排名贡献（按原始分数降序）
        sorted_vector = sorted(vector_nodes, key=lambda n: n.score or 0, reverse=True)
        for rank, node in enumerate(sorted_vector):
            nid = node.node.node_id or str(id(node))
            node_map[nid] = node
            rrf_scores[nid] = rrf_scores.get(nid, 0.0) + 1.0 / (k + rank + 1)

        # 排序并赋分
        ranked = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
        results = []
        for nid, score in ranked[:limit]:
            node = node_map[nid]
            node.score = score
            results.append(node)

        logger.info(
            f"RRF 融合完成：BM25={len(bm25_nodes)}个，向量={len(vector_nodes)}个，最终={len(results)}个"
        )
        if results:
            logger.info(
                f"RRF Top 3 分数：{[f'{n.score:.6f}' for n in results[:3]]}"
            )
        return results

    @staticmethod
    def get_dynamic_weights(
        query: str,
        query_analyzer=None,
        weight_config: Optional[Dict[str, Dict[str, float]]] = None,
        strategy: str = None,
    ) -> tuple[float, float]:
        """基于查询类型动态返回权重（适配中文场景）"""
        if strategy is None:
            strategy = settings.rag_weight_strategy

        if strategy == "fixed":
            bm25_weight = settings.rag_hybrid_bm25_weight
            return bm25_weight, 1 - bm25_weight

        if query_analyzer is None:
            query_analyzer = _get_default_analyzer()

        analysis = query_analyzer.analyze(query)

        if weight_config is None:
            weight_config = settings.rag_weight_by_query_type

        type_key = analysis.query_type.value
        weights = weight_config.get(type_key, weight_config["default"])

        bm25_weight = weights["bm25"]
        vector_weight = weights["vector"]

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
        """融合检索结果 — 内部委托给 RRF，保留签名兼容调用方"""
        if not bm25_nodes and not vector_nodes:
            return []

        return HybridRetrievalMerger.merge_rrf(bm25_nodes, vector_nodes, limit=limit)

    @staticmethod
    def merge_for_search(
        bm25_nodes: List[NodeWithScore],
        vector_nodes: List[NodeWithScore],
        bm25_weight: float = 0.7,
        vector_weight: float = 0.3,
        no_match_vector_penalty: float = 0.3,
        limit: int = 20,
    ) -> List[NodeWithScore]:
        """搜索页面融合 — 内部委托给 RRF，保留签名兼容调用方"""
        if not bm25_nodes and not vector_nodes:
            return []

        return HybridRetrievalMerger.merge_rrf(bm25_nodes, vector_nodes, limit=limit)
