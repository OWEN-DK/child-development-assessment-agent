"""第 2 节 v2：问题识别 — 融合 Neo4j RootCause 数据。

在 v1 基础上，将 Neo4j 中已有的 RootCause 节点注入 prompt，
帮助 LLM 更精准地识别问题的根本原因。
"""

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


def _build_neo4j_rootcause_context(neo4j_knowledge: dict) -> str:
    """从 Neo4j 知识中提取 RootCause 相关上下文。"""
    problem_context = neo4j_knowledge.get("problem_context", {})
    if not problem_context:
        return ""

    root_causes = problem_context.get("root_causes", [])
    if not root_causes:
        return ""

    lines = ["## Neo4j 已知根本原因参考"]
    for rc in root_causes:
        name = rc.get("name", "未知")
        desc = rc.get("description", "")
        related_problems = rc.get("related_problems", [])
        line = f"- **{name}**"
        if desc:
            line += f": {desc}"
        if related_problems:
            line += f" (关联问题: {', '.join(related_problems)})"
        lines.append(line)

    return "\n".join(lines)


async def identify_problems_v2_node(state: KnowledgeQAState) -> Dict[str, Any]:
    """第 2 节 v2：问题识别，融合 Neo4j RootCause。"""
    if not state.matched_book_ids:
        raise NoMatchingBooksError("未匹配到相关书籍，无法继续生成")

    neo4j_ctx = _build_neo4j_rootcause_context(state.neo4j_knowledge)

    def build_msg(s, prompt):
        s1 = s.sections.get(1)
        knowledge_extra = f"\n\n{neo4j_ctx}" if neo4j_ctx else ""

        return prompt["user_template"].format(
            question=s.question,
            section_1_content=s1.content if s1 else "",
            section_1_structured=json.dumps(
                s1.structured_data if s1 else {}, ensure_ascii=False
            ),
            matched_book_ids=json.dumps(s.matched_book_ids),
            knowledge_context=(s.knowledge_context or "") + knowledge_extra,
        )

    return await _run_section_node(
        state=state,
        section_index=2,
        section_label="问题识别",
        prompt_key="section_2",
        response_format=Section2Response,
        build_user_message=build_msg,
        step_label="identify_problems_v2",
    )
