"""Phase 3: 全书图质量审计（纯程序化，零 LLM 调用）。

放置位置: backend/src/core/knowledge_qa/d2g/graph_quality.py
"""

from __future__ import annotations

import logging

from .master_graph import MasterGraph
from .models import GraphQualityMetrics, QualityThresholds

logger = logging.getLogger(__name__)


def audit_graph_quality(
    master: MasterGraph,
    thresholds: QualityThresholds | None = None,
    skip_chapters: set[str] | None = None,
) -> tuple[GraphQualityMetrics, list[str]]:
    """计算图质量指标，返回 (metrics, issues)。

    Args:
        master: 主图
        thresholds: 质量阈值（None 使用默认值）
        skip_chapters: 需要排除的章节 ID 集合（如目录、前言等非内容章节）

    Returns:
        (metrics, issues) — issues 是人类可读的问题描述列表
    """
    if thresholds is None:
        thresholds = QualityThresholds()

    metrics = master.get_quality_metrics(skip_chapters=skip_chapters)
    issues: list[str] = []

    # 检查孤立实体率
    if metrics.orphan_rate > thresholds.max_orphan_rate:
        orphans = [
            n for n in master.graph.nodes
            if master.graph.degree(n) == 0
        ]
        issues.append(
            f"孤立实体率 {metrics.orphan_rate:.1%} 超过阈值 {thresholds.max_orphan_rate:.0%}。"
            f"孤立实体 ({len(orphans)} 个): {', '.join(orphans[:10])}"
            f"{'...' if len(orphans) > 10 else ''}"
        )

    # 检查连通分量
    if metrics.connected_components > thresholds.max_connected_components:
        issues.append(
            f"连通分量 {metrics.connected_components} 个，超过阈值 {thresholds.max_connected_components}。"
            f"可能存在遗漏的跨段关联。"
        )

    # 检查最大连通分量占比
    if metrics.largest_component_ratio < thresholds.min_largest_component_ratio:
        issues.append(
            f"最大连通分量占比 {metrics.largest_component_ratio:.1%}，"
            f"低于阈值 {thresholds.min_largest_component_ratio:.0%}。图太碎片化。"
        )

    # 检查平均度
    if metrics.avg_degree < thresholds.min_avg_degree:
        issues.append(
            f"平均关系数 {metrics.avg_degree:.1f}，低于阈值 {thresholds.min_avg_degree}。"
            f"实体间关系不够丰富。"
        )

    # 检查章节覆盖率（round 对齐显示精度，避免 59.8% 显示 "60%" 但被判不达标）
    low_coverage_chapters = [
        (ch_id, cov)
        for ch_id, cov in metrics.chapter_coverage.items()
        if round(cov) < thresholds.min_chapter_coverage * 100
    ]
    if low_coverage_chapters:
        ch_list = ", ".join(
            f"{ch} ({cov:.0f}%)" for ch, cov in low_coverage_chapters
        )
        issues.append(
            f"以下章节段落覆盖率低于 {thresholds.min_chapter_coverage:.0%}: {ch_list}"
        )

    # 检查全书段落覆盖率
    if round(metrics.overall_para_coverage) < thresholds.min_overall_para_coverage * 100:
        issues.append(
            f"全书段落覆盖率 {metrics.overall_para_coverage:.0f}%，"
            f"低于阈值 {thresholds.min_overall_para_coverage:.0%}。"
        )

    if issues:
        logger.warning("图质量检查发现 %d 个问题", len(issues))
    else:
        logger.info("图质量检查通过")

    return metrics, issues


def generate_quality_report(
    metrics: GraphQualityMetrics,
    issues: list[str],
) -> str:
    """生成人类可读的质量报告。"""
    lines = [
        "# 图质量报告",
        "",
        f"- 总实体数: {metrics.total_entities}",
        f"- 总关系数: {metrics.total_relationships}",
        f"- 孤立实体: {metrics.orphan_entities} ({metrics.orphan_rate:.1%})",
        f"- 平均关系数: {metrics.avg_degree:.1f}",
        f"- 连通分量: {metrics.connected_components}",
        f"- 最大连通分量占比: {metrics.largest_component_ratio:.1%}",
        f"- 全书段落覆盖率: {metrics.overall_para_coverage:.0f}%",
        "",
    ]

    if metrics.chapter_coverage:
        lines.append("## 章节覆盖率")
        lines.append("")
        for ch_id, cov in sorted(metrics.chapter_coverage.items()):
            status = "✅" if cov >= 60 else "⚠️"
            lines.append(f"- {ch_id}: {cov:.0f}% {status}")
        lines.append("")

    if issues:
        lines.append("## 问题")
        lines.append("")
        for i, issue in enumerate(issues, 1):
            lines.append(f"{i}. {issue}")
        lines.append("")
    else:
        lines.append("## ✅ 所有指标达标")
        lines.append("")

    return "\n".join(lines)


def generate_relation_source_report(master: MasterGraph) -> str:
    """生成关系来源分布报告。"""
    G = master.graph
    source_counts: dict[str, int] = {}
    for _, _, data in G.edges(data=True):
        src = data.get("relation_source", "unknown")
        source_counts[src] = source_counts.get(src, 0) + 1

    total = sum(source_counts.values())
    if total == 0:
        return "关系来源分布: 无关系"

    source_labels = {
        "llm_joint": "LLM 联合提取",
        "llm_coverage_fix": "LLM 覆盖度补全",
        "heuristic_rule": "类型规则推断",
        "cooccurrence": "段落共现推断",
        "embedding_sim": "Embedding 语义关联",
        "component_bridge": "跨分量桥接",
        "llm_global_fix": "LLM 全局补全",
        "star_fallback": "星型兜底",
        "unknown": "未知来源",
    }

    lines = ["## 关系来源分布", ""]
    for src, count in sorted(source_counts.items(), key=lambda x: -x[1]):
        label = source_labels.get(src, src)
        pct = count / total * 100
        lines.append(f"- {label}: {count} 条 ({pct:.1f}%)")
    lines.append(f"- **总计**: {total} 条")
    lines.append("")

    return "\n".join(lines)
