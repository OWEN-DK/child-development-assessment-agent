"""S4 引用独立生成节点

方案 A (gap-analysis-v2 P0#1): S4 引用单独一个轻量 LLM 调用生成。
传入正文+搜索结果，仅要求输出 citations[]，不承担正文生成。
LLM 全部容量用于保证 excerpt 逐字复制 + chapter 非空。
"""

import asyncio
import json
import logging
import re
from typing import Any, Dict, List

from pydantic import BaseModel, Field, field_validator

from src.core.knowledge_qa.nodes.base import (
    _direct_search,
    _format_search_context,
    _get_prompt_pair,
    _invoke_llm_structured,
    _sanitize_error,
)
from src.schemas.knowledge_qa import (
    KnowledgeQAState,
    SectionOutput,
    push_progress,
)

logger = logging.getLogger(__name__)


def _parse_list(v):
    """LLM 有时将列表字段输出为 JSON 字符串"""
    if isinstance(v, str):
        try:
            from json_repair import repair_json
            return json.loads(repair_json(v))
        except Exception:
            return []
    return v


class S4CitationsResponse(BaseModel):
    """S4 引用生成 response_format — 仅输出 citations，不输出正文"""

    citations: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="引用列表，每条含 citation_id/book_title/chapter/excerpt/relevance",
    )

    @field_validator("citations", mode="before")
    @classmethod
    def _parse_citations(cls, v):
        return _parse_list(v)


def _backfill_exercise_citations(s4_section: "SectionOutput", citations: list[dict]):
    """将节级 citations 映射回 structured_data 中每个 exercise 的 citation_ids。

    S4 的 structured_data 含 phases → weeks → days → main_exercises，
    每个 exercise 有 name 字段。将 citations 中 excerpt 匹配运动名的引用 ID 回填。
    """
    sd = s4_section.structured_data or {}

    for phase in sd.get("phases", []):
        for week in phase.get("weeks", []):
            for day in week.get("days", []):
                for ex in day.get("main_exercises", []):
                    ex_name = ex.get("name", "")
                    if not ex_name:
                        continue
                    # 归一化运动名：取第一段（去掉括号说明和斜杠别名）
                    # "弹跳训练/跳跃（模仿羚羊/袋鼠肌腱弹簧）" → "弹跳训练"
                    ex_name_clean = re.split(r"[（/]", ex_name)[0]
                    matched_ids = []
                    for c in citations:
                        excerpt = c.get("excerpt", "")
                        if (ex_name_clean in excerpt or
                            ex_name in excerpt or
                            any(kw in excerpt for kw in ex_name_clean.split() if len(kw) >= 2)):
                            matched_ids.append(c.get("citation_id", ""))
                    ex["citation_ids"] = [cid for cid in matched_ids if cid]


async def generate_s4_citations_node(state: KnowledgeQAState) -> Dict[str, Any]:
    """为 S4 独立生成引用。

    单一职责：拿到 S4 正文 + 知识库检索结果 → 仅输出 citations[]。
    不要求 LLM 生成正文，全部注意力放在 excerpt 逐字复制 + chapter 非空上。
    """
    s4 = state.sections.get(4)
    if not s4 or not s4.content:
        logger.info("generate_s4_citations: S4 内容为空，跳过")
        return {"current_step": ["s4_citations_skipped"]}


    await push_progress("s4_citations", "正在为运动方案生成引用依据…")

    # 从 S4 正文提取内联引用标记
    markers = re.findall(r"\[?(C\d+)\]?", s4.content)
    unique_markers = list(dict.fromkeys(markers))
    logger.info(
        f"S4 正文发现 {len(unique_markers)} 个唯一引用标记: {unique_markers[:10]}"
    )

    # 从 structured_data 提取运动名称作为搜索关键词
    search_terms = state.question
    try:
        sd = s4.structured_data or {}
        ex_names = set()
        for ph in (sd.get("phases") or [])[:2]:
            for wk in (ph.get("weeks") or [])[:2]:
                for day in (wk.get("days") or [])[:2]:
                    for ex in (day.get("main_exercises") or [])[:5]:
                        name = ex.get("name", "")
                        if name:
                            ex_names.add(name)
        if ex_names:
            search_terms = " ".join(list(ex_names)[:8])
    except Exception:
        pass

    # 搜索知识库获取原文
    search_parts = []
    if state.knowledge_context:
        search_parts.append(state.knowledge_context[:5000])
    try:
        bundle = getattr(state, "knowledge_bundle", None)
        if bundle is not None:
            # Bundle 模式：从 Bundle 提取全文 passages
            from src.core.knowledge_qa.bundle_consumer import (
                extract_for_section, build_priority_context,
            )
            section_passages = extract_for_section(bundle, 4, search_terms)
            search_context_part = build_priority_context(
                bundle=bundle, section_passages=section_passages, section_index=4,
            )
            if search_context_part:
                search_parts.append(search_context_part)
            logger.info(
                "S4 引用 Bundle 模式: context=%s, passages=%d",
                bool(state.knowledge_context), len(section_passages),
            )
        else:
            search_results = await _direct_search(search_terms, state.matched_book_ids)
            if search_results:
                search_parts.append(_format_search_context(search_results))
            logger.info(
                f"S4 引用: 预取 context={bool(state.knowledge_context)}, 补充搜索={len(search_results)} 条"
            )
    except Exception as e:
        logger.warning(f"S4 引用搜索失败: {e}")
    search_context = "\n\n".join(search_parts) if search_parts else "（无可用上下文）"

    # 构建轻量级引用生成 prompt
    prompt = await _get_prompt_pair("section_4_citations")
    system_prompt = prompt.get("system", "")
    if not system_prompt:
        # 降级：模板不存在时使用硬编码默认值
        system_prompt = (
            "你是一个学术引用专家。你的唯一任务是为运动方案正文生成完整的引用列表。\n"
            "硬性规则：excerpt 必须从检索结果中逐字复制（≥10字符）；"
            "chapter 必须非空；citation_id 与正文标记一一对应。\n"
            "输出 citations 数组，每条包含 citation_id, book_title, chapter, excerpt, relevance。"
        )

    # 提取正文中包含引用的上下文段落（减少 token 消耗）
    content_lines = s4.content.split("\n")
    relevant_blocks: List[str] = []
    current_block: List[str] = []
    for line in content_lines:
        current_block.append(line)
        if re.search(r"\[?C\d+\]?", line):
            relevant_blocks.extend(current_block)
            current_block = []
    if current_block and len(relevant_blocks) < 10:
        relevant_blocks.extend(current_block[:5])

    content_snippet = (
        "\n".join(relevant_blocks[:120])
        if relevant_blocks
        else s4.content[:5000]
    )

    marker_hint = (
        f"共发现 {len(unique_markers)} 个引用标记: {', '.join(unique_markers[:15])}。"
        f"请为每个标记生成一条 citation。"
        if unique_markers
        else "正文中未检测到引用标记，请根据正文内容与检索结果的匹配度自行确定引用位置和编号。"
    )

    user_message = f"""## 运动方案正文（含引用标记）
{content_snippet}

## 知识库检索结果
{search_context}

{marker_hint}"""

    try:
        response = await _invoke_llm_structured(
            system_prompt=system_prompt,
            user_message=user_message,
            response_format=S4CitationsResponse,
            step_label="generate_s4_citations",
            timeout_seconds=45,
        )

        data = response.model_dump() if hasattr(response, "model_dump") else response
        if isinstance(data, str):
            try:
                from json_repair import repair_json
                data = json.loads(repair_json(data))
            except Exception:
                data = {"citations": []}

        new_citations = data.get("citations", [])

        # 确保每条 citation 都有 citation_id，缺失则自动编号
        for i, c in enumerate(new_citations):
            if not c.get("citation_id"):
                c["citation_id"] = f"C{i+1:03d}"

        logger.info(f"S4 引用生成完成: {len(new_citations)} 条")

        # 回填 exercise citation_ids
        _backfill_exercise_citations(s4, new_citations)

        # 合并回 S4
        sections = dict(state.sections)
        s4_updated = SectionOutput(
            index=4,
            title=s4.title,
            content=s4.content,
            citations=new_citations,
            structured_data=s4.structured_data,
        )
        sections[4] = s4_updated

        await push_progress(
            "s4_citations_done",
            f"S4 引用生成完成 ({len(new_citations)} 条)",
        )

        return {
            "sections": sections,
            "current_step": ["s4_citations_done"],
        }

    except asyncio.TimeoutError:
        logger.warning("generate_s4_citations 超时，S4 引用保持原样")
        return {
            "errors": state.errors + ["s4_citations_timeout"],
            "current_step": ["s4_citations_timeout"],
            "partial": True,
        }
    except Exception as e:
        logger.exception("generate_s4_citations 失败")
        return {
            "errors": state.errors + [f"s4_citations_failed: {_sanitize_error(str(e))}"],
            "current_step": ["s4_citations_failed"],
            "partial": True,
        }
