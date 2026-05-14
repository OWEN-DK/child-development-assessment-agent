"""重建任务相关实体类"""
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class RebuildTrigger(str, Enum):
    """重建触发原因"""
    CHUNK_CHANGE = "chunk_change"
    EMBEDDING_CHANGE = "embedding_change"
    BACKEND_MIGRATION = "backend_migration"


class RebuildStatus(str, Enum):
    """重建状态"""
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class RebuildTaskSummary(BaseModel):
    """重建任务摘要"""
    id: str
    kb_id: str
    trigger: RebuildTrigger
    status: RebuildStatus
    progress_pct: int = 0
    progress_message: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None

    model_config = {"from_attributes": True}


class RebuildStatusResponse(BaseModel):
    """重建状态响应"""
    kb_id: str
    current_task: Optional[RebuildTaskSummary] = None
    recent_tasks: list[RebuildTaskSummary] = Field(default_factory=list)


class RebuildProgressEvent(BaseModel):
    """重建进度事件（SSE 推送）"""
    event: str = "progress"  # progress / complete / error
    task_id: str
    kb_id: str
    progress_pct: int = 0
    progress_message: str = ""
    status: RebuildStatus = RebuildStatus.RUNNING
