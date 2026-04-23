"""校验服务层

封装 ValidationOrchestrator 和 Layer6Runner，提供统一的校验接口。
"""

import logging
from typing import Any, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.validation.layers.layer6_runner import Layer6Runner
from src.core.validation.orchestrator import ValidationOrchestrator
from src.models.rag_eval.test_report import RagEvalTestReport
from src.models.rag_eval.test_run import RagEvalTestRun
from src.utils.exceptions import ResourceNotFoundException, ServiceUnavailableException

logger = logging.getLogger(__name__)

SessionFactory = Callable[[], AsyncSession]


class ValidationService:
    """校验服务门面类"""

    def __init__(self, session_factory: SessionFactory):
        self.session_factory = session_factory
        self.orchestrator = ValidationOrchestrator()

    async def execute_layer1_to_5(self, test_run: RagEvalTestRun) -> RagEvalTestReport:
        """执行 Layer 1-5 校验，创建 TestReport

        Args:
            test_run: 测试运行对象

        Returns:
            RagEvalTestReport: 包含校验结果的报告对象

        Raises:
            ResourceNotFoundException: 测试运行不存在
            ServiceUnavailableException: 校验队列已满
        """
        logger.info(f"开始执行 Layer 1-5 校验: test_run={test_run.id}")

        report = await self.orchestrator.execute(self.session_factory, test_run)

        logger.info(
            f"Layer 1-5 校验完成: test_run={test_run.id}, "
            f"report={report.id}, layers={len(report.validation_results or [])}"
        )

        return report

    async def execute_layer6(self, test_run: RagEvalTestRun) -> dict[str, Any]:
        """手动触发 Layer 6 校验

        Args:
            test_run: 测试运行对象

        Returns:
            Layer 6 校验结果字典

        Raises:
            ResourceNotFoundException: 测试运行不存在
        """
        logger.info(f"开始执行 Layer 6 校验: test_run={test_run.id}")

        runner = Layer6Runner(self.session_factory, test_run)
        result = await runner.execute()

        # 更新报告中的 Layer 6 结果
        await self._update_report_layer6(test_run.id, result)

        logger.info(f"Layer 6 校验完成: test_run={test_run.id}, status={result.get('status')}")

        return result

    async def get_validation_results(self, test_run_id: str) -> RagEvalTestReport:
        """获取测试运行的校验结果

        Args:
            test_run_id: 测试运行 ID

        Returns:
            RagEvalTestReport: 校验报告

        Raises:
            ResourceNotFoundException: 校验结果不存在
        """
        from sqlalchemy import select

        async with self.session_factory() as session:
            stmt = select(RagEvalTestReport).where(
                RagEvalTestReport.run_id == test_run_id
            )
            result = await session.execute(stmt)
            report = result.scalar_one_or_none()

            if not report:
                raise ResourceNotFoundException(message=f"校验结果不存在: {test_run_id}")

            return report

    async def _update_report_layer6(
        self, test_run_id: str, layer6_result: dict[str, Any]
    ) -> None:
        """更新报告中的 Layer 6 结果"""
        from sqlalchemy import select, update

        async with self.session_factory() as session:
            stmt = select(RagEvalTestReport).where(
                RagEvalTestReport.run_id == test_run_id
            )
            result = await session.execute(stmt)
            report = result.scalar_one_or_none()

            if not report:
                logger.warning(f"未找到报告，无法更新 Layer 6 结果: {test_run_id}")
                return

            # 更新 validation_results 中的 Layer 6 部分
            validation_results = report.validation_results or []
            for vr in validation_results:
                if vr.get("layer") == 6:
                    vr.update(layer6_result)
                    break
            else:
                validation_results.append(
                    {"layer": 6, **layer6_result}
                )

            stmt = (
                update(RagEvalTestReport)
                .where(RagEvalTestReport.id == report.id)
                .values(validation_results=validation_results)
            )
            await session.execute(stmt)
            await session.commit()


# 全局单例工厂
def get_validation_service(session_factory: SessionFactory) -> ValidationService:
    """获取校验服务实例"""
    return ValidationService(session_factory)
