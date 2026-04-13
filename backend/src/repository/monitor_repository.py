from typing import List
from sqlalchemy import desc
from sqlalchemy.ext.asyncio import async_sessionmaker
from src.repository.base import BaseRepository
from src.models.monitor import LLMCallLog, ABTestMetrics


class LLMCallLogRepository(BaseRepository[LLMCallLog]):
    def __init__(self, db_session_factory: async_sessionmaker):
        super().__init__(LLMCallLog, db_session_factory)

    async def get_logs_by_request_id(self, request_id: str) -> List[LLMCallLog]:
        """根据请求ID查询日志"""
        return await self.get_by_filter(request_id=request_id)

    async def get_recent_logs(self, limit: int = 100) -> List[LLMCallLog]:
        """获取最近的日志"""
        return await self.get_all(
            skip=0, limit=limit, order_by=desc(LLMCallLog.created_at)
        )

    async def get_error_logs(self, skip: int = 0, limit: int = 50) -> List[LLMCallLog]:
        """获取失败日志

        注意: LLMCallStatus枚举值为success/failed/timeout，没有error
        """
        return await self.get_by_filter(
            skip=skip,
            limit=limit,
            order_by=desc(LLMCallLog.created_at),
            status="failed",
        )

    async def get_logs_by_status(
        self, status: str, skip: int = 0, limit: int = 50
    ) -> List[LLMCallLog]:
        """根据状态查询日志 (success/failed/timeout)"""
        return await self.get_by_filter(
            skip=skip,
            limit=limit,
            order_by=desc(LLMCallLog.created_at),
            status=status,
        )


class ABTestMetricRepository(BaseRepository[ABTestMetrics]):
    def __init__(self, db_session_factory: async_sessionmaker):
        super().__init__(ABTestMetrics, db_session_factory)

    async def get_metrics_by_test(self, test_name: str) -> List[ABTestMetrics]:
        """获取指定测试的所有指标"""
        return await self.get_by_filter(test_name=test_name)

    async def get_metrics_by_variant(
        self, test_name: str, variant_name: str
    ) -> List[ABTestMetrics]:
        """获取指定变体的指标"""
        return await self.get_by_filter(test_name=test_name, variant_name=variant_name)
