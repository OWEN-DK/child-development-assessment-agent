"""追踪数据服务层"""

from datetime import datetime
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.monitor import CallLevel, LLMCallLog
from src.models.trace import Trace, TraceStatus
from src.utils.serializers import safe_enum_value


class TraceService:
    async def list_traces(
        self,
        session: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        status: Optional[str] = None,
        user_id: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> tuple[list[Trace], int]:
        """分页查询 Trace 列表"""
        query = select(Trace)

        if start_time:
            query = query.where(Trace.created_at >= start_time)
        if end_time:
            query = query.where(Trace.created_at <= end_time)
        if status:
            query = query.where(Trace.status == status)
        if user_id:
            query = query.where(Trace.user_id == user_id)
        if trace_id:
            query = query.where(Trace.trace_id == trace_id)

        count_query = select(func.count()).select_from(query.subquery())
        total_result = await session.execute(count_query)
        total = total_result.scalar() or 0

        items_query = (
            query.order_by(Trace.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items_result = await session.execute(items_query)
        items = items_result.scalars().all()

        return list(items), total

    async def get_trace_detail(
        self, session: AsyncSession, trace_id: str
    ) -> Optional[dict]:
        """获取 Trace 详情，包含所有 Span"""
        trace_result = await session.execute(
            select(Trace).where(Trace.trace_id == trace_id)
        )
        trace = trace_result.scalar_one_or_none()
        if not trace:
            return None

        spans_result = await session.execute(
            select(LLMCallLog).where(LLMCallLog.trace_id == trace_id)
        )
        spans = spans_result.scalars().all()

        return {
            "trace_id": trace.trace_id,
            "name": trace.name,
            "user_id": trace.user_id,
            "session_id": trace.session_id,
            "metadata": trace.trace_metadata,
            "start_time": trace.start_time.isoformat() if trace.start_time else None,
            "end_time": trace.end_time.isoformat() if trace.end_time else None,
            "total_duration_ms": trace.total_duration_ms,
            "total_tokens": trace.total_tokens,
            "total_cost": str(trace.total_cost) if trace.total_cost else None,
            "status": trace.status.value,
            "created_at": trace.created_at.isoformat() if trace.created_at else None,
            "spans": [self._span_to_dict(span) for span in spans],
        }

    async def get_span_detail(
        self, session: AsyncSession, trace_id: str, span_id: str
    ) -> Optional[dict]:
        """获取单个 Span 详情"""
        log_result = await session.execute(
            select(LLMCallLog).where(
                LLMCallLog.trace_id == trace_id,
                LLMCallLog.span_id == span_id,
            )
        )
        span = log_result.scalar_one_or_none()
        if not span:
            return None

        return self._span_to_dict(span)

    def _span_to_dict(self, span: LLMCallLog) -> dict:
        call_params = span.call_parameters or {}
        level_val = safe_enum_value(span.level)
        return {
            "span_id": span.span_id,
            "parent_span_id": span.parent_span_id,
            "name": call_params.get("scene", call_params.get("node_name", "unknown")),
            "duration_ms": call_params.get(
                "duration_ms", span.completion_start_time_ms
            ),
            "tokens": span.tokens,
            "status": "success" if level_val == "INFO" else "error",
            "prompt_messages": span.prompt_messages,
            "completion_message": span.completion_message,
            "call_parameters": span.call_parameters,
            "error": call_params.get("error") if level_val == "ERROR" else None,
        }

    async def list_llm_call_logs(
        self,
        session: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        trace_id: Optional[str] = None,
        model: Optional[str] = None,
        level: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> tuple[list[LLMCallLog], int]:
        """分页查询 LLM 调用日志"""
        query = select(LLMCallLog)

        if trace_id:
            query = query.where(LLMCallLog.trace_id == trace_id)
        if model:
            query = query.where(
                LLMCallLog.call_parameters["model"].as_string() == model
            )
        if level:
            query = query.where(LLMCallLog.level == level)
        if start_time:
            query = query.where(LLMCallLog.created_at >= start_time)
        if end_time:
            query = query.where(LLMCallLog.created_at <= end_time)

        count_query = select(func.count()).select_from(query.subquery())
        total_result = await session.execute(count_query)
        total = total_result.scalar() or 0

        items_query = (
            query.order_by(LLMCallLog.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items_result = await session.execute(items_query)
        items = items_result.scalars().all()

        return list(items), total

    async def get_llm_call_log_detail(
        self, session: AsyncSession, request_id: str
    ) -> Optional[dict]:
        """获取单次 LLM 调用的详细信息"""
        log_result = await session.execute(
            select(LLMCallLog).where(
                (LLMCallLog.span_id == request_id)
                | (LLMCallLog.id == int(request_id) if request_id.isdigit() else False)
            )
        )
        log = log_result.scalar_one_or_none()
        if not log:
            return None

        return {
            "id": log.id,
            "trace_id": log.trace_id,
            "span_id": log.span_id,
            "parent_span_id": log.parent_span_id,
            "prompt_messages": log.prompt_messages,
            "completion_message": log.completion_message,
            "call_parameters": log.call_parameters,
            "model_parameters": log.model_parameters,
            "tokens": log.tokens,
            "cost": str(log.cost) if log.cost else None,
            "tags": log.tags,
            "completion_start_time_ms": log.completion_start_time_ms,
            "level": log.level.value,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }

    async def get_cost_analysis(
        self,
        session: AsyncSession,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> dict:
        """成本分析"""
        query = select(LLMCallLog)
        if start_time:
            query = query.where(LLMCallLog.created_at >= start_time)
        if end_time:
            query = query.where(LLMCallLog.created_at <= end_time)

        result = await session.execute(query)
        logs = result.scalars().all()

        total_cost = sum(float(log.cost) for log in logs if log.cost)
        total_tokens = sum(log.tokens or 0 for log in logs)
        total_calls = len(logs)

        model_stats: dict[str, dict] = {}
        for log in logs:
            model = (
                log.call_parameters.get("model", "unknown")
                if log.call_parameters
                else "unknown"
            )
            if model not in model_stats:
                model_stats[model] = {
                    "model": model,
                    "calls": 0,
                    "tokens": 0,
                    "cost": 0,
                }
            model_stats[model]["calls"] += 1
            model_stats[model]["tokens"] += log.tokens or 0
            if log.cost:
                model_stats[model]["cost"] += float(log.cost)

        return {
            "total_cost": str(total_cost),
            "total_tokens": total_tokens,
            "total_calls": total_calls,
            "avg_cost_per_call": str(total_cost / total_calls)
            if total_calls > 0
            else "0",
            "model_stats": list(model_stats.values()),
        }

    async def get_latency_distribution(
        self,
        session: AsyncSession,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> dict:
        """延迟分布"""
        query = select(Trace.total_duration_ms).where(
            Trace.total_duration_ms.isnot(None)
        )
        if start_time:
            query = query.where(Trace.created_at >= start_time)
        if end_time:
            query = query.where(Trace.created_at <= end_time)

        result = await session.execute(query)
        durations = [d[0] for d in result.all()]
        if not durations:
            return {"p50": 0, "p95": 0, "p99": 0, "avg": 0, "min": 0, "max": 0}

        durations.sort()

        def percentile(data, p):
            idx = int(len(data) * p / 100)
            return data[min(idx, len(data) - 1)]

        return {
            "p50": percentile(durations, 50),
            "p95": percentile(durations, 95),
            "p99": percentile(durations, 99),
            "avg": sum(durations) / len(durations),
            "min": durations[0],
            "max": durations[-1],
        }

    async def get_error_analysis(
        self,
        session: AsyncSession,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> dict:
        """错误分析"""
        query = select(LLMCallLog).where(LLMCallLog.level == CallLevel.ERROR)
        if start_time:
            query = query.where(LLMCallLog.created_at >= start_time)
        if end_time:
            query = query.where(LLMCallLog.created_at <= end_time)

        result = await session.execute(query)
        errors = result.scalars().all()

        error_types: dict[str, dict] = {}
        for error in errors:
            error_msg = (
                error.call_parameters.get("error", "unknown")
                if error.call_parameters
                else "unknown"
            )
            error_type = error_msg.split(":")[0] if ":" in error_msg else error_msg
            if error_type not in error_types:
                error_types[error_type] = {
                    "type": error_type,
                    "count": 0,
                    "examples": [],
                }
            error_types[error_type]["count"] += 1
            if len(error_types[error_type]["examples"]) < 3:
                error_types[error_type]["examples"].append(
                    {
                        "trace_id": error.trace_id,
                        "span_id": error.span_id,
                        "message": error_msg,
                    }
                )

        return {
            "total_errors": len(errors),
            "error_types": list(error_types.values()),
        }
