"""APScheduler 定时任务调度器

负责管理所有后台定时任务：
- 报告清理：每天凌晨 2 点清理 30 天前的过期报告
- 草稿清理：每天凌晨 3 点清理 7 天未审核的草稿
- 追踪数据清理：每天凌晨 4 点清理 30 天前的过期追踪数据
"""

from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.core.database import db_session_factory
from src.repository.test_case_repository import TestCaseDraftRepository
from src.service.rag_report_service import rag_report_service
from src.utils.logger import logger

scheduler = AsyncIOScheduler()


async def cleanup_expired_reports():
    """清理过期报告（保留 30 天）"""
    logger.info("开始执行过期报告清理任务...")
    try:
        await rag_report_service.cleanup_expired_reports(retention_days=30)
        logger.info("过期报告清理任务完成")
    except Exception as e:
        logger.error(f"过期报告清理任务失败: {e}")


async def cleanup_orphaned_drafts():
    """清理 7 天未审核的草稿"""
    logger.info("开始执行孤儿草稿清理任务...")
    try:
        draft_repo = TestCaseDraftRepository(db_session_factory)
        cutoff = datetime.now() - timedelta(days=7)

        # 查询 7 天前的草稿
        async with db_session_factory() as session:
            from sqlalchemy import select

            from src.schemas import TestCaseDraft, TestCaseStatus

            stmt = select(TestCaseDraft).where(
                TestCaseDraft.status == TestCaseStatus.DRAFT,
                TestCaseDraft.created_at < cutoff,
            )
            result = await session.execute(stmt)
            old_drafts = result.scalars().all()

            cleaned_count = 0
            for draft in old_drafts:
                try:
                    await draft_repo.delete(draft.id)
                    cleaned_count += 1
                except Exception as e:
                    logger.error(f"清理草稿 {draft.id} 失败: {e}")

            await session.commit()
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
