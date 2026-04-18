from typing import Any, Dict

from src.core.nodes.base import BaseNode
from src.core.prompts_fallback import RAG_QUERY_TEMPLATE
from src.schemas import AgentState
from src.utils.logger import logger


class RetrievalNode(BaseNode):
    """混合检索"""

    async def __call__(self, state: AgentState) -> Dict[str, Any]:
        logger.info("Executing Retrieval Node...")
        from src.service.rag_service import rag_service

        # 构造查询
        query = RAG_QUERY_TEMPLATE.format(
            issues=state.child_profile.issues, goals=state.proposed_plan.goals
        )
        age = state.child_profile.age

        # 调用 RAG 服务
        docs = await rag_service.retrieve_knowledge(query, age, limit=5)

        return {"retrieved_docs": docs}
