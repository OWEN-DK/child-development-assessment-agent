from typing import Dict, Any
from src.model.schemas import AgentState
from src.core.nodes.base import BaseNode

class ValidationNode(BaseNode):
    """数据校验与标准化"""
    
    async def __call__(self, state: AgentState) -> Dict[str, Any]:
        print("Executing Validation Node...")
        # Pydantic 已经在入口处校验了，这里主要做业务规则校验
        # TODO: 智能填补缺失值
        return {"proposed_plan": state.proposed_plan}
