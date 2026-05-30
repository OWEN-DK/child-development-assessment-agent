"""第 3 节 v2：运动类型推荐 — 融合 Neo4j Exercise + diversity_rerank。

在 v1 基础上：
1. 优先从 Neo4j 查询匹配的 Exercise 节点（按年龄、问题筛选）
2. 使用 diversity_rerank 保证来源多样性
3. Neo4j 无结果时回退到 v1 全量清单 + LLM 选择
"""

import asyncio
import json
import logging
from typing import Any, Dict

from src.core.knowledge_qa.nodes.recommend_types import recommend_types_node as _v1_node
from src.schemas.knowledge_qa import KnowledgeQAState, push_progress

logger = logging.getLogger(__name__)


async def recommend_types_v2_node(state: KnowledgeQAState) -> Dict[str, Any]:
    """第 3 节 v2：运动类型推荐，融合 Neo4j Exercise + diversity_rerank。"""
    neo4j_exercises = state.neo4j_knowledge.get("exercises", [])

    if neo4j_exercises:
        logger.info("S3 v2: 使用 Neo4j Exercise 列表 (%d 条)", len(neo4j_exercises))
        await push_progress(
            "section_3_generating",
            f"正在从知识图谱筛选运动类型（{len(neo4j_exercises)} 个候选）…",
        )

        # 多样性重排
        try:
            from src.core.knowledge_qa.neo4j.diversity_rerank import diversity_rerank
            reranked = diversity_rerank(neo4j_exercises, top_k=20)
            logger.info("S3 v2: diversity_rerank 完成，保留 %d 条", len(reranked))

            # 将 Neo4j 候选注入 state 的 filtered_exercise_candidates 供审计
            candidates_md = _format_neo4j_exercises_as_markdown(reranked)
            state_copy = state.model_copy(update={
                "filtered_exercise_candidates": candidates_md,
            })
            return await _v1_node(state_copy)
        except Exception as e:
            logger.warning("S3 v2: diversity_rerank 失败，回退 v1: %s", e)

    # 降级：回退到 v1 全量清单
    logger.info("S3 v2: Neo4j 无运动数据，回退到 v1 全量清单")
    return await _v1_node(state)


def _format_neo4j_exercises_as_markdown(exercises: list) -> str:
    """将 Neo4j Exercise 结果格式化为 Markdown。"""
    if not exercises:
        return ""

    lines = ["## 知识图谱推荐运动候选", ""]
    for ex in exercises:
        name = ex.get("name", "未知")
        category = ex.get("category", "")
        age_range = ex.get("age_range", "")
        benefits = ex.get("benefits", "")
        source = ex.get("source_book", "")

        line = f"### {name}"
        if category:
            line += f"\n- 类别: {category}"
        if age_range:
            line += f"\n- 适用年龄: {age_range}"
        if benefits:
            line += f"\n- 益处: {benefits}"
        if source:
            line += f"\n- 来源: {source}"
        lines.append(line)
        lines.append("")

    return "\n".join(lines)
