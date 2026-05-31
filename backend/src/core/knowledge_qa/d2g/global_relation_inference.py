"""Phase 2.5: 全局关系补全 + 关系类型语义合并。

在所有章节提取 + 审核合入后，质量审计前执行。
包含 4 个子步骤：
  Step 0: 关系类型语义合并（将 LLM 自由输出的关系类型归类到标准类型）
  Step 1: 基于类型规则的启发式推断（零 LLM 成本）
  Step 2: 基于 Embedding 的语义关联（低成本）
  Step 3: LLM 全局孤立实体补全（兜底）

放置位置: backend/src/core/knowledge_qa/d2g/global_relation_inference.py
"""

from __future__ import annotations

import logging
from typing import Protocol

from .master_graph import MasterGraph
from .models import ExtractedRelationship, RelationType

logger = logging.getLogger(__name__)


class EmbeddingClient(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class LLMClient(Protocol):
    async def generate_structured(self, prompt: str, schema: type, model: str) -> dict | list: ...


# ──────────────────────────────────────────────────────────────
# Step 0: 关系类型语义合并
# ──────────────────────────────────────────────────────────────

# 标准关系类型（优先映射到这些）
CANONICAL_RELATION_TYPES: set[str] = {e.value for e in RelationType}


async def merge_relation_types(
    master: MasterGraph,
    embedding_client: EmbeddingClient,
    similarity_threshold: float = 0.80,
) -> dict[str, str]:
    """Step 0: 将图中所有自由形式的关系类型按语义相似度合并为标准类型。

    流程：
    1. 收集图中所有唯一关系类型
    2. 对每个关系类型做 embedding
    3. 计算与所有标准类型的相似度
    4. 如果最相似的标准类型 similarity >= threshold，则替换
    5. 否则保留原始值

    Args:
        master: 主图
        embedding_client: embedding 客户端
        similarity_threshold: 合并阈值

    Returns:
        映射表 {原始关系类型 → 合并后关系类型}
    """
    G = master.graph

    # 收集所有唯一关系类型
    raw_types: set[str] = set()
    for _, _, data in G.edges(data=True):
        rt = data.get("relation_type", "RELATES_TO")
        raw_types.add(rt)

    # 只处理非标准类型
    non_canonical = [t for t in raw_types if t not in CANONICAL_RELATION_TYPES]
    if not non_canonical:
        logger.info("关系类型合并: 所有关系类型已是标准类型，跳过")
        return {}

    canonical_list = sorted(CANONICAL_RELATION_TYPES)
    logger.info(
        "关系类型合并: %d 个非标准类型, %d 个标准类型",
        len(non_canonical), len(canonical_list),
    )

    # Embedding 非标准类型和标准类型
    non_canonical_embs = await embedding_client.embed(non_canonical)
    canonical_embs = await embedding_client.embed(canonical_list)

    # 计算映射
    mapping: dict[str, str] = {}
    for i, raw_type in enumerate(non_canonical):
        best_sim = 0.0
        best_canonical = raw_type
        for j, canonical in enumerate(canonical_list):
            sim = _cosine_similarity(non_canonical_embs[i], canonical_embs[j])
            if sim > best_sim:
                best_sim = sim
                best_canonical = canonical
        if best_sim >= similarity_threshold:
            mapping[raw_type] = best_canonical
            logger.info("  合并: '%s' → '%s' (sim=%.3f)", raw_type, best_canonical, best_sim)
        else:
            mapping[raw_type] = raw_type  # 保留原始值
            logger.debug("  保留: '%s' (best_sim=%.3f < %.2f)", raw_type, best_sim, similarity_threshold)

    # 应用映射到图
    replaced = 0
    for _, _, data in G.edges(data=True):
        rt = data.get("relation_type", "RELATES_TO")
        if rt in mapping and mapping[rt] != rt:
            data["relation_type"] = mapping[rt]
            replaced += 1

    merged_count = sum(1 for v in mapping.values() if v != mapping.keys().__iter__().__next__() if False)
    merged_count = sum(1 for k, v in mapping.items() if k != v)
    logger.info("关系类型合并完成: %d 条边的关系类型被替换", replaced)

    return mapping


# ──────────────────────────────────────────────────────────────
# Step 1: 类型规则推断
# ──────────────────────────────────────────────────────────────

# (source_type, target_type, relation_type, description_template)
TYPE_RULES: list[tuple[str, str, str, str]] = [
    # 运动 → 认知/问题
    ("Exercise", "CognitiveProcess", "THERAPEUTIC_IMPROVES", "{s} 改善 {t}"),
    ("Exercise", "Problem", "THERAPEUTIC_ALLEVIATES", "{s} 缓解 {t}"),
    ("Exercise", "BrainRegion", "FUNCTIONAL_REGULATES", "{s} 调节 {t} 的功能"),
    ("Exercise", "RootCause", "THERAPEUTIC_INHIBITS", "{s} 抑制 {t}"),

    # 问题 → 根因/方案
    ("Problem", "RootCause", "CAUSAL_CAUSES", "{t} 导致 {s}"),
    ("Problem", "Solution", "THERAPEUTIC_TREATS", "{t} 治疗 {s}"),
    ("Problem", "Risk", "CAUSAL_CONTRIBUTES_TO", "{t} 促成 {s}"),
    ("Problem", "BrainRegion", "FUNCTIONAL_INVOLVED_IN", "{s} 涉及 {t}"),

    # 脑区关系
    ("BrainRegion", "BrainRegion", "STRUCTURAL_PART_OF", "{s} 是 {t} 的一部分"),
    ("BrainRegion", "CognitiveProcess", "FUNCTIONAL_REGULATES", "{s} 调节 {t}"),
    ("BrainRegion", "Mechanism", "FUNCTIONAL_MEDIATES", "{s} 通过 {t} 发挥作用"),

    # 风险因素
    ("Risk", "Problem", "CAUSAL_CONTRIBUTES_TO", "{s} 促成 {t}"),
    ("Risk", "CognitiveProcess", "THERAPEUTIC_INHIBITS", "{s} 损害 {t}"),

    # 评估工具
    ("AssessmentTool", "Problem", "ATTRIBUTE_MEASURED_BY", "{t} 通过 {s} 评估"),
    ("AssessmentTool", "CognitiveProcess", "ATTRIBUTE_MEASURED_BY", "{t} 通过 {s} 测量"),

    # 发展阶段
    ("DevelopmentalStage", "CognitiveProcess", "TEMPORAL_DEVELOPS_INTO", "{s} 阶段发展 {t}"),
    ("DevelopmentalStage", "Problem", "CAUSAL_CONTRIBUTES_TO", "{s} 阶段易出现 {t}"),

    # 机制
    ("Mechanism", "BrainRegion", "FUNCTIONAL_REGULATES", "{s} 调节 {t}"),
    ("Mechanism", "CognitiveProcess", "FUNCTIONAL_MEDIATES", "{s} 介导 {t}"),
    ("Mechanism", "Problem", "CAUSAL_CAUSES", "{s} 导致 {t}"),

    # 理论/研究
    ("Theory", "ResearchFinding", "EVIDENCE_BASED_ON", "{s} 基于 {t}"),
    ("Theory", "CognitiveProcess", "EVIDENCE_SUPPORTS", "{s} 支持 {t} 的理解"),
    ("ResearchFinding", "Problem", "EVIDENCE_DEMONSTRATES", "{t} 证实 {s}"),
    ("ResearchFinding", "Mechanism", "EVIDENCE_SUPPORTS", "{s} 支持 {t}"),

    # 策略
    ("Strategy", "Problem", "THERAPEUTIC_ALLEVIATES", "{s} 缓解 {t}"),
    ("Strategy", "CognitiveProcess", "THERAPEUTIC_IMPROVES", "{s} 改善 {t}"),

    # 处方
    ("Prescription", "Exercise", "STRUCTURAL_CONTAINS", "{s} 包含 {t}"),
    ("Prescription", "Problem", "THERAPEUTIC_TREATS", "{s} 治疗 {t}"),

    # 核心洞见
    ("KeyInsight", "CognitiveProcess", "EVIDENCE_SUPPORTS", "{s} 支持 {t}"),
    ("KeyInsight", "Problem", "EVIDENCE_DEMONSTRATES", "{s} 揭示 {t}"),

    # 概念（补充覆盖 Concept 类型）
    ("Concept", "CognitiveProcess", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 与 {t} 相关"),
    ("Concept", "Problem", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 与 {t} 相关"),
    ("Concept", "BrainRegion", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 涉及 {t}"),
    ("Concept", "Mechanism", "FUNCTIONAL_MEDIATES", "{s} 通过 {t} 体现"),

    # 事实/数据
    ("Fact", "Problem", "EVIDENCE_DEMONSTRATES", "{s} 证实 {t}"),
    ("Fact", "CognitiveProcess", "EVIDENCE_SUPPORTS", "{s} 支持 {t}"),
    ("Fact", "Mechanism", "EVIDENCE_SUPPORTS", "{s} 支持 {t}"),

    # 儿童特征
    ("ChildProfile", "Problem", "CAUSAL_CONTRIBUTES_TO", "{s} 易出现 {t}"),
    ("ChildProfile", "DevelopmentalStage", "TEMPORAL_DEVELOPS_INTO", "{s} 处于 {t}"),
    ("ChildProfile", "CognitiveProcess", "FUNCTIONAL_INVOLVED_IN", "{s} 涉及 {t}"),

    # 洞见 → 根因
    ("KeyInsight", "RootCause", "EVIDENCE_DEMONSTRATES", "{s} 揭示 {t}"),

    # 策略 → 根因
    ("Strategy", "RootCause", "THERAPEUTIC_INHIBITS", "{s} 应对 {t}"),
    ("Strategy", "Risk", "THERAPEUTIC_ALLEVIATES", "{s} 降低 {t}"),
]


def infer_relations_by_type_rules(master: MasterGraph) -> list[ExtractedRelationship]:
    """基于 entity_type 组合的启发式规则推断关系。

    遍历图中所有实体对，如果类型组合匹配规则且尚无直接关系，则推断一条关系。
    标记 confidence=0.5, relation_source="heuristic_rule"。
    """
    G = master.graph
    nodes = list(G.nodes)
    added: list[ExtractedRelationship] = []
    seen_keys: set[tuple] = set()

    # 预构建类型索引
    type_index: dict[str, list[str]] = {}
    for n in nodes:
        ntype = G.nodes[n].get("entity_type", "AutoEntity")
        type_index.setdefault(ntype, []).append(n)

    for src_type, tgt_type, rel_type, desc_tpl in TYPE_RULES:
        src_nodes = type_index.get(src_type, [])
        tgt_nodes = type_index.get(tgt_type, [])

        for s_name in src_nodes:
            for t_name in tgt_nodes:
                if s_name == t_name:
                    continue
                if t_name not in G:
                    continue
                # 跳过已有直接关系的实体对
                if G.has_edge(s_name, t_name):
                    continue
                key = (s_name, t_name, rel_type)
                if key in seen_keys:
                    continue
                seen_keys.add(key)

                rel = ExtractedRelationship(
                    source=s_name,
                    target=t_name,
                    relation_type=rel_type,
                    evidence=f"类型规则推断: {src_type} → {rel_type} → {tgt_type}",
                    source_para_ids=[],
                    relation_source="heuristic_rule",
                    confidence=0.5,
                )
                added.append(rel)

    logger.info("类型规则推断: 新增 %d 条关系", len(added))
    return added


# ──────────────────────────────────────────────────────────────
# Step 2: Embedding 语义关联
# ──────────────────────────────────────────────────────────────


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """计算两个向量的余弦相似度。"""
    import math
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


async def infer_relations_by_embedding(
    master: MasterGraph,
    embedding_client: EmbeddingClient,
    top_k: int = 3,
    threshold: float = 0.75,
) -> list[ExtractedRelationship]:
    """对仍然孤立的实体，基于 embedding 相似度建立语义关联。

    标记 confidence=0.4, relation_source="embedding_sim"。
    """
    G = master.graph

    # 找出孤立实体
    orphans = [n for n in G.nodes if G.degree(n) == 0]
    if not orphans:
        logger.info("Embedding 语义关联: 无孤立实体，跳过")
        return []

    # 找出非孤立实体（作为连接目标）
    non_orphans = [n for n in G.nodes if G.degree(n) > 0]
    if not non_orphans:
        logger.info("Embedding 语义关联: 无非孤立实体，跳过")
        return []

    # 获取 embedding
    orphan_embs = await embedding_client.embed(orphans)
    non_orphan_embs = await embedding_client.embed(non_orphans)

    added: list[ExtractedRelationship] = []

    for i, o_name in enumerate(orphans):
        o_emb = orphan_embs[i]
        # 计算与所有非孤立实体的相似度
        sims = [(j, _cosine_similarity(o_emb, n_emb)) for j, n_emb in enumerate(non_orphan_embs)]
        sims.sort(key=lambda x: x[1], reverse=True)

        count = 0
        for j, sim in sims:
            if sim < threshold or count >= top_k:
                break
            target_name = non_orphans[j]
            rel = ExtractedRelationship(
                source=o_name,
                target=target_name,
                relation_type=RelationType.ATTRIBUTE_ASSOCIATED_WITH,
                evidence=f"Embedding 语义关联 (sim={sim:.3f})",
                source_para_ids=[],
                relation_source="embedding_sim",
                confidence=0.4,
            )
            added.append(rel)
            count += 1

    logger.info("Embedding 语义关联: 为 %d 个孤立实体新增 %d 条关系", len(orphans), len(added))
    return added


# ──────────────────────────────────────────────────────────────
# Step 3: LLM 全局孤立实体补全
# ──────────────────────────────────────────────────────────────

GLOBAL_FIX_PROMPT = """你是儿童发展领域知识图谱补全专家。以下实体在整个知识图谱中仍然孤立（无任何关系连接）。

## 孤立实体（含类型和描述）
{orphan_entities}

## 知识图谱中的核心实体（高度数，可作为关系目标）
{hub_entities}

---

## 任务
根据儿童发展领域的知识，为每个孤立实体找到至少 1 个与核心实体的关系。

### 关系类型
- CAUSAL_CAUSES / CAUSAL_CONTRIBUTES_TO: 因果
- THERAPEUTIC_IMPROVES / THERAPEUTIC_ALLEVIATES: 干预
- FUNCTIONAL_INVOLVED_IN / FUNCTIONAL_REGULATES: 功能
- EVIDENCE_SUPPORTS / EVIDENCE_BASED_ON: 证据
- ATTRIBUTE_ASSOCIATED_WITH: 关联
- RELATES_TO: 兜底

### 规则
1. 只输出你有把握的关系（基于领域知识）
2. source 必须是孤立实体之一，target 必须是核心实体之一
3. 每个孤立实体至少输出 1 条关系

## 输出格式
```json
{{
  "relations": [
    {{"source": "孤立实体", "target": "核心实体", "relation_type": "RELATES_TO", "reason": "领域知识依据"}}
  ]
}}
```
"""


async def infer_relations_by_llm_global(
    master: MasterGraph,
    llm_client: LLMClient,
    model: str = "qwen3.5-27b",
    batch_size: int = 30,
    hub_count: int = 50,
) -> list[ExtractedRelationship]:
    """对经过 Step 1+2 仍然孤立的实体，用 LLM 做全局补全。

    标记 confidence=0.7, relation_source="llm_global_fix"。
    """
    from .models import RelationshipListResponse

    G = master.graph
    orphans = [n for n in G.nodes if G.degree(n) == 0]
    if not orphans:
        logger.info("LLM 全局补全: 无孤立实体，跳过")
        return []

    # 取高度数实体作为连接目标
    hub_nodes = sorted(G.nodes, key=lambda n: G.degree(n), reverse=True)[:hub_count]

    # 构建孤立实体描述
    def _format_orphan(name: str) -> str:
        data = G.nodes[name]
        etype = data.get("entity_type", "AutoEntity")
        desc = data.get("description", "")
        return f"- {name} ({etype}) — {desc}"

    def _format_hub(name: str) -> str:
        data = G.nodes[name]
        etype = data.get("entity_type", "AutoEntity")
        desc = data.get("description", "")[:80]
        return f"- {name} ({etype}, degree={G.degree(name)}) — {desc}"

    hub_str = "\n".join(_format_hub(n) for n in hub_nodes)

    added: list[ExtractedRelationship] = []

    # 分批处理
    for batch_start in range(0, len(orphans), batch_size):
        batch = orphans[batch_start:batch_start + batch_size]
        orphan_str = "\n".join(_format_orphan(n) for n in batch)

        try:
            from .models import JointExtractionResponse  # noqa: avoid circular

            result = await llm_client.generate_structured(
                prompt=GLOBAL_FIX_PROMPT.format(
                    orphan_entities=orphan_str,
                    hub_entities=hub_str,
                ),
                schema=RelationshipListResponse,
                model=model,
            )

            if isinstance(result, dict):
                rels = result.get("relations", result.get("items", []))
            elif isinstance(result, RelationshipListResponse):
                rels = result.items
            else:
                rels = []

            # 验证关系的有效性
            orphan_set = set(batch)
            hub_set = set(hub_nodes)
            for r in rels:
                src = r.source if hasattr(r, "source") else r.get("source", "")
                tgt = r.target if hasattr(r, "target") else r.get("target", "")
                if src in orphan_set and tgt in hub_set:
                    if hasattr(r, "relation_source"):
                        r.relation_source = "llm_global_fix"
                        r.confidence = 0.7
                    added.append(r)

        except Exception as e:
            logger.warning("LLM 全局补全批次失败: %s", e)
            continue

    logger.info("LLM 全局补全: 新增 %d 条关系", len(added))
    return added


# ──────────────────────────────────────────────────────────────
# 主入口
# ──────────────────────────────────────────────────────────────


async def run_global_relation_inference(
    master: MasterGraph,
    embedding_client: EmbeddingClient | None = None,
    llm_client: LLMClient | None = None,
    model: str = "qwen3.5-27b",
) -> dict:
    """Phase 2.5 主入口：运行全局关系补全。

    Args:
        master: 主图
        embedding_client: embedding 客户端（Step 0 和 Step 2 需要）
        llm_client: LLM 客户端（Step 3 需要）
        model: LLM 模型名称

    Returns:
        执行结果摘要
    """
    G = master.graph
    initial_orphans = sum(1 for n in G.nodes if G.degree(n) == 0)
    initial_edges = G.number_of_edges()

    logger.info(
        "Phase 2.5 开始: %d 实体, %d 关系, %d 孤立",
        G.number_of_nodes(), initial_edges, initial_orphans,
    )

    # Step 0: 关系类型语义合并
    relation_type_mapping: dict[str, str] = {}
    if embedding_client:
        relation_type_mapping = await merge_relation_types(master, embedding_client)

    # Step 1: 类型规则推断
    rule_rels = infer_relations_by_type_rules(master)
    for rel in rule_rels:
        master.add_relationship(rel, chapter_id="__heuristic__")

    # Step 2: Embedding 语义关联
    embed_rels = []
    if embedding_client:
        embed_rels = await infer_relations_by_embedding(master, embedding_client)
        for rel in embed_rels:
            master.add_relationship(rel, chapter_id="__embedding__")

    # Step 2.5: 跨分量桥接
    bridge_rels = []
    if embedding_client:
        bridge_rels = await bridge_components(master, embedding_client)
        for rel in bridge_rels:
            master.add_relationship(rel, chapter_id="__bridge__")

    # Step 3: LLM 全局补全
    llm_rels = []
    remaining_orphans = sum(1 for n in G.nodes if G.degree(n) == 0)
    if llm_client and remaining_orphans > 0:
        llm_rels = await infer_relations_by_llm_global(master, llm_client, model=model)
        for rel in llm_rels:
            master.add_relationship(rel, chapter_id="__llm_global__")

    final_orphans = sum(1 for n in G.nodes if G.degree(n) == 0)
    final_edges = G.number_of_edges()

    result = {
        "initial_orphans": initial_orphans,
        "final_orphans": final_orphans,
        "relation_types_merged": len([k for k, v in relation_type_mapping.items() if k != v]),
        "relation_type_mapping": relation_type_mapping,
        "relations_added": {
            "heuristic_rule": len(rule_rels),
            "embedding_sim": len(embed_rels),
            "component_bridge": len(bridge_rels),
            "llm_global_fix": len(llm_rels),
            "total": len(rule_rels) + len(embed_rels) + len(bridge_rels) + len(llm_rels),
        },
        "total_relations_before": initial_edges,
        "total_relations_after": final_edges,
    }

    logger.info(
        "Phase 2.5 完成: 孤立实体 %d → %d, 关系数 %d → %d "
        "(规则 +%d, Embedding +%d, 桥接 +%d, LLM +%d)",
        initial_orphans, final_orphans,
        initial_edges, final_edges,
        len(rule_rels), len(embed_rels), len(bridge_rels), len(llm_rels),
    )

    return result


# ──────────────────────────────────────────────────────────────
# Step 2.5: 跨分量桥接（连接孤立的连通分量）
# ──────────────────────────────────────────────────────────────

async def bridge_components(
    master: MasterGraph,
    embedding_client: EmbeddingClient,
    threshold: float = 0.60,
) -> list[ExtractedRelationship]:
    """跨分量桥接：用 embedding 相似度连接不同的连通分量。

    对每对连通分量，找到最相似的实体对，如果相似度 >= threshold，
    创建一条 RELATES_TO 桥接关系。

    Args:
        master: 主图
        embedding_client: embedding 客户端
        threshold: 桥接阈值（低于消歧阈值，因为是跨分量）

    Returns:
        新增的桥接关系列表
    """
    import networkx as nx

    G = master.graph
    if G.number_of_nodes() == 0:
        return []

    undirected = G.to_undirected()
    components = list(nx.connected_components(undirected))
    if len(components) <= 1:
        logger.info("跨分量桥接: 只有 %d 个分量，跳过", len(components))
        return []

    # 按分量大小排序，最大的作为"主分量"
    components.sort(key=len, reverse=True)
    main_component = components[0]
    small_components = components[1:]

    logger.info(
        "跨分量桥接: %d 个分量（主分量 %d 个实体, %d 个小分量）",
        len(components), len(main_component), len(small_components),
    )

    # 收集所有需要桥接的实体
    main_names = list(main_component)
    main_embs = await embedding_client.embed(main_names)

    added: list[ExtractedRelationship] = []

    for small_comp in small_components:
        small_names = list(small_comp)
        small_embs = await embedding_client.embed(small_names)

        # 找小分量中与主分量最相似的实体对
        best_sim = -1.0
        best_small = ""
        best_main = ""

        for i, s_name in enumerate(small_names):
            for j, m_name in enumerate(main_names):
                sim = _cosine(small_embs[i], main_embs[j])
                if sim > best_sim:
                    best_sim = sim
                    best_small = s_name
                    best_main = m_name

        if best_sim >= threshold:
            rel = ExtractedRelationship(
                source=best_small,
                target=best_main,
                relation_type=RelationType.RELATES_TO,
                evidence=f"跨分量桥接 (embedding sim={best_sim:.3f})",
                source_para_ids=[],
                relation_source="component_bridge",
                confidence=best_sim,
            )
            added.append(rel)
            logger.info(
                "  桥接: '%s' ↔ '%s' (sim=%.3f, 分量大小 %d)",
                best_small, best_main, best_sim, len(small_comp),
            )
        else:
            logger.info(
                "  跳过小分量 (%d 实体): 最佳相似度 %.3f < %.2f",
                len(small_comp), best_sim, threshold,
            )

    logger.info("跨分量桥接完成: %d 条桥接关系", len(added))
    return added
