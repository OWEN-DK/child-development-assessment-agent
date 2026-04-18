"""元数据提取模块模型

包含元数据提取相关的 Pydantic 模型：
- ExtractedMetadata: 提取的元数据
"""

from typing import List

from pydantic import BaseModel, Field


class ExtractedMetadata(BaseModel):
    """提取的元数据"""

    summary: str = Field(default="", description="内容的简要摘要（最多 50 字）")
    topics: List[str] = Field(default_factory=list, description="关键词列表")
    brain_regions: List[str] = Field(default_factory=list, description="提到或隐含的大脑区域列表")
    target_age_min: float = Field(default=0.0, description="推荐最小年龄")
    target_age_max: float = Field(default=18.0, description="推荐最大年龄")
    activity_type: str = Field(default="Theory", description="内容类型")
