"""S1/S2 引用独立生成节点

方案: S1/S2 正文与引用分离——正文节点只生成 content + structured_data，
引用节点单独负责从知识库检索结果中逐字复制 excerpt 并生成 citations[]。

与 S4 citations 相同的模式：拿到正文 + 搜索结果 → 仅输出 citations[]。
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


class SectionCitationsResponse(BaseModel):
    """通用引用生成 response_format — 仅输出 citations，不输出正文"""

    citations: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="引用列表，每条含 citation_id/book_title/chapter/excerpt/relevance",
    )

    @field_validator("citations", mode="before")
    @classmethod
    def _parse_citations(cls, v):
        return _parse_list(v)


async def _generate_citations_for_section(
    state: KnowledgeQAState,
    section_index: int,
    section_label: str,
) -> Dict[str, Any]:
    """为指定节独立生成引用。

    单一职责：拿到正文 + 知识库检索结果 → 仅输出 citations[]。
    不要求 LLM 生成正文，全部注意力放在 excerpt 逐字复制 + chapter 非空上。
    """
    section = state.sections.get(section_index)
    if not section or not section.content:
        logger.info("generate_s%d_citations: 内容为空，跳过", section_index)
        return {"current_step": [f"s{section_index}_citations_skipped"]}

    await push_progress(
        f"s{section_index}_citations",
        f"正在为{section_label}生成引用依据…",
    )

    # 1. 从正文提取内联引用标记
    markers = re.findall(r"\[?(C\d+)\]?", section.content)
    unique_markers = list(dict.fromkeys(markers))
    logger.info(
        "S%d 正文发现 %d 个唯一引用标记: %s",
        section_index, len(unique_markers), unique_markers[:10],
    )

    # 2. 搜索知识库获取原文
    search_parts = []
    if state.knowledge_context:
        search_parts.append(state.knowledge_context[:5000])

    try:
        bundle = getattr(state, "knowledge_bundle", None)
        if bundle is not None:
            from src.core.knowledge_qa.bundle_consumer import (
                extract_for_section, build_priority_context,
            )
            section_passages = extract_for_section(bundle, section_index, state.question)
            if section_passages:
                context = build_priority_context(
                    bundle=bundle,
                    section_passages=section_passages,
                    section_index=section_index,
                    custom_knowledge_context=getattr(state, "custom_knowledge_context", "") or "",
                    knowledge_context=getattr(state, "knowledge_context", "") or "",
                )
                if context:
                    search_parts.append(context)
                logger.info(
                    "S%d 引用 Bundle 模式: %d passages",
                    section_index, len(section_passages),
                )
        else:
            # 旧版模式：按节搜索
            search_query = state.section_queries.get(section_index, state.question)
            search_results = await _direct_search(
                search_query, state.matched_book_ids, state=state,
            )
            if search_results:
                search_parts.append(_format_search_context(search_results))
            logger.info(
                "S%d 引用旧版模式: %d 条搜索结果",
                section_index, len(search_results),
            )
    except Exception as e:
        logger.warning("S%d 引用搜索失败: %s", section_index, e)

    search_context = "\n\n".join(search_parts) if search_parts else "（无可用上下文）"

    # 3. 构建引用生成 prompt
    prompt = await _get_prompt_pair(f"section_{section_index}_citations")
    system_prompt = prompt.get("system", "")
    if not system_prompt:
        # 降级：模板不存在时使用通用默认值
        system_prompt = (
            f"你是一个学术引用专家。你的唯一任务是为{section_label}正文生成引用列表。\n"
            "硬性规则：\n"
            "1. excerpt 必须从下方检索结果原文中逐字复制（≥15字符），禁止编造或改写\n"
            "2. chapter 必须非空\n"
            "3. citation_id 与正文中的 [C00X] 标记一一对应\n"
            "4. 如果无法在检索结果中找到对应原文，不要生成该条引用\n"
            "输出 citations 数组，每条包含 citation_id, book_title, chapter, excerpt, relevance。"
        )

    # 4. 提取正文中包含引用标记的上下文段落（减少 token 消耗）
    content_lines = section.content.split("\n")
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
        else section.content[:5000]
    )

    marker_hint = (
        f"共发现 {len(unique_markers)} 个引用标记: {', '.join(unique_markers[:15])}。"
        f"请为每个标记生成一条 citation。"
        if unique_markers
        else "正文中未检测到引用标记，请根据正文内容与检索结果的匹配度自行确定引用位置和编号。"
    )

    # 使用模板渲染 user_message（模板含 {content_snippet}, {search_context}, {marker_hint} 占位符）
    user_template = prompt.get("user_template", "")
    if user_template:
        user_message = user_template.format(
            content_snippet=content_snippet,
            search_context=search_context,
            marker_hint=marker_hint,
        )
    else:
        # 降级：模板不存在时硬编码
        user_message = (
            f"## {section_label}正文（含引用标记）\n{content_snippet}\n\n"
            f"## 知识库检索结果\n{search_context}\n\n{marker_hint}"
        )

    # 5. LLM 调用
    try:
        # S5 需要综合前 4 节内容，输出压力大，放宽超时
        timeout = 90 if section_index == 5 else 45
        response = await _invoke_llm_structured(
            system_prompt=system_prompt,
            user_message=user_message,
            response_format=SectionCitationsResponse,
            step_label=f"generate_s{section_index}_citations",
            timeout_seconds=timeout,
        )

        data = response.model_dump() if hasattr(response, "model_dump") else response
        if isinstance(data, str):
            try:
                from json_repair import repair_json
                data = json.loads(repair_json(data))
            except Exception:
                data = {"citations": []}

        new_citations = data.get("citations", [])

        # 确保每条 citation 都有 citation_id
        for i, c in enumerate(new_citations):
            if not c.get("citation_id"):
                c["citation_id"] = f"C{i+1:03d}"

        logger.info("S%d 引用生成完成: %d 条", section_index, len(new_citations))

        # 6. 合并回 section
        sections = dict(state.sections)
        updated = SectionOutput(
            index=section.index,
            title=section.title,
            content=section.content,
            citations=new_citations,
            structured_data=section.structured_data,
        )
        sections[section_index] = updated

        await push_progress(
            f"s{section_index}_citations_done",
            f"{section_label}引用生成完成 ({len(new_citations)} 条)",
        )

        return {
            "sections": sections,
            "current_step": [f"s{section_index}_citations_done"],
        }

    except asyncio.TimeoutError:
        logger.warning("generate_s%d_citations 超时", section_index)
        return {
            "errors": state.errors + [f"s{section_index}_citations_timeout"],
            "current_step": [f"s{section_index}_citations_timeout"],
            "partial": True,
        }
    except Exception as e:
        logger.exception("generate_s%d_citations 失败", section_index)
        return {
            "errors": state.errors + [
                f"s{section_index}_citations_failed: {_sanitize_error(str(e))}"
            ],
            "current_step": [f"s{section_index}_citations_failed"],
            "partial": True,
        }


async def generate_s1_citations_node(state: KnowledgeQAState) -> Dict[str, Any]:
    """为 S1 独立生成引用。"""
    return await _generate_citations_for_section(state, 1, "孩子状态分析")


async def generate_s2_citations_node(state: KnowledgeQAState) -> Dict[str, Any]:
    """为 S2 独立生成引用。"""
    return await _generate_citations_for_section(state, 2, "问题识别")


async def generate_s5_citations_node(state: KnowledgeQAState) -> Dict[str, Any]:
    """为 S5 独立生成引用。"""
    return await _generate_citations_for_section(state, 5, "最终结论")
