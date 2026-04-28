"""调优 Schema"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class TuningSuggestion(BaseModel):
    """调优建议"""

    id: str
    run_id: str
    report_id: Optional[str] = None
    category: str
    severity: str
    title: str
    description: str
    current_value: Optional[Any] = None
    suggested_value: Optional[Any] = None
    expected_impact: Optional[str] = None
    source: Optional[str] = None
    priority: Optional[int] = None
    safe_range: Optional[str] = None
    status: str
    conflict_with: Optional[str] = None
    applied_config_version_id: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConflictPair(BaseModel):
    """冲突对"""

    suggestion_id_1: str
    suggestion_id_2: str
    conflict_type: str
    description: str
    resolution: Optional[str] = None


class ConfigVersionRead(BaseModel):
    """配置版本读取"""

    id: str
    version_number: int
    version_label: str
    config_snapshot: dict
    change_summary: str
    created_by: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConfigChangeSetRead(BaseModel):
    """配置变更集读取"""

    id: str
    change_set_label: str
    config_version_id: str
    status: str
    rollback_reason: Optional[str] = None
    created_at: datetime
    rolled_back_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
