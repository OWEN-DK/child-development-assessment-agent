"""调优建议服务

负责获取、忽略调优建议等业务逻辑
"""

from typing import List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.rag_eval.tuning_suggestion import RagEvalTuningSuggestionRecord
from src.models.rag_eval.ignored_suggestion import RagEvalIgnoredSuggestion
from src.models.rag_eval.enums import RagEvalIgnoreScope, RagEvalIgnoredSuggestionType
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
