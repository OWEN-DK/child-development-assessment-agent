"""矛盾审计 v2：优先读取 Neo4j 跨书关系，LLM 仅补漏。

在 v1 基础上：
1. 优先从 Neo4j 获取已标记的跨书关系（CONSENSUS/COMPLEMENTS/CONFLICTS）
2. Neo4j 有数据时直接注入 S5 结论，跳过 LLM 审计
3. Neo4j 无数据时回退到 v1 全量 LLM 审计
"""

import logging
from typing import Any, Dict

from src.core.knowledge_qa.nodes.contradiction_audit import (
    contradiction_audit_node as _v1_node,
)
from src.schemas.knowledge_qa import KnowledgeQAState, push_progress

logger = logging.getLogger(__name__)


def _extract_neo4j_contradictions(neo4j_knowledge: dict) -> list[dict]:
    """从 Neo4j 跨书关系中提取矛盾信息。"""
    cross_book = neo4j_knowledge.get("cross_book_relations", {})
    if not cross_book:
        return []

    contradictions = []

    # 冲突关系 → 直接作为矛盾
    for conflict in cross_book.get("conflicts", []):
        contradictions.append({
            "topic": conflict.get("topic", "未知主题"),
            "view_a": conflict.get("view_a", ""),
            "view_b": conflict.get("view_b", ""),
            "resolution": conflict.get("resolution", "建议结合两本书的观点，根据孩子具体情况选择"),
            "severity": conflict.get("severity", "moderate"),
            "source": "neo4j",
        })

    return contradictions


async def contradiction_audit_v2_node(state: KnowledgeQAState) -> Dict[str, Any]:
    """矛盾审计 v2：优先使用 Neo4j 跨书关系。"""
    neo4j_contradictions = _extract_neo4j_contradictions(state.neo4j_knowledge)

    if neo4j_contradictions:
        logger.info(
            "矛盾审计 v2: Neo4j 提供 %d 条跨书冲突，跳过 LLM 审计",
            len(neo4j_contradictions),
        )
        await push_progress(
            "contradiction_audit",
            f"知识图谱已识别 {len(neo4j_contradictions)} 条跨书观点冲突",
        )
        # 直接返回 Neo4j 结果，注入 state.contradictions
        return {"contradictions": neo4j_contradictions}

    # 降级：回退到 v1 LLM 全量审计
    logger.info("矛盾审计 v2: Neo4j 无跨书冲突，回退 v1 LLM 审计")
    return await _v1_node(state)
