"""批量测试运行器

管理测试运行的完整生命周期：创建运行、分发用例执行、收集结果、更新状态。
支持 SSE 进度推送、并发控制、权限上下文注入。
"""
import asyncio
import time
import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.ext.asyncio import async_sessionmaker

from src.core.pipeline.compiler import PipelineCompiler
from src.core.pipeline.node_context import AuthContext
from src.models.rag_eval.test_case import TestCase, TestSet
from src.repository.rag_eval.test_case_repo import TestCaseRepository
from src.repository.rag_eval.test_run_repo import (
    TestRunRepository,
    TestRunResultRepository,
)
from src.repository.rag_eval.test_set_repo import TestSetRepository
from src.schemas.rag_eval.test_run import TestRunStatus
from src.service.rag_eval.run.executor import TestCaseExecutor
from src.utils.logger import logger

# 并发控制常量
MAX_CONCURRENT_RUNS = 2  # 全局最大并发运行数
MAX_CONCURRENT_CASES = 5  # 单运行内最大并发用例数


class AuthContextProvider:
    """权限上下文提供者

    根据运行配置构造 AuthContext，支持角色模拟。
    """

    def __init__(self, session_factory: async_sessionmaker):
        self._session_factory = session_factory

    async def get_context(
        self,
        user_id: str,
        tenant_id: str,
        roles: list[str] | None = None,
        role_slugs: list[str] | None = None,
        is_superadmin: bool = False,
    ) -> AuthContext:
        """构造评估执行的权限上下文"""
        return AuthContext(
            tenant_id=tenant_id,
            user_id=user_id,
            roles=roles or [],
            role_slugs=role_slugs or [],
            is_superadmin=is_superadmin,
            is_god_mode=False,
        )


class BatchTestRunner:
    """批量测试运行器

    管理从创建到完成的完整运行生命周期：
    1. 创建运行记录 → 状态 pending
    2. 并行分发用例到 TestCaseExecutor
    3. 收集结果 → 状态 completed/failed
    4. SSE 进度推送（通过回调）
    """

    def __init__(
        self,
        session_factory: async_sessionmaker,
        pipeline_compiler: PipelineCompiler,
        auth_provider: AuthContextProvider,
        run_repo: TestRunRepository,
        result_repo: TestRunResultRepository,
        case_repo: TestCaseRepository,
        set_repo: TestSetRepository,
    ):
        self._session_factory = session_factory
        self._compiler = pipeline_compiler
        self._auth_provider = auth_provider
        self._run_repo = run_repo
        self._result_repo = result_repo
        self._case_repo = case_repo
        self._set_repo = set_repo
        self._executor = TestCaseExecutor(pipeline_compiler, result_repo)
        # 回调：推送 SSE 事件
        self._progress_callback: Optional[callable] = None
        # 运行级信号量：最大并发运行数
        self._run_semaphore = asyncio.Semaphore(MAX_CONCURRENT_RUNS)

    def set_progress_callback(self, callback: callable):
        """设置 SSE 进度事件回调"""
        self._progress_callback = callback

    async def _emit(self, event_type: str, data: dict[str, Any]):
        """发送进度事件"""
        if self._progress_callback:
            try:
                await self._progress_callback(event_type, data)
            except Exception:
                pass  # 回调失败不阻塞主流程

    async def execute_run(
        self,
        run: TestRun,
        pipeline_config: dict[str, Any],
        user_id: str,
        roles: list[str],
        role_slugs: list[str],
        is_superadmin: bool = False,
        search_params: Optional[dict[str, Any]] = None,
    ) -> None:
        """执行一次完整的测试运行

        获取运行的所有用例，并行执行，收集结果并更新运行状态。
        评估运行通过内部通道执行，不经过发布 URL 限流。
        """
        async with self._run_semaphore:
            run_id = run.id
            tenant_id = run.tenant_id
            start_time = time.monotonic()

            # 收集所有用例
            test_cases = await self._gather_test_cases(
                test_set_ids=run.test_set_ids or [],
                tenant_id=tenant_id,
            )
            if not test_cases:
                logger.warning(f"运行 {run_id}: 没有找到测试用例")
                await self._run_repo.update(run_id, {
                    "status": TestRunStatus.FAILED.value,
                    "started_at": datetime.utcnow(),
                    "completed_at": datetime.utcnow(),
                    "total_test_cases": 0,
                }, tenant_id)
                return

            # 构造权限上下文
            auth_context = await self._auth_provider.get_context(
                user_id=user_id,
                tenant_id=tenant_id,
                roles=roles,
                role_slugs=role_slugs,
                is_superadmin=is_superadmin,
            )

            # 更新运行状态为 running
            await self._run_repo.update(run_id, {
                "status": TestRunStatus.RUNNING.value,
                "total_test_cases": len(test_cases),
                "started_at": datetime.utcnow(),
            }, tenant_id)

            await self._emit("run_started", {
                "run_id": run_id,
                "total_cases": len(test_cases),
                "pipeline_id": run.pipeline_id,
                "pipeline_version": run.pipeline_version,
            })

            # 并控执行所有用例
            semaphore = asyncio.Semaphore(MAX_CONCURRENT_CASES)
            completed_count = 0
            passed_count = 0
            errors: list[str] = []

            async def execute_one(case: TestCase):
                nonlocal completed_count, passed_count
                async with semaphore:
                    await self._emit("case_started", {
                        "run_id": run_id,
                        "case_id": case.id,
                    })
                    result = await self._executor.execute(
                        test_case=case,
                        run=run,
                        pipeline_config=pipeline_config,
                        auth_context=auth_context,
                        search_params=search_params,
                        timeout_ms=30000,  # 单用例 30s 超时
                    )
                    if result.passed == 1:
                        passed_count += 1
                    if result.error_message:
                        errors.append(result.error_message[:200])
                    completed_count += 1
                    await self._emit("case_completed", {
                        "run_id": run_id,
                        "case_id": case.id,
                        "passed": result.passed,
                        "completed": completed_count,
                        "total": len(test_cases),
                    })

            # 并行执行，收集异常
            tasks = [execute_one(c) for c in test_cases]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in results:
                if isinstance(r, Exception):
                    errors.append(str(r)[:200])

            # 更新运行完成状态
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            status = TestRunStatus.FAILED.value if errors else TestRunStatus.COMPLETED.value

            await self._run_repo.update(run_id, {
                "status": status,
                "total_test_cases": len(test_cases),
                "passed_test_cases": passed_count,
                "completed_at": datetime.utcnow(),
            }, tenant_id)

            await self._emit("run_completed", {
                "run_id": run_id,
                "status": status,
                "total_cases": len(test_cases),
                "passed_cases": passed_count,
                "elapsed_ms": elapsed_ms,
                "errors": errors[:10],  # 最多返回 10 条错误
            })

            logger.info(
                f"运行 {run_id} 完成: {passed_count}/{len(test_cases)} 通过, "
                f"elapsed={elapsed_ms}ms, status={status}"
            )

    async def _gather_test_cases(
        self,
        test_set_ids: list[str],
        tenant_id: str,
    ) -> list[TestCase]:
        """从测试集收集所有且去重后的用例列表"""
        seen: set[str] = set()
        cases: list[TestCase] = []

        for set_id in test_set_ids:
            test_set = await self._set_repo.get_by_id(set_id, tenant_id)
            if not test_set:
                continue
            case_ids = test_set.case_ids or []
            for case_id in case_ids:
                if case_id in seen:
                    continue
                seen.add(case_id)
                case = await self._case_repo.get_by_id(case_id, tenant_id)
                if case:
                    cases.append(case)

        return cases
