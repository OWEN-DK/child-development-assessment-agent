"""集成测试：LazyGraphRAG 完整导入流水线

覆盖：实体提取 → 图构建 → 社区检测 → 层级树存储 → 遍历 → 上下文构建
使用 mock LLM 避免外部依赖。
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import networkx as nx
import pytest

from src.core.knowledge_qa.graph.builder import (
    assign_chunks_to_communities,
    build_graph,
    dendrogram_to_tree,
)
from src.core.knowledge_qa.graph.community import detect_communities
from src.core.knowledge_qa.graph.extractor import Entity, Relation
from src.core.knowledge_qa.graph.traversal import (
    TraversalHit,
    build_knowledge_context,
    explore_community_tree,
)


def _create_test_chunks(n: int = 20) -> list:
    """创建模拟的文档块（带 topic 标签）"""
    chunks = []
    topics = [
        ["前庭觉", "注意力", "感觉统合"],
        ["运动干预", "蹦床训练", "前庭刺激"],
        ["ADHD", "注意力缺陷", "执行功能"],
        ["感觉统合评估", "SIPT", "临床评估"],
        ["儿童发展", "里程碑", "3岁"],
        ["前庭核", "小脑", "脑区"],
        ["触觉防御", "感觉处理", "行为问题"],
        ["运动计划", "大运动", "精细运动"],
    ]
    for i in range(n):
        node = MagicMock()
        node.get_content.return_value = f"测试块内容 {i}: 关于儿童感觉统合发展的描述。"
        node.metadata = {"topics": json.dumps(topics[i % len(topics)])}
        chunks.append(node)
    return chunks


def _create_mock_entities_and_relations():
    """创建模拟的实体和关系（跳过 LLM 提取）"""
    entities = [
        Entity(name="前庭觉失调", entity_type="symptom_behavior", description="前庭系统功能异常", book_id="doc-uuid-001", chunk_ids=["c0", "c1"]),
        Entity(name="注意力不集中", entity_type="symptom_behavior", description="无法持续关注", book_id="doc-uuid-001", chunk_ids=["c2"]),
        Entity(name="蹦床训练", entity_type="intervention_method", description="刺激前庭觉的运动", book_id="doc-uuid-001", chunk_ids=["c3", "c4"]),
        Entity(name="执行功能", entity_type="development_concept", description="高级认知功能", book_id="doc-uuid-001", chunk_ids=["c5"]),
        Entity(name="感觉统合", entity_type="development_concept", description="多感官整合", book_id="doc-uuid-001", chunk_ids=["c6"]),
        Entity(name="ADHD", entity_type="clinical_population", description="注意力缺陷多动障碍", book_id="doc-uuid-001", chunk_ids=["c7"]),
        Entity(name="SIPT", entity_type="assessment_tool", description="感觉统合评估量表", book_id="doc-uuid-001", chunk_ids=["c8"]),
        Entity(name="触觉防御", entity_type="symptom_behavior", description="对触觉刺激过度敏感", book_id="doc-uuid-001", chunk_ids=["c9"]),
        Entity(name="运动计划", entity_type="intervention_method", description="系统性运动方案", book_id="doc-uuid-001", chunk_ids=["c10"]),
        Entity(name="小脑", entity_type="brain_region", description="协调运动和平衡", book_id="doc-uuid-001", chunk_ids=["c11"]),
    ]

    relations = [
        Relation(source="前庭觉失调", target="注意力不集中", relation_type="causes", description="前庭功能异常导致注意力问题"),
        Relation(source="蹦床训练", target="前庭觉失调", relation_type="treats", description="蹦床训练改善前庭功能"),
        Relation(source="ADHD", target="注意力不集中", relation_type="related_to", description="ADHD 核心症状"),
        Relation(source="SIPT", target="感觉统合", relation_type="assesses", description="评估感觉统合能力"),
        Relation(source="执行功能", target="注意力不集中", relation_type="related_to", description="执行功能影响注意力"),
        Relation(source="小脑", target="前庭觉失调", relation_type="related_to", description="小脑参与前庭信息处理"),
        Relation(source="触觉防御", target="感觉统合", relation_type="related_to", description="触觉防御是感觉统合问题"),
    ]

    return entities, relations


class MockCommunityRepo:
    """模拟 GraphCommunityRepository"""

    def __init__(self, nodes: list):
        self._nodes = {n["node_id"]: n for n in nodes}

    async def get_node(self, node_id: str):
        node_data = self._nodes.get(node_id)
        if not node_data:
            return None
        node = MagicMock()
        node.node_id = node_data["node_id"]
        node.parent_id = node_data.get("parent_id")
        node.is_leaf = node_data.get("is_leaf", False)
        node.label = node_data.get("label", "")
        node.entity_names = node_data.get("entity_names", [])
        node.chunk_ids = node_data.get("chunk_ids", [])
        return node

    async def get_children(self, parent_id: str):
        children = [n for n in self._nodes.values() if n.get("parent_id") == parent_id]
        result = []
        for c in children:
            node = MagicMock()
            node.node_id = c["node_id"]
            node.parent_id = c.get("parent_id")
            node.is_leaf = c.get("is_leaf", False)
            node.label = c.get("label", "")
            node.entity_names = c.get("entity_names", [])
            node.chunk_ids = c.get("chunk_ids", [])
            result.append(node)
        return result

    async def get_roots(self, scope="book", book_id=None):
        roots = [n for n in self._nodes.values() if n.get("parent_id") is None]
        return [await self.get_node(r["node_id"]) for r in roots]

    async def get_children_batch(self, parent_ids: list[str]) -> dict[str, list]:
        """批量查询多个父节点的子节点（模拟 get_children 的批量版本）"""
        result = {}
        for pid in parent_ids:
            result[pid] = await self.get_children(pid)
        return result

    async def batch_insert(self, nodes):
        return len(nodes)

    async def delete_by_book(self, book_id):
        return 0


class TestGraphPipelineIntegration:
    """完整导入流水线集成测试"""

    def test_extract_to_graph_to_tree(self):
        """从实体/关系到图构建到社区检测到层级树的完整流程"""
        entities, relations = _create_mock_entities_and_relations()

        # Step 1: 构建图
        G = build_graph(entities, relations)
        assert G.number_of_nodes() == 10
        assert G.number_of_edges() == 7

        # Step 2: 社区检测
        partition, dendrogram = detect_communities(G)
        assert len(partition) == 10
        community_count = len(set(partition.values()))
        assert community_count >= 2

        # Step 3: 层级树
        tree_nodes, tree_edges = dendrogram_to_tree(
            G=G, partition=partition, dendrogram=dendrogram, book_id="doc-uuid-001",
        )
        assert len(tree_nodes) >= 2

        leaves = [n for n in tree_nodes if n["is_leaf"]]
        assert len(leaves) >= 2
        assert all(len(n["entity_names"]) > 0 for n in leaves)

        # Step 4: 分配块
        tree_nodes = assign_chunks_to_communities(tree_nodes, entities)
        total_chunks = sum(len(n["chunk_ids"]) for n in leaves)
        assert total_chunks > 0

    def test_tree_has_valid_parent_child(self):
        """层级树的父子关系应完整一致"""
        entities, relations = _create_mock_entities_and_relations()
        G = build_graph(entities, relations)
        partition, dendrogram = detect_communities(G)
        tree_nodes, tree_edges = dendrogram_to_tree(G, partition, dendrogram, book_id="doc-uuid-001")

        node_ids = {n["node_id"] for n in tree_nodes}
        for edge in tree_edges:
            assert edge["parent"] in node_ids
            assert edge["child"] in node_ids

        # 所有非根节点应有父节点
        roots = [n for n in tree_nodes if n.get("parent_id") is None]
        assert len(roots) >= 1

    @pytest.mark.asyncio
    async def test_traversal_from_mock_tree(self):
        """从模拟社区树执行层级遍历"""
        # 构建一个 2 层树: root → [intermediate] → [leaf_0, leaf_1]
        tree_nodes = [
            {"node_id": "root", "parent_id": None, "is_leaf": False, "label": "根节点", "entity_names": [], "chunk_ids": []},
            {"node_id": "leaf_0", "parent_id": "root", "is_leaf": True, "label": "[症状] 前庭觉", "entity_names": ["前庭觉失调", "注意力不集中"], "chunk_ids": ["c1", "c2"]},
            {"node_id": "leaf_1", "parent_id": "root", "is_leaf": True, "label": "[干预] 运动训练", "entity_names": ["蹦床训练", "运动计划"], "chunk_ids": ["c3", "c4"]},
        ]
        repo = MockCommunityRepo(tree_nodes)

        # Mock LLM 相关性判定：全部判定为相关
        with patch("src.core.knowledge_qa.graph.traversal._check_relevance", new_callable=AsyncMock) as mock_relevance:
            mock_relevance.return_value = True

            hits = await explore_community_tree(
                question="4岁男孩注意力不集中",
                root_id="root",
                community_repo=repo,
            )

            assert len(hits) == 2
            assert all(isinstance(h, TraversalHit) for h in hits)
            total_chunks = sum(len(h.chunk_ids) for h in hits)
            assert total_chunks == 4

    @pytest.mark.asyncio
    async def test_traversal_with_pruning(self):
        """层级遍历应剪掉不相关分支"""
        tree_nodes = [
            {"node_id": "root", "parent_id": None, "is_leaf": False, "label": "根", "entity_names": [], "chunk_ids": []},
            {"node_id": "leaf_relevant", "parent_id": "root", "is_leaf": True, "label": "[症状] 注意力", "entity_names": ["注意力不集中"], "chunk_ids": ["c1"]},
            {"node_id": "leaf_irrelevant", "parent_id": "root", "is_leaf": True, "label": "[评估] 量表", "entity_names": ["SIPT"], "chunk_ids": ["c2"]},
        ]
        repo = MockCommunityRepo(tree_nodes)

        # Mock: 只有注意力相关的社区判定为相关
        async def selective_relevance(question, community, model_name="qwen-turbo"):
            return "注意力" in community.get("label", "")

        with patch("src.core.knowledge_qa.graph.traversal._check_relevance", side_effect=selective_relevance):
            hits = await explore_community_tree(
                question="注意力不集中",
                root_id="root",
                community_repo=repo,
            )

            assert len(hits) == 1
            assert hits[0].node_id == "leaf_relevant"

    @pytest.mark.asyncio
    async def test_end_to_end_context_building(self):
        """从实体到知识上下文的完整端到端流程"""
        entities, relations = _create_mock_entities_and_relations()

        # 构建图 + 社区检测
        G = build_graph(entities, relations)
        partition, dendrogram = detect_communities(G)
        tree_nodes, _ = dendrogram_to_tree(G, partition, dendrogram, book_id="doc-uuid-001")
        tree_nodes = assign_chunks_to_communities(tree_nodes, entities)

        # 提取叶子社区作为 hits
        hits = [
            TraversalHit(
                node_id=n["node_id"],
                label=n.get("label", ""),
                entity_names=n.get("entity_names", []),
                chunk_ids=n.get("chunk_ids", []),
            )
            for n in tree_nodes if n["is_leaf"]
        ]

        # 构建上下文
        async def mock_loader(chunk_ids):
            return {cid: f"这是关于 {cid} 的测试文本内容，包含儿童发展的相关信息。" for cid in chunk_ids}

        context = await build_knowledge_context(
            question="4岁男孩注意力不集中如何改善",
            hits=hits,
            chunk_loader=mock_loader,
        )

        assert len(context) > 0
        assert "知识上下文" in context
        assert "社区" in context

    @pytest.mark.asyncio
    async def test_token_budget_limits_traversal(self):
        """token 预算应限制遍历结果数量"""
        # 大量叶子社区
        tree_nodes = [
            {"node_id": "root", "parent_id": None, "is_leaf": False, "label": "根", "entity_names": [], "chunk_ids": []},
        ]
        for i in range(10):
            tree_nodes.append({
                "node_id": f"leaf_{i}",
                "parent_id": "root",
                "is_leaf": True,
                "label": f"社区{i}",
                "entity_names": [f"概念{i}"],
                "chunk_ids": [f"c_{i}_1", f"c_{i}_2", f"c_{i}_3"],  # 每个 3 块 * 500 = 1500 tokens
            })
        repo = MockCommunityRepo(tree_nodes)

        with patch("src.core.knowledge_qa.graph.traversal._check_relevance", new_callable=AsyncMock) as mock_relevance:
            mock_relevance.return_value = True

            # 预算 3000 tokens ≈ 6 块
            hits = await explore_community_tree(
                question="测试",
                root_id="root",
                community_repo=repo,
                max_tokens=3000,
            )

            total_chunks = sum(len(h.chunk_ids) for h in hits)
            assert total_chunks <= 8  # 允许少量超预算（500/块 估算）
