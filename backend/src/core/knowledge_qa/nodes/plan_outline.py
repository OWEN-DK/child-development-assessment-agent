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


async def plan_outline_node(state: KnowledgeQAState) -> Dict[str, Any]:
    """第 4 节大纲：设计阶段划分 + 每周主题 + 运动类型名称。
    始终生成运动方案大纲，无论问题是否显式提及运动。
    """
    await push_progress("section_4_outline", "正在生成运动方案大纲…")

    data = None  # 初始化，确保异常处理中可安全引用
    try:
        # Step 1: 直接搜索
        search_results = await _direct_search(state.question, state.matched_book_ids, state=state)
        search_context = _format_search_context(search_results)

        # Step 2: 构建前序节内容
        s1 = state.sections.get(1)
        s2 = state.sections.get(2)
        s3 = state.sections.get(3)

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

        if state.exercise_context:
            full_message += f"\n\n{state.exercise_context}"

        # 使用纯文本 JSON 输出（绕过 DashScope function_calling 对深层嵌套的缺陷）
        data = await _invoke_llm_json(
            system_prompt=prompt["system"],
            user_message=full_message,
            step_label="plan_outline",
            timeout_seconds=90,
        )

        # 补全缺失字段
        data.setdefault("title", "运动方案大纲")
        data.setdefault("content", "")
        data.setdefault("citations", [])
        data.setdefault("structured_data", {})

        # ── 显式校验 phases ──
        phases = data.get("phases", [])
        if not phases:
            logger.warning(
                f"plan_outline: LLM 返回空 phases, data_keys={list(data.keys())}。"
                f"尝试用简化 prompt 重新生成"
            )
            # 重试：用更简洁的 prompt 聚焦于 phases 结构
            phases = await _retry_outline_phases(state, s3, search_context)
            if phases:
                data["phases"] = phases
                logger.info(f"plan_outline: 重试成功, 获得 {len(phases)} 个 phases")
            else:
                # 降级：从 S3 运动类型构建最小可用 phases
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
            # 再次尝试降级构建
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
        data["phases"] = _enforce_rest_days(data["phases"], max_training_days=5)

        try:
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
        except Exception as e:
            logger.warning(f"plan_outline: push_progress/SectionOutput 失败: {e}, 仍返回 data")
            # push_progress 失败不影响结果返回，data 中已有完整的 phases

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
        # 如果降级构建成功（data 中有 phases），保留数据
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
        # 如果降级构建成功（data 中有 phases），保留数据
        if data is not None and data.get("phases"):
            result["section_4_outline"] = data
            logger.info("plan_outline: 异常但保留降级 phases 数据")
        return result


async def _retry_outline_phases(
    state: "KnowledgeQAState",
    s3,
    search_context: str,
) -> list:
    """用简化 prompt 重新生成 phases（绕过完整大纲，只要 phases JSON）。

    当 plan_outline 首次调用返回空 phases 时，用更聚焦的 prompt 重试。
    简化 prompt 只要求输出 phases 数组结构，不要求 content/citations。
    """


    s3_ets = []
    if s3 and s3.structured_data:
        s3_ets = s3.structured_data.get("exercise_types", [])

    exercise_names = [et.get("name", "") for et in s3_ets if et.get("name")]
    if not exercise_names:
        return []

    # 构造简化 prompt：只要求输出 phases 数组
    system = """你是儿童运动方案设计师。只输出一个 JSON 对象，包含 phases 数组。
不要输出 markdown、不要输出解释，只输出 JSON。

phases 结构要求：
- 2-3 个阶段，每阶段含 phase_id(PH01)、name、goal、duration_weeks、weeks[]
- 每阶段 2 周，每周 5 天（周一到周五），每天 1-2 个运动
- 运动名称必须来自下方提供的合法运动名称列表
- exercise_id 全局唯一递增(EX001-EX999)
- type_id 引用第 3 节的 type_id

输出格式：
{"phases": [{"phase_id":"PH01","name":"...","goal":"...","duration_weeks":2,"weeks":[{"week_index":1,"days":[{"day_index":1,"main_exercises":[{"exercise_id":"EX001","name":"...","type_id":"ET001","duration_min":30,"intensity":"中"}]}]}]}]}"""

    exercise_list = "、".join(exercise_names[:10])
    type_mapping = "\n".join(
        f"  - {et.get('name', '')}: type_id={et.get('type_id', '')}, tier={et.get('tier', '')}"
        for et in s3_ets[:8]
    )

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
            # 验证 phases 结构完整性
            exercise_count = 0
            for ph in phases:
                for wk in ph.get("weeks", []):
                    for day in wk.get("days", []):
                        for ex in day.get("main_exercises", []):
                            if ex.get("name"):
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
    """统计 phases 中所有带 name 的 exercise 数量。

    plan_expand_parallel_node._extract_exercise_slots 的过滤条件是
    `ex.get("name")`，与此处计数逻辑保持一致。
    """
    count = 0
    for phase in (phases or []):
        for week in phase.get("weeks", []):
            for day in week.get("days", []):
                for ex in day.get("main_exercises", []):
                    if ex.get("name"):
                        count += 1
    return count




def _ensure_min_phases(phases: list, min_phases: int = 2) -> list:
    """确保至少有 min_phases 个阶段。不足时从已有阶段复制并调整。

    当 LLM 未遵守"固定 2 个阶段"约束时自动补全。
    """
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
        # 根据阶段序号调整名称和目标
        phase_names = ["基础适应期", "能力提升期", "巩固维持期"]
        phase_goals = [
            "建立运动习惯，适应基础训练",
            "提升运动强度，巩固训练效果",
            "维持训练成果，形成日常习惯",
        ]
        new_phase["name"] = phase_names[idx] if idx < len(phase_names) else f"第{idx + 1}阶段"
        new_phase["goal"] = phase_goals[idx] if idx < len(phase_goals) else "巩固训练效果"
        new_phase["duration_weeks"] = 2
        # 调整 weeks 的 week_index
        base_week = len(result) * 2  # 前面阶段的周数偏移
        for wi, week in enumerate(new_phase.get("weeks", [])):
            week["week_index"] = base_week + wi + 1
        result.append(new_phase)
        logger.info(f"_ensure_min_phases: 自动补全第 {idx + 1} 阶段 '{new_phase['name']}'")
    return result


def _enforce_rest_days(phases: list, max_training_days: int = 5) -> list:
    """确保每周不超过 max_training_days 天训练，多余的天数转为休息日。

    遍历每个 phase 的每个 week，如果训练天数超过 max_training_days，
    将多余的天数（从周末开始）设为休息日（清空 main_exercises）。
    """
    for phase in phases:
        for week in phase.get("weeks", []):
            days = week.get("days", [])
            if len(days) <= max_training_days:
                continue
            # 按 day_index 排序，确保从后面开始截断
            days.sort(key=lambda d: d.get("day_index", 0))
            # 保留前 max_training_days 天，后面的天数转为休息日
            for i in range(max_training_days, len(days)):
                day = days[i]
                if day.get("main_exercises"):
                    day["main_exercises"] = []
                    logger.info(
                        f"_enforce_rest_days: 第{phase.get('phase_id', '?')}阶段 "
                        f"第{week.get('week_index', '?')}周 "
                        f"Day{day.get('day_index', '?')} 转为休息日"
                    )
    return phases

def _ensure_full_weeks(phases: list, days_per_week: int = 7) -> list:
    """确保每周恰好有 days_per_week 天。

    - 不足 7 天的周：补全日（main_exercises=[]），追加到周末
    - 超过 7 天的周：截断到 7 天
    - 补全的天自动标记为休息日

    这保证 total_duration_days 的计算准确（2阶段 × 2周 × 7天 = 28天）。
    """
    for phase in phases:
        for week in phase.get("weeks", []):
            days = week.get("days", [])
            days.sort(key=lambda d: d.get("day_index", 0))

            if len(days) < days_per_week:
                # 补全缺失天数（作为休息日）
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
                # 截断到 7 天
                week["days"] = days[:days_per_week]
                logger.info(
                    f"_ensure_full_weeks: 第{phase.get('phase_id', '?')}阶段 "
                    f"第{week.get('week_index', '?')}周 截断到 {days_per_week} 天"
                )
    return phases

def _try_build_phases_from_content(content: str, state: KnowledgeQAState) -> list:
    """从 S3 运动类型推荐构建降级 phases。

    当 plan_outline LLM 调用返回空 phases 时的最终降级策略。
    从第 3 节的 exercise_types 构建完整阶段结构，包含：
    - 按 tier 分类的运动调度（primary 每天、secondary 轮换、supplementary 补充）
    - 阶段渐进（适应期 vs 提升期的强度/时长递增）
    - 每个 exercise 填充 category/target_skill 等 expand 所需字段
    """
    s3 = state.sections.get(3)
    exercise_types = []
    if s3 and s3.structured_data:
        exercise_types = s3.structured_data.get("exercise_types", [])

    if not exercise_types:
        return []

    # 按 tier 分组
    primary = [et for et in exercise_types if et.get("tier") == "primary"]
    secondary = [et for et in exercise_types if et.get("tier") == "secondary"]
    supplementary = [et for et in exercise_types if et.get("tier") == "supplementary"]
    # 确保每组非空（回退到全列表）
    if not primary:
        primary = exercise_types[:2]
    if not secondary:
        secondary = exercise_types[2:4] if len(exercise_types) > 2 else exercise_types[:2]

    ex_id_counter = [1]  # mutable counter for nested functions

    def _make_exercise(etype: dict, phase_idx: int) -> dict:
        """从运动类型构建 exercise 条目（含 expand 所需的完整字段）"""
        eid = f"EX{ex_id_counter[0]:03d}"
        ex_id_counter[0] += 1
        # 适应期偏短偏低，提升期递增
        base_duration = 20 if phase_idx == 0 else 30
        base_intensity = "低" if phase_idx == 0 else "中"
        tier = etype.get("tier", "secondary")
        if tier == "primary":
            base_duration += 5
        return {
            "exercise_id": eid,
            "name": etype.get("name", ""),
            "type_id": etype.get("type_id", ""),
            "category": etype.get("category", ""),
            "duration_min": base_duration,
            "intensity": base_intensity,
            "target_skill": ", ".join(etype.get("target_skills", [])[:2]),
            "citation_ids": etype.get("citation_ids", []),
        }

    def _build_week_schedule(phase_idx: int, week_idx: int) -> dict:
        """构建一周 5 天的运动安排"""
        days = []
        for day_idx in range(5):
            exercises = []
            # 每天：1 个 primary + 轮换 secondary/supplementary
            if primary:
                p_idx = day_idx % len(primary)
                exercises.append(_make_exercise(primary[p_idx], phase_idx))
            # 交替安排 secondary 和 supplementary
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
