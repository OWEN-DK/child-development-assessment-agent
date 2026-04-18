"""查询路由模块模型

包含查询分类相关的 Pydantic 模型：
- QueryClassification: 查询分类结果
"""

from enum import Enum

from pydantic import BaseModel, Field


class QueryType(str, Enum):
    """查询类型"""

    DIRECT = "direct"
    COMPARISON = "comparison"
    EXPLORATION = "exploration"


class QueryClassification(BaseModel):
    """查询分类结果"""

    query_type: QueryType
    confidence: float
    reasoning: str = ""
