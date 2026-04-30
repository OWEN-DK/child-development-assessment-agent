"""查询路由模块模型

包含查询分类相关的 Pydantic 模型：
- QueryClassification: 查询分类结果
- QueryType: 统一查询类型枚举（全项目唯一）
"""

from enum import Enum

from pydantic import BaseModel, Field


class QueryType(str, Enum):
    """统一查询类型枚举 — 全项目唯一定义"""

    SIMPLE = "simple"
    COMPLEX = "complex"
    DEFAULT = "default"


class QueryClassification(BaseModel):
    """查询分类结果"""

    query_type: QueryType
    confidence: float
    reasoning: str = ""
