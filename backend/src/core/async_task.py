import asyncio
import uuid
from typing import Callable, Awaitable, Any, Optional
from fastapi.encoders import jsonable_encoder
from src.api.sse import SSEPublisher
from src.utils.logger import logger


class AsyncTaskManager:
    """通用异步任务管理器（内置SSE进度推送能力）
    所有需要后台运行+实时进度推送的任务都可以用这个工具类实现，无需重复写样板代码
    """

    # 强引用集合，防止任务被 GC 回收
    _active_tasks: dict[str, asyncio.Task] = {}

    @classmethod
    async def start_task(
        cls,
        task_type: str,
        task_func: Callable[..., Awaitable[Any]],
        *args,
        progress_callback: Optional[Callable[[int, int, str], Awaitable[None]]] = None,
        **kwargs,
    ) -> str:
        """启动异步后台任务
        Args:
            task_type: 任务类型（用于SSE频道前缀，比如draft_generation、document_import、model_training）
            task_func: 实际的业务执行函数，需要是async函数，并且支持接收progress_callback参数（如果需要进度）
            *args: 传给task_func的位置参数
            progress_callback: 自定义进度回调，如果不传则使用默认的SSE推送回调
            **kwargs: 传给task_func的关键字参数
        Returns:
            task_id: 生成的任务ID，用于前端监听SSE进度
        """
        # 生成唯一任务ID
        task_id = str(uuid.uuid4())
        channel = f"{task_type}:{task_id}"

        # 如果没传自定义回调，使用默认的SSE进度推送回调
        if not progress_callback:

            async def default_progress_callback(current: int, total: int, message: str):
                await cls.publish_progress(
                    task_type=task_type,
                    task_id=task_id,
                    current=current,
                    total=total,
                    message=message,
                )

            progress_callback = default_progress_callback

        # 包装后台任务，统一处理异常和完成消息
        async def wrapped_task():
            try:
                logger.info(f"异步任务[{task_type}:{task_id}] 开始执行")
                # 执行实际业务函数，注入progress_callback参数
                result = await task_func(
                    *args, progress_callback=progress_callback, **kwargs
                )
                logger.info(f"异步任务[{task_type}:{task_id}] 执行完成")

                # 安全地序列化结果，避免 SQLAlchemy ORM 或 Pydantic 模型引发 json 序列化错误
                try:
                    safe_result = jsonable_encoder(result) if result is not None else {}
                except Exception as enc_err:
                    logger.warning(f"结果序列化失败，将返回空字典: {enc_err}")
                    safe_result = {}

                # 推送完成消息
                await cls.publish_complete(
                    task_type=task_type, task_id=task_id, result=safe_result
                )
                return result
            except Exception as e:
                logger.error(
                    f"异步任务[{task_type}:{task_id}] 执行失败: {e}", exc_info=True
                )
                # 推送错误消息
                try:
                    await cls.publish_error(
                        task_type=task_type, task_id=task_id, error=str(e)
                    )
                except Exception as pub_err:
                    logger.error(f"推送任务错误消息失败: {pub_err}", exc_info=True)
                return None
            finally:
                # 任务完成后自动清理引用
                cls._active_tasks.pop(task_id, None)

        # 创建任务并保持强引用
        task = asyncio.create_task(wrapped_task(), name=f"async-task-{task_id}")
        cls._active_tasks[task_id] = task

        # 添加任务完成回调（双重保险）
        task.add_done_callback(cls._on_task_done)

        return task_id

    @classmethod
    def _on_task_done(cls, task: asyncio.Task):
        """任务完成回调"""
        task_id = None
        for tid, t in cls._active_tasks.items():
            if t is task:
                task_id = tid
                break

        if task_id:
            if task.exception():
                logger.error(f"任务 {task_id} 抛出未捕获异常: {task.exception()}")
            cls._active_tasks.pop(task_id, None)

    @classmethod
    def get_active_tasks(cls) -> dict[str, dict]:
        """获取所有活跃任务信息"""
        result = {}
        for task_id, task in cls._active_tasks.items():
            result[task_id] = {
                "name": task.get_name(),
                "done": task.done(),
                "cancelled": task.cancelled(),
            }
        return result

    @classmethod
    async def cancel_task(cls, task_id: str) -> bool:
        """取消指定任务"""
        task = cls._active_tasks.get(task_id)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                logger.info(f"任务 {task_id} 已取消")
                return True
        return False

    @staticmethod
    async def publish_progress(
        task_type: str,
        task_id: str,
        current: int,
        total: int,
        message: str,
        extra: Optional[dict] = None,
    ):
        """推送进度消息（通用格式）"""
        data = {
            "type": "progress",
            "task_id": task_id,
            "current": current,
            "total": total,
            "message": message,
            "progress": round(current / total * 100, 2) if total > 0 else 0,
        }
        if extra:
            data.update(extra)
        await SSEPublisher.publish(f"{task_type}:{task_id}", data)

    @staticmethod
    async def publish_complete(
        task_type: str,
        task_id: str,
        result: Optional[dict] = None,
        message: str = "任务执行完成",
    ):
        """推送完成消息（通用格式）"""
        data = {
            "type": "complete",
            "task_id": task_id,
            "message": message,
            "result": result or {},
        }
        await SSEPublisher.publish(f"{task_type}:{task_id}", data)

    @staticmethod
    async def publish_error(
        task_type: str, task_id: str, error: str, message: str = "任务执行失败"
    ):
        """推送错误消息（通用格式）"""
        data = {"type": "error", "task_id": task_id, "message": message, "error": error}
        await SSEPublisher.publish(f"{task_type}:{task_id}", data)

    @staticmethod
    def get_sse_channel(task_type: str, task_id: str) -> str:
        """获取SSE频道名称"""
        return f"{task_type}:{task_id}"


# 单例实例
async_task_manager = AsyncTaskManager()
