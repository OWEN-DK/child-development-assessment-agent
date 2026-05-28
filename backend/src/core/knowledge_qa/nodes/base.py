"""Agent 节点工厂与通用执行逻辑

重构: 去掉 7B 协调器。qwen-turbo 已统一切换为 qwen3.5-27b。
改为: Python 直接搜索 + 27B 单次 structured_output 调用。
"""

import asyncio
import json
import string
import logging
import difflib
from pathlib import Path
from typing import Any, Callable, Dict, List, Type

from pydantic import BaseModel

from src.core.knowledge_qa.prompts.templates import PROMPT_TEMPLATES
from src.schemas.knowledge_qa import (
    KnowledgeQAState,
    SectionOutput,
    get_prompt_manager,
    push_progress,
)

logger = logging.getLogger(__name__)

NODE_TEMPERATURES_DEFAULT = {
    "match_books": 0.3,
    "analyze_child": 0.5,
    "identify_problems": 0.5,
    "recommend_types": 0.5,
    "plan_outline": 0.5,
    "plan_expand_content": 0.3,
    "conclusion": 0.3,
}

NODE_TIMEOUT_SECONDS = {
    "match_books": 40,
    "prefetch_context": 30,
    "analyze_child": 90,
    "identify_problems": 90,
    "recommend_types": 90,
    "plan_outline": 90,
    "plan_expand_content": 90,
    "conclusion": 90,
}
SECTION_TIMEOUT_SECONDS = 90


def get_timeout(step_label: str) -> int:
    return NODE_TIMEOUT_SECONDS.get(step_label, SECTION_TIMEOUT_SECONDS)


async def _get_prompt_pair(prompt_key: str) -> Dict[str, str]:
    """获取 prompt 对 (system + user_template)。

    优先级：templates.py（文件默认）为主，MySQL 仅在管理员显式覆盖时使用。
    判定依据：DB 内容 ≠ 文件默认 → 管理员手动编辑过 → 使用 DB。
    DB 内容 = 文件默认或为空 → 使用文件（确保代码更新即刻生效）。
    """
    templates = PROMPT_TEMPLATES.get(prompt_key)
    fallback_system = templates["system"] if templates else "You are a helpful assistant."
    fallback_user = templates["user_template"] if templates else "{question}"

    # 默认使用文件内容
    system = fallback_system
    user_template = fallback_user

    try:
        pm = get_prompt_manager()
        db_system = await pm.get_prompt(prompt_key=f"knowledge_qa_{prompt_key}_system")
        # DB 内容与文件默认不同 → 管理员显式覆盖，使用 DB
        if db_system and db_system not in ("You are a helpful assistant.", fallback_system):
            system = db_system

        db_user = await pm.get_prompt(prompt_key=f"knowledge_qa_{prompt_key}_user")
        if db_user and db_user not in ("You are a helpful assistant.", fallback_user):
            user_template = db_user
    except Exception as e:
        logger.warning(f"获取数据库 prompt 失败 [{prompt_key}]: {e}，使用内置模板")

    return {"system": system, "user_template": user_template}


async def _get_temperature(step_label: str) -> float:
    """获取节点 temperature"""
    try:
        pm = get_prompt_manager()
        temp_str = await pm.get_prompt(prompt_key=f"knowledge_qa_{step_label}_temperature")
        if temp_str and temp_str != "You are a helpful assistant.":
            try:
                return float(temp_str.strip())
            except ValueError:
                pass
    except Exception:
        pass
    return NODE_TEMPERATURES_DEFAULT.get(step_label, 0.5)


async def _get_model_name(step_label: str) -> str:
    """获取模型名称。与 _get_temperature 对称，优先从 prompt manager 获取。"""
    try:
        pm = get_prompt_manager()
        name = await pm.get_prompt(prompt_key=f"knowledge_qa_{step_label}_model_name")
        if name and name.strip() and name != "You are a helpful assistant.":
            return name.strip()
    except Exception:
        pass
    return "qwen3.5-27b"


async def _invoke_llm_structured(
    system_prompt: str,
    user_message: str,
    response_format: Type[BaseModel],
    step_label: str,
    *,
    max_retries: int = 1,
    timeout_seconds: int | None = None,
) -> BaseModel:
    """统一 structured_output LLM 调用，含重试（仅限瞬时错误）。

    - 对 TimeoutError 和网络错误 (ConnectionError, OSError) 重试 max_retries 次
    - 其他异常（如 Pydantic 校验失败）不重试，直接抛出
    """
    from src.core.llm.factory import LLMServiceFactoryCompat

    if timeout_seconds is None:
        timeout_seconds = get_timeout(step_label)

    model_name = await _get_model_name(step_label)
    temperature = await _get_temperature(step_label)

    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            model = LLMServiceFactoryCompat.create_raw(
                model_name=model_name, temperature=temperature,
            )
            structured_model = model.with_structured_output(response_format)
            return await asyncio.wait_for(
                structured_model.ainvoke([
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ]),
                timeout=timeout_seconds,
            )
        except asyncio.TimeoutError:
            last_error = asyncio.TimeoutError(f"LLM 超时 {timeout_seconds}s, step={step_label}")
            if attempt < max_retries:
                logger.warning(f"LLM 超时 (attempt {attempt+1}/{max_retries+1}), step={step_label}")
                continue
            raise last_error
        except (ConnectionError, OSError) as e:
            last_error = e
            if attempt < max_retries:
                logger.warning(f"LLM 网络错误 (attempt {attempt+1}/{max_retries+1}): {e}")
                await asyncio.sleep(1)
                continue
            raise
        # 其他异常不重试
        raise
    raise last_error  # type: ignore[misc]  # unreachable safety


async def _invoke_llm_plain(
    prompt: str,
    step_label: str,
    *,
    max_retries: int = 1,
    timeout_seconds: int = 15,
) -> str:
    """统一纯文本 LLM 调用，含重试（仅限瞬时错误）。返回 response.content。"""
    from src.core.llm.factory import LLMServiceFactoryCompat

    model_name = await _get_model_name(step_label)
    temperature = await _get_temperature(step_label)

    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            model = LLMServiceFactoryCompat.create_raw(
                model_name=model_name, temperature=temperature,
            )
            response = await asyncio.wait_for(
                model.ainvoke(prompt),
                timeout=timeout_seconds,
            )
            return response.content if hasattr(response, "content") else str(response)
        except asyncio.TimeoutError:
            last_error = asyncio.TimeoutError(f"LLM 超时 {timeout_seconds}s, step={step_label}")
            if attempt < max_retries:
                logger.warning(f"LLM 超时 (attempt {attempt+1}/{max_retries+1}), step={step_label}")
                continue
            raise last_error
        except (ConnectionError, OSError) as e:
            last_error = e
            if attempt < max_retries:
                logger.warning(f"LLM 网络错误 (attempt {attempt+1}/{max_retries+1}): {e}")
                await asyncio.sleep(1)
                continue
            raise
        raise
    raise last_error  # type: ignore[misc]  # unreachable safety


async def _direct_search(question: str, book_ids: List[str]) -> List[Dict]:
    """直接搜索知识库（通过 HTTP 调用 RAG 端点）。"""
    import httpx
    from src.config import settings

    host = getattr(settings, "app_host", "127.0.0.1")
    port = getattr(settings, "app_port", 8000)
    # 0.0.0.0 是监听地址，不能用于主动连接；Docker 环境下常见此配置
    if host == "0.0.0.0":
        host = "127.0.0.1"

    queries = [question]
    short = " ".join(question.replace("，", " ").replace("、", " ").split()[:10])
    if short and short != question:
        queries.append(short)

    all_results: List[Dict] = []
    seen_ids: set[str] = set()

    async with httpx.AsyncClient(
        base_url=f"http://{host}:{port}",
        timeout=httpx.Timeout(10.0),
    ) as client:
        for query in queries[:2]:
            await push_progress(
                "searching",
                f"正在检索知识库: {query[:60]}…",
            )
            try:
                params: Dict[str, Any] = {"query": query, "limit": 15}
                if book_ids:
                    params["book_ids"] = ",".join(book_ids)
                resp = await client.get("/rag/search", params=params)
                resp.raise_for_status()
                data = resp.json()
                results = data.get("data", {}).get("results", [])
                logger.info(f"_direct_search '{query[:50]}' → {len(results)} 条")
                await push_progress(
                    "search_done",
                    f"检索完成: {len(results)} 条结果",
                )
            except Exception as e:
                logger.warning(f"_direct_search 失败 (query={query[:50]}): {e}")
                continue

            for r in results:
                rid = r.get("id", "")
                if rid and rid not in seen_ids:
                    seen_ids.add(rid)
                    all_results.append(r)

    return all_results


def _normalize_book_title(raw: str) -> str:
    """规范化书名：去文件扩展名 + trim + 去首尾空白。

    "运动改变大脑 .epub" → "运动改变大脑"
    "学习如何学习.epub" → "学习如何学习"
    """
    if not raw:
        return "未知"
    name = raw.strip()
    for ext in (".epub", ".pdf", ".txt", ".md", ".docx", ".html", ".mobi"):
        if name.lower().endswith(ext):
            name = name[:-len(ext)]
            break
    return name.strip()


def _format_search_context(results: List[Dict]) -> str:
    """将搜索结果格式化为 LLM 可读的上下文。

    关键：字段名映射为输出 schema 对应的字段名，避免 LLM 混淆。
    source_book → book_title (已规范化，去扩展名), chapter_title → chapter
    """
    if not results:
        return "（未搜索到相关内容）"

    seen: set[str] = set()
    parts: List[str] = []
    total_chars = 0
    max_chars = 10000

    for r in sorted(results, key=lambda x: x.get("score", 0) or 0, reverse=True):
        cid = r.get("id") or r.get("chunk_id") or ""
        if cid in seen:
            continue
        seen.add(cid)
        source = _normalize_book_title(r.get("source_book", ""))
        chapter = r.get("chapter_title", "未知")
        entry = (
            f"--- book_title=\"{source}\" | "
            f"chapter=\"{chapter}\" ---\n"
            f"{r.get('content', '') or ''}\n"
        )
        if total_chars + len(entry) > max_chars:
            parts.append(f"\n... (共 {len(results)} 条，已截断至 {len(parts)} 条)")
            break
        parts.append(entry)
        total_chars += len(entry)

    parts.append(
        "\n> 引用提示：citations 中每条必须包含 book_title, chapter, excerpt, relevance 字段。"
        "book_title 使用上方已规范化的书名（不含文件扩展名），chapter 使用上方的章节名。"
        "excerpt 必须从上方结果中的原文逐字复制，不允许改写或概括。"
    )
    return "\n".join(parts)


def _build_full_user_message(
    user_message_from_template: str,
    search_context: str,
    previous_sections: Dict[int, SectionOutput],
    knowledge_context: str,
    exercise_context: str = "",
) -> str:
    """构建完整的 user message：模板内容 + 搜索上下文 + 前序节 + 运动清单约束(S3/S4)。"""
    parts = [user_message_from_template]

    if search_context and search_context != "（未搜索到相关内容）":
        parts.append(f"\n\n## 知识库检索结果\n{search_context}")

    if previous_sections:
        prev_parts = []
        for i in sorted(previous_sections.keys()):
            sec = previous_sections[i]
            if sec and sec.content:
                prev_parts.append(f"### 第{i}节\n{sec.content[:800]}")
        if prev_parts:
            parts.append(f"\n\n## 前序节内容\n" + "\n\n".join(prev_parts))

    if knowledge_context:
        parts.append(f"\n\n## 知识上下文（预取）\n{knowledge_context}")

    if exercise_context:
        parts.append(f"\n\n{exercise_context}")

    return "\n\n".join(parts)


async def _build_empty_search_fallback(
    state: KnowledgeQAState,
    section_index: int,
    section_label: str,
) -> Dict[str, Any]:
    """知识库搜索为空时，跳过 LLM 生成，直接返回无引用空节。"""
    await push_progress(
        f"section_{section_index}_done",
        f"第 {section_index} 节：{section_label}已跳过（知识库无数据）",
    )
    content = (
        f"## {section_label}\n\n"
        f"知识库中未找到与此节相关的专业依据，无法生成有引用的内容。\n\n"
        f"> 请联系管理员上传相关书籍资料后重试。"
    )
    sections = dict(state.sections)
    sections[section_index] = SectionOutput(
        index=section_index,
        title=section_label,
        content=content,
        citations=[],
        structured_data={},
    )
    return {
        "sections": sections,
        "errors": state.errors + [f"section_{section_index}_empty_search"],
        "current_step": [f"section_{section_index}_done"],
        "partial": True,
    }


def _section_fallback(
    state: KnowledgeQAState,
    section_index: int,
    section_label: str,
    error: str,
) -> Dict[str, Any]:
    """降级：生成失败时构建有意义的占位内容。"""
    safe_error = _sanitize_error(error)
    content = (
        f"本节生成失败。\n\n"
        f"原因：{safe_error}\n\n"
        f"> 请稍后重试或联系管理员。"
    )

    sections = dict(state.sections)
    sections[section_index] = SectionOutput(
        index=section_index,
        title=section_label,
        content=content,
        citations=[],
        structured_data={},
    )
    return {
        "sections": sections,
        "errors": state.errors + [f"section_{section_index}_failed: {error}"],
        "current_step": [f"section_{section_index}_failed"],
        "partial": True,
    }


def _sanitize_error(error: str) -> str:
    safe_map = {
        "timeout": "生成超时",
        "TimeoutError": "生成超时",
        "生成超时": "生成超时",
        "Agent 未返回结构化响应": "Agent 未返回结构化响应",
        "大纲未生成": "大纲未生成",
        "未返回": "未返回有效响应",
    }
    for keyword, safe_msg in safe_map.items():
        if keyword in error:
            return safe_msg
    return "内部处理异常"




def _safe_format(template: str, **kwargs) -> str:
    """安全 format：忽略模板中存在但 kwargs 中不存在的占位符。"""
    formatter = string.Formatter()
    result = []
    for literal_text, field_name, _, _ in formatter.parse(template):
        result.append(literal_text)
        if field_name is not None:
            result.append(str(kwargs.get(field_name, f"{{{field_name}}}")))
    return "".join(result)


def get_exercise_json_path() -> str:
    """运动清单 JSON 标准路径（单点定义）。"""
    return str(
        Path(__file__).resolve().parent.parent.parent.parent
        / "data" / "运动改变大脑_运动清单.json"
    )



def fuzzy_match_exercise(
    name: str | None, valid_names: list[str], cutoff: float = 0.6
) -> str | None:
    """统一运动名称模糊匹配（精确 → 子串 → difflib）。

    替代 plan_assemble._validate_exercise_names 和
    verify_citations._fuzzy_match_exercise 的重复逻辑。
    """
    if not name or not valid_names:
        return None
    name_lower = name.strip().lower()
    valid_lower = {n.lower().strip(): n for n in valid_names if n.strip()}

    # 1. 精确匹配
    if name_lower in valid_lower:
        return valid_lower[name_lower]

    # 2. 子串匹配
    for vl, vo in valid_lower.items():
        if vl in name_lower or name_lower in vl:
            return vo

    # 3. difflib 序列匹配
    matches = difflib.get_close_matches(
        name, list(valid_lower.keys()), n=1, cutoff=cutoff
    )
    return valid_lower[matches[0]] if matches else None

async def _run_section_node(
    state: KnowledgeQAState,
    section_index: int,
    section_label: str,
    prompt_key: str,
    response_format: Type[BaseModel],
    build_user_message: Callable[[KnowledgeQAState, Dict[str, str]], str],
    step_label: str,
) -> Dict[str, Any]:
    """通用节生成节点：直接搜索 + 27B 单次 structured_output 调用。"""
    from src.core.llm.factory import LLMServiceFactoryCompat

    await push_progress(
        f"section_{section_index}_generating",
        f"正在生成第 {section_index} 节：{section_label}…",
    )

    try:
        # 检查取消信号（通过 progress_context 获取）
        from src.schemas.knowledge_qa import get_progress_context
        ctx = get_progress_context()
        if ctx and ctx.get("cancellation_event") and ctx["cancellation_event"].is_set():
            raise asyncio.CancelledError("任务已被取消")

        # Step 1: 直接搜索知识库
        search_results = await _direct_search(state.question, state.matched_book_ids)
        search_context = _format_search_context(search_results)
        logger.info(
            f"第{section_index}节 _direct_search: {len(search_results)} 条"
        )

        # 空搜索守卫：知识库无结果时跳过 LLM 调用，避免 LLM 编造不存在书籍的引用
        if not search_results:
            logger.warning(f"第{section_index}节知识库无搜索结果，跳过 LLM 调用")
            return await _build_empty_search_fallback(state, section_index, section_label)

        # Step 2: 获取 prompt 模板并构建消息
        prompt = await _get_prompt_pair(prompt_key)
        user_message = build_user_message(state, prompt)

        full_message = _build_full_user_message(
            user_message_from_template=user_message,
            search_context=search_context,
            previous_sections=state.sections,
            knowledge_context=state.knowledge_context or "",
            exercise_context=state.exercise_context if section_index == 3 else "",
        )

        # Step 3: 27B 单次 structured_output 调用
        temperature = await _get_temperature(step_label)
        model = LLMServiceFactoryCompat.create_raw(
            model_name=await _get_model_name(step_label),
            temperature=temperature,
        )
        structured_model = model.with_structured_output(response_format)

        timeout = get_timeout(step_label)
        response = await asyncio.wait_for(
            structured_model.ainvoke([
                {"role": "system", "content": prompt["system"]},
                {"role": "user", "content": full_message},
            ]),
            timeout=timeout,
        )

        # Step 4: 提取数据
        data = response.model_dump() if hasattr(response, "model_dump") else response
        if isinstance(data, str):
            try:
                from json_repair import repair_json
                data = json.loads(repair_json(data))
            except Exception:
                data = {"title": section_label, "content": data, "citations": [], "structured_data": {}}

        section = SectionOutput(
            index=section_index,
            title=data.get("title", section_label),
            content=data.get("content", ""),
            citations=data.get("citations", []),
            structured_data=data.get("structured_data", {}),
        )


        await push_progress(
            f"section_{section_index}_done",
            f"第 {section_index} 节：{section_label}已完成",
            section=section.model_dump(),
        )

        sections = dict(state.sections)
        sections[section_index] = section
        return {"sections": sections, "current_step": [f"section_{section_index}_done"]}

    except asyncio.TimeoutError:
        logger.warning(f"第{section_index}节生成超时 ({timeout}s)")
        return _section_fallback(state, section_index, section_label, "生成超时")
    except Exception as e:
        logger.exception(f"第{section_index}节生成失败")
        return _section_fallback(state, section_index, section_label, str(e))
