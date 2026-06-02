"""第 4 节并行展开：大纲 → 分组 → 并行 LLM → 运动参数

替代原来的 plan_expand_content_node 单次巨大 LLM 调用。
改为：提取大纲中的所有运动条目 → 分组(每组3-4个) → 并行 LLM 生成参数。
"""

import asyncio
import json
import logging
from typing import Any, Dict, List

from src.core.knowledge_qa.nodes.base import (
    _direct_search,
    _format_search_context,
    _get_prompt_pair,
    _invoke_llm_json,
    _invoke_llm_structured,
    _safe_format,
)
from src.schemas.knowledge_qa import (
    ExerciseGroupResponse,
    KnowledgeQAState,
    push_progress,
)

logger = logging.getLogger(__name__)

GROUP_SIZE = 4  # 每组最多 4 个运动
MAX_PARALLEL = 6  # 最大并行 LLM 调用数


def _extract_exercise_slots(outline: dict) -> List[dict]:
    """从大纲中提取所有运动条目及其上下文，保留定位信息用于回填。

    Returns:
        [{slot_idx, phase_idx, week_idx, day_idx, exercise_idx, exercise}]
    """
    slots = []
    idx = 0
    phases = outline.get("phases", [])
    for pi, phase in enumerate(phases):
        for wi, week in enumerate(phase.get("weeks", [])):
            for di, day in enumerate(week.get("days", [])):
                for ei, ex in enumerate(day.get("main_exercises", [])):
                    if ex.get("name"):
                        slots.append({
                            "slot_idx": idx,
                            "phase_idx": pi,
                            "week_idx": wi,
                            "day_idx": di,
                            "exercise_idx": ei,
                            "exercise": {
                                "exercise_id": ex.get("exercise_id", f"EX{idx + 1:03d}"),
                                "name": ex.get("name", ""),
                                "type_id": ex.get("type_id", ""),
                                "category": ex.get("category", ""),
                                "target_skill": ex.get("target_skill", ""),
                                "citation_ids": ex.get("citation_ids", []),
                            },
                        })
                        idx += 1
    return slots


def _split_into_groups(slots: List[dict], group_size: int = GROUP_SIZE) -> List[List[dict]]:
    """将运动条目分组。"""
    return [slots[i:i + group_size] for i in range(0, len(slots), group_size)]


def _build_group_prompt(
    group_slots: List[dict],
    search_context: str,
    state: KnowledgeQAState,
) -> str:
    """为一个分组的运动构建 LLM prompt。

    只包含本组运动的基本信息 + 知识库搜索结果 + 前序节摘要。
    prompt 要求 LLM 输出 ExerciseGroupResponse JSON。
    """
    exercises_json = []
    for s in group_slots:
        ex = s["exercise"]
        ctx = f"  - phase={s['phase_idx']}, week={s['week_idx']}, day={s['day_idx']}"
        exercises_json.append({
            "exercise_id": ex["exercise_id"],
            "name": ex["name"],
            "type_id": ex["type_id"],
            "category": ex["category"],
            "target_skill": ex["target_skill"],
            "citation_ids": ex["citation_ids"],
            "_context": ctx,
        })

    # 前序节摘要
    s1 = state.sections.get(1)
    s2 = state.sections.get(2)
    s3 = state.sections.get(3)

    prev_parts = []
    for i, sec in [(1, s1), (2, s2), (3, s3)]:
        if sec and sec.content:
            prev_parts.append(f"### 第{i}节\n{sec.content[:400]}")

    # S3 运动类型列表（验证运动名称用）
    valid_names = []
    if s3 and s3.structured_data:
        ets = s3.structured_data.get("exercise_types", [])
        for et in ets:
            if et.get("name"):
                valid_names.append(et["name"])

    parts = [
        f"## 任务：为以下 {len(group_slots)} 项运动生成完整执行参数",
        "",
        "```json",
        json.dumps(exercises_json, ensure_ascii=False, indent=2),
        "```",
        "",
        "## 前序分析",
        "\n\n".join(prev_parts) if prev_parts else "（无）",
        "",
        "## 知识库检索结果",
        search_context,
    ]

    if state.knowledge_context:
        parts.append("")
        parts.append("## 预取知识上下文（高优先级）")
        parts.append(state.knowledge_context[:3000])

    if valid_names:
        parts.append("")
        parts.append("## 运动名称约束")
        parts.append("所有运动的 name 必须来自以下合法名称列表（精确匹配）：")
        parts.append("、".join(valid_names))

    if state.exercise_context:
        parts.append("")
        parts.append(state.exercise_context)

    return "\n\n".join(parts)


async def _expand_single_group(
    group_idx: int,
    group_slots: List[dict],
    search_context: str,
    state: KnowledgeQAState,
) -> tuple:
    """展开单个分组：调用 LLM 生成运动参数。失败返回降级数据。"""
    try:
        prompt = await _get_prompt_pair("section_4_expand_group")

        # 模板化 user message：如果 prompt manager 提供了 user_template 则优先使用
        user_template = prompt.get("user_template", "")
        # 始终构建 group_context（无论模板是否存在），确保 {group_context} 占位符可被替换
        group_context = _build_group_prompt(group_slots, search_context, state)
        if user_template and "{group_context}" in user_template:
            # 标准模板：{group_context} 占位符 → 直接替换
            user_message = _safe_format(
                user_template,
                group_context=group_context,
            )
        elif user_template:
            # 自定义模板：使用各个字段展开
            exercises_json = []
            for s in group_slots:
                ex = s["exercise"]
                exercises_json.append({
                    "exercise_id": ex["exercise_id"],
                    "name": ex["name"],
                    "type_id": ex["type_id"],
                    "category": ex["category"],
                    "target_skill": ex["target_skill"],
                    "citation_ids": ex["citation_ids"],
                    "_context": f"phase={s['phase_idx']}, week={s['week_idx']}, day={s['day_idx']}",
                })
            prev_parts = []
            for i in (1, 2, 3):
                sec = state.sections.get(i)
                if sec and sec.content:
                    prev_parts.append(f"### 第{i}节\n{sec.content[:400]}")
            valid_names = []
            s3 = state.sections.get(3)
            if s3 and s3.structured_data:
                for et in s3.structured_data.get("exercise_types", []):
                    if et.get("name"):
                        valid_names.append(et["name"])
            user_message = _safe_format(
                user_template,
                group_context=group_context,
                exercises_json=json.dumps(exercises_json, ensure_ascii=False, indent=2),
                previous_sections="\n\n".join(prev_parts) if prev_parts else "（无）",
                search_context=search_context,
                knowledge_context=state.knowledge_context or "",
                exercise_context=state.exercise_context or "",
                valid_names="、".join(valid_names) if valid_names else "",
                group_size=str(len(group_slots)),
            )
        else:
            user_message = group_context

        # 优先用纯文本 JSON 解析（绕过 DashScope structured_output 对深层嵌套的缺陷）
        exercises = []
        try:
            json_data = await _invoke_llm_json(
                system_prompt=prompt["system"] + "\n\n输出格式：JSON 对象，含 exercises 数组。",
                user_message=user_message,
                step_label="plan_expand",
                timeout_seconds=60,
                no_cache=True,
            )
            exercises = json_data.get("exercises", [])
        except Exception as json_err:
            logger.warning(
                f"plan_expand_parallel: 分组[{group_idx}] JSON 解析失败: {json_err}, "
                f"降级到 structured_output"
            )

        # JSON 解析返回空时，用 structured_output 重试
        if not exercises:
            logger.info(
                f"plan_expand_parallel: 分组[{group_idx}] JSON 解析返回空, "
                f"尝试 structured_output 重试"
            )
            try:
                response = await _invoke_llm_structured(
                    system_prompt=prompt["system"],
                    user_message=user_message,
                    response_format=ExerciseGroupResponse,
                    step_label="plan_expand_struct",
                    timeout_seconds=60,
                    no_cache=True,
                )
                exercises = response.model_dump().get("exercises", [])
            except Exception as struct_err:
                logger.warning(
                    f"plan_expand_parallel: 分组[{group_idx}] structured_output 重试也失败: {struct_err}"
                )
        # 如果两次 LLM 调用都返回空，用 slot 原始数据构建降级条目
        if not exercises:
            logger.warning(
                f"plan_expand_parallel: 分组[{group_idx}] LLM 返回空, 使用 slot 降级数据"
            )
            exercises = []
            for s in group_slots:
                ex = s["exercise"]
                exercises.append({
                    "exercise_id": ex["exercise_id"],
                    "name": ex["name"],
                    "type_id": ex.get("type_id", ""),
                    "category": ex.get("category", ""),
                    "duration_min": 25,
                    "intensity": "中",
                    "intensity_hint": "",
                    "sets": None,
                    "reps": None,
                    "rest_seconds": None,
                    "target_skill": ex.get("target_skill", ""),
                    "notes": "（LLM 未返回参数，使用默认值）",
                    "alternatives": [],
                    "citation_ids": ex.get("citation_ids", []),
                })

        logger.info(
            f"plan_expand_parallel: 分组[{group_idx}] 完成, {len(exercises)} 个运动"
        )
        return (group_idx, exercises)

    except Exception as e:
        logger.warning(f"plan_expand_parallel: 分组[{group_idx}] 失败: {e}")
        # 降级：返回空参数的基本条目
        fallback = []
        for s in group_slots:
            ex = s["exercise"]
            fallback.append({
                "exercise_id": ex["exercise_id"],
                "name": ex["name"],
                "type_id": ex["type_id"],
                "category": ex.get("category", ""),
                "duration_min": 15,
                "intensity": "中",
                "intensity_hint": "",
                "sets": None,
                "reps": None,
                "rest_seconds": None,
                "target_skill": ex.get("target_skill", ""),
                "notes": "（本组生成失败，使用默认参数）",
                "alternatives": [],
                "citation_ids": ex.get("citation_ids", []),
            })
        return (group_idx, fallback)


async def plan_expand_parallel_node(state: KnowledgeQAState) -> Dict[str, Any]:
    """第 4 节并行展开：提取大纲运动条目 → 分组 → 并行生成参数。"""
    outline = state.section_4_outline
    if not outline or not outline.get("phases"):
        return {
            "errors": state.errors + ["section_4_expand: 大纲为空"],
            "current_step": ["section_4_expand_failed"],
        }

    slots = _extract_exercise_slots(outline)
    if not slots:
        logger.info("plan_expand_parallel: 大纲中无运动条目，跳过")
        return {"current_step": ["section_4_expand_empty"]}

    groups = _split_into_groups(slots, GROUP_SIZE)

    await push_progress(
        "section_4_expanding",
        f"正在并行展开 {len(slots)} 项运动参数 ({len(groups)} 组)…",
    )

    # 共享搜索上下文（所有组共用同一份检索结果）
    bundle = getattr(state, "knowledge_bundle", None)

    if bundle is not None:
        from src.core.knowledge_qa.bundle_consumer import (
            extract_for_section, build_priority_context,
        )
        section_passages = extract_for_section(bundle, 4, state.question)
        base_search_context = build_priority_context(
            bundle=bundle, section_passages=section_passages, section_index=4,
            custom_knowledge_context=getattr(state, "custom_knowledge_context", "") or "",
            knowledge_context=getattr(state, "knowledge_context", "") or "",
            exercise_context=state.exercise_context or "",
        )
        # 每组按运动名过滤 Bundle passages 做专项上下文
        group_search_contexts = []
        for group_idx, group_slots in enumerate(groups):
            ex_names = " ".join(
                s["exercise"]["name"] for s in group_slots if s["exercise"].get("name")
            )
            ex_context = base_search_context
            if ex_names and len(ex_names) > 5:
                keywords = [w.strip() for w in ex_names.split() if len(w.strip()) >= 2]
                matched_passages = [
                    p for p in section_passages
                    if any(kw in p.content for kw in keywords)
                ]
                if matched_passages:
                    parts = ["\n\n## 本组运动专项知识"]
                    for mp in matched_passages[:5]:
                        parts.append(f"> **{mp.chapter_title}**\n> {mp.content[:300]}\n")
                    ex_context = base_search_context + "\n".join(parts)
            group_search_contexts.append(ex_context)
        logger.info("S4 expand Bundle 模式: %d passages", len(section_passages))
    else:
        search_results = await _direct_search(state.question, state.matched_book_ids, state=state)
        base_search_context = _format_search_context(search_results)

        # 为每组预取运动专项搜索上下文（含动作要领等关键词）
        group_search_contexts = []
        for group_idx, group_slots in enumerate(groups):
            ex_names = " ".join(
                s["exercise"]["name"] for s in group_slots if s["exercise"].get("name")
            )
            if ex_names and len(ex_names) > 5:
                ex_query = f"{ex_names} 动作要领 执行要点 家长指导"
                try:
                    ex_results = await _direct_search(
                        ex_query, state.matched_book_ids, state=state
                    )
                    gc = _format_search_context(ex_results)
                    if gc:
                        group_search_contexts.append(
                            base_search_context + "\n\n## 本组运动专项检索结果\n" + gc
                        )
                        continue
                except Exception:
                    pass
            group_search_contexts.append(base_search_context)

    # 并行展开（信号量限流）
    sem = asyncio.Semaphore(MAX_PARALLEL)

    async def _limited(group_idx, group_slots):
        async with sem:
            gc = group_search_contexts[group_idx] if group_idx < len(group_search_contexts) else base_search_context
            return await _expand_single_group(
                group_idx, group_slots, gc, state
            )

    try:
        group_results_raw = await asyncio.gather(
            *[_limited(i, g) for i, g in enumerate(groups)],
        )
    except Exception as e:
        logger.exception("plan_expand_parallel: 并行展开异常")
        return {
            "errors": state.errors + [f"section_4_expand: 并行展开失败: {e}"],
            "current_step": ["section_4_expand_failed"],
        }

    # 按 group_idx 排序
    group_results_raw.sort(key=lambda x: x[0])
    all_results = {}
    for gidx, exercises in group_results_raw:
        all_results[str(gidx)] = exercises

    exercise_count = sum(len(v) for v in all_results.values())
    logger.info(
        f"plan_expand_parallel 完成: {exercise_count} 个运动, "
        f"{len(groups)} 组"
    )

    await push_progress(
        "section_4_expanded",
        f"运动参数展开完成：{exercise_count} 项",
    )

    return {
        "section_4_group_results": all_results,
        "section_4_slots": slots,
        "current_step": ["section_4_expanded"],
    }
