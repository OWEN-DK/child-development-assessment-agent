"""统一任务 API 控制器

承载所有任务类型的 CRUD + SSE + 取消操作
"""

import time
import uuid
from typing import Any, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from src.api.sse import sse_response
from src.schemas.common import APIResponse
from src.schemas.task import TaskState, TaskStatus
from src.service.task_sse_publisher import TaskSsePublisher
from src.service.task_state_service import TaskStateService
from src.utils.di import get_task_state_service
from src.utils.exceptions import AppException
from src.utils.logger import logger

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])


# ==================== 请求模型 ====================


class CreateTaskRequest(BaseModel):
    """创建任务请求"""

    task_type: str = Field(..., description="任务类型（upload/draft_generation/export/test_run）")
    metadata: Optional[dict[str, Any]] = Field(None, description="扩展元数据")


class UpdateTaskRequest(BaseModel):
    """更新任务状态请求（内部使用）"""

    status: TaskStatus
    stage: Optional[str] = None
    progress: Optional[float] = None
    message: Optional[str] = None
    error: Optional[str] = None
    result: Optional[dict[str, Any]] = None


# ==================== API 端点 ====================


@router.post("/{task_type}")
async def create_task(
    task_type: str,
    request: CreateTaskRequest,
):
    """创建任务
    
    返回任务 ID 和初始状态（pending）
    """
    service = get_task_state_service()
    
    task_id = str(uuid.uuid4())
    state = TaskState.create(
        task_id=task_id,
        task_type=task_type,
        metadata=request.metadata or {},
    )
    
    await service.create(state)
    
    logger.info(f"Task created: type={task_type}, id={task_id}")
    
    return APIResponse.success({
        "task_id": task_id,
        "status": state.status.value,
        "created_at": state.created_at,
    })


@router.get("/{task_type}/{task_id}")
async def get_task_status(
    task_type: str,
    task_id: str,
):
    """查询任务状态"""
    service = get_task_state_service()
    
    state = await service.get(task_id, task_type)
    if not state:
        raise AppException(
            status_code=404,
            code=10020,
            message="任务不存在",
            error_code="TASK_NOT_FOUND",
        )
    
    return APIResponse.success(state.model_dump())


@router.get("/{task_type}/{task_id}/stream")
async def stream_task_events(
    task_type: str,
    task_id: str,
):
    """SSE 监听任务事件
    
    频道命名：{task_type}:{task_id}
    """
    channel = f"{task_type}:{task_id}"
    return sse_response(channel)


@router.post("/{task_type}/{task_id}/cancel")
async def cancel_task(
    task_type: str,
    task_id: str,
):
    """取消任务
    
    1. 设置取消信号
    2. 更新 Redis 状态为 cancelled
    3. 推送 SSE 取消事件
    """
    service = get_task_state_service()
    
    # 先检查任务是否存在
    state = await service.get(task_id, task_type)
    if not state:
        raise AppException(
            status_code=404,
            code=10020,
            message="任务不存在",
            error_code="TASK_NOT_FOUND",
        )
    
    # 检查是否已经是终态
    if state.is_terminal:
        raise AppException(
            status_code=400,
            code=10021,
            message=f"任务无法取消（当前状态：{state.status.value}）",
            error_code="TASK_ALREADY_TERMINAL",
        )
    
    # 执行取消
    success = await service.cancel(task_id, task_type)
    if not success:
        raise AppException(
            status_code=500,
            code=10022,
            message="取消失败（可能已进入终态）",
            error_code="TASK_CANCEL_FAILED",
        )
    
    # 推送 SSE 取消事件
    await TaskSsePublisher.publish_cancelled(task_type, task_id)
    
    return APIResponse.success({"status": TaskStatus.CANCELLED.value})


@router.delete("/{task_type}/{task_id}")
async def delete_task(
    task_type: str,
    task_id: str,
):
    """删除任务
    
    同时从 Redis 和活跃任务索引中移除
    """
    service = get_task_state_service()
    
    success = await service.delete(task_id, task_type)
    if not success:
        logger.warning(f"Failed to delete task: type={task_type}, id={task_id}")
    
    return APIResponse.success()


@router.get("/active")
async def list_active_tasks(
    task_type: Optional[str] = Query(None, description="过滤任务类型"),
):
    """列出所有活跃任务（非终态）"""
    service = get_task_state_service()
    
    tasks = await service.list_active(task_type)
    
    return APIResponse.success({
        "tasks": [task.model_dump() for task in tasks],
        "count": len(tasks),
    })
