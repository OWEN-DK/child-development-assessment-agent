"""最终汇总节点 — 纯函数，不依赖 LLM 或工具"""

import logging
from typing import Any, Dict

from src.schemas.knowledge_qa import KnowledgeQAState

logger = logging.getLogger(__name__)


async def finalize_node(state: KnowledgeQAState) -> Dict[str, Any]:
    """纯函数节点：汇总最终状态"""
    missing = [i for i in range(1, 6) if i not in state.sections]
    return {
        "current_step": ["completed"],
        "errors": state.errors + (["缺失节: " + str(missing)] if missing else []),
        "partial": state.partial or bool(missing),
    }
