"""监控 API 控制器"""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import async_session_factory
from src.schemas.common import APIResponse
from src.service.alert_service import AlertService
from src.service.monitoring_service import MonitoringService
from src.service.trace_service import TraceService

router = APIRouter(prefix="/api/v1", tags=["Monitoring"])


async def get_db():
    async with async_session_factory() as session:
        yield session


@router.get("/monitoring/statistics")
async def get_statistics(
    days: int = Query(default=7, ge=1, le=30),
    model: str = None,
    scenario: str = None,
):
    """获取调用统计"""
    service = MonitoringService()

    end_time = datetime.now()
    start_time = end_time - timedelta(days=days)

    stats = await service.get_call_statistics(
        start_time=start_time,
        end_time=end_time,
        model_name=model,
        scenario=scenario,
    )

    alerts = AlertService.check_alerts(stats)

    return APIResponse.success(data={
        **stats,
        "alerts": [
            {"name": a.name, "message": a.message, "severity": a.severity}
            for a in alerts
        ],
    })


@router.get("/monitoring/trend")
async def get_trend(
    days: int = Query(default=7, ge=1, le=30),
    type: str = Query(default="calls", enum=["calls", "tokens", "duration"]),
):
    """获取趋势数据"""
    service = MonitoringService()

    end_time = datetime.now()
    start_time = end_time - timedelta(days=days)

    trend = await service.get_hourly_trend(
        start_time=start_time,
        end_time=end_time,
        metric=type,
    )

    return APIResponse.success(data={"trend": trend, "metric": type})


@router.get("/monitoring/model-distribution")
async def get_model_distribution(
    days: int = Query(default=7, ge=1, le=30),
):
    """获取模型分布"""
    service = MonitoringService()

    end_time = datetime.now()
    start_time = end_time - timedelta(days=days)

    distribution = await service.get_model_distribution(
        start_time=start_time,
        end_time=end_time,
    )

    return APIResponse.success(data={"distribution": distribution})


@router.get("/monitoring/scenarios")
async def get_scenario_statistics(
    days: int = Query(default=7, ge=1, le=30),
):
    """获取场景统计"""
    service = MonitoringService()

    end_time = datetime.now()
    start_time = end_time - timedelta(days=days)

    stats = await service.get_scenario_statistics(
        start_time=start_time,
        end_time=end_time,
    )

    return APIResponse.success(data={"scenarios": stats})


@router.get("/monitoring/ab-comparison")
async def get_ab_comparison(
    test_name: str,
    days: int = Query(default=7, ge=1, le=30),
):
    """A/B 测试 variant 对比"""
    service = MonitoringService()

    end_time = datetime.now()
    start_time = end_time - timedelta(days=days)

    variants = await service.get_ab_variant_stats(test_name, start_time, end_time)

    comparison = {}
    if len(variants) >= 2:
        variant_a = variants[0]
        variant_b = variants[1]
        comparison = {
            "precision_diff": variant_b.get("precision", 0)
            - variant_a.get("precision", 0),
            "recall_diff": variant_b.get("recall", 0) - variant_a.get("recall", 0),
            "f1_diff": variant_b.get("f1", 0) - variant_a.get("f1", 0),
            "avg_duration_diff": variant_b.get("avg_duration", 0)
            - variant_a.get("avg_duration", 0),
        }

    return APIResponse.success(data={
        "test_name": test_name,
        "variants": variants,
        "comparison": comparison,
    })


# ===== 追踪系统 API =====


@router.get("/monitoring/traces")
async def list_traces(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    status: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    trace_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """分页查询追踪列表"""
    service = TraceService()
    items, total = await service.list_traces(
        db, page, page_size, start_time, end_time, status, user_id, trace_id
    )
    return APIResponse.success(data={
        "items": [
            {
                "trace_id": item.trace_id,
                "name": item.name,
                "user_id": item.user_id,
                "status": item.status.value,
                "total_tokens": item.total_tokens,
                "total_duration_ms": item.total_duration_ms,
                "total_cost": str(item.total_cost) if item.total_cost else None,
                "created_at": item.created_at.isoformat() if item.created_at else None,
                "metadata": item.trace_metadata,
            }
            for item in items
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    })


@router.get("/monitoring/traces/{trace_id}")
async def get_trace_detail(
    trace_id: str,
    db: AsyncSession = Depends(get_db),
):
    """获取 Trace 详情，包含所有 Span"""
    service = TraceService()
    result = await service.get_trace_detail(db, trace_id)
    if not result:
        return APIResponse.success(data={"error": "Trace not found"})
    return APIResponse.success(data=result)


@router.get("/monitoring/traces/{trace_id}/spans/{span_id}")
async def get_span_detail(
    trace_id: str,
    span_id: str,
    db: AsyncSession = Depends(get_db),
):
    """获取单个 Span 详情"""
    service = TraceService()
    result = await service.get_span_detail(db, trace_id, span_id)
    if not result:
        return APIResponse.success(data={"error": "Span not found"})
    return APIResponse.success(data=result)


@router.get("/monitoring/logs")
async def list_llm_call_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    trace_id: Optional[str] = Query(None),
    model: Optional[str] = Query(None),
    level: Optional[str] = Query(None),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """分页查询 LLM 调用日志"""
    service = TraceService()
    items, total = await service.list_llm_call_logs(
        db, page, page_size, trace_id, model, level, start_time, end_time
    )
    return APIResponse.success(data={
        "items": [
            {
                "id": item.id,
                "trace_id": item.trace_id,
                "span_id": item.span_id,
                "model_name": item.model_name,
                "tokens": item.tokens,
                "cost": str(item.cost) if item.cost else None,
                "level": item.level.value,
                "created_at": item.created_at.isoformat() if item.created_at else None,
            }
            for item in items
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    })


@router.get("/monitoring/logs/{request_id}")
async def get_llm_call_log_detail(
    request_id: str,
    db: AsyncSession = Depends(get_db),
):
    """获取单次 LLM 调用的详细信息"""
    service = TraceService()
    result = await service.get_llm_call_log_detail(db, request_id)
    if not result:
        return APIResponse.success(data={"error": "LLM call log not found"})
    return APIResponse.success(data=result)


@router.get("/monitoring/cost")
async def get_cost_analysis(
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """成本分析"""
    service = TraceService()
    return APIResponse.success(data=await service.get_cost_analysis(db, start_time, end_time))


@router.get("/monitoring/latency")
async def get_latency_distribution(
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """延迟分布"""
    service = TraceService()
    return APIResponse.success(data=await service.get_latency_distribution(db, start_time, end_time))


@router.get("/monitoring/errors")
async def get_error_analysis(
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """错误分析"""
    service = TraceService()
    return APIResponse.success(data=await service.get_error_analysis(db, start_time, end_time))
