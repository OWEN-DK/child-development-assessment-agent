"""审核 MD 生成器 — 从主图 + 章节提取结果生成审核用 MD。

放置位置: backend/src/core/knowledge_qa/d2g/review_md_generator.py

生成的 MD 格式兼容现有 DraftEditorPage 前端（## 类型 → ### 实体名）。
"""

from __future__ import annotations

import yaml
from datetime import datetime, timezone

from .master_graph import MasterGraph
from .models import ChapterExtraction


def generate_review_md(
    extraction: ChapterExtraction,
    master: MasterGraph,
) -> str:
    """为单章提取结果生成审核用 MD。

    Args:
        extraction: 章节提取结果
        master: 主图（用于判断哪些是新实体）

    Returns:
        完整的 Markdown 字符串（含 YAML front matter）
    """
    existing_entities = set(master.graph.nodes)

    # 分类：新实体 vs 已有实体
    new_entities = [e for e in extraction.entities if e.name not in existing_entities]
    existing_ents = [e for e in extraction.entities if e.name in existing_entities]

    # 计算段落覆盖率
    total_paras = max(
        (pid for e in extraction.entities for pid in e.source_para_ids),
        default=0,
    )
    covered_paras = set()
    for e in extraction.entities:
        covered_paras.update(e.source_para_ids)
    coverage = f"{len(covered_paras)}/{total_paras}" if total_paras > 0 else "N/A"

    lines = [
        "---",
        yaml.dump(
            {
                "book_id": master.book_id,
                "book_title": master.book_title,
                "status": "draft",
                "version": 1,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "reviewed_by": None,
                "reviewed_at": None,
                "chapter_id": extraction.chapter_id,
            },
            allow_unicode=True,
            default_flow_style=False,
        ).strip(),
        "---",
        "",
        f"# {extraction.chapter_title} — 提取审核",
        "",
        f"> 本章提取了 {len(extraction.entities)} 个实体、"
        f"{len(extraction.relationships)} 条关系。"
        f"段落覆盖: {coverage}",
        "",
    ]

    # ─── 新增实体 ───
    if new_entities:
        lines.append("## 概念\n")
        for entity in new_entities:
            lines.append(f"### {entity.name}")
            lines.append(f"- **entity_type**: {entity.entity_type}")
            lines.append(f"- **description**: {entity.description}")
            if entity.source_para_ids:
                pids = ", ".join(f"P{p}" for p in entity.source_para_ids)
                lines.append(f"- **来源**: {pids}")
            lines.append("")

    # ─── 已有实体（图中已存在，本章新增信息）───
    if existing_ents:
        lines.append("## 已有实体\n")
        for entity in existing_ents:
            source_chs = master.graph.nodes[entity.name].get("source_chapters", [])
            ch_str = ", ".join(source_chs) if source_chs else "未知"
            lines.append(f"### {entity.name} [已在 {ch_str} 提取]")
            lines.append(f"- **entity_type**: {entity.entity_type}")
            lines.append(f"- **本章新增来源**: P{', P'.join(map(str, entity.source_para_ids))}")
            lines.append("")

    # ─── 关系 ───
    if extraction.relationships:
        lines.append("## 主张\n")
        for rel in extraction.relationships:
            lines.append(f"### {rel.source} → {rel.target}")
            lines.append(f"- **relation_type**: {str(rel.relation_type)}")
            lines.append(f"- **evidence**: {rel.evidence}")
            if rel.source_para_ids:
                pids = ", ".join(f"P{p}" for p in rel.source_para_ids)
                lines.append(f"- **来源**: {pids}")
            lines.append("")

    # ─── 案例与故事 ───
    if extraction.cases:
        lines.append("## 案例/故事\n")
        for case in extraction.cases:
            lines.append(f"### {case.title}")
            lines.append(f"- **背景**: {case.background}")
            lines.append(f"- **过程**: {case.process}")
            lines.append(f"- **结果**: {case.result}")
            lines.append(f"- **启示**: {case.insight}")
            if case.related_entities:
                lines.append(f"- **相关实体**: {', '.join(case.related_entities)}")
            if case.source_para_ids:
                pids = ", ".join(f"P{p}" for p in case.source_para_ids)
                lines.append(f"- **来源**: {pids}")
            lines.append("")

    # ─── 数据/事实 ───
    if extraction.data_points:
        lines.append("## 数据/事实\n")
        for dp in extraction.data_points:
            lines.append(f"### {dp.metric}: {dp.value}")
            lines.append(f"- **上下文**: {dp.context}")
            if dp.source_attribution:
                lines.append(f"- **来源**: {dp.source_attribution}")
            if dp.source_para_ids:
                pids = ", ".join(f"P{p}" for p in dp.source_para_ids)
                lines.append(f"- **段落**: {pids}")
            lines.append("")

    # ─── 引言 ───
    if extraction.quotes:
        lines.append("## 关键引言\n")
        for q in extraction.quotes:
            lines.append(f"> \"{q.text}\" — {q.speaker}")
            if q.context:
                lines.append(f"\n**上下文**: {q.context}")
            lines.append("")

    # ─── 核心论点 ───
    if extraction.key_arguments:
        lines.append("## 核心论点\n")
        for arg in extraction.key_arguments:
            lines.append(f"- {arg}")
        lines.append("")

    # ─── 实践建议 ───
    if extraction.recommendations:
        lines.append("## 实践建议\n")
        for rec in extraction.recommendations:
            title = rec.get("title", "建议")
            lines.append(f"### {title}")
            for key, value in rec.items():
                if key != "title":
                    lines.append(f"- **{key}**: {value}")
            lines.append("")

    # ─── 段落覆盖详情 ───
    lines.append("## 段落覆盖详情\n")
    for pid in range(1, total_paras + 1):
        if pid in covered_paras:
            lines.append(f"- P{pid}: ✅")
        else:
            lines.append(f"- P{pid}: ❌ 未覆盖")
    lines.append("")

    return "\n".join(lines)


# ── 跨书匹配展示（§08-3） ───────────────────────────────────


def generate_cross_book_section(
    cross_matches: list[dict],
) -> str:
    """生成审核 MD 中的"跨书匹配"章节。

    Args:
        cross_matches: 跨书匹配结果列表，每项包含:
            - entity_name: 本章实体名
            - matches: [{book_title, entity_name, similarity, llm_reason}]

    Returns:
        Markdown 格式的跨书匹配章节
    """
    if not cross_matches:
        return ""

    lines = ["## 跨书匹配（与已入库书籍的相似实体）\n"]

    for item in cross_matches:
        entity_name = item.get("entity_name", "")
        matches = item.get("matches", [])
        if not matches:
            continue

        lines.append(f"### {entity_name}")
        desc = item.get("description", "")
        if desc:
            lines.append(f"**本章描述**: {desc[:200]}...\n")

        lines.append("**匹配到**:")
        lines.append("| # | 书名 | 实体名 | 相似度 | LLM判断 | 审核者决策 |")
        lines.append("|---|------|--------|--------|---------|-----------|")

        for idx, m in enumerate(matches, 1):
            book_title = m.get("book_title", "")
            matched_name = m.get("entity_name", "")
            sim = m.get("similarity", 0)
            llm_reason = m.get("llm_reason", "")
            lines.append(
                f"| {idx} | {book_title} | {matched_name} | {sim:.2f} | "
                f"{llm_reason} | ○合并 ○独立 ○跳过 |"
            )
        lines.append("")

    lines.append('> **默认值**: 审核者决策列默认选中"跳过"。审核者不操作时视为"跳过"，Phase 5 按自动阈值处理。\n')

    return "\n".join(lines)


def generate_merge_log_section(merge_log: list[dict]) -> str:
    """生成消歧合并记录的审核 MD 段落。

    Args:
        merge_log: [{alias, representative, similarity, reason}, ...]

    Returns:
        Markdown 格式的合并记录
    """
    if not merge_log:
        return ""

    lines = [
        "## 消歧合并记录\n",
        "以下实体被自动判定为同一概念并合并。如需拆分，请在审核时注明。",
        "",
        "| 原始实体 | 合并为 | 相似度 | LLM 理由 |",
        "|---------|--------|--------|----------|",
    ]

    for entry in merge_log:
        alias = entry.get("alias", "")
        rep = entry.get("representative", "")
        sim = entry.get("similarity", 0)
        reason = entry.get("reason", "")
        lines.append(f"| {alias} | {rep} | {sim:.3f} | {reason} |")

    lines.append("")
    lines.append(f"> 共 {len(merge_log)} 次合并。")
    lines.append("")

    return "\n".join(lines)
