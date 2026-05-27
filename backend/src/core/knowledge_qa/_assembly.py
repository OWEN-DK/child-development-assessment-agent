"""知识问答 LangGraph 图组装

图结构:
match_books → (无匹配书籍 → finalize)
            → (有匹配 → prefetch_context → analyze_child → identify_problems
               → recommend_types → plan_outline → plan_expand_parallel
               → plan_assemble → generate_s4_citations
               → conclusion → verify_citations → finalize → END)
"""

from langgraph.graph import END, StateGraph

from src.core.knowledge_qa.nodes.analyze_child import analyze_child_node
from src.core.knowledge_qa.nodes.conclusion import conclusion_node
from src.core.knowledge_qa.nodes.finalize import finalize_node
from src.core.knowledge_qa.nodes.generate_s4_citations import generate_s4_citations_node
from src.core.knowledge_qa.nodes.identify_problems import identify_problems_node
from src.core.knowledge_qa.nodes.match_books import match_books_node
from src.core.knowledge_qa.nodes.plan_outline import plan_outline_node
from src.core.knowledge_qa.nodes.plan_expand_parallel import plan_expand_parallel_node
from src.core.knowledge_qa.nodes.plan_assemble import plan_assemble_node
from src.core.knowledge_qa.nodes.prefetch_context import prefetch_context_node
from src.core.knowledge_qa.nodes.recommend_types import recommend_types_node
from src.core.knowledge_qa.nodes.verify_citations import verify_citations_node
from src.schemas.knowledge_qa import KnowledgeQAState


def _route_after_match_books(state: KnowledgeQAState) -> str:
    """匹配到书籍 → 继续流水线；未匹配 → 直接结束，避免无效 LLM 调用。"""
    if state.matched_book_ids:
        return "prefetch_context"
    return "finalize"


def create_knowledge_qa_graph() -> StateGraph:
    """创建知识问答 LangGraph 图。"""
    workflow = StateGraph(KnowledgeQAState)

    workflow.add_node("match_books", match_books_node)
    workflow.add_node("prefetch_context", prefetch_context_node)
    workflow.add_node("analyze_child", analyze_child_node)
    workflow.add_node("identify_problems", identify_problems_node)
    workflow.add_node("recommend_types", recommend_types_node)
    workflow.add_node("plan_outline", plan_outline_node)
    workflow.add_node("plan_expand_parallel", plan_expand_parallel_node)
    workflow.add_node("plan_assemble", plan_assemble_node)
    workflow.add_node("generate_s4_citations", generate_s4_citations_node)
    workflow.add_node("conclusion", conclusion_node)
    workflow.add_node("verify_citations", verify_citations_node)
    workflow.add_node("finalize", finalize_node)

    workflow.set_entry_point("match_books")

    # 条件边：无匹配书籍 → 直接结束
    workflow.add_conditional_edges(
        "match_books",
        _route_after_match_books,
        {"prefetch_context": "prefetch_context", "finalize": "finalize"},
    )

    workflow.add_edge("prefetch_context", "analyze_child")
    workflow.add_edge("analyze_child", "identify_problems")
    workflow.add_edge("identify_problems", "recommend_types")
    workflow.add_edge("recommend_types", "plan_outline")
    workflow.add_edge("plan_outline", "plan_expand_parallel")
    workflow.add_edge("plan_expand_parallel", "plan_assemble")
    workflow.add_edge("plan_assemble", "generate_s4_citations")
    workflow.add_edge("generate_s4_citations", "conclusion")
    workflow.add_edge("conclusion", "verify_citations")
    workflow.add_edge("verify_citations", "finalize")
    workflow.add_edge("finalize", END)

    return workflow.compile()


# 全局单例
knowledge_qa_graph = create_knowledge_qa_graph()
