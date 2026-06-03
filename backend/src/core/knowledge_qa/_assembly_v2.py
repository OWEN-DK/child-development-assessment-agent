"""知识问答 LangGraph 图组装 — v2（三层架构融合 + Bundle 统一检索）

图结构变更（相对 v1）:
1. 新增 build_bundle 节点——prefetch 完成后立即统一检索，产出 KnowledgeBundle
2. S1-S5 全部消费 Bundle（零搜索），消除旧版 _direct_search 路径
3. Node 内 if/else 兼容——Bundle 可用时走新路径，否则走旧版（降级）

降级路径:
- Bundle 构建失败 → S1-S5 回退旧版 _direct_search
- Neo4j 不可用 → Bundle 仅含 Chroma + LazyGraphRAG
"""

import logging
from langgraph.graph import END, StateGraph

from src.core.knowledge_qa.nodes.match_books import match_books_node
from src.core.knowledge_qa.nodes.prefetch_context import prefetch_context_node
from src.core.knowledge_qa.nodes.fast_knowledge_match import fast_knowledge_match_node
from src.core.knowledge_qa.nodes_v2.analyze_child_v2 import analyze_child_v2_node
from src.core.knowledge_qa.nodes_v2.identify_problems_v2 import identify_problems_v2_node
from src.core.knowledge_qa.nodes.generate_s1_s2_citations import (
    generate_s1_citations_node,
    generate_s2_citations_node,
    generate_s5_citations_node,
)
from src.core.knowledge_qa.nodes_v2.recommend_types_v2 import recommend_types_v2_node
from src.core.knowledge_qa.nodes.recommend_types import generate_s3_citations_node
from src.core.knowledge_qa.nodes_v2.plan_outline_v2 import plan_outline_v2_node
from src.core.knowledge_qa.nodes_v2.plan_expand_parallel_v2 import plan_expand_parallel_v2_node
from src.core.knowledge_qa.nodes.plan_assemble import plan_assemble_node
from src.core.knowledge_qa.nodes.generate_s4_citations import generate_s4_citations_node
from src.core.knowledge_qa.nodes_v2.knowledge_synthesis_v2 import knowledge_synthesis_v2_node
from src.core.knowledge_qa.nodes.conclusion import conclusion_node
from src.core.knowledge_qa.nodes.verify_citations import verify_citations_node
from src.core.knowledge_qa.nodes.finalize import finalize_node
from src.schemas.knowledge_qa import KnowledgeQAState

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Bundle build node (Phase 1: unified retrieval)
# ═══════════════════════════════════════════════════════════════════════════════


async def build_bundle_node(state: KnowledgeQAState) -> dict:
    """Phase 1: 构建 KnowledgeBundle。

    在 prefetch_context 之后、S1 之前执行——确保 S1-S5 全部走 Bundle 路径。
    s2_problems 此时为空（S2 尚未运行），Neo4j 查询降级为使用
    custom_entities（来自 fast_knowledge_match）+ question embedding 补偿。
    Bundle 构建成功后注入 state，S1-S5 从 Bundle 消费。
    """
    from src.core.knowledge_qa.bundle_config import _use_bundle
    from src.schemas.knowledge_qa import push_progress

    if not _use_bundle():
        logger.info("Bundle 模式未启用，跳过 build_bundle")
        return {"current_step": ["build_bundle_skipped"]}

    await push_progress("build_bundle", "正在统一检索知识…")

    try:
        from src.core.knowledge_qa.bundle_builder import build_knowledge_bundle

        # 提取 S2 结构化 problems
        s2_problems: list[str] = []
        if hasattr(state, "sections") and 2 in state.sections:
            s2_structured = state.sections[2].structured_data or {}
            for p in s2_structured.get("problems", []):
                if isinstance(p, dict) and p.get("name"):
                    s2_problems.append(p["name"])

        # 提取 custom_entities
        custom_entities = getattr(state, "custom_knowledge_entities", []) or []

        bundle = await build_knowledge_bundle(
            question=state.question,
            matched_book_ids=state.matched_book_ids,
            s2_problems=s2_problems,
            custom_entities=list(custom_entities),
            child_profile=getattr(state, "child_profile", {}),
            section_queries=getattr(state, "section_queries", None),
        )

        await push_progress(
            "build_bundle_done",
            f"知识检索完成: {len(bundle.passages)} 段落, "
            f"{bundle.retrieval_stats.neo4j_entity_count} 实体, "
            f"{bundle.retrieval_stats.retrieval_duration_ms}ms",
        )

        return {
            "knowledge_bundle": bundle,
            "current_step": ["build_bundle_done"],
        }

    except Exception as e:
        # 安全：完整异常仅记日志，前端只暴露类型名称（防止内部路径/凭证泄露）
        logger.exception("Bundle 构建失败: %s", e)
        safe_reason = type(e).__name__
        await push_progress("build_bundle_failed", f"Bundle 构建失败（{safe_reason}），降级搜索")
        return {
            "knowledge_bundle": None,
            "current_step": ["build_bundle_failed"],
            "errors": [f"build_bundle_failed: {safe_reason}"],
        }


# ═══════════════════════════════════════════════════════════════════════════════
# Routing
# ═══════════════════════════════════════════════════════════════════════════════


def _route_after_match_books(state: KnowledgeQAState) -> str:
    """匹配到书籍 → 先走自定义知识匹配；未匹配 → 直接结束。"""
    if state.matched_book_ids:
        return "fast_knowledge_match"
    return "finalize"


MAX_S4_RETRIES = 2


def _route_after_s4_assemble(state: KnowledgeQAState) -> str:
    """S4 链路重试路由。"""
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


# ═══════════════════════════════════════════════════════════════════════════════
# Graph construction
# ═══════════════════════════════════════════════════════════════════════════════


def create_knowledge_qa_v2_graph() -> StateGraph:
    """创建 v2 知识问答 LangGraph 图。

    拓扑: match_books → fast_km → prefetch
           → build_bundle（Phase 1: 统一检索）
           → S1 → S2 → S3 → S4(outline→expand→assemble→citations)
           → synth → conclusion → verify → finalize
    """
    workflow = StateGraph(KnowledgeQAState)

    # ── 保留 v1 节点 ──
    workflow.add_node("match_books", match_books_node)
    workflow.add_node("prefetch_context", prefetch_context_node)
    workflow.add_node("plan_assemble", plan_assemble_node)
    workflow.add_node("generate_s3_citations", generate_s3_citations_node)
    workflow.add_node("generate_s4_citations", generate_s4_citations_node)
    workflow.add_node("conclusion", conclusion_node)
    workflow.add_node("generate_s5_citations", generate_s5_citations_node)
    workflow.add_node("verify_citations", verify_citations_node)
    workflow.add_node("finalize", finalize_node)

    # ── v2 节点 ──
    workflow.add_node("fast_knowledge_match", fast_knowledge_match_node)
    workflow.add_node("analyze_child_v2", analyze_child_v2_node)
    workflow.add_node("generate_s1_citations", generate_s1_citations_node)
    workflow.add_node("identify_problems_v2", identify_problems_v2_node)
    workflow.add_node("generate_s2_citations", generate_s2_citations_node)
    workflow.add_node("recommend_types_v2", recommend_types_v2_node)
    workflow.add_node("plan_outline_v2", plan_outline_v2_node)
    workflow.add_node("plan_expand_parallel_v2", plan_expand_parallel_v2_node)
    workflow.add_node("knowledge_synthesis_v2", knowledge_synthesis_v2_node)

    # ── 新节点: Bundle 构建（替代 query_neo4j_graph 的独立阶段）──
    workflow.add_node("build_bundle", build_bundle_node)

    workflow.set_entry_point("match_books")

    # ── 条件边: 无匹配书籍 → 直接结束 ──
    workflow.add_conditional_edges(
        "match_books",
        _route_after_match_books,
        {"fast_knowledge_match": "fast_knowledge_match", "finalize": "finalize"},
    )

    # ── 新拓扑: match_books → fast_km → prefetch → build_bundle → S1 → S1_citations → S2 → S2_citations → S3 → S4 → ... ──
    workflow.add_edge("fast_knowledge_match", "prefetch_context")
    workflow.add_edge("prefetch_context", "build_bundle")
    workflow.add_edge("build_bundle", "analyze_child_v2")
    workflow.add_edge("analyze_child_v2", "generate_s1_citations")
    workflow.add_edge("generate_s1_citations", "identify_problems_v2")
    workflow.add_edge("identify_problems_v2", "generate_s2_citations")
    workflow.add_edge("generate_s2_citations", "recommend_types_v2")
    workflow.add_edge("recommend_types_v2", "generate_s3_citations")
    workflow.add_edge("generate_s3_citations", "plan_outline_v2")
    workflow.add_edge("plan_outline_v2", "plan_expand_parallel_v2")
    workflow.add_edge("plan_expand_parallel_v2", "plan_assemble")

    # ── S4 重试路由 ──
    workflow.add_conditional_edges(
        "plan_assemble",
        _route_after_s4_assemble,
        {
            "plan_outline_v2": "plan_outline_v2",
            "generate_s4_citations": "generate_s4_citations",
        },
    )

    # ── S4 → synth → S5 → S5_citations → verify → finalize ──
    workflow.add_edge("generate_s4_citations", "knowledge_synthesis_v2")
    workflow.add_edge("knowledge_synthesis_v2", "conclusion")
    workflow.add_edge("conclusion", "generate_s5_citations")
    workflow.add_edge("generate_s5_citations", "verify_citations")
    workflow.add_edge("verify_citations", "finalize")
    workflow.add_edge("finalize", END)

    return workflow.compile()


# 全局单例
knowledge_qa_v2_graph = create_knowledge_qa_v2_graph()
