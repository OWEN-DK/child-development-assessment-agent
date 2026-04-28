"""APScheduler 定时任务调度器

负责管理所有后台定时任务：
- 报告清理：每天凌晨 2 点清理 30 天前的过期报告
- 草稿清理：每天凌晨 3 点清理 7 天未审核的草稿
- 追踪数据清理：每天凌晨 4 点清理 30 天前的过期追踪数据
"""

from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.utils.logger import logger

scheduler = AsyncIOScheduler()
_scheduler_ever_started = False


async def cleanup_expired_reports():
    """清理过期报告（保留 30 天）"""
    from src.core.di_container import injector
    from src.service.rag_eval.report.facade import ReportEngineFacade
    
    logger.info("开始执行过期报告清理任务...")
    try:
        facade = injector.get(ReportEngineFacade)
        cleaned_count = await facade.cleanup_expired_reports(retention_days=30)
        logger.info(f"过期报告清理任务完成，共删除 {cleaned_count} 个报告")
    except Exception as e:
        logger.error(f"过期报告清理任务失败: {e}")


async def cleanup_orphaned_drafts():
    """清理 7 天未审核的草稿"""
    from src.core.di_container import injector
    from src.service.rag_eval.draft.facade import DraftEngineFacade
    
    logger.info("开始执行孤儿草稿清理任务...")
    try:
        facade = injector.get(DraftEngineFacade)
        cleaned_count = await facade.cleanup_orphaned_drafts(retention_days=7)
        logger.info(f"孤儿草稿清理完成，共删除 {cleaned_count} 个草稿")
    except Exception as e:
        logger.error(f"孤儿草稿清理任务失败: {e}")


async def cleanup_expired_traces():
    """清理过期追踪数据（保留 30 天）"""
    logger.info("开始执行过期追踪数据清理任务...")
    try:
        from src.core.tracing.cleanup import \
            cleanup_expired_traces as cleanup_traces

        deleted = await cleanup_traces(retention_days=30, batch_size=1000)
        logger.info(f"过期追踪数据清理完成，共删除 {deleted} 条记录")
    except Exception as e:
        logger.error(f"过期追踪数据清理任务失败: {e}")


def start_scheduler():
    """启动定时任务调度器"""
    global _scheduler_ever_started
    if _scheduler_ever_started:
        logger.debug("APScheduler 已初始化过，跳过重复启动")
        return
    _scheduler_ever_started = True

    # 每天凌晨 2 点清理过期报告
    scheduler.add_job(
        cleanup_expired_reports,
        CronTrigger(hour=2, minute=0),
        id="cleanup_expired_reports",
        name="清理过期报告",
        replace_existing=True,
        max_instances=1,
    )

    # 每天凌晨 3 点清理孤儿草稿
    scheduler.add_job(
        cleanup_orphaned_drafts,
        CronTrigger(hour=3, minute=0),
        id="cleanup_orphaned_drafts",
        name="清理孤儿草稿",
        replace_existing=True,
        max_instances=1,
    )

    # 每天凌晨 4 点清理过期追踪数据
    scheduler.add_job(
        cleanup_expired_traces,
        CronTrigger(hour=4, minute=0),
        id="cleanup_expired_traces",
        name="清理过期追踪数据",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.start()
    logger.info("APScheduler 定时任务调度器已启动")
    logger.info("  - 清理过期报告: 每天 02:00")
    logger.info("  - 清理孤儿草稿: 每天 03:00")
    logger.info("  - 清理过期追踪数据: 每天 04:00")


def stop_scheduler():
    """停止定时任务调度器"""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler 定时任务调度器已关闭")
