"""源文档 Schema"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class SourceDocumentRead(BaseModel):
    """源文档读取"""

    id: str
    title: str
    file_type: str
    file_path: str
    file_hash: str
    content_summary: Optional[str] = None
    page_count: Optional[int] = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SourceDocumentUpload(BaseModel):
    """上传响应"""

    id: str
    task_id: str
