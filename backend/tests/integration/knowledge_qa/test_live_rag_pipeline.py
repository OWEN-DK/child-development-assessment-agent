"""知识问答全流程 Live RAG 测试

使用真实 DashScope LLM + 真实 RAG 搜索服务，端到端验证完整流水线。
需要:
  1. 后端服务运行中（默认 http://localhost:8000），且 RAG 已索引文档
  2. DASHSCOPE_API_KEY 环境变量（.env.dev 中已配置即可）

测试层级:
  R1: RAG 服务连通性 + 文档可用性
  R2: 真实 RAG 搜索返回有效结果
  R3: search_knowledge_base 工具通过真实 RAG 执行
  R4: 完整 9 节点 graph（真实 LLM + 真实 RAG）

运行:
  cd backend && uv run pytest tests/integration/knowledge_qa/test_live_rag_pipeline.py -v -s
"""

import json
import os
import time
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock

import pytest


# ==================== 配置 ====================

RAG_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")

DASHSCOPE_API_KEY = os.environ.get("DASHSCOPE_API_KEY")
if not DASHSCOPE_API_KEY:
    _env_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "..", ".env.dev"
    )
    if os.path.exists(_env_path):
        with open(_env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("DASHSCOPE_API_KEY="):
                    DASHSCOPE_API_KEY = line.split("=", 1)[1].strip()
                    break

pytestmark = pytest.mark.skipif(
    not DASHSCOPE_API_KEY,
    reason="需要 DASHSCOPE_API_KEY",
)


def _check_server():
    """检查后端服务是否可达"""
    import urllib.request

    try:
        r = urllib.request.urlopen(f"{RAG_BASE_URL}/rag/documents", timeout=5)
        data = json.loads(r.read())
        docs = data.get("data", {}).get("documents", [])
        return True, docs
    except Exception as e:
        return False, str(e)


_server_ok, _server_docs = _check_server()

pytestmark = pytest.mark.skipif(
    not DASHSCOPE_API_KEY or not _server_ok,
    reason="需要 DASHSCOPE_API_KEY 且后端服务运行中",
)


# ==================== Fixtures ====================


@pytest.fixture(autouse=True)
def _clear_factory_cache():
    from src.core.llm.factory import LLMServiceFactoryCompat

    LLMServiceFactoryCompat._raw_instances.clear()
    yield
    LLMServiceFactoryCompat._raw_instances.clear()


@pytest.fixture
def _setup_rag_context():
    """设置知识问答 ContextVar（真实 RAG + mock 进度回调）"""
    from src.core.knowledge_qa.tools import (
        clear_http_client,
        set_http_client,
    )
    from src.schemas.knowledge_qa import (
        clear_partial_collector,
        clear_progress_context,
        clear_prompt_manager,
        init_partial_collector,
        set_progress_context,
        set_prompt_manager,
    )
    from src.utils.http_client import RagHttpClient

    progress_log: list[str] = []

    async def mock_progress(step: str, message: str, **meta):
        progress_log.append(f"[{step}] {message}")
        print(f"  📌 {step}: {message}")

    set_progress_context(
        callback=mock_progress, task_id="live-rag-test", task_type="knowledge_qa"
    )

    mock_pm = MagicMock()
    mock_pm.get_prompt = AsyncMock(return_value=None)
    set_prompt_manager(mock_pm)

    # 使用真实 RAG HTTP 客户端
    rag_client = RagHttpClient(base_url=RAG_BASE_URL)
    set_http_client(rag_client)

    init_partial_collector()

    yield progress_log

    clear_progress_context()
    clear_prompt_manager()
    clear_partial_collector()
    clear_http_client()
    # 关闭真实 HTTP 客户端
    import asyncio

    asyncio.get_event_loop().run_until_complete(rag_client.close())


# ==================== R1: RAG 连通 + 文档 ====================


def test_r1_rag_service_connectivity():
    """R1: 验证 RAG 服务可达且已索引文档"""
    import urllib.request

    r = urllib.request.urlopen(f"{RAG_BASE_URL}/rag/documents", timeout=5)
    data = json.loads(r.read())

    assert data.get("code") == 0, f"R1 失败: {data}"
    docs = data["data"]["documents"]
    assert len(docs) >= 1, f"R1 失败: 知识库中无索引文档"
    print(f"  ✅ R1 通过: 知识库有 {len(docs)} 本索引文档")
    for doc in docs:
        print(f"     - {doc['file_name']} ({doc['total_pages']} 页)")


# ==================== R2: 真实 RAG 搜索 ====================


def test_r2_rag_search_returns_results():
    """R2: 真实 RAG 搜索返回有效结果"""
    import urllib.parse
    import urllib.request

    query = "运动对儿童大脑发展的影响"
    url = f"{RAG_BASE_URL}/rag/search?" + urllib.parse.urlencode(
        {"query": query, "limit": 5}
    )
    r = urllib.request.urlopen(url, timeout=10)
    data = json.loads(r.read())

    assert data.get("code") == 0, f"R2 失败: {data}"
    results = data["data"]["results"]
    assert len(results) >= 1, f"R2 失败: 搜索 '{query}' 无结果"

    first = results[0]
    # 验证关键字段存在
    for key in ["id", "content", "score", "source_book", "chapter_title"]:
        assert key in first, f"R2 失败: 结果缺少字段 '{key}'"

    print(f"  ✅ R2 通过: 搜索 '{query}' 返回 {len(results)} 条结果")
    print(f"     Top 1: score={first['score']}, chapter={first['chapter_title']}")
    print(f"     内容摘要: {first['content'][:80]}...")


# ==================== R3: 工具级 RAG 搜索 ====================


@pytest.mark.asyncio
async def test_r3_tool_search_with_real_rag(_setup_rag_context):
    """R3: search_knowledge_base 工具通过真实 RAG 搜索"""
    from src.core.knowledge_qa.tools import search_knowledge_base

    results = await search_knowledge_base.ainvoke(
        {"query": "运动改变大脑", "top_k": 3}
    )

    assert isinstance(results, list), f"R3 失败: 应返回 list，实际: {type(results)}"
    # 不应有 error 项
    errors = [r for r in results if "error" in r]
    assert not errors, f"R3 失败: 搜索返回错误: {errors}"
    assert len(results) >= 1, f"R3 失败: 搜索无结果"

    print(f"  ✅ R3 通过: 工具搜索返回 {len(results)} 条结果")
    for r in results[:3]:
        title = r.get("source_book", r.get("book_title", "unknown"))
        score = r.get("score", "?")
        content_preview = r.get("content", r.get("text", ""))[:60]
        print(f"     [{score}] {title}: {content_preview}...")


# ==================== R4: 完整 9 节点 graph ====================


@pytest.mark.asyncio
async def test_r4_full_graph_with_real_rag(_setup_rag_context):
    """R4: 完整 9 节点知识问答流水线（真实 LLM + 真实 RAG）

    match_books → analyze_child → identify_problems → recommend_types
    → plan_outline → plan_expand → conclusion → verify_citations → finalize

    这是最关键的端到端测试，验证真实环境下 LLM 能从真实 RAG 中检索到
    相关内容并生成完整报告。
    """
    from src.core.knowledge_qa.graph import create_knowledge_qa_graph
    from src.schemas.knowledge_qa import KnowledgeQAState

    graph = create_knowledge_qa_graph()

    question = "孩子5岁，经常精神不集中，一件事没有做完就会做下一件，有什么运动建议？"
    start = time.monotonic()

    result = await graph.ainvoke(
        KnowledgeQAState(question=question),
    )

    elapsed = time.monotonic() - start

    # --- 基本断言 ---
    assert "completed" in result["current_step"], (
        f"R4 失败: graph 未完成。current_step={result['current_step']}"
    )

    books = result["matched_books_detail"]
    assert len(books) >= 1, "R4 失败: 未匹配到书籍"
    print(f"\n  📚 匹配书籍: {', '.join(b.title for b in books)}")
    for b in books:
        print(f"     - [{b.book_id}] {b.title} (匹配理由: {b.match_reason[:50]})")

    sections = result["sections"]
    assert len(sections) >= 4, f"R4 失败: 仅完成 {len(sections)} 节，期望 >= 4"

    for i in range(1, 6):
        sec = sections.get(i)
        if sec is None:
            print(f"  ⚠️  第{i}节缺失")
            continue
        cite_count = len(sec.citations)
        print(f"  📝 第{i}节 [{sec.title}]: {len(sec.content)} 字, {cite_count} 条引用")
        # 检查内容非空
        assert sec.content, f"R4 失败: 第{i}节内容为空"

    # 最终统计
    total_sections = len(sections)
    total_citations = sum(len(sec.citations) for sec in sections.values())
    partial = result.get("partial", True)

    print(f"\n  {'✅' if not partial else '⚠️ '} R4 结果:")
    print(f"     问题: {question}")
    print(f"     总耗时: {elapsed:.1f}s")
    print(f"     完成节数: {total_sections}/5")
    print(f"     总引用数: {total_citations}")
    print(f"     降级标记: {'是' if partial else '否'}")
    if result.get("errors"):
        print(f"     错误列表: {result['errors']}")

    # 打印报告摘要
    print(f"\n  ===== 报告摘要 =====")
    for i in range(1, 6):
        sec = sections.get(i)
        if sec:
            print(f"  --- 第{i}节: {sec.title} ---")
            print(f"  {sec.content[:200]}...")
            if sec.citations:
                for c in sec.citations[:2]:
                    book = c.get("book_title", "未知")
                    ch = c.get("chapter", "未知章节")
                    print(f"  引用: [{book}] {ch}")
                if len(sec.citations) > 2:
                    print(f"  ... 还有 {len(sec.citations) - 2} 条引用")
            print()

    # 至少完成 4 节才算通过
    assert total_sections >= 4, f"R4 失败: 仅完成 {total_sections} 节"
