"""趋势数据服务

负责聚合测试运行数据，按配置版本分组统计指标趋势。
"""

from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.rag_eval.test_run import RagEvalTestRun
from src.models.rag_eval.test_run_result import RagEvalTestRunResult
from src.models.rag_eval.config_version import RagEvalConfigVersion
from src.models.rag_eval.config_change_set import RagEvalConfigChangeSet
from src.utils.logger import logger


async def get_trend_data(
    session: AsyncSession,
    test_set_id: str,
    metric: str = "overall_f1",
    days: int = 30,
) -> List[dict]:
    """获取趋势数据

    按配置版本聚合测试运行结果，返回每个版本的指标统计信息。

    Args:
        session: 数据库会话
        test_set_id: 测试集ID
        metric: 指标名称 (precision/recall/f1/mrr/ndcg)
        days: 回溯天数

    Returns:
        趋势数据列表，每个元素包含版本信息和指标统计
    """
    cutoff_date = datetime.utcnow() - timedelta(days=days)

    # 映射前端指标名到数据库字段
    metric_field_map = {
        "precision": "overall_precision",
        "recall": "overall_recall",
        "f1": "overall_f1",
        "mrr": "overall_mrr",
        "ndcg": "overall_ndcg",
    }
    db_field = metric_field_map.get(metric, "overall_f1")

    # 查询指定测试集在时间范围内的已完成运行
    stmt = (
        select(RagEvalTestRun)
        .where(
            and_(
                RagEvalTestRun.test_set_id == test_set_id,
                RagEvalTestRun.status == "completed",
                RagEvalTestRun.created_at >= cutoff_date,
                RagEvalTestRun.config_version_id.isnot(None),
            )
        )
        .options(selectinload(RagEvalTestRun.config_version))
        .order_by(RagEvalTestRun.created_at.asc())
    )

    result = await session.execute(stmt)
    runs = result.scalars().all()

    # 按配置版本分组
    version_runs: dict[str, list] = {}
    for run in runs:
        version_id = run.config_version_id
        if version_id not in version_runs:
            version_runs[version_id] = []
        version_runs[version_id].append(run)

    # 获取所有相关的 ConfigChangeSet
    config_version_ids = list(version_runs.keys())
    change_sets_map: dict[str, list] = {}
    if config_version_ids:
        cs_stmt = select(RagEvalConfigChangeSet).where(
            RagEvalConfigChangeSet.config_version_id.in_(config_version_ids)
        )
        cs_result = await session.execute(cs_stmt)
        change_sets = cs_result.scalars().all()
        for cs in change_sets:
            if cs.config_version_id not in change_sets_map:
                change_sets_map[cs.config_version_id] = []
            change_sets_map[cs.config_version_id].append(cs)

    # 聚合每个版本的数据
    trend_data = []
    for version_id, runs_list in version_runs.items():
        # 提取指标值
        values = []
        run_details = []
        for run in runs_list:
            value = getattr(run, db_field, None)
            if value is not None:
                values.append(value)
                run_details.append(
                    {
                        "run_id": run.id,
                        "value": value,
                        "started_at": run.created_at.isoformat()
                        if run.created_at
                        else None,
                    }
                )

        if not values:
            continue

        # 获取配置版本信息
        config_version = runs_list[0].config_version
        version_label = config_version.version_label if config_version else "unknown"
        created_at = (
            config_version.created_at.isoformat()
            if config_version and config_version.created_at
            else None
        )

        # 获取关联的变更集
        config_changes = []
        if version_id in change_sets_map:
            for cs in change_sets_map[version_id]:
                config_changes.append(
                    {
                        "change_set_id": cs.id,
                        "change_set_label": cs.change_set_label,
                        "status": cs.status.value if cs.status else "unknown",
                        "rollback_reason": cs.rollback_reason,
                        "created_at": cs.created_at.isoformat()
                        if cs.created_at
                        else None,
                    }
                )

        trend_data.append(
            {
                "version_id": version_id,
                "version_label": version_label,
                "created_at": created_at,
                "run_count": len(runs_list),
                "mean": sum(values) / len(values),
                "min": min(values),
                "max": max(values),
                "runs": run_details,
                "config_changes": config_changes,
            }
        )

    # 按创建时间排序
    trend_data.sort(key=lambda x: x["created_at"] or "")

    logger.info(
        f"趋势数据获取完成: test_set={test_set_id}, metric={metric}, versions={len(trend_data)}"
    )
    return trend_data


async def get_multi_metric_trend(
    session: AsyncSession,
    test_set_id: str,
    metrics: List[str],
    days: int = 30,
) -> dict:
    """获取多指标趋势数据

    一次性返回多个指标的趋势数据，避免多次查询。

    Args:
        session: 数据库会话
        test_set_id: 测试集ID
        metrics: 指标列表
        days: 回溯天数

    Returns:
        以指标名为key的趋势数据字典
    """
    result = {}
    for metric in metrics:
        result[metric] = await get_trend_data(session, test_set_id, metric, days)
    return result
