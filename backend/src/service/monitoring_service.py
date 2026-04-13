"""RAG 监控服务 - 采集和上报 RAG 系统运行指标"""

import time
import threading
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy import select, func, and_
from sqlalchemy.orm import aliased

from src.core.database import db_session_factory
from src.models.monitor import LLMCallLog, LLMCallStatus, ABTestMetrics
from src.core.prometheus_metrics import (
    LLM_CALLS_TOTAL,
    LLM_CALL_DURATION,
    LLM_TOKENS_TOTAL,
)
from src.config import settings
from src.utils.logger import logger


@dataclass
class MetricPoint:
    name: str
    value: float
    timestamp: float
    tags: Dict[str, str] = field(default_factory=dict)


class MonitoringService:
    """RAG 监控服务"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.metrics: List[MetricPoint] = []
        self.enabled = settings.rag_monitoring_enabled
        self.db_session_factory = db_session_factory
        self._llm_log_repo = None
        self._ab_metric_repo = None
        self._initialized = True

    def _get_repos(self):
        """懒加载Repository实例"""
        if self._llm_log_repo is None:
            from src.repository import LLMCallLogRepository, ABTestMetricRepository

            self._llm_log_repo = LLMCallLogRepository(self.db_session_factory)
            self._ab_metric_repo = ABTestMetricRepository(self.db_session_factory)
        return self._llm_log_repo, self._ab_metric_repo

    def record_metric(self, name: str, value: float, tags: Dict[str, str] = None):
        """记录内存指标"""
        if not self.enabled:
            return
        point = MetricPoint(
            name=name,
            value=value,
            timestamp=time.time(),
            tags=tags or {},
        )
        self.metrics.append(point)
        logger.debug(f"Metric recorded: {name}={value} {tags}")

    def get_metrics(self, name: str = None, since: float = None) -> List[MetricPoint]:
        """获取内存指标"""
        result = self.metrics
        if name:
            result = [m for m in result if m.name == name]
        if since:
            result = [m for m in result if m.timestamp >= since]
        return result

    def get_latest(self, name: str) -> Optional[MetricPoint]:
        """获取最新内存指标值"""
        metrics = [m for m in self.metrics if m.name == name]
        return max(metrics, key=lambda m: m.timestamp) if metrics else None

    async def log_llm_call(
        self,
        request_id: str,
        model_name: str,
        prompt_key: str = None,
        prompt_version: str = None,
        scenario: str = None,
        input_tokens: int = None,
        output_tokens: int = None,
        total_tokens: int = None,
        duration_ms: int = None,
        status: str = "success",
        error_message: str = None,
    ):
        """记录 LLM 调用日志到数据库并上报 Prometheus"""
        llm_log_repo, _ = self._get_repos()
        await llm_log_repo.create(
            {
                "request_id": request_id,
                "prompt_key": prompt_key,
                "prompt_version": prompt_version,
                "scenario": scenario,
                "model_name": model_name,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
                "duration_ms": duration_ms,
                "status": status,
                "error_message": error_message,
            }
        )

        LLM_CALLS_TOTAL.labels(
            model=model_name,
            scenario=scenario or "unknown",
            status=status,
        ).inc()

        if duration_ms:
            LLM_CALL_DURATION.labels(
                model=model_name,
                scenario=scenario or "unknown",
            ).observe(duration_ms / 1000.0)

        if input_tokens:
            LLM_TOKENS_TOTAL.labels(
                model=model_name,
                scenario=scenario or "unknown",
                type="input",
            ).inc(input_tokens)

        if output_tokens:
            LLM_TOKENS_TOTAL.labels(
                model=model_name,
                scenario=scenario or "unknown",
                type="output",
            ).inc(output_tokens)

        logger.debug(f"LLM 调用日志已记录：{request_id}")

    async def get_call_statistics(
        self,
        start_time: datetime,
        end_time: datetime,
        model_name: str = None,
        scenario: str = None,
    ) -> dict:
        """获取调用统计"""
        async with self.db_session_factory() as session:
            filters = [
                LLMCallLog.created_at >= start_time,
                LLMCallLog.created_at <= end_time,
            ]
            if model_name:
                filters.append(LLMCallLog.model_name == model_name)
            if scenario:
                filters.append(LLMCallLog.scenario == scenario)

            total_result = await session.execute(
                select(func.count()).select_from(LLMCallLog).where(and_(*filters))
            )
            total_calls = total_result.scalar() or 0

            status_result = await session.execute(
                select(LLMCallLog.status, func.count().label("count"))
                .where(and_(*filters))
                .group_by(LLMCallLog.status)
            )
            status_counts = {
                row[0].value if hasattr(row[0], "value") else row[0]: row[1]
                for row in status_result.all()
            }

            token_result = await session.execute(
                select(
                    func.sum(LLMCallLog.input_tokens).label("input_tokens"),
                    func.sum(LLMCallLog.output_tokens).label("output_tokens"),
                    func.sum(LLMCallLog.total_tokens).label("total_tokens"),
                ).where(and_(*filters))
            )
            token_stats = token_result.one()

            duration_result = await session.execute(
                select(
                    func.avg(LLMCallLog.duration_ms).label("avg_duration"),
                    func.max(LLMCallLog.duration_ms).label("max_duration"),
                    func.min(LLMCallLog.duration_ms).label("min_duration"),
                ).where(and_(*filters))
            )
            duration_stats = duration_result.one()

            failed_count = status_counts.get("failed", 0)
            timeout_count = status_counts.get("timeout", 0)

            return {
                "total_calls": total_calls,
                "success_count": status_counts.get("success", 0),
                "failed_count": failed_count,
                "timeout_count": timeout_count,
                "error_rate": (failed_count + timeout_count) / total_calls
                if total_calls > 0
                else 0,
                "input_tokens": token_stats.input_tokens or 0,
                "output_tokens": token_stats.output_tokens or 0,
                "total_tokens": token_stats.total_tokens or 0,
                "avg_duration_ms": int(duration_stats.avg_duration or 0),
                "max_duration_ms": int(duration_stats.max_duration or 0),
                "min_duration_ms": int(duration_stats.min_duration or 0),
            }

    async def get_hourly_trend(
        self,
        start_time: datetime,
        end_time: datetime,
        metric: str = "calls",
    ) -> list[dict]:
        """获取小时级趋势"""
        async with self.db_session_factory() as session:
            filters = [
                LLMCallLog.created_at >= start_time,
                LLMCallLog.created_at <= end_time,
            ]

            if metric == "calls":
                stmt = (
                    select(
                        func.date_format(
                            LLMCallLog.created_at, "%Y-%m-%d %H:00:00"
                        ).label("hour"),
                        func.count().label("value"),
                    )
                    .where(and_(*filters))
                    .group_by(
                        func.date_format(LLMCallLog.created_at, "%Y-%m-%d %H:00:00")
                    )
                    .order_by(
                        func.date_format(LLMCallLog.created_at, "%Y-%m-%d %H:00:00")
                    )
                )
            elif metric == "tokens":
                stmt = (
                    select(
                        func.date_format(
                            LLMCallLog.created_at, "%Y-%m-%d %H:00:00"
                        ).label("hour"),
                        func.sum(LLMCallLog.total_tokens).label("value"),
                    )
                    .where(and_(*filters))
                    .group_by(
                        func.date_format(LLMCallLog.created_at, "%Y-%m-%d %H:00:00")
                    )
                    .order_by(
                        func.date_format(LLMCallLog.created_at, "%Y-%m-%d %H:00:00")
                    )
                )
            elif metric == "duration":
                stmt = (
                    select(
                        func.date_format(
                            LLMCallLog.created_at, "%Y-%m-%d %H:00:00"
                        ).label("hour"),
                        func.avg(LLMCallLog.duration_ms).label("value"),
                    )
                    .where(and_(*filters))
                    .group_by(
                        func.date_format(LLMCallLog.created_at, "%Y-%m-%d %H:00:00")
                    )
                    .order_by(
                        func.date_format(LLMCallLog.created_at, "%Y-%m-%d %H:00:00")
                    )
                )
            else:
                return []

            result = await session.execute(stmt)
            return [{"hour": row[0], "value": row[1]} for row in result.all()]

    async def get_model_distribution(
        self,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict]:
        """获取模型使用分布"""
        async with self.db_session_factory() as session:
            stmt = (
                select(
                    LLMCallLog.model_name,
                    func.count().label("count"),
                    func.sum(LLMCallLog.total_tokens).label("total_tokens"),
                )
                .where(
                    and_(
                        LLMCallLog.created_at >= start_time,
                        LLMCallLog.created_at <= end_time,
                    )
                )
                .group_by(LLMCallLog.model_name)
                .order_by(func.count().desc())
            )

            result = await session.execute(stmt)
            return [
                {
                    "model_name": row[0],
                    "count": row[1],
                    "total_tokens": row[2] or 0,
                }
                for row in result.all()
            ]

    async def get_scenario_statistics(
        self,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict]:
        """获取场景统计"""
        async with self.db_session_factory() as session:
            stmt = (
                select(
                    LLMCallLog.scenario,
                    func.count().label("count"),
                    func.avg(LLMCallLog.duration_ms).label("avg_duration"),
                    func.sum(LLMCallLog.total_tokens).label("total_tokens"),
                )
                .where(
                    and_(
                        LLMCallLog.created_at >= start_time,
                        LLMCallLog.created_at <= end_time,
                    )
                )
                .group_by(LLMCallLog.scenario)
                .order_by(func.count().desc())
            )

            result = await session.execute(stmt)
            return [
                {
                    "scenario": row[0],
                    "count": row[1],
                    "avg_duration_ms": int(row[2] or 0),
                    "total_tokens": row[3] or 0,
                }
                for row in result.all()
            ]

    async def get_ab_variant_stats(
        self,
        test_name: str,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict]:
        """获取 A/B 测试各 variant 的指标"""
        async with self.db_session_factory() as session:
            stmt = (
                select(
                    ABTestMetrics.variant_name,
                    ABTestMetrics.metric_type,
                    func.avg(ABTestMetrics.metric_value).label("avg_value"),
                    func.count().label("count"),
                )
                .where(
                    and_(
                        ABTestMetrics.test_name == test_name,
                        ABTestMetrics.recorded_at >= start_time,
                        ABTestMetrics.recorded_at <= end_time,
                    )
                )
                .group_by(
                    ABTestMetrics.variant_name,
                    ABTestMetrics.metric_type,
                )
                .order_by(ABTestMetrics.variant_name)
            )

            result = await session.execute(stmt)
            variants = {}
            for row in result.all():
                variant = row[0]
                metric_type = row[1]
                avg_value = float(row[2])

                if variant not in variants:
                    variants[variant] = {"variant_name": variant}
                variants[variant][metric_type] = avg_value

            return list(variants.values())


monitoring_service = MonitoringService()
