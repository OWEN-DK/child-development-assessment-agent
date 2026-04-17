"""趋势数据控制器

提供趋势数据查询 API，支持单指标和多指标查询。
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List

from src.core.database import db_session_factory
from src.service import trend_service
from src.utils.logger import logger

router = APIRouter(prefix="/api/v1/rag/test", tags=["RAG Eval Trend"])


@router.get("/trends/{test_set_id}")
async def get_trend(
    test_set_id: str,
    metric: str = Query("f1", description="指标名称: precision/recall/f1/mrr/ndcg"),
    days: int = Query(30, ge=1, le=365, description="回溯天数"),
):
    """获取趋势数据

    按配置版本聚合测试运行结果，返回指定指标的趋势数据。
    """
    try:
        async with db_session_factory() as session:
            trend_data = await trend_service.get_trend_data(
                session=session,
                test_set_id=test_set_id,
                metric=metric,
                days=days,
            )
            return {
                "status": "success",
                "test_set_id": test_set_id,
                "metric": metric,
                "days": days,
                "data": trend_data,
            }
    except Exception as e:
        logger.error(f"获取趋势数据失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取趋势数据失败: {str(e)}")


@router.get("/trends/{test_set_id}/multi")
async def get_multi_metric_trend(
    test_set_id: str,
    metrics: str = Query(
        "f1,precision,recall",
        description="逗号分隔的指标列表",
    ),
    days: int = Query(30, ge=1, le=365, description="回溯天数"),
):
    """获取多指标趋势数据

    一次性返回多个指标的趋势数据，避免多次查询。
    """
    try:
        metrics_list = [m.strip() for m in metrics.split(",") if m.strip()]
        if not metrics_list:
            raise HTTPException(status_code=400, detail="指标列表不能为空")

        async with db_session_factory() as session:
            trend_data = await trend_service.get_multi_metric_trend(
                session=session,
                test_set_id=test_set_id,
                metrics=metrics_list,
                days=days,
            )
            return {
                "status": "success",
                "test_set_id": test_set_id,
                "metrics": metrics_list,
                "days": days,
                "data": trend_data,
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取多指标趋势数据失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取多指标趋势数据失败: {str(e)}")
