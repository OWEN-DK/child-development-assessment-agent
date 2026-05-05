"""指标与诊断控制器"""

import asyncio

from fastapi import APIRouter, Path

from src.schemas.common import APIResponse
from src.service.rag_eval.metrics.facade import MetricEngineFacade
from src.service.rag_eval.run.facade import RunEngineFacade
from src.utils.logger import logger


class MetricController:
    """指标与诊断端点"""

    def __init__(
        self,
        metric_engine: MetricEngineFacade,
        run_engine: RunEngineFacade,
    ):
        self._metric = metric_engine
        self._run = run_engine

    def register(self, router: APIRouter) -> None:
        router.add_api_route("/runs/{run_id}/metrics", self.get_metrics, methods=["GET"])
        router.add_api_route("/runs/{run_id}/diagnosis", self.get_diagnosis, methods=["GET"])
        router.add_api_route("/runs/{run_id}/evaluate", self.evaluate, methods=["POST"])

    async def get_metrics(self, run_id: str = Path(...)):
        """获取三层指标 — 从 test_runs JSON 字段读取已缓存的指标数据"""
        run = await self._run.get_run(run_id)
        l1 = run.l1_metrics_json or {}
        l2 = run.l2_metrics_json or {}
        l3 = run.l3_metrics_json or {}
        return APIResponse.success({
            "overall_score": run.overall_score,
            "l1_metrics": l1,
            "l2_metrics": l2,
            "l3_metrics": l3,
        })

    async def get_diagnosis(self, run_id: str = Path(...)):
        """获取六层诊断 — 从 test_runs JSON 字段读取已缓存的诊断数据"""
        run = await self._run.get_run(run_id)
        return APIResponse.success(run.diagnosis_json or {})

    async def evaluate(self, run_id: str = Path(...)):
        """触发双轨评估 — 后台执行，立即返回"""

        async def _do_evaluate():
            try:
                await self._run.update_status(run_id, "running")
                run = await self._run.get_run(run_id)
                results = await self._run.get_run_results(run_id)
                metrics, diagnosis = await self._metric.calculate_and_diagnose(
                    run_id, results, run_data=run,
                )
                await self._run.save_evaluation(run_id, metrics, diagnosis)
                await self._run.update_status(run_id, "completed")
                logger.info(f"运行[{run_id}] 手动评估完成")
            except Exception as e:
                await self._run.update_status(run_id, "failed")
                logger.error(f"运行[{run_id}] 手动评估失败: {e}", exc_info=True)

        asyncio.create_task(_do_evaluate())
        return APIResponse.success({"message": "评估已启动"})
