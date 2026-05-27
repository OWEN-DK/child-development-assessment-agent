"""运行引擎门面"""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

from sqlalchemy import desc, func, select

from src.core.async_task import AsyncTaskManager
from src.core.config.cache import ConfigCache
from src.core.database import async_session_factory
from src.core.interfaces import IRetrievalService
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
from src.utils.logger import logger
from src.utils.orm_mapper import OrmMapper


class RunEngineFacade:
    """运行引擎门面"""

    def __init__(
        self,
        executor: TestCaseExecutor,
        batch_runner: BatchTestRunner,
        result_processor: ResultProcessor,
        snapshot_manager: SnapshotManager,
        test_run_repository: TestRunRepository,
        test_run_result_repository: TestRunResultRepository,
        case_engine: CaseEngineFacade,
        retrieval_service: IRetrievalService | None = None,
        generation_service=None,
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
        self._retrieval = retrieval_service
        self._generation = generation_service
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
        # 如果已在运行中，拒绝重复启动
        if self._mapper.safe_enum_value(run.status) == "running":
            raise AppException(409, 13021, "测试运行已在执行中", "RUN_ALREADY_RUNNING")
        case_ids = set(run.custom_case_ids or [])
        for set_id in run.test_set_ids or []:
            try:
                case_ids.update((await self._case_engine.get_set(set_id)).case_ids)
            except AppException:
                continue
        async def _load_case(cid: str):
            try:
                return await self._case_engine.get_case(cid)
            except AppException:
                return None

        loaded = await asyncio.gather(*[_load_case(cid) for cid in case_ids])
        test_cases = [c for c in loaded if c is not None]
        if not test_cases:
            raise AppException(400, 13019, "测试集为空", "TEST_SET_EMPTY")
        # 立即清除上次运行的残留字段，确保前端 refetch 能拿到干净状态
        await self._run_repo.update(run_id, {
            "status": "running",
            "started_at": datetime.now(timezone.utc),
            "completed_at": None,
            "passed_test_cases": 0,
            "total_test_cases": len(test_cases),
        })
        task_id = await self._task_manager.start_task(
            task_type="test_run", task_func=self._batch_runner.execute_run,
            run_id=run_id, test_cases=test_cases)
        # 存储 task_id 用于后续取消
        await self._run_repo.update(run_id, {"task_id": task_id})
        return task_id

    def build_execution_functions(
        self,
    ) -> tuple[
        Callable[[str, list[str] | None], Awaitable[list[dict]]] | None,
        Callable[[str, list[str]], Awaitable[str | None]] | None,
    ]:
        """构建检索和生成函数，供 execute_single 和 batch_runner 共用

        两个闭包通过 _retrieved_items 共享检索结果：
        retrieval_fn 填充内容，generation_fn 读取内容生成答案。
        每次测试用例执行串行调用，不存在并发竞争。

        retrieval_fn 支持可选的 book_ids 参数：
        - 传入 book_ids 时，走 search_content 路径（与 knowledge-qa 的 search_knowledge_base 一致）
        - 不传 book_ids 时，走原有的 retrieve_knowledge 路径
        """
        _retrieved_items: list[dict] = []

        retrieval_fn = None
        if self._retrieval:
            async def _retrieval(query: str, book_ids: list[str] | None = None):
                if book_ids:
                    # knowledge-qa 路径：search_content + book_ids 过滤
                    result = await self._retrieval.search_content(
                        query, limit=5, book_ids=book_ids
                    )
                    raw_items = result.get("results", []) if isinstance(result, dict) else []
                    items = [
                        {"id": r.get("id", ""), "content": r.get("content", "")}
                        for r in raw_items
                    ]
                else:
                    # 原有路径：retrieve_knowledge（无 book 过滤）
                    results = await self._retrieval.retrieve_knowledge(
                        query, limit=5, skip_classification=True
                    )
                    items = []
                    for r in (results or []):
                        if isinstance(r, dict):
                            items.append({"id": r.get("id", ""), "content": r.get("content", "")})
                        else:
                            items.append({"id": getattr(r, "id", "") or "", "content": getattr(r, "content", "") or ""})
                _retrieved_items.clear()
                _retrieved_items.extend(items)
                valid_items = [i for i in items if i.get("id")]
                if not valid_items:
                    logger.warning(
                        f"[RAG-EVAL] 检索返回 {len(items)} 个结果但无有效ID, "
                        f"query='{query[:80]}'"
                    )
                else:
                    logger.info(
                        f"[RAG-EVAL] 检索成功: {len(valid_items)} 个有效片段, "
                        f"IDs={[i['id'][:12] for i in valid_items]}"
                    )
                return items
            retrieval_fn = _retrieval

        generation_fn = None
        if self._generation:
            async def _generation(query: str, retrieved_ids: list[str]):
                from src.core.prompts_fallback import (
                    ANSWER_GENERATION_SYSTEM_PROMPT,
                    ANSWER_GENERATION_USER_PROMPT,
                )
                from src.schemas.llm import LLMMessage, LLMRequest

                context = "\n\n".join(
                    item.get("content", "") for item in _retrieved_items if item.get("content")
                )
                if not context:
                    logger.warning(
                        f"[RAG-EVAL] 生成阶段上下文为空，检索到 {len(retrieved_ids)} 个ID "
                        f"但 _retrieved_items 中无有效内容 "
                        f"(items={[item.get('id','?') for item in _retrieved_items]})"
                    )
                    return None

                model = self._config.get_str("rag.eval.run.generation_model", "qwen-plus")
                llm_timeout = self._config.get_int("rag.eval.run.llm_timeout", 120)
                user_prompt = ANSWER_GENERATION_USER_PROMPT.format(
                    query=query, context=context,
                )
                resp = await self._generation.chat_with_retry(LLMRequest(
                    messages=[
                        LLMMessage(role="system", content=ANSWER_GENERATION_SYSTEM_PROMPT),
                        LLMMessage(role="user", content=user_prompt),
                    ],
                    model_name=model,
                    temperature=0.3,
                    max_tokens=2048,
                    timeout=llm_timeout,
                ))
                answer = resp.content
                if not answer:
                    logger.warning(
                        f"[RAG-EVAL] LLM 返回空答案, model={model}, "
                        f"context_len={len(context)}, query='{query[:80]}'"
                    )
                return answer
            generation_fn = _generation

        return retrieval_fn, generation_fn


    async def execute_single(self, run_id: str, case_id: str) -> TestRunResultItem:
        """执行单个测试用例"""
        case = await self._case_engine.get_case(case_id)
        if not case:
            raise TestCaseNotFoundException(case_id)
        retrieval_fn, generation_fn = self.build_execution_functions()
        return await self._executor.execute(
            test_case=case, run_id=run_id,
            retrieval_fn=retrieval_fn, generation_fn=generation_fn,
        )

    async def get_run(self, run_id: str) -> TestRunRead:
        """获取测试运行详情"""
        orm_obj = await self._run_repo.get_by_id(run_id)
        if not orm_obj:
            raise TestRunNotFoundException(run_id)
        return self._mapper.to_read(orm_obj, TestRunRead)

    async def get_run_results(self, run_id: str) -> list[TestRunResultItem]:
        """获取测试运行的全部结果项"""
        orm_results = await self._result_repo.get_by_run_id(run_id)
        return [TestRunResultItem.model_validate(r) for r in orm_results]

    async def update_status(self, run_id: str, status: str) -> None:
        """更新测试运行状态"""
        await self._run_repo.update(run_id, {"status": status})

    async def save_evaluation(
        self,
        run_id: str,
        metrics: "RunMetrics | None" = None,
        diagnosis: "DiagnosisResult | None" = None,
    ) -> None:
        """将评估结果回写到 test_runs 表"""
        update_data: dict = {}
        if metrics is not None:
            update_data["l1_metrics_json"] = metrics.l1.model_dump(mode="json")
            update_data["l2_metrics_json"] = metrics.l2.model_dump(mode="json")
            update_data["l3_metrics_json"] = metrics.l3.model_dump(mode="json")
            update_data["overall_score"] = metrics.overall_score
        if diagnosis is not None:
            update_data["diagnosis_json"] = diagnosis.model_dump(mode="json")
        if update_data:
            await self._run_repo.update(run_id, update_data)

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

    async def cancel_run(self, run_id: str) -> None:
        """取消正在运行的测试"""
        run = await self._run_repo.get_by_id(run_id)
        if not run:
            raise TestRunNotFoundException(run_id)
        status = self._mapper.safe_enum_value(run.status)
        if status != "running":
            raise AppException(409, 13022, "仅 running 状态的测试可取消", "RUN_NOT_RUNNING")
        task_id = run.task_id
        if not task_id:
            # 无 task_id 直接标记为取消
            await self._run_repo.update(run_id, {"status": "cancelled"})
            return
        await self._task_manager.cancel_task(task_id, "test_run")

    async def delete_run(self, run_id: str) -> None:
        """删除测试运行，running 状态先取消再删除"""
        run = await self._run_repo.get_by_id(run_id)
        if not run:
            raise TestRunNotFoundException(run_id)
        # running 状态先取消
        if self._mapper.safe_enum_value(run.status) == "running":
            await self.cancel_run(run_id)
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
