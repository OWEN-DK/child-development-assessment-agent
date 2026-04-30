from typing import Any, Dict

from src.core.nodes.base import BaseNode
from src.core.prompt_impl.facade import prompt_manager
from src.schemas import AgentState
from src.utils.logger import logger


class RetrievalNode(BaseNode):
    """混合检索"""

    async def __call__(self, state: AgentState) -> Dict[str, Any]:
        logger.info("Executing Retrieval Node...")
        from src.service.rag_service import rag_service

        query = await prompt_manager.get_prompt(
            "rag_query_template",
            variables={"issues": state.child_profile.issues, "goals": state.proposed_plan.goals},
        )
        docs = await rag_service.retrieve_knowledge(query, limit=5)

        return {"retrieved_docs": docs}
