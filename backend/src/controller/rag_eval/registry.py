"""RagEvalControllerRegistry - 统一注册所有子控制器到FastAPI router"""

from fastapi import APIRouter

from src.controller.rag_eval.case_controller import CaseController
from src.controller.rag_eval.draft_controller import DraftController
from src.controller.rag_eval.metric_controller import MetricController
from src.controller.rag_eval.report_controller import ReportController
from src.controller.rag_eval.run_controller import RunController
from src.controller.rag_eval.snapshot_controller import SnapshotController
from src.controller.rag_eval.tuning_controller import TuningController
from src.service.rag_eval.orchestrator import RagEvalOrchestrator


class RagEvalControllerRegistry:
    """统一注册所有子控制器到FastAPI router

    路由前缀统一为 /rag/eval/，由 server.py 侧配置。
    orchestrator 作为依赖注入，确保 DI 容器实例化它（触发 post_run_pipeline 回调绑定）。
    """

    def __init__(
        self,
        draft_ctrl: DraftController,
        case_ctrl: CaseController,
        run_ctrl: RunController,
        metric_ctrl: MetricController,
        report_ctrl: ReportController,
        tuning_ctrl: TuningController,
        snapshot_ctrl: SnapshotController,
        orchestrator: RagEvalOrchestrator,
    ):
        self._draft_ctrl = draft_ctrl
        self._case_ctrl = case_ctrl
        self._run_ctrl = run_ctrl
        self._metric_ctrl = metric_ctrl
        self._report_ctrl = report_ctrl
        self._tuning_ctrl = tuning_ctrl
        self._snapshot_ctrl = snapshot_ctrl
        self._orchestrator = orchestrator

    def register_all(self, router: APIRouter) -> None:
        """注册所有子控制器，路由前缀 /rag/eval/"""
        self._draft_ctrl.register(router)
        self._case_ctrl.register(router)
        self._run_ctrl.register(router)
        self._metric_ctrl.register(router)
        self._report_ctrl.register(router)
        self._tuning_ctrl.register(router)
        self._snapshot_ctrl.register(router)
