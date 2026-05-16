"""评估报告导出器

支持三种导出格式：Markdown、JSON、CSV。
JSON 导出包含跨域数据，CSV 导出新增跨域指标摘要行。
"""
import csv
import io
import json
from typing import Any, Optional

from src.schemas.rag_eval.report import ReportRead
from src.utils.logger import logger


class ReportExporter:
    """评估报告导出器"""

    def export_markdown(self, report: ReportRead) -> str:
        """导出 Markdown 格式（直接返回已渲染的 Markdown 内容）"""
        return report.markdown_content or ""

    def export_json(self, report: ReportRead) -> str:
        """导出 JSON 格式（含跨域数据）"""
        data = {
            "report_id": report.id,
            "run_id": report.run_id,
            "overall_score": report.overall_score,
            "l1_score": report.l1_score,
            "l2_score": report.l2_score,
            "l3_score": report.l3_score,
            "cross_domain_score": report.cross_domain_score,
            "metrics": report.metrics_json,
            "diagnosis": report.diagnosis_json,
            "bad_cases": report.bad_cases_json,
            "suggestions": report.suggestions_json,
            "cross_domain": report.cross_domain_json,
            "status": report.status,
            "created_at": report.created_at.isoformat() if report.created_at else None,
        }
        return json.dumps(data, ensure_ascii=False, indent=2, default=str)

    def export_csv(self, report: ReportRead) -> str:
        """导出 CSV 格式（指标摘要 + 跨域摘要行）

        CSV 结构：
        - 头行：指标名
        - 值行：各指标的值
        """
        output = io.StringIO()
        writer = csv.writer(output)

        # 总体
        writer.writerow(["指标", "值"])
        writer.writerow(["overall_score", report.overall_score])
        writer.writerow(["l1_score", report.l1_score])
        writer.writerow(["l2_score", report.l2_score])
        writer.writerow(["l3_score", report.l3_score])
        writer.writerow(["cross_domain_score", report.cross_domain_score])
        writer.writerow([])

        # 详细指标
        metrics = report.metrics_json or {}
        for layer_key in ["l1", "l2", "l3"]:
            layer = metrics.get(layer_key, {})
            if not layer:
                continue
            writer.writerow([f"{layer_key.upper()} 指标"])
            scores = layer.get("scores", [])
            if isinstance(scores, list):
                writer.writerow(["指标名", "分数", "通过"])
                for s in scores:
                    if isinstance(s, dict):
                        writer.writerow([
                            s.get("display_name", s.get("name", "")),
                            s.get("score", 0),
                            "Y" if s.get("passed") else "N",
                        ])
            writer.writerow([])

        # 跨域指标
        cross = report.cross_domain_json or {}
        if cross:
            writer.writerow(["跨域指标"])
            writer.writerow(["域激活准确率", cross.get("overall_activation_accuracy", 0)])
            writer.writerow(["跨域覆盖率", cross.get("overall_cross_coverage", 0)])
            writer.writerow(["冲突检测率", cross.get("overall_conflict_detection_rate", 0)])
            latency = cross.get("e2e_latency_distribution", {})
            writer.writerow(["P50延迟(ms)", latency.get("p50_ms", 0)])
            writer.writerow(["P95延迟(ms)", latency.get("p95_ms", 0)])
            writer.writerow(["P99延迟(ms)", latency.get("p99_ms", 0)])

        return output.getvalue()
