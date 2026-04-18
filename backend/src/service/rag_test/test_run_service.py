from typing import Callable, Dict, List, Optional

from src.models.test_case import TestCase
from src.schemas import TestResult, TestRunStatus
from src.service.rag_test.test_run import (
    TestBatchRunner,
    TestExecutor,
    TestResultAnalyzer,
    TestRunCreator,
    TestRunStorage,
)


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
        self.storage = TestRunStorage()

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
            run_test_case_fn=self.executor.run_test_case,
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

    def save_test_run(self, test_run):
        """保存测试运行到文件"""
        return self.storage.save_test_run(test_run=test_run)

    def list_test_runs(self) -> List:
        """列出所有测试运行"""
        return self.storage.list_test_runs()

    def get_test_run(self, run_id: str):
        """获取指定测试运行"""
        return self.storage.get_test_run(run_id=run_id)

    async def get_last_test_run(self):
        """获取最后一个测试运行"""
        return self.storage.get_last_test_run()

    def compare_config_versions(self, version_id1: str, version_id2: str) -> Dict:
        """比较两个配置版本的测试表现"""
        return self.analyzer.compare_config_versions(
            version_id1=version_id1,
            version_id2=version_id2,
        )


test_run_service = TestRunService()
