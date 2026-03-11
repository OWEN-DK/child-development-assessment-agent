from typing import Dict, Any
from src.model.schemas import AgentState, ChildState
from src.core.nodes.base import BaseNode

class AssessmentNode(BaseNode):
    """儿童发展评估"""
    
    async def __call__(self, state: AgentState) -> Dict[str, Any]:
        print("Executing Assessment Node...")
        # TODO: 调用 LLM 进行评估
        child_state = ChildState(
            vestibular_system={"status": "deficit", "level": 2, "description": "前庭敏感"},
            core_strength={"status": "weak", "level": 3, "description": "核心力量不足"},
            overall_assessment="整体发展正常，但前庭觉和核心力量需要加强。"
        )
        return {"child_state": child_state}
