"""调优建议服务

负责获取、忽略、状态更新、批量操作、统计等调优建议相关业务逻辑
"""

from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.rag_eval.enums import (RagEvalIgnoredSuggestionType,
                                       RagEvalIgnoreScope,
                                       RagEvalSuggestionSource)
from src.models.rag_eval.ignored_suggestion import RagEvalIgnoredSuggestion
from src.models.rag_eval.tuning_suggestion import RagEvalTuningSuggestionRecord
from src.utils.logger import logger


class TuningSuggestionService:
    """调优建议服务"""

    async def get_active_suggestions(
        self,
        report_id: str,
        test_set_id: str,
        session: AsyncSession,
    ) -> List[RagEvalTuningSuggestionRecord]:
        """获取未被忽略的调优建议

        Args:
            report_id: 报告ID
            test_set_id: 测试集ID
            session: 数据库会话

        Returns:
            未被忽略的建议列表
        """
        # 查询该报告的所有建议
        stmt_suggestions = select(RagEvalTuningSuggestionRecord).where(
            RagEvalTuningSuggestionRecord.report_id == report_id
        )
        result = await session.execute(stmt_suggestions)
        all_suggestions = result.scalars().all()

        if not all_suggestions:
            return []

        # 查询该测试集和报告级别的忽略记录（未恢复的）
        stmt_ignored = select(RagEvalIgnoredSuggestion).where(
            RagEvalIgnoredSuggestion.test_set_id == test_set_id,
            RagEvalIgnoredSuggestion.restored == False,
        )
        ignored_result = await session.execute(stmt_ignored)
        ignored_records = ignored_result.scalars().all()

        # 构建忽略的参数名集合
        ignored_param_names = set()
        for record in ignored_records:
            # report级别忽略只影响当前报告
            if record.ignore_scope == RagEvalIgnoreScope.REPORT:
                if record.report_id == report_id:
                    ignored_param_names.add(record.param_name)
            # test_set级别忽略影响该测试集下所有报告
            elif record.ignore_scope == RagEvalIgnoreScope.TEST_SET:
                ignored_param_names.add(record.param_name)

        # 过滤掉被忽略的建议
        active_suggestions = [
            s for s in all_suggestions if s.param_name not in ignored_param_names
        ]

        return active_suggestions

    async def get_suggestions_by_report(
        self,
        report_id: str,
        session: AsyncSession,
        status: Optional[str] = None,
    ) -> List[RagEvalTuningSuggestionRecord]:
        """获取指定报告的所有调优建议

        Args:
            report_id: 报告ID
            session: 数据库会话
            status: 状态筛选（pending/applied/ignored）

        Returns:
            建议列表
        """
        stmt = select(RagEvalTuningSuggestionRecord).where(
            RagEvalTuningSuggestionRecord.report_id == report_id
        )

        if status == "applied":
            stmt = stmt.where(RagEvalTuningSuggestionRecord.applied == True)
        elif status == "pending":
            stmt = stmt.where(RagEvalTuningSuggestionRecord.applied == False)

        stmt = stmt.order_by(RagEvalTuningSuggestionRecord.priority.desc())
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_suggestion_by_id(
        self,
        suggestion_id: str,
        session: AsyncSession,
    ) -> Optional[RagEvalTuningSuggestionRecord]:
        """根据ID获取调优建议

        Args:
            suggestion_id: 建议ID
            session: 数据库会话

        Returns:
            建议对象或None
        """
        stmt = select(RagEvalTuningSuggestionRecord).where(
            RagEvalTuningSuggestionRecord.id == suggestion_id
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_suggestion_status(
        self,
        suggestion_id: str,
        applied: bool,
        session: AsyncSession,
        applied_config_version_id: Optional[str] = None,
    ) -> Optional[RagEvalTuningSuggestionRecord]:
        """更新调优建议状态

        Args:
            suggestion_id: 建议ID
            applied: 是否已采纳
            session: 数据库会话
            applied_config_version_id: 采纳后应用到的配置版本ID

        Returns:
            更新后的建议对象或None
        """
        suggestion = await self.get_suggestion_by_id(suggestion_id, session)
        if not suggestion:
            return None

        suggestion.applied = applied
        if applied and applied_config_version_id:
            suggestion.applied_config_version_id = applied_config_version_id

        await session.commit()
        await session.refresh(suggestion)

        logger.info(
            f"调优建议状态已更新: suggestion_id={suggestion_id}, applied={applied}"
        )

        return suggestion

    async def batch_update_suggestions(
        self,
        suggestion_ids: List[str],
        applied: bool,
        session: AsyncSession,
        applied_config_version_id: Optional[str] = None,
    ) -> int:
        """批量更新调优建议状态

        Args:
            suggestion_ids: 建议ID列表
            applied: 是否已采纳
            session: 数据库会话
            applied_config_version_id: 采纳后应用到的配置版本ID

        Returns:
            更新的建议数量
        """
        stmt = (
            update(RagEvalTuningSuggestionRecord)
            .where(RagEvalTuningSuggestionRecord.id.in_(suggestion_ids))
            .values(
                applied=applied,
                applied_config_version_id=applied_config_version_id,
            )
        )
        result = await session.execute(stmt)
        await session.commit()

        updated_count = result.rowcount
        logger.info(
            f"批量更新调优建议: count={updated_count}, applied={applied}"
        )

        return updated_count

    async def get_suggestion_stats(
        self,
        report_id: Optional[str] = None,
        session: Optional[AsyncSession] = None,
    ) -> Dict[str, int]:
        """获取调优建议统计

        Args:
            report_id: 报告ID（可选，不传则统计全部）
            session: 数据库会话

        Returns:
            统计数据 {pending: int, applied: int, ignored: int, total: int}
        """
        if session is None:
            return {"pending": 0, "applied": 0, "ignored": 0, "total": 0}

        stmt = select(
            func.count().label("total"),
            func.sum(func.cast(RagEvalTuningSuggestionRecord.applied, int)).label("applied"),
        )

        if report_id:
            stmt = stmt.where(RagEvalTuningSuggestionRecord.report_id == report_id)

        result = await session.execute(stmt)
        row = result.first()

        total = row.total if row and row.total else 0
        applied = row.applied if row and row.applied else 0
        pending = total - applied

        # 查询忽略记录数量
        ignored_stmt = select(func.count()).select_from(RagEvalIgnoredSuggestion)
        if report_id:
            ignored_stmt = ignored_stmt.where(
                RagEvalIgnoredSuggestion.report_id == report_id,
                RagEvalIgnoredSuggestion.restored == False,
            )
        ignored_result = await session.execute(ignored_stmt)
        ignored = ignored_result.scalar() or 0

        return {
            "total": total,
            "pending": pending,
            "applied": applied,
            "ignored": ignored,
        }

    async def ignore_suggestion(
        self,
        suggestion_id: str,
        scope: RagEvalIgnoreScope,
        reason: str | None,
        session: AsyncSession,
        test_set_id: str,
        report_id: str | None = None,
        param_name: str | None = None,
        suggestion_type: RagEvalIgnoredSuggestionType = RagEvalIgnoredSuggestionType.CONFIG,
        ignored_by: str | None = None,
    ) -> RagEvalIgnoredSuggestion:
        """忽略调优建议

        Args:
            suggestion_id: 建议ID（用于日志记录）
            scope: 忽略范围（report或test_set）
            reason: 忽略原因
            session: 数据库会话
            test_set_id: 测试集ID
            report_id: 报告ID（scope为report时必填）
            param_name: 参数名（从建议中获取）
            suggestion_type: 建议类型
            ignored_by: 操作用户ID

        Returns:
            创建的忽略记录
        """
        ignored_record = RagEvalIgnoredSuggestion(
            test_set_id=test_set_id,
            report_id=report_id,
            param_name=param_name or "",
            suggestion_type=suggestion_type,
            ignore_scope=scope,
            ignored_by=ignored_by,
            ignore_reason=reason,
            restored=False,
        )

        session.add(ignored_record)
        await session.commit()

        logger.info(
            f"已忽略调优建议: suggestion_id={suggestion_id}, "
            f"scope={scope.value}, param={param_name}"
        )

        return ignored_record

    async def restore_ignored_suggestion(
        self,
        ignored_suggestion_id: str,
        session: AsyncSession,
    ) -> Optional[RagEvalIgnoredSuggestion]:
        """恢复被忽略的建议

        Args:
            ignored_suggestion_id: 忽略记录ID
            session: 数据库会话

        Returns:
            恢复后的忽略记录或None
        """
        stmt = select(RagEvalIgnoredSuggestion).where(
            RagEvalIgnoredSuggestion.id == ignored_suggestion_id
        )
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()

        if not record:
            return None

        record.restored = True
        await session.commit()
        await session.refresh(record)

        logger.info(f"已恢复调优建议: ignored_id={ignored_suggestion_id}")

        return record
