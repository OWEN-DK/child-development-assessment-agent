"""统一任务状态模型"""

import json
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


def _json_default(obj):
    """处理Decimal类型的JSON序列化"""
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")


class TaskStatus(str, Enum):
    """统一任务状态枚举"""

    PENDING = "pending"  # 已创建，等待执行
    RUNNING = "running"  # 正在执行
    COMPLETED = "completed"  # 执行成功（终态）
    FAILED = "failed"  # 执行失败（终态）
    CANCELLED = "cancelled"  # 用户取消（终态）
    RETRYING = "retrying"  # 失败重试中（可选，当前阶段不启用）


# 终态集合（不可逆）
TERMINAL_STATES = frozenset({TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED})

# 活跃状态集合（非终态）
ACTIVE_STATES = frozenset({TaskStatus.PENDING, TaskStatus.RUNNING, TaskStatus.RETRYING})


class TaskState(BaseModel):
    """统一任务状态模型（Redis Hash 存储结构）"""

    # 标识
    task_id: str = Field(..., description="任务唯一标识")
    task_type: str = Field(..., description="任务类型（upload/draft_generation/export/test_run）")

    # 状态
    status: TaskStatus = Field(..., description="当前状态")
    stage: Optional[str] = Field(None, description="执行阶段（如 parsing/indexing）")
    progress: float = Field(0.0, ge=0.0, le=100.0, description="进度百分比（0-100）")
    message: Optional[str] = Field(None, description="用户可见消息")

    # 结果（终态时填充）
    error: Optional[str] = Field(None, description="失败时的错误信息")
    result: Optional[dict[str, Any]] = Field(None, description="成功时的结果数据")

    # 时间戳（Unix 时间戳）
    created_at: float = Field(..., description="创建时间")
    started_at: Optional[float] = Field(None, description="开始执行时间")
    completed_at: Optional[float] = Field(None, description="完成时间")

    # 元数据（扩展字段）
    metadata: dict[str, Any] = Field(default_factory=dict, description="扩展元数据")

    @property
    def is_terminal(self) -> bool:
        """是否为终态"""
        return self.status in TERMINAL_STATES

    @property
    def is_active(self) -> bool:
        """是否为活跃状态"""
        return self.status in ACTIVE_STATES

    @classmethod
    def create(cls, task_id: str, task_type: str, metadata: Optional[dict[str, Any]] = None) -> "TaskState":
        """创建初始任务状态（pending）"""
        return cls(
            task_id=task_id,
            task_type=task_type,
            status=TaskStatus.PENDING,
            created_at=datetime.now(timezone.utc).timestamp(),
            metadata=metadata or {},
        )

    def to_redis_hash(self) -> dict[str, str]:
        """转换为 Redis Hash 字段（所有值转为字符串）"""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "status": self.status.value,
            "stage": self.stage or "",
            "progress": str(self.progress),
            "message": self.message or "",
            "error": self.error or "",
            "result": json.dumps(self.result, default=_json_default) if self.result else "",
            "created_at": str(self.created_at),
            "started_at": str(self.started_at) if self.started_at else "",
            "completed_at": str(self.completed_at) if self.completed_at else "",
            "metadata": json.dumps(self.metadata, default=_json_default) if self.metadata else "",
        }

    @classmethod
    def from_redis_hash(cls, data: dict[str, str], task_type: str) -> Optional["TaskState"]:
        """从 Redis Hash 恢复任务状态"""
        import json

        if not data or "task_id" not in data:
            return None

        def parse_float(value: str) -> Optional[float]:
            return float(value) if value else None

        def parse_json(value: str) -> Any:
            return json.loads(value) if value else None

        return cls(
            task_id=data["task_id"],
            task_type=task_type,
            status=TaskStatus(data["status"]),
            stage=data.get("stage") or None,
            progress=float(data.get("progress", 0)),
            message=data.get("message") or None,
            error=data.get("error") or None,
            result=parse_json(data.get("result", "")),
            created_at=float(data["created_at"]),
            started_at=parse_float(data.get("started_at", "")),
            completed_at=parse_float(data.get("completed_at", "")),
            metadata=parse_json(data.get("metadata", "{}")) or {},
        )


class TaskSseEvent(BaseModel):
    """统一 SSE 事件格式"""

    type: str = Field(..., description="事件类型（progress/complete/error/heartbeat）")
    task_id: str = Field(..., description="任务 ID")
    task_type: str = Field(..., description="任务类型")
    timestamp: str = Field(..., description="ISO 8601 时间戳")

    # 可选字段（根据事件类型不同）
    status: Optional[TaskStatus] = None
    stage: Optional[str] = None
    progress: Optional[float] = None
    message: Optional[str] = None
    error: Optional[str] = None
    result: Optional[dict[str, Any]] = None
    metadata: Optional[dict[str, Any]] = None

    @classmethod
    def create_progress(
        cls,
        task_id: str,
        task_type: str,
        status: TaskStatus,
        progress: float,
        stage: Optional[str] = None,
        message: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> "TaskSseEvent":
        """创建进度事件"""
        return cls(
            type="progress",
            task_id=task_id,
            task_type=task_type,
            timestamp=datetime.now(timezone.utc).isoformat(),
            status=status,
            progress=progress,
            stage=stage,
            message=message,
            metadata=metadata,
        )

    @classmethod
    def create_complete(
        cls,
        task_id: str,
        task_type: str,
        result: Optional[dict[str, Any]] = None,
        message: Optional[str] = None,
    ) -> "TaskSseEvent":
        """创建完成事件"""
        return cls(
            type="complete",
            task_id=task_id,
            task_type=task_type,
            timestamp=datetime.now(timezone.utc).isoformat(),
            status=TaskStatus.COMPLETED,
            result=result,
            message=message,
        )

    @classmethod
    def create_error(
        cls,
        task_id: str,
        task_type: str,
        error: str,
        message: Optional[str] = None,
    ) -> "TaskSseEvent":
        """创建错误事件"""
        return cls(
            type="error",
            task_id=task_id,
            task_type=task_type,
            timestamp=datetime.now(timezone.utc).isoformat(),
            status=TaskStatus.FAILED,
            error=error,
            message=message,
        )

    @classmethod
    def create_cancelled(
        cls,
        task_id: str,
        task_type: str,
    ) -> "TaskSseEvent":
        """创建取消事件"""
        return cls(
            type="complete",  # 取消也使用 complete 事件类型
            task_id=task_id,
            task_type=task_type,
            timestamp=datetime.now(timezone.utc).isoformat(),
            status=TaskStatus.CANCELLED,
            message="任务已取消",
        )
