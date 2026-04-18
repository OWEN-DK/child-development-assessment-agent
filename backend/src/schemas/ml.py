"""ML 评分模块模型

包含 ML 评分相关的 Pydantic 模型：
- QwenScoringOutput: Qwen 评分输出
"""

from typing import Dict

from pydantic import BaseModel, Field


class QwenScoringOutput(BaseModel):
    """Qwen 评分输出"""

    score: float = Field(description="预测的评分，0-100 之间")
    reasoning: str = Field(description="评分理由")
    feature_importance: Dict[str, float] = Field(description="各特征重要度，总和为 100")
