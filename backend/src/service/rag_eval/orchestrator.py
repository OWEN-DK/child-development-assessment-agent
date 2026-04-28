"""RagEvalOrchestrator - 跨引擎协调器

协调六个引擎完成完整的评估工作流：
草稿生成 → 用例管理 → 测试运行 → 双轨评估 → 报告生成 → 调优分析
"""

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
    ):
        self._draft = draft_engine
        self._case = case_engine
        self._run = run_engine
        self._metric = metric_engine
        self._report = report_engine
        self._tuning = tuning_engine

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
