"""社区检测 — Louvain 层级聚类

对构建好的知识图谱执行 Louvain 社区检测，返回层级树（dendrogram）。
"""

import logging
from typing import Any

import community as community_louvain
import networkx as nx

logger = logging.getLogger(__name__)


def detect_communities(G: nx.Graph) -> tuple[dict[str, int], list]:
    """Louvain 社区检测 + 层级合并序列。

    Args:
        G: 知识图谱（无向图，边有权重）

    Returns:
        (partition, dendrogram):
          - partition: {node_name: community_id}
          - dendrogram: multi-level 合并序列
    """
    if G.number_of_nodes() == 0:
        logger.warning("空图，跳过社区检测")
        return {}, []

    if G.number_of_nodes() < 3:
        # 节点太少，每个节点自成一个社区
        logger.info(f"节点数 {G.number_of_nodes()} < 3，每个节点自成社区")
        partition = {n: i for i, n in enumerate(G.nodes())}
        return partition, []

    try:
        partition = community_louvain.best_partition(
            G, weight="weight", random_state=42
        )
        dendrogram = community_louvain.generate_dendrogram(
            G, weight="weight", random_state=42
        )

        num_communities = len(set(partition.values()))
        num_levels = len(dendrogram)
        logger.info(
            f"社区检测完成: {num_communities} 个社区, {num_levels} 层合并"
        )
        return partition, dendrogram

    except Exception as e:
        logger.exception(f"社区检测失败: {e}")
        # 降级：每个节点自成社区
        partition = {n: i for i, n in enumerate(G.nodes())}
        return partition, []
