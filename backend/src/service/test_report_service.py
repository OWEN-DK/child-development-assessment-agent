"""测试报告服务 - 基于 ValidationOrchestrator 的校验报告生成"""

import logging
from typing import Callable

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.validation.orchestrator import ValidationOrchestrator
from src.models.rag_eval.test_run import RagEvalTestRun
from src.models.rag_eval.test_report import RagEvalTestReport

logger = logging.getLogger(__name__)

SessionFactory = Callable[[], AsyncSession]


class TestReportService:
    """测试报告服务，通过 ValidationOrchestrator 执行校验并生成报告"""

    def __init__(self, session_factory: SessionFactory):
        self.session_factory = session_factory
        self.orchestrator = ValidationOrchestrator()

    async def generate_validation_report(
        self, test_run: RagEvalTestRun
    ) -> RagEvalTestReport:
        """执行校验并生成报告

        调用 ValidationOrchestrator.execute() 执行 Layer 1-5 校验，
        返回包含校验结果的 RagEvalTestReport。

        Args:
            test_run: 要校验的测试运行记录

        Returns:
            RagEvalTestReport: 包含校验结果的报告

        Raises:
            HTTPException: 503 当队列已满时
            ValueError: 当 test_run 状态不允许执行校验时
        """
        if not test_run.id:
            raise ValueError("test_run.id 不能为空")

        logger.info(f"开始执行校验报告生成，test_run_id={test_run.id}")

        try:
            report = await self.orchestrator.execute(self.session_factory, test_run)
            logger.info(
                f"校验报告生成完成，report_id={report.id}, status={report.status}"
            )
            return report
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"校验报告生成失败: {e}", exc_info=True)
            raise RuntimeError(f"校验报告生成失败: {e}") from e


test_report_service: TestReportService | None = None


def get_test_report_service(session_factory: SessionFactory) -> TestReportService:
    """获取 TestReportService 实例

    Args:
        session_factory: 异步 session 工厂函数

    Returns:
        TestReportService 实例
    """
    global test_report_service
    if test_report_service is None:
        test_report_service = TestReportService(session_factory)
    return test_report_service
