"""MD 渲染器 — 从聚合结果生成标准格式的 Markdown 草稿。

放置位置: backend/src/core/knowledge_qa/neo4j/md_renderer.py
"""

from __future__ import annotations

import yaml
from datetime import datetime, timezone
from .aggregator import AggregatedBook


def render_md_draft(book: AggregatedBook, version: int = 1) -> str:
    """将聚合结果渲染为标准 MD 草稿。

    Args:
        book: 聚合结果
        version: 版本号

    Returns:
        完整的 Markdown 字符串（含 YAML front matter）
    """
    front_matter = {
        "book_id": book.book_id,
        "book_title": book.book_title,
        "status": "draft",
        "version": version,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "reviewed_by": None,
        "reviewed_at": None,
    }

    lines = [
        "---",
        yaml.dump(front_matter, allow_unicode=True, default_flow_style=False).strip(),
        "---",
        "",
        f"# {book.book_title} — 结构化知识",
        "",
    ]

    # 概念
    if book.entities:
        lines.append("## 概念\n")
        for ent in book.entities:
            lines.append(f"### {ent.name}")
            lines.append(f"- **entity_type**: {ent.entity_type}")
            lines.append(f"- **description**: {ent.descriptions[0] if ent.descriptions else ''}")
            if ent.sources:
                lines.append(f"- **source**: {ent.sources[0]}")
            lines.append("")

    # 主张
    if book.claims:
        lines.append("## 主张\n")
        for i, claim in enumerate(book.claims):
            # 生成标题: 优先用 source→target 格式，其次 title 字段，最后序号
            src = claim.get("source_concept", claim.get("source_problem", ""))
            tgt = claim.get("target_concept", claim.get("source_solution", ""))
            if src and tgt:
                title = f"{src} → {tgt}"
            else:
                title = claim.get("title", f"主张 {i+1}")
            lines.append(f"### {title}")
            for key, value in claim.items():
                if key not in ("title", "chapter_id", "source_concept", "target_concept",
                               "source_problem", "source_solution"):
                    lines.append(f"- **{key}**: {value}")
            lines.append("")

    # 运动处方
    if book.prescriptions:
        lines.append("## 运动处方\n")
        for rx in book.prescriptions:
            name = rx.get("exercise", "未知运动")
            lines.append(f"### {name}")
            for key, value in rx.items():
                if key not in ("chapter_id",):
                    lines.append(f"- **{key}**: {value}")
            lines.append("")

    # 核心论点
    if book.key_arguments:
        lines.append("## 核心论点\n")
        for i, arg in enumerate(book.key_arguments):
            title = arg.get("argument", f"论点 {i+1}")[:60]
            lines.append(f"### {title}")
            for key, value in arg.items():
                if key == "argument":
                    continue
                if isinstance(value, list):
                    lines.append(f"- **{key}**:")
                    for item in value:
                        lines.append(f"  - {item}")
                else:
                    lines.append(f"- **{key}**: {value}")
            lines.append("")

    # 案例/故事
    if book.case_studies:
        lines.append("## 案例/故事\n")
        for i, case in enumerate(book.case_studies):
            title = case.get("title", f"案例 {i+1}")
            lines.append(f"### {title}")
            for key, value in case.items():
                if key == "title":
                    continue
                if isinstance(value, list):
                    lines.append(f"- **{key}**:")
                    for item in value:
                        lines.append(f"  - {item}")
                else:
                    lines.append(f"- **{key}**: {value}")
            lines.append("")

    # 数据/事实
    if book.data_points:
        lines.append("## 数据/事实\n")
        for i, dp in enumerate(book.data_points):
            metric = dp.get("metric", f"数据 {i+1}")
            value = dp.get("value", "")
            title = f"{metric}: {value}" if value else metric
            lines.append(f"### {title}")
            for key, val in dp.items():
                if key in ("metric", "value"):
                    continue
                lines.append(f"- **{key}**: {val}")
            lines.append("")

    # 章节摘要
    if book.chapter_summaries:
        lines.append("## 章节摘要\n")
        for i, summary in enumerate(book.chapter_summaries):
            theme = summary.get("central_theme", f"摘要 {i+1}")
            lines.append(f"### {theme}")
            for key, value in summary.items():
                if key == "central_theme":
                    continue
                if isinstance(value, list):
                    lines.append(f"- **{key}**:")
                    for item in value:
                        lines.append(f"  - {item}")
                else:
                    lines.append(f"- **{key}**: {value}")
            lines.append("")

    return "\n".join(lines)
