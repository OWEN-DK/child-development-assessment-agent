"""第 1 节：孩子状态分析 Agent 节点"""

import json
import logging
from typing import Any, Dict

from src.core.knowledge_qa.nodes.base import _run_section_node
from src.schemas.knowledge_qa import KnowledgeQAState, Section1Response

logger = logging.getLogger(__name__)


async def analyze_child_node(state: KnowledgeQAState) -> Dict[str, Any]:
    """第 1 节：孩子状态分析。提取孩子信息，并搜索知识库获取专业背景知识。"""

    def build_msg(s, prompt):
        return prompt["user_template"].format(
            question=s.question,
            matched_book_ids=json.dumps(s.matched_book_ids),
            knowledge_context=s.knowledge_context or "",
        )

    return await _run_section_node(
        state=state,
        section_index=1,
        section_label="孩子状态分析",
        prompt_key="section_1",
        response_format=Section1Response,
        build_user_message=build_msg,
        step_label="analyze_child",
    )
