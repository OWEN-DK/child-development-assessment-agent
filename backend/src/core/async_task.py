import asyncio
import uuid
from decimal import Decimal
from typing import Any, Awaitable, Callable, Optional

from fastapi.encoders import jsonable_encoder

from src.schemas.task import TaskState, TaskStatus
from src.service.task_sse_publisher import TaskSsePublisher
from src.utils.di import get_task_state_service
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
        
        # 获取任务状态服务实例
        task_state_service = get_task_state_service()
        
        # 创建初始任务状态（pending）
        initial_state = TaskState.create(
            task_id=task_id,
            task_type=task_type,
            metadata={}
        )
        initial_state.progress = 0.0
        initial_state.message = "等待执行"
        await task_state_service.create(initial_state)
        
        # 获取取消信号
        cancellation_event = task_state_service.get_cancellation_signal(task_id, task_type)

        # 如果没传自定义回调，使用默认的SSE进度推送回调
        if not progress_callback:

            async def default_progress_callback(current: int, total: int, message: str, stage: Optional[str] = None):
                progress = round(current / total * 100, 2) if total > 0 else 0
                
                # 更新Redis状态
                await task_state_service.update(
                    task_id=task_id,
                    task_type=task_type,
                    updates={
                        "status": TaskStatus.RUNNING,
                        "progress": progress,
                        "message": message,
                        "stage": stage
                    }
                )
                
                # 推送SSE消息
                await TaskSsePublisher.publish_progress(
                    task_type=task_type,
                    task_id=task_id,
                    progress=progress,
                    message=message,
                    stage=stage
                )

            progress_callback = default_progress_callback

        # 包装后台任务，统一处理异常和完成消息
        async def wrapped_task():
            try:
                logger.info(f"异步任务[{task_type}:{task_id}] 开始执行")
                
                # 更新状态为running
                await task_state_service.update(
                    task_id=task_id,
                    task_type=task_type,
                    updates={"status": TaskStatus.RUNNING, "message": "执行中"}
                )
                
                # 执行实际业务函数，注入progress_callback、cancellation_event、task_id和task_type参数
                result = await task_func(
                    *args, 
                    progress_callback=progress_callback,
                    cancellation_event=cancellation_event,
                    task_id=task_id,
                    task_type=task_type,
                    **kwargs
                )
                logger.info(f"异步任务[{task_type}:{task_id}] 执行完成")

                # 安全地序列化结果，避免 SQLAlchemy ORM 或 Pydantic 模型引发 json 序列化错误
                try:
                    safe_result = jsonable_encoder(
                        result,
                        custom_encoder={Decimal: lambda v: float(v)}
                    ) if result is not None else {}
                except Exception as enc_err:
                    logger.warning(f"结果序列化失败，将返回空字典: {enc_err}")
                    safe_result = {}
                
                # 更新状态为completed
                await task_state_service.update(
                    task_id=task_id,
                    task_type=task_type,
                    updates={
                        "status": TaskStatus.COMPLETED,
                        "progress": 100.0,
                        "message": "执行完成",
                        "result": safe_result
                    }
                )

                # 推送完成消息
                await TaskSsePublisher.publish_complete(
                    task_type=task_type, 
                    task_id=task_id, 
                    result=safe_result
                )
                return result
            except asyncio.CancelledError:
                logger.info(f"异步任务[{task_type}:{task_id}] 已取消")
                
                # 更新状态为cancelled
                await task_state_service.update(
                    task_id=task_id,
                    task_type=task_type,
                    updates={"status": TaskStatus.CANCELLED, "message": "已取消"}
                )
                
                # 推送取消事件
                await TaskSsePublisher.publish_cancelled(
                    task_type=task_type,
                    task_id=task_id
                )
                return None
            except Exception as e:
                logger.error(
                    f"异步任务[{task_type}:{task_id}] 执行失败: {e}", exc_info=True
                )
                
                # 更新状态为failed
                await task_state_service.update(
                    task_id=task_id,
                    task_type=task_type,
                    updates={"status": TaskStatus.FAILED, "error": str(e), "message": "执行失败"}
                )
                
                # 推送错误消息
                try:
                    await TaskSsePublisher.publish_error(
                        task_type=task_type, 
                        task_id=task_id, 
                        error=str(e)
                    )
                except Exception as pub_err:
                    logger.error(f"推送任务错误消息失败: {pub_err}", exc_info=True)
                return None
            finally:
                # 清理取消信号
                task_state_service.cleanup_cancellation_signal(task_id, task_type)
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
    async def cancel_task(cls, task_id: str, task_type: str) -> bool:
        """取消指定任务
        
        Returns:
            bool: Redis 状态更新成功即返回 True（任务可能已完成，但状态已成功标记为取消）
        """
        task_state_service = get_task_state_service()
        
        # 调用任务状态服务的cancel方法设置取消信号并更新 Redis 状态
        redis_success = await task_state_service.cancel(task_id, task_type)
        
        # 尝试取消 asyncio 任务（如果仍在运行）
        task = cls._active_tasks.get(task_id)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                logger.info(f"任务 {task_id} 已取消")
        
        # 以 Redis 状态更新结果为准
        return redis_success

    @staticmethod
    def get_sse_channel(task_type: str, task_id: str) -> str:
        """获取SSE频道名称"""
        return f"{task_type}:{task_id}"


# 单例实例
async_task_manager = AsyncTaskManager()
