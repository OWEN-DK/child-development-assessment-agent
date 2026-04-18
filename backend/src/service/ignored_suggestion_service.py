"""忽略建议服务

负责获取、恢复、删除已忽略建议的业务逻辑
"""

from datetime import datetime, timezone
from typing import List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.rag_eval.ignored_suggestion import RagEvalIgnoredSuggestion
from src.utils.logger import logger


class IgnoredSuggestionService:
    """忽略建议服务"""

    async def get_ignored_suggestions(
        self,
        test_set_id: str,
        session: AsyncSession,
        report_id: str | None = None,
    ) -> List[RagEvalIgnoredSuggestion]:
        """获取已忽略建议列表

        Args:
            test_set_id: 测试集ID
            session: 数据库会话
            report_id: 报告ID（可选，用于过滤）

        Returns:
            未恢复的忽略建议列表
        """
        stmt = select(RagEvalIgnoredSuggestion).where(
            RagEvalIgnoredSuggestion.test_set_id == test_set_id,
            RagEvalIgnoredSuggestion.restored == False,
        )

        if report_id:
            stmt = stmt.where(RagEvalIgnoredSuggestion.report_id == report_id)

        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def restore_ignored_suggestion(
        self,
        suggestion_id: str,
        session: AsyncSession,
    ) -> RagEvalIgnoredSuggestion:
        """恢复已忽略建议

        Args:
            suggestion_id: 忽略记录ID
            session: 数据库会话

        Returns:
            更新后的忽略记录

        Raises:
            ValueError: 记录不存在或已恢复
        """
        record = await session.get(RagEvalIgnoredSuggestion, suggestion_id)
        if not record:
            raise ValueError("忽略记录不存在")

        if record.restored:
            raise ValueError("该记录已恢复")

        record.restored = True
        record.restored_at = datetime.now(timezone.utc)

        await session.commit()

        logger.info(f"已恢复忽略建议: suggestion_id={suggestion_id}")
        return record

    async def delete_ignored_suggestion(
        self,
        suggestion_id: str,
        session: AsyncSession,
    ) -> None:
        """删除忽略记录

        Args:
            suggestion_id: 忽略记录ID
            session: 数据库会话

        Raises:
            ValueError: 记录不存在
        """
        record = await session.get(RagEvalIgnoredSuggestion, suggestion_id)
        if not record:
            raise ValueError("忽略记录不存在")

        session.delete(record)
        await session.commit()

        logger.info(f"已删除忽略记录: suggestion_id={suggestion_id}")
