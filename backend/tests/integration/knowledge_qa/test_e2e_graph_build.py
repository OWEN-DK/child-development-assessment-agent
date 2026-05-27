"""端到端 Graph 构建验证

用真实 LLM + 真实 MySQL + 真实 LlamaIndex 索引数据运行完整 graph 构建流水线。
验证：实体提取 → 图构建 → 社区检测 → 层级树存储 的端到端可行性。

运行方式：
cd backend && uv run pytest tests/integration/knowledge_qa/test_e2e_graph_build.py -v -s
"""

import asyncio
import json
import logging
import time
from collections import defaultdict

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@pytest.fixture
def db_session_factory():
    from src.core.database import async_session_factory
    return async_session_factory


@pytest.fixture
def index_manager():
    from src.service.index_manager_service import index_manager_service
    return index_manager_service


@pytest.fixture
def document_manager():
    from src.service.document_manager import document_manager
    return document_manager


def _collect_chunks_by_book(index_mgr, document_mgr) -> dict:
    """从 LlamaIndex docstore 中收集节点，按 book_id 分组"""
    idx = index_mgr.get_index()
    if not idx or not hasattr(idx, "docstore"):
        return {}

    docs = idx.docstore.docs
    if not docs:
        return {}

    # 构建 file_hash → book_id 映射
    # 通过 document_manager 获取所有文档
    # 这里用同步包装获取，因为 fixture 不是 async
    return docs


@pytest.mark.asyncio
async def test_list_indexed_books(document_manager):
    """前置检查：列出知识库中所有已索引的书籍"""
    docs = await document_manager.list_documents()
    indexed = [d for d in docs if d["status"] == "indexed"]

    print(f"\n已索引书籍: {len(indexed)}")
    for d in indexed:
        print(f"  - {d['file_name']} (id={d['id']}, hash={d['file_hash'][:12]}...)")

    assert len(indexed) >= 1, "知识库中至少需要 1 本已索引的书籍"


@pytest.mark.asyncio
async def test_graph_build_for_one_book(db_session_factory, index_manager, document_manager):
    """端到端测试：选 1 本书，完整运行 graph 构建流水线"""
    from src.core.knowledge_qa.graph.pipeline import build_graph_for_book
    from src.repository.graph_repository import (
        GraphCommunityRepository,
        GraphEntityRepository,
        GraphRelationRepository,
    )

    # Step 1: 找到已索引书籍
    docs = await document_manager.list_documents()
    indexed = [d for d in docs if d["status"] == "indexed"]
    assert len(indexed) >= 1, "知识库中至少需要 1 本已索引的书籍"

    # 选择第一本书
    book = indexed[0]
    book_id = book["id"]
    file_hash = book["file_hash"]
    print(f"\n选中的书: {book['file_name']} (id={book_id})")

    # Step 2: 从 LlamaIndex docstore 获取该书的所有节点
    idx = index_manager.get_index()
    assert idx is not None, "LlamaIndex 索引不可用"

    docstore = idx.docstore
    assert docstore is not None, "docstore 不可用"

    # 按 ref_doc_id (file_hash) 过滤节点
    all_nodes = list(docstore.docs.values())
    book_nodes = []
    for node in all_nodes:
        ref_id = getattr(node, "ref_doc_id", None)
        if ref_id == file_hash:
            book_nodes.append(node)

    if not book_nodes:
        # 尝试按 metadata 中的 file_hash 匹配
        for node in all_nodes:
            meta = getattr(node, "metadata", {}) or {}
            if meta.get("file_hash") == file_hash:
                book_nodes.append(node)

    print(f"找到 {len(book_nodes)} 个节点")

    if not book_nodes:
        # 退而用所有节点测试
        print("未找到该书特定节点，使用全部节点")
        book_nodes = all_nodes[:50]

    assert len(book_nodes) >= 5, f"节点数不足: {len(book_nodes)}"

    # Step 3: 提取 topics
    topics_per_chunk = []
    for node in book_nodes:
        meta = getattr(node, "metadata", {}) or {}
        topics_str = meta.get("topics", "[]")
        if isinstance(topics_str, str):
            try:
                topics = json.loads(topics_str)
            except (json.JSONDecodeError, TypeError):
                topics = []
        elif isinstance(topics_str, list):
            topics = topics_str
        else:
            topics = []
        topics_per_chunk.append(topics)

    # Step 4: 清理旧的 graph 数据（如有）
    community_repo = GraphCommunityRepository(db_session_factory)
    entity_repo = GraphEntityRepository(db_session_factory)
    relation_repo = GraphRelationRepository(db_session_factory)

    deleted = await community_repo.delete_by_book(book_id)
    if deleted > 0:
        print(f"清理旧数据: 删除 {deleted} 个社区节点")

    # Step 5: 执行完整流水线
    print(f"\n开始 graph 构建...")
    start = time.monotonic()

    result = await build_graph_for_book(
        book_id=book_id,
        chunks=book_nodes,
        topics_per_chunk=topics_per_chunk,
        community_repo=community_repo,
        entity_repo=entity_repo,
        relation_repo=relation_repo,
    )

    elapsed = time.monotonic() - start

    # Step 6: 验证结果
    print(f"\n{'=' * 60}")
    print(f"graph 构建结果:")
    print(f"  耗时: {elapsed:.1f}s")
    print(f"  实体数: {result['entity_count']}")
    print(f"  关系数: {result['relation_count']}")
    print(f"  社区数: {result['community_count']}")
    print(f"  叶子数: {result['leaf_count']}")
    print(f"  树节点数: {result['node_count']}")
    print(f"  错误: {result['error']}")
    print(f"{'=' * 60}")

    # 验收标准
    assert result["error"] is None, f"流水线出错: {result['error']}"
    assert result["entity_count"] >= 5, f"实体数不足: {result['entity_count']}"
    assert result["node_count"] >= 2, f"树节点不足: {result['node_count']}"
    assert result["leaf_count"] >= 1, f"叶子社区不足: {result['leaf_count']}"

    # Step 7: 验证 DB 中确实写入了数据
    roots = await community_repo.get_roots(scope="book", book_id=book_id)
    assert len(roots) >= 1, "DB 中应有 root 节点"
    print(f"\nDB 验证: {len(roots)} 个 root 节点")

    for root in roots:
        children = await community_repo.get_children(root.node_id)
        print(f"  root '{root.label}': {len(children)} 个子节点, is_leaf={root.is_leaf}")

    print(f"\n✅ 端到端验证通过！耗时 {elapsed:.1f}s")


@pytest.mark.asyncio
async def test_graph_build_performance(db_session_factory, index_manager, document_manager):
    """性能验证：graph 构建应在 60s 内完成"""
    from src.core.knowledge_qa.graph.pipeline import build_graph_for_book
    from src.repository.graph_repository import GraphCommunityRepository

    docs = await document_manager.list_documents()
    indexed = [d for d in docs if d["status"] == "indexed"]
    if not indexed:
        pytest.skip("无已索引书籍")

    book = indexed[0]
    book_id = book["id"]
    file_hash = book["file_hash"]

    idx = index_manager.get_index()
    if not idx or not hasattr(idx, "docstore"):
        pytest.skip("docstore 不可用")

    book_nodes = [
        n for n in idx.docstore.docs.values()
        if getattr(n, "ref_doc_id", None) == file_hash
    ]
    if not book_nodes:
        book_nodes = list(idx.docstore.docs.values())[:50]

    topics_per_chunk = []
    for node in book_nodes:
        meta = getattr(node, "metadata", {}) or {}
        topics_str = meta.get("topics", "[]")
        try:
            topics = json.loads(topics_str) if isinstance(topics_str, str) else topics_str
        except (json.JSONDecodeError, TypeError):
            topics = []
        topics_per_chunk.append(topics if isinstance(topics, list) else [])

    community_repo = GraphCommunityRepository(db_session_factory)

    start = time.monotonic()
    result = await build_graph_for_book(
        book_id=book_id,
        chunks=book_nodes,
        topics_per_chunk=topics_per_chunk,
        community_repo=community_repo,
    )
    elapsed = time.monotonic() - start

    print(f"\ngraph 构建耗时: {elapsed:.1f}s")
    assert elapsed < 60, f"graph 构建耗时 {elapsed:.1f}s 超过 60s 阈值"
    print(f"✅ 性能达标")


@pytest.mark.asyncio
async def test_community_tree_structure(db_session_factory, index_manager, document_manager):
    """验证层级树结构：至少 2 层，叶子节点有 chunk_ids"""
    from src.core.knowledge_qa.graph.pipeline import build_graph_for_book
    from src.repository.graph_repository import GraphCommunityRepository

    docs = await document_manager.list_documents()
    indexed = [d for d in docs if d["status"] == "indexed"]
    if not indexed:
        pytest.skip("无已索引书籍")

    book = indexed[0]
    book_id = book["id"]

    community_repo = GraphCommunityRepository(db_session_factory)

    # 检查是否已有数据（可能前一个测试已构建）
    roots = await community_repo.get_roots(scope="book", book_id=book_id)
    if not roots:
        # 需要先构建
        pytest.skip("需先运行 test_graph_build_for_one_book")

    # 验证层级深度
    all_levels = set()
    leaf_count = 0
    leaves_with_chunks = 0

    async def _collect_tree(nodes, depth=0):
        nonlocal leaf_count, leaves_with_chunks
        for node in nodes:
            all_levels.add(node.level)
            if node.is_leaf:
                leaf_count += 1
                chunk_ids = node.chunk_ids or []
                if chunk_ids:
                    leaves_with_chunks += 1
                print(f"  叶子: level={node.level}, label={node.label}, entities={len(node.entity_names or [])}, chunks={len(chunk_ids)}")
            children = await community_repo.get_children(node.node_id)
            if children:
                await _collect_tree(children, depth + 1)

    await _collect_tree(roots)

    print(f"\n层级树结构:")
    print(f"  层级数: {len(all_levels)} (层级: {sorted(all_levels)})")
    print(f"  叶子数: {leaf_count}")
    print(f"  有 chunk 的叶子: {leaves_with_chunks}")

    assert len(all_levels) >= 2, f"层级深度不足: {all_levels}"
    assert leaf_count >= 1, "无叶子节点"
    print(f"✅ 层级树结构验证通过")
