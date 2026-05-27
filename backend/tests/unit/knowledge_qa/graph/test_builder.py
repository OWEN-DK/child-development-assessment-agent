"""单元测试：知识图谱图构建器 (builder.py)

覆盖：图构建、层级树构建、社区标签生成、块分配
"""

import pytest

from src.core.knowledge_qa.graph.builder import (
    assign_chunks_to_communities,
    build_graph,
    dendrogram_to_tree,
)
from src.core.knowledge_qa.graph.extractor import Entity, Relation


def _make_entities() -> list[Entity]:
    """创建测试用实体集"""
    return [
        Entity(name="前庭觉失调", entity_type="symptom_behavior", description="前庭系统功能异常", book_id="1", chunk_ids=["c1", "c2"]),
        Entity(name="注意力不集中", entity_type="symptom_behavior", description="无法持续关注任务", book_id="1", chunk_ids=["c3"]),
        Entity(name="蹦床训练", entity_type="intervention_method", description="通过蹦床刺激前庭觉", book_id="1", chunk_ids=["c4"]),
        Entity(name="执行功能", entity_type="development_concept", description="大脑高级认知功能", book_id="1", chunk_ids=["c5"]),
        Entity(name="感觉统合", entity_type="development_concept", description="多感官信息整合能力", book_id="1", chunk_ids=["c6"]),
    ]


def _make_relations(entities: list[Entity]) -> list[Relation]:
    """创建测试用关系"""
    return [
        Relation(source="前庭觉失调", target="注意力不集中", relation_type="causes", description="前庭功能异常导致注意力问题"),
        Relation(source="蹦床训练", target="前庭觉失调", relation_type="treats", description="蹦床训练改善前庭功能"),
        Relation(source="执行功能", target="注意力不集中", relation_type="related_to", description="执行功能影响注意力"),
    ]


class TestBuildGraph:
    """图构建测试"""

    def test_build_graph_basic(self):
        """实体和关系应正确构建为 networkx 图"""
        entities = _make_entities()
        relations = _make_relations(entities)
        G = build_graph(entities, relations)

        assert G.number_of_nodes() == 5
        assert G.number_of_edges() == 3
        assert G.has_edge("前庭觉失调", "注意力不集中")
        assert G.has_edge("蹦床训练", "前庭觉失调")

    def test_build_graph_node_attributes(self):
        """节点应包含 type, description, aliases, book_id"""
        entities = _make_entities()
        relations = _make_relations(entities)
        G = build_graph(entities, relations)

        node = G.nodes["前庭觉失调"]
        assert node["type"] == "symptom_behavior"
        assert node["description"] == "前庭系统功能异常"
        assert node["book_id"] == "1"

    def test_build_graph_edge_attributes(self):
        """边应包含 type, description, weight"""
        entities = _make_entities()
        relations = _make_relations(entities)
        G = build_graph(entities, relations)

        edge = G.edges["前庭觉失调", "注意力不集中"]
        assert edge["type"] == "causes"
        assert edge["weight"] == 1.0

    def test_build_graph_empty(self):
        """空输入应返回空图"""
        G = build_graph([], [])
        assert G.number_of_nodes() == 0
        assert G.number_of_edges() == 0

    def test_build_graph_no_relations(self):
        """仅有实体无关系时，应只有节点无边"""
        entities = _make_entities()
        G = build_graph(entities, [])

        assert G.number_of_nodes() == 5
        assert G.number_of_edges() == 0

    def test_build_graph_invalid_relation_skipped(self):
        """关系引用不存在的实体时，边应被跳过"""
        entities = _make_entities()[:2]
        relations = [
            Relation(source="前庭觉失调", target="不存在的实体", relation_type="causes", description="测试"),
        ]
        G = build_graph(entities, relations)

        assert G.number_of_nodes() == 2
        assert G.number_of_edges() == 0


class TestDendrogramToTree:
    """层级树构建测试"""

    def test_basic_tree_structure(self):
        """基本的 Louvain 输出应转换为正确的层级树"""
        entities = _make_entities()
        relations = _make_relations(entities)
        G = build_graph(entities, relations)

        # 模拟 Louvain partition（2 个社区）
        partition = {
            "前庭觉失调": 0,
            "注意力不集中": 0,
            "蹦床训练": 0,
            "执行功能": 1,
            "感觉统合": 1,
        }

        # 模拟 dendrogram（一层合并）
        dendrogram = [[[0, 1]]]

        tree_nodes, tree_edges = dendrogram_to_tree(G, partition, dendrogram, book_id="doc-001")

        # 2 叶子 + 1 中间 = 3 节点（dendrogram 合并了 2 个社区，单根不需要虚拟根）
        assert len(tree_nodes) == 3
        leaves = [n for n in tree_nodes if n["is_leaf"]]
        assert len(leaves) == 2
        assert any("前庭觉失调" in n["entity_names"] for n in leaves)
        assert any("执行功能" in n["entity_names"] for n in leaves)

    def test_single_community(self):
        """只有一个社区时，应创建单个节点"""
        entities = _make_entities()[:2]
        G = build_graph(entities, [])

        partition = {"前庭觉失调": 0, "注意力不集中": 0}
        dendrogram = []

        tree_nodes, tree_edges = dendrogram_to_tree(G, partition, dendrogram, book_id="doc-001")

        leaves = [n for n in tree_nodes if n["is_leaf"]]
        assert len(leaves) == 1
        assert len(leaves[0]["entity_names"]) == 2

    def test_tree_node_ids_prefixed(self):
        """节点 ID 应包含 book_id 前缀"""
        entities = _make_entities()[:2]
        G = build_graph(entities, [])

        partition = {"前庭觉失调": 0, "注意力不集中": 0}
        dendrogram = []

        tree_nodes, _ = dendrogram_to_tree(G, partition, dendrogram, book_id="doc-001")

        for node in tree_nodes:
            assert node["node_id"].startswith("book_doc-001_")

    def test_parent_child_edges(self):
        """层级树的父子关系边应正确"""
        entities = _make_entities()
        relations = _make_relations(entities)
        G = build_graph(entities, relations)

        partition = {
            "前庭觉失调": 0,
            "注意力不集中": 0,
            "蹦床训练": 1,
            "执行功能": 1,
            "感觉统合": 1,
        }
        dendrogram = [[[0, 1]]]

        tree_nodes, tree_edges = dendrogram_to_tree(G, partition, dendrogram, book_id="doc-001")

        # 每条边应有 parent 和 child
        for edge in tree_edges:
            assert "parent" in edge
            assert "child" in edge
            # parent 和 child 节点都应存在
            node_ids = {n["node_id"] for n in tree_nodes}
            assert edge["parent"] in node_ids
            assert edge["child"] in node_ids


class TestAssignChunksToCommunities:
    """块分配测试"""

    def test_chunks_assigned_to_leaves(self):
        """实体的 chunk_ids 应分配到对应的叶子社区"""
        entities = _make_entities()
        tree_nodes = [
            {
                "node_id": "leaf_0",
                "is_leaf": True,
                "entity_names": ["前庭觉失调", "注意力不集中"],
                "chunk_ids": [],
            },
            {
                "node_id": "leaf_1",
                "is_leaf": True,
                "entity_names": ["执行功能", "感觉统合"],
                "chunk_ids": [],
            },
        ]

        result = assign_chunks_to_communities(tree_nodes, entities)

        leaf_0 = next(n for n in result if n["node_id"] == "leaf_0")
        assert "c1" in leaf_0["chunk_ids"]
        assert "c2" in leaf_0["chunk_ids"]
        assert "c3" in leaf_0["chunk_ids"]

        leaf_1 = next(n for n in result if n["node_id"] == "leaf_1")
        assert "c5" in leaf_1["chunk_ids"]
        assert "c6" in leaf_1["chunk_ids"]

    def test_chunk_dedup(self):
        """同一叶子社区内的重复 chunk_id 应去重"""
        entities = [
            Entity(name="A", entity_type="symptom_behavior", description="", book_id="1", chunk_ids=["c1", "c1"]),
            Entity(name="B", entity_type="symptom_behavior", description="", book_id="1", chunk_ids=["c1"]),
        ]
        tree_nodes = [
            {"node_id": "leaf_0", "is_leaf": True, "entity_names": ["A", "B"], "chunk_ids": []},
        ]

        result = assign_chunks_to_communities(tree_nodes, entities)
        assert result[0]["chunk_ids"] == ["c1"]

    def test_non_leaf_not_modified(self):
        """非叶子节点不应被修改"""
        entities = _make_entities()[:1]
        tree_nodes = [
            {"node_id": "root", "is_leaf": False, "entity_names": [], "chunk_ids": []},
        ]

        result = assign_chunks_to_communities(tree_nodes, entities)
        assert result[0]["chunk_ids"] == []
