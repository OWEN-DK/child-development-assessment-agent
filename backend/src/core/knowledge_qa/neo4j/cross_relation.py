"""⚠️ DEPRECATED (2026-06): 已被 cross_book_phase5a.py 替代。
新路径使用 schema.py CROSS_BOOK_RELATION_TYPES（23 种）+ CROSS_RELATION_TYPE_COMBOS（类型感知）。
旧路径仅 3 种类型（CONSENSUS/COMPLEMENTS/CONFLICTS），保留仅供向后兼容和测试。

跨书关系检测 — Neo4j 查询已有实体 → 相似度粗筛 → LLM 精判。

放置位置: backend/src/core/knowledge_qa/neo4j/cross_relation.py
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Protocol

logger = logging.getLogger(__name__)


class CrossBookRelationType(Enum):
    CONSENSUS = "CONSENSUS"        # 共识
    COMPLEMENTS = "COMPLEMENTS"    # 互补
    CONFLICTS = "CONFLICTS"        # 冲突


@dataclass
class CrossBookRelation:
    source_entity: str
    source_book: str
    target_entity: str
    target_book: str
    relation_type: CrossBookRelationType
    confidence: float
    explanation: str


class LLMClient(Protocol):
    async def generate(self, prompt: str, model: str) -> str: ...


async def detect_cross_book_relations(
    new_entities: list[dict],
    new_book_id: str,
    neo4j_session,
    llm_client: LLMClient,
    similarity_threshold: float = 0.7,
) -> list[CrossBookRelation]:
    """检测新书实体与 Neo4j 中已有实体的跨书关系。

    Args:
        new_entities: 新书的实体列表 [{name, entity_type, description}]
        new_book_id: 新书 ID
        neo4j_session: Neo4j session
        llm_client: LLM 客户端
        similarity_threshold: 相似度阈值

    Returns:
        确认的跨书关系列表
    """
    relations = []

    existing = neo4j_session.run("""
        MATCH (ae:AutoEntity)
        WHERE ae.book_id <> $book_id
        RETURN ae.name AS name, ae.entity_type AS type,
               ae.description AS desc, ae.book_id AS book_id
        UNION ALL
        MATCH (n:Problem)
        WHERE n.book_id <> $book_id
        RETURN n.name AS name, n.entity_type AS type,
               n.description AS desc, n.book_id AS book_id
        UNION ALL
        MATCH (n:Solution)
        WHERE n.book_id <> $book_id
        RETURN n.name AS name, n.entity_type AS type,
               n.description AS desc, n.book_id AS book_id
        UNION ALL
        MATCH (n:BrainRegion)
        WHERE n.book_id <> $book_id
        RETURN n.name AS name, n.entity_type AS type,
               n.description AS desc, n.book_id AS book_id
        UNION ALL
        MATCH (n:Risk)
        WHERE n.book_id <> $book_id
        RETURN n.name AS name, n.entity_type AS type,
               n.description AS desc, n.book_id AS book_id
        UNION ALL
        MATCH (n:Exercise)
        WHERE n.book_id <> $book_id
        RETURN n.name AS name, n.entity_type AS type,
               n.description AS desc, n.book_id AS book_id
        UNION ALL
        MATCH (n:RootCause)
        WHERE n.book_id <> $book_id
        RETURN n.name AS name, n.entity_type AS type,
               n.description AS desc, n.book_id AS book_id
        UNION ALL
        MATCH (n:Prescription)
        WHERE n.book_id <> $book_id
        RETURN n.name AS name, n.entity_type AS type,
               n.description AS desc, n.book_id AS book_id
        UNION ALL
        MATCH (n:ChildProfile)
        WHERE n.book_id <> $book_id
        RETURN n.name AS name, n.entity_type AS type,
               n.description AS desc, n.book_id AS book_id
        UNION ALL
        MATCH (n:CognitiveProcess)
        WHERE n.book_id <> $book_id
        RETURN n.name AS name, n.entity_type AS type,
               n.description AS desc, n.book_id AS book_id
        UNION ALL
        MATCH (n:Theory)
        WHERE n.book_id <> $book_id
        RETURN n.name AS name, n.entity_type AS type,
               n.description AS desc, n.book_id AS book_id
        UNION ALL
        MATCH (n:Mechanism)
        WHERE n.book_id <> $book_id
        RETURN n.name AS name, n.entity_type AS type,
               n.description AS desc, n.book_id AS book_id
        UNION ALL
        MATCH (n:DevelopmentalStage)
        WHERE n.book_id <> $book_id
        RETURN n.name AS name, n.entity_type AS type,
               n.description AS desc, n.book_id AS book_id
        UNION ALL
        MATCH (n:Strategy)
        WHERE n.book_id <> $book_id
        RETURN n.name AS name, n.entity_type AS type,
               n.description AS desc, n.book_id AS book_id
        UNION ALL
        MATCH (n:KeyInsight)
        WHERE n.book_id <> $book_id
        RETURN n.name AS name, n.entity_type AS type,
               n.description AS desc, n.book_id AS book_id
        UNION ALL
        MATCH (n:ResearchFinding)
        WHERE n.book_id <> $book_id
        RETURN n.name AS name, n.entity_type AS type,
               n.description AS desc, n.book_id AS book_id
    """, book_id=new_book_id).data()

    if not existing:
        logger.info("Neo4j 中无其他书的实体，跳过跨书检测")
        return []

    # 粗筛: 同类型 + 名称相似
    candidates = []
    for new_ent in new_entities:
        for old_ent in existing:
            if new_ent.get("entity_type") != old_ent["type"]:
                continue
            sim = _name_similarity(new_ent.get("name", ""), old_ent["name"])
            if sim >= similarity_threshold:
                candidates.append((new_ent, old_ent, sim))

    logger.info("跨书粗筛: %d 个候选", len(candidates))

    # LLM 精判
    for new_ent, old_ent, sim in candidates:
        relation = await _llm_judge(new_ent, old_ent, llm_client)
        if relation:
            relations.append(relation)

    logger.info("跨书检测完成: %d / %d 个确认", len(relations), len(candidates))
    return relations


def _name_similarity(a: str, b: str) -> float:
    """名称相似度（简化版，生产环境应用 embedding）。"""
    if a == b:
        return 1.0
    if a in b or b in a:
        return 0.9
    # 去除括号后比较
    a_clean = a.split("(")[0].strip()
    b_clean = b.split("(")[0].strip()
    if a_clean == b_clean:
        return 0.85
    return 0.0


async def _llm_judge(
    new_ent: dict, old_ent: dict, llm_client: LLMClient
) -> Optional[CrossBookRelation]:
    """LLM 判断两个实体的关系类型。"""
    prompt = f"""判断以下两个来自不同书籍的实体之间的关系。

实体 A（新书）: {new_ent.get('name')} - {new_ent.get('description', '')}
实体 B（已有）: {old_ent['name']} - {old_ent.get('desc', '')}

选项:
- CONSENSUS: 两书观点一致
- COMPLEMENTS: 两书观点互补
- CONFLICTS: 两书观点矛盾
- UNRELATED: 无关

仅输出 JSON: {{"type": "...", "confidence": 0.0-1.0, "explanation": "简要说明"}}"""

    try:
        response = await llm_client.generate(prompt=prompt, model="qwen3.7-max")
        # 提取 JSON — LLM 可能在 JSON 前后附加文本
        import re as _re
        json_match = _re.search(r'\{[^{}]*\}', response)
        if not json_match:
            logger.warning("LLM 返回中未找到 JSON: %s", response[:200])
            return None
        result = json.loads(json_match.group())

        if result.get("type") == "UNRELATED":
            return None

        return CrossBookRelation(
            source_entity=new_ent.get("name", ""),
            source_book=new_ent.get("book_id", ""),
            target_entity=old_ent["name"],
            target_book=old_ent["book_id"],
            relation_type=CrossBookRelationType(result["type"]),
            confidence=result.get("confidence", 0.5),
            explanation=result.get("explanation", ""),
        )
    except Exception as e:
        logger.warning("LLM 跨书判断失败: %s", e)
        return None


# ── Phase 5 跨书关系检测（§08-5.3） ─────────────────────────


async def detect_cross_book_relations_for_same_as(
    neo4j_session,
    llm_client: LLMClient,
) -> list[CrossBookRelation]:
    """检测已有 SAME_AS 边的实体对之间的跨书关系类型。

    Phase 5 已完成相似实体发现和 SAME_AS 建边，
    本函数只需对这些 SAME_AS 实体对检测 CONSENSUS/COMPLEMENTS/CONFLICTS。
    """
    pairs = neo4j_session.run("""
        MATCH (a)-[r:SAME_AS]->(b)
        WHERE a.book_id <> b.book_id
          AND NOT coalesce(r.revoked, false)
        RETURN a.name AS name_a, a.description AS desc_a, a.book_id AS book_a,
               b.name AS name_b, b.description AS desc_b, b.book_id AS book_b,
               r.confidence AS similarity
    """).data()

    if not pairs:
        logger.info("无 SAME_AS 实体对，跳过跨书关系检测")
        return []

    logger.info("跨书关系检测: %d 个 SAME_AS 候选对", len(pairs))

    relations = []
    for pair in pairs:
        new_ent = {
            "name": pair["name_a"],
            "description": pair.get("desc_a", ""),
            "book_id": pair.get("book_a", ""),
        }
        old_ent = {
            "name": pair["name_b"],
            "desc": pair.get("desc_b", ""),
            "book_id": pair.get("book_b", ""),
        }
        relation = await _llm_judge(new_ent, old_ent, llm_client)
        if relation:
            relations.append(relation)

    logger.info("跨书关系检测完成: %d / %d 个确认", len(relations), len(pairs))
    return relations
