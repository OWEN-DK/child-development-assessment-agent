"""查询侧层级遍历验证

验证 3 个真实问题是否通过层级遍历命中相关块。
这是 Phase 1 验收标准的核心测试。

运行方式：
cd backend && uv run pytest tests/integration/knowledge_qa/test_query_traversal.py -v -s
"""

import asyncio
import logging
import time

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


BOOK_ID = "f47fa73f-c946-4ec8-92b4-4d2740daf0f1"

# 3 个测试问题（与《由内而外的教养》内容相关）
TEST_QUESTIONS = [
    "4岁孩子情绪波动大、容易发脾气，如何帮助他学会情绪调节？",
    "孩子晚上经常做噩梦哭醒，这跟白天的创伤经历有关吗？家长应该怎么处理？",
    "如何通过亲子互动游戏促进3岁孩子的脑部发育？",
]

# 1 个完全不相关的问题（应返回空或极少命中）
IRRELEVANT_QUESTION = "量子力学的基本原理是什么？"


@pytest.fixture
def db_session_factory():
    from src.core.database import async_session_factory
    return async_session_factory


@pytest.fixture
def community_repo(db_session_factory):
    from src.repository.graph_repository import GraphCommunityRepository
    return GraphCommunityRepository(db_session_factory)


@pytest.mark.asyncio
async def test_tree_has_data_for_book(community_repo):
    """前置检查：确认 DB 中有该书的社区树数据"""
    roots = await community_repo.get_roots(scope="book", book_id=BOOK_ID)
    assert len(roots) >= 1, f"无 root 节点 (book_id={BOOK_ID})"
    print(f"\nRoot 节点: {len(roots)}")
    for r in roots:
        print(f"  {r.node_id}: {r.label}")


@pytest.mark.asyncio
async def test_relevant_questions_hit_chunks(community_repo):
    """核心验证：3 个相关问题中至少 2 个通过层级遍历命中相关块"""
    from src.core.knowledge_qa.graph.traversal import explore_community_tree

    roots = await community_repo.get_roots(scope="book", book_id=BOOK_ID)
    assert roots, "无 root 节点"

    results = []
    for q in TEST_QUESTIONS:
        all_hits = []
        start = time.monotonic()
        for root in roots:
            hits = await explore_community_tree(
                question=q,
                root_id=root.node_id,
                community_repo=community_repo,
            )
            all_hits.extend(hits)
        elapsed = time.monotonic() - start

        total_chunks = sum(len(h.chunk_ids) for h in all_hits)
        hit_communities = [h.label for h in all_hits]
        results.append({
            "question": q,
            "hits": len(all_hits),
            "chunks": total_chunks,
            "communities": hit_communities,
            "elapsed": elapsed,
        })

        print(f"\n问题: {q}")
        print(f"  命中社区: {len(all_hits)}, 块数: {total_chunks}, 耗时: {elapsed:.1f}s")
        for h in all_hits:
            print(f"    - {h.label} ({len(h.chunk_ids)} chunks)")

    # 至少 2/3 命中
    successful = sum(1 for r in results if r["chunks"] > 0)
    print(f"\n命中统计: {successful}/3 个问题命中了相关块")
    assert successful >= 2, f"仅 {successful}/3 个问题命中，要求 ≥2"


@pytest.mark.asyncio
async def test_irrelevant_question_returns_empty(community_repo):
    """完全不相关的问题应返回极少或零命中"""
    from src.core.knowledge_qa.graph.traversal import explore_community_tree

    roots = await community_repo.get_roots(scope="book", book_id=BOOK_ID)
    all_hits = []
    for root in roots:
        hits = await explore_community_tree(
            question=IRRELEVANT_QUESTION,
            root_id=root.node_id,
            community_repo=community_repo,
        )
        all_hits.extend(hits)

    total_chunks = sum(len(h.chunk_ids) for h in all_hits)
    print(f"\n不相关问题: 命中 {len(all_hits)} 社区, {total_chunks} 块")
    for h in all_hits:
        print(f"  - {h.label} ({len(h.chunk_ids)} chunks)")

    # 不相关问题命中应该很少（允许少量噪声，但不应超过 5 个社区）
    assert len(all_hits) <= 5, f"不相关问题命中了 {len(all_hits)} 个社区，剪枝效果不佳"


@pytest.mark.asyncio
async def test_build_knowledge_context(community_repo):
    """验证 build_knowledge_context 生成结构化 Markdown"""
    from src.core.knowledge_qa.graph.traversal import (
        build_knowledge_context,
        explore_community_tree,
    )

    roots = await community_repo.get_roots(scope="book", book_id=BOOK_ID)
    all_hits = []
    for root in roots:
        hits = await explore_community_tree(
            question=TEST_QUESTIONS[0],
            root_id=root.node_id,
            community_repo=community_repo,
        )
        all_hits.extend(hits)

    if not all_hits:
        pytest.skip("层级遍历未命中")

    context = await build_knowledge_context(
        question=TEST_QUESTIONS[0],
        hits=all_hits,
    )

    print(f"\n知识上下文长度: {len(context)} 字符")
    assert len(context) > 0, "知识上下文为空"
    assert "### 社区：" in context, "缺少社区标题"
    assert "**关键概念**" in context, "缺少关键概念"

    # 打印前 500 字符预览
    print(f"\n预览:\n{context[:500]}...")


@pytest.mark.asyncio
async def test_traversal_performance(community_repo):
    """性能验证：层级遍历应在 30s 内完成"""
    from src.core.knowledge_qa.graph.traversal import explore_community_tree

    roots = await community_repo.get_roots(scope="book", book_id=BOOK_ID)

    start = time.monotonic()
    for root in roots:
        await explore_community_tree(
            question=TEST_QUESTIONS[0],
            root_id=root.node_id,
            community_repo=community_repo,
        )
    elapsed = time.monotonic() - start

    print(f"\n层级遍历耗时: {elapsed:.1f}s")
    assert elapsed < 30, f"层级遍历耗时 {elapsed:.1f}s 超过 30s 阈值"
