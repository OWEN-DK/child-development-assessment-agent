"""query_neo4j_graph 节点 — Layer 1 Neo4j 知识图谱查询入口。

放置位置: backend/src/core/knowledge_qa/nodes_v2/query_neo4j_graph.py
"""

from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)

NEO4J_QUERY_TIMEOUT = 30  # 秒


async def query_neo4j_graph_node(state) -> dict:
    """查询 Neo4j 知识图谱，将结构化知识注入 State。

    Neo4j 不可用或查询失败时返回空字典（不阻塞流水线）。

    Args:
        state: KnowledgeQAState，需包含:
            - question: 用户问题
            - child_profile: 儿童档案
            - matched_books: 匹配的书籍列表
            - sections[1].structured_data: S2 识别的问题/根因

    Returns:
        {"neo4j_knowledge": {...}} 或 {"neo4j_knowledge": {}}
    """
    from core.knowledge_qa.neo4j.driver import neo4j_available

    if not neo4j_available():
        logger.info("Neo4j 不可用，跳过知识图谱查询")
        return {"neo4j_knowledge": {}}

    from core.knowledge_qa.neo4j.query_dispatcher import query_all

    try:
        # 提取 S2 结构化数据
        s2_data = {}
        if hasattr(state, "sections") and len(state.sections) > 1:
            s2_data = state.sections[1].structured_data or {}

        neo4j_knowledge = await asyncio.wait_for(
            query_all(
                question=state.question,
                child_profile=getattr(state, "child_profile", {}),
                matched_book_ids=[b["book_id"] for b in getattr(state, "matched_books", [])],
                s2_problems=[p["name"] for p in s2_data.get("problems", [])],
                s2_root_causes=s2_data.get("root_causes", []),
            ),
            timeout=NEO4J_QUERY_TIMEOUT,
        )
        return {"neo4j_knowledge": neo4j_knowledge}

    except asyncio.TimeoutError:
        logger.warning("Neo4j 查询超时 (%ds)，降级", NEO4J_QUERY_TIMEOUT)
        return {"neo4j_knowledge": {}}
    except Exception as e:
        logger.warning("Neo4j 查询失败，降级: %s", e)
        return {"neo4j_knowledge": {}}
