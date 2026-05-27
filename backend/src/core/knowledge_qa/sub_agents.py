"""知识问答子 Agent 工具

供 7B 协调器调用的 @tool 函数。每个工具内部调用 32B 模型做单次无工具推理，
结果通过 ContextVar 传递回 _run_section_node。

包含：
- comprehend_results: 让 32B 深度理解搜索结果
- generate_section: 让 32B 生成完整节内容
- match_books_finalize: 让 7B 从搜索结果推断匹配书籍

ContextVar 全景：
  新增 6 个：_search_accumulator(tools.py), _comprehension, _generated_section,
           _state_snapshot, _generation_call_count, _match_books_result
  已有 5 个：_http_client_ctx, _tool_call_state, _progress_callback, _progress_ctx, _prompt_manager
"""

import asyncio
import contextvars
import json
import logging
from typing import Any, Dict, List, Optional

from langchain_core.tools import tool

from src.core.knowledge_qa.prompts.templates import (
    COMPREHEND_SYSTEM,
    GENERATE_SECTION_SYSTEM,
)
from src.core.knowledge_qa.tools import get_search_accumulator
from src.utils.logger import logger

# ==================== ContextVar 定义 ====================

# 理解结果暂存（使用 dict 包装器确保跨 Task 可见）
_comprehension: contextvars.ContextVar[Optional[Dict]] = (
    contextvars.ContextVar("kqa_comprehension", default=None)
)

# 生成结果暂存（使用 dict 包装器确保跨 Task 可见）
_generated_section: contextvars.ContextVar[Optional[Dict]] = (
    contextvars.ContextVar("kqa_generated_section", default=None)
)

# 状态快照（question + matched_book_ids + 前序节输出）
_state_snapshot: contextvars.ContextVar[Optional[dict]] = (
    contextvars.ContextVar("kqa_state_snapshot", default=None)
)

# generate_section 调用计数（使用 dict 包装器确保跨 Task 可见）
_generation_call_count: contextvars.ContextVar[Optional[Dict]] = (
    contextvars.ContextVar("kqa_gen_count", default=None)
)

# match_books 匹配结果暂存
_match_books_result: contextvars.ContextVar[Optional[list]] = (
    contextvars.ContextVar("kqa_match_books_result", default=None)
)


# ==================== Helper 函数 ====================

def init_comprehension():
    _comprehension.set({})

def get_comprehension() -> Optional[str]:
    c = _comprehension.get()
    return c.get("text") if c else None

def clear_comprehension():
    _comprehension.set(None)

def init_generated_section():
    _generated_section.set({})

def get_generated_section() -> Optional[dict]:
    g = _generated_section.get()
    if g and g.get("data"):
        return {"section_type": g.get("section_type"), "data": g.get("data")}
    return None

def clear_generated_section():
    _generated_section.set(None)

def set_state_snapshot(snapshot: dict):
    _state_snapshot.set(snapshot)

def get_state_snapshot() -> Optional[dict]:
    return _state_snapshot.get()

def clear_state_snapshot():
    _state_snapshot.set(None)

def init_gen_count():
    _generation_call_count.set({"value": 0})

def clear_gen_count():
    _generation_call_count.set(None)

def init_match_books_result():
    _match_books_result.set(None)

def get_match_books_result() -> Optional[list]:
    return _match_books_result.get()

def clear_match_books_result():
    _match_books_result.set(None)


# ==================== 子 Agent 工具 ====================


@tool
async def comprehend_results(focus_areas: str) -> str:
    """让专家深度分析已搜索到的书籍内容，提取关键事实和信息缺口。

    调用时机：在 search_knowledge_base 积累了足够搜索结果后调用。
    此工具会调用 32B 模型仔细阅读所有搜索结果，输出结构化的理解摘要。

    Args:
        focus_areas: 重点关注方向，如 "关于ADHD儿童运动干预的具体建议和训练参数"
    """
    logger.info(f"comprehend_results 被调用: focus_areas={focus_areas[:100]}")
    results = get_search_accumulator()
    if not results:
        return "尚未搜索到任何结果，请先调用 search_knowledge_base。"

    # 按 chunk_id 去重（优先保留 score 高的）
    seen: set[str] = set()
    deduped: List[Dict] = []
    for r in sorted(results, key=lambda x: x.get("score", 0) or 0, reverse=True):
        cid = r.get("id") or r.get("chunk_id") or json.dumps(r, sort_keys=True, default=str)
        if cid not in seen:
            seen.add(cid)
            deduped.append(r)

    # 构建结构化上下文（限制总长度避免超 token）
    context_parts = []
    total_chars = 0
    max_chars = 12000
    for r in deduped:
        entry = (
            f"[{r.get('source_book', '未知')}] {r.get('chapter_title', '未知')}\n"
            f"{r.get('content', '') or ''}\n"
        )
        if total_chars + len(entry) > max_chars:
            context_parts.append(f"... (共 {len(deduped)} 条，已截断至 {len(context_parts)} 条)")
            break
        context_parts.append(entry)
        total_chars += len(entry)

    context_text = "\n---\n".join(context_parts)

    user_message = f"""请分析以下书籍片段，重点关注：{focus_areas}

## 书籍片段
{context_text}

请按以下格式输出分析结果：
1. 关键事实 (key_facts)
2. 信息缺口 (info_gaps)
3. 覆盖度评估 (coverage): 充分 / 部分 / 不足
4. 建议补充方向 (suggestions)"""

    from src.core.llm.factory import LLMServiceFactoryCompat

    try:
        model = LLMServiceFactoryCompat.create_raw(
            model_name="qwen3.5-27b",
            temperature=0.3,
        )
        response = await asyncio.wait_for(
            model.ainvoke([
                {"role": "system", "content": COMPREHEND_SYSTEM},
                {"role": "user", "content": user_message},
            ]),
            timeout=30,
        )
        comprehension_text = response.content if hasattr(response, "content") else str(response)
        c = _comprehension.get()
        if c is not None:
            c["text"] = comprehension_text
        # 返回精简摘要给协调器
        preview = comprehension_text[:800] + ("..." if len(comprehension_text) > 800 else "")
        return preview

    except asyncio.TimeoutError:
        logger.warning("comprehend_results 超时 (30s)")
        fallback = (
            f"comprehend_results 暂不可用：理解超时。"
            f"已搜索到 {len(deduped)} 条结果，覆盖 "
            f"{len(set(r.get('source_book', '') for r in deduped))} 本书。"
            f"请直接调用 generate_section。"
        )
        return fallback
    except Exception as e:
        logger.warning(f"comprehend_results 异常: {type(e).__name__}: {e}")
        fallback = (
            f"comprehend_results 暂不可用：{type(e).__name__}。"
            f"已搜索到 {len(deduped)} 条结果。请基于搜索摘要直接调用 generate_section。"
        )
        return fallback


@tool
async def generate_section(section_type: str) -> str:
    """基于搜索结果和理解摘要，生成完整的节内容（结构化输出）。

    必须是协调器工作流的最后一步。调用后任务结束。

    Args:
        section_type: 节类型标识。
            "section_1" / "section_2" / "section_3" / "section_5" — 标准节
            "section_4_outline" — 第 4 节大纲（存入 state.section_4_outline）
            "section_4_expand" — 第 4 节展开（正常写入 sections[4]）
    """
    logger.info(f"generate_section 被调用: section_type={section_type}")
    # 代码层防重复调用（使用 dict wrapper 确保跨 Task 可见）
    count_dict = _generation_call_count.get()
    if count_dict is None:
        logger.warning("generate_section: _generation_call_count 未初始化")
        return "generate_section: 内部错误（调用计数器未初始化）。"
    current = count_dict.get("value", 0)
    if current >= 1:
        logger.warning(f"generate_section 重复调用被拒绝: count={current}")
        return "generate_section 已调用过，请结束任务。"
    count_dict["value"] = current + 1

    state = get_state_snapshot() or {}
    comprehension = get_comprehension()
    results = get_search_accumulator()

    # 提取引用元数据（source_book, chapter_title 去重列表）
    book_chapters: List[Dict[str, str]] = []
    seen_meta: set[str] = set()
    for r in results:
        key = f"{r.get('source_book', '')}|{r.get('chapter_title', '')}"
        if key not in seen_meta:
            seen_meta.add(key)
            book_chapters.append({
                "source_book": r.get("source_book", ""),
                "chapter_title": r.get("chapter_title", ""),
            })

    # 加载节特定的 prompt 模板
    prompt_key = _section_type_to_prompt_key(section_type)
    output_schema = _section_type_to_output_schema(section_type)
    section_prompt = _get_section_prompt(prompt_key)

    # 构建 prompt：理解摘要 + 引用元数据 + 前序节 + 知识上下文
    comprehension_block = comprehension or "（跳过理解阶段，基于搜索摘要直接生成）"
    meta_block = "\n".join(
        f"- {m['source_book']}: {m['chapter_title']}" for m in book_chapters[:20]
    )
    prev_sections_block = _build_previous_sections_block(state)
    knowledge_context = state.get("knowledge_context", "")

    user_message = f"""## 问题
{state.get('question', '')}

## 引用元数据（可从以下来源引用）
{meta_block if meta_block else '（无搜索结果）'}

## 理解摘要
{comprehension_block}

## 前序节内容
{prev_sections_block if prev_sections_block else '（无前序节）'}

## 知识上下文（预取）
{knowledge_context if knowledge_context else '（无）'}

请基于以上资料，生成完整的节内容。"""

    from src.core.llm.factory import LLMServiceFactoryCompat

    try:
        model = LLMServiceFactoryCompat.create_raw(
            model_name="qwen3.5-27b",
            temperature=0.5,
        )

        if output_schema is not None:
            structured_model = model.with_structured_output(output_schema)
            response = await asyncio.wait_for(
                structured_model.ainvoke([
                    {"role": "system", "content": section_prompt},
                    {"role": "user", "content": user_message},
                ]),
                timeout=60,
            )
        else:
            # section_4_outline 无专用 response_format，用 Section4OutlineResponse
            from src.schemas.knowledge_qa import Section4OutlineResponse
            structured_model = model.with_structured_output(Section4OutlineResponse)
            response = await asyncio.wait_for(
                structured_model.ainvoke([
                    {"role": "system", "content": section_prompt},
                    {"role": "user", "content": user_message},
                ]),
                timeout=60,
            )

        data = response.model_dump() if hasattr(response, "model_dump") else response
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except Exception:
                data = {"title": "", "content": data, "citations": [], "structured_data": {}}

        citations_count = len(data.get("citations", []))
        content_len = len(data.get("content", ""))

        g = _generated_section.get()
        if g is not None:
            g["section_type"] = section_type
            g["data"] = data
        logger.info(f"generate_section 成功存储结果: section_type={section_type}, content_len={content_len}")
        section_names = {
            "section_1": "第1节", "section_2": "第2节", "section_3": "第3节",
            "section_4_outline": "第4节大纲", "section_4_expand": "第4节", "section_5": "第5节",
        }
        sec_label = section_names.get(section_type, "本节")
        return f"{sec_label}生成完成：{content_len}字，含{citations_count}条引用"

    except asyncio.TimeoutError:
        logger.warning(f"generate_section 超时 (60s)，生成降级内容")
        return _generate_fallback_section(section_type, "生成超时 (60s)")
    except Exception as e:
        logger.exception(f"generate_section 异常: {type(e).__name__}: {e}")
        return _generate_fallback_section(section_type, f"生成异常: {type(e).__name__}")


@tool
async def match_books_finalize() -> str:
    """从搜索累加器中提取匹配书籍并结构化输出。

    在 match_books 协调器完成搜索后调用。输出存入 _match_books_result ContextVar。
    """
    results = get_search_accumulator()
    if not results:
        _match_books_result.set([])
        return "未搜索到任何结果，无法匹配书籍。"

    # 提取唯一的 source_book 列表
    source_books: Dict[str, int] = {}
    for r in results:
        sb = r.get("source_book", "")
        if sb:
            source_books[sb] = source_books.get(sb, 0) + 1

    from src.core.llm.factory import LLMServiceFactoryCompat

    user_message = f"""从搜索结果中提取到的书籍文件名和命中次数：
{json.dumps(source_books, ensure_ascii=False)}

请为每本书：
1. 推断一个有意义的书名（去掉文件扩展名，根据内容推测）
2. 判断匹配理由（如 "与问题中的运动干预主题高度相关"）
3. 按命中次数排序，命中最多的为主参考书

输出格式：每行一个书名，格式为 "书名 (文件名) — 匹配理由" """

    try:
        model = LLMServiceFactoryCompat.create_raw(
            model_name="qwen3.5-27b",
            temperature=0.3,
        )
        response = await asyncio.wait_for(
            model.ainvoke([
                {"role": "system", "content": "你是一个文献检索助手。根据书籍文件名推断书名和匹配理由。"},
                {"role": "user", "content": user_message},
            ]),
            timeout=15,
        )
        text = response.content if hasattr(response, "content") else str(response)

        # 解析 LLM 输出为结构化列表
        matched = []
        sorted_books = sorted(source_books.items(), key=lambda x: x[1], reverse=True)
        for i, (file_name, hit_count) in enumerate(sorted_books):
            title = file_name.rsplit(".", 1)[0] if "." in file_name else file_name
            matched.append({
                "book_id": file_name,
                "title": title,
                "author": None,
                "source_type": "book",
                "match_reason": f"搜索结果命中 {hit_count} 次" + ("，主参考书" if i == 0 else ""),
            })

        _match_books_result.set(matched)
        return json.dumps({"matched_books": [m["title"] for m in matched], "count": len(matched)}, ensure_ascii=False)

    except asyncio.TimeoutError:
        # 降级：直接从 source_books 构建
        matched = []
        sorted_books = sorted(source_books.items(), key=lambda x: x[1], reverse=True)
        for i, (file_name, hit_count) in enumerate(sorted_books):
            title = file_name.rsplit(".", 1)[0] if "." in file_name else file_name
            matched.append({
                "book_id": file_name,
                "title": title,
                "author": None,
                "source_type": "book",
                "match_reason": f"搜索结果命中 {hit_count} 次" + ("，主参考书" if i == 0 else ""),
            })
        _match_books_result.set(matched)
        return json.dumps({"matched_books": [m["title"] for m in matched], "count": len(matched), "note": "超时降级"}, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"match_books_finalize 异常: {type(e).__name__}: {e}")
        _match_books_result.set([])
        return f"match_books_finalize 失败: {type(e).__name__}"


# ==================== 内部辅助函数 ====================


def _section_type_to_prompt_key(section_type: str) -> str:
    mapping = {
        "section_1": "section_1",
        "section_2": "section_2",
        "section_3": "section_3",
        "section_4_outline": "section_4_outline",
        "section_4_expand": "section_4_expand",
        "section_5": "section_5",
    }
    return mapping.get(section_type, "section_1")


def _section_type_to_output_schema(section_type: str):
    from src.schemas.knowledge_qa import (
        Section1Response,
        Section2Response,
        Section3Response,
        Section4Response,
        Section5Response,
    )
    mapping = {
        "section_1": Section1Response,
        "section_2": Section2Response,
        "section_3": Section3Response,
        "section_4_outline": None,  # 特殊处理
        "section_4_expand": Section4Response,
        "section_5": Section5Response,
    }
    return mapping.get(section_type)


def _get_section_prompt(prompt_key: str) -> str:
    from src.core.knowledge_qa.prompts.templates import PROMPT_TEMPLATES
    templates = PROMPT_TEMPLATES.get(prompt_key)
    if templates:
        return templates["system"]
    return GENERATE_SECTION_SYSTEM


def _build_previous_sections_block(state: dict) -> str:
    sections = state.get("sections", {})
    if not sections:
        return ""
    parts = []
    for i in range(1, 6):
        sec = sections.get(i)
        if sec:
            sec_content = sec.content if hasattr(sec, "content") else sec.get("content", "")
            parts.append(f"## 第{i}节\n{sec_content[:500]}")
    return "\n\n".join(parts)


def _generate_fallback_section(section_type: str, reason: str) -> str:
    section_names = {
        "section_1": "孩子状态分析",
        "section_2": "问题识别",
        "section_3": "运动类型推荐",
        "section_4_outline": "运动方案大纲",
        "section_4_expand": "运动方案",
        "section_5": "最终结论",
    }
    name = section_names.get(section_type, section_type)
    g = _generated_section.get()
    if g is not None:
        g["section_type"] = section_type
        g["data"] = {
            "title": name,
            "content": f"本节因 {reason} 未能完成生成。",
            "citations": [],
            "structured_data": {},
        }
    return f"generate_section 失败：{reason}。已生成降级占位内容。"
