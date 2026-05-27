"""第 2 节：问题识别 Agent 节点"""

import json
import logging
from typing import Any, Dict

from src.core.knowledge_qa.nodes.base import _run_section_node
from src.schemas.knowledge_qa import (
    KnowledgeQAState,
    NoMatchingBooksError,
    Section2Response,
)

logger = logging.getLogger(__name__)


async def identify_problems_node(state: KnowledgeQAState) -> Dict[str, Any]:
    """第 2 节：问题识别。依赖第 1 节输出 + match_books 成功。"""
    if not state.matched_book_ids:
        raise NoMatchingBooksError("未匹配到相关书籍，无法继续生成")

    def build_msg(s, prompt):
        s1 = s.sections.get(1)
        return prompt["user_template"].format(
            question=s.question,
            section_1_content=s1.content if s1 else "",
            section_1_structured=json.dumps(
                s1.structured_data if s1 else {}, ensure_ascii=False
            ),
            matched_book_ids=json.dumps(s.matched_book_ids),
            knowledge_context=s.knowledge_context or "",
        )

    return await _run_section_node(
        state=state,
        section_index=2,
        section_label="问题识别",
        prompt_key="section_2",
        response_format=Section2Response,
        build_user_message=build_msg,
        step_label="identify_problems",
    )
