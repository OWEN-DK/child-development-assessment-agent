"""Phase 1: 逐章 3 轮聚焦提取。

放置位置: backend/src/core/knowledge_qa/neo4j/chapter_extractor.py
"""

from __future__ import annotations

import asyncio
import logging
from typing import Protocol

from .chapter_parser import Chapter
from .long_chapter import segment_chapter, merge_entity_results, merge_relationship_results, merge_detail_results
from .models import (
    BookContext,
    ChapterDetails,
    ChapterExtraction,
    ExtractedEntity,
    ExtractedRelationship,
    ModelConfig,
)

logger = logging.getLogger(__name__)


class LLMClient(Protocol):
    async def generate_structured(
        self, prompt: str, schema: type, model: str,
    ) -> dict | list: ...


# ──────────────────────────────────────────────────────────────
# Prompts
# ──────────────────────────────────────────────────────────────

ENTITY_EXTRACTION_PROMPT = """你是一位知识提取专家。从以下章节中提取所有重要实体。

## 全书背景
{book_context}

## 章节原文（段落已编号 [P1], [P2], ...）
{chapter_content}

---

## 任务
逐段扫描原文，提取所有实体。规则:
1. 宁多勿漏，不确定时也提取
2. description 不少于 20 字，保留原文关键信息
3. 标注每条信息的来源段落号（如 [3, 5, 7]）
4. entity_type 必须是枚举值之一
"""


RELATIONSHIP_EXTRACTION_PROMPT = """你是一位知识关系分析专家。

## 章节原文（段落已编号）
{chapter_content}

## 本章已识别的实体
{entity_list}

## 已审核章节中出现的实体（可作为关系目标）
{existing_entities}

---

## 任务
找出实体之间的所有关系。规则:
1. 实体名称必须与上方实体列表一致
2. evidence 必须是原文直接引用
3. 已审核章节的实体可作为关系目标（跨章关系）
4. 标注来源段落号
"""


DETAIL_EXTRACTION_PROMPT = """你是一位知识整理专家。

## 章节原文（段落已编号）
{chapter_content}

## 已识别的实体
{entity_list}

---

## 任务
提取以下非实体信息:

1. **案例/故事**: 保留完整叙事（背景→过程→结果→启示）
2. **数据/事实**: 保留数值、上下文、来源
3. **引言/金句**: 保留原文措辞，标注说话人
4. **核心论点**: 本章作者想要说服读者相信什么
5. **实践建议**: 具体做什么、怎么做

每条信息标注来源段落号。
"""


# ──────────────────────────────────────────────────────────────
# 段落编号预处理
# ──────────────────────────────────────────────────────────────


def add_paragraph_ids(chapter_markdown: str) -> str:
    """在每个段落前插入 [P{n}] 标记。"""
    paragraphs = chapter_markdown.split("\n\n")
    return "\n\n".join(
        f"[P{i+1}] {para}"
        for i, para in enumerate(paragraphs)
        if para.strip()
    )


def _count_paragraphs(chapter_markdown: str) -> int:
    """计算章节的段落数。"""
    return len([p for p in chapter_markdown.split("\n\n") if p.strip()])


# ──────────────────────────────────────────────────────────────
# 格式化工具
# ──────────────────────────────────────────────────────────────


def _format_entity_list(entities: list[dict] | list[ExtractedEntity]) -> str:
    """将实体列表格式化为 LLM 可读的文本。"""
    lines = []
    for e in entities:
        if isinstance(e, ExtractedEntity):
            lines.append(f"- {e.name} ({e.entity_type.value}): {e.description[:80]}")
        else:
            lines.append(f"- {e['name']} ({e.get('entity_type', '?')}): {e.get('description', '')[:80]}")
    return "\n".join(lines) if lines else "（暂无）"


def _format_existing_entities(entities: list[dict]) -> str:
    """格式化已审核章节的实体列表。"""
    if not entities:
        return "（这是第一个审核的章节，无已有实体）"
    return "\n".join(
        f"- {e['name']} ({e.get('entity_type', '?')}) — 来自 {e.get('source_chapter', '?')}"
        for e in entities
    )


# ──────────────────────────────────────────────────────────────
# 公开 API
# ──────────────────────────────────────────────────────────────


async def extract_chapter(
    chapter: Chapter,
    book_context: BookContext,
    existing_entities: list[dict],
    llm_client: LLMClient,
    config: ModelConfig,
    long_chapter_threshold: int = 20_000,
) -> ChapterExtraction:
    """单章深度提取: 自动判断短/长章节，走不同流程。

    Args:
        chapter: 章节数据
        book_context: Phase 0 输出的全书上下文
        existing_entities: 已审核章节的实体列表
        llm_client: LLM 客户端
        config: 模型配置
        long_chapter_threshold: 长章节阈值 (tokens)

    Returns:
        ChapterExtraction 提取结果
    """
    segments = segment_chapter(chapter, long_chapter_threshold)

    if len(segments) == 1:
        return await _extract_short(
            chapter, segments[0], book_context, existing_entities,
            llm_client, config,
        )
    else:
        return await _extract_long(
            chapter, segments, book_context, existing_entities,
            llm_client, config,
        )


# ──────────────────────────────────────────────────────────────
# 短章节提取（< 20K tokens）
# ──────────────────────────────────────────────────────────────


async def _extract_short(
    chapter: Chapter,
    segment,  # Segment from long_chapter.py
    book_context: BookContext,
    existing_entities: list[dict],
    llm_client: LLMClient,
    config: ModelConfig,
) -> ChapterExtraction:
    """短章节: 标准 3 轮提取。"""

    chapter_text = segment.text_with_ids
    ctx_str = f"{book_context.core_thesis}\n术语: {', '.join(book_context.terminology.keys())}"

    # Round 1: 实体提取
    entities = await llm_client.generate_structured(
        prompt=ENTITY_EXTRACTION_PROMPT.format(
            book_context=ctx_str,
            chapter_content=chapter_text,
        ),
        schema=list[ExtractedEntity],
        model=config.extraction,
    )

    # Round 2: 关系提取
    relationships = await llm_client.generate_structured(
        prompt=RELATIONSHIP_EXTRACTION_PROMPT.format(
            chapter_content=chapter_text,
            entity_list=_format_entity_list(entities),
            existing_entities=_format_existing_entities(existing_entities),
        ),
        schema=list[ExtractedRelationship],
        model=config.extraction,
    )

    # Round 3: 细节提取
    details = await llm_client.generate_structured(
        prompt=DETAIL_EXTRACTION_PROMPT.format(
            chapter_content=chapter_text,
            entity_list=_format_entity_list(entities),
        ),
        schema=ChapterDetails,
        model=config.extraction,
    )

    return ChapterExtraction(
        chapter_id=chapter.id,
        chapter_title=chapter.title,
        entities=entities if isinstance(entities, list) else [],
        relationships=relationships if isinstance(relationships, list) else [],
        cases=details.cases if isinstance(details, ChapterDetails) else [],
        data_points=details.data_points if isinstance(details, ChapterDetails) else [],
        quotes=details.quotes if isinstance(details, ChapterDetails) else [],
        key_arguments=details.key_arguments if isinstance(details, ChapterDetails) else [],
        recommendations=details.recommendations if isinstance(details, ChapterDetails) else [],
    )


# ──────────────────────────────────────────────────────────────
# 长章节提取（≥ 20K tokens）
# ──────────────────────────────────────────────────────────────


async def _extract_long(
    chapter: Chapter,
    segments: list,  # list[Segment]
    book_context: BookContext,
    existing_entities: list[dict],
    llm_client: LLMClient,
    config: ModelConfig,
) -> ChapterExtraction:
    """长章节: 分段并行 + 跨段桥接。"""

    ctx_str = f"{book_context.core_thesis}\n术语: {', '.join(book_context.terminology.keys())}"
    entity_list_str = _format_existing_entities(existing_entities)

    # Round 1: 各段并行实体提取
    r1_tasks = [
        llm_client.generate_structured(
            prompt=ENTITY_EXTRACTION_PROMPT.format(
                book_context=ctx_str,
                chapter_content=seg.text_with_ids,
            ),
            schema=list[ExtractedEntity],
            model=config.extraction,
        )
        for seg in segments
    ]
    seg_entity_results = await asyncio.gather(*r1_tasks)
    merged_entities = merge_entity_results(seg_entity_results)

    # Round 2a: 各段并行关系提取
    r2a_tasks = [
        llm_client.generate_structured(
            prompt=RELATIONSHIP_EXTRACTION_PROMPT.format(
                chapter_content=seg.text_with_ids,
                entity_list=_format_entity_list(merged_entities.entities),
                existing_entities=entity_list_str,
            ),
            schema=list[ExtractedRelationship],
            model=config.extraction,
        )
        for seg in segments
    ]
    seg_rel_results = await asyncio.gather(*r2a_tasks)

    # Round 2b: 跨段桥接
    bridge_rels = await _bridge_cross_segment_relations(
        segments, merged_entities, seg_rel_results, llm_client, config,
    )
    all_relationships = merge_relationship_results(seg_rel_results, bridge_rels)

    # Round 3: 各段并行细节提取
    r3_tasks = [
        llm_client.generate_structured(
            prompt=DETAIL_EXTRACTION_PROMPT.format(
                chapter_content=seg.text_with_ids,
                entity_list=_format_entity_list(merged_entities.entities),
            ),
            schema=ChapterDetails,
            model=config.extraction,
        )
        for seg in segments
    ]
    seg_detail_results = await asyncio.gather(*r3_tasks)
    merged_details = merge_detail_results(seg_detail_results)

    return ChapterExtraction(
        chapter_id=chapter.id,
        chapter_title=chapter.title,
        entities=merged_entities.entities,
        relationships=all_relationships,
        cases=merged_details.get("cases", []),
        data_points=merged_details.get("data_points", []),
        quotes=merged_details.get("quotes", []),
        key_arguments=merged_details.get("key_arguments", []),
        recommendations=merged_details.get("recommendations", []),
    )


BRIDGE_RELATION_PROMPT = """你是知识关系分析专家。以下是一个长章节被分段提取后的结果。

## 各段摘要
{segment_summaries}

## 合并后的完整实体列表
{entity_list}

## 各段已发现的段内关系
{intra_segment_relations}

## 任务
找出**跨段存在但段内提取未捕获的关系**。重点关注:
1. 在不同段落出现的同一实体，前后文是否有未被提取的关系
2. 段 A 提到的实体与段 B 提到的实体之间的因果/影响关系
3. 作者在某段提出的论点，在另一段给出的论据支撑

只输出确实跨段的关系，不要重复段内已有的关系。
"""


async def _bridge_cross_segment_relations(
    segments: list,
    merged_entities,
    seg_rel_results: list,
    llm_client: LLMClient,
    config: ModelConfig,
) -> list[dict]:
    """跨段桥接: 从各段摘要中推断跨段关系。"""

    # 构造各段摘要
    summaries = []
    for seg in segments:
        first_200 = seg.text_with_ids[:200].replace("\n", " ")
        summaries.append(
            f"段 {seg.index + 1} [P{seg.paragraph_ids[0]}-P{seg.paragraph_ids[-1]}]: "
            f"{first_200}..."
        )
    segment_summaries = "\n".join(summaries)

    # 构造已发现的段内关系摘要
    intra_rels = []
    for seg_rels in seg_rel_results:
        for rel in seg_rels:
            if isinstance(rel, ExtractedRelationship):
                intra_rels.append(
                    f"{rel.source} → {rel.relation_type.value} → {rel.target}"
                )
            elif isinstance(rel, dict):
                intra_rels.append(
                    f"{rel.get('source', '?')} → {rel.get('relation_type', '?')} → {rel.get('target', '?')}"
                )
    intra_rels_str = "\n".join(intra_rels[:50])

    result = await llm_client.generate_structured(
        prompt=BRIDGE_RELATION_PROMPT.format(
            segment_summaries=segment_summaries,
            entity_list=_format_entity_list(merged_entities.entities),
            intra_segment_relations=intra_rels_str,
        ),
        schema=list[ExtractedRelationship],
        model=config.extraction,
    )
    return result if isinstance(result, list) else []
