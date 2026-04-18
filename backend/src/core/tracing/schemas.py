"""追踪系统 Pydantic 模型定义"""

from typing import Optional

from pydantic import BaseModel, Field


class TraceMetadata(BaseModel):
    """Trace metadata 结构化模型

    写入时通过 model_dump() 转为 JSON，确保字段一致性。
    """

    child_profile_id: Optional[str] = Field(None, description="儿童档案 ID")
    test_run_id: Optional[str] = Field(None, description="测试运行 ID")
    test_set_id: Optional[str] = Field(None, description="测试集 ID")
    test_case_id: Optional[str] = Field(None, description="测试用例 ID")
    document_id: Optional[str] = Field(None, description="文档 ID")
    model: Optional[str] = Field(None, description="使用的模型名称")
    provider: Optional[str] = Field(None, description="模型提供商")
    extra: Optional[dict] = Field(None, description="其他自定义字段")
