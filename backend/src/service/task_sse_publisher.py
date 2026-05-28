"""统一任务 SSE 发布器"""

from datetime import datetime, timezone
from typing import Any, Optional

from src.api.sse import SSEPublisher
from src.schemas.task import TaskSseEvent, TaskStatus
from src.utils.logger import logger


class TaskSsePublisher:
    """统一任务 SSE 发布器
    
    所有任务类型使用统一的 SSE 事件格式，前端只需一套消费逻辑。
    频道命名规范：{task_type}:{task_id}
    """

    @classmethod
    async def publish(
        cls,
        task_type: str,
        task_id: str,
        event_type: str,
        data: dict[str, Any],
    ) -> None:
        """发布统一格式 SSE 事件
        
        Args:
            task_type: 任务类型（upload/draft_generation/export/test_run）
            task_id: 任务 ID
            event_type: 事件类型（progress/complete/error/heartbeat）
            data: 事件数据（不包含 type/task_id/task_type/timestamp）
        """
        channel = f"{task_type}:{task_id}"
        payload = {
            "type": event_type,
            "task_id": task_id,
            "task_type": task_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **data,
        }
        
        try:
            await SSEPublisher.publish(channel, payload)
            logger.debug(
                f"SSE event published: type={event_type}, "
                f"task_type={task_type}, task_id={task_id}"
            )
        except Exception as e:
            logger.error(f"Failed to publish SSE event: {e}")

    @classmethod
    async def publish_progress(
        cls,
        task_type: str,
        task_id: str,
        status: TaskStatus = TaskStatus.RUNNING,
        progress: float = 0.0,
        stage: Optional[str] = None,
        message: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """发布进度事件"""
        data = {
            "status": status.value,
            "progress": progress,
        }
        if stage:
            data["stage"] = stage
        if message:
            data["message"] = message
        if metadata:
            data["metadata"] = metadata
        
        await cls.publish(task_type, task_id, "progress", data)

    @classmethod
    async def publish_complete(
        cls,
        task_type: str,
        task_id: str,
        result: Optional[dict[str, Any]] = None,
        message: Optional[str] = None,
    ) -> None:
        """发布完成事件"""
        data = {
            "status": TaskStatus.COMPLETED.value,
        }
        if result:
            data["result"] = result
        if message:
            data["message"] = message
        
        await cls.publish(task_type, task_id, "complete", data)

    @classmethod
    async def publish_error(
        cls,
        task_type: str,
        task_id: str,
        error: str,
        message: Optional[str] = None,
    ) -> None:
        """发布错误事件"""
        data = {
            "status": TaskStatus.FAILED.value,
            "error": error,
        }
        if message:
            data["message"] = message
        
        await cls.publish(task_type, task_id, "error", data)

    @classmethod
    async def publish_cancelled(
        cls,
        task_type: str,
        task_id: str,
    ) -> None:
        """发布取消事件"""
        data = {
            "status": TaskStatus.CANCELLED.value,
            "message": "任务已取消",
        }
        
        await cls.publish(task_type, task_id, "complete", data)

    @classmethod
    async def wait_for_subscriber(
        cls,
        task_type: str,
        task_id: str,
        timeout: float = None,
    ) -> bool:
        """等待 SSE 订阅者就绪，解决竞态条件"""
        channel = f"{task_type}:{task_id}"
        return await SSEPublisher.wait_for_subscriber(channel, timeout)

    @classmethod
    async def publish_heartbeat(
        cls,
        task_type: str,
        task_id: str,
    ) -> None:
        """发布心跳事件"""
        data = {
            "status": TaskStatus.RUNNING.value,
        }
        
        await cls.publish(task_type, task_id, "heartbeat", data)
