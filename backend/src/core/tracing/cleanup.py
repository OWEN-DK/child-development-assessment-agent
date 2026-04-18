"""TTL 自动清理任务

支持按时间自动清理过期追踪数据（默认保留 30 天）。
"""

import logging
from datetime import datetime, timedelta

from sqlalchemy import delete, select

from src.core.database import async_session_factory
from src.models.monitor import LLMCallLog
from src.models.trace import Trace

logger = logging.getLogger(__name__)


async def cleanup_expired_traces(
    retention_days: int = 30,
    batch_size: int = 1000,
    dry_run: bool = False,
) -> int:
    """清理过期 Trace 数据

    Args:
        retention_days: 保留天数
        batch_size: 单次处理批次大小
        dry_run: 是否仅模拟执行

    Returns:
        删除的记录数
    """
    cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
    total_deleted = 0

    async with async_session_factory() as session:
        async with session.begin():
            expired_traces_result = await session.execute(
                select(Trace.trace_id)
                .filter(Trace.created_at < cutoff_date)
                .limit(batch_size)
            )
            expired_traces = expired_traces_result.scalars().all()

            if not expired_traces:
                return 0

            expired_ids = list(expired_traces)

            if not dry_run:
                await session.execute(
                    delete(LLMCallLog).where(LLMCallLog.trace_id.in_(expired_ids))
                )
                await session.execute(
                    delete(Trace).where(Trace.trace_id.in_(expired_ids))
                )

            total_deleted = len(expired_ids)

    logger.info(
        f"清理过期追踪数据: {'模拟' if dry_run else '实际'}删除 {total_deleted} 条记录"
    )
    return total_deleted
