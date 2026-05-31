"""Phase 2: 增量实体消歧。

放置位置: backend/src/core/knowledge_qa/d2g/entity_resolver.py
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


# ──────────────────────────────────────────────────────────────
# 全局批量消歧（Blocking + Pairwise + Union-Find）
# ──────────────────────────────────────────────────────────────

import math


def _cosine(a: list[float], b: list[float]) -> float:
    """计算两个向量的余弦相似度。"""
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


class UnionFind:
    """并查集：追踪实体等价类，支持传递合并（A=B, B=C → A=C）。"""

    def __init__(self):
        self.parent: dict[str, str] = {}
        self.rank: dict[str, int] = {}

    def make(self, x: str) -> None:
        """初始化：每个元素自成一组。"""
        if x not in self.parent:
            self.parent[x] = x
            self.rank[x] = 0

    def find(self, x: str) -> str:
        """查找根代表（路径压缩）。"""
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]

    def union(self, x: str, y: str) -> None:
        """合并两组（按秩合并）。"""
        rx, ry = self.find(x), self.find(y)
        if rx == ry:
            return
        if self.rank[rx] < self.rank[ry]:
            rx, ry = ry, rx
        self.parent[ry] = rx
        if self.rank[rx] == self.rank[ry]:
            self.rank[rx] += 1

    def clusters(self) -> dict[str, list[str]]:
        """输出所有等价类 {root: [members]}。"""
        groups: dict[str, list[str]] = {}
        for x in self.parent:
            root = self.find(x)
            groups.setdefault(root, []).append(x)
        return groups


async def batch_resolve_entities(
    staging_extractions: dict[str, "ChapterExtraction"],
    master: MasterGraph,
    embedding_client: EmbeddingClient,
    llm_client: LLMClient,
    model: str = "qwen-turbo",
    similarity_threshold: float = 0.85,
) -> tuple[dict[str, list[str]], list[dict]]:
    """全局消歧：两级 Blocking + Pairwise + Union-Find。

    1. 收集所有章节的实体
    2. 两级 Blocking（类型内 + 全局 embedding top-k）
    3. 候选对 LLM 精判
    4. Union-Find 合并输出等价类
    5. 代表实体 + 映射后关系入图

    Args:
        staging_extractions: {chapter_id: ChapterExtraction}
        master: 主图（消歧后的实体和关系写入此处）
        embedding_client: embedding 客户端
        llm_client: LLM 客户端
        model: LLM 模型名称
        similarity_threshold: 相似度阈值

    Returns:
        (merge_map, merge_log)
        merge_map: {representative: [alias1, alias2, ...]}
        merge_log: [{alias, representative, similarity, reason}, ...]
    """
    from .models import ExtractedRelationship

    # ── 收集所有实体（去重：同名实体保留最长描述）──
    entity_pool: dict[str, ExtractedEntity] = {}
    for ch_id, ext in staging_extractions.items():
        for e in ext.entities:
            if e.name not in entity_pool or len(e.description) > len(entity_pool[e.name].description):
                entity_pool[e.name] = e
    all_entities = list(entity_pool.values())
    if not all_entities:
        return {}, []

    all_names = [e.name for e in all_entities]
    entity_desc = {e.name: e.description for e in all_entities}
    entity_type = {e.name: e.entity_type for e in all_entities}

    logger.info("全局消歧开始: %d 个唯一实体", len(all_entities))

    # ── Step 1: 全局 embedding ──
    all_embs = await embedding_client.embed(all_names)
    emb_index = {name: emb for name, emb in zip(all_names, all_embs)}

    # ── Step 2: 两级 Blocking ──
    # Level 1: 按 entity_type 分桶，桶内 pairwise
    type_buckets: dict[str, list[str]] = {}
    for name in all_names:
        type_buckets.setdefault(entity_type[name], []).append(name)

    candidate_pairs: set[tuple[str, str]] = set()

    for etype, bucket in type_buckets.items():
        if len(bucket) < 2:
            continue
        for i in range(len(bucket)):
            for j in range(i + 1, len(bucket)):
                sim = _cosine(emb_index[bucket[i]], emb_index[bucket[j]])
                if sim >= similarity_threshold * 0.9:
                    candidate_pairs.add(tuple(sorted([bucket[i], bucket[j]])))

    # Level 2: 全局 top-k 近邻（跨类型兜底）
    for i, name in enumerate(all_names):
        sims = [
            (j, _cosine(all_embs[i], all_embs[j]))
            for j in range(len(all_names))
            if j != i
        ]
        sims.sort(key=lambda x: x[1], reverse=True)
        for j, sim in sims[:10]:
            if sim >= similarity_threshold * 0.9:
                candidate_pairs.add(tuple(sorted([all_names[i], all_names[j]])))

    logger.info(
        "Blocking 完成: %d 个桶, %d 个候选对",
        len(type_buckets), len(candidate_pairs),
    )

    if not candidate_pairs:
        logger.info("无候选对，跳过 LLM 判定")
        # 直接入图（无合并）
        _ingest_to_graph(staging_extractions, master, {})
        return {}, []

    # ── Step 3: LLM 判定 + Step 4: Union-Find 合并 ──
    uf = UnionFind()
    for name in all_names:
        uf.make(name)

    merge_log: list[dict] = []

    for name_a, name_b in candidate_pairs:
        try:
            judgment = await llm_client.generate_structured(
                prompt=SAME_ENTITY_PROMPT.format(
                    name_a=name_a,
                    desc_a=entity_desc.get(name_a, ""),
                    name_b=name_b,
                    desc_b=entity_desc.get(name_b, ""),
                ),
                schema=EntityMatchJudgment,
                model=model,
            )
            if isinstance(judgment, EntityMatchJudgment) and judgment.same:
                sim = _cosine(emb_index[name_a], emb_index[name_b])
                uf.union(name_a, name_b)
                merge_log.append({
                    "alias": name_b,
                    "representative": name_a,
                    "similarity": round(sim, 3),
                    "reason": getattr(judgment, "reason", ""),
                })
                logger.info(
                    "消歧合并: '%s' ↔ '%s' (sim=%.2f, reason=%s)",
                    name_a, name_b, sim, getattr(judgment, "reason", ""),
                )
        except Exception as e:
            logger.warning("消歧 LLM 判定失败: %s ↔ %s: %s", name_a, name_b, e)

    # ── Step 5: 代表选举（描述最长的为代表）──
    clusters = uf.clusters()
    merge_map: dict[str, str] = {}  # alias → representative
    for root, members in clusters.items():
        representative = max(members, key=lambda n: len(entity_desc.get(n, "")))
        for m in members:
            merge_map[m] = representative

    # ── Step 6: 消歧后入图 ──
    _ingest_to_graph(staging_extractions, master, merge_map)

    merged_count = sum(1 for a, b in merge_map.items() if a != b)
    logger.info(
        "全局消歧完成: %d 实体 → %d 簇, %d 次合并",
        len(all_entities), len(clusters), merged_count,
    )

    # 输出 {representative: [aliases]}
    rep_to_aliases: dict[str, list[str]] = {}
    for alias, rep in merge_map.items():
        rep_to_aliases.setdefault(rep, []).append(alias)

    return rep_to_aliases, merge_log


def _ingest_to_graph(
    staging_extractions: dict[str, "ChapterExtraction"],
    master: MasterGraph,
    merge_map: dict[str, str],
) -> None:
    """将 staging 中的实体和关系经 merge_map 映射后写入主图。"""
    from .models import ExtractedRelationship

    for ch_id, ext in staging_extractions.items():
        # 设置段落总数
        para_count = max(
            (pid for e in ext.entities for pid in e.source_para_ids),
            default=0,
        )
        master.chapter_para_count[ch_id] = para_count

        # 实体入图（映射到代表实体）
        for entity in ext.entities:
            rep = merge_map.get(entity.name, entity.name)
            master.add_entity(
                ExtractedEntity(
                    name=rep,
                    entity_type=entity.entity_type,
                    description=entity.description,
                    source_para_ids=entity.source_para_ids,
                ),
                ch_id,
            )

        # 关系入图（source/target 映射到代表实体）
        for rel in ext.relationships:
            mapped_src = merge_map.get(rel.source, rel.source)
            mapped_tgt = merge_map.get(rel.target, rel.target)
            master.add_relationship(
                ExtractedRelationship(
                    source=mapped_src,
                    target=mapped_tgt,
                    relation_type=rel.relation_type,
                    evidence=rel.evidence,
                    source_para_ids=rel.source_para_ids,
                    relation_source=rel.relation_source,
                    confidence=rel.confidence,
                ),
                ch_id,
            )
