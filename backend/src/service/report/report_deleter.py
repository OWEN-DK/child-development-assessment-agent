"""报告删除器

负责物理删除测试报告
"""

from pathlib import Path

from src.core.database import db_session_factory
from src.repository.test_case_repository import TestRunRepository
from src.utils.logger import logger


class ReportDeleter:
    """报告删除器"""

    def __init__(self):
        self.test_run_repo = TestRunRepository(db_session_factory)

    async def delete(self, run_id: str):
        """物理删除报告"""
        test_run = await self.test_run_repo.get_by_id(run_id)
        if not test_run:
            raise ValueError(f"测试运行 {run_id} 不存在")

        try:
            # 删除报告文件
            if test_run.report_storage_path:
                path = Path(test_run.report_storage_path)
                if path.exists():
                    path.unlink()
                    logger.info(f"已删除报告文件: {test_run.report_storage_path}")

            # 物理删除数据库记录（级联删除结果）
            await self.test_run_repo.delete(run_id)
            logger.info(f"已物理删除报告 {run_id}")
        except Exception as e:
            logger.error(f"删除报告 {run_id} 失败: {e}")
            raise
