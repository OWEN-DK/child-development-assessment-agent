"""LazyGraphRAG 图核心模块

索引时：实体提取 → 图构建 → 社区检测 → 层级树存储（零 LLM 摘要）
查询时：向量种子 → 层级遍历 → 加载相关块 → 构建知识上下文
"""

from src.core.knowledge_qa.graph.extractor import (
    Entity,
    Relation,
    extract_entities_relations,
)
from src.core.knowledge_qa.graph.builder import (
    assign_chunks_to_communities,
    build_graph,
    dendrogram_to_tree,
    store_community_tree,
)
from src.core.knowledge_qa.graph.community import (
    detect_communities,
)
from src.core.knowledge_qa.graph.traversal import (
    TraversalHit,
    build_knowledge_context,
    explore_community_tree,
    find_lowest_common_ancestor,
)
from src.core.knowledge_qa.graph.pipeline import build_graph_for_book
from src.core.knowledge_qa.graph.global_rebuild import rebuild_global_graph

# 重新导出旧 graph.py（已重命名为 _assembly.py）中的图组装函数和单例
from src.core.knowledge_qa._assembly import (
    create_knowledge_qa_graph,
    knowledge_qa_graph,
)

__all__ = [
    # Extractor
    "Entity",
    "Relation",
    "extract_entities_relations",
    # Builder
    "build_graph",
    "dendrogram_to_tree",
    "assign_chunks_to_communities",
    "store_community_tree",
    # Community
    "detect_communities",
    # Traversal
    "TraversalHit",
    "explore_community_tree",
    "find_lowest_common_ancestor",
    "build_knowledge_context",
    # Pipeline
    "build_graph_for_book",
    # Global rebuild
    "rebuild_global_graph",
    # Graph assembly (legacy)
    "create_knowledge_qa_graph",
    "knowledge_qa_graph",
]
