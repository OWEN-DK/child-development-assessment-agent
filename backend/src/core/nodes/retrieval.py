from typing import Dict, Any
from src.model.schemas import AgentState
from src.core.nodes.base import BaseNode

from src.core.prompts import RAG_QUERY_TEMPLATE

class RetrievalNode(BaseNode):
    """混合检索"""
    
    async def __call__(self, state: AgentState) -> Dict[str, Any]:
        print("Executing Retrieval Node...")
        from src.service.rag_service import rag_service
        
        # 构造查询
        query = RAG_QUERY_TEMPLATE.format(
            issues=state.child_profile.issues, 
            goals=state.proposed_plan.goals
        )
        age = state.child_profile.age
        
        # 调用 RAG 服务
        docs = await rag_service.retrieve_knowledge(query, age)
        
        return {"retrieved_docs": docs}
