"""Phase 2: 增量实体消歧。

放置位置: backend/src/core/knowledge_qa/neo4j/entity_resolver.py
"""

from __future__ import annotations

import logging
from typing import Protocol

from .master_graph import MasterGraph
from .models import EntityMatchJudgment, ExtractedEntity

logger = logging.getLogger(__name__)


class EmbeddingClient(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class LLMClient(Protocol):
    async def generate_structured(
        self, prompt: str, schema: type, model: str,
    ) -> dict | list: ...


SAME_ENTITY_PROMPT = """判断以下两个实体是否指同一事物。

实体 A: {name_a}
描述: {desc_a}

实体 B: {name_b}
描述: {desc_b}

判断标准:
- 名称相同或高度相似（如"ADHD"和"注意力缺陷多动障碍"）
- 描述指向同一概念（即使措辞不同）
- 如果一个是有别名/缩写，另一个是全称，视为相同
"""


def cosine_similarity_matrix(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    """计算两组向量的余弦相似度矩阵。"""
    import math

    def _norm(v: list[float]) -> float:
        return math.sqrt(sum(x * x for x in v))

    result = []
    for va in a:
        row = []
        na = _norm(va)
        for vb in b:
            nb = _norm(vb)
            if na == 0 or nb == 0:
                row.append(0.0)
            else:
                dot = sum(x * y for x, y in zip(va, vb))
                row.append(dot / (na * nb))
        result.append(row)
    return result


async def resolve_and_merge(
    new_entities: list[ExtractedEntity],
    chapter_id: str,
    master: MasterGraph,
    embedding_client: EmbeddingClient,
    llm_client: LLMClient,
    model: str = "qwen-turbo",
    similarity_threshold: float = 0.85,
) -> int:
    """将新章节的实体合入主图，处理消歧。

    Args:
        new_entities: 新章节提取的实体列表
        chapter_id: 章节 ID
        master: 主图
        embedding_client: embedding 客户端
        llm_client: LLM 客户端
        model: LLM 模型名称
        similarity_threshold: 相似度阈值

    Returns:
        合并的实体数量
    """
    existing_names = list(master.graph.nodes)
    if not existing_names:
        # 主图为空，直接添加所有实体
        for entity in new_entities:
            master.add_entity(entity, chapter_id)
        return 0

    # 获取已有实体的 embedding
    existing_embeddings = await embedding_client.embed(existing_names)
    merged_count = 0

    for entity in new_entities:
        # 获取新实体的 embedding
        new_emb_list = await embedding_client.embed([entity.name])
        new_emb = new_emb_list[0]

        # 计算与所有已有实体的相似度
        sims = cosine_similarity_matrix([new_emb], existing_embeddings)[0]

        # 找到最相似的已有实体
        best_idx = int(max(range(len(sims)), key=lambda i: sims[i]))
        best_sim = sims[best_idx]
        best_name = existing_names[best_idx]

        if best_sim >= similarity_threshold:
            # 高相似度 → LLM 精判
            existing_desc = master.graph.nodes[best_name].get("description", "")
            judgment = await llm_client.generate_structured(
                prompt=SAME_ENTITY_PROMPT.format(
                    name_a=entity.name,
                    desc_a=entity.description,
                    name_b=best_name,
                    desc_b=existing_desc,
                ),
                schema=EntityMatchJudgment,
                model=model,
            )

            if isinstance(judgment, EntityMatchJudgment) and judgment.same:
                master.merge_entity(canonical=best_name, alias=entity.name)
                # 补充新章节的段落来源
                master.add_entity(
                    ExtractedEntity(
                        name=best_name,
                        entity_type=entity.entity_type,
                        description=entity.description,
                        source_para_ids=entity.source_para_ids,
                    ),
                    chapter_id,
                )
                merged_count += 1
                logger.info(
                    "消歧合并: '%s' → '%s' (sim=%.2f, reason=%s)",
                    entity.name, best_name, best_sim, judgment.reason,
                )
                continue

        # 不同实体或低相似度 → 新增
        master.add_entity(entity, chapter_id)

    logger.info(
        "实体消歧完成: %d 新实体, %d 合并",
        len(new_entities) - merged_count, merged_count,
    )
    return merged_count
