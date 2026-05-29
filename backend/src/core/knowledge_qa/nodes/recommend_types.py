"""第 3 节：运动类型推荐 Agent 节点

自管理 LLM 调用（不通过 _run_section_node），流程：
预筛选候选运动 → 搜索知识库 → LLM 选择 → type_id 校验 → 代码填充 → content 生成
"""

import asyncio
import json
import logging
from pathlib import Path
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

    自管理流程（不通过 _run_section_node）：
    1. 预筛选候选运动（年龄 + 关键词相关度）
    2. 搜索知识库
    3. LLM 从候选表中选择（S3SelectionResponse）
    4. 后处理：type_id 校验 + 代码填充 + content 生成
    """
    await push_progress("section_3_generating", "正在生成第 3 节：运动类型推荐…")

    try:
        # 取消信号检查
        from src.schemas.knowledge_qa import get_progress_context
        ctx = get_progress_context()
        if ctx and ctx.get("cancellation_event") and ctx["cancellation_event"].is_set():
            raise asyncio.CancelledError("任务已被取消")

        # Step 0: 预筛选
        child_age = _extract_child_age(state)
        s2_sd = state.sections.get(2).structured_data if state.sections.get(2) else {}
        keywords = _extract_problem_keywords(s2_sd)
        exercise_data = _load_exercise_data()
        candidates = _prefilter_exercises(
            exercise_data["exercises"], child_age, keywords
        )
        exercise_map = _build_exercise_map(exercise_data["exercises"])
        candidates_markdown = _build_candidates_markdown(candidates)

        # Step 1: 搜索知识库
        search_results = await _direct_search(
            state.question, state.matched_book_ids, state=state
        )
        search_context = _format_search_context(search_results)
        logger.info(f"S3 _direct_search: {len(search_results)} 条")

        if not search_results:
            logger.warning("S3 知识库无搜索结果，跳过 LLM 调用")
            return await _build_empty_search_fallback(state, 3, "运动类型推荐")

        # Step 2: 构建 prompt + full_message
        prompt = await _get_prompt_pair("section_3")
        user_message = _build_s3_user_message(state, prompt)
        full_message = _build_s3_full_message(
            user_message=user_message,
            search_context=search_context,
            previous_sections=state.sections,
            knowledge_context=state.knowledge_context or "",
            candidates_markdown=candidates_markdown,
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
        result = _build_s3_result(response, exercise_map, exercise_data, state, child_age)

        await push_progress("section_3_done", "第 3 节：运动类型推荐已完成")
        return result

    except asyncio.TimeoutError:
        logger.warning(f"S3 生成超时 ({timeout}s)")
        return await _section_fallback(state, 3, "运动类型推荐", "生成超时")
    except Exception as e:
        logger.exception("S3 生成失败")
        return await _section_fallback(state, 3, "运动类型推荐", str(e))


# ==================== 预筛选 ====================


def _load_exercise_data() -> dict:
    """加载运动清单 JSON 数据。"""
    json_path = get_exercise_json_path()
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"加载运动清单失败: {e}")
        return {"exercises": []}


def _extract_child_age(state: KnowledgeQAState) -> int | None:
    """从 S1 structured_data 中提取孩子年龄"""
    s1 = state.sections.get(1)
    if s1 and s1.structured_data:
        profile = s1.structured_data.get("child_profile", {})
        age = profile.get("age")
        if age and isinstance(age, (int, float)):
            return int(age)
    import re
    match = re.search(r'(\d+)\s*岁', state.question)
    if match:
        return int(match.group(1))
    return None


def _extract_problem_keywords(s2_structured_data: dict) -> list[str]:
    """从 S2 structured_data 提取问题关键词。

    取 problems 中每项的 category + name 作为关键词。
    """
    problems = s2_structured_data.get("problems", [])
    keywords: set[str] = set()
    for p in problems:
        if p.get("category"):
            keywords.add(p["category"])
        if p.get("name"):
            keywords.add(p["name"])
    return list(keywords)


def _parse_age_range(age_str: str) -> tuple[int, int] | None:
    """解析运动清单中的年龄段字符串，返回 (min_age, max_age)"""
    if not age_str:
        return None
    import re
    match = re.search(r'[（(](\d+)\s*[岁~～]+\s*(\d+)?[岁]?[）)]', age_str)
    if match:
        min_age = int(match.group(1))
        max_age = int(match.group(2)) if match.group(2) else 120
        return (min_age, max_age)
    match = re.search(r'(\d+)\s*岁\s*\+', age_str)
    if match:
        return (int(match.group(1)), 120)
    return None


def _prefilter_exercises(
    all_exercises: list[dict],
    child_age: int | None,
    problem_keywords: list[str],
) -> list[dict]:
    """年龄过滤 + 相关度排序 + 多样性选择，返回候选列表。

    策略：
    1. 年龄过滤：移除 min_age > child_age 或 max_age < child_age 的运动
    2. 相关度排序：problem_keywords 与运动 benefits 的关键词交集计数
    3. 取 Top 20（按相关度）+ 按 category 分散取 5 项（保证多样性）
    """
    if not all_exercises:
        return []

    # Step 1: 年龄过滤
    if child_age is not None:
        age_filtered = []
        for ex in all_exercises:
            age_range = _parse_age_range(ex.get("age", ""))
            if age_range is None:
                age_filtered.append(ex)  # 无年龄信息的保留
            elif age_range[0] <= child_age <= age_range[1]:
                age_filtered.append(ex)
        if not age_filtered:
            # 极端情况：无适龄运动，跳过年龄过滤使用全量
            logger.warning(f"年龄过滤(child_age={child_age})后无候选，使用全量")
            age_filtered = list(all_exercises)
    else:
        age_filtered = list(all_exercises)

    # Step 2: 相关度排序
    scored: list[tuple[int, dict]] = []
    kw_set = set(problem_keywords)
    for ex in age_filtered:
        benefits = ex.get("benefits", "") or ""
        brain = ex.get("brain_mechanisms", "") or ""
        text = f"{benefits} {brain}"
        score = sum(1 for kw in kw_set if kw in text)
        scored.append((score, ex))
    scored.sort(key=lambda x: x[0], reverse=True)

    # Step 3: Top 20 + 多样性选择
    top = [ex for _, ex in scored[:20]]

    # 按 category 分散取（保证分类多样性）
    by_cat: dict[str, list[dict]] = {}
    for ex in top:
        cat = ex.get("type", "其他")
        by_cat.setdefault(cat, []).append(ex)

    diverse: list[dict] = []
    seen_ids: set[int] = set()
    # 每个分类至少取 1 项（按相关度最高的）
    for cat_exs in by_cat.values():
        ex = cat_exs[0]
        if ex["id"] not in seen_ids:
            diverse.append(ex)
            seen_ids.add(ex["id"])
    # 补足到 25 项（从 top 中按顺序填充）
    for ex in top:
        if ex["id"] not in seen_ids:
            diverse.append(ex)
            seen_ids.add(ex["id"])
        if len(diverse) >= 25:
            break

    return diverse


def _build_exercise_map(exercises: list[dict]) -> dict[str, dict]:
    """构建 type_id → exercise record 的映射。"""
    return {f"ET{ex['id']:03d}": ex for ex in exercises}


def _build_candidates_markdown(candidates: list[dict]) -> str:
    """将候选运动列表格式化为 Markdown 表格，注入 S3 user message。"""
    if not candidates:
        return "（无适龄候选运动，请从通用运动中选择）"

    lines = [
        "| type_id | 运动名称 | 运动类型 | 适用年龄 | 主要益处 |",
        "|---------|---------|---------|---------|---------|",
    ]
    for ex in candidates:
        tid = f"ET{ex['id']:03d}"
        name = ex.get("name", "")
        cat = ex.get("type", "")
        age = ex.get("age", "")
        benefits = (ex.get("benefits", "") or "")[:60]
        lines.append(f"| {tid} | {name} | {cat} | {age} | {benefits} |")

    return "\n".join(lines)


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
    candidates_markdown: str,
) -> str:
    """构建 S3 的完整 user message。

    替代 _build_full_user_message：exercise_context 替换为预筛选候选表。
    """
    parts = [user_message]

    if search_context and search_context != "（未搜索到相关内容）":
        parts.append(f"\n\n## 知识库检索结果\n{search_context}")

    # 前序节内容（与 _run_section_node 一致：截取前 800 字）
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

    if candidates_markdown:
        parts.append(f"\n\n## 候选运动表（预筛选后）\n{candidates_markdown}")

    return "\n\n".join(parts)


# ==================== 后处理 ====================


def _validate_selections(
    selections: list[S3SelectionItem],
    exercise_map: dict[str, dict],
) -> list[S3SelectionItem]:
    """过滤掉运动清单中不存在的 type_id。"""
    valid = [s for s in selections if s.type_id in exercise_map]
    if len(valid) < len(selections):
        invalid_ids = [s.type_id for s in selections if s.type_id not in exercise_map]
        logger.warning(f"S3 过滤 {len(invalid_ids)} 个无效 type_id: {invalid_ids}")
    return valid


def _infer_skills(exercise: dict) -> list[str]:
    """从运动的 benefits + brain_mechanisms 推导 target_skills。"""
    text = f"{exercise.get('benefits', '')} {exercise.get('brain_mechanisms', '')}"
    return [
        skill
        for skill, keywords in SKILL_KEYWORDS.items()
        if any(kw in text for kw in keywords)
    ]


def _build_s3_result(
    response: S3SelectionResponse,
    exercise_map: dict[str, dict],
    exercise_data: dict,
    state: KnowledgeQAState,
    child_age: int | None,
) -> Dict[str, Any]:
    """后处理：type_id 校验 → 代码填充 → content 生成 → 构建 SectionOutput。"""
    # 4a. type_id 校验
    valid_selections = _validate_selections(response.selections, exercise_map)

    # 全部无效 → 触发兜底（使用旧逻辑从 content 模糊匹配）
    if not valid_selections and response.selections:
        logger.warning("S3 所有 type_id 无效，触发兜底逻辑")
        # 构造一个空 structured_data 的 SectionOutput，交给兜底函数
        fallback_section = SectionOutput(
            index=3,
            title="运动类型推荐",
            content="运动类型推荐",
            citations=[],
            structured_data={},
        )
        fallback_section = _validate_and_fix_s3_structured_data(
            fallback_section, get_exercise_json_path()
        )
        sections = dict(state.sections)
        sections[3] = fallback_section
        return {
            "sections": sections,
            "current_step": ["section_3_done"],
            "errors": state.errors + ["s3_all_type_ids_invalid"],
            "partial": True,
            "filtered_exercise_candidates": _build_candidates_markdown(
                _prefilter_exercises(
                    exercise_data["exercises"], child_age,
                    _extract_problem_keywords(
                        state.sections.get(2).structured_data
                        if state.sections.get(2) else {}
                    ),
                )
            ),
        }

    # 4b. 代码填充：从运动清单精确填充每个字段
    matched_books = [b.title for b in state.matched_books_detail]
    exercise_types: list[dict] = []

    for sel in valid_selections:
        ex = exercise_map[sel.type_id]
        exercise_types.append({
            "type_id": sel.type_id,
            "name": ex.get("name", ""),
            "tier": sel.tier,
            "category": ex.get("type", ""),
            "target_problem_ids": sel.target_problem_ids,
            "target_skills": _infer_skills(ex),
            "recommendation_rationale": sel.recommendation_rationale,
            "citation_ids": [],
            "source_books": matched_books,
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

    # 候选运动表存入 state（审计用）
    candidates_markdown = _build_candidates_markdown(
        _prefilter_exercises(
            exercise_data["exercises"], child_age,
            _extract_problem_keywords(
                state.sections.get(2).structured_data
                if state.sections.get(2) else {}
            ),
        )
    )

    return {
        "sections": sections,
        "current_step": ["section_3_done"],
        "filtered_exercise_candidates": candidates_markdown,
    }


def _generate_s3_content(sd: dict) -> str:
    """从 structured_data 用模板生成 SSE 预览和下载用的文本摘要。"""
    ets = sd.get("exercise_types", [])
    if not ets:
        return "运动类型推荐"

    names: list[str] = []
    tier_counts: dict[str, int] = {"primary": 0, "secondary": 0, "supplementary": 0}
    tier_labels = {"primary": "核心", "secondary": "辅助", "supplementary": "补充"}
    for et in ets:
        name = et.get("name", "")
        tier = et.get("tier", "")
        if name:
            names.append(name)
        if tier in tier_counts:
            tier_counts[tier] += 1

    child_age = sd.get("child_age_group", "")
    age_hint = f"适用于{child_age}" if child_age else ""

    tier_parts = []
    for t_key in ("primary", "secondary", "supplementary"):
        cnt = tier_counts[t_key]
        if cnt > 0:
            tier_parts.append(f"{tier_labels[t_key]}{cnt}项")
    tier_summary = f"（{'，'.join(tier_parts)}）" if tier_parts else ""

    name_str = "、".join(names[:6]) if names else ""
    return (
        f"针对{age_hint}孩子推荐{len(ets)}种运动类型{tier_summary}"
        f"{'，包括' + name_str if name_str else ''}。"
    )


# ==================== 兜底逻辑 ====================


def _validate_and_fix_s3_structured_data(
    s3: SectionOutput, exercise_list_path: str
) -> SectionOutput:
    """兜底：exercise_types 为空时，从 content 和运动清单模糊匹配提取运动类型。"""
    sd = s3.structured_data
    if not isinstance(sd, dict):
        s3.structured_data = {}
        sd = {}

    ets = sd.get("exercise_types", [])
    if ets:
        return s3

    try:
        with open(exercise_list_path, "r", encoding="utf-8") as f:
            ex_data = json.load(f)
    except Exception:
        return s3

    exercises = ex_data.get("exercises", [])
    content = s3.content or ""

    matched = []
    for ex in exercises:
        name = ex.get("name", "")
        if name and name in content:
            matched.append({
                "type_id": f"ET{ex['id']:03d}",
                "name": name,
                "tier": "secondary",
                "category": ex.get("type", ""),
                "target_problem_ids": [],
                "target_skills": _infer_skills(ex),
                "recommendation_rationale": ex.get("benefits", ""),
                "citation_ids": [],
                "source_books": [],
            })

    if not matched:
        return s3

    new_sd = dict(sd)
    new_sd["exercise_types"] = matched[:8]
    s3.structured_data = new_sd
    s3.content = _generate_s3_content(new_sd)

    logger.info(f"S3 兜底填充: 从内容提取 {len(matched)} 项运动")
    return s3
