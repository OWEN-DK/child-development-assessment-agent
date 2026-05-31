"""第 5 节：最终结论 Agent 节点"""

import json
import logging
from typing import Any, Dict

from src.core.knowledge_qa.nodes.base import _run_section_node
from src.schemas.knowledge_qa import KnowledgeQAState, Section5Response, SectionOutput


def _summarize_structured_data(section: "SectionOutput") -> str:
    """从 structured_data 提取有意义的摘要文本，替代截断 JSON。

    S3/S4 的 content 已被精简为短摘要（~56-200 字），
    这里从 structured_data 展开关键字段供结论 LLM 理解上下文。
    """
    sd = section.structured_data or {}
    if not sd:
        return ""

    idx = section.index
    if idx == 2:
        problems = sd.get("problems", [])
        if not problems:
            return ""
        lines = ["识别到的问题："]
        for p in problems[:5]:
            name = p.get("name") or p.get("description", "")
            severity = p.get("severity", "")
            lines.append(f"- {name}" + (f"（{severity}）" if severity else ""))
        return "\n".join(lines)

    if idx == 3:
        ets = sd.get("exercise_types", [])
        if not ets:
            return ""
        lines = ["推荐的运动类型："]
        for et in ets[:8]:
            name = et.get("name", "")
            tier_map = {"primary": "核心", "secondary": "辅助", "supplementary": "补充"}
            tier = tier_map.get(et.get("tier", ""), "")
            rationale = (et.get("recommendation_rationale", "") or "")[:80]
            lines.append(f"- {name}" + (f"（{tier}）" if tier else ""))
            if rationale:
                lines.append(f"  理由: {rationale}")
        return "\n".join(lines)

    if idx == 4:
        phases = sd.get("phases", [])
        if not phases:
            return ""
        lines = ["运动方案阶段概览："]
        for ph in phases[:3]:
            phase_name = ph.get("phase_name") or ph.get("name", "")
            ex_names = []
            for wk in (ph.get("weeks") or [])[:1]:
                for day in (wk.get("days") or [])[:2]:
                    for ex in (day.get("main_exercises") or [])[:3]:
                        n = ex.get("name", "")
                        if n:
                            ex_names.append(n)
            if ex_names:
                lines.append(f"- {phase_name}: {', '.join(ex_names)}")
        return "\n".join(lines)

    return ""

logger = logging.getLogger(__name__)


async def conclusion_node(state: KnowledgeQAState) -> Dict[str, Any]:
    """第 5 节：最终结论。依赖全部前 4 节。"""

    def build_msg(s, prompt):
        parts = []

        # ── 自定义知识上下文（最高优先级，§09-5） ──
        custom_ctx = getattr(s, 'custom_knowledge_context', None) or ""
        if custom_ctx.strip():
            parts.append(
                "## ⚡ 专家知识（最高优先级，优先采纳）\n\n"
                + custom_ctx.strip()
                + "\n\n> 💡 以下书籍知识应与上述专家知识对齐。如有冲突，以专家知识为准。\n"
            )

        # ── 三层知识综合（优先）或矛盾审计结果（降级） ──
        synthesis = getattr(s, 'three_layer_synthesis', None) or {}
        if synthesis:
            for item in synthesis.get("consensus", []):
                sources = "、".join(f"《{b}》" for b in item.get("sources", []))
                parts.append(f"## ✅ 统一共识\n{item.get('agreement', '')}\n📖 来源: {sources}")
            for item in synthesis.get("complementary", []):
                parts.append(f"## 🧩 互补完善\n{item.get('integrated_summary', '')}")
            for item in synthesis.get("conflicts", []):
                va = item.get("view_a", {})
                vb = item.get("view_b", {})
                parts.append(
                    f"## ⚠️ 冲突辨析\n"
                    f"- 📖 《{va.get('book', '')}》: {va.get('position', '')}\n"
                    f"- 📖 《{vb.get('book', '')}》: {vb.get('position', '')}\n"
                    f"🔍 原因: {item.get('why_different', '')}\n"
                    f"💡 建议: {item.get('recommendation', '')}"
                )
        elif s.contradictions:
            # 降级: 无三层综合时使用旧的 contradictions
            parts.append("## 跨书籍观点差异（供参考）\n")
            for c in s.contradictions:
                parts.append(
                    f"- **{c.get('topic', '')}**\n"
                    f"  - {c.get('view_a', '')}\n"
                    f"  - {c.get('view_b', '')}\n"
                    f"  - 调和建议: {c.get('resolution', '请根据实际情况判断')}\n"
                )

        for i in range(1, 5):
            sec = s.sections.get(i)
            if sec:
                sd_summary = _summarize_structured_data(sec)
                sd_block = f"\n关键数据：{sd_summary}" if sd_summary else ""
                parts.append(f"## 第{i}节\n{sec.content}{sd_block}")
        return prompt["user_template"].format(
            question=s.question,
            previous_sections="\n\n".join(parts),
            matched_book_ids=json.dumps(s.matched_book_ids),
            knowledge_context=s.knowledge_context or "",
        )

    return await _run_section_node(
        state=state,
        section_index=5,
        section_label="最终结论",
        prompt_key="section_5",
        response_format=Section5Response,
        build_user_message=build_msg,
        step_label="conclusion",
    )
