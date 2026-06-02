"""长章节分段处理。

放置位置: backend/src/core/knowledge_qa/d2g/long_chapter.py
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from src.core.knowledge_qa.neo4j.chapter_parser import Chapter, _estimate_tokens

logger = logging.getLogger(__name__)


def split_paragraphs(text: str) -> list[str]:
    """将 Markdown 文本按段落边界稳健分割。

    归一化处理：
    - \\r\\n\\r\\n (Windows 双换行)
    - \\n\\n (Unix 双换行)
    - \\n    \\n (空行含空白字符)
    - 连续多个空行等同单个分隔

    返回非空段落列表（已 strip 首尾空白）。
    """
    normalized = re.sub(r'\r\n', '\n', text)
    parts = re.split(r'\n\s*\n', normalized)
    return [p.strip() for p in parts if p.strip()]

LONG_CHAPTER_THRESHOLD = 20_000
SEGMENT_TARGET_SIZE = 12_000
OVERLAP_SIZE = 1_500
MAX_SEGMENTS = 8


@dataclass
class Segment:
    """一个分段。"""
    index: int
    paragraph_ids: list[int]
    text_with_ids: str
    token_count: int


def segment_chapter(
    chapter: Chapter,
    threshold: int = LONG_CHAPTER_THRESHOLD,
    seg_target: int = SEGMENT_TARGET_SIZE,
    overlap: int = OVERLAP_SIZE,
) -> list[Segment]:
    """将章节按段落边界分段，带滑窗重叠。

    短章节（< threshold）返回单元素列表。
    """
    paragraphs = split_paragraphs(chapter.markdown)
    para_tokens = [_estimate_tokens(p) for p in paragraphs]
    total_tokens = sum(para_tokens)

    if total_tokens <= threshold:
        text = "\n\n".join(f"[P{i+1}] {p}" for i, p in enumerate(paragraphs))
        return [Segment(
            index=0,
            paragraph_ids=list(range(1, len(paragraphs) + 1)),
            text_with_ids=text,
            token_count=total_tokens,
        )]

    segments: list[Segment] = []
    seg_start = 0
    seg_idx = 0

    while seg_start < len(paragraphs) and seg_idx < MAX_SEGMENTS:
        # 累积段落直到达到目标大小
        seg_end = seg_start
        acc_tokens = 0
        while seg_end < len(paragraphs) and acc_tokens < seg_target:
            acc_tokens += para_tokens[seg_end]
            seg_end += 1

        # 构造带 ID 的文本
        text = "\n\n".join(
            f"[P{i+1}] {paragraphs[i]}" for i in range(seg_start, seg_end)
        )

        segments.append(Segment(
            index=seg_idx,
            paragraph_ids=list(range(seg_start + 1, seg_end + 1)),
            text_with_ids=text,
            token_count=acc_tokens,
        ))

        # 计算重叠段落数
        overlap_paras = 0
        overlap_tokens = 0
        for i in range(seg_end - 1, seg_start, -1):
            if overlap_tokens + para_tokens[i] > overlap:
                break
            overlap_tokens += para_tokens[i]
            overlap_paras += 1

        next_start = seg_end - overlap_paras
        if next_start <= seg_start:
            next_start = seg_start + 1  # 防止死循环

        seg_start = next_start
        seg_idx += 1

    logger.info(
        "长章节 '%s' 分为 %d 段 (原 %d tokens)",
        chapter.title, len(segments), total_tokens,
    )
    return segments


# ──────────────────────────────────────────────────────────────
# 合并函数
# ──────────────────────────────────────────────────────────────


@dataclass
class MergedEntities:
    """合并后的实体列表。"""
    entities: list = field(default_factory=list)
    seen: dict[str, int] = field(default_factory=dict)


def merge_entity_results(segment_results: list[list]) -> MergedEntities:
    """合并多段的实体提取结果，按 name+type 去重。"""
    merged = MergedEntities()

    for seg_entities in segment_results:
        for entity in seg_entities:
            name = entity.name if hasattr(entity, "name") else entity.get("name", "")
            etype = (
                entity.entity_type
                if hasattr(entity, "entity_type")
                else entity.get("entity_type", "")
            )
            key = f"{name}::{etype}"

            if key in merged.seen:
                idx = merged.seen[key]
                existing = merged.entities[idx]
                # 保留更长的描述
                new_desc = entity.description if hasattr(entity, "description") else entity.get("description", "")
                old_desc = existing.description if hasattr(existing, "description") else existing.get("description", "")
                if len(new_desc) > len(old_desc):
                    if hasattr(existing, "description"):
                        existing.description = new_desc
                    else:
                        existing["description"] = new_desc
                # 合并 source_para_ids
                new_pids = entity.source_para_ids if hasattr(entity, "source_para_ids") else entity.get("source_para_ids", [])
                old_pids = existing.source_para_ids if hasattr(existing, "source_para_ids") else existing.get("source_para_ids", [])
                union_pids = sorted(set(old_pids) | set(new_pids))
                if hasattr(existing, "source_para_ids"):
                    existing.source_para_ids = union_pids
                else:
                    existing["source_para_ids"] = union_pids
            else:
                merged.seen[key] = len(merged.entities)
                merged.entities.append(entity)

    return merged


def merge_relationship_results(
    seg_rel_results: list[list],
    bridge_rels: list,
) -> list:
    """合并多段关系 + 跨段桥接关系。"""
    seen: dict[str, int] = {}
    result: list = []

    def _key(rel):
        s = rel.source if hasattr(rel, "source") else rel.get("source", "")
        t = rel.target if hasattr(rel, "target") else rel.get("target", "")
        r = (
            str(rel.relation_type)
            if hasattr(rel, "relation_type")
            else rel.get("relation_type", "")
        )
        return f"{s}::{t}::{r}"

    def _evidence(rel):
        return rel.evidence if hasattr(rel, "evidence") else rel.get("evidence", "")

    def _pids(rel):
        return (
            rel.source_para_ids
            if hasattr(rel, "source_para_ids")
            else rel.get("source_para_ids", [])
        )

    all_rels = []
    for seg_rels in seg_rel_results:
        all_rels.extend(seg_rels)
    all_rels.extend(bridge_rels)

    for rel in all_rels:
        key = _key(rel)
        if key in seen:
            idx = seen[key]
            if len(_evidence(rel)) > len(_evidence(result[idx])):
                if hasattr(result[idx], "evidence"):
                    result[idx].evidence = _evidence(rel)
                else:
                    result[idx]["evidence"] = _evidence(rel)
            # 合并 para_ids
            union_pids = sorted(set(_pids(result[idx])) | set(_pids(rel)))
            if hasattr(result[idx], "source_para_ids"):
                result[idx].source_para_ids = union_pids
            else:
                result[idx]["source_para_ids"] = union_pids
        else:
            seen[key] = len(result)
            result.append(rel)

    return result


def merge_detail_results(seg_details: list) -> dict:
    """合并多段的细节提取结果。"""
    merged = {
        "cases": [],
        "data_points": [],
        "quotes": [],
        "key_arguments": [],
        "recommendations": [],
    }

    seen_cases: set[str] = set()
    seen_data: set[str] = set()
    seen_quotes: set[str] = set()

    for detail in seg_details:
        # 跳过纯列表（旧版 API 兼容，不应出现但防御性处理）
        if isinstance(detail, list):
            continue
        # 兼容 Pydantic 对象和 dict
        cases = detail.cases if hasattr(detail, "cases") else detail.get("cases", [])
        data_points = (
            detail.data_points if hasattr(detail, "data_points")
            else detail.get("data_points", [])
        )
        quotes = detail.quotes if hasattr(detail, "quotes") else detail.get("quotes", [])
        args = (
            detail.key_arguments if hasattr(detail, "key_arguments")
            else detail.get("key_arguments", [])
        )
        recs = (
            detail.recommendations if hasattr(detail, "recommendations")
            else detail.get("recommendations", [])
        )

        for case in cases:
            title = case.title if hasattr(case, "title") else case.get("title", "")
            if title not in seen_cases:
                seen_cases.add(title)
                merged["cases"].append(case)

        for dp in data_points:
            metric = dp.metric if hasattr(dp, "metric") else dp.get("metric", "")
            value = dp.value if hasattr(dp, "value") else dp.get("value", "")
            key = f"{metric}::{value}"
            if key not in seen_data:
                seen_data.add(key)
                merged["data_points"].append(dp)

        for q in quotes:
            text = q.text if hasattr(q, "text") else q.get("text", "")
            prefix = text[:50]
            if prefix not in seen_quotes:
                seen_quotes.add(prefix)
                merged["quotes"].append(q)

        merged["key_arguments"].extend(args)
        merged["recommendations"].extend(recs)

    return merged



def merge_entity_results(seg_results: list[list]) -> list:
    """合并各段的实体提取结果，去重。"""
    seen = set()
    merged = []
    for entities in seg_results:
        for e in (entities if isinstance(entities, list) else []):
            if e.name not in seen:
                seen.add(e.name)
                merged.append(e)
    return merged


def merge_relationship_results(seg_results: list[list], bridge_rels: list | None = None) -> list:
    """合并各段的关系提取结果，去重。"""
    seen = set()
    merged = []
    all_rels = list(seg_results) if seg_results else []
    if bridge_rels:
        all_rels.extend(bridge_rels)
    for rel_list in all_rels:
        for r in (rel_list if isinstance(rel_list, list) else []):
            key = (r.source, r.target, r.relation_type.value if hasattr(r.relation_type, 'value') else str(r.relation_type))
            if key not in seen:
                seen.add(key)
                merged.append(r)
    return merged

