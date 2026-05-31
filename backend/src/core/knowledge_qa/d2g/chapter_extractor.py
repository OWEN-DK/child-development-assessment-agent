"""Phase 1: 逐章联合提取（实体+关系单 Pass）+ 覆盖度自检。

放置位置: backend/src/core/knowledge_qa/d2g/chapter_extractor.py

v2 变更:
- Round 1+2 合并为单 Pass 联合提取（实体+关系一体输出）
- 新增覆盖度自检：提取后检查孤立实体，不达标则触发定向补全
- 保留 Round 3 细节提取不变
"""

from __future__ import annotations

import asyncio
import logging
from typing import List, Protocol, Type, TypeVar

from src.core.knowledge_qa.neo4j.chapter_parser import Chapter
from .long_chapter import segment_chapter, merge_entity_results, merge_relationship_results, merge_detail_results
from .models import (
    EntityListResponse, RelationshipListResponse, JointExtractionResponse,
    BookContext,
    ChapterDetails,
    ChapterExtraction,
    ExtractedEntity,
    ExtractedRelationship,
    ModelConfig,
    RelationType,
)

logger = logging.getLogger(__name__)

# 覆盖度阈值：孤立实体率超过此值触发补全
COVERAGE_ORPHAN_THRESHOLD = 0.20


_T = TypeVar("_T")

def _normalize_relation_dict(d: dict) -> dict:
    """规范化关系字典：将 LLM 输出的 'type' 映射为 Pydantic 期望的 'relation_type'。"""
    if "type" in d and "relation_type" not in d:
        d = dict(d)
        d["relation_type"] = d.pop("type")
    return d


def _normalize_entity_dict(d: dict) -> dict:
    """规范化实体字典：将 LLM 输出的 'type' 映射为 Pydantic 期望的 'entity_type'。"""
    if "type" in d and "entity_type" not in d:
        d = dict(d)
        d["entity_type"] = d.pop("type")
    return d


def _as_model(result: object, schema: Type[_T]) -> _T:
    """将 generate_structured 的 dict/list 返回值规范化为 Pydantic model。"""
    if isinstance(result, schema):
        return result
    if isinstance(result, dict):
        # 尝试直接解析
        try:
            return schema(**result)
        except Exception as e:
            logger.debug("_as_model 直接解析 %s 失败: %s", schema.__name__, e)
        # 规范化 LLM 输出的字段名
        try:
            normalized = dict(result)
            if "entities" in normalized:
                normalized["entities"] = [_normalize_entity_dict(e) for e in normalized["entities"]]
            if "relations" in normalized:
                normalized["relations"] = [_normalize_relation_dict(r) for r in normalized["relations"]]
            # RelationshipListResponse / EntityListResponse 用 items
            if "items" in normalized and normalized["items"]:
                sample = normalized["items"][0] if normalized["items"] else {}
                if "name" in sample and "entity_type" not in sample:
                    normalized["items"] = [_normalize_entity_dict(e) for e in normalized["items"]]
                elif "source" in sample and "relation_type" not in sample:
                    normalized["items"] = [_normalize_relation_dict(r) for r in normalized["items"]]
            return schema(**normalized)
        except Exception as e:
            logger.warning("_as_model 规范化解析 %s 失败: %s, 输入 keys=%s", schema.__name__, e, list(result.keys()) if isinstance(result, dict) else type(result))
    if isinstance(result, list):
        try:
            return schema(items=result)
        except Exception as e:
            logger.warning("_as_model 列表解析 %s 失败: %s", schema.__name__, e)
    if isinstance(result, str):
        logger.warning("_as_model 收到字符串而非 dict (schema=%s), 前 200 字符: %s", schema.__name__, result[:200])
    # 尝试展开嵌套结构（如 {'entities': {'items': [...]}} 或 {'result': {...}}）
    if isinstance(result, dict) and schema.__name__ == "JointExtractionResponse":
        # 展开 {'result': {...}} 包装
        if "entities" not in result and "relations" not in result:
            for key in ["result", "data", "output", "response"]:
                if key in result and isinstance(result[key], dict):
                    result = result[key]
                    logger.info("_as_model 展开嵌套包装 '%s'", key)
                    break
        # 展开 {'entities': {'items': [...]}} 结构
        if "entities" in result and isinstance(result.get("entities"), dict):
            result["entities"] = result["entities"].get("items", result["entities"].get("entities", []))
        if "relations" in result and isinstance(result.get("relations"), dict):
            result["relations"] = result["relations"].get("items", result["relations"].get("relations", []))

    # 最后手段：对 JointExtractionResponse 做手动构造
    if schema.__name__ == "JointExtractionResponse" and isinstance(result, dict):
        try:
            entities = []
            for e in result.get("entities", []):
                if isinstance(e, dict) and e.get("name"):
                    etype = e.get("entity_type") or e.get("type", "AutoEntity")
                    entities.append(ExtractedEntity(
                        name=e["name"], entity_type=etype,
                        description=e.get("description", ""),
                        source_para_ids=e.get("source_para_ids", []),
                    ))
            relations = []
            for r in result.get("relations", []):
                if isinstance(r, dict) and r.get("source") and r.get("target"):
                    rtype_str = r.get("relation_type") or r.get("type", "RELATES_TO")
                    # 回退未知枚举值
                    if rtype_str not in RelationType.__members__:
                        rtype_str = "RELATES_TO"
                    rtype = rtype_str
                    relations.append(ExtractedRelationship(
                        source=r["source"], target=r["target"],
                        relation_type=rtype,
                        evidence=r.get("evidence", ""),
                        source_para_ids=r.get("source_para_ids", []),
                    ))
            if entities or relations:
                logger.info("_as_model 手动构造成功: %d entities, %d relations", len(entities), len(relations))
                return JointExtractionResponse(entities=entities, relations=relations)
        except Exception as e:
            logger.warning("_as_model 手动构造失败: %s", e)
    return schema()


class LLMClient(Protocol):
    async def generate_structured(
        self, prompt: str, schema: type, model: str,
    ) -> dict | list: ...


# ──────────────────────────────────────────────────────────────
# Prompts — 联合提取
# ──────────────────────────────────────────────────────────────

JOINT_EXTRACTION_PROMPT = """你是一位儿童发展领域知识提取专家。从以下章节中**同时提取实体和关系**。

## 全书背景
{book_context}

## 章节原文（段落已编号 [P1], [P2], ...）
{chapter_content}

## 已有实体（来自前面的章节，可作为关系目标）
{existing_entities}

---

## 任务
1. 提取所有重要实体（宁多勿漏，不确定时也提取）
2. 为每个实体找到至少 1 个关系（作为 source 或 target）
3. 关系必须有原文证据（带段落号）
4. entity_type 使用英文 PascalCase（如 BrainRegion、CognitiveProcess、Exercise 等）

### 关系类型（从以下大类中选择）
- CAUSAL_CAUSES / CAUSAL_LEADS_TO / CAUSAL_CONTRIBUTES_TO: 因果关系
- THERAPEUTIC_TREATS / THERAPEUTIC_IMPROVES / THERAPEUTIC_ALLEVIATES: 治疗/干预
- STRUCTURAL_PART_OF / STRUCTURAL_CONTAINS / STRUCTURAL_BELONGS_TO: 结构/组成
- FUNCTIONAL_REGULATES / FUNCTIONAL_INVOLVED_IN / FUNCTIONAL_MEDIATES: 功能/参与
- EVIDENCE_SUPPORTS / EVIDENCE_BASED_ON / EVIDENCE_DEMONSTRATES: 证据/研究
- TEMPORAL_PRECEDES / TEMPORAL_DEVELOPS_INTO: 时间/发展
- COMPARISON_SIMILAR_TO / COMPARISON_DIFFERENT_FROM: 比较
- ATTRIBUTE_ASSOCIATED_WITH / ATTRIBUTE_MEASURED_BY: 属性/关联
- RELATES_TO: 兜底（尽量少用）

### 覆盖度约束（硬性）
- 关系数 >= 实体数 × 0.8（即孤立率 < 20%）
- 每个实体必须出现在至少 1 条关系中（作为 source 或 target）
- 提取完成后自查：列出未被任何关系覆盖的实体，为它们补充关系

### 已有实体作为关系目标
如果原文中有与"已有实体"相关的描述，请提取跨章节关系。
关系的 source 或 target 可以是已有实体的名称。

## 输出格式
严格按以下 JSON 格式输出：
```json
{{
  "entities": [
    {{"name": "实体名", "type": "BrainRegion", "description": "简要描述", "source_para_ids": [1, 3]}}
  ],
  "relations": [
    {{"source": "实体A", "target": "实体B", "relation_type": "CAUSAL_CAUSES", "evidence": "原文引用", "source_para_ids": [2]}}
  ]
}}
```
"""


COVERAGE_FIX_PROMPT = """你是知识关系补全专家。以下实体在上一轮提取中未找到任何关系连接。

## 章节原文（段落已编号）
{chapter_content}

## 孤立实体列表
{orphan_entities}

## 已有实体（可作为关系目标）
{all_entities}

---

## 任务
从原文中为每个孤立实体找到至少 1 个关系。重点关注：
1. 原文中该实体与其他实体共现的段落
2. 该实体在上下文中的因果、功能、或关联关系

### 关系类型
- CAUSAL_CAUSES / CAUSAL_LEADS_TO / CAUSAL_CONTRIBUTES_TO
- THERAPEUTIC_TREATS / THERAPEUTIC_IMPROVES / THERAPEUTIC_ALLEVIATES
- STRUCTURAL_PART_OF / STRUCTURAL_CONTAINS
- FUNCTIONAL_REGULATES / FUNCTIONAL_INVOLVED_IN / FUNCTIONAL_MEDIATES
- EVIDENCE_SUPPORTS / EVIDENCE_BASED_ON
- ATTRIBUTE_ASSOCIATED_WITH / RELATES_TO

## 输出要求
- 只输出 relations 数组，每个关系包含 source、target、relation_type、evidence
- relation_type 从上方列表中选择
- 为每个孤立实体至少找到 1 条关系
"""


# ──────────────────────────────────────────────────────────────
# Prompts — 细节提取（不变）
# ──────────────────────────────────────────────────────────────

DETAIL_EXTRACTION_PROMPT = """你是知识细节提取专家。从以下章节中提取案例、数据和引言。

## 章节原文（段落已编号）
{chapter_content}

## 本章实体
{entity_list}

## 任务
1. 提取案例/故事（case）: 标题、背景、过程、结果、启示
2. 提取数据/事实（data_point）: 指标、数值、上下文、来源
3. 提取引言/金句（quote）: 原文引用、说话人、上下文
4. 提取核心论点（key_arguments）
5. 提取实践建议（recommendations）
"""


# ──────────────────────────────────────────────────────────────
# 格式化工具
# ──────────────────────────────────────────────────────────────


def _format_entity_list(entities) -> str:
    """格式化实体列表为 prompt 文本。"""
    if not entities:
        return "（无实体）"
    lines = []
    for e in entities:
        if hasattr(e, "name"):
            lines.append(f"- {e.name} ({e.entity_type}) — {e.description}")
        elif isinstance(e, dict):
            lines.append(f"- {e.get('name', '?')} ({e.get('entity_type', '?')}) — {e.get('description', '')}")
    return "\n".join(lines)


def _format_existing_entities(entities: list[dict]) -> str:
    """格式化已审核章节的实体列表。"""
    if not entities:
        return "（这是第一个审核的章节，无已有实体）"
    return "\n".join(
        f"- {e['name']} ({e.get('entity_type', '?')}) — 来自 {e.get('source_chapter', '?')}"
        for e in entities
    )


def _format_orphan_entities(orphan_names: list[str], all_entities) -> str:
    """格式化孤立实体列表，附带类型和描述。"""
    lines = []
    entity_map = {}
    for e in all_entities:
        name = e.name if hasattr(e, "name") else e.get("name", "")
        entity_map[name] = e
    for name in orphan_names:
        e = entity_map.get(name)
        if e:
            etype = e.entity_type if hasattr(e, "entity_type") else e.get("entity_type", "?")
            desc = e.description if hasattr(e, "description") else e.get("description", "")
            lines.append(f"- {name} ({etype}) — {desc}")
        else:
            lines.append(f"- {name}")
    return "\n".join(lines)


def _find_orphan_entities(
    entities: list,
    relations: list,
) -> list[str]:
    """找出未被任何关系覆盖的实体名称列表。"""
    connected = set()
    for r in relations:
        src = r.source if hasattr(r, "source") else r.get("source", "")
        tgt = r.target if hasattr(r, "target") else r.get("target", "")
        if src:
            connected.add(src)
        if tgt:
            connected.add(tgt)
    orphans = []
    for e in entities:
        name = e.name if hasattr(e, "name") else e.get("name", "")
        if name and name not in connected:
            orphans.append(name)
    return orphans


def _mark_relation_source(relations: list, source: str) -> None:
    """标记关系的来源。"""
    for r in relations:
        if hasattr(r, "relation_source"):
            r.relation_source = source
        elif isinstance(r, dict):
            r["relation_source"] = source


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
    """单章联合提取: 自动判断短/长章节，走不同流程。

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
        return await _extract_short_joint(
            chapter, segments[0], book_context, existing_entities,
            llm_client, config,
        )
    else:
        return await _extract_long_joint(
            chapter, segments, book_context, existing_entities,
            llm_client, config,
        )


# ──────────────────────────────────────────────────────────────
# 短章节：单 Pass 联合提取
# ──────────────────────────────────────────────────────────────


async def _extract_short_joint(
    chapter: Chapter,
    segment,
    book_context: BookContext,
    existing_entities: list[dict],
    llm_client: LLMClient,
    config: ModelConfig,
) -> ChapterExtraction:
    """短章节: 单 Pass 联合提取（实体+关系一体）+ 覆盖度自检。"""

    chapter_text = segment.text_with_ids
    ctx_str = f"{book_context.core_thesis}\n术语: {', '.join(book_context.terminology.keys())}"

    # Round 1: 单 Pass 联合提取（实体 + 关系）
    logger.info("  [%s] Round 1/2: 联合提取实体+关系…", chapter.id)
    raw_result = await llm_client.generate_structured(
        prompt=JOINT_EXTRACTION_PROMPT.format(
            book_context=ctx_str,
            chapter_content=chapter_text,
            existing_entities=_format_existing_entities(existing_entities),
        ),
        schema=JointExtractionResponse,
        model=config.extraction,
    )
    if isinstance(raw_result, str):
        logger.warning("  [%s] LLM 返回字符串而非 dict，前 500 字符: %s", chapter.id, raw_result[:500])
    elif isinstance(raw_result, dict):
        ent_count = len(raw_result.get("entities", []))
        rel_count = len(raw_result.get("relations", []))
        logger.info("  [%s] LLM 返回 dict: %d entities, %d relations", chapter.id, ent_count, rel_count)
        if ent_count == 0 and rel_count == 0:
            logger.warning("  [%s] LLM 返回空 entities+relations, 原始 keys: %s", chapter.id, list(raw_result.keys()))
    joint_result = _as_model(raw_result, JointExtractionResponse)

    entities = joint_result.entities or []
    relations = joint_result.relations or []
    _mark_relation_source(relations, "llm_joint")

    logger.info(
        "  [%s] 联合提取完成: %d 实体, %d 关系",
        chapter.id, len(entities), len(relations),
    )

    # 覆盖度自检 + 定向补全
    orphans = _find_orphan_entities(entities, relations)
    orphan_rate = len(orphans) / len(entities) if entities else 0

    if orphan_rate > COVERAGE_ORPHAN_THRESHOLD and orphans:
        logger.info(
            "  [%s] 孤立率 %.1f%% > %.0f%%，触发定向补全 (%d 个孤立实体)",
            chapter.id, orphan_rate * 100, COVERAGE_ORPHAN_THRESHOLD * 100, len(orphans),
        )
        fix_rels = await _fix_orphan_entities(
            orphans=orphans,
            all_entities=entities,
            chapter_text=chapter_text,
            llm_client=llm_client,
            config=config,
        )
        relations.extend(fix_rels)
        # 重新计算孤立率
        orphans_after = _find_orphan_entities(entities, relations)
        logger.info(
            "  [%s] 补全后: %d 关系, 孤立实体 %d → %d",
            chapter.id, len(relations), len(orphans), len(orphans_after),
        )

    # Round 2: 细节提取（不变）
    logger.info("  [%s] Round 2/2: 提取细节…", chapter.id)
    details = _as_model(
        await llm_client.generate_structured(
            prompt=DETAIL_EXTRACTION_PROMPT.format(
                chapter_content=chapter_text,
                entity_list=_format_entity_list(entities),
            ),
            schema=ChapterDetails,
            model=config.extraction,
        ),
        ChapterDetails,
    )

    return ChapterExtraction(
        chapter_id=chapter.id,
        chapter_title=chapter.title,
        entities=entities,
        relationships=relations,
        cases=details.cases if isinstance(details, ChapterDetails) else [],
        data_points=details.data_points if isinstance(details, ChapterDetails) else [],
        quotes=details.quotes if isinstance(details, ChapterDetails) else [],
        key_arguments=details.key_arguments if isinstance(details, ChapterDetails) else [],
        recommendations=details.recommendations if isinstance(details, ChapterDetails) else [],
    )


# ──────────────────────────────────────────────────────────────
# 长章节：分段联合提取 + 跨段桥接
# ──────────────────────────────────────────────────────────────


async def _extract_long_joint(
    chapter: Chapter,
    segments: list,
    book_context: BookContext,
    existing_entities: list[dict],
    llm_client: LLMClient,
    config: ModelConfig,
) -> ChapterExtraction:
    """长章节: 分段并行联合提取 + 跨段桥接 + 覆盖度自检。"""

    ctx_str = f"{book_context.core_thesis}\n术语: {', '.join(book_context.terminology.keys())}"
    entity_list_str = _format_existing_entities(existing_entities)

    # Round 1: 各段并行联合提取（实体+关系）
    logger.info("  [%s] 长章节 %d 段 → Round 1/2: 并行联合提取…", chapter.id, len(segments))
    r1_tasks = [
        llm_client.generate_structured(
            prompt=JOINT_EXTRACTION_PROMPT.format(
                book_context=ctx_str,
                chapter_content=seg.text_with_ids,
                existing_entities=entity_list_str,
            ),
            schema=JointExtractionResponse,
            model=config.extraction,
        )
        for seg in segments
    ]
    seg_results = [_as_model(r, JointExtractionResponse) for r in await asyncio.gather(*r1_tasks)]

    # 合并各段结果
    all_entities_raw = []
    all_rels_raw = []
    for sr in seg_results:
        if sr.entities:
            all_entities_raw.extend(sr.entities)
        if sr.relations:
            all_rels_raw.extend(sr.relations)

    merged_entities = merge_entity_results([all_entities_raw])
    merged_rels = merge_relationship_results([all_rels_raw], [])
    _mark_relation_source(merged_rels, "llm_joint")

    logger.info(
        "  [%s] 联合提取完成: %d 实体, %d 关系",
        chapter.id,
        len(merged_entities.entities) if hasattr(merged_entities, 'entities') else len(merged_entities),
        len(merged_rels),
    )

    # 跨段桥接（复用已有逻辑）
    bridge_rels_raw = await _bridge_cross_segment_relations(
        segments, merged_entities, [all_rels_raw], llm_client, config,
    )
    if bridge_rels_raw:
        bridge_rels = merge_relationship_results([], bridge_rels_raw)
        _mark_relation_source(bridge_rels, "llm_joint")
        all_relationships = merge_relationship_results([merged_rels], bridge_rels)
    else:
        all_relationships = merged_rels

    # 覆盖度自检
    entity_list = merged_entities.entities if hasattr(merged_entities, 'entities') else merged_entities
    orphans = _find_orphan_entities(entity_list, all_relationships)
    orphan_rate = len(orphans) / len(entity_list) if entity_list else 0

    if orphan_rate > COVERAGE_ORPHAN_THRESHOLD and orphans:
        # 构建完整原文用于补全
        full_text = "\n\n".join(seg.text_with_ids for seg in segments)
        logger.info(
            "  [%s] 孤立率 %.1f%% > %.0f%%，触发定向补全 (%d 个孤立实体)",
            chapter.id, orphan_rate * 100, COVERAGE_ORPHAN_THRESHOLD * 100, len(orphans),
        )
        fix_rels = await _fix_orphan_entities(
            orphans=orphans,
            all_entities=entity_list,
            chapter_text=full_text,
            llm_client=llm_client,
            config=config,
        )
        all_relationships = merge_relationship_results([all_relationships], fix_rels)
        orphans_after = _find_orphan_entities(entity_list, all_relationships)
        logger.info(
            "  [%s] 补全后: %d 关系, 孤立实体 %d → %d",
            chapter.id, len(all_relationships), len(orphans), len(orphans_after),
        )

    # Round 2: 细节提取
    logger.info("  [%s] Round 2/2: 提取细节…", chapter.id)
    r2_tasks = [
        llm_client.generate_structured(
            prompt=DETAIL_EXTRACTION_PROMPT.format(
                chapter_content=seg.text_with_ids,
                entity_list=_format_entity_list(entity_list),
            ),
            schema=ChapterDetails,
            model=config.extraction,
        )
        for seg in segments
    ]
    seg_detail_results = [_as_model(r, ChapterDetails) for r in await asyncio.gather(*r2_tasks)]
    merged_details = merge_detail_results(seg_detail_results)
    logger.info("  [%s] 提取完成", chapter.id)

    return ChapterExtraction(
        chapter_id=chapter.id,
        chapter_title=chapter.title,
        entities=entity_list,
        relationships=all_relationships,
        cases=merged_details.get("cases", []),
        data_points=merged_details.get("data_points", []),
        quotes=merged_details.get("quotes", []),
        key_arguments=merged_details.get("key_arguments", []),
        recommendations=merged_details.get("recommendations", []),
    )


# ──────────────────────────────────────────────────────────────
# 孤立实体定向补全
# ──────────────────────────────────────────────────────────────


async def _fix_orphan_entities(
    orphans: list[str],
    all_entities: list,
    chapter_text: str,
    llm_client: LLMClient,
    config: ModelConfig,
) -> list:
    """对孤立实体定向补全关系。"""
    # 截断原文避免上下文过长
    if len(chapter_text) > 30000:
        chapter_text = chapter_text[:30000] + "\n...(原文截断)"

    result = _as_model(
        await llm_client.generate_structured(
            prompt=COVERAGE_FIX_PROMPT.format(
                chapter_content=chapter_text,
                orphan_entities=_format_orphan_entities(orphans, all_entities),
                all_entities=_format_entity_list(all_entities),
            ),
            schema=RelationshipListResponse,
            model=config.extraction,
        ),
        RelationshipListResponse,
    )

    fix_rels = result.items if result.items else []
    _mark_relation_source(fix_rels, "llm_coverage_fix")
    return fix_rels


# ──────────────────────────────────────────────────────────────
# 跨段桥接（复用）
# ──────────────────────────────────────────────────────────────


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
) -> list:
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
                    f"{rel.source} → {str(rel.relation_type)} → {rel.target}"
                )
            elif isinstance(rel, dict):
                intra_rels.append(
                    f"{rel.get('source', '?')} → {rel.get('relation_type', '?')} → {rel.get('target', '?')}"
                )
    intra_rels_str = "\n".join(intra_rels[:50])

    result = _as_model(
        await llm_client.generate_structured(
            prompt=BRIDGE_RELATION_PROMPT.format(
                segment_summaries=segment_summaries,
                entity_list=_format_entity_list(merged_entities),
                intra_segment_relations=intra_rels_str,
            ),
            schema=RelationshipListResponse,
            model=config.extraction,
        ),
        RelationshipListResponse,
    )
    return result.items
