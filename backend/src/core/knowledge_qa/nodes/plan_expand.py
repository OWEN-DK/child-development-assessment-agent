"""第 4 节：LLM 直接生成 Section4StructuredData → Python 渲染 Markdown

重构: 翻转生成顺序。之前是 plan_outline → plan_expand_content (Markdown) →
plan_extract_params (逆向提取 structured_data)，现在改为 LLM 直接产出
Pydantic 强校验的 Section4StructuredData，Markdown 正文由纯函数渲染。
plan_extract_params_node 已删除。
"""

import asyncio
import difflib
import json
import logging
import re
from typing import Any, Dict

from json_repair import repair_json
from pydantic import ValidationError

from src.core.knowledge_qa.nodes.base import (
    _direct_search,
    _format_search_context,
    _get_prompt_pair,
    _get_temperature,
    _section_fallback,
)
from src.schemas.knowledge_qa import (
    KnowledgeQAState,
    Section4StructuredData,
    SectionOutput,
    push_progress,
)

logger = logging.getLogger(__name__)


def _extract_and_validate_json(raw_text: str) -> dict | None:
    """从 LLM 原始响应中提取 JSON 并通过 Pydantic 校验。

    优先使用 json-repair 修复破损 JSON，
    处理 LLM 将 JSON 包裹在 markdown 代码块中的情况。
    返回通过 Section4StructuredData 校验的 dict，失败则返回 None。
    """
    if not raw_text or not raw_text.strip():
        return None

    candidates: list[str] = []

    # 尝试1: 直接使用原始文本
    candidates.append(raw_text.strip())

    # 尝试2: 提取 ```json ... ``` 代码块
    m = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", raw_text, re.DOTALL)
    if m:
        candidates.insert(0, m.group(1).strip())

    # 尝试3: 提取 { ... } 最外层 JSON 对象（处理 LLM 在 JSON 前后附加说明的情况）
    m = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if m:
        extracted = m.group(0)
        if extracted not in candidates:
            candidates.append(extracted)

    for i, candidate in enumerate(candidates):
        try:
            repaired = repair_json(candidate)
            parsed = json.loads(repaired)
            validated = Section4StructuredData(**parsed)
            logger.info(f"_extract_and_validate_json: 候选[{i}] 解析成功, {len(validated.phases)} phases")
            return validated.model_dump()
        except (json.JSONDecodeError, ValidationError, ValueError, TypeError) as e:
            err_msg = str(e)[:300]
            logger.warning(f"_extract_and_validate_json: 候选[{i}] 失败 ({type(e).__name__}): {err_msg}")
            continue

    return None


def _render_s4_markdown(structured_data: dict, outline: dict | None = None) -> str:
    """从 Section4StructuredData 渲染人类可读的 Markdown 正文。纯字符串操作，无 LLM 调用。"""
    lines = ["## 运动方案", ""]

    phases = structured_data.get("phases", [])
    for pi, phase in enumerate(phases):
        phase_name = phase.get("phase_name", f"第{pi + 1}阶段")
        lines.append(f"### 第{pi + 1}阶段：{phase_name}")
        lines.append("")

        weeks = phase.get("weeks", [])
        for week in weeks:
            week_idx = week.get("week_index", 1)
            lines.append(f"#### 第{week_idx}周")
            lines.append("")

            days = week.get("days", [])
            for day in days:
                day_idx = day.get("day_index", 1)
                exercises = day.get("main_exercises", [])

                if not exercises:
                    lines.append(f"- **第{day_idx}天**：休息日")
                else:
                    for ex in exercises:
                        name = ex.get("name", "未知运动")
                        duration = ex.get("duration_min", 30)
                        intensity = ex.get("intensity", "中")
                        desc = ex.get("description", "")

                        line = f"- **第{day_idx}天**：{name}，{duration}分钟，{intensity}强度"
                        if desc:
                            line += f"。{desc}"
                        lines.append(line)
                lines.append("")

    # 方案摘要
    plan_summary = structured_data.get("plan_summary", {})
    if plan_summary:
        lines.append("### 方案摘要")
        lines.append("")
        lines.append(f"- 总天数：{plan_summary.get('total_duration_days', 'N/A')} 天")
        lines.append(f"- 阶段数：{plan_summary.get('total_phases', 'N/A')} 个")
        lines.append(f"- 每日训练时长：{plan_summary.get('daily_duration_min', 'N/A')} 分钟")
        lines.append(f"- 每周训练频率：{plan_summary.get('weekly_frequency', 'N/A')} 天")
        lines.append("")

    # 注意事项
    caution = structured_data.get("caution", "")
    if caution:
        lines.append("### 注意事项")
        lines.append("")
        lines.append(caution)
        lines.append("")

    return "\n".join(lines)


async def plan_expand_content_node(state: KnowledgeQAState) -> Dict[str, Any]:
    """第 4 节结构化方案生成 + Markdown 渲染。

    LLM 直接产出 Section4StructuredData（Pydantic 强校验，字段不完整则拒绝），
    Markdown 正文由 _render_s4_markdown 纯函数渲染（零额外 LLM 调用）。
    运动名称后处理硬校验：遍历 phases → weeks → days → exercises，
    与 S3 合法名称集合做精确/模糊匹配，违规项自动修正。
    """
    from src.core.llm.factory import LLMServiceFactoryCompat

    if state.section_4_outline is None:
        return await _generate_simplified_plan(state)

    # 大纲 phases 为空 → 降级为简化方案生成，不做跳过
    outline = state.section_4_outline or {}
    phases = outline.get("phases") or outline.get("structured_data", {}).get("phases", [])
    if not phases:
        logger.info("plan_expand_content: 大纲 phases 为空，降级为简化方案生成")
        return await _generate_simplified_plan(state)

    await push_progress("section_4_expand", "正在生成结构化运动方案…")

    try:
        # Step 1: 搜索知识库（用大纲中的运动名称作为关键词）
        search_terms = state.question
        try:
            if phases:
                ex_names = set()
                for ph in phases[:2]:
                    for wk in ph.get("weeks", [])[:2]:
                        for day in wk.get("days", [])[:2]:
                            for ex in day.get("main_exercises", [])[:3]:
                                name = ex.get("name", "")
                                if name:
                                    ex_names.add(name)
                if ex_names:
                    search_terms = " ".join(list(ex_names)[:5])
        except Exception:
            pass

        search_results = await _direct_search(search_terms, state.matched_book_ids)
        search_context = _format_search_context(search_results)

        # Step 2: 构建 prompt
        prompt = await _get_prompt_pair("section_4_expand")
        prev_parts = []
        for i in range(1, 4):
            sec = state.sections.get(i)
            if sec:
                prev_parts.append(f"第{i}节：{sec.content[:500] if sec.content else ''}")

        s3 = state.sections.get(3)
        section_3_structured = json.dumps(
            s3.structured_data if s3 else {}, ensure_ascii=False
        )

        user_message = prompt["user_template"].format(
            question=state.question,
            outline=json.dumps(outline, ensure_ascii=False),
            previous_sections_content="\n\n".join(prev_parts),
            section_3_structured=section_3_structured,
            matched_book_ids=json.dumps(state.matched_book_ids),
            knowledge_context=state.knowledge_context or "",
        )

        full_message = f"{user_message}\n\n## 知识库检索结果\n{search_context}"

        if state.exercise_context:
            full_message += f"\n\n{state.exercise_context}"

        # Step 3: S3 已验证运动名称短清单注入 S4 prompt（硬约束）
        if s3 and s3.structured_data:
            ets = s3.structured_data.get("exercise_types", [])
            if ets:
                valid_names = [et.get("name", "") for et in ets if et.get("name")]
                if valid_names:
                    name_list = "\n".join(f"  - {n}" for n in valid_names)
                    full_message += (
                        f"\n\n## ⚠️ 硬性约束：运动中必须使用的运动名称\n"
                        f"以下 {len(valid_names)} 个运动名称来自第3节推荐（已经过权威清单校验），"
                        f"你在 S4 方案中使用的所有具体运动名称**必须**从以下列表中选取，"
                        f"不允许使用列表外的任何名称，不允许自行发明或改写：\n"
                        f"{name_list}\n"
                        f"如果你认为需要某个不在列表中的运动，"
                        f"请从列表中选择最接近的替代。"
                    )

        # Step 4: 原始 LLM 调用 + json-repair 兜底 + Pydantic 校验
        # 不使用 with_structured_output(Section4StructuredData)，
        # 因为 DashScope 兼容端点对复杂嵌套 schema 的函数调用不稳定，偶发返回 {}。
        temperature = await _get_temperature("plan_expand")
        model = LLMServiceFactoryCompat.create_raw(
            model_name="qwen3.5-27b",
            temperature=temperature,
            max_tokens=16384,  # 4层嵌套JSON需要大量token预算
        )

        # 在 user message 末尾追加 JSON 输出格式指令
        json_instruction = """
## 输出格式要求

你必须输出一个完整的 JSON 对象，包含以下三个顶层字段：

```json
{
  "phases": [
    {
      "phase_name": "阶段名称",
      "weeks": [
        {
          "week_index": 1,
          "days": [
            {
              "day_index": 1,
              "main_exercises": [
                {
                  "exercise_id": "EX001",
                  "name": "运动名称（来自权威清单）",
                  "type_id": "关联第3节的type_id",
                  "duration_min": 30,
                  "intensity": "低",
                  "description": "执行要点和家长指导"
                }
              ]
            }
          ]
        }
      ]
    }
  ],
  "plan_summary": {
    "total_duration_days": 14,
    "total_phases": 2,
    "daily_duration_min": 30,
    "weekly_frequency": 5
  },
  "caution": "注意事项文字"
}
```

只输出 JSON，不要输出任何其他文字。"""

        full_message += json_instruction

        raw_response = await asyncio.wait_for(
            model.ainvoke([
                {"role": "system", "content": prompt["system"]},
                {"role": "user", "content": full_message},
            ]),
            timeout=90,
        )

        raw_text = raw_response.content if hasattr(raw_response, "content") else str(raw_response)

        # 从响应中提取 JSON（处理 LLM 可能包裹的 markdown 代码块）
        extracted = _extract_and_validate_json(raw_text)
        if extracted is None:
            # json-repair 也无法修复，记录原始响应并降级
            logger.warning(f"plan_expand: 无法解析 LLM 响应为 Section4StructuredData，前200字符: {raw_text[:200]}")
            return _section_fallback(state, 4, "运动方案", "LLM 响应解析失败")

        # Step 5: 后处理 — 运动名称硬校验（与 S3 合法名称集合精确/模糊匹配）
        if s3 and s3.structured_data:
            ets = s3.structured_data.get("exercise_types", [])
            if ets:
                valid_names_map = {et.get("name", "").lower().strip(): et.get("name", "") for et in ets if et.get("name")}
                fixed_count = 0
                for ph in extracted.get("phases", []):
                    for wk in ph.get("weeks", []):
                        for day in wk.get("days", []):
                            for ex in day.get("main_exercises", []):
                                ex_name = ex.get("name", "").strip()
                                if not ex_name:
                                    continue
                                if ex_name.lower() not in valid_names_map:
                                    # 优先子串匹配
                                    best_match = None
                                    for vn_lower, vn_orig in valid_names_map.items():
                                        if vn_lower in ex_name.lower() or ex_name.lower() in vn_lower:
                                            best_match = vn_orig
                                            break
                                    # 其次编辑距离
                                    if not best_match:
                                        matches = difflib.get_close_matches(
                                            ex_name.lower(), list(valid_names_map.keys()), n=1, cutoff=0.5
                                        )
                                        if matches:
                                            best_match = valid_names_map[matches[0]]
                                    if best_match:
                                        ex["name"] = best_match
                                        fixed_count += 1
                if fixed_count:
                    logger.info(f"S4 运动名称后处理修正: {fixed_count} 项")

        # Step 6: 从 structured_data 渲染 Markdown 正文（纯 Python，零 LLM 调用）
        markdown_content = _render_s4_markdown(extracted, outline)

        section = SectionOutput(
            index=4,
            title="运动方案",
            content=markdown_content,
            citations=[],  # 由 generate_s4_citations_node 后续填充
            structured_data=extracted,
        )


        phase_count = len(extracted.get("phases", []))
        logger.info(f"plan_expand 完成: {phase_count} 个阶段, {len(markdown_content)} 字符 Markdown")

        await push_progress(
            "section_4_done",
            f"第 4 节：运动方案已完成 ({phase_count} 个阶段)",
            section=section.model_dump(),
        )

        sections = dict(state.sections)
        sections[4] = section
        return {"sections": sections, "current_step": ["section_4_done"]}

    except asyncio.TimeoutError:
        logger.warning("plan_expand_content 超时")
        return _section_fallback(state, 4, "运动方案", "生成超时")
    except Exception as e:
        logger.exception("plan_expand_content 失败")
        return _section_fallback(state, 4, "运动方案", str(e))


async def _generate_simplified_plan(state: KnowledgeQAState) -> Dict[str, Any]:
    """大纲不可用时，基于 S1-S3 内容直接生成简化版结构化方案。"""
    from src.core.llm.factory import LLMServiceFactoryCompat

    await push_progress("section_4_simplified", "大纲未生成，正在基于前序内容生成简化运动方案…")

    s3 = state.sections.get(3)
    exercise_types = []
    if s3 and s3.structured_data:
        exercise_types = s3.structured_data.get("exercise_types", [])

    previous_content = "\n\n".join(
        f"第{i}节：{sec.content[:500]}"
        for i in range(1, 4)
        if (sec := state.sections.get(i))
    )

    exercise_list = "\n".join(
        f"- {et.get('name', '未知')}（优先级: {et.get('tier', '?')}，目标: {', '.join(et.get('target_skills', []))}）"
        for et in exercise_types[:6]
    )

    try:
        search_results = await _direct_search(state.question, state.matched_book_ids)
        search_context = _format_search_context(search_results)
    except Exception:
        search_context = "（搜索不可用）"

    user_message = f"""用户原始问题：{state.question}

前序分析摘要：
{previous_content}

第 3 节推荐的运动类型：
{exercise_list if exercise_list else "未能提取运动类型，请根据前序分析自行推荐"}

已匹配的书籍 ID：{json.dumps(state.matched_book_ids)}

请基于以上信息，设计一个简化版结构化运动方案。
至少包含 1 个阶段，每阶段 1-2 周，每周 2-3 天有运动安排。
如果书中找不到具体参数，可基于通用运动科学知识给出合理建议。

## 知识库检索结果
{search_context}"""

    if state.exercise_context:
        user_message += f"\n\n{state.exercise_context}"

    try:
        prompt = await _get_prompt_pair("section_4_expand")
        temperature = await _get_temperature("plan_expand")
        model = LLMServiceFactoryCompat.create_raw(
            model_name="qwen3.5-27b",
            temperature=temperature,
            max_tokens=16384,  # 4层嵌套JSON需要大量token预算
        )

        # 追加 JSON 输出格式指令
        json_instruction = """
## 输出格式要求

你必须输出一个完整的 JSON 对象，格式如下：

```json
{
  "phases": [{"phase_name": "...", "weeks": [{"week_index": 1, "days": [{"day_index": 1, "main_exercises": [{"exercise_id": "EX001", "name": "...", "type_id": "...", "duration_min": 30, "intensity": "低", "description": "..."}]}]}]}],
  "plan_summary": {"total_duration_days": 7, "total_phases": 1, "daily_duration_min": 20, "weekly_frequency": 3},
  "caution": "注意事项"
}
```

只输出 JSON，不要输出任何其他文字。"""
        user_message += json_instruction

        raw_response = await asyncio.wait_for(
            model.ainvoke([
                {"role": "system", "content": prompt["system"]},
                {"role": "user", "content": user_message},
            ]),
            timeout=90,
        )

        raw_text = raw_response.content if hasattr(raw_response, "content") else str(raw_response)
        extracted = _extract_and_validate_json(raw_text)

        if extracted is None:
            logger.warning(f"_generate_simplified_plan: 无法解析 LLM 响应，前200字符: {raw_text[:200]}")
            return _section_fallback(state, 4, "运动方案", "简化方案 JSON 解析失败")

        markdown_content = _render_s4_markdown(extracted)

        section = SectionOutput(
            index=4,
            title="简化运动方案",
            content=markdown_content,
            citations=[],
            structured_data=extracted,
        )


        await push_progress(
            "section_4_done",
            "第 4 节：简化运动方案已完成",
            section=section.model_dump(),
        )

        sections = dict(state.sections)
        sections[4] = section
        return {"sections": sections, "current_step": ["section_4_done"]}

    except Exception as e:
        logger.exception("简化版运动方案生成失败")
        return _section_fallback(state, 4, "运动方案", str(e))
