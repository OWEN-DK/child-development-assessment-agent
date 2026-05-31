"""三层知识综合节点 — 替代 contradiction_audit_v2

放置位置: backend/src/core/knowledge_qa/nodes_v2/knowledge_synthesis_v2.py

从 Neo4j 跨书关系提取三层:
  1. 统一共识层 (CROSS_BOOK_CONSENSUS)
  2. 互补完善层 (CROSS_BOOK_COMPLEMENTS)
  3. 冲突辨析层 (CROSS_BOOK_CONFLICTS)

Neo4j 数据不足时由 LLM 从前 4 节内容推断。
同时写入 three_layer_synthesis + contradictions（向后兼容）。
"""

from __future__ import annotations
import json
import logging
from typing import Any, Dict

from src.schemas.knowledge_qa import KnowledgeQAState, push_progress

logger = logging.getLogger(__name__)


def _extract_three_layers(neo4j_knowledge: dict) -> Dict[str, Any]:
    """从 Neo4j 跨书关系提取三层综合结果。"""
    cross = neo4j_knowledge.get("cross_book_relations", [])
    if not cross:
        return {}

    consensus, complementary, conflicts = [], [], []

    for rel in cross:
        rtype = rel.get("relation_type", "")
        entry = {
            "topic": f"{rel.get('source_entity', '')} ↔ {rel.get('target_entity', '')}",
            "source_book": rel.get("source_book", ""),
            "target_book": rel.get("target_book", ""),
            "explanation": rel.get("explanation", ""),
        }

        if "CONSENSUS" in rtype:
            consensus.append({
                "topic": entry["topic"],
                "agreement": entry["explanation"] or f"两书对 {entry['topic']} 达成共识",
                "confidence": "high",
                "sources": [entry["source_book"], entry["target_book"]],
            })
        elif "COMPLEMENTS" in rtype:
            complementary.append({
                "topic": entry["topic"],
                "fragments": [
                    {"book": entry["source_book"], "perspective": entry["explanation"]},
                ],
                "integrated_summary": entry["explanation"] or f"两书从不同角度补充 {entry['topic']}",
            })
        elif "CONFLICTS" in rtype:
            conflicts.append({
                "topic": entry["topic"],
                "view_a": {"book": entry["source_book"], "position": ""},
                "view_b": {"book": entry["target_book"], "position": ""},
                "why_different": entry["explanation"],
                "recommendation": "请根据孩子具体情况选择",
                "severity": "moderate",
            })

    if not any([consensus, complementary, conflicts]):
        return {}

    return {
        "consensus": consensus,
        "complementary": complementary,
        "conflicts": conflicts,
    }


async def _llm_infer_three_layers(state: KnowledgeQAState) -> Dict[str, Any]:
    """Neo4j 数据不足时，LLM 从前 4 节内容推断三层。"""
    from src.core.llm.factory import LLMServiceFactoryCompat
    from langchain_core.messages import HumanMessage, SystemMessage

    sections_text = []
    for i in range(1, 5):
        sec = state.sections.get(i)
        if sec and sec.content:
            sections_text.append(f"第{i}节 ({sec.title}): {sec.content[:800]}")

    if len(sections_text) < 2:
        return {}

    system = (
        "基于以下多个知识节的内容，从三个维度综合分析。\n\n"
        "输出严格 JSON:\n"
        "{\n"
        '  "consensus": [{"topic": "...", "agreement": "...", "confidence": "high", "sources": ["..."]}],\n'
        '  "complementary": [{"topic": "...", "fragments": [{"book": "...", "perspective": "..."}], "integrated_summary": "..."}],\n'
        '  "conflicts": [{"topic": "...", "view_a": {"book": "...", "position": "..."}, "view_b": {"book": "...", "position": "..."}, "why_different": "...", "recommendation": "..."}]\n'
        "}\n\n"
        "如果某个维度无数据，返回空数组。"
    )

    try:
        model = LLMServiceFactoryCompat.create_raw(model_name="qwen3.5-27b", temperature=0.2)
        resp = await model.ainvoke([
            SystemMessage(content=system),
            HumanMessage(content="\n\n".join(sections_text)),
        ])
        raw = resp.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
        return json.loads(raw)
    except Exception as e:
        logger.warning(f"LLM three-layer inference failed: {e}")
        return {}


async def knowledge_synthesis_v2_node(state: KnowledgeQAState) -> Dict[str, Any]:
    """三层知识综合: 统一共识 / 互补完善 / 冲突辨析。"""
    await push_progress("knowledge_synthesis", "正在综合多书知识…")

    # Step 1: 从 Neo4j 提取
    synthesis = _extract_three_layers(state.neo4j_knowledge)

    # Step 2: Neo4j 不足时 LLM 推断（仅多书场景）
    if not synthesis:
        matched = state.matched_books_detail or []
        if len(matched) >= 2:
            logger.info("Neo4j 无跨书关系，LLM 推断三层")
            synthesis = await _llm_infer_three_layers(state)

    if not synthesis:
        return {"three_layer_synthesis": {}, "current_step": ["synthesis_empty"]}

    # Step 3: 兼容 — 从 conflicts 提取 contradictions
    contradictions = []
    for c in synthesis.get("conflicts", []):
        contradictions.append({
            "topic": c.get("topic", ""),
            "view_a": f"{c.get('view_a', {}).get('book', '')}: {c.get('view_a', {}).get('position', '')}",
            "view_b": f"{c.get('view_b', {}).get('book', '')}: {c.get('view_b', {}).get('position', '')}",
            "resolution": c.get("recommendation", ""),
            "severity": c.get("severity", "moderate"),
        })

    logger.info(
        f"三层综合完成: consensus={len(synthesis.get('consensus', []))}, "
        f"complementary={len(synthesis.get('complementary', []))}, "
        f"conflicts={len(synthesis.get('conflicts', []))}"
    )

    return {
        "three_layer_synthesis": synthesis,
        "contradictions": contradictions,
        "current_step": ["synthesis_done"],
    }
