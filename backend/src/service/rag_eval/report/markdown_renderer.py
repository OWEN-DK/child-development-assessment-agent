"""Markdown 渲染器——将 EvalReportData 渲染为 Markdown"""

from src.schemas.rag_eval.report import EvalReportData, MetricCard

_S = {"pass": "✅", "warn": "⚠️", "fail": "❌", "skip": "⏭️", "error": "💥"}
_SE = {"critical": "fail", "warning": "warn", "info": "pass"}

class MarkdownRenderer:
    """将 EvalReportData 渲染为 Markdown"""

    def render(self, data: EvalReportData) -> str:
        s = data.summary
        rate = (s.passed_cases / s.total_cases * 100) if s.total_cases else 0
        lines = [
            f"# 评估报告: {s.run_name}", "",
            f"- **总体得分**: {s.overall_score:.2%} | **通过率**: {rate:.1f}% ({s.passed_cases}/{s.total_cases})",
            f"- **L1**: {s.l1_score:.2%} | **L2**: {s.l2_score:.2%} | **L3**: {s.l3_score:.2%}",
            f"- **诊断**: {s.diagnosis_health:.2%} | **问题**: {s.total_issues} / 严重: {s.critical_issues}",
        ]
        if s.duration_ms:
            lines.append(f"- **执行时间**: {s.duration_ms}ms")
        lines.append("")

        lines += ["## 📊 三层指标看板", ""]
        lines += [self._mt(data.scoring_dashboard.l1, "L1 检索质量"),
                  self._mt(data.scoring_dashboard.l2, "L2 生成质量"),
                  self._mt(data.scoring_dashboard.l3, "L3 系统质量")]

        lines += ["## 🔍 六层诊断详情", ""]
        for sec in data.diagnosis_details:
            lines.append(self._dx(sec))

        lines += ["## ❌ 坏案分析", "", self._bc(data.bad_cases),
                  "## 🔧 调优建议", ""]
        if data.tuning_suggestions:
            for i, e in enumerate(data.tuning_suggestions):
                lines.append(self._tu(e, i + 1))
        else:
            lines.append("暂无调优建议")
        lines += ["", "## 📈 趋势摘要", "", "趋势数据可通过 `/rag/eval/trends` 接口获取。", ""]
        return "\n".join(lines)

    def _mt(self, cards: list[MetricCard], title: str) -> str:
        h = "| 指标名 | 得分 | 阈值 | 状态 | 变化 |\n|--------|------|------|------|------|"
        rows = [f"### {title}", "", h]
        for c in cards:
            e = _S.get("pass" if c.passed else "fail", "")
            d = f"{c.delta:+.2f}" if c.delta is not None else "—"
            rows.append(f"| {c.name} | {c.value:.2%} | {c.threshold:.2%} | {e} | {d} |")
        rows.append("")
        return "\n".join(rows)

    def _dx(self, sec) -> str:
        e = _S.get(sec.status, "")
        lines = [f"<details>", f"<summary>L{sec.layer}: {sec.name} {e}（{sec.score:.2%}）</summary>"]
        if sec.issues:
            lines += ["", "| 严重度 | 类别 | 描述 | 影响条目 | 建议 |",
                      "|--------|------|------|---------|------|"]
            for i in sec.issues:
                a = ", ".join(i.affected_items) if i.affected_items else "—"
                sg = (i.suggestion or "—")[:60]
                ev = _SE.get(i.severity, "skip")
                lines.append(f"| {_S.get(ev, '')} {i.severity} | {i.category} | {i.description[:80]} | {a[:40]} | {sg} |")
        else:
            lines.append("无问题")
        if sec.suggestions:
            lines += ["", "**建议：**"] + [f"- {s}" for s in sec.suggestions]
        lines += ["", "</details>", ""]
        return "\n".join(lines)

    def _bc(self, cases) -> str:
        if not cases:
            return "无坏案"
        h = "| 问题 | 领域 | 年龄 | 精确率 | 召回率 | 错误信息 |\n|------|------|------|--------|--------|----------|"
        rows = [h]
        for c in cases:
            p = f"{c.precision:.2%}" if c.precision is not None else "—"
            r = f"{c.recall:.2%}" if c.recall is not None else "—"
            err = (c.error_message or "—")[:60]
            age = f"{c.age:.1f}" if c.age is not None else "—"
            rows.append(f"| {c.query[:40]} | {c.domain or '—'} | {age} | {p} | {r} | {err} |")
        return "\n".join(rows)

    def _tu(self, e, idx: int) -> str:
        ev = _SE.get(e.severity, "skip")
        lines = [f"### {idx}. {_S.get(ev, '')} [{e.category}] {e.title}", "",
                 f"- **严重度**: {e.severity} | **类别**: {e.category}", f"- **描述**: {e.description}"]
        if e.current_value is not None: lines.append(f"- **当前值**: `{e.current_value}`")
        if e.suggested_value is not None: lines.append(f"- **建议值**: `{e.suggested_value}`")
        if e.expected_impact: lines.append(f"- **预期影响**: {e.expected_impact}")
        if e.conflict_with: lines.append(f"- ⚠️ 冲突: 建议 `{e.conflict_with}`")
        lines.append("")
        return "\n".join(lines)
