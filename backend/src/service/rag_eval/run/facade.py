"""运行引擎门面"""

from datetime import datetime, timezone

from sqlalchemy import desc, func, select

from src.core.async_task import AsyncTaskManager
from src.core.config.cache import ConfigCache
from src.core.database import async_session_factory
from src.models.rag_eval.test_run import TestRun
from src.repository.rag_eval.test_run_repository import TestRunRepository
from src.repository.rag_eval.test_run_result_repository import TestRunResultRepository
from src.schemas.rag_eval.test_run import (
    RunComparison, TestRunCreate, TestRunList, TestRunRead, TestRunResultItem,
)
from src.service.rag_eval.case.facade import CaseEngineFacade
from src.service.rag_eval.run.batch_runner import BatchTestRunner
from src.service.rag_eval.run.executor import TestCaseExecutor
from src.service.rag_eval.run.result_processor import ResultProcessor
from src.service.rag_eval.run.snapshot_manager import SnapshotManager
from src.utils.exceptions import AppException, TestCaseNotFoundException, TestRunNotFoundException
from src.utils.id_generator import generate_id
from src.utils.orm_mapper import OrmMapper


class RunEngineFacade:
    """运行引擎门面"""

    def __init__(        self,
        executor: TestCaseExecutor,
        batch_runner: BatchTestRunner,
        result_processor: ResultProcessor,
        snapshot_manager: SnapshotManager,
        test_run_repository: TestRunRepository,
        test_run_result_repository: TestRunResultRepository,
        case_engine: CaseEngineFacade,
        config_cache: ConfigCache | None = None,
        async_task_manager: AsyncTaskManager | None = None,
    ):
        self._executor = executor
        self._batch_runner = batch_runner
        self._result_processor = result_processor
        self._snapshot = snapshot_manager
        self._run_repo = test_run_repository
        self._result_repo = test_run_result_repository
        self._case_engine = case_engine
        self._config = config_cache or ConfigCache.get_instance()
        self._task_manager = async_task_manager or AsyncTaskManager()
        self._mapper = OrmMapper()

    async def create_run(self, data: TestRunCreate) -> TestRunRead:
        """创建测试运行记录，收集用例并去重，auto_snapshot=true 时自动创建快照"""
        case_ids = set(data.custom_case_ids)
        for set_id in data.test_set_ids:
            try:
                set_data = await self._case_engine.get_set(set_id)
                case_ids.update(set_data.case_ids)
            except AppException:
                continue
        snapshot_id = data.snapshot_id
        if not snapshot_id and data.auto_snapshot:
            auto_s = await self._snapshot.create_snapshot(
                name=f"auto_run_{datetime.now(timezone.utc).isoformat()}",
                description="测试运行自动创建")
            snapshot_id = auto_s.id
        run_id = generate_id()
        orm_obj = await self._run_repo.create({
            "id": run_id, "name": data.name, "description": data.description,
            "test_set_ids": data.test_set_ids, "custom_case_ids": data.custom_case_ids,
            "snapshot_id": snapshot_id, "status": "pending", "total_test_cases": len(case_ids),
        })
        return self._mapper.to_read(orm_obj, TestRunRead)

    async def start_run(self, run_id: str) -> str:
        """启动测试运行（后台任务），返回 task_id"""
        run = await self._run_repo.get_by_id(run_id)
        if not run:
            raise TestRunNotFoundException(run_id)
        case_ids = set(run.custom_case_ids or [])
        for set_id in run.test_set_ids or []:
            try:
                case_ids.update((await self._case_engine.get_set(set_id)).case_ids)
            except AppException:
                continue
        test_cases = []
        for cid in case_ids:
            try:
                test_cases.append(await self._case_engine.get_case(cid))
            except AppException:
                continue
        if not test_cases:
            raise AppException(400, 13019, "测试集为空", "TEST_SET_EMPTY")
        return await self._task_manager.start_task(
            task_type="test_run", task_func=self._batch_runner.execute_run,
            run_id=run_id, test_cases=test_cases)

    async def execute_single(self, run_id: str, case_id: str) -> TestRunResultItem:
        """执行单个测试用例"""
        case = await self._case_engine.get_case(case_id)
        if not case:
            raise TestCaseNotFoundException(case_id)
        return await self._executor.execute(test_case=case, run_id=run_id)

    async def get_run(self, run_id: str) -> TestRunRead:
        """获取测试运行详情"""
        orm_obj = await self._run_repo.get_by_id(run_id)
        if not orm_obj:
            raise TestRunNotFoundException(run_id)
        return self._mapper.to_read(orm_obj, TestRunRead)

    async def list_runs(self, status: str | None = None, test_set_id: str | None = None,
                        page: int = 1, page_size: int = 20) -> TestRunList:
        """列出测试运行，支持按 status 过滤和分页"""
        async with async_session_factory() as session:
            count_q = select(func.count()).select_from(TestRun)
            query = select(TestRun)
            if status:
                count_q = count_q.where(TestRun.status == status)
                query = query.where(TestRun.status == status)
            total = (await session.execute(count_q)).scalar_one()
            query = query.order_by(desc(TestRun.created_at))
            query = query.offset((page - 1) * page_size).limit(page_size)
            items = list((await session.execute(query)).scalars().all())
        return TestRunList(
            items=self._mapper.to_read_list(items, TestRunRead),
            total=total, page=page, page_size=page_size)

    async def delete_run(self, run_id: str) -> None:
        """删除测试运行，running 状态不可删除"""
        run = await self._run_repo.get_by_id(run_id)
        if not run:
            raise TestRunNotFoundException(run_id)
        if self._mapper.safe_enum_value(run.status) == "running":
            raise AppException(409, 13020, "运行中的测试不可删除", "RUN_IN_PROGRESS")
        results = await self._result_repo.get_by_run_id(run_id)
        for r in results:
            await self._result_repo.delete(r.id)
        await self._run_repo.delete(run_id)

    async def batch_delete_runs(self, run_ids: list[str]) -> None:
        """批量删除测试运行"""
        for run_id in run_ids:
            await self.delete_run(run_id)

    async def compare_runs(self, run_id_1: str, run_id_2: str) -> RunComparison:
        """比较两个测试运行"""
        return await self._result_processor.compare(run_id_1, run_id_2)
