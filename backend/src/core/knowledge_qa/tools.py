"""知识问答工具定义

所有 Agent 节点共用的唯一工具：search_knowledge_base。
LLM 在需要从知识库获取信息时主动调用。

防护机制：
- 调用计数：单请求最多调用 MAX_TOOL_CALLS 次
- 重复检测：相同查询直接返回缓存结果 + 提示
- 类型兼容：book_ids 自动转换字符串为列表

搜索结果累加器：
- 搜索结果全量存入 _search_accumulator（供子 Agent 使用）
- 只返回摘要给协调器（避免上下文膨胀）
"""

import contextvars
import hashlib
import json
from typing import Any, Dict, List, Optional

from langchain_core.tools import tool

from src.utils.logger import logger

# 请求级 HTTP 客户端，通过 ContextVar 传递
_http_client_ctx: contextvars.ContextVar[Optional[Any]] = (
    contextvars.ContextVar("knowledge_qa_http_client", default=None)
)

# 工具调用防护状态（请求级）
_tool_call_state: contextvars.ContextVar[Optional[Dict[str, Any]]] = (
    contextvars.ContextVar("knowledge_qa_tool_call_state", default=None)
)

# 默认最大工具调用次数（单节点），可被 init_tool_call_state(max_calls=) 覆盖
DEFAULT_MAX_TOOL_CALLS = 10

# 搜索结果累加器（请求级）—— 全量原文供子 Agent 使用
_search_accumulator: contextvars.ContextVar[Optional[List[Dict]]] = (
    contextvars.ContextVar("kqa_search_accumulator", default=None)
)


def init_search_accumulator():
    """初始化搜索累加器（每个 _run_section_node 入口处调用）"""
    _search_accumulator.set([])


def add_to_search_accumulator(results: List[Dict]):
    """将搜索结果追加到累加器"""
    acc = _search_accumulator.get()
    if acc is not None:
        acc.extend(results)


def get_search_accumulator() -> List[Dict]:
    """获取当前累加的全部搜索结果"""
    return _search_accumulator.get() or []


def clear_search_accumulator():
    """清除搜索累加器（每个 _run_section_node 出口处调用）"""
    _search_accumulator.set(None)


def set_http_client(client):
    """由 Service 在请求开始时调用，设置请求级 HTTP 客户端"""
    _http_client_ctx.set(client)


def clear_http_client():
    """由 Service 在请求结束时调用，清除 HTTP 客户端引用"""
    _http_client_ctx.set(None)


def init_tool_call_state(max_calls: int = DEFAULT_MAX_TOOL_CALLS):
    """初始化工具调用状态（每个节点开始时调用）

    Args:
        max_calls: 本节点允许的最大工具调用次数
    """
    _tool_call_state.set({
        "call_count": 0,
        "max_calls": max_calls,
        "seen_queries": {},  # {query_hash: query_text}
    })


def clear_tool_call_state():
    """清除工具调用状态（每个节点结束时调用）"""
    _tool_call_state.set(None)


def _get_http_client():
    """获取当前请求的 HTTP 客户端实例"""
    client = _http_client_ctx.get()
    if client is None:
        raise RuntimeError("HTTP 客户端未设置，请确保 Service 已调用 set_http_client()")
    return client


def _get_tool_call_state() -> Dict[str, Any]:
    """获取当前请求的工具调用状态，未初始化时自动初始化"""
    state = _tool_call_state.get()
    if state is None:
        state = {"call_count": 0, "seen_queries": {}}
        _tool_call_state.set(state)
    return state


def _hash_query(query: str, book_ids: Optional[List[str]] = None) -> str:
    """生成查询的哈希值（用于去重）"""
    key = json.dumps(
        {"query": query.strip().lower(), "book_ids": sorted(book_ids or [])},
        sort_keys=True,
    )
    return hashlib.md5(key.encode()).hexdigest()


@tool
async def search_knowledge_base(
    query: str,
    book_ids: Optional[List[str]] = None,
    top_k: int = 20,
) -> List[Dict[str, Any]]:
    """
    搜索知识库中的书籍内容。当你需要从已索引的书籍中查找信息、验证某个主张、
    或获取章节原文时，调用此工具。

    使用建议：
    - 用自然语言描述你要查找的内容，如 "运动对儿童注意力的影响 有氧运动"
    - 如果已经知道要查哪本书，传入 book_ids 缩小范围
    - 从不同角度搜索，每次使用不同的关键词组合
    - top_k 默认 20，返回足够多的结果供多角度参考

    重要：返回结果中 source_book 字段是书籍的唯一标识（文件名），
    在 match_books 的 book_id 字段中请直接使用 source_book 的值。

    Args:
        query: 检索查询词，用自然语言描述你需要的信息
        book_ids: 可选，限制在指定书籍 ID 内检索
        top_k: 返回结果数，默认 10

    Returns:
        检索结果列表，每项含: id, content（原文）, source_book（书籍文件名，用作 book_id）,
        chapter_title, page_label, file_hash, score 等字段
    """
    import httpx

    # ===== 防护层：类型兼容 =====
    # book_ids 可能被 LLM 传为 JSON 字符串，自动转换
    if isinstance(book_ids, str):
        try:
            book_ids = json.loads(book_ids)
        except (json.JSONDecodeError, TypeError):
            book_ids = [book_ids] if book_ids else []

    # ===== 防护层：调用计数 =====
    state = _get_tool_call_state()
    state["call_count"] += 1
    call_count = state["call_count"]
    max_calls = state.get("max_calls", DEFAULT_MAX_TOOL_CALLS)

    if call_count > max_calls:
        logger.warning(f"工具调用次数已达上限 ({max_calls})，拒绝继续搜索")
        return [{
            "info": "call_limit_reached",
            "message": f"已达到搜索次数上限（{max_calls}次），请基于已有的搜索结果生成回答，不要再调用工具。",
            "total_calls": call_count,
        }]

    # ===== 防护层：重复查询检测 =====
    query_hash = _hash_query(query, book_ids)
    if query_hash in state["seen_queries"]:
        original_query = state["seen_queries"][query_hash]
        logger.info(f"检测到重复查询: '{query}' (与 '{original_query}' 相同)")
        return [{
            "info": "duplicate_query",
            "message": f"你已经用相同的关键词搜索过（'{query}'），结果已经返回。请换一个不同的角度或关键词重新搜索。",
            "original_query": original_query,
            "call_count": call_count,
            "max_calls": max_calls,
            "remaining_calls": max_calls - call_count,
        }]

    # 记录本次查询
    state["seen_queries"][query_hash] = query

    # ===== 执行实际搜索 =====
    client = _get_http_client()
    try:
        results = await client.search_chunks(
            question=query,
            book_ids=book_ids or [],
            limit=top_k,
        )
    except (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError):
        try:
            results = await client.search_chunks(
                question=query,
                book_ids=book_ids or [],
                limit=top_k,
            )
        except Exception:
            return [{
                "error": "rag_unavailable",
                "message": "知识库检索服务暂不可用，请基于已有信息继续或标注'检索不可用'",
            }]
    except Exception as e:
        logger.warning(f"搜索异常: {type(e).__name__}: {e}")
        return [{"error": "search_error", "message": "知识库检索遇到异常，请基于已有信息继续"}]

    if not results or not isinstance(results, list):
        return [{"summary": f"搜索 '{query}' 未命中任何结果，请换关键词重试。", "hit_count": 0}]

    # 全量存入累加器（供子 Agent 使用）
    add_to_search_accumulator(results)

    # 构建摘要返回给协调器（避免上下文膨胀）
    # 统计覆盖的书籍和章节
    books: Dict[str, int] = {}
    for r in results:
        sb = r.get("source_book", "未知")
        books[sb] = books.get(sb, 0) + 1

    top_n = min(3, len(results))
    top_hits = []
    for r in results[:top_n]:
        top_hits.append({
            "book": r.get("source_book", "未知"),
            "chapter": r.get("chapter_title", "未知"),
            "snippet": (r.get("content", "") or "")[:100],
        })

    book_summary = "、".join(f"《{b}》({c}条)" for b, c in list(books.items())[:5])

    return [{
        "summary": f"搜索 '{query}' 命中 {len(results)} 条结果，覆盖 {book_summary}",
        "top_hits": top_hits,
        "hit_count": len(results),
        "call_count": call_count,
        "max_calls": max_calls,
        "remaining_calls": max_calls - call_count,
        "hint": "信息不足时换关键词重新搜索，信息充分后调用 comprehend_results 深度理解",
    }]
