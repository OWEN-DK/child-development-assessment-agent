"""测试集 Schema"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from src.schemas.rag_eval.test_case import TestCaseRead


class TestSetCreate(BaseModel):
    """测试集创建请求"""

    name: str
    description: str = ""
    case_ids: list[str] = []


class TestSetRead(BaseModel):
    """测试集读取"""

    id: str
    name: str
    description: str
    source_type: str
    case_count: int
    case_ids: list[str] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TestSetUpdate(BaseModel):
    """测试集更新"""

    name: Optional[str] = None
    description: Optional[str] = None


class TestSetExport(BaseModel):
    """测试集导出格式"""

    name: str
    description: str
    source_type: str
    exported_at: datetime
    cases: list[TestCaseRead]
