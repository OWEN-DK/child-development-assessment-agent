"""第 5 节：最终结论 Agent 节点"""

import json
import logging
from typing import Any, Dict

from src.core.knowledge_qa.nodes.base import _run_section_node
from src.schemas.knowledge_qa import KnowledgeQAState, Section5Response


def _safe_truncate_json(data: dict, max_len: int = 500) -> str:
    """安全截断 JSON，确保不在 UTF-8 多字节字符中间截断且不产生非法 JSON 片段。"""
    s = json.dumps(data, ensure_ascii=False)
    if len(s) <= max_len:
        return s
    # 向前搜索最后一个完整 JSON 值结束位置
    cut = s.rfind('",', 0, max_len)
    if cut > 0:
        return s[:cut + 1]
    cut = s.rfind("',", 0, max_len)
    if cut > 0:
        return s[:cut + 1]
    return s[:max_len]

logger = logging.getLogger(__name__)


async def conclusion_node(state: KnowledgeQAState) -> Dict[str, Any]:
    """第 5 节：最终结论。依赖全部前 4 节。"""

    def build_msg(s, prompt):
        parts = []
        for i in range(1, 5):
            sec = s.sections.get(i)
            if sec:
                parts.append(f"## 第{i}节\n{sec.content}\n结构化数据：{_safe_truncate_json(sec.structured_data, 500)}")
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
