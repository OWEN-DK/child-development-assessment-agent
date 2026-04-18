from typing import Dict, List, Optional

from sqlalchemy import select

from src.config import config_manager
from src.core.database import db_session_factory
from src.models.test_case import TestCase, TestRun, TestRunResult
from src.schemas import TestRunStatus
from src.utils.logger import logger


class TestResultAnalyzer:
    """测试结果分析器，负责分析和比较测试运行结果"""

    def __init__(self):
        self.db_session_factory = db_session_factory

    async def analyze_test_run(self, run_id: str) -> dict:
        """
        分析测试运行结果
        
        Args:
            run_id: 测试运行ID
            
        Returns:
            分析结果字典
        """
        async with self.db_session_factory() as session:
            stmt = select(TestRun).where(TestRun.id == run_id)
            result = await session.execute(stmt)
            test_run = result.scalar_one()

            stmt = select(TestRunResult).where(TestRunResult.run_id == run_id)
            result = await session.execute(stmt)
            test_results = result.scalars().all()

            domain_stats = {}
            for test_result in test_results:
                test_case = await session.get(TestCase, test_result.test_case_id)
                domain = test_case.domain.value

                if domain not in domain_stats:
                    domain_stats[domain] = {
                        "total": 0,
                        "passed": 0,
                        "precision_sum": 0.0,
                        "recall_sum": 0.0,
                    }

                domain_stats[domain]["total"] += 1
                if test_result.passed:
                    domain_stats[domain]["passed"] += 1
                if test_result.precision:
                    domain_stats[domain]["precision_sum"] += test_result.precision
                if test_result.recall:
                    domain_stats[domain]["recall_sum"] += test_result.recall

            for domain in domain_stats:
                total = domain_stats[domain]["total"]
                domain_stats[domain]["avg_precision"] = (
                    domain_stats[domain]["precision_sum"] / total
                )
                domain_stats[domain]["avg_recall"] = (
                    domain_stats[domain]["recall_sum"] / total
                )
                domain_stats[domain]["pass_rate"] = (
                    domain_stats[domain]["passed"] / total
                )

            return {
                "run_id": run_id,
                "name": test_run.name,
                "status": test_run.status,
                "total": test_run.total_test_cases,
                "passed": test_run.passed_test_cases,
                "overall_precision": test_run.overall_precision,
                "overall_recall": test_run.overall_recall,
                "overall_f1": test_run.overall_f1,
                "domain_stats": domain_stats,
            }

    async def compare_test_runs(self, run_id_1: str, run_id_2: str) -> dict:
        """
        比较两个测试运行
        
        Args:
            run_id_1: 第一个测试运行ID
            run_id_2: 第二个测试运行ID
            
        Returns:
            比较结果字典
        """
        stats_1 = await self.analyze_test_run(run_id_1)
        stats_2 = await self.analyze_test_run(run_id_2)

        return {
            "run_1": stats_1,
            "run_2": stats_2,
            "comparison": {
                "precision_diff": stats_2["overall_precision"]
                - stats_1["overall_precision"],
                "recall_diff": stats_2["overall_recall"] - stats_1["overall_recall"],
                "f1_diff": stats_2["overall_f1"] - stats_1["overall_f1"],
                "pass_rate_diff": (stats_2["passed"] / stats_2["total"])
                - (stats_1["passed"] / stats_1["total"]),
            },
        }

    async def recalculate_aggregate_scores(self):
        """重算所有已完成测试运行的聚合评分"""
        async with self.db_session_factory() as session:
            stmt = select(TestRun).where(TestRun.status == TestRunStatus.COMPLETED)
            result = await session.execute(stmt)
            runs = result.scalars().all()

            for run in runs:
                results_stmt = select(TestRunResult).where(
                    TestRunResult.run_id == run.id
                )
                results_result = await session.execute(results_stmt)
                results = results_result.scalars().all()

                if not results:
                    continue

                total = len(results)
                passed = sum(1 for r in results if r.passed)
                run.passed_test_cases = passed
                run.overall_precision = (
                    sum(r.precision for r in results if r.precision) / total
                )
                run.overall_recall = sum(r.recall for r in results if r.recall) / total
                run.overall_f1 = sum(r.f1 for r in results if r.f1) / total

            await session.commit()
            logger.info(f"聚合评分已重算：{len(runs)} 个运行")

    def compare_config_versions(self, version_id1: str, version_id2: str) -> Dict:
        """
        比较两个配置版本的测试表现
        
        Args:
            version_id1: 第一个配置版本ID
            version_id2: 第二个配置版本ID
            
        Returns:
            比较结果字典
            
        Raises:
            ValueError: 如果找不到对应版本的测试运行
        """
        runs = self._list_test_runs_from_files()
        runs_for_v1 = [r for r in runs if r.config_version_id == version_id1]
        runs_for_v2 = [r for r in runs if r.config_version_id == version_id2]

        if not runs_for_v1:
            raise ValueError(f"No test runs found for config version {version_id1}")
        if not runs_for_v2:
            raise ValueError(f"No test runs found for config version {version_id2}")

        avg_v1_precision = sum(r.overall_precision for r in runs_for_v1) / len(
            runs_for_v1
        )
        avg_v1_recall = sum(r.overall_recall for r in runs_for_v1) / len(runs_for_v1)
        avg_v1_f1 = sum(r.overall_f1 for r in runs_for_v1) / len(runs_for_v1)
        avg_v1_mrr = sum(r.overall_mrr for r in runs_for_v1) / len(runs_for_v1)

        avg_v2_precision = sum(r.overall_precision for r in runs_for_v2) / len(
            runs_for_v2
        )
        avg_v2_recall = sum(r.overall_recall for r in runs_for_v2) / len(runs_for_v2)
        avg_v2_f1 = sum(r.overall_f1 for r in runs_for_v2) / len(runs_for_v2)
        avg_v2_mrr = sum(r.overall_mrr for r in runs_for_v2) / len(runs_for_v2)

        return {
            "version1": {
                "version_id": version_id1,
                "run_count": len(runs_for_v1),
                "avg_precision": avg_v1_precision,
                "avg_recall": avg_v1_recall,
                "avg_f1": avg_v1_f1,
                "avg_mrr": avg_v1_mrr,
            },
            "version2": {
                "version_id": version_id2,
                "run_count": len(runs_for_v2),
                "avg_precision": avg_v2_precision,
                "avg_recall": avg_v2_recall,
                "avg_f1": avg_v2_f1,
                "avg_mrr": avg_v2_mrr,
            },
            "differences": {
                "precision_change": avg_v2_precision - avg_v1_precision,
                "recall_change": avg_v2_recall - avg_v1_recall,
                "f1_change": avg_v2_f1 - avg_v1_f1,
                "mrr_change": avg_v2_mrr - avg_v1_mrr,
            },
        }

    def _list_test_runs_from_files(self) -> List[TestRun]:
        """从文件列表获取测试运行"""
        import json
        import os

        test_runs = []
        try:
            test_runs_dir = f"{__import__('src.config', fromlist=['settings']).settings.rag_storage_dir}/test_runs"
            for filename in os.listdir(test_runs_dir):
                if filename.endswith(".json"):
                    file_path = os.path.join(test_runs_dir, filename)
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        test_runs.append(TestRun(**data))
            test_runs.sort(key=lambda x: x.created_at, reverse=True)
        except Exception as e:
            logger.error(f"Failed to list test runs: {e}")
        return test_runs
