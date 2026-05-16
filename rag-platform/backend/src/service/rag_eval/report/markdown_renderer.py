"""Markdown 报告渲染器

将评估指标、诊断结果、跨域分析、调优建议、失败用例
渲染为可读的 Markdown 报告。
"""
from typing import Any, Optional


class MarkdownRenderer:
    """Markdown 报告渲染器"""

    def render_full_report(
        self,
        run_id: str,
        run_name: str,
        pipeline_id: str,
        pipeline_version: int,
        overall_score: float,
        l1_metrics: Optional[dict[str, Any]],
        l2_metrics: Optional[dict[str, Any]],
        l3_metrics: Optional[dict[str, Any]],
        cross_domain_section: Optional[dict[str, Any]],
        bad_cases: Optional[dict[str, Any]],
        tuning_suggestions: Optional[list[dict[str, Any]]],
        diagnosis_json: Optional[dict[str, Any]],
    ) -> str:
        """渲染完整 Markdown 报告"""
        sections = [
            self._render_header(
                run_id=run_id,
                run_name=run_name,
                pipeline_id=pipeline_id,
                pipeline_version=pipeline_version,
                overall_score=overall_score,
            ),
            self._render_metrics_section(l1_metrics, l2_metrics, l3_metrics),
            self._render_cross_domain_section(cross_domain_section),
            self._render_diagnosis_section(diagnosis_json),
            self._render_tuning_section(tuning_suggestions),
            self._render_bad_cases_section(bad_cases),
        ]
        return "\n\n".join(s for s in sections if s)

    def _render_header(
        self,
        run_id: str,
        run_name: str,
        pipeline_id: str,
        pipeline_version: int,
        overall_score: float,
    ) -> str:
        title = run_name or f"评估报告 {run_id}"
        return f"""# {title}

| 属性 | 值 |
|------|-----|
| 运行 ID | `{run_id}` |
| 管道 ID | `{pipeline_id}` |
| 管道版本 | v{pipeline_version} |
| 综合得分 | **{overall_score:.4f}** |

"""

    def _render_metrics_section(
        self,
        l1: Optional[dict[str, Any]],
        l2: Optional[dict[str, Any]],
        l3: Optional[dict[str, Any]],
    ) -> str:
        """渲染三层指标表格"""
        lines = ["## 指标详情\n"]
        layers = [("L1 检索层", l1), ("L2 生成层", l2), ("L3 系统层", l3)]

        for layer_name, metrics in layers:
            if not metrics:
                continue
            lines.append(f"### {layer_name}\n")
            avg_score = metrics.get("avg_score", metrics.get("avg_score", 0))
            lines.append(f"**加权平均分**: {avg_score:.4f}\n")
            lines.append("| 指标 | 分数 | 通过 | 权重 |")
            lines.append("|------|------|------|------|")
            scores = metrics.get("scores", [])
            if isinstance(scores, list):
                for s in scores:
                    if isinstance(s, dict):
                        name = s.get("display_name", s.get("name", "N/A"))
                        score = s.get("score", 0)
                        passed = "✓" if s.get("passed") else "✗"
                        weight = s.get("weight", 0)
                        lines.append(
                            f"| {name} | {score:.4f} | {passed} | {weight:.2f} |"
                        )
            lines.append("")

        return "\n".join(lines)

    def _render_cross_domain_section(
        self, section: Optional[dict[str, Any]]
    ) -> str:
        """渲染跨域分析章节

        包含域贡献度表格、冲突统计表格、延迟分布表格。
        """
        if not section:
            return ""

        lines = ["## 跨域分析\n"]

        # 域贡献度
        contributions = section.get("domain_contributions", [])
        if contributions:
            lines.append("### 域贡献度\n")
            lines.append("| 域 | 激活准确率 | 命中次数 | 平均贡献度 |")
            lines.append("|------|-----------|---------|----------|")
            for dc in contributions:
                name = dc.get("domain_name", dc.get("domain_id", "N/A"))
                acc = dc.get("activation_accuracy", 0)
                hits = dc.get("chunk_count", dc.get("hit_count", 0))
                contrib = dc.get("contribution_score", 0)
                lines.append(f"| {name} | {acc:.4f} | {hits} | {contrib:.4f} |")
            lines.append("")

        # 冲突统计
        conflicts = section.get("domain_conflicts", [])
        if conflicts:
            lines.append("### 跨域冲突统计\n")
            lines.append("| 域对 | 期望冲突 | 检测到冲突 | 检测率 |")
            lines.append("|------|---------|----------|--------|")
            for c in conflicts:
                if isinstance(c, dict):
                    pair = c.get("domain_pair", "N/A")
                    expected = c.get("total_conflicts", 0)
                    detected = c.get("detected_conflicts", 0)
                    rate = c.get("detection_rate", 0)
                    lines.append(f"| {pair} | {expected} | {detected} | {rate:.4f} |")
            lines.append("")

        # 延迟分布
        latency = section.get("e2e_latency_distribution", {})
        if latency:
            lines.append("### 端到端延迟分布\n")
            lines.append("| P50 | P95 | P99 | 平均 |")
            lines.append("|-----|-----|-----|------|")
            p50 = latency.get("p50_ms", 0)
            p95 = latency.get("p95_ms", 0)
            p99 = latency.get("p99_ms", 0)
            avg = latency.get("avg_ms", 0)
            lines.append(f"| {p50}ms | {p95}ms | {p99}ms | {avg}ms |")
            lines.append("")

        return "\n".join(lines)

    def _render_diagnosis_section(
        self, diagnosis: Optional[dict[str, Any]]
    ) -> str:
        """渲染六层诊断结果"""
        if not diagnosis:
            return ""
        lines = ["## 诊断结果\n"]
        layers = diagnosis.get("layers", [])
        if isinstance(layers, list):
            for layer in layers:
                if isinstance(layer, dict):
                    layer_name = layer.get("name", layer.get("layer", "N/A"))
                    status = layer.get("status", "N/A")
                    issues = layer.get("issues", [])
                    lines.append(f"### {layer_name} (状态: {status})\n")
                    if issues:
                        lines.append("| # | 问题 | 严重度 | 详情 |")
                        lines.append("|---|------|--------|------|")
                        for i, issue in enumerate(issues, 1):
                            if isinstance(issue, dict):
                                desc = issue.get("description", issue.get("message", ""))
                                severity = issue.get("severity", "info")
                                detail = issue.get("detail", "")
                                lines.append(f"| {i} | {desc} | {severity} | {detail} |")
                    else:
                        lines.append("无问题。\n")
                    lines.append("")
        return "\n".join(lines)

    def _render_tuning_section(
        self, suggestions: Optional[list[dict[str, Any]]]
    ) -> str:
        """渲染调优建议"""
        if not suggestions:
            return ""
        lines = ["## 调优建议\n"]
        lines.append("| # | 类别 | 严重度 | 标题 | 预期影响 |")
        lines.append("|---|------|--------|------|----------|")
        for i, s in enumerate(suggestions, 1):
            if isinstance(s, dict):
                category = s.get("category", "N/A")
                severity = s.get("severity", "info")
                title = s.get("title", "N/A")
                impact = s.get("expected_impact", "N/A")
                lines.append(f"| {i} | {category} | {severity} | {title} | {impact} |")
        lines.append("")
        return "\n".join(lines)

    def _render_bad_cases_section(
        self, bad_cases: Optional[dict[str, Any]]
    ) -> str:
        """渲染失败用例列表"""
        if not bad_cases:
            return ""
        items = bad_cases.get("items", [])
        if not items:
            return ""
        lines = [f"## 失败用例 ({bad_cases.get('total', len(items))})\n"]
        lines.append("| 用例 ID | 查询 | Precision | Recall | F1 | 耗时(ms) | 错误 |")
        lines.append("|---------|------|-----------|--------|-----|----------|------|")
        for bc in items:
            if isinstance(bc, dict):
                cid = bc.get("case_id", "N/A")
                query = bc.get("query", "")[:50]
                precision = bc.get("precision", 0) or 0
                recall = bc.get("recall", 0) or 0
                f1 = bc.get("f1", 0) or 0
                elapsed = bc.get("elapsed_ms", 0)
                error = (bc.get("error") or "")[:100]
                lines.append(
                    f"| {cid} | {query} | {precision:.4f} | {recall:.4f} "
                    f"| {f1:.4f} | {elapsed} | {error} |"
                )
        lines.append("")
        return "\n".join(lines)
