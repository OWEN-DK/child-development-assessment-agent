"""监控 API 控制器"""

from fastapi import APIRouter, Query
from datetime import datetime, timedelta

from src.service.monitoring_service import MonitoringService
from src.service.alert_service import AlertService

router = APIRouter(prefix="/api/v1", tags=["Monitoring"])


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

    return {
        **stats,
        "alerts": [
            {"name": a.name, "message": a.message, "severity": a.severity}
            for a in alerts
        ],
    }


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

    return {"trend": trend, "metric": type}


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

    return {"distribution": distribution}


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

    return {"scenarios": stats}


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

    return {
        "test_name": test_name,
        "variants": variants,
        "comparison": comparison,
    }
