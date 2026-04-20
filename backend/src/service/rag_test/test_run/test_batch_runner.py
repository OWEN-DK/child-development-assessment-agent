import asyncio
import uuid
from datetime import datetime
from typing import Callable, List, Optional

from sqlalchemy import and_, desc, select

from src.config import config_manager
from src.core.database import db_session_factory
from src.core.distributed_lock import DistributedLock
from src.models.test_case import TestCase, TestRun, TestRunResult
from src.schemas import TestRunStatus
from src.schemas.task import TaskState, TaskStatus
from src.service.task_sse_publisher import TaskSsePublisher
from src.service.test_run_task_adapter import test_run_task_adapter
from src.utils.logger import logger


class TestBatchRunner:
    """测试批量运行器，负责运行所有测试和批量执行"""

    def __init__(self):
        self.db_session_factory = db_session_factory

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
            run_test_case_fn: 运行单个测试用例的函数（应为 execute_test_case）
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

        previous_run = await self._get_last_test_run_from_db()
        previous_config_version = (
            previous_run.config_version_id if previous_run else None
        )

        run_id = str(uuid.uuid4())
        test_run = TestRun(
            id=run_id,
            name=name or f"Test Run {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            description=description,
            total_test_cases=len(test_cases),
            status=TestRunStatus.PENDING,
            config_version_id=current_version,
            config_snapshot=config_snapshot,
            previous_config_version_id=previous_config_version,
        )

        # 立即保存到数据库
        async with self.db_session_factory() as session:
            session.add(test_run)
            await session.commit()

        # 创建统一任务状态（Redis）
        initial_state = TaskState.create(
            task_id=run_id,
            task_type="test_run",
            metadata={
                "name": test_run.name,
                "total_test_cases": len(test_cases),
            },
        )
        initial_state.message = "等待执行"
        await test_run_task_adapter.create(initial_state)

        # 更新状态为 running
        await test_run_task_adapter.update(
            run_id, {"status": TaskStatus.RUNNING, "message": "测试执行中"}
        )
        test_run.status = TestRunStatus.RUNNING

        passed_count = 0
        total_precision = 0.0
        total_recall = 0.0
        total_f1 = 0.0
        total_mrr = 0.0
        total_ndcg = 0.0
        test_count = 0

        for i, test_case in enumerate(test_cases):
            try:
                # 调用 execute_test_case 而非 run_test_case
                # execute_test_case 返回 TestRunResult（ORM）并保存到数据库
                result = await run_test_case_fn(run_id, test_case)

                # 累加指标
                total_precision += result.precision or 0.0
                total_recall += result.recall or 0.0
                total_f1 += result.f1 or 0.0
                total_mrr += result.mrr or 0.0
                total_ndcg += result.ndcg or 0.0

                if result.passed:
                    passed_count += 1

                test_count += 1

                # 更新进度
                progress = ((i + 1) / len(test_cases)) * 100
                await test_run_task_adapter.update(
                    run_id,
                    {
                        "progress": progress,
                        "message": f"已执行 {i + 1}/{len(test_cases)} 个用例",
                    }
                )

            except Exception as e:
                logger.error(f"Failed to run test case {test_case.id}: {e}")
                continue

        # 更新聚合指标
        if test_count > 0:
            test_run.overall_precision = total_precision / test_count
            test_run.overall_recall = total_recall / test_count
            test_run.overall_f1 = total_f1 / test_count
            test_run.overall_mrr = total_mrr / test_count
            test_run.overall_ndcg = total_ndcg / test_count

        test_run.passed_test_cases = passed_count
        test_run.status = TestRunStatus.COMPLETED
        test_run.completed_at = datetime.now()

        # 更新终态
        await test_run_task_adapter.update(
            run_id,
            {
                "status": TaskStatus.COMPLETED,
                "progress": 100.0,
                "message": "测试完成",
                "result": {
                    "total_test_cases": len(test_cases),
                    "passed_test_cases": passed_count,
                    "precision": test_run.overall_precision,
                    "recall": test_run.overall_recall,
                    "f1": test_run.overall_f1,
                }
            }
        )

        # 更新数据库中的聚合指标
        async with self.db_session_factory() as session:
            session.add(test_run)
            await session.commit()

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

            # 更新统一任务状态
            await test_run_task_adapter.update(
                run_id,
                {
                    "status": TaskStatus.COMPLETED,
                    "progress": 100.0,
                    "message": "测试完成",
                    "result": {
                        "total": total,
                        "passed": passed,
                        "precision": avg_precision,
                        "recall": avg_recall,
                        "f1": avg_f1,
                    }
                }
            )

            # 清理同步记录
            test_run_task_adapter.cleanup_sync_records(run_id)

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

            # 更新状态为 running
            await test_run_task_adapter.update(
                run_id, {"status": TaskStatus.RUNNING, "message": "批量测试执行中"}
            )

            semaphore = asyncio.Semaphore(concurrency)
            completed = 0
            total = len(test_cases)

            async def execute_single(test_case):
                nonlocal completed
                async with semaphore:
                    result = await execute_test_case_fn(
                        run_id, test_case, progress_callback
                    )
                    completed += 1
                    # 更新进度
                    progress = (completed / total) * 100 if total > 0 else 0
                    await test_run_task_adapter.update(
                        run_id,
                        {
                            "progress": progress,
                            "message": f"已执行 {completed}/{total} 个用例",
                        }
                    )
                    return result

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

    async def _get_last_test_run_from_db(self) -> Optional[TestRun]:
        """从数据库获取最后一个测试运行"""
        async with self.db_session_factory() as session:
            stmt = select(TestRun).order_by(desc(TestRun.created_at)).limit(1)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
