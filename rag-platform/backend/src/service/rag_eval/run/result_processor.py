"""评估结果后处理器

聚合所有用例执行结果，计算整体指标，更新运行记录。
支持跨域指标聚合、分层指标汇总和域贡献度统计。
"""
from typing import Any

from src.models.rag_eval.test_run import TestRun, TestRunResult
from src.repository.rag_eval.test_run_repo import (
    TestRunRepository,
    TestRunResultRepository,
)
from src.utils.logger import logger


class ResultProcessor:
    """评估结果后处理器

    在所有用例执行完成后调用，聚合结果并计算宏观指标：
    - L1 检索指标汇总（avg precision/recall/F1/MRR/NDCG）
    - 跨域聚合统计（各域激活次数、贡献度均值）
    - 延迟分布（P50/P95/P99/avg）
    - 通过率统计
    """

    def __init__(
        self,
        run_repo: TestRunRepository,
        result_repo: TestRunResultRepository,
    ):
        self._run_repo = run_repo
        self._result_repo = result_repo

    async def process(self, run: TestRun) -> dict[str, Any]:
        """处理运行结果，计算汇总指标并更新运行记录

        Returns:
            汇总指标字典，供后续指标计算和报告生成使用
        """
        results = await self._result_repo.list_results(run.id)

        if not results:
            return {}

        # 分离正常结果和错误结果
        valid_results = [r for r in results if r.error_message is None]

        # 汇总 L1 指标
        l1_summary = self._aggregate_l1_metrics(valid_results)

        # 汇总跨域结果
        cross_domain = self._aggregate_cross_domain_results(results)

        # 延迟分布
        latency = self._compute_latency_distribution(results)

        # 通过统计
        total = len(results)
        passed = sum(1 for r in results if r.passed == 1)
        failed = sum(1 for r in results if r.passed == 0)
        errors = sum(1 for r in results if r.error_message is not None)

        summary = {
            "total_cases": total,
            "passed_cases": passed,
            "failed_cases": failed,
            "error_cases": errors,
            "pass_rate": round(passed / total, 4) if total > 0 else 0.0,
            "l1_metrics": l1_summary,
            "cross_domain": cross_domain,
            "latency": latency,
        }

        # 更新运行记录
        await self._run_repo.update(run.id, {
            "l1_metrics_json": l1_summary,
            "cross_domain_metrics_json": cross_domain,
            "passed_test_cases": passed,
        }, run.tenant_id)

        logger.info(
            f"运行 {run.id} 结果处理完成: {passed}/{total} 通过, "
            f"avg_precision={l1_summary.get('avg_precision', 0):.3f}"
        )

        return summary

    def _aggregate_l1_metrics(self, results: list[TestRunResult]) -> dict[str, Any]:
        """汇总 L1 检索层指标

        计算所有有效结果的平均 precision/recall/F1/MRR/NDCG。
        跳过 N/A 结果（无 expected_knowledge_ids 的用例）。
        """
        if not results:
            return {}

        metrics = {
            "precision": [],
            "recall": [],
            "f1": [],
            "mrr": [],
            "ndcg": [],
        }

        for r in results:
            if r.precision is not None:
                metrics["precision"].append(float(r.precision))
            if r.recall is not None:
                metrics["recall"].append(float(r.recall))
            if r.f1 is not None:
                metrics["f1"].append(float(r.f1))
            if r.mrr is not None:
                metrics["mrr"].append(float(r.mrr))
            if r.ndcg is not None:
                metrics["ndcg"].append(float(r.ndcg))

        def _avg(vals: list[float]) -> float:
            return round(sum(vals) / len(vals), 4) if vals else 0.0

        return {
            "avg_precision": _avg(metrics["precision"]),
            "avg_recall": _avg(metrics["recall"]),
            "avg_f1": _avg(metrics["f1"]),
            "avg_mrr": _avg(metrics["mrr"]),
            "avg_ndcg": _avg(metrics["ndcg"]),
            "valid_count": len(results),
        }

    def _aggregate_cross_domain_results(
        self, results: list[TestRunResult]
    ) -> dict[str, Any]:
        """从所有用例的 domain_results_json 聚合跨域统计

        按域汇总：
        - 激活次数 / 贡献度均值
        - 域对冲突统计
        """
        domain_stats: dict[str, dict[str, Any]] = {}
        total_cases = len(results)

        for r in results:
            domain_json = r.domain_results_json or {}
            for domain_id, info in domain_json.items():
                if domain_id not in domain_stats:
                    domain_stats[domain_id] = {
                        "activated_count": 0,
                        "total_contribution": 0.0,
                        "hit_count": 0,
                        "top_chunks_count": 0,
                    }
                stats = domain_stats[domain_id]
                if info.get("activated"):
                    stats["activated_count"] += 1
                stats["total_contribution"] += info.get("contribution", 0.0)
                stats["hit_count"] += info.get("hit_count", 0)
                stats["top_chunks_count"] += len(info.get("top_chunks", []))

        # 转换格式
        domain_contributions = []
        for domain_id, stats in domain_stats.items():
            domain_contributions.append({
                "domain_id": domain_id,
                "activated_count": stats["activated_count"],
                "activation_accuracy": round(
                    stats["activated_count"] / total_cases, 4
                ) if total_cases > 0 else 0.0,
                "avg_contribution": round(
                    stats["total_contribution"] / total_cases, 4
                ) if total_cases > 0 else 0.0,
                "total_hits": stats["hit_count"],
            })

        return {
            "domain_contributions": domain_contributions,
            "total_domains": len(domain_stats),
            "total_cases": total_cases,
        }

    def _compute_latency_distribution(
        self, results: list[TestRunResult]
    ) -> dict[str, Any]:
        """计算端到端延迟分布

        从所有执行时间中计算 P50/P95/P99/avg。
        """
        times = [
            r.execution_time_ms
            for r in results
            if r.execution_time_ms is not None
        ]
        if not times:
            return {"p50": 0, "p95": 0, "p99": 0, "avg": 0, "count": 0}

        sorted_times = sorted(times)
        n = len(sorted_times)

        def _percentile(p: float) -> int:
            idx = int(n * p / 100)
            return sorted_times[min(idx, n - 1)]

        return {
            "p50_ms": _percentile(50),
            "p95_ms": _percentile(95),
            "p99_ms": _percentile(99),
            "avg_ms": round(sum(times) / n),
            "min_ms": sorted_times[0],
            "max_ms": sorted_times[-1],
            "count": n,
        }
