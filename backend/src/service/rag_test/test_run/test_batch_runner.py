import asyncio
import json
import os
import uuid
from datetime import datetime
from typing import Callable, List, Optional

from sqlalchemy import and_, select

from src.config import config_manager
from src.core.database import db_session_factory
from src.core.distributed_lock import DistributedLock
from src.models.test_case import TestCase, TestRun, TestRunResult
from src.schemas import TestRunStatus
from src.utils.logger import logger


class TestBatchRunner:
    """测试批量运行器，负责运行所有测试和批量执行"""

    def __init__(self):
        self.db_session_factory = db_session_factory
        self.test_runs_dir = f"{__import__('src.config', fromlist=['settings']).settings.rag_storage_dir}/test_runs"
        os.makedirs(self.test_runs_dir, exist_ok=True)

    async def run_all_tests(
        self,
        run_test_case_fn,
        name: str = "",
        description: str = "",
        limit: int = 10,
    ) -> TestRun:
        """
        运行所有测试用例
        
        Args:
            run_test_case_fn: 运行单个测试用例的函数
            name: 测试运行名称
            description: 描述
            limit: 检索数量限制
            
        Returns:
            测试运行对象
        """
        from src.service.rag_test.test_case_service import test_case_service

        test_cases = await test_case_service.list()
        if not test_cases:
            raise ValueError("No test cases available")

        current_version = config_manager.get_active_version()
        config_snapshot = config_manager.get_full_config()

        previous_run = await self._get_last_test_run()
        previous_config_version = (
            previous_run.config_version_id if previous_run else None
        )

        test_run = TestRun(
            id=str(uuid.uuid4()),
            name=name or f"Test Run {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            description=description,
            total_test_cases=len(test_cases),
            status=TestRunStatus.RUNNING,
            config_version_id=current_version,
            config_snapshot=config_snapshot,
            previous_config_version_id=previous_config_version,
        )

        test_results = []
        passed_count = 0
        total_precision = 0.0
        total_recall = 0.0
        total_f1 = 0.0
        total_mrr = 0.0
        total_ndcg = 0.0

        for test_case in test_cases:
            try:
                result = await run_test_case_fn(test_case, limit)
                test_results.append(result)

                total_precision += result.precision
                total_recall += result.recall
                total_f1 += result.f1_score
                total_mrr += result.mrr
                total_ndcg += result.ndcg_at_k

                if result.f1_score >= 0.7:
                    passed_count += 1

            except Exception as e:
                logger.error(f"Failed to run test case {test_case.id}: {e}")
                continue

        test_count = len(test_results)
        if test_count > 0:
            test_run.overall_precision = total_precision / test_count
            test_run.overall_recall = total_recall / test_count
            test_run.overall_f1 = total_f1 / test_count
            test_run.overall_mrr = total_mrr / test_count
            test_run.overall_ndcg = total_ndcg / test_count

        test_run.test_results = test_results
        test_run.passed_test_cases = passed_count
        test_run.status = TestRunStatus.COMPLETED
        test_run.completed_at = datetime.now()

        self._save_test_run(test_run)

        return test_run

    async def complete_test_run(self, run_id: str):
        """
        完成测试运行，计算聚合指标
        
        Args:
            run_id: 测试运行ID
        """
        async with self.db_session_factory() as session:
            stmt = select(TestRunResult).where(TestRunResult.run_id == run_id)
            result = await session.execute(stmt)
            test_results = result.scalars().all()

            total = len(test_results)
            passed = sum(1 for r in test_results if r.passed)

            avg_precision = (
                sum(r.precision for r in test_results if r.precision is not None)
                / total
                if total > 0
                else 0.0
            )
            avg_recall = (
                sum(r.recall for r in test_results if r.recall is not None) / total
                if total > 0
                else 0.0
            )
            avg_f1 = (
                sum(r.f1 for r in test_results if r.f1 is not None) / total
                if total > 0
                else 0.0
            )

            stmt = select(TestRun).where(TestRun.id == run_id)
            result = await session.execute(stmt)
            test_run = result.scalar_one()

            test_run.status = TestRunStatus.COMPLETED
            test_run.completed_at = datetime.now()
            test_run.passed_test_cases = passed
            test_run.overall_precision = avg_precision
            test_run.overall_recall = avg_recall
            test_run.overall_f1 = avg_f1

            await session.commit()

            logger.info(
                f"测试运行已完成：{run_id}, 通过率={passed}/{total}={passed / total:.2%}"
            )

    async def execute_batch(
        self,
        run_id: str,
        execute_test_case_fn,
        concurrency: int = 5,
        progress_callback: Optional[Callable] = None,
    ) -> list:
        """
        批量执行测试用例
        
        Args:
            run_id: 测试运行ID
            execute_test_case_fn: 执行单个测试用例的函数
            concurrency: 并发数
            progress_callback: 进度回调函数
            
        Returns:
            测试结果列表
        """
        lock_name = f"rag:test_run:{run_id}"

        async def _execute_with_lock():
            async with self.db_session_factory() as session:
                stmt = select(TestRun).where(TestRun.id == run_id)
                result = await session.execute(stmt)
                test_run = result.scalar_one()

                stmt = (
                    select(TestCase)
                    .outerjoin(
                        TestRunResult,
                        and_(
                            TestCase.id == TestRunResult.test_case_id,
                            TestRunResult.run_id == run_id,
                        ),
                    )
                    .where(TestRunResult.id.is_(None))
                )
                result = await session.execute(stmt)
                test_cases = result.scalars().all()

            semaphore = asyncio.Semaphore(concurrency)

            async def execute_single(test_case):
                async with semaphore:
                    return await execute_test_case_fn(
                        run_id, test_case, progress_callback
                    )

            tasks = [execute_single(tc) for tc in test_cases]
            results = await asyncio.gather(*tasks)

            await self.complete_test_run(run_id)

            return results

        results = await DistributedLock.execute_with_lock(
            lock_name,
            _execute_with_lock,
            timeout=3600,
        )

        return results

    def _save_test_run(self, test_run: TestRun):
        """保存测试运行到文件"""
        try:
            file_path = os.path.join(self.test_runs_dir, f"{test_run.id}.json")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(test_run.model_dump_json(indent=2))
            logger.info(f"Test run saved to {file_path}")
        except Exception as e:
            logger.error(f"Failed to save test run: {e}")

    async def _get_last_test_run(self) -> Optional[TestRun]:
        """获取最后一个测试运行"""
        runs = self._list_test_runs_from_files()
        if runs:
            return runs[0]
        return None

    def _list_test_runs_from_files(self) -> List[TestRun]:
        """从文件列表获取测试运行"""
        test_runs = []
        try:
            for filename in os.listdir(self.test_runs_dir):
                if filename.endswith(".json"):
                    file_path = os.path.join(self.test_runs_dir, filename)
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        test_runs.append(TestRun(**data))
            test_runs.sort(key=lambda x: x.created_at, reverse=True)
        except Exception as e:
            logger.error(f"Failed to list test runs: {e}")
        return test_runs
