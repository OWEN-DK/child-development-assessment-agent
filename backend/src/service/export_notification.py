"""导出SSE通知辅助函数

为PDF/CSV/JSON导出任务提供独立的SSE通道推送功能。
与测试运行通道隔离，避免事件混淆。
"""

from datetime import datetime, timedelta
from typing import Optional

from fastapi.encoders import jsonable_encoder

from src.api.sse import SSEPublisher
from src.utils.logger import logger


async def notify_export_ready(
    user_id: str,
    task_id: str,
    report_id: str,
    download_url: str,
    file_size_bytes: int,
):
    """通知用户导出完成

    Args:
        user_id: 用户标识
        task_id: 导出任务ID
        report_id: 报告ID
        download_url: 下载链接
        file_size_bytes: 文件大小（字节）
    """
    try:
        await SSEPublisher.publish(
            f"exports:{user_id}",
            jsonable_encoder(
                {
                    "type": "export_ready",
                    "task_id": task_id,
                    "report_id": report_id,
                    "download_url": download_url,
                    "file_size_bytes": file_size_bytes,
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                }
            ),
        )
        logger.info(f"导出完成通知已发送: user_id={user_id}, task_id={task_id}")
    except Exception as e:
        logger.error(f"发送导出完成通知失败: {e}", exc_info=True)


async def notify_export_failed(
    user_id: str,
    task_id: str,
    report_id: str,
    error: str,
):
    """通知用户导出失败

    Args:
        user_id: 用户标识
        task_id: 导出任务ID
        report_id: 报告ID
        error: 错误信息
    """
    try:
        await SSEPublisher.publish(
            f"exports:{user_id}",
            jsonable_encoder(
                {
                    "type": "export_failed",
                    "task_id": task_id,
                    "report_id": report_id,
                    "error": error,
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                }
            ),
        )
        logger.info(f"导出失败通知已发送: user_id={user_id}, task_id={task_id}")
    except Exception as e:
        logger.error(f"发送导出失败通知失败: {e}", exc_info=True)


async def run_export_task(
    user_id: str,
    task_id: str,
    report_id: str,
    export_func,
):
    """导出异步任务包装器

    Args:
        user_id: 用户标识
        task_id: 导出任务ID
        report_id: 报告ID
        export_func: 实际执行导出的异步函数，应返回 (download_url, file_size_bytes)
    """
    try:
        # 1. 执行导出
        download_url, file_size_bytes = await export_func()

        # 2. 通知用户导出完成
        await notify_export_ready(
            user_id=user_id,
            task_id=task_id,
            report_id=report_id,
            download_url=download_url,
            file_size_bytes=file_size_bytes,
        )

    except Exception as e:
        # 导出失败也通知用户
        await notify_export_failed(
            user_id=user_id,
            task_id=task_id,
            report_id=report_id,
            error=str(e),
        )
