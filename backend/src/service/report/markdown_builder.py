"""Markdown报告构建器

负责生成Markdown格式的测试报告
"""

from datetime import datetime, timezone
from typing import Any, Dict, List


class MarkdownBuilder:
    """Markdown报告构建器"""

    def build(
        self,
        test_run,
        total_cases: int,
        metrics: Dict[str, float],
        domain_stats: Dict[str, Any],
        bad_cases: List,
    ) -> str:
        """生成Markdown格式报告"""
        content = self._build_header(test_run, total_cases)
        content += self._build_overall_metrics(metrics)
        content += self._build_domain_stats(domain_stats)
        content += self._build_bad_cases(bad_cases)
        return content

    def _build_header(self, test_run, total_cases: int) -> str:
        """构建报告头部"""
        return f"""# RAG测试报告

## 基本信息
- 测试运行ID: {test_run.id}
- 测试名称: {test_run.name or "未命名"}
- 执行时间: {test_run.completed_at or datetime.now(timezone.utc)}
- 总测试用例数: {total_cases}

"""

    def _build_overall_metrics(self, metrics: Dict[str, float]) -> str:
        """构建整体指标表格"""
        return f"""## 整体指标
| 指标 | 值 |
|------|----|
| 平均MRR | {metrics['avg_mrr']:.4f} |
| 平均NDCG | {metrics['avg_ndcg']:.4f} |
| 平均精确率(Precision) | {metrics['avg_precision']:.4f} |
| 平均召回率(Recall) | {metrics['avg_recall']:.4f} |
| 平均命中率@1 | {metrics['avg_hit_rate_1']:.4f} |
| 平均命中率@3 | {metrics['avg_hit_rate_3']:.4f} |
| 平均命中率@5 | {metrics['avg_hit_rate_5']:.4f} |

"""

    def _build_domain_stats(self, domain_stats: Dict[str, Any]) -> str:
        """构建分领域统计表格"""
        content = """## 分领域统计
| 领域 | 用例数 | 平均MRR | 平均NDCG | 平均Precision | 平均Recall |
|------|--------|---------|----------|---------------|------------|
"""
        for domain, stats in domain_stats.items():
            content += f"| {domain} | {stats['count']} | {stats['avg_mrr']:.4f} | {stats['avg_ndcg']:.4f} | {stats['avg_precision']:.4f} | {stats['avg_recall']:.4f} |\n"

        return content + "\n"

    def _build_bad_cases(self, bad_cases: List) -> str:
        """构建Bad Case列表"""
        content = f"""## Bad Case 列表
共 {len(bad_cases)} 个Bad Case（MRR < 0.3）

"""
        for idx, case in enumerate(bad_cases[:20]):
            content += f"{idx + 1}. 用例ID: {case.test_case_id}, 查询: {case.query}, MRR: {float(case.mrr):.4f}\n"

        return content
