"""第 4 节大纲：运动方案大纲 — 直接搜索 + 27B 单次生成

重设计：从 selected_exercise_types（S3 输出）构建可用运动清单，
LLM 输出 type_index + exercise_index（序号引用），代码反查完整运动信息。
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
    _invoke_llm_json,
    _invoke_llm_structured,
    _safe_format,
    _sanitize_error,
)
from src.schemas.knowledge_qa import (
    KnowledgeQAState,
    Section4OutlineResponse,
    SectionOutput,
    push_progress,
)

logger = logging.getLogger(__name__)


# ==================== 运动清单构建 ====================


def _build_available_exercises_markdown(selected_exercise_types: list[dict]) -> str:
    """从 S3 输出的 selected_exercise_types 构建可用运动清单 Markdown。

    按类型分组，每个运动显示 exercise_index（文档原始序号）+ 名称 + 强度 + 益处。
    LLM 通过 type_index + exercise_index 引用运动，代码反查完整信息。
    """
    if not selected_exercise_types:
        return "（无可用运动清单）"

    parts = ["## 可用运动清单（来自 S3 选中的运动类型）\n"]
    for type_info in selected_exercise_types:
        type_idx = type_info.get("index", "?")
        type_name = type_info.get("type", "未知")
        tier = type_info.get("tier", "")
        exercises = type_info.get("exercises", [])

        tier_label = {"primary": "核心", "secondary": "辅助", "supplementary": "补充"}.get(tier, "")
        # 去除括号后缀用于展示
        import re as _re
        display_name = _re.sub(r"[（(][^）)]*[）)]$", "", type_name).strip() or type_name
        header = f"### {display_name}（type_index={type_idx}，{tier_label}推荐）"
        parts.append(header)
        parts.append("")

        if exercises:
            parts.append("| exercise_index | 运动名称 | 强度 | 主要益处 |")
            parts.append("|---------------|---------|------|---------|")
            for ex in exercises:
                # exercise_index 使用运动在原始 exercises 数组中的 id - 1（0-based 序号）
                # 或直接用运动对象中记录的位置信息
                ex_idx = ex.get("_exercise_index", ex.get("id", 0) - 1)
                name = ex.get("name", "")
                intensity = ex.get("intensity", "")
                benefits = (ex.get("benefits", "") or "")[:60]
                parts.append(f"| {ex_idx} | {name} | {intensity} | {benefits} |")
            parts.append("")
        else:
            parts.append("（该类型下无运动）\n")

    return "\n".join(parts)


def _build_exercise_lookup(selected_exercise_types: list[dict]) -> dict:
    """构建 (type_index, exercise_index) → exercise 对象的查找表。

    用于 S4 后处理：从 LLM 输出的 type_index + exercise_index 反查完整运动信息。
    """
    lookup = {}
    for type_info in selected_exercise_types:
        type_idx = type_info.get("index", -1)
        for ex in type_info.get("exercises", []):
            ex_idx = ex.get("_exercise_index", ex.get("id", 0) - 1)
            lookup[(type_idx, ex_idx)] = ex
    return lookup


def _enrich_phases_with_exercise_info(
    phases: list[dict],
    exercise_lookup: dict,
    selected_exercise_types: list[dict],
) -> list[dict]:
    """为 phases 中每个 exercise 填充 name/category/target_skill 等字段。

    LLM 输出 type_index + exercise_index，代码反查完整运动信息并填充。
    """
    # 构建 type_index → type_name 映射
    type_map = {t.get("index", -1): t.get("type", "") for t in selected_exercise_types}

    for phase in phases:
        for week in phase.get("weeks", []):
            for day in week.get("days", []):
                for ex in day.get("main_exercises", []):
                    type_idx = ex.get("type_index", -1)
                    ex_idx = ex.get("exercise_index", -1)
                    key = (type_idx, ex_idx)

                    if key in exercise_lookup:
                        full_ex = exercise_lookup[key]
                        # 填充 LLM 未输出的字段
                        ex["name"] = full_ex.get("name", ex.get("name", ""))
                        ex["category"] = full_ex.get("type", "")
                        ex["brain_mechanisms"] = full_ex.get("brain_mechanisms", "")
                        ex["benefits"] = full_ex.get("benefits", "")
                        ex["chapter"] = full_ex.get("chapter", "")
                    else:
                        # 序号越界：尝试从 type_map 获取类型名作为降级
                        type_name = type_map.get(type_idx, "未知")
                        if not ex.get("name"):
                            ex["name"] = f"{type_name}运动"
                        logger.warning(
                            f"S4 exercise 反查失败: type_index={type_idx}, "
                            f"exercise_index={ex_idx}, 降级使用类型名"
                        )
    return phases


# ==================== 主入口 ====================


async def plan_outline_node(state: KnowledgeQAState) -> Dict[str, Any]:
    """第 4 节大纲：设计阶段划分 + 每周主题 + 具体运动。
    始终生成运动方案大纲，无论问题是否显式提及运动。
    """
    await push_progress("section_4_outline", "正在生成运动方案大纲…")

    data = None  # 初始化，确保异常处理中可安全引用
    try:
        # Step 1: 获取知识上下文
        s4_query = state.section_queries.get(4, state.question)
        bundle = getattr(state, "knowledge_bundle", None)

        if bundle is not None:
            from src.core.knowledge_qa.bundle_consumer import (
                extract_for_section, build_priority_context,
            )
            section_passages = extract_for_section(bundle, 4, s4_query)
            search_context = build_priority_context(
                bundle=bundle, section_passages=section_passages, section_index=4,
                custom_knowledge_context=getattr(state, "custom_knowledge_context", "") or "",
                knowledge_context=getattr(state, "knowledge_context", "") or "",
                exercise_context="",  # 不再传全量 exercise_context
            )
            logger.info("S4 outline Bundle 模式: %d passages", len(section_passages))
        else:
            search_results = await _direct_search(s4_query, state.matched_book_ids, state=state)
            search_context = _format_search_context(search_results)

        # Step 2: 构建前序节内容 + 可用运动清单
        s1 = state.sections.get(1)
        s2 = state.sections.get(2)
        s3 = state.sections.get(3)

        # 从 state 读取 S3 输出的 selected_exercise_types
        selected_exercise_types = state.selected_exercise_types or []
        available_exercises_md = _build_available_exercises_markdown(selected_exercise_types)
        exercise_lookup = _build_exercise_lookup(selected_exercise_types)

        # Step 3: 获取 prompt 并生成
        prompt = await _get_prompt_pair("section_4_outline")
        user_message = _safe_format(
            prompt["user_template"],
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

        # 注入可用运动清单（替代全量 exercise_context）
        if selected_exercise_types:
            full_message += f"\n\n{available_exercises_md}"

        # ── 分阶段生成：两次 LLM 调用，避免单次生成两个 phase 导致 Phase 2 质量崩塌 ──
        # Phase 1: 生成第 1 阶段（第 1-2 周）
        phase1_message = (
            full_message
            + "\n\n## 任务：仅生成第 1 阶段（PH01，第 1-2 周）\n"
            + "输出 phases 数组仅包含 1 个元素（PH01），包含 week 1 和 week 2。"
        )
        phase1_data = await _invoke_llm_json(
            system_prompt=prompt["system"],
            user_message=phase1_message,
            step_label="plan_outline",
            timeout_seconds=120,
        )
        phase1_phases = phase1_data.get("phases", [])
        logger.info(f"plan_outline Phase 1: {len(phase1_phases)} phases, "
                    f"{_count_exercises_in_phases(phase1_phases)} exercises")

        # Phase 2: 生成第 2 阶段（第 3-4 周），携带 Phase 1 摘要作为递进上下文
        ph1_summary = _build_phase1_summary(phase1_phases)
        phase2_message = (
            full_message
            + f"\n\n## 第 1 阶段摘要（已完成）\n{ph1_summary}\n\n"
            + "## 任务：仅生成第 2 阶段（PH02，第 3-4 周）\n"
            + "输出 phases 数组仅包含 1 个元素（PH02），包含 week 3 和 week 4。"
            + "运动强度和复杂度应在第 1 阶段基础上递进，但不能重复第 1 阶段的运动。"
        )
        phase2_data = await _invoke_llm_json(
            system_prompt=prompt["system"],
            user_message=phase2_message,
            step_label="plan_outline_phase2",
            timeout_seconds=120,
        )
        phase2_phases = phase2_data.get("phases", [])
        logger.info(f"plan_outline Phase 2: {len(phase2_phases)} phases, "
                    f"{_count_exercises_in_phases(phase2_phases)} exercises")

        # 合并两个 phase → 统一 data
        data = {
            "title": phase1_data.get("title", "运动方案大纲"),
            "content": (phase1_data.get("content", "") + "\n\n" + phase2_data.get("content", "")).strip(),
            "citations": (phase1_data.get("citations", []) + phase2_data.get("citations", [])),
            "structured_data": phase1_data.get("structured_data", {}),
            "phases": phase1_phases + phase2_phases,
        }

        # ── 后置处理：从 type_index + exercise_index 反查运动信息 ──
        if selected_exercise_types and exercise_lookup:
            data["phases"] = _enrich_phases_with_exercise_info(
                data["phases"], exercise_lookup, selected_exercise_types,
            )

        # ── 显式校验 phases ──
        phases = data.get("phases", [])
        if not phases:
            logger.warning(
                f"plan_outline: LLM 返回空 phases, data_keys={list(data.keys())}。"
                f"尝试用简化 prompt 重新生成"
            )
            phases = await _retry_outline_phases(state, s3, search_context, selected_exercise_types)
            if phases:
                if selected_exercise_types and exercise_lookup:
                    phases = _enrich_phases_with_exercise_info(
                        phases, exercise_lookup, selected_exercise_types,
                    )
                data["phases"] = phases
                logger.info(f"plan_outline: 重试成功, 获得 {len(phases)} 个 phases")
            else:
                logger.warning("plan_outline: 重试仍无 phases，从 S3 运动类型降级构建")
                fallback_phases = _try_build_phases_from_content(data.get("content", ""), state)
                if fallback_phases:
                    data["phases"] = fallback_phases
                    logger.info(f"plan_outline: 降级构建了 {len(fallback_phases)} 个 phases")
                else:
                    logger.warning("plan_outline: 降级构建也失败，标记重试")
                    return {
                        "errors": state.errors + ["section_4_outline_no_exercises"],
                        "current_step": ["section_4_outline_failed"],
                    }

        # ── 后置校验：phases 中的 exercise 完整性 ──
        exercise_count = _count_exercises_in_phases(data.get("phases", []))
        if exercise_count == 0:
            logger.warning("plan_outline: phases 中无运动条目 (exercise_count=0)")
            fallback_phases = _try_build_phases_from_content(data.get("content", ""), state)
            if fallback_phases:
                data["phases"] = fallback_phases
                exercise_count = _count_exercises_in_phases(fallback_phases)
                if exercise_count > 0:
                    logger.info(f"plan_outline: 降级构建成功，exercise_count={exercise_count}")
                else:
                    return {
                        "errors": state.errors + ["section_4_outline_no_exercises"],
                        "current_step": ["section_4_outline_failed"],
                        }
            else:
                return {
                    "errors": state.errors + ["section_4_outline_no_exercises"],
                    "current_step": ["section_4_outline_failed"],
                }

        # ── day_index 归一化：LLM 输出全局递增索引，转为每周末尾局部值 1..N ──
        data["phases"] = _normalize_day_indices(data["phases"])

        # ── F9: 确保至少 2 个阶段 ──
        phases = data.get("phases", [])
        if len(phases) < 2:
            logger.warning(
                f"plan_outline: LLM 只生成 {len(phases)} 个阶段，自动补全至 2 阶段"
            )
            data["phases"] = _ensure_min_phases(phases, min_phases=2)

        # ── 确保每周恰好 7 天（补全缺失天为休息日）──
        data["phases"] = _ensure_full_weeks(data["phases"], days_per_week=7)

        # ── 强制每周最多 5 天训练，保证休息日 ──
        data["phases"] = _enforce_rest_days(data["phases"], state=state)

        # phases 变量重新读取（经过三次兜底函数后可能已变）
        phases = data["phases"]

        try:
            outline_section = SectionOutput(
                index=4,
                title=data.get("title", "运动方案大纲"),
                content=data.get("content", "") or "运动方案大纲（结构化数据见下方）",
                citations=data.get("citations", []),
                structured_data=data.get("structured_data", {}),
            )

            await push_progress(
                "section_4_outline_done",
                "运动方案大纲已完成",
                section=outline_section.model_dump(),
            )
        except Exception as e:
            logger.warning(f"plan_outline: push_progress/SectionOutput 失败: {e}, 仍返回 data")

        return {
            "section_4_outline": data,
            "current_step": ["section_4_outline_done"],
        }

    except asyncio.TimeoutError:
        logger.warning("plan_outline 超时")
        result: Dict[str, Any] = {
            "errors": state.errors + ["section_4_outline_failed: 生成超时"],
            "current_step": ["section_4_outline_failed"],
            "s4_retry_count": state.s4_retry_count + 1,
        }
        if data is not None and data.get("phases"):
            result["section_4_outline"] = data
            logger.info("plan_outline: 超时但保留降级 phases 数据")
        return result
    except Exception as e:
        logger.exception("plan_outline 失败")
        result: Dict[str, Any] = {
            "errors": state.errors + [f"section_4_outline_failed: {_sanitize_error(str(e))}"],
            "current_step": ["section_4_outline_failed"],
            "s4_retry_count": state.s4_retry_count + 1,
        }
        if data is not None and data.get("phases"):
            result["section_4_outline"] = data
            logger.info("plan_outline: 异常但保留降级 phases 数据")
        return result


# ==================== 重试与降级 ====================


async def _retry_outline_phases(
    state: "KnowledgeQAState",
    s3,
    search_context: str,
    selected_exercise_types: list[dict],
) -> list:
    """用简化 prompt 重新生成 phases（绕过完整大纲，只要 phases JSON）。"""

    # 从 selected_exercise_types 构建运动名称列表
    exercise_names = []
    type_mapping_lines = []
    for type_info in selected_exercise_types:
        type_name = type_info.get("type", "")
        type_idx = type_info.get("index", "?")
        tier = type_info.get("tier", "")
        type_mapping_lines.append(f"  - {type_name}: type_index={type_idx}, tier={tier}")
        for ex in type_info.get("exercises", [])[:3]:
            name = ex.get("name", "")
            if name:
                exercise_names.append(name)

    if not exercise_names:
        return []

    system = """你是儿童运动方案设计师。只输出一个 JSON 对象，包含 phases 数组。
不要输出 markdown、不要输出解释，只输出 JSON。

phases 结构要求：
- 2-3 个阶段，每阶段含 phase_id(PH01)、name、goal、duration_weeks、weeks[]
- 每阶段 2 周，每周 5 天（周一到周五），每天 1-2 个运动
- 运动名称必须来自下方提供的合法运动名称列表
- exercise_id 全局唯一递增(EX001-EX999)
- type_index 引用运动类型序号
- exercise_index 引用运动在清单中的序号

输出格式：
{"phases": [{"phase_id":"PH01","name":"...","goal":"...","duration_weeks":2,"weeks":[{"week_index":1,"days":[{"day_index":1,"main_exercises":[{"exercise_id":"EX001","type_index":0,"exercise_index":0,"duration_min":30,"intensity":"中"}]}]}]}]}"""

    exercise_list = "、".join(exercise_names[:10])
    type_mapping = "\n".join(type_mapping_lines[:8])

    user_msg = f"""用户问题：{state.question}

合法运动名称（只能从这里选）：
{exercise_list}

运动类型映射：
{type_mapping}

前序分析摘要：
{state.sections.get(1).content[:200] if state.sections.get(1) else ''}
{state.sections.get(2).content[:200] if state.sections.get(2) else ''}

请直接输出 JSON，不要任何解释文字。"""

    try:
        data = await _invoke_llm_json(
            system_prompt=system,
            user_message=user_msg,
            step_label="plan_outline_retry",
            timeout_seconds=60,
        )
        phases = data.get("phases", [])
        if phases and isinstance(phases, list) and len(phases) > 0:
            exercise_count = 0
            for ph in phases:
                for wk in ph.get("weeks", []):
                    for day in wk.get("days", []):
                        for ex in day.get("main_exercises", []):
                            if ex.get("name") or ex.get("type_index") is not None:
                                exercise_count += 1
            if exercise_count > 0:
                return phases
            else:
                logger.warning("_retry_outline_phases: phases 中无运动条目")
                return []
        return []
    except Exception as e:
        logger.warning(f"_retry_outline_phases 失败: {e}")
        return []


def _count_exercises_in_phases(phases: list) -> int:
    """统计 phases 中所有带 name 或 type_index 的 exercise 数量。"""
    count = 0
    for phase in (phases or []):
        for week in phase.get("weeks", []):
            for day in week.get("days", []):
                for ex in day.get("main_exercises", []):
                    if ex.get("name") or ex.get("type_index") is not None:
                        count += 1
    return count


def _build_phase1_summary(phases: list) -> str:
    """构建 Phase 1 摘要，供 Phase 2 生成时作为递进上下文。"""
    if not phases:
        return "（第 1 阶段未生成）"
    lines = []
    for ph in phases[:1]:
        pn = ph.get("phase_name") or ph.get("name", "阶段")
        pg = ph.get("goal", "")
        lines.append(f"阶段名：{pn}")
        if pg:
            lines.append(f"目标：{pg}")
        for wk in ph.get("weeks", []):
            wi = wk.get("week_index", "?")
            ex_names = []
            for day in wk.get("days", []):
                for ex in day.get("main_exercises", []):
                    name = ex.get("name", "")
                    if name:
                        ex_names.append(name)
            lines.append(f"第{wi}周运动：{' → '.join(ex_names[:8])}{'…' if len(ex_names) > 8 else ''}")
    lines.append("\n请基于以上第 1 阶段安排，设计递进的第 2 阶段（提高强度/复杂度/社交性，不重复运动名称）。")
    return "\n".join(lines)


def _normalize_day_indices(phases: list) -> list:
    """将 LLM 输出的全局递增 day_index 归一化为每周末尾局部值 1..N。"""
    for phase in phases:
        for week in phase.get("weeks", []):
            days = week.get("days", [])
            if not days:
                continue
            days.sort(key=lambda d: d.get("day_index", 0))
            for i, day in enumerate(days):
                day["day_index"] = i + 1
    return phases


def _ensure_min_phases(phases: list, min_phases: int = 2) -> list:
    """确保至少有 min_phases 个阶段。不足时从已有阶段复制并调整。"""
    if len(phases) >= min_phases:
        return phases

    import copy
    result = list(phases)
    while len(result) < min_phases:
        src = result[-1] if result else None
        if src is None:
            break
        new_phase = copy.deepcopy(src)
        idx = len(result)
        new_phase["phase_id"] = f"PH{idx + 1:02d}"
        phase_names = ["基础适应期", "能力提升期", "巩固维持期"]
        phase_goals = [
            "建立运动习惯，适应基础训练",
            "提升运动强度，巩固训练效果",
            "维持训练成果，形成日常习惯",
        ]
        new_phase["name"] = phase_names[idx] if idx < len(phase_names) else f"第{idx + 1}阶段"
        new_phase["goal"] = phase_goals[idx] if idx < len(phase_goals) else "巩固训练效果"
        new_phase["duration_weeks"] = 2
        base_week = len(result) * 2
        for wi, week in enumerate(new_phase.get("weeks", [])):
            week["week_index"] = base_week + wi + 1
        result.append(new_phase)
        logger.info(f"_ensure_min_phases: 自动补全第 {idx + 1} 阶段 '{new_phase['name']}'")
    return result


def _enforce_rest_days(phases: list, max_training_days: int | None = None, state=None) -> list:
    """确保每周休息日数量合理。"""
    if max_training_days is None:
        max_training_days = _compute_max_training_days(state)

    for phase in phases:
        for week in phase.get("weeks", []):
            days = week.get("days", [])
            if len(days) <= max_training_days:
                continue
            days.sort(key=lambda d: d.get("day_index", 0))
            training_days = [d for d in days if d.get("main_exercises")]
            if len(training_days) > max_training_days:
                excess = len(training_days) - max_training_days
                interval = max(len(training_days) // (excess + 1), 1)
                rest_positions = set()
                pos = interval
                for _ in range(excess):
                    if pos < len(training_days):
                        rest_positions.add(training_days[pos].get("day_index"))
                    pos += interval + 1
                for day in training_days:
                    if day.get("day_index") in rest_positions and day.get("main_exercises"):
                        day["main_exercises"] = []
                        logger.info(
                            f"_enforce_rest_days: 第{phase.get('phase_id', '?')}阶段 "
                            f"第{week.get('week_index', '?')}周 "
                            f"Day{day.get('day_index', '?')} 转为休息日 (均匀分布)"
                        )
    return phases


def _compute_max_training_days(state) -> int:
    """根据孩子年龄和运动强度动态计算每周最大训练天数。"""
    age = 8
    try:
        s1 = state.sections.get(1) if state else None
        if s1 and s1.structured_data:
            age = s1.structured_data.get("child_profile", {}).get("age", 8)
            if isinstance(age, str):
                age = int("".join(c for c in age if c.isdigit()) or "8")
    except Exception:
        pass

    if age <= 6:
        base = 4
    elif age <= 10:
        base = 5
    else:
        base = 6

    try:
        if state:
            for ph in (state.section_4_outline or {}).get("phases", []):
                for wk in ph.get("weeks", []):
                    for day in wk.get("days", []):
                        for ex in day.get("main_exercises", []):
                            if ex.get("intensity") == "高":
                                base -= 1
                                logger.info(
                                    f"_compute_max_training_days: 检测到高强度运动 {ex.get('name')}, "
                                    f"max_training 调整为 {base}"
                                )
                                return max(base, 3)
    except Exception:
        pass

    return base

def _ensure_full_weeks(phases: list, days_per_week: int = 7) -> list:
    """确保每周恰好有 days_per_week 天。"""
    for phase in phases:
        for week in phase.get("weeks", []):
            days = week.get("days", [])
            days.sort(key=lambda d: d.get("day_index", 0))

            if len(days) < days_per_week:
                existing_indices = {d.get("day_index") for d in days}
                for di in range(1, days_per_week + 1):
                    if di not in existing_indices:
                        days.append({"day_index": di, "main_exercises": []})
                        logger.info(
                            f"_ensure_full_weeks: 第{phase.get('phase_id', '?')}阶段 "
                            f"第{week.get('week_index', '?')}周 Day{di} 补全为休息日"
                        )
                days.sort(key=lambda d: d.get("day_index", 0))
            elif len(days) > days_per_week:
                week["days"] = days[:days_per_week]
                logger.info(
                    f"_ensure_full_weeks: 第{phase.get('phase_id', '?')}阶段 "
                    f"第{week.get('week_index', '?')}周 截断到 {days_per_week} 天"
                )
    return phases

def _try_build_phases_from_content(content: str, state: KnowledgeQAState) -> list:
    """从 S3 selected_exercise_types 构建降级 phases。"""
    selected = state.selected_exercise_types or []
    if not selected:
        # 兜底：尝试从 sections[3] structured_data 获取
        s3 = state.sections.get(3)
        exercise_types = []
        if s3 and s3.structured_data:
            exercise_types = s3.structured_data.get("exercise_types", [])
        if not exercise_types:
            return []

        # 从 exercise_types 降级构建
        primary = [et for et in exercise_types if et.get("tier") == "primary"]
        secondary = [et for et in exercise_types if et.get("tier") == "secondary"]
        supplementary = [et for et in exercise_types if et.get("tier") == "supplementary"]
    else:
        primary = [t for t in selected if t.get("tier") == "primary"]
        secondary = [t for t in selected if t.get("tier") == "secondary"]
        supplementary = [t for t in selected if t.get("tier") == "supplementary"]

    if not primary:
        primary = selected[:2] if selected else exercise_types[:2]
    if not secondary:
        secondary = selected[2:4] if len(selected) > 2 else selected[:2]

    ex_id_counter = [1]

    def _make_exercise(type_info: dict, phase_idx: int) -> dict:
        """从运动类型信息构建 exercise 条目"""
        eid = f"EX{ex_id_counter[0]:03d}"
        ex_id_counter[0] += 1
        base_duration = 20 if phase_idx == 0 else 30
        base_intensity = "低" if phase_idx == 0 else "中"
        tier = type_info.get("tier", "secondary")
        if tier == "primary":
            base_duration += 5

        # 从 exercises 列表取第一个作为代表
        exercises = type_info.get("exercises", [])
        representative = exercises[0] if exercises else {}

        return {
            "exercise_id": eid,
            "name": representative.get("name", type_info.get("type", "")),
            "type_index": type_info.get("index", 0),
            "exercise_index": representative.get("_exercise_index", representative.get("id", 1) - 1),
            "category": representative.get("type", type_info.get("type", "")),
            "duration_min": base_duration,
            "intensity": base_intensity,
            "target_skill": ", ".join(
                k for k, v in {
                    "专注力": any(kw in str(representative.get("benefits", "")) for kw in ["专注", "注意", "集中"]),
                    "身体协调": any(kw in str(representative.get("benefits", "")) for kw in ["协调", "平衡"]),
                }.items() if v
            ) or "综合发展",
        }

    def _build_week_schedule(phase_idx: int, week_idx: int) -> dict:
        days = []
        for day_idx in range(5):
            exercises = []
            if primary:
                p_idx = day_idx % len(primary)
                exercises.append(_make_exercise(primary[p_idx], phase_idx))
            if day_idx % 2 == 0 and secondary:
                s_idx = (day_idx + week_idx) % len(secondary)
                exercises.append(_make_exercise(secondary[s_idx], phase_idx))
            elif supplementary:
                sup_idx = (day_idx + week_idx) % len(supplementary)
                exercises.append(_make_exercise(supplementary[sup_idx], phase_idx))
            days.append({
                "day_index": day_idx + 1,
                "main_exercises": exercises,
            })
        return {"week_index": week_idx + 1, "days": days}

    phases = []
    for phase_idx in range(2):
        phase_id = f"PH{phase_idx + 1:02d}"
        phase_name = "基础适应期" if phase_idx == 0 else "能力提升期"
        phase_goal = "建立运动习惯，适应基础训练" if phase_idx == 0 else "提升运动强度，巩固训练效果"
        weeks = [_build_week_schedule(phase_idx, w) for w in range(2)]
        phases.append({
            "phase_id": phase_id,
            "name": phase_name,
            "goal": phase_goal,
            "duration_weeks": 2,
            "weeks": weeks,
        })

    total_exercises = sum(
        1
        for ph in phases
        for wk in ph.get("weeks", [])
        for day in wk.get("days", [])
        for ex in day.get("main_exercises", [])
        if ex.get("name")
    )
    logger.info(
        f"_try_build_phases_from_content: 构建 {len(phases)} 阶段, "
        f"{total_exercises} 个运动条目"
    )
    return phases
