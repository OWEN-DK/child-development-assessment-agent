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

from src.core.knowledge_qa.bundle import CrossBookConflict, CrossBookConsensus, KnowledgeBundle
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



def _extract_three_layers_from_bundle(
    consensus_list: list[CrossBookConsensus],
    conflicts_list: list[CrossBookConflict],
) -> dict:
    """从 Bundle 跨书关系提取三层综合结果。

    替代 _extract_three_layers——直接消费 Bundle 数据，
    避免重复查询 Neo4j。
    """
    if not consensus_list and not conflicts_list:
        return {}

    _consensus, _complementary, _conflicts = [], [], []

    for c in consensus_list:
        topic = c.entity_name
        books = c.books or []
        sources = list(dict.fromkeys(books))  # 去重保序
        entry = {
            "topic": topic,
            "source_book": sources[0] if sources else "",
            "target_book": sources[1] if len(sources) > 1 else "",
            "explanation": c.description or "",
        }

        if c.relation_type == "SAME_AS":
            _consensus.append({
                "topic": entry["topic"],
                "agreement": entry["explanation"] or f"两书对 {topic} 达成共识",
                "confidence": "high",
                "sources": sources,
            })
        elif c.relation_type in ("CROSS_BOOK_COMPLEMENTS", "CROSS_TREATS"):
            _complementary.append({
                "topic": entry["topic"],
                "fragments": [
                    {"book": s, "perspective": entry["explanation"] if s == sources[0] else ""}
                    for s in sources
                ],
                "integrated_summary": entry["explanation"] or f"多书从不同角度补充 {topic}",
            })

    for c in conflicts_list:
        books = c.books or []
        _conflicts.append({
            "topic": c.entity_name,
            "view_a": {"book": books[0] if books else "", "position": c.positions[0] if c.positions else ""},
            "view_b": {"book": books[1] if len(books) > 1 else "", "position": c.positions[1] if len(c.positions) > 1 else ""},
            "why_different": c.neo4j_relation_type,
            "recommendation": "请根据孩子具体情况选择",
            "severity": "moderate",
        })

    if not any([_consensus, _complementary, _conflicts]):
        return {}

    return {
        "consensus": _consensus,
        "complementary": _complementary,
        "conflicts": _conflicts,
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
        import asyncio
        from src.core.knowledge_qa.nodes.base import _get_model_name, get_timeout
        model_name = await _get_model_name("knowledge_synthesis")
        model = LLMServiceFactoryCompat.create_raw(model_name=model_name, temperature=0.2)
        timeout = get_timeout("knowledge_synthesis")
        resp = await asyncio.wait_for(
            model.ainvoke([
                SystemMessage(content=system),
                HumanMessage(content="\n\n".join(sections_text)),
            ]),
            timeout=timeout,
        )
        raw = resp.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
        return json.loads(raw)
    except asyncio.TimeoutError:
        logger.warning("LLM three-layer inference timed out (%ds)", timeout)
        return {}
    except Exception as e:
        logger.warning(f"LLM three-layer inference failed: {e}")
        return {}


async def knowledge_synthesis_v2_node(state: KnowledgeQAState) -> Dict[str, Any]:
    """三层知识综合: 统一共识 / 互补完善 / 冲突辨析。"""
    await push_progress("knowledge_synthesis", "正在综合多书知识…")

    # Step 1: 优先从 Bundle 提取跨书关系（避免重复查询 Neo4j）
    bundle = getattr(state, "knowledge_bundle", None)
    bundle_has_cross_book = (
        isinstance(bundle, KnowledgeBundle)
        and (bundle.cross_book_consensus or bundle.cross_book_conflicts)
    )
    if bundle_has_cross_book:
        synthesis = _extract_three_layers_from_bundle(
            bundle.cross_book_consensus,
            bundle.cross_book_conflicts,
        )
        logger.info("三层综合: 从 Bundle 消费跨书关系")
    else:
        synthesis = _extract_three_layers(state.neo4j_knowledge)

    # Step 2: Neo4j 不足时 LLM 推断（仅多书场景）
    if not synthesis:
        matched = state.matched_books_detail or []
        if len(matched) >= 2:
            logger.info("Neo4j 无跨书关系，LLM 推断三层")
            synthesis = await _llm_infer_three_layers(state)

    if not synthesis:
        return {"three_layer_synthesis": {}, "current_step": ["synthesis_empty"]}

    # Step 3: 剔除冲突层 — 仅保留共识与互补，不输出 contradictions
    synthesis.pop("conflicts", None)

    logger.info(
        f"三层综合完成: consensus={len(synthesis.get('consensus', []))}, "
        f"complementary={len(synthesis.get('complementary', []))}"
    )

    return {
        "three_layer_synthesis": synthesis,
        "contradictions": [],
        "current_step": ["synthesis_done"],
    }
