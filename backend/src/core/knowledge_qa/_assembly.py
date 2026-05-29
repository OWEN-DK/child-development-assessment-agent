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
from src.core.knowledge_qa.nodes.contradiction_audit import contradiction_audit_node
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


MAX_S4_RETRIES = 2


def _route_after_s4_assemble(state: KnowledgeQAState) -> str:
    """S4 链路重试路由。

    plan_assemble 降级时设置 s4_needs_retry=True（有 outline 但无分组结果）。
    或 plan_outline 返回 section_4_outline_no_exercises error。

    重试时清空 S4 中间产物，让 plan_outline 重新生成。
    """
    # 区分结构性故障（重试无意义）和瞬时故障（重试可能成功）
    # section_4_expand_empty: 大纲无运动条目，属于 outline 质量问题，重试同一 outline 无意义
    structural_errors = any(
        "section_4_expand_empty" in e for e in (state.errors or [])
    )
    needs_retry = (state.s4_needs_retry or any(
        "section_4_outline_no_exercises" in e for e in (state.errors or [])
    )) and not structural_errors
    if needs_retry and state.s4_retry_count < MAX_S4_RETRIES:
        import logging
        logger = logging.getLogger(__name__)
        logger.info(
            f"S4 重试 {state.s4_retry_count + 1}/{MAX_S4_RETRIES}: "
            f"路由回 plan_outline（清空操作由节点函数负责）"
        )
        # 注意：条件边函数不能修改 graph state。
        # s4_retry_count 递增和中间产物清空由 plan_assemble_node / plan_outline_node
        # 在返回 dict 中完成。
        return "plan_outline"
    return "generate_s4_citations"


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
    workflow.add_node("contradiction_audit", contradiction_audit_node)
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
    # 条件边：S4 链路可重试
    workflow.add_conditional_edges(
        "plan_assemble",
        _route_after_s4_assemble,
        {"plan_outline": "plan_outline", "generate_s4_citations": "generate_s4_citations"},
    )
    workflow.add_edge("generate_s4_citations", "contradiction_audit")
    workflow.add_edge("contradiction_audit", "conclusion")
    workflow.add_edge("conclusion", "verify_citations")
    workflow.add_edge("verify_citations", "finalize")
    workflow.add_edge("finalize", END)

    return workflow.compile()


# 全局单例
knowledge_qa_graph = create_knowledge_qa_graph()
