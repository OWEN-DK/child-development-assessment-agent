"""跨章聚合 — 合并同名实体、检测章间矛盾。

放置位置: backend/src/core/knowledge_qa/neo4j/aggregator.py
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class AggregatedEntity:
    """聚合后的实体。"""
    name: str
    entity_type: str
    descriptions: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    confidence: float = 0.0
    merged_from: list[str] = field(default_factory=list)


@dataclass
class AggregatedBook:
    """整本书的聚合结果。"""
    book_id: str
    book_title: str
    entities: list[AggregatedEntity] = field(default_factory=list)
    claims: list[dict] = field(default_factory=list)
    prescriptions: list[dict] = field(default_factory=list)
    contradictions: list[dict] = field(default_factory=list)
    key_arguments: list[dict] = field(default_factory=list)
    case_studies: list[dict] = field(default_factory=list)
    data_points: list[dict] = field(default_factory=list)
    chapter_summaries: list[dict] = field(default_factory=list)


def aggregate_chapters(chapter_results: list[dict], book_id: str, book_title: str) -> AggregatedBook:
    """将多个章节的提取结果聚合为一本书的结构化知识。

    Args:
        chapter_results: 每章的提取结果 [{chapter_id, success, concepts, claims, prescriptions}]
        book_id: 书籍 ID
        book_title: 书名

    Returns:
        AggregatedBook 聚合结果
    """
    book = AggregatedBook(book_id=book_id, book_title=book_title)
    entity_map: dict[str, AggregatedEntity] = {}

    for result in chapter_results:
        if not result.get("success"):
            continue

        chapter_id = result.get("chapter_id", "")

        for concept in result.get("concepts", []):
            key = f"{concept.get('entity_type', '')}::{concept.get('name', '')}"
            if key in entity_map:
                entity_map[key].descriptions.append(concept.get("description", ""))
                entity_map[key].sources.append(concept.get("source", chapter_id))
                entity_map[key].merged_from.append(chapter_id)
            else:
                entity_map[key] = AggregatedEntity(
                    name=concept["name"],
                    entity_type=concept.get("entity_type", "AutoEntity"),
                    descriptions=[concept.get("description", "")],
                    sources=[concept.get("source", chapter_id)],
                    confidence=concept.get("confidence", 0.8),
                    merged_from=[chapter_id],
                )

        for claim in result.get("claims", []):
            book.claims.append({**claim, "chapter_id": chapter_id})

        for rx in result.get("prescriptions", []):
            book.prescriptions.append({**rx, "chapter_id": chapter_id})

        for arg in result.get("key_arguments", []):
            book.key_arguments.append({**arg, "chapter_id": chapter_id})

        for case in result.get("case_studies", []):
            book.case_studies.append({**case, "chapter_id": chapter_id})

        for dp in result.get("data_points", []):
            book.data_points.append({**dp, "chapter_id": chapter_id})

        summary = result.get("chapter_summary")
        if summary:
            book.chapter_summaries.append({**summary, "chapter_id": chapter_id})

    book.entities = list(entity_map.values())
    book.contradictions = _detect_contradictions(book.entities)

    logger.info(
        "聚合完成: %d 实体, %d 主张, %d 处方, %d 矛盾, %d 论点, %d 案例, %d 数据",
        len(book.entities), len(book.claims), len(book.prescriptions),
        len(book.contradictions), len(book.key_arguments),
        len(book.case_studies), len(book.data_points),
    )
    return book


def _detect_contradictions(entities: list[AggregatedEntity]) -> list[dict]:
    """检测同一实体在不同章节中的描述矛盾。"""
    contradictions = []

    for ent in entities:
        if len(ent.descriptions) < 2:
            continue

        # 简单关键词矛盾检测
        high_severity = {"高", "严重", "重度", "high", "severe"}
        low_severity = {"低", "轻微", "轻度", "low", "mild"}

        has_high = any(kw in d for d in ent.descriptions for kw in high_severity)
        has_low = any(kw in d for d in ent.descriptions for kw in low_severity)

        if has_high and has_low:
            contradictions.append({
                "entity_name": ent.name,
                "type": "severity_conflict",
                "descriptions": ent.descriptions,
                "sources": ent.sources,
            })

    return contradictions
