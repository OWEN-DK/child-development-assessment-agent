"""第 4 节组装：合并并行展开结果 → Section4StructuredData → 渲染 Markdown

替代原来 plan_expand_content_node 的单次巨型 JSON 校验失败问题。
组装步骤：
  1. 将分组结果按 slot_idx 回填到 outline 结构
  2. 从结构推导 plan_summary（纯计算，无 LLM 调用）
  3. 小 LLM 生成 caution（注意事项）
  4. Pydantic 校验 → 渲染 Markdown
"""

import json
import logging
from typing import Any, Dict, List

from src.core.knowledge_qa.nodes.base import (
    _invoke_llm_plain,
    fuzzy_match_exercise,
)
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


def _default_duration_for_age(state) -> int:
    """根据第 1 节分析的孩子年龄返回默认运动时长。"""
    try:
        s1 = state.sections.get(1)
        if s1 and s1.structured_data:
            age = s1.structured_data.get("child_profile", {}).get("age", 8)
            if isinstance(age, (int, float)):
                if age <= 6:
                    return 20
                elif age <= 10:
                    return 30
                else:
                    return 40
    except Exception:
        pass
    return 25  # 安全默认值


def _merge_group_results(
    outline: dict,
    slots: List[dict],
    group_results: Dict[str, List[dict]],
    state: "KnowledgeQAState" = None,
) -> List[dict]:
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
    failed_slots: List[int] = []

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
            # 时长：用 LLM 输出值，若为 0 则根据年龄取默认值
            dur = params.get("duration_min", 0)
            orig["duration_min"] = dur if dur > 0 else _default_duration_for_age(state)
            orig["intensity"] = params.get("intensity", "中")
            orig["intensity_hint"] = params.get("intensity_hint", "")
            orig["sets"] = params.get("sets")
            orig["reps"] = params.get("reps")
            orig["rest_seconds"] = params.get("rest_seconds")
            orig["target_skill"] = params.get("target_skill", orig.get("target_skill", ""))
            # notes → description（LLM 输出用 notes，存储用 description）
            orig["description"] = params.get("notes", "") or params.get("description", "")
            orig["alternatives"] = params.get("alternatives", [])
            orig["citation_ids"] = params.get("citation_ids", orig.get("citation_ids", []))
        except (IndexError, KeyError) as e:
            logger.warning(f"plan_assemble: slot[{si}] 回填失败: {e}")
            failed_slots.append(si)

    if failed_slots:
        logger.warning(f"plan_assemble: {len(failed_slots)}/{len(slots)} 个 slot 回填失败")
    return phases


def _validate_exercise_names(phases: List[dict], valid_names: List[str]) -> int:
    """后处理：用 S3 运动名称做模糊匹配修正。委托给 base.fuzzy_match_exercise。"""
    if not valid_names:
        return 0

    fixed_count = 0
    for ph in phases:
        for wk in ph.get("weeks", []):
            for day in wk.get("days", []):
                for ex in day.get("main_exercises", []):
                    ex_name = (ex.get("name", "") or "").strip()
                    if not ex_name:
                        continue
                    matched = fuzzy_match_exercise(ex_name, valid_names)
                    if matched and matched != ex_name:
                        ex["name"] = matched
                        fixed_count += 1
                        logger.info(f"运动名称修正: '{ex_name}' → '{matched}'")

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

    # 计算训练天数（有运动安排的天数）
    training_days = 0
    for ph in phases:
        for wk in ph.get("weeks", []):
            for day in wk.get("days", []):
                if day.get("main_exercises"):
                    training_days += 1

    return PlanSummary(
        # 总天数以实际 phases 结构为准（包含休息日），不使用 outline 旧值
        total_duration_days=total_days,
        total_phases=len(phases),
        daily_duration_min=existing.get("daily_duration_min", 30),
        weekly_frequency=existing.get("weekly_frequency", min(training_days, 5)),
    )


async def _generate_caution(state: KnowledgeQAState, phases: List[dict]) -> str:
    """用小 LLM 调用生成注意事项。失败返回通用提示。"""
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
        prompt = f"""你是一个儿童运动安全专家。根据以下运动方案，写一段注意事项和禁忌情况。

运动项目：{', '.join(exercise_names[:10])}
用户问题：{state.question}

请用 2-4 句话写出安全注意事项和禁忌情况。简明扼要，只输出注意事项文本（不要 markdown 格式）。"""

        result = await _invoke_llm_plain(
            prompt=prompt,
            step_label="plan_assemble_caution",
            timeout_seconds=15,
        )
        return result.strip()[:500]
    except Exception as e:
        logger.warning(f"caution 生成失败: {e}")
        return "请在专业教练指导下进行训练，根据孩子的实际体能状况调整运动强度和时间。"


def _extract_exercise_types_from_phases(phases: list, s3_ets: list) -> list:
    """从 S4 phases 中提取扁平运动类型列表，复用 S3 的类型元数据。

    将方案中所有运动按 name 去重后，匹配 S3 exercise_types 中的
    type_id/category/target_skills 等信息，输出与 S3 exercise_types 同构的数组。
    """
    if not phases:
        return []

    # 构建 S3 name → 类型元数据 的查找表
    s3_lookup: dict[str, dict] = {}
    for et in (s3_ets or []):
        name = (et.get("name", "") or "").strip()
        if name:
            s3_lookup[name] = {
                "type_id": et.get("type_id", ""),
                "category": et.get("category", ""),
                "target_skills": et.get("target_skills", []),
                "citation_ids": et.get("citation_ids", []),
            }

    seen: set[str] = set()
    result: list[dict] = []

    for ph in phases:
        for wk in ph.get("weeks", []):
            for day in wk.get("days", []):
                for ex in day.get("main_exercises", []):
                    name = (ex.get("name", "") or "").strip()
                    if not name or name in seen:
                        continue
                    seen.add(name)

                    meta = s3_lookup.get(name, {})
                    item = {
                        "type_id": meta.get("type_id", ex.get("type_id", "")),
                        "name": name,
                        "tier": ex.get("tier", "secondary"),
                        "category": meta.get("category", ex.get("category", "")),
                        "target_problem_ids": ex.get("target_problem_ids", []),
                        "target_skills": meta.get("target_skills", ex.get("target_skills", [])),
                        "recommendation_rationale": ex.get("notes", ""),
                        "citation_ids": meta.get("citation_ids", ex.get("citation_ids", [])),
                    }
                    result.append(item)

    return result


def _build_s4_summary(structured_data: dict) -> str:
    """从 S4 structured_data 生成简短摘要（100 字以内）。"""
    phases = structured_data.get("phases", [])
    if not phases:
        return "已根据孩子情况生成个性化运动方案。"

    ps = structured_data.get("plan_summary", {})
    total_days = ps.get("total_duration_days", "?")
    total_phases = len(phases)
    daily_min = ps.get("daily_duration_min", 30)

    # 收集所有运动名称
    all_names = []
    for ph in phases:
        for wk in ph.get("weeks", []):
            for day in wk.get("days", []):
                for ex in day.get("main_exercises", []):
                    name = ex.get("name", "")
                    if name and name not in all_names:
                        all_names.append(name)

    name_str = "、".join(all_names[:5])
    if len(all_names) > 5:
        name_str += "等"

    return f"共{total_phases}阶段{total_days}天方案，含{name_str}，每日约{daily_min}分钟。"


def _render_s4_markdown(structured_data: dict) -> str:
    """从 Section4StructuredData 渲染 Markdown 正文（美化版）。"""
    lines = []

    plan_summary = structured_data.get("plan_summary", {})
    if plan_summary:
        lines.append(f"> 📅 **方案总览**")
        lines.append(f"> - 总时长：**{plan_summary.get('total_duration_days', '?')} 天**")
        lines.append(f"> - 阶段数：**{plan_summary.get('total_phases', '?')} 个**")
        lines.append(f"> - 每日训练：约 **{plan_summary.get('daily_duration_min', '?')} 分钟**")
        lines.append(f"> - 每周频率：**{plan_summary.get('weekly_frequency', '?')} 天**")
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
                    notes = ex.get("description", "") or ex.get("notes", "")

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
                        lines.append(f"  > 💡 {notes}")
                    # target_skill
                    target = ex.get("target_skill", "")
                    if target:
                        lines.append(f"  *训练目标：{target}*")

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
            content_text = outline.get("content", "")
            if content_text:
                logger.info("plan_assemble: 降级使用 outline content 作为 S4")
                # 尝试从 outline 构造最小 structured_data
                degraded_sd = dict(outline.get("structured_data", {}))
                phases_raw = outline.get("phases", [])
                if phases_raw:
                    degraded_sd["phases"] = phases_raw
                else:
                    degraded_sd["phases"] = [{
                        "phase_name": "方案大纲（降级模式）",
                        "weeks": [],
                    }]
                degraded_sd.setdefault("caution", "本节为降级生成，缺乏完整结构化数据。建议重试以获得完整方案。")
                from src.schemas.knowledge_qa import PlanSummary
                degraded_sd.setdefault("plan_summary", PlanSummary(
                    total_duration_days=7,
                    total_phases=1,
                    daily_duration_min=30,
                    weekly_frequency=5,
                ).model_dump())
                # 降级模式下也提取 exercise_types
                s3_dg = state.sections.get(3)
                s3_dg_meta = (s3_dg.structured_data or {}).get("exercise_types", []) if s3_dg else []
                degraded_sd.setdefault("exercise_types", _extract_exercise_types_from_phases(phases_raw, s3_dg_meta))
                section = SectionOutput(
                    index=4,
                    title=outline.get("title", "运动方案大纲"),
                    content=content_text[:200] + "..." if len(content_text) > 200 else content_text,
                    citations=outline.get("citations", []),
                    structured_data=degraded_sd,
                )
                await push_progress("section_4_done", "运动方案大纲（降级）", section=section.model_dump())
                sections = dict(state.sections)
                sections[4] = section
                return {
                    "sections": sections,
                    "current_step": ["section_4_done_fallback"],
                    "s4_needs_retry": True,  # 有 outline 但无分组结果 → 可重试
                    "s4_retry_count": state.s4_retry_count + 1,
                }

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
        try:
            await push_progress(
                "section_4_done",
                "运动方案（占位）",
                section=fallback_section.model_dump(),
            )
        except Exception:
            pass  # push_progress 失败不阻塞流程
        return {
            "sections": sections,
            "errors": state.errors + ["section_4_assemble: 无可用数据"],
            "current_step": ["section_4_done_fallback"],
            "partial": True,
            "s4_retry_count": state.s4_retry_count + 1,
        }

    # ---- 正常路径 ----
    await push_progress("section_4_assembling", "正在组装运动方案…")

    try:
        # Step 1: 合并
        phases = _merge_group_results(outline, slots, group_results, state)

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

        # Step 4b: 从 phases 提取扁平 exercise_types（复用 S3 元数据）
        s3_ets_meta = (s3.structured_data or {}).get("exercise_types", []) if s3 else []
        s4_exercise_types = _extract_exercise_types_from_phases(phases, s3_ets_meta)

        # Step 5: Pydantic 校验
        try:
            s4_data = Section4StructuredData(
                exercise_types=s4_exercise_types,
                phases=phases,
                plan_summary=plan_summary,
                caution=caution,
            )
        except Exception as ve:
            logger.warning(f"plan_assemble: Pydantic 校验失败: {ve}，尝试修复")
            # 降级：跳过校验失败的字段，用默认值
            skipped_days = 0
            skipped_weeks = 0
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
                                                duration_min=ex.get("duration_min", 15) or _default_duration_for_age(state),
                                                intensity=ex.get("intensity", "中"),
                                                intensity_hint=ex.get("intensity_hint", ""),
                                                target_skill=ex.get("target_skill", ""),
                                                sets=ex.get("sets"),
                                                reps=ex.get("reps"),
                                                description=ex.get("notes", "") or ex.get("description", ""),
                                            ))
                                    safe_days.append(Day(
                                        day_index=day.get("day_index", 1),
                                        main_exercises=safe_exs,
                                    ))
                                except Exception:
                                    skipped_days += 1
                                    continue
                            safe_weeks.append(Week(
                                week_index=wk.get("week_index", 1),
                                days=safe_days,
                            ))
                        except Exception:
                            skipped_weeks += 1
                            continue
                    safe_phases.append(Phase(
                        phase_name=ph.get("phase_name") or ph.get("name", "阶段"),
                        weeks=safe_weeks,
                    ))
                except Exception:
                    continue

            if skipped_days or skipped_weeks:
                logger.warning(
                    f"plan_assemble: Pydantic 降级 — 丢弃 {skipped_days} 天, {skipped_weeks} 周"
                )

            try:
                s4_data = Section4StructuredData(
                    exercise_types=s4_exercise_types,
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

        # Step 6: 构建简短摘要（100 字以内）+ 完整 structured_data
        # 详细 Markdown 由前端从 structured_data 渲染，PDF 由 knowledge_qa_service 渲染
        data_dict = s4_data.model_dump()

        summary = _build_s4_summary(data_dict)

        # Step 7: 存储
        section = SectionOutput(
            index=4,
            title="运动方案",
            content=summary,
            citations=[],  # 由 generate_s4_citations_node 填充
            structured_data=data_dict,
        )


        phase_count = len(data_dict.get("phases", []))
        logger.info(f"plan_assemble 完成: {phase_count} 阶段, content={len(summary)} 字符")

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
        # 降级：尝试从 outline 构建最小可用 S4 section，避免 S4 完全缺失
        try:
            outline = state.section_4_outline or {}
            phases_raw = outline.get("phases", [])
            if phases_raw:
                # 从 outline 构建简化 structured_data
                fallback_phases = []
                for ph in phases_raw:
                    safe_weeks = []
                    for wk in (ph.get("weeks") or []):
                        safe_days = []
                        for day in (wk.get("days") or []):
                            safe_exs = []
                            for ex in (day.get("main_exercises") or []):
                                if ex.get("name"):
                                    safe_exs.append(Exercise(
                                        exercise_id=ex.get("exercise_id", "EX000"),
                                        name=ex["name"],
                                        type_id=ex.get("type_id", ""),
                                        duration_min=ex.get("duration_min", 25) or _default_duration_for_age(state),
                                        intensity=ex.get("intensity", "中"),
                                        intensity_hint=ex.get("intensity_hint", ""),
                                        target_skill=ex.get("target_skill", ""),
                                        sets=ex.get("sets"),
                                        reps=ex.get("reps"),
                                        description=ex.get("notes", "") or ex.get("description", ""),
                                    ))
                            if safe_exs:
                                safe_days.append(Day(
                                    day_index=day.get("day_index", 1),
                                    main_exercises=safe_exs,
                                ))
                        if safe_days:
                            safe_weeks.append(Week(
                                week_index=wk.get("week_index", 1),
                                days=safe_days,
                            ))
                    if safe_weeks:
                        fallback_phases.append(Phase(
                            phase_name=ph.get("phase_name") or ph.get("name", "阶段"),
                            weeks=safe_weeks,
                        ))

                if fallback_phases:
                    s4_data = Section4StructuredData(
                        phases=fallback_phases,
                        plan_summary=PlanSummary(
                            total_duration_days=outline.get("plan_summary", {}).get("total_duration_days", 42),
                            total_phases=len(fallback_phases),
                            daily_duration_min=outline.get("plan_summary", {}).get("daily_duration_min", 30),
                            weekly_frequency=outline.get("plan_summary", {}).get("weekly_frequency", 5),
                            intensity_overall="中",
                        ),
                        caution="本节由降级逻辑生成，运动参数可能不完整，请结合实际情况调整。",
                    )
                    data_dict = s4_data.model_dump()
                    summary = _build_s4_summary(data_dict)
                    section = SectionOutput(
                        index=4,
                        title="运动方案",
                        content=summary,
                        citations=[],
                        structured_data=data_dict,
                    )
                    sections = dict(state.sections)
                    sections[4] = section
                    logger.info(f"plan_assemble 降级成功: {len(fallback_phases)} 阶段")
                    await push_progress(
                        "section_4_done",
                        f"运动方案（降级）: {len(fallback_phases)} 个阶段",
                        section=section.model_dump(),
                    )
                    return {
                        "sections": sections,
                        "errors": state.errors + [f"section_4_assemble_fallback: {str(e)}"],
                        "current_step": ["section_4_done"],
                        "partial": True,
                    }
        except Exception as fallback_err:
            logger.error(f"plan_assemble 降级也失败: {fallback_err}")

        return {
            "errors": state.errors + [f"section_4_assemble: {str(e)}"],
            "current_step": ["section_4_assemble_failed"],
            "partial": True,
        }
