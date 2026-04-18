"""父子块分块策略模块

实现父子块关联分块策略，大块提供完整上下文，小块用于精确检索。
"""

import re
from typing import List, Optional

from llama_index.core.schema import Document, Node

from src.utils.logger import logger


def hierarchical_chunking(
    documents: List[Document],
    parent_chunk_size: int = 1500,
    child_chunk_size: int = 400,
    file_hash: Optional[str] = None,
) -> List[Node]:
    """父子块关联分块策略

    - 大块（parent）：提供完整上下文（1000-2000 tokens）
    - 小块（child）：用于精确检索（200-400 tokens）
    - 元数据关联：child 块记录 parent_id

    业界最佳实践：
    - 语义边界优先：使用标题层级（H1/H2/H3）、段落边界作为首要分割点
    - 结构感知：Markdown/HTML 标签、列表、代码块保持完整
    - 动态分块大小：根据内容密度自动调整，避免切断语义单元

    Args:
        documents: 文档列表
        parent_chunk_size: 父块大小（字符数）
        child_chunk_size: 子块大小（字符数）
        file_hash: 文档哈希值

    Returns:
        分块后的节点列表（包含父子块）
    """
    all_nodes = []

    for doc in documents:
        sections = re.split(r"\n(?=##?\s+)", doc.text)

        parent_nodes = []
        child_nodes = []

        for section_idx, section in enumerate(sections):
            if not section.strip():
                continue

            parent_node = Node(text=section, metadata=doc.metadata.copy())
            parent_node.metadata["chunk_type"] = "parent"
            parent_node.metadata["chunk_size"] = "large"
            parent_nodes.append(parent_node)

            paragraphs = section.split("\n\n")

            current_child_text = ""
            child_count = 0

            for para in paragraphs:
                if not para.strip():
                    continue

                if len(current_child_text) + len(para) > child_chunk_size * 1.5:
                    if current_child_text.strip():
                        child_node = Node(
                            text=current_child_text.strip(),
                            metadata={
                                **doc.metadata,
                                "parent_id": parent_node.node_id,
                                "chunk_type": "child",
                                "chunk_size": "small",
                                "child_index": child_count,
                            },
                        )
                        child_nodes.append(child_node)
                        child_count += 1

                    current_child_text = para
                else:
                    current_child_text += "\n\n" + para if current_child_text else para

            if current_child_text.strip():
                child_node = Node(
                    text=current_child_text.strip(),
                    metadata={
                        **doc.metadata,
                        "parent_id": parent_node.node_id,
                        "chunk_type": "child",
                        "chunk_size": "small",
                        "child_index": child_count,
                    },
                )
                child_nodes.append(child_node)

        for parent_node in parent_nodes:
            _attach_file_hash(parent_node, file_hash)
            all_nodes.append(parent_node)

        for child_node in child_nodes:
            _attach_file_hash(child_node, file_hash)
            all_nodes.append(child_node)

    logger.info(
        f"Hierarchical chunking completed: {len(documents)} documents -> "
        f"{len(all_nodes)} nodes (including parent-child relationships)"
    )

    return all_nodes


def _attach_file_hash(node: Node, file_hash: Optional[str]) -> None:
    """为节点附加文件哈希和源关联"""
    if file_hash:
        from llama_index.core.schema import NodeRelationship, RelatedNodeInfo

        node.metadata["file_hash"] = file_hash
        node.relationships[NodeRelationship.SOURCE] = RelatedNodeInfo(
            node_id=file_hash
        )
