"""多模式查询调度器 — 聚合所有 Neo4j 查询模式。

放置位置: backend/src/core/knowledge_qa/neo4j/query_dispatcher.py
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


async def query_all(
    question: str,
    child_profile: dict,
    matched_book_ids: list[str],
    s2_problems: list[str],
    s2_root_causes: list[str],
) -> dict:
    """执行所有 Neo4j 查询模式，返回聚合结果。

    Args:
        question: 用户原始问题
        child_profile: 儿童档案 {age, gender, ...}
        matched_book_ids: Chroma 匹配的书籍 ID 列表
        s2_problems: S2 识别的问题名称列表
        s2_root_causes: S2 识别的根因列表

    Returns:
        {
            "exercises": [...],
            "cross_book_relations": [...],
            "problem_context": [...],
            "source_coverage": {...},
        }
    """
    from core.knowledge_qa.neo4j.driver import get_neo4j_driver

    driver = get_neo4j_driver()
    if driver is None:
        return {}

    result = {}

    with driver.session() as session:
        result["exercises"] = _query_exercises(session, child_profile, s2_problems)
        result["cross_book_relations"] = _query_cross_book(session, matched_book_ids)
        result["problem_context"] = _query_problem_context(session, s2_problems)
        result["source_coverage"] = _query_source_coverage(session, matched_book_ids)

    return result


def _query_exercises(session, child_profile: dict, problems: list[str]) -> list[dict]:
    """按年龄查询运动推荐，如果有已知问题则优先匹配相关运动。"""
    age = child_profile.get("age", 6)

    # 基础查询: 按年龄筛选适合儿童的运动
    base_query = """
        MATCH (e:Exercise)
        WHERE e.suitable_for_children = true
          AND e.min_age <= $age AND e.max_age >= $age
    """

    # 如果有已知问题，优先返回与问题所在章节相关的运动
    if problems:
        query = base_query + """
            OPTIONAL MATCH (e)<-[:DESCRIBES_EXERCISE]-(ch:Chapter)<-[:HAS_CHAPTER]-(b:Book)
                          <-[:CONTAINS_ENTITY]-(p:Problem)
            WHERE p.name IN $problems
            WITH e, CASE WHEN p IS NOT NULL THEN 1 ELSE 0 END AS relevance
            RETURN e.name AS name, e.category AS category,
                   e.benefits AS benefits, e.intensity AS intensity,
                   e.exercise_id AS id, e.book_id AS book_id,
                   relevance
            ORDER BY relevance DESC, e.name
            LIMIT 20
        """
        params = {"age": age, "problems": problems[:5]}
    else:
        query = base_query + """
            RETURN e.name AS name, e.category AS category,
                   e.benefits AS benefits, e.intensity AS intensity,
                   e.exercise_id AS id, e.book_id AS book_id,
                   0 AS relevance
            ORDER BY e.name
            LIMIT 20
        """
        params = {"age": age}

    try:
        return session.run(query, **params).data()
    except Exception as e:
        logger.warning("Exercise 查询失败: %s", e)
        # 降级: 返回基础查询
        try:
            fallback = base_query + """
                RETURN e.name AS name, e.category AS category,
                       e.benefits AS benefits, e.intensity AS intensity,
                       e.exercise_id AS id, e.book_id AS book_id
                ORDER BY e.name LIMIT 20
            """
            return session.run(fallback, age=age).data()
        except Exception:
            return []


def _query_cross_book(session, book_ids: list[str]) -> list[dict]:
    """查询跨书关系。"""
    if len(book_ids) < 2:
        return []

    query = """
        MATCH (a)-[r:CROSS_BOOK_CONSENSUS|CROSS_BOOK_COMPLEMENTS|CROSS_BOOK_CONFLICTS]->(b)
        WHERE a.book_id IN $book_ids AND b.book_id IN $book_ids
        RETURN a.name AS source_entity, a.book_id AS source_book,
               type(r) AS relation_type, b.name AS target_entity,
               b.book_id AS target_book, r.explanation AS explanation
    """
    try:
        return session.run(query, book_ids=book_ids).data()
    except Exception as e:
        logger.warning("跨书关系查询失败: %s", e)
        return []


def _query_problem_context(session, problems: list[str]) -> list[dict]:
    """查询问题相关的根因和诊断链。"""
    if not problems:
        return []

    query = """
        MATCH (p:Problem)-[r]->(rc:RootCause)
        WHERE p.name IN $problems
        RETURN p.name AS problem, rc.name AS root_cause, type(r) AS relation
    """
    try:
        return session.run(query, problems=problems).data()
    except Exception as e:
        logger.warning("Problem context 查询失败: %s", e)
        return []


def _query_source_coverage(session, book_ids: list[str]) -> dict:
    """查询各书的知识覆盖度。"""
    query = """
        MATCH (b:Book)
        WHERE b.book_id IN $book_ids
        OPTIONAL MATCH (b)-[:CONTAINS_ENTITY]->(e)
        RETURN b.book_id AS book_id, b.title AS title, count(e) AS entity_count
    """
    try:
        rows = session.run(query, book_ids=book_ids).data()
        return {r["book_id"]: r for r in rows}
    except Exception as e:
        logger.warning("Source coverage 查询失败: %s", e)
        return {}
