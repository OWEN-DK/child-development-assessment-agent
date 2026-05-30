"""知识问答 LangGraph 图组装 — v2 (三层架构融合)

图结构变更（相对 v1）:
1. 新增 query_neo4j_graph 节点（match_books → prefetch_context 之间）
2. S1-S4 节点替换为 v2 变体（融合 Neo4j 知识）
3. contradiction_audit 替换为 v2 变体（优先使用 Neo4j 跨书关系）
4. NEO4J_ENABLED=False 时自动跳过 query_neo4j_graph，行为与 v1 一致

降级路径:
- Neo4j 不可用 → query_neo4j_graph 返回空 {} → v2 节点回退到 v1 行为
- Neo4j 查询超时 → 同上
"""

import logging
from langgraph.graph import END, StateGraph

from src.core.knowledge_qa.nodes.match_books import match_books_node
from src.core.knowledge_qa.nodes.prefetch_context import prefetch_context_node
from src.core.knowledge_qa.nodes_v2.query_neo4j_graph import query_neo4j_graph_node
from src.core.knowledge_qa.nodes_v2.analyze_child_v2 import analyze_child_v2_node
from src.core.knowledge_qa.nodes_v2.identify_problems_v2 import identify_problems_v2_node
from src.core.knowledge_qa.nodes_v2.recommend_types_v2 import recommend_types_v2_node
from src.core.knowledge_qa.nodes_v2.plan_outline_v2 import plan_outline_v2_node
from src.core.knowledge_qa.nodes_v2.plan_expand_parallel_v2 import plan_expand_parallel_v2_node
from src.core.knowledge_qa.nodes.plan_assemble import plan_assemble_node
from src.core.knowledge_qa.nodes.generate_s4_citations import generate_s4_citations_node
from src.core.knowledge_qa.nodes_v2.contradiction_audit_v2 import contradiction_audit_v2_node
from src.core.knowledge_qa.nodes.conclusion import conclusion_node
from src.core.knowledge_qa.nodes.verify_citations import verify_citations_node
from src.core.knowledge_qa.nodes.finalize import finalize_node
from src.schemas.knowledge_qa import KnowledgeQAState

logger = logging.getLogger(__name__)


def _route_after_match_books(state: KnowledgeQAState) -> str:
    """匹配到书籍 → 继续流水线；未匹配 → 直接结束。"""
    if state.matched_book_ids:
        return "query_neo4j_graph"
    return "finalize"


MAX_S4_RETRIES = 2


def _route_after_s4_assemble(state: KnowledgeQAState) -> str:
    """S4 链路重试路由（与 v1 逻辑一致）。"""
    structural_errors = any(
        "section_4_expand_empty" in e for e in (state.errors or [])
    )
    needs_retry = (state.s4_needs_retry or any(
        "section_4_outline_no_exercises" in e for e in (state.errors or [])
    )) and not structural_errors
    if needs_retry and state.s4_retry_count < MAX_S4_RETRIES:
        logger.info(
            "S4 v2 重试 %d/%d: 路由回 plan_outline_v2",
            state.s4_retry_count + 1, MAX_S4_RETRIES,
        )
        return "plan_outline_v2"
    return "generate_s4_citations"


def create_knowledge_qa_v2_graph() -> StateGraph:
    """创建 v2 知识问答 LangGraph 图（融合 Neo4j 三层架构）。"""
    workflow = StateGraph(KnowledgeQAState)

    # 保留 v1 节点
    workflow.add_node("match_books", match_books_node)
    workflow.add_node("prefetch_context", prefetch_context_node)
    workflow.add_node("plan_assemble", plan_assemble_node)
    workflow.add_node("generate_s4_citations", generate_s4_citations_node)
    workflow.add_node("conclusion", conclusion_node)
    workflow.add_node("verify_citations", verify_citations_node)
    workflow.add_node("finalize", finalize_node)

    # 新增 / v2 节点
    workflow.add_node("query_neo4j_graph", query_neo4j_graph_node)
    workflow.add_node("analyze_child_v2", analyze_child_v2_node)
    workflow.add_node("identify_problems_v2", identify_problems_v2_node)
    workflow.add_node("recommend_types_v2", recommend_types_v2_node)
    workflow.add_node("plan_outline_v2", plan_outline_v2_node)
    workflow.add_node("plan_expand_parallel_v2", plan_expand_parallel_v2_node)
    workflow.add_node("contradiction_audit_v2", contradiction_audit_v2_node)

    workflow.set_entry_point("match_books")

    # 条件边：无匹配书籍 → 直接结束
    workflow.add_conditional_edges(
        "match_books",
        _route_after_match_books,
        {"query_neo4j_graph": "query_neo4j_graph", "finalize": "finalize"},
    )

    # v2 主链路
    workflow.add_edge("query_neo4j_graph", "prefetch_context")
    workflow.add_edge("prefetch_context", "analyze_child_v2")
    workflow.add_edge("analyze_child_v2", "identify_problems_v2")
    workflow.add_edge("identify_problems_v2", "recommend_types_v2")
    workflow.add_edge("recommend_types_v2", "plan_outline_v2")
    workflow.add_edge("plan_outline_v2", "plan_expand_parallel_v2")
    workflow.add_edge("plan_expand_parallel_v2", "plan_assemble")

    # S4 重试路由
    workflow.add_conditional_edges(
        "plan_assemble",
        _route_after_s4_assemble,
        {
            "plan_outline_v2": "plan_outline_v2",
            "generate_s4_citations": "generate_s4_citations",
        },
    )

    workflow.add_edge("generate_s4_citations", "contradiction_audit_v2")
    workflow.add_edge("contradiction_audit_v2", "conclusion")
    workflow.add_edge("conclusion", "verify_citations")
    workflow.add_edge("verify_citations", "finalize")
    workflow.add_edge("finalize", END)

    return workflow.compile()


# 全局单例
knowledge_qa_v2_graph = create_knowledge_qa_v2_graph()
