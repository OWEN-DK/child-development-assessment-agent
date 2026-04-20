from typing import Callable, Dict, List, Optional

from sqlalchemy import select

from src.core.database import db_session_factory
from src.models.test_case import TestCase, TestRun, TestRunResult
from src.repository.test_case_repository import TestRunRepository
from src.schemas import TestResult, TestRunStatus


class TestRunService:
    """
    测试运行服务门面类
    协调所有子服务，保持对外API完全兼容
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TestRunService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.creator = TestRunCreator()
        self.executor = TestExecutor()
        self.batch_runner = TestBatchRunner()
        self.analyzer = TestResultAnalyzer()
        self.repo = TestRunRepository(db_session_factory)

        self._initialized = True

    async def create_test_run(
        self,
        name: str,
        description: str = None,
        test_case_ids: list[str] = None,
        test_set_id: str = None,
    ) -> str:
        """创建测试运行"""
        return await self.creator.create_test_run(
            name=name,
            description=description,
            test_case_ids=test_case_ids,
            test_set_id=test_set_id,
        )

    async def execute_test_case(
        self,
        run_id: str,
        test_case: TestCase,
        progress_callback: Optional[Callable] = None,
    ):
        """执行单个测试用例"""
        return await self.executor.execute_test_case(
            run_id=run_id,
            test_case=test_case,
            progress_callback=progress_callback,
        )

    async def run_test_case(self, test_case: TestCase, limit: int = 10) -> TestResult:
        """运行单个测试用例并返回详细结果"""
        return await self.executor.run_test_case(
            test_case=test_case,
            limit=limit,
        )

    async def run_all_tests(
        self, name: str = "", description: str = "", limit: int = 10
    ):
        """运行所有测试用例"""
        return await self.batch_runner.run_all_tests(
            run_test_case_fn=self.executor.execute_test_case,
            name=name,
            description=description,
            limit=limit,
        )

    async def complete_test_run(self, run_id: str):
        """完成测试运行"""
        return await self.batch_runner.complete_test_run(run_id=run_id)

    async def execute_batch(
        self,
        run_id: str,
        concurrency: int = 5,
        progress_callback: Optional[Callable] = None,
    ) -> list:
        """批量执行测试用例"""
        return await self.batch_runner.execute_batch(
            run_id=run_id,
            execute_test_case_fn=self.executor.execute_test_case,
            concurrency=concurrency,
            progress_callback=progress_callback,
        )

    async def analyze_test_run(self, run_id: str) -> dict:
        """分析测试运行结果"""
        return await self.analyzer.analyze_test_run(run_id=run_id)

    async def compare_test_runs(self, run_id_1: str, run_id_2: str) -> dict:
        """比较两个测试运行"""
        return await self.analyzer.compare_test_runs(
            run_id_1=run_id_1,
            run_id_2=run_id_2,
        )

    async def recalculate_aggregate_scores(self):
        """重算所有已完成测试运行的聚合评分"""
        return await self.analyzer.recalculate_aggregate_scores()

    async def list_test_runs(self) -> List[TestRun]:
        """列出所有测试运行（返回 ORM 对象）"""
        return await self.repo.get_latest_runs(limit=50)

    async def get_test_run(self, run_id: str) -> Optional[dict]:
        """获取指定测试运行（包含 test_results 关联查询，返回字典）"""
        async with db_session_factory() as session:
            # 获取 TestRun
            stmt = select(TestRun).where(TestRun.id == run_id)
            result = await session.execute(stmt)
            test_run = result.scalar_one_or_none()
            
            if not test_run:
                return None
            
            # 关联查询 TestRunResult
            stmt = select(TestRunResult).where(TestRunResult.run_id == run_id)
            result = await session.execute(stmt)
            test_results = result.scalars().all()
            
            # 转换为字典并添加 test_results
            return {
                'id': test_run.id,
                'name': test_run.name,
                'description': test_run.description,
                'overall_precision': float(test_run.overall_precision) if test_run.overall_precision else 0.0,
                'overall_recall': float(test_run.overall_recall) if test_run.overall_recall else 0.0,
                'overall_f1': float(test_run.overall_f1) if test_run.overall_f1 else 0.0,
                'overall_mrr': float(test_run.overall_mrr) if test_run.overall_mrr else 0.0,
                'overall_ndcg': float(test_run.overall_ndcg) if test_run.overall_ndcg else 0.0,
                'total_test_cases': test_run.total_test_cases,
                'passed_test_cases': test_run.passed_test_cases,
                'status': test_run.status.value if hasattr(test_run.status, 'value') else test_run.status,
                'created_at': test_run.created_at.isoformat() if test_run.created_at else None,
                'completed_at': test_run.completed_at.isoformat() if test_run.completed_at else None,
                'snapshot_id': test_run.snapshot_id,
                'config_version_id': test_run.config_version_id,
                'previous_config_version_id': test_run.previous_config_version_id,
                'config_snapshot': test_run.config_snapshot,
                'test_results': [
                    {
                        'id': r.id,
                        'test_case_id': r.test_case_id,
                        'query': r.query,
                        'precision': float(r.precision) if r.precision else 0.0,
                        'recall': float(r.recall) if r.recall else 0.0,
                        'f1': float(r.f1) if r.f1 else 0.0,
                        'mrr': float(r.mrr) if r.mrr else 0.0,
                        'ndcg': float(r.ndcg) if r.ndcg else 0.0,
                        'passed': r.passed,
                        'matched_count': r.matched_count,
                        'expected_count': r.expected_count,
                        'actual_count': r.actual_count,
                        'execution_time_ms': r.execution_time_ms,
                        'error_message': r.error_message,
                    }
                    for r in test_results
                ]
            }

    async def get_last_test_run(self) -> Optional[TestRun]:
        """获取最后一个测试运行"""
        runs = await self.repo.get_latest_runs(limit=1)
        return runs[0] if runs else None

    def compare_config_versions(self, version_id1: str, version_id2: str) -> Dict:
        """比较两个配置版本的测试表现"""
        return self.analyzer.compare_config_versions(
            version_id1=version_id1,
            version_id2=version_id2,
        )


test_run_service = TestRunService()
