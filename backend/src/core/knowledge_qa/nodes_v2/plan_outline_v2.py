"""第 4 节大纲 v2：运动方案大纲 — 合并 Neo4j 知识图谱上下文。

在 v1 基础上，将 Neo4j 查询结果（运动推荐、跨书关系）注入 prompt，
使大纲生成基于结构化知识而非仅依赖向量检索。
"""

import asyncio
import json
import logging
from typing import Any, Dict

from src.core.knowledge_qa.nodes.plan_outline import plan_outline_node as _v1_node
from src.schemas.knowledge_qa import KnowledgeQAState, push_progress

logger = logging.getLogger(__name__)


def _build_neo4j_outline_context(neo4j_knowledge: dict) -> str:
    """构建 Neo4j 知识用于大纲生成的上下文。"""
    parts = []

    # 运动推荐
    exercises = neo4j_knowledge.get("exercises", [])
    if exercises:
        names = [e.get("name", "") for e in exercises[:10] if e.get("name")]
        if names:
            parts.append(f"知识图谱推荐运动: {', '.join(names)}")

    # 跨书关系
    cross_book = neo4j_knowledge.get("cross_book_relations", {})
    if cross_book:
        consensus = cross_book.get("consensus", [])
        conflicts = cross_book.get("conflicts", [])
        if consensus:
            topics = [c.get("topic", "") for c in consensus[:3]]
            parts.append(f"跨书共识主题: {', '.join(topics)}")
        if conflicts:
            topics = [c.get("topic", "") for c in conflicts[:3]]
            parts.append(f"⚠️ 跨书冲突主题: {', '.join(topics)}")

    return "\n".join(parts) if parts else ""


async def plan_outline_v2_node(state: KnowledgeQAState) -> Dict[str, Any]:
    """第 4 节大纲 v2：融合 Neo4j 知识生成运动方案大纲。"""
    neo4j_ctx = _build_neo4j_outline_context(state.neo4j_knowledge)
    if neo4j_ctx:
        logger.info("S4 outline v2: 注入 Neo4j 上下文")
        # 将 Neo4j 上下文追加到 knowledge_context
        enriched = state.model_copy(update={
            "knowledge_context": (state.knowledge_context or "") + f"\n\n## 知识图谱参考\n{neo4j_ctx}",
        })
        return await _v1_node(enriched)

    return await _v1_node(state)
