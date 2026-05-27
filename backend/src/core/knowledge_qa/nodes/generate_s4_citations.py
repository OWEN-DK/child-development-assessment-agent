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
    try:
        search_results = await _direct_search(search_terms, state.matched_book_ids)
        search_context = _format_search_context(search_results)
        logger.info(f"S4 引用生成搜索: {len(search_results)} 条结果")
    except Exception as e:
        logger.warning(f"S4 引用生成搜索失败: {e}")
        search_context = "（搜索不可用）"

    # 构建轻量级引用生成 prompt
    system_prompt = """你是一个学术引用专家。你的**唯一任务**是为运动方案正文生成完整的引用列表。

## 硬性规则（违反将导致整条引用被丢弃）

1. **excerpt 必须从下方知识库检索结果中逐字复制原文**（≥10字符）。绝不允许改写、概括或自行总结。
2. **chapter 必须非空**。使用检索结果中 --- 分隔线后的 chapter= 字段值（如 "第3章"）。
3. **book_title 使用检索结果中已规范化的书名**（book_title= 字段值），不含文件扩展名。
4. citation_id 与正文中的 [C001]、[C002] 等标记一一对应。
5. relevance 用一句话说明该引用与正文内容的关联。

## 工作步骤

1. 阅读正文，找出每个引用标记附近的观点
2. 在知识库检索结果中寻找支持该观点的原文段落
3. 为每个标记生成一条 citation，excerpt 从检索结果中逐字复制

## 输出格式

仅输出 citations 数组，每条 citation 必须包含全部 5 个字段:
- citation_id: "C001"
- book_title: "运动改变大脑"
- chapter: "第3章"
- excerpt: "原文逐字引用..."
- relevance: "一句话关联说明"

如果正文中没有引用标记，或检索结果中找不到对应原文，返回空数组。不要编造引用。"""

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
        from src.core.llm.factory import LLMServiceFactoryCompat

        temperature = 0.1
        model = LLMServiceFactoryCompat.create_raw(
            model_name="qwen3.5-27b",
            temperature=temperature,
        )
        structured_model = model.with_structured_output(S4CitationsResponse)

        response = await asyncio.wait_for(
            structured_model.ainvoke([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ]),
            timeout=45,
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
