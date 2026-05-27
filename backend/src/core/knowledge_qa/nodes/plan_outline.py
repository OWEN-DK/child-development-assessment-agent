"""第 4 节大纲：运动方案大纲 — 直接搜索 + 27B 单次生成
始终生成完整运动方案大纲，不再做领域跳过判断。
"""

import asyncio
import json
import logging
from typing import Any, Dict

from src.core.knowledge_qa.nodes.base import (
    _direct_search,
    _format_search_context,
    _get_prompt_pair,
    _get_temperature,
    _sanitize_error,
)
from src.schemas.knowledge_qa import (
    KnowledgeQAState,
    Section4OutlineResponse,
    SectionOutput,
    push_progress,
)

logger = logging.getLogger(__name__)


async def plan_outline_node(state: KnowledgeQAState) -> Dict[str, Any]:
    """第 4 节大纲：设计阶段划分 + 每周主题 + 运动类型名称。
    始终生成运动方案大纲，无论问题是否显式提及运动。
    """
    from src.core.llm.factory import LLMServiceFactoryCompat

    await push_progress("section_4_outline", "正在生成运动方案大纲…")

    try:
        # Step 1: 直接搜索
        search_results = await _direct_search(state.question, state.matched_book_ids)
        search_context = _format_search_context(search_results)

        # Step 2: 构建前序节内容
        s1 = state.sections.get(1)
        s2 = state.sections.get(2)
        s3 = state.sections.get(3)

        # Step 3: 获取 prompt 并生成
        prompt = await _get_prompt_pair("section_4_outline")
        user_message = prompt["user_template"].format(
            question=state.question,
            section_1_content=s1.content if s1 else "",
            section_2_content=s2.content if s2 else "",
            section_3_content=s3.content if s3 else "",
            section_3_structured=json.dumps(
                s3.structured_data if s3 else {}, ensure_ascii=False
            ),
            matched_book_ids=json.dumps(state.matched_book_ids),
            knowledge_context=state.knowledge_context or "",
        )

        full_message = f"{user_message}\n\n## 知识库检索结果\n{search_context}"

        if state.exercise_context:
            full_message += f"\n\n{state.exercise_context}"

        temperature = await _get_temperature("plan_outline")
        model = LLMServiceFactoryCompat.create_raw(
            model_name="qwen3.5-27b",
            temperature=temperature,
        )
        structured_model = model.with_structured_output(Section4OutlineResponse)

        response = await asyncio.wait_for(
            structured_model.ainvoke([
                {"role": "system", "content": prompt["system"]},
                {"role": "user", "content": full_message},
            ]),
            timeout=90,
        )

        data = response.model_dump() if hasattr(response, "model_dump") else response
        if isinstance(data, str):
            data = {"title": "运动方案大纲", "content": data, "citations": [], "structured_data": {}}

        outline_section = SectionOutput(
            index=4,
            title=data.get("title", "运动方案大纲"),
            content=data.get("content", ""),
            citations=data.get("citations", []),
            structured_data=data.get("structured_data", {}),
        )

        await push_progress(
            "section_4_outline_done",
            "运动方案大纲已完成",
            section=outline_section.model_dump(),
        )

        return {
            "section_4_outline": data,
            "current_step": ["section_4_outline_done"],
        }

    except asyncio.TimeoutError:
        logger.warning("plan_outline 超时")
        return {
            "errors": state.errors + ["section_4_outline_failed: 生成超时"],
            "current_step": ["section_4_outline_failed"],
        }
    except Exception as e:
        logger.exception("plan_outline 失败")
        return {
            "errors": state.errors + [f"section_4_outline_failed: {_sanitize_error(str(e))}"],
            "current_step": ["section_4_outline_failed"],
        }
