"""报告导出器——支持 JSON/CSV/Markdown 多格式导出"""

import csv
import io
import json

from src.schemas.rag_eval.report import EvalReportRead
from src.utils.exceptions import AppException


class ReportExporter:
    """报告导出为多种格式

    支持格式：JSON / CSV / Markdown
    PDF 为可选格式（需 weasyprint 等依赖库）
    """

    async def export_json(self, report: EvalReportRead) -> bytes:
        """导出为 JSON 格式"""
        data = report.model_dump(mode="json")
        return json.dumps(data, ensure_ascii=False, indent=2, default=str).encode("utf-8")

    async def export_csv(self, report: EvalReportRead) -> bytes:
        """导出为 CSV 格式

        输出两张表：
        1. 指标表：三层指标卡片的 CSV
        2. 坏案表：坏案条目的 CSV
        """
        output = io.StringIO()
        writer = csv.writer(output)

        # 表1：指标卡片
        writer.writerow(["=== 三层指标看板 ==="])
        writer.writerow(["层级", "指标名", "得分", "状态", "阈值", "变化"])

        for layer_label, cards in [
            ("L1 检索质量", report.scoring_dashboard.l1),
            ("L2 生成质量", report.scoring_dashboard.l2),
            ("L3 系统质量", report.scoring_dashboard.l3),
        ]:
            for card in cards:
                status = "通过" if card.passed else "未通过"
                delta_str = f"{card.delta:+.4f}" if card.delta is not None else "—"
                writer.writerow([layer_label, card.name, f"{card.value:.4f}", status, f"{card.threshold:.4f}", delta_str])

        writer.writerow([])
        writer.writerow(["=== 坏案分析 ==="])
        writer.writerow(["问题", "领域", "年龄", "精确率", "召回率", "错误信息"])

        for c in report.bad_cases:
            writer.writerow([
                c.query,
                c.domain or "",
                c.age if c.age is not None else "",
                f"{c.precision:.4f}" if c.precision is not None else "",
                f"{c.recall:.4f}" if c.recall is not None else "",
                c.error_message or "",
            ])

        return output.getvalue().encode("utf-8")

    async def export_markdown(self, report: EvalReportRead) -> bytes:
        """导出为 Markdown 格式（直接使用 markdown_content）"""
        content = report.markdown_content or ""
        return content.encode("utf-8")

    async def export_pdf(self, report: EvalReportRead) -> bytes:
        """导出为 PDF 格式

        Markdown → HTML → PDF（可选依赖：weasyprint）
        若 PDF 依赖库不可用，抛 AppException
        """
        try:
            import markdown
            from weasyprint import HTML
        except ImportError:
            raise AppException(
                status_code=500,
                code=13006,
                message="PDF 导出需要 weasyprint 依赖库，请安装后重试",
                error_code="REPORT_EXPORT_FAILED",
            )

        markdown_content = report.markdown_content or ""
        html_body = markdown.markdown(
            markdown_content,
            extensions=["tables", "fenced_code"],
        )

        html_doc = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>body {{ font-family: sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; }}
table {{ border-collapse: collapse; width: 100%; }} th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
th {{ background-color: #f2f2f2; }}</style></head>
<body>{html_body}</body></html>"""

        pdf_bytes = HTML(string=html_doc).write_pdf()
        return pdf_bytes
