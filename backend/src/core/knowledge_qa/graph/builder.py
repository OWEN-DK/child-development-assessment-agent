"""知识图谱构建器

将提取的实体和关系构建为 networkx 图，执行 Louvain 社区检测并存储层级树。
"""

import logging
import uuid
from typing import Any, List, Tuple

import networkx as nx

from src.core.knowledge_qa.graph.extractor import Entity, Relation

logger = logging.getLogger(__name__)


def build_graph(
    entities: list[Entity],
    relations: list[Relation],
) -> nx.Graph:
    """构建知识图谱：实体为节点，关系为边。"""
    G = nx.Graph()

    for e in entities:
        G.add_node(
            e.name,
            type=e.entity_type,
            description=e.description,
            aliases=e.aliases,
            book_id=e.book_id,
        )

    for r in relations:
        if r.source in G and r.target in G:
            G.add_edge(
                r.source,
                r.target,
                type=r.relation_type,
                description=r.description,
                weight=r.confidence,
            )

    logger.info(f"图构建完成: {G.number_of_nodes()} 节点, {G.number_of_edges()} 边")
    return G


def dendrogram_to_tree(
    G: nx.Graph,
    partition: dict[str, int],
    dendrogram: list[dict],
    book_id: str,
    scope: str = "book",
) -> tuple[list[dict], list[dict]]:
    """将 Louvain 层级合并序列转换为社区树结构。

    Args:
        G: networkx 图
        partition: Louvain best_partition 结果 {node_name: community_id}
        dendrogram: generate_dendrogram 结果 [level0_dict, level1_dict, ...]
            level0_dict: {node_id: community_id_at_level_0}
            level1_dict: {community_id_at_level_0: community_id_at_level_1}
        book_id: 书籍 ID（scope=global 时为空字符串）
        scope: 'book' 或 'global'

    Returns:
        (tree_nodes, tree_edges): 层级树节点和父子关系边
    """
    from collections import defaultdict

    node_map: dict[int, str] = {}
    tree_nodes: list[dict] = []
    tree_edges: list[dict] = []

    prefix = "global" if scope == "global" else f"book_{book_id}"

    # Step 1: 用 partition 创建叶子社区节点
    community_ids = sorted(set(partition.values()))
    entities_by_community: dict[int, list[str]] = {}
    for node_name, comm_id in partition.items():
        entities_by_community.setdefault(comm_id, []).append(node_name)

    for comm_id in community_ids:
        node_id = f"{prefix}_leaf_{comm_id}"
        entity_names = entities_by_community.get(comm_id, [])
        label = _generate_community_label(entity_names, G, scope=scope)
        tree_nodes.append({
            "node_id": node_id,
            "parent_id": None,
            "level": 0,
            "is_leaf": True,
            "entity_names": entity_names,
            "label": label,
            "chunk_ids": [],
        })
        node_map[comm_id] = node_id

    # Step 2: 逐层处理 dendrogram，将子社区合并为父节点
    # dendrogram[0] 已被 partition 覆盖（叶子层），从 dendrogram[1] 开始
    next_comm_id = max(community_ids) + 1 if community_ids else 0

    for level_idx in range(1, len(dendrogram)):
        level = level_idx
        level_dict = dendrogram[level_idx]

        # 按父社区 ID 分组：合并到同一父社区的子节点互为兄弟
        parent_groups: dict[int, list[int]] = defaultdict(list)
        for child_id, parent_id in level_dict.items():
            parent_groups[parent_id].append(child_id)

        for parent_id, child_ids in parent_groups.items():
            parent_id_str = f"{prefix}_lvl{level}_p{parent_id}"

            # 收集所有子节点的实体名
            combined: list[str] = []
            valid_child_ids: list[int] = []
            for cid in child_ids:
                child_node_id = node_map.get(cid)
                if child_node_id is None:
                    continue
                valid_child_ids.append(cid)
                for n in tree_nodes:
                    if n["node_id"] == child_node_id:
                        combined.extend(n.get("entity_names", []))
            combined = list(dict.fromkeys(combined))

            if not valid_child_ids:
                continue

            label = _generate_community_label(combined, G, scope=scope)
            tree_nodes.append({
                "node_id": parent_id_str,
                "parent_id": None,
                "level": level,
                "is_leaf": False,
                "entity_names": combined,
                "label": label,
                "chunk_ids": [],
            })

            for cid in valid_child_ids:
                child_node_id = node_map[cid]
                tree_edges.append({"parent": parent_id_str, "child": child_node_id})
                for n in tree_nodes:
                    if n["node_id"] == child_node_id:
                        n["parent_id"] = parent_id_str

            node_map[next_comm_id] = parent_id_str
            next_comm_id += 1

    # Step 3: 虚拟根节点（多个根时合并）
    roots = [n for n in tree_nodes if n["parent_id"] is None]
    if len(roots) > 1:
        root_id = f"{prefix}_root"
        root_label = "全局知识图谱根节点" if scope == "global" else f"书籍 {book_id} 根节点"
        tree_nodes.append({
            "node_id": root_id,
            "parent_id": None,
            "level": max(n["level"] for n in tree_nodes) + 1 if tree_nodes else 1,
            "is_leaf": False,
            "entity_names": [],
            "label": root_label,
            "chunk_ids": [],
        })
        for r in roots:
            r["parent_id"] = root_id
            tree_edges.append({"parent": root_id, "child": r["node_id"]})

    logger.info(
        f"层级树构建: {len(tree_nodes)} 节点, {len(tree_edges)} 边, "
        f"{sum(1 for n in tree_nodes if n['is_leaf'])} 叶子"
    )
    return tree_nodes, tree_edges


def _generate_community_label(entity_names: list[str], G: nx.Graph, scope: str = "book") -> str:
    """生成社区标签：取度数最高的 top 实体 + 最常见实体类型"""
    if not entity_names:
        return "空社区"

    top_n = 5 if scope == "global" else 3

    # Top-N 高度数实体
    degrees = {n: G.degree(n) for n in entity_names if n in G}
    sorted_entities = sorted(degrees.keys(), key=lambda n: degrees[n], reverse=True)
    top = sorted_entities[:top_n]

    # 最常见实体类型
    type_counts: dict[str, int] = {}
    book_ids: set[str] = set()
    for n in entity_names:
        if n in G:
            t = G.nodes[n].get("type", "unknown")
            type_counts[t] = type_counts.get(t, 0) + 1
            bid = G.nodes[n].get("book_id", "")
            if bid:
                book_ids.add(bid)
    dominant_type = max(type_counts, key=type_counts.get) if type_counts else ""

    label = " + ".join(top)
    if dominant_type:
        type_cn = {
            "development_concept": "发展",
            "symptom_behavior": "症状",
            "intervention_method": "干预",
            "assessment_tool": "评估",
            "brain_region": "脑区",
            "age_milestone": "里程碑",
            "clinical_population": "人群",
        }.get(dominant_type, dominant_type)
        label = f"[{type_cn}] {label}"

    # 全局模式：显示涉及书籍数量
    if scope == "global" and book_ids:
        label += f" (涉及 {len(book_ids)} 本书)"

    return label[:500]


def assign_chunks_to_communities(
    tree_nodes: list[dict],
    entities: list[Entity],
) -> list[dict]:
    """将每个实体的 chunk_ids 分配到所属的叶子社区。

    修改 tree_nodes 中的叶子节点的 chunk_ids 字段。
    """
    # 构建实体名到 chunk_ids 的映射
    entity_chunks: dict[str, list[str]] = {}
    for e in entities:
        if e.chunk_ids:
            entity_chunks.setdefault(e.name, []).extend(e.chunk_ids)

    for node in tree_nodes:
        if node["is_leaf"]:
            chunk_ids = []
            for ename in node.get("entity_names", []):
                chunk_ids.extend(entity_chunks.get(ename, []))
            node["chunk_ids"] = list(dict.fromkeys(chunk_ids))  # 去重

    return tree_nodes


async def store_community_tree(
    book_id: str,
    tree_nodes: list[dict],
    tree_edges: list[dict],
    community_repo: Any,
    scope: str = "book",
) -> int:
    """将层级社区树写入 MySQL。

    Args:
        book_id: 书籍 ID（scope=global 时传空字符串）
        tree_nodes: 层级树节点列表
        tree_edges: 父子关系边列表
        http_client: RagHttpClient 或 HttpGraphAdapter 实例
        scope: 'book' 或 'global'

    Returns:
        写入的节点总数
    """
    from src.models.graph import CommunityScope, GraphCommunityNode

    # 清理旧数据
    if scope == "global":
        await community_repo.delete_by_scope("global")
    else:
        await community_repo.delete_by_book(book_id)

    # 建立 parent_id 映射
    node_parents: dict[str, str | None] = {n["node_id"]: n.get("parent_id") for n in tree_nodes}
    for edge in tree_edges:
        node_parents[edge["child"]] = edge["parent"]

    comm_scope = CommunityScope.GLOBAL if scope == "global" else CommunityScope.BOOK
    effective_book_id = None if scope == "global" else book_id

    # 构建 ORM 对象并批量写入
    orm_nodes = []
    for n in tree_nodes:
        orm_nodes.append(GraphCommunityNode(
            node_id=n["node_id"],
            parent_id=node_parents.get(n["node_id"]),
            level=n.get("level", 0),
            scope=comm_scope,
            book_id=effective_book_id,
            label=n.get("label", ""),
            entity_names=n.get("entity_names", []),
            chunk_ids=n.get("chunk_ids", []),
            is_leaf=n.get("is_leaf", False),
        ))

    count = await community_repo.batch_insert(orm_nodes)
    logger.info(f"社区树存储完成: {count} 个节点 (scope={scope}, book_id={effective_book_id})")
    return count
