"""State + Assembly + 现有节点修改参考

本文件记录所有需要对现有代码做的修改（diff 形式），
实施时按此文件逐项修改对应的目标文件。

放置位置: 仅作参考，不直接放入 backend
"""

# ════════════════════════════════════════════════════════════════
# 1. schemas/knowledge_qa.py — KnowledgeQAState 新增字段
# ════════════════════════════════════════════════════════════════

STATE_NEW_FIELDS = '''
    # ===== 自定义知识（最高优先级，引导下游搜索） =====
    custom_knowledge_context: str = Field(
        default="",
        description="自定义知识命中后注入的上下文 Markdown (fast_knowledge_match_node 写入)",
    )
    custom_knowledge_entities: List[str] = Field(
        default_factory=list,
        description="从自定义知识中提取的关键实体名，传递给下游搜索节点作为引导",
    )
    fast_knowledge_hit: bool = Field(
        default=False,
        description="自定义知识是否命中",
    )
    three_layer_synthesis: Dict[str, Any] = Field(
        default_factory=dict,
        description="三层知识综合结果 (knowledge_synthesis_v2_node 写入)。keys: consensus, complementary, conflicts",
    )
'''

# 插入位置: neo4j_knowledge 字段之后、class Config 之前


# ════════════════════════════════════════════════════════════════
# 2. _assembly_v2.py — 新增节点 + 路由变更
# ════════════════════════════════════════════════════════════════

ASSEMBLY_IMPORTS = '''
from src.core.knowledge_qa.nodes.fast_knowledge_match import fast_knowledge_match_node
from src.core.knowledge_qa.nodes_v2.knowledge_synthesis_v2 import knowledge_synthesis_v2_node
'''

ASSEMBLY_ROUTE_MATCH_BOOKS = '''
def _route_after_match_books(state: KnowledgeQAState) -> str:
    """匹配到书籍 → 先走自定义知识匹配；未匹配 → 直接结束。"""
    if state.matched_book_ids:
        return "fast_knowledge_match"
    return "finalize"
'''

ASSEMBLY_NODES = '''
    workflow.add_node("fast_knowledge_match", fast_knowledge_match_node)
    workflow.add_node("knowledge_synthesis_v2", knowledge_synthesis_v2_node)
'''

ASSEMBLY_EDGES = '''
    # match_books → fast_knowledge_match / finalize
    workflow.add_conditional_edges(
        "match_books", _route_after_match_books,
        {"fast_knowledge_match": "fast_knowledge_match", "finalize": "finalize"},
    )

    # fast_knowledge_match → query_neo4j_graph（无条件，不短路）
    workflow.add_edge("fast_knowledge_match", "query_neo4j_graph")

    # knowledge_synthesis_v2 替代 contradiction_audit_v2
    workflow.add_edge("generate_s4_citations", "knowledge_synthesis_v2")
    workflow.add_edge("knowledge_synthesis_v2", "conclusion")

    # 删除旧边:
    # workflow.add_edge("generate_s4_citations", "contradiction_audit_v2")  ← 删除
    # workflow.add_edge("contradiction_audit_v2", "conclusion")             ← 删除
'''


# ════════════════════════════════════════════════════════════════
# 3. nodes/prefetch_context.py — 删除 skip + 增强 question
# ════════════════════════════════════════════════════════════════

PREFETCH_DELETE_SKIP = '''
# 删除第 32-33 行:
#   if state.knowledge_context:
#       return {"current_step": ["prefetch_context_skipped"]}
# 原因: 自定义知识命中后 knowledge_context 可能已有内容，但 LazyGraphRAG 仍需补充
'''

PREFETCH_ENHANCE_CALL = '''
# 修改 _do_prefetch 调用:
# 旧: _do_prefetch(state.question, book_ids)
# 新: _do_prefetch(state.question, book_ids, state.custom_knowledge_entities)
'''

PREFETCH_ENHANCE_DEF = '''
# 修改 _do_prefetch 签名:
# 旧: async def _do_prefetch(question: str, book_ids: list[str]) -> ...
# 新: async def _do_prefetch(question: str, book_ids: list[str], custom_entities: list[str] = None) -> ...

# 修改遍历时的 question:
# 旧: hits = await explore_community_tree(question=question, ...)
# 新:
#     enhanced_q = question
#     if custom_entities:
#         enhanced_q = question + " " + " ".join(custom_entities[:5])
#     hits = await explore_community_tree(question=enhanced_q, ...)
'''


# ════════════════════════════════════════════════════════════════
# 4. nodes_v2/query_neo4j_graph.py — 增强 s2_problems
# ════════════════════════════════════════════════════════════════

QUERY_NEO4J_ENHANCE = '''
# 修改 s2_problems 参数:
# 旧: s2_problems=[p["name"] for p in s2_data.get("problems", [])]
# 新: s2_problems=[p["name"] for p in s2_data.get("problems", [])] + list(getattr(state, "custom_knowledge_entities", []) or [])
'''


# ════════════════════════════════════════════════════════════════
# 5. nodes/base.py — _build_full_user_message 新增参数
# ════════════════════════════════════════════════════════════════

BASE_SIGNATURE = '''
# 修改签名:
# 旧: def _build_full_user_message(user_message, search_context, previous_sections, knowledge_context, exercise_context=""):
# 新: def _build_full_user_message(user_message, search_context, previous_sections, custom_knowledge_context="", knowledge_context="", exercise_context=""):
'''

BASE_BODY = '''
# 在 parts = [user_message_from_template] 之后新增:
#     if custom_knowledge_context:
#         parts.append(f"\\n\\n{custom_knowledge_context}")
'''

BASE_CALL_SITE = '''
# 修改调用处:
# 旧: knowledge_context=state.knowledge_context or "",
# 新:
#     custom_knowledge_context=getattr(state, "custom_knowledge_context", "") or "",
#     knowledge_context=state.knowledge_context or "",
'''


# ════════════════════════════════════════════════════════════════
# 6. nodes/conclusion.py — 注入三层综合
# ════════════════════════════════════════════════════════════════

CONCLUSION_SYNTHESIS = '''
# 在 build_msg 中，替换原有 contradictions 注入为三层综合:

# 旧:
#     if s.contradictions:
#         parts.append("## 跨书籍观点差异\\n...")
#         for c in s.contradictions: ...

# 新:
#     synthesis = s.three_layer_synthesis
#     if synthesis:
#         for item in synthesis.get("consensus", []):
#             sources = "、".join(f"《{b}》" for b in item.get("sources", []))
#             parts.append(f"## ✅ 统一共识\\n{item.get('agreement', '')}\\n📖 来源: {sources}")
#         for item in synthesis.get("complementary", []):
#             parts.append(f"## 🧩 互补完善\\n{item.get('integrated_summary', '')}")
#         for item in synthesis.get("conflicts", []):
#             va = item.get("view_a", {})
#             vb = item.get("view_b", {})
#             parts.append(
#                 f"## ⚠️ 冲突辨析\\n"
#                 f"- 📖 《{va.get('book', '')}》: {va.get('position', '')}\\n"
#                 f"- 📖 《{vb.get('book', '')}》: {vb.get('position', '')}\\n"
#                 f"🔍 原因: {item.get('why_different', '')}\\n"
#                 f"💡 建议: {item.get('recommendation', '')}"
#             )
#     elif s.contradictions:
#         # 降级: 无三层综合时使用旧的 contradictions
#         parts.append("## 跨书籍观点差异\\n")
#         for c in s.contradictions:
#             parts.append(f"- **{c.get('topic', '')}**\\n  ...")
'''
