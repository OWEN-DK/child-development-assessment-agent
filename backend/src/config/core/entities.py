from pydantic import BaseModel
from datetime import datetime
from typing import Any, Optional


class ConfigVersion(BaseModel):
    """配置版本实体"""

    id: str
    created_at: datetime
    created_by: Optional[str] = None
    description: Optional[str] = None
    config_snapshot: dict[str, Any]
    parent_version_id: Optional[str] = None
    is_factory_reset: bool = False
