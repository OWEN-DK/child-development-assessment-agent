"""第 4 节组装：合并并行展开结果 → Section4StructuredData → 渲染 Markdown

替代原来 plan_expand_content_node 的单次巨型 JSON 校验失败问题。
组装步骤：
  1. 将分组结果按 slot_idx 回填到 outline 结构
  2. 从结构推导 plan_summary（纯计算，无 LLM 调用）
  3. 小 LLM 生成 caution（注意事项）
  4. Pydantic 校验 → 渲染 Markdown
"""

import asyncio
import difflib
import json
import logging
from typing import Any, Dict, List

from src.schemas.knowledge_qa import (
    KnowledgeQAState,
    PlanSummary,
    Phase,
    Week,
    Day,
    Exercise,
    Section4StructuredData,
    SectionOutput,
    push_progress,
)

logger = logging.getLogger(__name__)


def _merge_group_results(
    outline: dict,
    slots: List[dict],
    group_results: Dict[str, List[dict]],
) -> dict:
    """将各组的运动参数回填到 outline 的 phases 结构中。

    策略：遍历 slots（保持原始顺序），用 slot 中的定位信息找到
    outline 中对应的位置，用 group_results 中的参数覆盖。

    Returns:
        {"phases": [...], "plan_summary": {...}, "caution": ""}
    """
    # 构建 flat 索引：slot_idx → exercise_params
    flat: Dict[int, dict] = {}
    for gidx, exercises in group_results.items():
        base = int(gidx) * 4  # GROUP_SIZE=4
        for ei, ex in enumerate(exercises):
            flat[base + ei] = ex

    # Deep copy outline phases（避免修改原始数据）
    phases = json.loads(json.dumps(outline.get("phases", [])))

    # 验证运动名称（与 S3 合法名称集合做模糊匹配）
    # 同时回填参数
    for slot in slots:
        si = slot["slot_idx"]
        pi = slot["phase_idx"]
        wi = slot["week_idx"]
        di = slot["day_idx"]
        ei = slot["exercise_idx"]

        params = flat.get(si, slot["exercise"])
        try:
            phase = phases[pi]
            week = phase["weeks"][wi]
            day = week["days"][di]
            orig = day["main_exercises"][ei]

            # 回填参数（保留大纲中的原始字段，用 LLM 生成值覆盖）
            orig["name"] = params.get("name", orig.get("name", ""))
            orig["type_id"] = params.get("type_id", orig.get("type_id", ""))
            orig["category"] = params.get("category", orig.get("category", ""))
            orig["duration_min"] = params.get("duration_min", 0)
            orig["intensity"] = params.get("intensity", "中")
            orig["intensity_hint"] = params.get("intensity_hint", "")
            orig["sets"] = params.get("sets")
            orig["reps"] = params.get("reps")
            orig["rest_seconds"] = params.get("rest_seconds")
            orig["target_skill"] = params.get("target_skill", orig.get("target_skill", ""))
            orig["notes"] = params.get("notes", "")
            orig["alternatives"] = params.get("alternatives", [])
            orig["citation_ids"] = params.get("citation_ids", orig.get("citation_ids", []))
        except (IndexError, KeyError) as e:
            logger.warning(f"plan_assemble: slot[{si}] 回填失败: {e}")

    return phases


def _validate_exercise_names(phases: List[dict], valid_names: List[str]) -> int:
    """后处理：用 S3 运动名称做模糊匹配修正。返回修正数量。"""
    if not valid_names:
        return 0

    fixed_count = 0
    valid_lower = {n.lower().strip(): n for n in valid_names if n.strip()}

    for ph in phases:
        for wk in ph.get("weeks", []):
            for day in wk.get("days", []):
                for ex in day.get("main_exercises", []):
                    ex_name = (ex.get("name", "") or "").strip()
                    if not ex_name:
                        continue
                    if ex_name.lower() in valid_lower:
                        continue  # 精确匹配

                    # 模糊匹配
                    best = None
                    for vl, vo in valid_lower.items():
                        if vl in ex_name.lower() or ex_name.lower() in vl:
                            best = vo
                            break
                    if not best:
                        matches = difflib.get_close_matches(
                            ex_name.lower(), list(valid_lower.keys()), n=1, cutoff=0.5
                        )
                        if matches:
                            best = valid_lower[matches[0]]
                    if best and best != ex_name:
                        ex["name"] = best
                        fixed_count += 1
                        logger.info(f"运动名称修正: '{ex_name}' → '{best}'")

    return fixed_count


def _derive_plan_summary(
    phases: List[dict],
    outline: dict,
) -> PlanSummary:
    """从结构推导方案摘要（纯计算，无 LLM）。"""
    existing = outline.get("structured_data", {})
    if isinstance(existing, str):
        existing = {}

    total_days = 0
    for ph in phases:
        for wk in ph.get("weeks", []):
            total_days += len(wk.get("days", []))

    return PlanSummary(
        total_duration_days=existing.get("total_duration_days", total_days),
        total_phases=existing.get("total_phases", len(phases)),
        daily_duration_min=existing.get("daily_duration_min", 30),
        weekly_frequency=existing.get("weekly_frequency", 5),
    )


async def _generate_caution(state: KnowledgeQAState, phases: List[dict]) -> str:
    """用小 LLM 调用生成注意事项。失败返回通用提示。"""
    from src.core.llm.factory import LLMServiceFactoryCompat

    # 提取运动名称摘要
    exercise_names = []
    for ph in phases[:2]:
        for wk in ph.get("weeks", []):
            for day in wk.get("days", []):
                for ex in day.get("main_exercises", []):
                    n = ex.get("name", "")
                    if n and n not in exercise_names:
                        exercise_names.append(n)
                        if len(exercise_names) >= 10:
                            break

    if not exercise_names:
        return "请在专业教练指导下进行训练，根据孩子的实际体能状况调整运动强度和时间。"

    try:
        model = LLMServiceFactoryCompat.create_raw(
            model_name="qwen3.5-27b",
            temperature=0.3,
        )

        prompt = f"""你是一个儿童运动安全专家。根据以下运动方案，写一段注意事项和禁忌情况。

运动项目：{', '.join(exercise_names[:10])}
用户问题：{state.question}

请用 2-4 句话写出安全注意事项和禁忌情况。简明扼要，只输出注意事项文本（不要 markdown 格式）。"""

        response = await asyncio.wait_for(
            model.ainvoke(prompt),
            timeout=15,
        )
        content = response.content if hasattr(response, "content") else str(response)
        return content.strip()[:500]
    except Exception as e:
        logger.warning(f"caution 生成失败: {e}")
        return "请在专业教练指导下进行训练，根据孩子的实际体能状况调整运动强度和时间。"


def _render_s4_markdown(structured_data: dict) -> str:
    """从 Section4StructuredData 渲染 Markdown 正文。纯字符串操作。"""
    lines = ["## 运动方案", ""]

    plan_summary = structured_data.get("plan_summary", {})
    if plan_summary:
        lines.append(f"> **方案总览**：共 {plan_summary.get('total_duration_days', '?')} 天，"
                     f"{plan_summary.get('total_phases', '?')} 个阶段，"
                     f"每天约 {plan_summary.get('daily_duration_min', '?')} 分钟，"
                     f"每周 {plan_summary.get('weekly_frequency', '?')} 天")
        lines.append("")

    phases = structured_data.get("phases", [])
    for pi, phase in enumerate(phases):
        phase_name = phase.get("phase_name", f"第{pi + 1}阶段")
        goal = phase.get("goal", "")
        lines.append(f"### 第{pi + 1}阶段：{phase_name}")
        if goal:
            lines.append(f"> {goal}")
        lines.append("")

        weeks = phase.get("weeks", [])
        for week in weeks:
            week_idx = week.get("week_index", 1)
            focus = week.get("focus", "")
            lines.append(f"#### 第{week_idx}周")
            if focus:
                lines.append(f"**本周重点**：{focus}")
            lines.append("")

            days = week.get("days", [])
            for day in days:
                day_idx = day.get("day_index", 1)
                day_label = day.get("day_label", f"第{day_idx}天")
                exercises = day.get("main_exercises", [])

                if not exercises:
                    lines.append(f"**{day_label}**：休息日")
                    lines.append("")
                    continue

                # Warmup
                warmup = day.get("warmup", {})
                if warmup and warmup.get("activity"):
                    lines.append(f"**{day_label}**")
                    lines.append(f"- 🏃 热身：{warmup['activity']}（{warmup.get('duration_min', 0)}分钟）")
                else:
                    lines.append(f"**{day_label}**")

                # Main exercises
                for ex in exercises:
                    name = ex.get("name", "未命名")
                    duration = ex.get("duration_min", 0)
                    intensity = ex.get("intensity", "")
                    intensity_hint = ex.get("intensity_hint", "")
                    sets = ex.get("sets")
                    reps = ex.get("reps")
                    notes = ex.get("notes", "")

                    params = []
                    if duration:
                        params.append(f"{duration}分钟")
                    if intensity:
                        hint = f"（{intensity_hint}）" if intensity_hint else ""
                        params.append(f"{intensity}{hint}")
                    if sets:
                        params.append(f"{sets}组")
                    if reps:
                        params.append(f"{reps}")

                    line = f"- 🎯 **{name}**"
                    if params:
                        line += f" — {' · '.join(params)}"
                    lines.append(line)

                    if notes:
                        lines.append(f"  > {notes}")

                # Cooldown
                cooldown = day.get("cooldown", {})
                if cooldown and cooldown.get("activity"):
                    lines.append(f"- 🧘 放松：{cooldown['activity']}（{cooldown.get('duration_min', 0)}分钟）")

                total = day.get("total_duration_min", 0)
                if total:
                    lines.append(f"  *当日总计：约{total}分钟*")
                lines.append("")

    caution = structured_data.get("caution", "")
    if caution:
        lines.append("### ⚠️ 注意事项")
        lines.append(f"> {caution}")
        lines.append("")

    return "\n".join(lines)


async def plan_assemble_node(state: KnowledgeQAState) -> Dict[str, Any]:
    """组装第 4 节：合并分组结果 → 校验 → 生成 caution → 渲染。

    降级路径:
      1. 无分组结果但有 outline → 用 outline 的 content 直接作为 S4 Markdown
      2. 无 outline → 生成占位 S4
    """
    outline = state.section_4_outline
    slots = state.section_4_slots
    group_results = state.section_4_group_results

    # ---- 降级路径 1: 无分组结果，用 outline content 直接作为 S4 ----
    if not slots or not group_results:
        if outline:
            content = outline.get("content", "")
            if content:
                logger.info("plan_assemble: 降级使用 outline content 作为 S4")
                section = SectionOutput(
                    index=4,
                    title=outline.get("title", "运动方案大纲"),
                    content=content,
                    citations=outline.get("citations", []),
                    structured_data=outline.get("structured_data", {}),
                )
                await push_progress("section_4_done", "运动方案大纲（降级）", section=section.model_dump())
                sections = dict(state.sections)
                sections[4] = section
                return {"sections": sections, "current_step": ["section_4_done_fallback"]}

        # ---- 降级路径 2: 完全无数据 ----
        logger.warning("plan_assemble: 无 outline 也无分组结果，生成占位 S4")
        fallback_section = SectionOutput(
            index=4,
            title="运动方案",
            content="本节因数据不足未生成。请确保知识库中有足够的运动方案参考内容。",
            citations=[],
            structured_data={},
        )
        sections = dict(state.sections)
        sections[4] = fallback_section
        return {
            "sections": sections,
            "errors": state.errors + ["section_4_assemble: 无可用数据"],
            "current_step": ["section_4_done_fallback"],
            "partial": True,
        }

    # ---- 正常路径 ----
    await push_progress("section_4_assembling", "正在组装运动方案…")

    try:
        # Step 1: 合并
        phases = _merge_group_results(outline, slots, group_results)

        # Step 2: 运动名称校验
        s3 = state.sections.get(3)
        valid_names = []
        if s3 and s3.structured_data:
            ets = s3.structured_data.get("exercise_types", [])
            valid_names = [et.get("name", "") for et in ets if et.get("name")]
        if valid_names:
            fixed = _validate_exercise_names(phases, valid_names)
            if fixed:
                logger.info(f"plan_assemble: 运动名称修正 {fixed} 项")

        # Step 3: 推导 plan_summary
        plan_summary = _derive_plan_summary(phases, outline)

        # Step 4: LLM 生成 caution
        caution = await _generate_caution(state, phases)

        # Step 5: Pydantic 校验
        try:
            s4_data = Section4StructuredData(
                phases=phases,
                plan_summary=plan_summary,
                caution=caution,
            )
        except Exception as ve:
            logger.warning(f"plan_assemble: Pydantic 校验失败: {ve}，尝试修复")
            # 降级：跳过校验失败的字段，用默认值
            safe_phases = []
            for ph in phases:
                try:
                    safe_weeks = []
                    for wk in ph.get("weeks", []):
                        try:
                            safe_days = []
                            for day in wk.get("days", []):
                                try:
                                    safe_exs = []
                                    for ex in day.get("main_exercises", []):
                                        try:
                                            safe_exs.append(Exercise(**ex))
                                        except Exception:
                                            safe_exs.append(Exercise(
                                                exercise_id=ex.get("exercise_id", "EX000"),
                                                name=ex.get("name", "未知"),
                                                type_id=ex.get("type_id", ""),
                                                duration_min=ex.get("duration_min", 15),
                                                intensity=ex.get("intensity", "中"),
                                                description=ex.get("notes", ""),
                                            ))
                                    safe_days.append(Day(
                                        day_index=day.get("day_index", 1),
                                        main_exercises=safe_exs,
                                    ))
                                except Exception:
                                    continue
                            safe_weeks.append(Week(
                                week_index=wk.get("week_index", 1),
                                days=safe_days,
                            ))
                        except Exception:
                            continue
                    safe_phases.append(Phase(
                        phase_name=ph.get("phase_name", "阶段"),
                        weeks=safe_weeks,
                    ))
                except Exception:
                    continue

            try:
                s4_data = Section4StructuredData(
                    phases=safe_phases,
                    plan_summary=plan_summary,
                    caution=caution,
                )
            except Exception:
                # 完全失败：使用最小有效数据
                logger.error("plan_assemble: 无法构建有效 S4 数据")
                return {
                    "errors": state.errors + ["section_4_assemble: 数据校验完全失败"],
                    "current_step": ["section_4_assemble_failed"],
                }

        # Step 6: 渲染 Markdown
        data_dict = s4_data.model_dump()
        markdown = _render_s4_markdown(data_dict)

        # Step 7: 存储
        section = SectionOutput(
            index=4,
            title="运动方案",
            content=markdown,
            citations=[],  # 由 generate_s4_citations_node 填充
            structured_data=data_dict,
        )


        phase_count = len(data_dict.get("phases", []))
        logger.info(f"plan_assemble 完成: {phase_count} 阶段, {len(markdown)} 字符")

        await push_progress(
            "section_4_done",
            f"运动方案组装完成 ({phase_count} 个阶段)",
            section=section.model_dump(),
        )

        sections = dict(state.sections)
        sections[4] = section
        return {"sections": sections, "current_step": ["section_4_done"]}

    except Exception as e:
        logger.exception("plan_assemble 失败")
        return {
            "errors": state.errors + [f"section_4_assemble: {str(e)}"],
            "current_step": ["section_4_assemble_failed"],
        }
