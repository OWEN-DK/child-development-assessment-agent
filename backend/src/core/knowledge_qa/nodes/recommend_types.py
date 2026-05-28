"""第 3 节：运动类型推荐 Agent 节点
始终基于前序分析推荐运动类型，不再做领域跳过判断。
"""

import json
import logging
from typing import Any, Dict

from src.core.knowledge_qa.nodes.base import _run_section_node
from src.schemas.knowledge_qa import (
    KnowledgeQAState,
    Section3Response,
    SectionOutput,
)

logger = logging.getLogger(__name__)


async def recommend_types_node(state: KnowledgeQAState) -> Dict[str, Any]:
    """第 3 节：运动类型推荐。依赖第 2 节输出。
    始终生成运动类型推荐，无论问题是否显式提及运动。
    """

    def build_msg(s, prompt):
        s1 = s.sections.get(1)
        s2 = s.sections.get(2)
        return prompt["user_template"].format(
            question=s.question,
            section_1_content=s1.content if s1 else "",
            section_2_content=s2.content if s2 else "",
            section_2_structured=json.dumps(
                s2.structured_data if s2 else {}, ensure_ascii=False
            ),
            matched_book_ids=json.dumps(s.matched_book_ids),
            knowledge_context=s.knowledge_context or "",
        )

    result = await _run_section_node(
        state=state,
        section_index=3,
        section_label="运动类型推荐",
        prompt_key="section_3",
        response_format=Section3Response,
        build_user_message=build_msg,
        step_label="recommend_types",
    )

    # Post-process: 精简 S3 content 为简短摘要（100 字以内）
    # 详细 Markdown 由前端从 structured_data 渲染
    # 同时验证 exercise_types 非空
    sections = result.get("sections", {})
    s3 = sections.get(3)
    if s3:
        from src.core.knowledge_qa.nodes.base import get_exercise_json_path
        s3 = _validate_and_fix_s3_structured_data(s3, get_exercise_json_path())
        s3.content = _simplify_s3_content(s3)
        sections[3] = s3
        result["sections"] = sections
    return result



def _simplify_s3_content(section: SectionOutput) -> str:
    """从 S3 structured_data 生成简短摘要，替代 LLM 生成的冗长 Markdown。"""
    sd = section.structured_data
    if not isinstance(sd, dict):
        return section.content[:100] if section.content else "运动类型推荐"

    ets = sd.get("exercise_types", [])
    if not ets:
        return "已根据孩子情况生成个性化运动类型推荐。"

    names = []
    tiers = {"primary": "核心", "secondary": "辅助", "supplementary": "补充"}
    for et in ets[:5]:
        name = et.get("name", "")
        tier = tiers.get(et.get("tier", ""), "")
        if name:
            names.append(f"{name}({tier})" if tier else name)

    child_age = sd.get("child_age_group", "")
    age_hint = f"适用于{child_age}" if child_age else ""

    return f"针对{age_hint}孩子推荐{len(ets)}种运动类型{'，包括' + '、'.join(names) if names else ''}。"


def _validate_and_fix_s3_structured_data(s3: SectionOutput, exercise_list_path: str) -> SectionOutput:
    """后处理：验证 S3 structured_data 中的 exercise_types 非空且名称合法。
    如果为空，回退到基于内容和运动清单提取运动类型。
    """
    sd = s3.structured_data
    if not isinstance(sd, dict):
        return s3

    ets = sd.get("exercise_types", [])
    if ets:
        return s3  # 已有数据，不再处理

    # exercise_types 为空，尝试从 content 和运动清单提取
    import json
    from pathlib import Path

    try:
        with open(exercise_list_path, "r", encoding="utf-8") as f:
            ex_data = json.load(f)
    except Exception:
        return s3  # 无法加载运动清单，保持原样

    exercises = ex_data.get("exercises", [])
    content = (s3.content or "").lower()

    # 从内容中模糊提取提到的运动名称
    matched = []
    for ex in exercises:
        name = ex.get("name", "")
        if name and name in s3.content:
            matched.append({
                "type_id": f"ET{ex['id']:03d}",
                "name": name,
                "tier": "secondary",
                "category": ex.get("type", ""),
                "target_problem_ids": [],
                "target_skills": [],
                "recommendation_rationale": ex.get("benefits", ""),
                "citation_ids": [],
            })

    if not matched:
        return s3  # 无匹配，保持原样

    # 更新 structured_data
    new_sd = dict(sd)
    new_sd["exercise_types"] = matched[:8]
    s3.structured_data = new_sd

    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"S3 exercise_types 降级填充: 从内容提取 {len(matched)} 项运动")

    return s3
