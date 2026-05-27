"""单元测试：社区检测 (community.py)

覆盖：Louvain 社区检测、边界情况
"""

import networkx as nx
import pytest

from src.core.knowledge_qa.graph.community import detect_communities


class TestDetectCommunities:
    """社区检测测试"""

    def test_karate_club(self):
        """用 Zachary karate club 标准图验证 Louvain 检测"""
        G = nx.karate_club_graph()
        partition, dendrogram = detect_communities(G)

        assert len(partition) == 34  # 每个节点都有分区
        assert len(set(partition.values())) >= 2  # 至少 2 个社区

    def test_basic_community_detection(self):
        """5 节点图应至少检测出 1 个社区"""
        G = nx.Graph()
        G.add_edges_from([
            ("A", "B"), ("B", "C"), ("C", "D"), ("D", "E"),
        ])
        partition, dendrogram = detect_communities(G)

        assert len(partition) == 5
        assert len(set(partition.values())) >= 1

    def test_two_clear_clusters(self):
        """两个明显分离的簇应被检测为不同社区"""
        G = nx.Graph()
        # 簇 1: 紧密连接
        G.add_edges_from([("A", "B"), ("B", "C"), ("A", "C")])
        # 簇 2: 紧密连接
        G.add_edges_from([("D", "E"), ("E", "F"), ("D", "F")])
        # 单条弱连接
        G.add_edge("C", "D")

        partition, dendrogram = detect_communities(G)

        assert len(partition) == 6
        communities = set(partition.values())
        assert len(communities) >= 2  # 至少 2 个社区
        # A, B, C 应在同一社区，D, E, F 在另一社区
        assert partition["A"] == partition["B"] == partition["C"]
        assert partition["D"] == partition["E"] == partition["F"]
        assert partition["A"] != partition["D"]

    def test_empty_graph(self):
        """空图不应异常"""
        G = nx.Graph()
        partition, dendrogram = detect_communities(G)

        assert len(partition) == 0

    def test_single_node(self):
        """单节点图应返回空（节点数 < 3 时回退）"""
        G = nx.Graph()
        G.add_node("A")

        partition, dendrogram = detect_communities(G)

        # 回退模式：所有节点在社区 0
        assert len(partition) == 1

    def test_two_nodes(self):
        """两节点图应返回回退分区"""
        G = nx.Graph()
        G.add_edge("A", "B")

        partition, dendrogram = detect_communities(G)

        assert len(partition) == 2

    def test_partition_values_are_integers(self):
        """分区值应为整数"""
        G = nx.karate_club_graph()
        partition, _ = detect_communities(G)

        for node, community_id in partition.items():
            assert isinstance(community_id, int)
