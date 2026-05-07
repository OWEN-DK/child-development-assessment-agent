"""RagEvalOrchestrator - 跨引擎协调器

协调六个引擎完成完整的评估工作流：
草稿生成 → 用例管理 → 测试运行 → 双轨评估 → 报告生成 → 调优分析
"""

import asyncio

from src.schemas.rag_eval.draft import DraftGenerationConfig
from src.schemas.rag_eval.test_run import TestRunCreate
from src.service.rag_eval.case.facade import CaseEngineFacade
from src.service.rag_eval.draft.facade import DraftEngineFacade
from src.service.rag_eval.metrics.facade import MetricEngineFacade
from src.service.rag_eval.report.facade import ReportEngineFacade
from src.service.rag_eval.run.facade import RunEngineFacade
from src.service.rag_eval.tuning.facade import TuningEngineFacade
from src.utils.logger import logger


class RagEvalOrchestrator:
    """跨引擎协调器

    协调六个引擎完成完整的评估工作流：
    草稿生成 → 用例管理 → 测试运行 → 双轨评估 → 报告生成 → 调优分析
    """

    def __init__(
        self,
        draft_engine: DraftEngineFacade,
        case_engine: CaseEngineFacade,
        run_engine: RunEngineFacade,
        metric_engine: MetricEngineFacade,
        report_engine: ReportEngineFacade,
        tuning_engine: TuningEngineFacade,
        sse_publisher=None,
    ):
        self._draft = draft_engine
        self._case = case_engine
        self._run = run_engine
        self._metric = metric_engine
        self._report = report_engine
        self._tuning = tuning_engine
        self._sse = sse_publisher

    async def run_full_evaluation(
        self, test_set_ids: list[str], config: dict | None = None
    ) -> str:
        """完整评估工作流：快照→执行→双轨指标→报告→调优

        内部由 RunEngine.start_run 触发的 BatchTestRunner 自动完成
        执行→结果处理→指标→诊断→报告→调优的完整链路。
        本方法负责创建运行记录并启动后台任务。

        Args:
            test_set_ids: 测试集 ID 列表
            config: 可选的运行配置

        Returns:
            测试运行 ID
        """
        config = config or {}
        data = TestRunCreate(
            name=config.get("name", "完整评估"),
            description=config.get("description", ""),
            test_set_ids=test_set_ids,
            custom_case_ids=config.get("custom_case_ids", []),
        )
        run = await self._run.create_run(data)
        task_id = await self._run.start_run(run.id)
        logger.info(f"完整评估已启动: run={run.id}, task={task_id}")
        return run.id

    async def _push(self, channel: str, event_type: str, data: dict) -> None:
        """推送 SSE 事件（复用 test_run:{run_id} 通道）"""
        if not self._sse:
            return
        try:
            from fastapi.encoders import jsonable_encoder
            payload = {"type": event_type, "data": data}
            await self._sse.publish(channel, jsonable_encoder(payload))
        except Exception as e:
            logger.warning(f"SSE 推送失败 [{event_type}]: {e}")

    async def post_run_pipeline(self, run_id: str) -> None:
        """运行完成后处理流水线：双轨评估 → 报告生成

        由 BatchTestRunner 的 on_complete 回调触发。
        各步骤独立 catch，单步失败不阻塞后续步骤。
        通过 test_run:{run_id} 通道推送进度事件，前端可实时展示全链路状态。

        并行化策略：
        - get_run + get_run_results 并行（独立 DB 读）
        - calculate_all + diagnose_all 并行（已由 MetricEngineFacade 实现）
        - render + supersede 并行（CPU 与 DB 写独立）

        Args:
            run_id: 已完成的测试运行 ID
        """
        channel = f"test_run:{run_id}"

        # 步骤 1：双轨评估（指标计算 + 六层诊断）
        try:
            await self._push(channel, "metrics_computing", {"run_id": run_id})
            # 并行获取运行记录和结果（独立 DB 读）
            run, results = await asyncio.gather(
                self._run.get_run(run_id),
                asyncio.wait_for(self._run.get_run_results(run_id), timeout=30.0),
            )
            if not results:
                logger.error(f"运行[{run_id}] 结果列表为空，跳过评估")
                await self._push(channel, "report_failed", {
                    "run_id": run_id, "error": "结果列表为空",
                })
                return
            metrics, diagnosis = await self._metric.calculate_and_diagnose(
                run_id, results, run_data=run,
            )
            # 验证指标是否包含有效数据（至少一个 L1 指标有 case_count）
            l1_details = metrics.l1.context_precision.details or {}
            if not l1_details.get("case_count"):
                logger.error(
                    f"运行[{run_id}] 指标计算结果为空（无 case_count），跳过保存和报告生成"
                )
                await self._push(channel, "report_failed", {
                    "run_id": run_id, "error": "指标计算结果为空",
                })
                return
            await self._run.save_evaluation(run_id, metrics, diagnosis)
            await self._push(channel, "metrics_done", {"run_id": run_id})
            logger.info(f"运行[{run_id}] 双轨评估完成")
        except asyncio.TimeoutError:
            logger.error(f"运行[{run_id}] 获取结果超时（30s），跳过评估")
            await self._push(channel, "report_failed", {
                "run_id": run_id, "error": "获取结果超时",
            })
            return
        except Exception as e:
            logger.error(f"运行[{run_id}] 双轨评估失败: {e}", exc_info=True)
            await self._push(channel, "report_failed", {
                "run_id": run_id, "error": str(e),
            })
            return

        # 步骤 2：报告生成（build → render ∥ supersede → save）
        try:
            await self._push(channel, "report_generating", {
                "run_id": run_id, "stage": "building",
            })
            data = await self._report._b.build(run_id)

            await self._push(channel, "report_generating", {
                "run_id": run_id, "stage": "rendering",
            })
            # 并行：Markdown 渲染（CPU）+ 标记旧报告 superseded（DB 写）
            md, _ = await asyncio.gather(
                asyncio.to_thread(self._report._r.render, data),
                self._report._supersede(run_id),
            )

            await self._push(channel, "report_generating", {
                "run_id": run_id, "stage": "saving",
            })
            from src.utils.id_generator import generate_id
            rid = generate_id()
            await self._report._rr.create({
                "id": rid, "run_id": run_id,
                "test_set_id": run.test_set_ids[0] if run.test_set_ids else None,
                "config_version_id": getattr(run, "config_version_id", None),
                "overall_score": data.summary.overall_score,
                "l1_score": data.summary.l1_score,
                "l2_score": data.summary.l2_score,
                "l3_score": data.summary.l3_score,
                "metrics_json": data.model_dump(mode="json"),
                "diagnosis_json": {
                    "sections": [s.model_dump(mode="json") for s in data.diagnosis_details],
                    "overall_health": data.summary.diagnosis_health,
                },
                "bad_cases_json": [c.model_dump(mode="json") for c in data.bad_cases],
                "suggestions_json": [s.model_dump(mode="json") for s in data.tuning_suggestions],
                "markdown_content": md, "status": "completed",
            })

            await self._push(channel, "report_completed", {
                "run_id": run_id, "report_id": rid,
            })
            logger.info(f"运行[{run_id}] 报告生成完成")
        except Exception as e:
            logger.error(f"运行[{run_id}] 报告生成失败: {e}", exc_info=True)
            await self._push(channel, "report_failed", {
                "run_id": run_id, "error": str(e),
            })

    async def generate_and_review_drafts(
        self, doc_id: str, config: DraftGenerationConfig | None = None
    ) -> str:
        """草稿全流程：生成→忠实度验证→去重→保存

        DraftEngineFacade.start_generation 内部已编排完整流程。

        Args:
            doc_id: 源文档 ID
            config: 可选的生成配置

        Returns:
            后台任务 ID
        """
        config = config or DraftGenerationConfig()
        task_id = await self._draft.start_generation(doc_id, config)
        logger.info(f"草稿生成已启动: doc={doc_id}, task={task_id}")
        return task_id
