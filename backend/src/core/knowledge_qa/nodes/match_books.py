"""书籍匹配节点 — 直接搜索 + 27B 单次 LLM 调用匹配

7B qwen-turbo 已统一切换为 qwen3.5-27b。搜索由 Python 代码直接执行，LLM 做单次 structured_output 调用。
"""

import asyncio
import logging
from typing import Any, Dict, List

from pydantic import BaseModel, Field

from src.core.knowledge_qa.tools import (
    clear_search_accumulator,
    clear_tool_call_state,
    get_search_accumulator,
    init_search_accumulator,
    init_tool_call_state,
)
from src.schemas.knowledge_qa import (
    KnowledgeQAState,
    MatchedBook,
    NoMatchingBooksError,
    push_progress,
)

logger = logging.getLogger(__name__)


class MatchedBookItem(BaseModel):
    """单本书匹配结果（LLM 结构化输出）"""
    book_id: str = Field(description="搜索结果中的 source_book 字段值（文件名）")
    title: str = Field(description="推断的书名")
    match_reason: str = Field(description="匹配理由，一句话")


class MatchBooksResponse(BaseModel):
    """书籍匹配 LLM 输出"""
    matched_books: List[MatchedBookItem] = Field(description="匹配的书籍列表，按匹配度排序")


async def _batch_resolve_book_ids(raw_ids: list[str]) -> dict[str, str]:
    """通过 HTTP 调用 RAG 服务批量将 book_id 映射为 DocumentRecord UUID。

    先前直接查询知识库数据库，现已改为 HTTP 调用 /rag/books/batch-resolve，
    为后续知识库独立部署做准备。
    """
    if not raw_ids:
        return {}

    trimmed_ids = [rid.strip() for rid in raw_ids]
    try:
        from src.core.knowledge_qa.tools import _get_http_client

        client = _get_http_client()
        books = await client.batch_resolve_books(trimmed_ids)

        mapping: dict[str, str] = {}
        for b in books:
            uuid_str = b["id"]
            mapping[uuid_str] = uuid_str
            if b.get("file_name"):
                mapping[b["file_name"]] = uuid_str
                mapping[b["file_name"].strip()] = uuid_str
            if b.get("file_hash"):
                mapping[b["file_hash"]] = uuid_str
        return mapping
    except Exception as e:
        logger.warning(f"批量 book_id 解析失败 (HTTP): {e}")
        return {}


async def _extract_candidate_books(search_results: List[Dict]) -> List[Dict]:
    """从搜索结果中提取候选书籍信息（去重，书名规范化去扩展名）。"""
    import re as _re

    seen = {}
    for r in search_results:
        sb = r.get("source_book", "")
        if not sb:
            continue
        # 规范化: trim + 去文件扩展名
        sb_clean = sb.strip()
        for ext in (".epub", ".pdf", ".txt", ".md", ".docx", ".html", ".mobi"):
            if sb_clean.lower().endswith(ext):
                sb_clean = sb_clean[:-len(ext)].strip()
                break
        if sb_clean and sb_clean not in seen:
            seen[sb_clean] = {
                "source_book": sb_clean,  # 使用规范化后的书名
                "_raw_source_book": sb,    # 保留原始值用于精确 DB 匹配
                "file_hash": r.get("file_hash", ""),
                "chapters": [],
            }
        if sb_clean in seen:
            ch = r.get("chapter_title", "")
            if ch and ch not in seen[sb_clean]["chapters"]:
                seen[sb_clean]["chapters"].append(ch)
    return list(seen.values())


async def _direct_search(question: str) -> List[Dict]:
    """直接搜索知识库通过 ContextVar HTTP 客户端。"""
    import httpx
    from src.config import settings

    host = getattr(settings, "app_host", "127.0.0.1")
    port = getattr(settings, "app_port", 8000)

    # 生成搜索关键词
    queries = [question]
    import re
    book_mentions = re.findall(r'《([^》]+)》', question)
    for bm in book_mentions:
        queries.append(bm)
    short = " ".join(question.replace("，", " ").replace("、", " ").split()[:8])
    if short and short != question:
        queries.append(short)

    all_results = []
    seen_ids = set()

    async with httpx.AsyncClient(
        base_url=f"http://{host}:{port}",
        timeout=httpx.Timeout(10.0),
    ) as client:
        for query in queries[:3]:
            try:
                resp = await client.get(
                    "/rag/search",
                    params={"query": query, "limit": 10},
                )
                resp.raise_for_status()
                data = resp.json()
                results = data.get("data", {}).get("results", [])
                logger.info(f"match_books 搜索 '{query[:40]}' 返回 {len(results)} 条")
            except Exception as e:
                logger.warning(f"match_books 搜索失败 (query={query[:50]}): {e}")
                continue

            for r in results:
                rid = r.get("id", "")
                if rid and rid not in seen_ids:
                    seen_ids.add(rid)
                    all_results.append(r)

            if len(all_results) >= 10:
                break

    return all_results


async def _llm_match_books(question: str, candidates: List[Dict]) -> List[MatchedBookItem]:
    """使用 27B LLM 从候选书籍中选择匹配的书籍。"""
    if not candidates:
        return []

    from src.core.llm.factory import LLMServiceFactoryCompat

    # 构建候选摘要
    candidate_text = ""
    for i, c in enumerate(candidates):
        chapters_str = "、".join(c["chapters"][:3]) if c["chapters"] else "未知"
        candidate_text += (
            f"[{i}] book_id=\"{c['source_book']}\", "
            f"涉及章节: {chapters_str}\n"
        )

    prompt = f"""你是一个文献检索专家。根据用户问题，从候选书籍中选择最相关的书籍。

用户问题：{question}

候选书籍（从知识库搜索结果中提取）：
{candidate_text}

请选出与用户问题最相关的书籍（通常 1-2 本），按匹配度排序。
- book_id 必须使用候选书籍中显示的 book_id 值
- title 根据 book_id 推断一个有意义的书名（去掉文件扩展名）
- 为每本书写一句话匹配理由
- 如果候选书籍都不相关，返回空数组"""

    model = LLMServiceFactoryCompat.create_raw(
        model_name="qwen3.5-27b",
        temperature=0.3,
    )

    try:
        structured_model = model.with_structured_output(MatchBooksResponse)
        result = await asyncio.wait_for(
            structured_model.ainvoke(prompt),
            timeout=15,
        )
        return result.matched_books
    except Exception as e:
        logger.warning(f"LLM 书籍匹配失败: {e}")
        return []


async def match_books_node(state: KnowledgeQAState) -> Dict[str, Any]:
    """书籍匹配节点：直接搜索知识库 + 27B LLM 单次匹配。"""
    await push_progress("started", "正在分析问题意图并匹配书籍…")

    init_search_accumulator()
    init_tool_call_state(max_calls=10)

    try:
        # Step 1: 直接调用 search_knowledge_base 工具搜索知识库
        search_results = await _direct_search(state.question)
        logger.info(f"match_books 直接搜索: {len(search_results)} 条结果")

        if not search_results:
            raise NoMatchingBooksError()

        # Step 2: 从搜索结果中提取候选书籍
        candidates = await _extract_candidate_books(search_results)
        logger.info(f"match_books 候选书籍: {[c['source_book'] for c in candidates]}")

        if not candidates:
            raise NoMatchingBooksError()

        # Step 3: 使用 27B LLM 做匹配评估（单次调用，无工具）
        matched_items = await _llm_match_books(state.question, candidates)

        # Step 4: 如果 LLM 匹配失败，降级为直接提取全部候选
        if not matched_items:
            logger.info("LLM 匹配返回空，降级为直接提取")
            for c in candidates:
                clean_name = c["source_book"]
                matched_items.append(MatchedBookItem(
                    book_id=clean_name,
                    title=clean_name,
                    match_reason="从搜索结果中自动匹配",
                ))

        # Step 5: 解析 book_id → UUID（用于 matched_books_detail）
        # 同时构建 source_book → file_hash 映射（用于 RAG 搜索过滤）
        source_to_hash: Dict[str, str] = {}
        for c in candidates:
            raw = c.get("_raw_source_book", c["source_book"])
            clean = c["source_book"]
            fh = c.get("file_hash", "")
            if fh:
                source_to_hash[clean] = fh
                if raw != clean:
                    source_to_hash[raw] = fh

        raw_ids = [m.book_id for m in matched_items]
        id_mapping = await _batch_resolve_book_ids(raw_ids)

        search_book_ids = []  # file_hash — 供后续节点 RAG 搜索过滤
        resolved_books = []
        books_detail = []
        for i, item in enumerate(matched_items):
            # 多路径解析: 先精确匹配，再 trim，再用 file_hash 降级
            resolved_id = (
                id_mapping.get(item.book_id)
                or id_mapping.get(item.book_id.strip())
            )
            if not resolved_id:
                # 用规范化前的原始书名重试
                for c in candidates:
                    if c["source_book"] == item.book_id and c.get("_raw_source_book"):
                        resolved_id = id_mapping.get(c["_raw_source_book"])
                        if resolved_id:
                            break

            fh = source_to_hash.get(item.book_id, "") or source_to_hash.get(item.book_id.strip(), "")

            if not resolved_id and not fh:
                logger.warning(f"book_id 无法解析且无 file_hash: {item.book_id}")
                continue

            if not resolved_id:
                # 最终降级: 用 file_hash 作为 book_id
                resolved_id = fh
                search_book_ids.append(fh)
            else:
                if fh:
                    search_book_ids.append(fh)

            resolved_books.append({"book_id": resolved_id, "title": item.title, "file_hash": fh})
            books_detail.append(MatchedBook(
                book_id=resolved_id,
                title=item.title,
                source_type="book",
                match_reason=item.match_reason,
                is_primary=(i == 0),
            ))

        if not books_detail:
            raise NoMatchingBooksError()

        await push_progress("books_matched", f"已匹配书籍: {books_detail[0].title}")

        # search_book_ids 存 file_hash（供 RAG 过滤），resolved_books 中的 book_id 存 UUID（供详情输出）
        return {
            "matched_book_ids": search_book_ids,
            "matched_books_detail": books_detail,
            "current_step": ["books_matched"],
        }

    except NoMatchingBooksError:
        raise

    except Exception as e:
        logger.exception(f"match_books 节点异常: {e}")
        return {
            "matched_book_ids": [],
            "matched_books_detail": [],
            "errors": state.errors + [f"match_books_failed: {e}"],
            "current_step": ["books_matched_failed"],
        }

    finally:
        clear_search_accumulator()
        clear_tool_call_state()
