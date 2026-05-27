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

    return await _run_section_node(
        state=state,
        section_index=3,
        section_label="运动类型推荐",
        prompt_key="section_3",
        response_format=Section3Response,
        build_user_message=build_msg,
        step_label="recommend_types",
    )
