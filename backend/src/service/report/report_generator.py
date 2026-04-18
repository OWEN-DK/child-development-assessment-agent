"""报告生成器

负责生成测试报告，包含分布式锁和指标计算逻辑
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from sqlalchemy import update

from src.config import settings
from src.core.database import db_session_factory
from src.core.redis_client import RedisClient
from src.repository.test_case_repository import (TestRunRepository,
                                                  TestRunResultRepository)
from src.utils.logger import logger

from .markdown_builder import MarkdownBuilder


class ReportGenerator:
    """报告生成器"""

    def __init__(self):
        self.test_run_repo = TestRunRepository(db_session_factory)
        self.test_run_result_repo = TestRunResultRepository(db_session_factory)
        self.redis_client = RedisClient.get_client()
        self.report_dir = (
            Path(getattr(settings, "rag_storage_dir", "./app_data/rag_storage"))
            / "reports"
        )
        self.report_dir.mkdir(parents=True, exist_ok=True)
        self.markdown_builder = MarkdownBuilder()

    async def generate(self, run_id: str) -> dict:
        """生成测试报告（带分布式锁防止并发生成）"""
        lock_key = f"report:generate:{run_id}"

        try:
            # 获取分布式锁
            acquired = await self.redis_client.set(lock_key, "1", nx=True, ex=60)
            if not acquired:
                raise RuntimeError(f"报告 {run_id} 正在生成中，请勿重复提交")

            async with db_session_factory() as session:
                # 获取测试运行
                test_run = await self.test_run_repo.get_by_id(run_id)
                if not test_run:
                    raise ValueError(f"测试运行 {run_id} 不存在")

                # 获取所有结果
                results = await self.test_run_result_repo.get_by_run_id(run_id)
                if not results:
                    raise ValueError(f"测试运行 {run_id} 无结果数据")

                # 计算指标
                total_cases = len(results)
                metrics = self._calculate_overall_metrics(results)
                domain_stats = self._calculate_domain_stats(results)
                bad_cases = self._find_bad_cases(results)

                # 生成Markdown报告
                content = self.markdown_builder.build(
                    test_run=test_run,
                    total_cases=total_cases,
                    metrics=metrics,
                    domain_stats=domain_stats,
                    bad_cases=bad_cases,
                )

                # 保存报告文件
                report_path = self._save_report_file(run_id, content)

                # 更新数据库记录
                await self._update_database(session, test_run, report_path)

                return {
                    "run_id": run_id,
                    "content": content,
                    "storage_path": str(report_path),
                    "overall_metrics": metrics,
                    "domain_stats": domain_stats,
                    "bad_case_count": len(bad_cases),
                }

        finally:
            try:
                await self.redis_client.delete(lock_key)
            except Exception:
                pass

    def _calculate_overall_metrics(self, results: List) -> Dict[str, float]:
        """计算整体指标"""
        mrr_values = [float(r.mrr) for r in results if r.mrr is not None]
        avg_mrr = sum(mrr_values) / len(mrr_values) if mrr_values else 0.0

        ndcg_values = [float(r.ndcg) for r in results if r.ndcg is not None]
        avg_ndcg = sum(ndcg_values) / len(ndcg_values) if ndcg_values else 0.0

        precision_values = [
            float(r.precision) for r in results if r.precision is not None
        ]
        avg_precision = (
            sum(precision_values) / len(precision_values)
            if precision_values
            else 0.0
        )

        recall_values = [
            float(r.recall) for r in results if r.recall is not None
        ]
        avg_recall = (
            sum(recall_values) / len(recall_values) if recall_values else 0.0
        )

        hit_rate_1_values = [
            float(r.hit_rate_1) for r in results if r.hit_rate_1 is not None
        ]
        avg_hit_rate_1 = (
            sum(hit_rate_1_values) / len(hit_rate_1_values)
            if hit_rate_1_values
            else 0.0
        )

        hit_rate_3_values = [
            float(r.hit_rate_3) for r in results if r.hit_rate_3 is not None
        ]
        avg_hit_rate_3 = (
            sum(hit_rate_3_values) / len(hit_rate_3_values)
            if hit_rate_3_values
            else 0.0
        )

        hit_rate_5_values = [
            float(r.hit_rate_5) for r in results if r.hit_rate_5 is not None
        ]
        avg_hit_rate_5 = (
            sum(hit_rate_5_values) / len(hit_rate_5_values)
            if hit_rate_5_values
            else 0.0
        )

        return {
            "avg_mrr": avg_mrr,
            "avg_ndcg": avg_ndcg,
            "avg_precision": avg_precision,
            "avg_recall": avg_recall,
            "avg_hit_rate_1": avg_hit_rate_1,
            "avg_hit_rate_3": avg_hit_rate_3,
            "avg_hit_rate_5": avg_hit_rate_5,
        }

    def _calculate_domain_stats(self, results: List) -> Dict[str, Any]:
        """按领域统计指标"""
        domain_stats = {}
        for result in results:
            domain = getattr(result, "domain", "未知")

            if domain not in domain_stats:
                domain_stats[domain] = {
                    "count": 0,
                    "total_mrr": 0.0,
                    "total_ndcg": 0.0,
                    "ndcg_count": 0,
                    "total_precision": 0.0,
                    "precision_count": 0,
                    "total_recall": 0.0,
                    "recall_count": 0,
                }

            stats = domain_stats[domain]
            stats["count"] += 1

            if result.mrr is not None:
                stats["total_mrr"] += float(result.mrr)
            if result.ndcg is not None:
                stats["total_ndcg"] += float(result.ndcg)
                stats["ndcg_count"] += 1
            if result.precision is not None:
                stats["total_precision"] += float(result.precision)
                stats["precision_count"] += 1
            if result.recall is not None:
                stats["total_recall"] += float(result.recall)
                stats["recall_count"] += 1

        # 计算平均值
        for domain in domain_stats:
            stats = domain_stats[domain]
            stats["avg_mrr"] = (
                stats["total_mrr"] / stats["count"]
                if stats["count"] > 0
                else 0.0
            )
            stats["avg_ndcg"] = (
                stats["total_ndcg"] / stats["ndcg_count"]
                if stats["ndcg_count"] > 0
                else 0.0
            )
            stats["avg_precision"] = (
                stats["total_precision"] / stats["precision_count"]
                if stats["precision_count"] > 0
                else 0.0
            )
            stats["avg_recall"] = (
                stats["total_recall"] / stats["recall_count"]
                if stats["recall_count"] > 0
                else 0.0
            )

        return domain_stats

    def _find_bad_cases(self, results: List) -> List:
        """找出Bad Case（MRR < 0.3）"""
        return [
            r for r in results if r.mrr is not None and float(r.mrr) < 0.3
        ]

    def _save_report_file(self, run_id: str, content: str) -> Path:
        """保存报告文件"""
        date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        report_path = (
            self.report_dir
            / date_str
            / f"run_{run_id}_{datetime.now(timezone.utc).strftime('%H%M%S')}.md"
        )
        report_path.parent.mkdir(parents=True, exist_ok=True)

        with open(report_path, "w", encoding="utf-8") as f:
            f.write(content)

        return report_path

    async def _update_database(self, session, test_run, report_path: Path):
        """更新数据库记录"""
        stmt = (
            update(test_run.__class__)
            .where(test_run.__class__.id == test_run.id)
            .values(report_storage_path=str(report_path))
        )
        await session.execute(stmt)
        await session.commit()
