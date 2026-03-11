from typing import Dict, Any
from src.model.schemas import AgentState, EvaluationResult
from src.core.nodes.base import BaseNode

class ScoringNode(BaseNode):
    """评分"""
    
    async def __call__(self, state: AgentState) -> Dict[str, Any]:
        print("Executing Scoring Node...")
        # TODO: 实现 AHP 评分
        result = EvaluationResult(
            score=85.5,
            reasoning="计划针对性强，符合年龄特征，但强度略高。",
            shap_explanation={"scientific_match": 10, "age_appropriateness": 5, "safety": -2},
            suggestions=["建议前两周适当降低跳绳时长"]
        )
        return {"evaluation_result": result}
