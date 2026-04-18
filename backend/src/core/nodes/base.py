from abc import ABC, abstractmethod
from typing import Any, Dict

from src.schemas import AgentState


class BaseNode(ABC):
    """LangGraph 节点基类"""

    @abstractmethod
    async def __call__(self, state: AgentState) -> Dict[str, Any]:
        """执行节点逻辑"""
        pass
