"""第 1 节 v2：孩子状态分析 — 融合 Neo4j Problem 列表。

在 v1 基础上，将 Neo4j 中已有的 Problem 节点注入 prompt，
帮助 LLM 更准确地识别孩子可能存在的发展问题。
"""

import json
import logging
from typing import Any, Dict

from src.core.knowledge_qa.nodes.base import _run_section_node
from src.schemas.knowledge_qa import KnowledgeQAState, Section1Response

logger = logging.getLogger(__name__)


def _build_neo4j_problem_context(neo4j_knowledge: dict) -> str:
    """从 Neo4j 知识中提取 Problem 相关上下文。"""
    problem_context = neo4j_knowledge.get("problem_context", {})
    if not problem_context:
        return ""

    problems = problem_context.get("problems", [])
    if not problems:
        return ""

    lines = ["## Neo4j 已有发展问题参考"]
    for p in problems:
        severity = p.get("severity", "unknown")
        name = p.get("name", "未知")
        desc = p.get("description", "")
        symptoms = p.get("symptoms", "")
        line = f"- **{name}** (严重度: {severity})"
        if desc:
            line += f" — {desc}"
        if symptoms:
            line += f" | 症状: {symptoms}"
        lines.append(line)

    source_coverage = neo4j_knowledge.get("source_coverage", {})
    if source_coverage:
        total = source_coverage.get("total_books", 0)
        if total > 0:
            lines.append(f"\n> 当前知识图谱已收录 {total} 本书籍的结构化知识")

    return "\n".join(lines)


async def analyze_child_v2_node(state: KnowledgeQAState) -> Dict[str, Any]:
    """第 1 节 v2：孩子状态分析，融合 Neo4j Problem 列表。"""
    neo4j_ctx = _build_neo4j_problem_context(state.neo4j_knowledge)

    def build_msg(s, prompt):
        parts = []
        if neo4j_ctx:
            parts.append(f"### 知识图谱参考\n{neo4j_ctx}")
        knowledge_extra = "\n\n".join(parts) if parts else ""

        return prompt["user_template"].format(
            question=s.question,
            matched_book_ids=json.dumps(s.matched_book_ids),
            knowledge_context=(s.knowledge_context or "") + knowledge_extra,
        )

    return await _run_section_node(
        state=state,
        section_index=1,
        section_label="孩子状态分析",
        prompt_key="section_1",
        response_format=Section1Response,
        build_user_message=build_msg,
        step_label="analyze_child_v2",
    )
