"""第 3 节：运动类型推荐 Agent 节点

重设计：从 exercise_type_set 选择运动类型（按序号），而非从预筛选运动列表选择。

流程：
1. 从 state 读取 exercise_type_set（标准化类型集合）+ exercise_list（完整运动列表）
2. 构建类型选择表 Markdown 注入 prompt
3. LLM 从类型表中选择序号 + tier + target_problem_ids
4. 后处理：序号校验 → 代码填充（从 exercise_list 按类型过滤） → content 生成
5. 输出 selected_exercise_types 到 state（S4 消费）
"""

import asyncio
import json
import logging
from typing import Any, Dict

from src.core.knowledge_qa.nodes.base import (
    SKILL_KEYWORDS,
    _build_empty_search_fallback,
    _direct_search,
    _format_search_context,
    _get_model_name,
    _get_prompt_pair,
    _get_temperature,
    _section_fallback,
    get_exercise_json_path,
    get_timeout,
    push_progress,
)
from src.core.llm.factory import LLMServiceFactoryCompat
from src.schemas.knowledge_qa import (
    KnowledgeQAState,
    S3SelectionItem,
    S3SelectionResponse,
    SectionOutput,
)

logger = logging.getLogger(__name__)


# ==================== 主入口 ====================


async def recommend_types_node(state: KnowledgeQAState) -> Dict[str, Any]:
    """第 3 节：运动类型推荐。依赖第 2 节输出。

    从 exercise_type_set 中选择运动类型（按序号），而非从预筛选运动列表选择。
    LLM 输出 index（exercise_type_set 数组序号），代码反查完整类型信息。
    """
    await push_progress("section_3_generating", "正在生成第 3 节：运动类型推荐…")

    try:
        # 取消信号检查
        from src.schemas.knowledge_qa import get_progress_context
        ctx = get_progress_context()
        if ctx and ctx.get("cancellation_event") and ctx["cancellation_event"].is_set():
            raise asyncio.CancelledError("任务已被取消")

        # Step 0: 从 state 读取结构化运动数据
        exercise_type_set = state.exercise_type_set
        exercise_list = state.exercise_list

        if not exercise_type_set:
            logger.warning("S3: exercise_type_set 为空，无法执行类型选择")
            return await _section_fallback(state, 3, "运动类型推荐", "exercise_type_set 为空")

        # 构建类型选择表 + 类型→运动映射
        type_set_markdown = _build_type_set_markdown(exercise_type_set, exercise_list)
        exercise_map = _build_exercise_map(exercise_list)

        # Step 1: 获取知识上下文
        bundle = getattr(state, "knowledge_bundle", None)
        s3_query = state.section_queries.get(3, state.question)

        if bundle is not None:
            from src.core.knowledge_qa.bundle_consumer import (
                extract_for_section, build_priority_context,
            )
            section_passages = extract_for_section(bundle, 3, s3_query)
            search_context = build_priority_context(
                bundle=bundle,
                section_passages=section_passages,
                section_index=3,
                custom_knowledge_context=getattr(state, "custom_knowledge_context", "") or "",
                knowledge_context=getattr(state, "knowledge_context", "") or "",
            )
            if section_passages:
                logger.info("S3 Bundle 模式: %d passages", len(section_passages))
            else:
                logger.warning("S3 Bundle passages 为空，继续使用 S1/S2 内容 + 运动清单生成")
        else:
            search_results = await _direct_search(
                s3_query, state.matched_book_ids, state=state
            )
            search_context = _format_search_context(search_results)
            logger.info(f"S3 _direct_search: {len(search_results)} 条")

            if not search_results:
                logger.warning("S3 知识库无搜索结果，继续使用 S1/S2 内容 + 运动清单生成")
                search_context = "（知识库无直接检索结果，请基于前序分析和运动清单生成推荐）"

        # Step 2: 构建 prompt + full_message
        prompt = await _get_prompt_pair("section_3")
        user_message = _build_s3_user_message(state, prompt)
        full_message = _build_s3_full_message(
            user_message=user_message,
            search_context=search_context,
            previous_sections=state.sections,
            knowledge_context=state.knowledge_context or "",
            type_set_markdown=type_set_markdown,
        )

        # Step 3: LLM 调用（S3SelectionResponse 轻量输出）
        model = LLMServiceFactoryCompat.create_raw(
            model_name=await _get_model_name("recommend_types"),
            temperature=await _get_temperature("recommend_types"),
        )
        structured_model = model.with_structured_output(S3SelectionResponse)
        timeout = get_timeout("recommend_types")
        response = await asyncio.wait_for(
            structured_model.ainvoke([
                {"role": "system", "content": prompt["system"]},
                {"role": "user", "content": full_message},
            ]),
            timeout=timeout,
        )

        # Step 4: 后处理
        result = _build_s3_result(
            response, exercise_type_set, exercise_list, exercise_map, state,
        )

        await push_progress("section_3_done", "第 3 节：运动类型推荐已完成")
        return result

    except asyncio.TimeoutError:
        logger.warning(f"S3 生成超时 ({timeout}s)")
        return await _section_fallback(state, 3, "运动类型推荐", "生成超时")
    except Exception as e:
        logger.exception("S3 生成失败")
        return await _section_fallback(state, 3, "运动类型推荐", str(e))


# ==================== 类型选择表构建 ====================


def _build_type_set_markdown(
    exercise_type_set: list[str],
    exercise_list: list[dict],
) -> str:
    """从 exercise_type_set 构建类型选择表 Markdown。

    每行含：序号 | 运动类型 | 包含运动数 | 代表性运动
    """
    # 预计算每个类型下的运动
    type_to_exercises: dict[str, list[str]] = {}
    for ex in exercise_list:
        t = ex.get("type", "")
        type_to_exercises.setdefault(t, []).append(ex.get("name", ""))

    lines = [
        "| 序号 | 运动类型 | 包含运动数 | 代表性运动 |",
        "|------|---------|-----------|-----------|",
    ]
    for i, type_name in enumerate(exercise_type_set):
        names = type_to_exercises.get(type_name, [])
        count = len(names)
        repr_names = "、".join(names[:3])
        if count > 3:
            repr_names += f"…（共{count}项）"
        display_name = _clean_type_name(type_name)
        lines.append(f"| {i} | {display_name} | {count} | {repr_names} |")

    return "\n".join(lines)


def _build_exercise_map(exercises: list[dict]) -> dict[str, dict]:
    """构建 type → exercises 列表的映射。"""
    result: dict[str, list[dict]] = {}
    for ex in exercises:
        t = ex.get("type", "")
        result.setdefault(t, []).append(ex)
    return result


# ==================== Message 构建 ====================


def _build_s3_user_message(state: KnowledgeQAState, prompt: dict) -> str:
    """从模板渲染 S3 的 user message（前序节内容 + 占位符替换）。"""
    s1 = state.sections.get(1)
    s2 = state.sections.get(2)
    return prompt["user_template"].format(
        question=state.question,
        section_1_content=s1.content if s1 else "",
        section_2_content=s2.content if s2 else "",
        section_2_structured=json.dumps(
            s2.structured_data if s2 else {}, ensure_ascii=False
        ),
        matched_book_ids=json.dumps(state.matched_book_ids),
        knowledge_context=state.knowledge_context or "",
    )


def _build_s3_full_message(
    user_message: str,
    search_context: str,
    previous_sections: Dict[int, SectionOutput],
    knowledge_context: str,
    type_set_markdown: str,
) -> str:
    """构建 S3 的完整 user message。

    替代 _build_full_user_message：exercise_context 替换为类型选择表。
    """
    parts = [user_message]

    if search_context and search_context != "（未搜索到相关内容）":
        parts.append(f"\n\n## 知识库检索结果\n{search_context}")

    # 前序节内容
    if previous_sections:
        prev_parts = []
        for i in sorted(previous_sections.keys()):
            sec = previous_sections[i]
            if sec and sec.content:
                prev_parts.append(f"### 第{i}节\n{sec.content[:800]}")
        if prev_parts:
            parts.append(f"\n\n## 前序节内容\n" + "\n\n".join(prev_parts))

    if knowledge_context:
        parts.append(f"\n\n## 知识上下文（预取）\n{knowledge_context}")

    if type_set_markdown:
        parts.append(f"\n\n## 运动类型集合（exercise_type_set）\n{type_set_markdown}")

    return "\n\n".join(parts)


# ==================== 后处理 ====================


def _validate_selections(
    selections: list[S3SelectionItem],
    exercise_type_set: list[str],
) -> list[S3SelectionItem]:
    """过滤掉超出 exercise_type_set 范围的 index。"""
    max_index = len(exercise_type_set) - 1
    valid = [s for s in selections if 0 <= s.index <= max_index]
    if len(valid) < len(selections):
        invalid = [s.index for s in selections if not (0 <= s.index <= max_index)]
        logger.warning(f"S3 过滤 {len(invalid)} 个越界 index: {invalid}")
    return valid


def _infer_skills(exercise: dict) -> list[str]:
    """从运动的 benefits 字段直接提取训练效果（不再关键词推导）。"""
    benefits = exercise.get("benefits", "")
    if not benefits:
        return []
    # 按中文分号/顿号拆分为多条效果
    import re
    parts = re.split(r"[；;、]", benefits)
    return [p.strip() for p in parts if p.strip()]


def _build_s3_result(
    response: S3SelectionResponse,
    exercise_type_set: list[str],
    exercise_list: list[dict],
    exercise_map: dict[str, list[dict]],
    state: KnowledgeQAState,
) -> Dict[str, Any]:
    """后处理：index 校验 → 代码填充 → content 生成 → 构建 SectionOutput。"""
    # 4a. index 校验
    valid_selections = _validate_selections(response.selections, exercise_type_set)

    # 全部无效 → 降级
    if not valid_selections and response.selections:
        logger.warning("S3 所有 index 无效，触发降级逻辑")
        fallback_section = SectionOutput(
            index=3,
            title="运动类型推荐",
            content="运动类型推荐",
            citations=[],
            structured_data={},
        )
        fallback_section = _validate_and_fix_s3_structured_data(
            fallback_section, exercise_type_set, exercise_list,
        )
        sections = dict(state.sections)
        sections[3] = fallback_section
        return {
            "sections": sections,
            "current_step": ["section_3_done"],
            "errors": state.errors + ["s3_all_indices_invalid"],
            "partial": True,
        }

    # 4b. 代码填充：从 index 反查类型信息 + 该类型下的运动
    # 构建 exercise → exercise_list 位置索引的映射（用于 S4 exercise_index 反查）
    id_to_list_index: dict[int, int] = {}
    for pos, ex in enumerate(exercise_list):
        ex_id = ex.get("id")
        if ex_id is not None:
            id_to_list_index[ex_id] = pos

    matched_books = [b.title for b in state.matched_books_detail]
    exercise_types: list[dict] = []
    selected_exercise_types: list[dict] = []

    for sel in valid_selections:
        type_name = exercise_type_set[sel.index]
        exercises_of_type = exercise_map.get(type_name, [])
        # 为每个 exercise 写入 _exercise_index（在 exercise_list 中的位置）
        for ex in exercises_of_type:
            ex_id = ex.get("id")
            ex["_exercise_index"] = id_to_list_index.get(ex_id, ex_id - 1 if ex_id else 0)
        exercise_types.append({
            "type_index": sel.index,
            "type": type_name,
            "name": _clean_type_name(type_name),
            "tier": sel.tier,
            "target_problem_ids": sel.target_problem_ids,
            "target_skills": _infer_skills(exercises_of_type[0]) if exercises_of_type else [],
            "recommendation_rationale": sel.recommendation_rationale,
            "citation_ids": [],
            "source_books": matched_books,
        })
        selected_exercise_types.append({
            "index": sel.index,
            "type": type_name,
            "tier": sel.tier,
            "target_problem_ids": sel.target_problem_ids,
            "recommendation_rationale": sel.recommendation_rationale,
            "exercises": exercises_of_type,
        })

    # 构建 structured_data
    structured_data = {
        "exercise_types": exercise_types,
        "child_age_group": response.child_age_group,
    }

    # 4c. content 生成
    content = _generate_s3_content(structured_data)

    section = SectionOutput(
        index=3,
        title="运动类型推荐",
        content=content,
        citations=[],
        structured_data=structured_data,
    )

    sections = dict(state.sections)
    sections[3] = section

    return {
        "sections": sections,
        "current_step": ["section_3_done"],
        "selected_exercise_types": selected_exercise_types,
    }


def _clean_type_name(type_name: str) -> str:
    """去除运动类型名称中的括号后缀，用于展示。

    "拉伸/瑜伽(综合系统)" → "拉伸/瑜伽"
    "力量训练(战斗/治疗)" → "力量训练"
    "呼吸调节" → "呼吸调节"（无括号，原样返回）
    """
    import re
    return re.sub(r"[（(][^）)]*[）)]$", "", type_name).strip() or type_name


def _generate_s3_content(sd: dict) -> str:
    """从 structured_data 用模板生成 SSE 预览和下载用的文本摘要。"""
    ets = sd.get("exercise_types", [])
    if not ets:
        return "运动类型推荐"

    # 清理类型名 + 去重（保留顺序）
    seen: set[str] = set()
    names: list[str] = []
    tier_counts: dict[str, int] = {"primary": 0, "secondary": 0, "supplementary": 0}
    tier_labels = {"primary": "核心", "secondary": "辅助", "supplementary": "补充"}
    for et in ets:
        raw_name = et.get("type", "")
        name = _clean_type_name(raw_name)
        tier = et.get("tier", "")
        if name and name not in seen:
            names.append(name)
            seen.add(name)
        if tier in tier_counts:
            tier_counts[tier] += 1

    child_age = sd.get("child_age_group", "")
    # 措辞修正："适用于7岁男孩" → "7岁男孩"
    age_hint = child_age.replace("适用于", "") if child_age else ""

    tier_parts = []
    for t_key in ("primary", "secondary", "supplementary"):
        cnt = tier_counts[t_key]
        if cnt > 0:
            tier_parts.append(f"{tier_labels[t_key]}{cnt}项")
    tier_summary = f"（{'，'.join(tier_parts)}）" if tier_parts else ""

    name_str = "、".join(names[:6]) if names else ""
    return (
        f"针对{age_hint}推荐{len(ets)}种运动类型{tier_summary}"
        f"{'，包括' + name_str if name_str else ''}。"
    )


# ==================== 降级逻辑 ====================


def _validate_and_fix_s3_structured_data(
    s3: SectionOutput,
    exercise_type_set: list[str],
    exercise_list: list[dict],
) -> SectionOutput:
    """兜底：exercise_types 为空时，从 content 和运动类型集合模糊匹配提取。"""
    sd = s3.structured_data
    if not isinstance(sd, dict):
        s3.structured_data = {}
        sd = {}

    ets = sd.get("exercise_types", [])
    if ets:
        return s3

    content = s3.content or ""

    matched = []
    for i, type_name in enumerate(exercise_type_set):
        if type_name in content:
            exercises_of_type = [ex for ex in exercise_list if ex.get("type") == type_name]
            matched.append({
                "type_index": i,
                "type": type_name,
                "name": _clean_type_name(type_name),
                "tier": "secondary",
                "target_problem_ids": [],
                "target_skills": _infer_skills(exercises_of_type[0]) if exercises_of_type else [],
                "recommendation_rationale": "",
                "citation_ids": [],
                "source_books": [],
            })

    if not matched:
        return s3

    new_sd = dict(sd)
    new_sd["exercise_types"] = matched[:8]
    s3.structured_data = new_sd
    s3.content = _generate_s3_content(new_sd)

    logger.info(f"S3 兜底填充: 从内容提取 {len(matched)} 个运动类型")
    return s3


# ==================== S3 引用生成（入口函数保留） ====================


async def generate_s3_citations_node(state: KnowledgeQAState) -> Dict[str, Any]:
    """为 S3 独立生成引用（委托给通用引用生成函数）。"""
    from src.core.knowledge_qa.nodes.generate_s1_s2_citations import (
        _generate_citations_for_section,
    )
    return await _generate_citations_for_section(state, 3, "运动类型推荐")
