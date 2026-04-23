"""审计日志服务"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.rag_eval.audit_log import RagEvalAuditLog
from src.utils.logger import logger


class AuditLogService:
    """审计日志服务"""

    async def create_log(
        self,
        session: AsyncSession,
        operator: str,
        action: str,
        target_type: str,
        target_id: str,
        after_value: dict,
        before_value: Optional[dict] = None,
        diff_summary: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> RagEvalAuditLog:
        """创建审计日志"""
        log = RagEvalAuditLog(
            operator=operator,
            action=action,
            target_type=target_type,
            target_id=target_id,
            before_value=before_value,
            after_value=after_value,
            diff_summary=diff_summary,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        session.add(log)
        await session.commit()
        await session.refresh(log)

        logger.info(
            f"审计日志已创建: operator={operator}, action={action}, "
            f"target={target_type}:{target_id}"
        )

        return log

    async def query_logs(
        self,
        session: AsyncSession,
        operator: Optional[str] = None,
        action: Optional[str] = None,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[List[RagEvalAuditLog], int]:
        """查询审计日志（分页）"""
        stmt = select(RagEvalAuditLog)

        if operator:
            stmt = stmt.where(RagEvalAuditLog.operator == operator)
        if action:
            stmt = stmt.where(RagEvalAuditLog.action == action)
        if target_type:
            stmt = stmt.where(RagEvalAuditLog.target_type == target_type)
        if target_id:
            stmt = stmt.where(RagEvalAuditLog.target_id == target_id)
        if from_date:
            stmt = stmt.where(RagEvalAuditLog.created_at >= from_date)
        if to_date:
            stmt = stmt.where(RagEvalAuditLog.created_at <= to_date)

        # 统计总数
        count_stmt = select(func.count()).select_from(stmt.subquery())
        count_result = await session.execute(count_stmt)
        total = count_result.scalar() or 0

        # 分页查询
        offset = (page - 1) * page_size
        stmt = stmt.order_by(RagEvalAuditLog.created_at.desc())
        stmt = stmt.offset(offset).limit(page_size)

        result = await session.execute(stmt)
        logs = list(result.scalars().all())

        return logs, total

    async def get_log_by_id(
        self, session: AsyncSession, log_id: str
    ) -> Optional[RagEvalAuditLog]:
        """根据ID获取审计日志"""
        stmt = select(RagEvalAuditLog).where(RagEvalAuditLog.id == log_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()
