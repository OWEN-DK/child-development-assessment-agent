"""第 4 节并行展开 v2：Prescription 从 Neo4j 获取 + LLM 微调。

在 v1 基础上：
1. 优先从 Neo4j 查询 Prescription 节点（运动处方：频率/时长/强度/年龄）
2. Neo4j 有处方数据时直接使用，LLM 仅做个性化微调
3. Neo4j 无处方时回退到 v1 全量 LLM 生成
"""

import asyncio
import json
import logging
from typing import Any, Dict, List

from src.core.knowledge_qa.nodes.plan_expand_parallel import (
    plan_expand_parallel_node as _v1_node,
    _extract_exercise_slots,
)
from src.schemas.knowledge_qa import KnowledgeQAState, push_progress

logger = logging.getLogger(__name__)


def _find_prescriptions(neo4j_knowledge: dict, exercise_names: list[str]) -> dict:
    """从 Neo4j 知识中查找运动处方。"""
    exercises = neo4j_knowledge.get("exercises", [])
    prescription_map = {}

    for ex in exercises:
        name = ex.get("name", "")
        if name in exercise_names:
            prescription = ex.get("prescription")
            if prescription:
                prescription_map[name] = prescription

    return prescription_map


async def plan_expand_parallel_v2_node(state: KnowledgeQAState) -> Dict[str, Any]:
    """第 4 节并行展开 v2：Neo4j Prescription + LLM 微调。"""
    if not state.section_4_outline:
        logger.warning("S4 expand v2: 无大纲，回退 v1")
        return await _v1_node(state)

    # 提取运动名称
    slots = _extract_exercise_slots(state.section_4_outline)
    exercise_names = [s.get("exercise", {}).get("name", "") for s in slots if s.get("exercise", {}).get("name")]

    # 查找 Neo4j 处方
    prescriptions = _find_prescriptions(state.neo4j_knowledge, exercise_names)

    if prescriptions:
        logger.info("S4 expand v2: 找到 %d 个 Neo4j 处方", len(prescriptions))
        await push_progress(
            "section_4_expanding",
            f"正在融合知识图谱处方数据展开运动方案（{len(prescriptions)} 个处方）…",
        )
        # 将处方数据注入 exercise_context 供 LLM 参考
        rx_lines = ["## 知识图谱运动处方参考"]
        for name, rx in prescriptions.items():
            rx_lines.append(f"### {name}")
            for k, v in rx.items():
                if v:
                    rx_lines.append(f"- {k}: {v}")
        rx_context = "\n".join(rx_lines)

        enriched = state.model_copy(update={
            "exercise_context": (state.exercise_context or "") + f"\n\n{rx_context}",
        })
        return await _v1_node(enriched)

    logger.info("S4 expand v2: Neo4j 无处方数据，回退 v1")
    return await _v1_node(state)
