"""Phase 2.5: 全局关系补全 + 关系类型语义合并。

在所有章节提取 + 审核合入后，质量审计前执行。
包含 7 个子步骤：
  Step 0: 关系类型语义合并（将 LLM 自由输出的关系类型归类到标准类型）
  Step 1: 基于类型规则的启发式推断（零 LLM 成本）
  Step 1.5: 段落共现关系推断（零 LLM 成本）
  Step 2: 基于 Embedding 的语义关联（低成本）
  Step 2.5: 跨分量桥接
  Step 3: LLM 全局孤立实体补全（兜底）
  Step 4: 星型兜底（embedding 最近邻）
  Step 5: 类型匹配兜底（零依赖，确保最终零孤立）

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

TYPE_RULES: list[tuple[str, str, str, str]] = [
    # ── 全覆盖矩阵（20 类型 × 19 目标 = 380 对）──
    # ── Problem → ... ──
    ("Problem", "Solution", "THERAPEUTIC_TREATS", "{t} 治疗 {s}"),
    ("Problem", "BrainRegion", "FUNCTIONAL_INVOLVED_IN", "{s} 涉及 {t}"),
    ("Problem", "Risk", "CAUSAL_CONTRIBUTES_TO", "{t} 促成 {s}"),
    ("Problem", "Exercise", "THERAPEUTIC_ALLEVIATES", "{t} 缓解 {s}"),
    ("Problem", "RootCause", "CAUSAL_CAUSES", "{t} 导致 {s}"),
    ("Problem", "Prescription", "THERAPEUTIC_TREATS", "{t} 治疗 {s}"),
    ("Problem", "ChildProfile", "CAUSAL_CONTRIBUTES_TO", "{s} 易出现于 {t}"),
    ("Problem", "CognitiveProcess", "FUNCTIONAL_INVOLVED_IN", "{s} 影响 {t}"),
    ("Problem", "Theory", "EVIDENCE_SUPPORTS", "{t} 支持对 {s} 的理解"),
    ("Problem", "Mechanism", "FUNCTIONAL_INVOLVED_IN", "{s} 涉及 {t}"),
    ("Problem", "DevelopmentalStage", "CAUSAL_CONTRIBUTES_TO", "{t} 阶段易出现 {s}"),
    ("Problem", "Strategy", "THERAPEUTIC_ALLEVIATES", "{t} 缓解 {s}"),
    ("Problem", "KeyInsight", "EVIDENCE_DEMONSTRATES", "{t} 揭示 {s}"),
    ("Problem", "ResearchFinding", "EVIDENCE_DEMONSTRATES", "{t} 证实 {s}"),
    ("Problem", "BookTitle", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 在 {t} 中被讨论"),
    ("Problem", "Concept", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 与 {t} 相关"),
    ("Problem", "Fact", "EVIDENCE_DEMONSTRATES", "{t} 证实 {s}"),
    ("Problem", "Quote", "EVIDENCE_DEMONSTRATES", "{t} 说明 {s}"),
    ("Problem", "DataPoint", "EVIDENCE_DEMONSTRATES", "{t} 数据支持 {s} 的存在"),
    # ── Solution → ... ──
    ("Solution", "Problem", "THERAPEUTIC_TREATS", "{s} 治疗 {t}"),
    ("Solution", "BrainRegion", "FUNCTIONAL_REGULATES", "{s} 调节 {t}"),
    ("Solution", "Risk", "THERAPEUTIC_ALLEVIATES", "{s} 降低 {t}"),
    ("Solution", "Exercise", "STRUCTURAL_CONTAINS", "{s} 包含 {t}"),
    ("Solution", "RootCause", "THERAPEUTIC_INHIBITS", "{s} 应对 {t}"),
    ("Solution", "Prescription", "STRUCTURAL_CONTAINS", "{s} 包含 {t}"),
    ("Solution", "ChildProfile", "THERAPEUTIC_TREATS", "{s} 适用于 {t}"),
    ("Solution", "CognitiveProcess", "THERAPEUTIC_IMPROVES", "{s} 改善 {t}"),
    ("Solution", "Theory", "EVIDENCE_BASED_ON", "{s} 基于 {t}"),
    ("Solution", "Mechanism", "FUNCTIONAL_INVOLVED_IN", "{s} 通过 {t} 起作用"),
    ("Solution", "DevelopmentalStage", "THERAPEUTIC_IMPROVES", "{s} 在 {t} 阶段有效"),
    ("Solution", "Strategy", "STRUCTURAL_BELONGS_TO", "{s} 属于 {t}"),
    ("Solution", "KeyInsight", "EVIDENCE_SUPPORTS", "{t} 支持 {s}"),
    ("Solution", "ResearchFinding", "EVIDENCE_BASED_ON", "{s} 基于 {t}"),
    ("Solution", "BookTitle", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 在 {t} 中被介绍"),
    ("Solution", "Concept", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 与 {t} 相关"),
    ("Solution", "Fact", "EVIDENCE_BASED_ON", "{s} 基于 {t}"),
    ("Solution", "Quote", "EVIDENCE_SUPPORTS", "{t} 支持 {s}"),
    ("Solution", "DataPoint", "EVIDENCE_BASED_ON", "{s} 基于 {t} 数据"),
    # ── BrainRegion → ... ──
    ("BrainRegion", "Problem", "FUNCTIONAL_INVOLVED_IN", "{s} 涉及 {t}"),
    ("BrainRegion", "Solution", "FUNCTIONAL_REGULATES", "{s} 调节 {t} 的效果"),
    ("BrainRegion", "Risk", "FUNCTIONAL_INVOLVED_IN", "{s} 涉及 {t}"),
    ("BrainRegion", "Exercise", "FUNCTIONAL_INVOLVED_IN", "{s} 参与 {t}"),
    ("BrainRegion", "RootCause", "FUNCTIONAL_INVOLVED_IN", "{s} 涉及 {t}"),
    ("BrainRegion", "Prescription", "FUNCTIONAL_REGULATES", "{s} 调节 {t} 的效果"),
    ("BrainRegion", "ChildProfile", "FUNCTIONAL_INVOLVED_IN", "{s} 与 {t} 相关"),
    ("BrainRegion", "CognitiveProcess", "FUNCTIONAL_REGULATES", "{s} 调节 {t}"),
    ("BrainRegion", "Theory", "EVIDENCE_SUPPORTS", "{s} 数据支持 {t}"),
    ("BrainRegion", "Mechanism", "FUNCTIONAL_MEDIATES", "{s} 通过 {t} 发挥作用"),
    ("BrainRegion", "DevelopmentalStage", "FUNCTIONAL_INVOLVED_IN", "{s} 在 {t} 发育"),
    ("BrainRegion", "Strategy", "FUNCTIONAL_REGULATES", "{s} 调节 {t} 的效果"),
    ("BrainRegion", "KeyInsight", "EVIDENCE_DEMONSTRATES", "{s} 揭示 {t}"),
    ("BrainRegion", "ResearchFinding", "EVIDENCE_DEMONSTRATES", "{s} 参与 {t} 的发现"),
    ("BrainRegion", "BookTitle", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 在 {t} 中被讨论"),
    ("BrainRegion", "Concept", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 与 {t} 相关"),
    ("BrainRegion", "Fact", "EVIDENCE_DEMONSTRATES", "{t} 证实 {s} 的功能"),
    ("BrainRegion", "Quote", "ATTRIBUTE_ASSOCIATED_WITH", "{t} 提到 {s}"),
    ("BrainRegion", "DataPoint", "ATTRIBUTE_MEASURED_BY", "{s} 通过 {t} 测量"),
    # ── Risk → ... ──
    ("Risk", "Problem", "CAUSAL_CONTRIBUTES_TO", "{s} 促成 {t}"),
    ("Risk", "Solution", "THERAPEUTIC_ALLEVIATES", "{t} 降低 {s}"),
    ("Risk", "BrainRegion", "FUNCTIONAL_INVOLVED_IN", "{s} 影响 {t}"),
    ("Risk", "Exercise", "THERAPEUTIC_ALLEVIATES", "{t} 降低 {s}"),
    ("Risk", "RootCause", "CAUSAL_CAUSES", "{t} 导致 {s}"),
    ("Risk", "Prescription", "THERAPEUTIC_ALLEVIATES", "{t} 降低 {s}"),
    ("Risk", "ChildProfile", "CAUSAL_CONTRIBUTES_TO", "{s} 增加 {t} 风险"),
    ("Risk", "CognitiveProcess", "THERAPEUTIC_INHIBITS", "{s} 损害 {t}"),
    ("Risk", "Theory", "EVIDENCE_SUPPORTS", "{t} 支持 {s} 的存在"),
    ("Risk", "Mechanism", "FUNCTIONAL_INVOLVED_IN", "{s} 通过 {t} 起作用"),
    ("Risk", "DevelopmentalStage", "CAUSAL_CONTRIBUTES_TO", "{s} 在 {t} 阶段增加"),
    ("Risk", "Strategy", "THERAPEUTIC_ALLEVIATES", "{t} 降低 {s}"),
    ("Risk", "KeyInsight", "EVIDENCE_DEMONSTRATES", "{t} 揭示 {s}"),
    ("Risk", "ResearchFinding", "EVIDENCE_DEMONSTRATES", "{t} 证实 {s}"),
    ("Risk", "BookTitle", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 在 {t} 中被讨论"),
    ("Risk", "Concept", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 与 {t} 相关"),
    ("Risk", "Fact", "EVIDENCE_DEMONSTRATES", "{t} 证实 {s}"),
    ("Risk", "Quote", "EVIDENCE_DEMONSTRATES", "{t} 说明 {s}"),
    ("Risk", "DataPoint", "EVIDENCE_DEMONSTRATES", "{t} 数据支持 {s}"),
    # ── Exercise → ... ──
    ("Exercise", "Problem", "THERAPEUTIC_ALLEVIATES", "{s} 缓解 {t}"),
    ("Exercise", "Solution", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 与 {t} 相关"),
    ("Exercise", "BrainRegion", "FUNCTIONAL_REGULATES", "{s} 调节 {t}"),
    ("Exercise", "Risk", "THERAPEUTIC_ALLEVIATES", "{s} 降低 {t}"),
    ("Exercise", "RootCause", "THERAPEUTIC_INHIBITS", "{s} 抑制 {t}"),
    ("Exercise", "Prescription", "STRUCTURAL_BELONGS_TO", "{s} 属于 {t}"),
    ("Exercise", "ChildProfile", "THERAPEUTIC_IMPROVES", "{s} 改善 {t} 的状况"),
    ("Exercise", "CognitiveProcess", "THERAPEUTIC_IMPROVES", "{s} 改善 {t}"),
    ("Exercise", "Theory", "EVIDENCE_BASED_ON", "{s} 基于 {t}"),
    ("Exercise", "Mechanism", "FUNCTIONAL_INVOLVED_IN", "{s} 涉及 {t}"),
    ("Exercise", "DevelopmentalStage", "THERAPEUTIC_IMPROVES", "{s} 在 {t} 阶段有益"),
    ("Exercise", "Strategy", "STRUCTURAL_CONTAINS", "{s} 是 {t} 的组成部分"),
    ("Exercise", "KeyInsight", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 与 {t} 相关"),
    ("Exercise", "ResearchFinding", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 与 {t} 相关"),
    ("Exercise", "BookTitle", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 与 {t} 相关"),
    ("Exercise", "Concept", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 与 {t} 相关"),
    ("Exercise", "Fact", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 与 {t} 相关"),
    ("Exercise", "Quote", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 与 {t} 相关"),
    ("Exercise", "DataPoint", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 与 {t} 相关"),
    # ── RootCause → ... ──
    ("RootCause", "Problem", "CAUSAL_CAUSES", "{s} 导致 {t}"),
    ("RootCause", "Solution", "THERAPEUTIC_INHIBITS", "{t} 应对 {s}"),
    ("RootCause", "BrainRegion", "FUNCTIONAL_INVOLVED_IN", "{s} 涉及 {t}"),
    ("RootCause", "Risk", "CAUSAL_CONTRIBUTES_TO", "{s} 促成 {t}"),
    ("RootCause", "Exercise", "THERAPEUTIC_INHIBITS", "{t} 抑制 {s}"),
    ("RootCause", "Prescription", "THERAPEUTIC_INHIBITS", "{t} 应对 {s}"),
    ("RootCause", "ChildProfile", "CAUSAL_CONTRIBUTES_TO", "{s} 增加 {t} 风险"),
    ("RootCause", "CognitiveProcess", "FUNCTIONAL_INVOLVED_IN", "{s} 影响 {t}"),
    ("RootCause", "Theory", "EVIDENCE_SUPPORTS", "{t} 支持 {s}"),
    ("RootCause", "Mechanism", "FUNCTIONAL_MEDIATES", "{s} 通过 {t} 起作用"),
    ("RootCause", "DevelopmentalStage", "CAUSAL_CONTRIBUTES_TO", "{s} 在 {t} 阶段出现"),
    ("RootCause", "Strategy", "THERAPEUTIC_INHIBITS", "{t} 应对 {s}"),
    ("RootCause", "KeyInsight", "EVIDENCE_DEMONSTRATES", "{s} 被 {t} 揭示"),
    ("RootCause", "ResearchFinding", "EVIDENCE_DEMONSTRATES", "{t} 证实 {s}"),
    ("RootCause", "BookTitle", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 在 {t} 中被讨论"),
    ("RootCause", "Concept", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 与 {t} 相关"),
    ("RootCause", "Fact", "EVIDENCE_DEMONSTRATES", "{t} 证实 {s}"),
    ("RootCause", "Quote", "EVIDENCE_DEMONSTRATES", "{t} 说明 {s}"),
    ("RootCause", "DataPoint", "EVIDENCE_DEMONSTRATES", "{t} 数据支持 {s}"),
    # ── Prescription → ... ──
    ("Prescription", "Problem", "THERAPEUTIC_TREATS", "{s} 治疗 {t}"),
    ("Prescription", "Solution", "STRUCTURAL_BELONGS_TO", "{s} 属于 {t}"),
    ("Prescription", "BrainRegion", "FUNCTIONAL_REGULATES", "{s} 调节 {t}"),
    ("Prescription", "Risk", "THERAPEUTIC_ALLEVIATES", "{s} 降低 {t}"),
    ("Prescription", "Exercise", "STRUCTURAL_CONTAINS", "{s} 包含 {t}"),
    ("Prescription", "RootCause", "THERAPEUTIC_INHIBITS", "{s} 应对 {t}"),
    ("Prescription", "ChildProfile", "THERAPEUTIC_TREATS", "{s} 用于 {t}"),
    ("Prescription", "CognitiveProcess", "THERAPEUTIC_IMPROVES", "{s} 改善 {t}"),
    ("Prescription", "Theory", "EVIDENCE_BASED_ON", "{s} 基于 {t}"),
    ("Prescription", "Mechanism", "FUNCTIONAL_INVOLVED_IN", "{s} 通过 {t} 起作用"),
    ("Prescription", "DevelopmentalStage", "THERAPEUTIC_IMPROVES", "{s} 在 {t} 阶段有效"),
    ("Prescription", "Strategy", "STRUCTURAL_CONTAINS", "{s} 包含 {t}"),
    ("Prescription", "KeyInsight", "EVIDENCE_SUPPORTS", "{t} 支持 {s}"),
    ("Prescription", "ResearchFinding", "EVIDENCE_BASED_ON", "{s} 基于 {t}"),
    ("Prescription", "BookTitle", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 在 {t} 中被介绍"),
    ("Prescription", "Concept", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 涉及 {t}"),
    ("Prescription", "Fact", "EVIDENCE_BASED_ON", "{s} 基于 {t}"),
    ("Prescription", "Quote", "EVIDENCE_SUPPORTS", "{t} 支持 {s}"),
    ("Prescription", "DataPoint", "EVIDENCE_BASED_ON", "{s} 基于 {t} 数据"),
    # ── ChildProfile → ... ──
    ("ChildProfile", "Problem", "CAUSAL_CONTRIBUTES_TO", "{s} 易出现 {t}"),
    ("ChildProfile", "Solution", "THERAPEUTIC_TREATS", "{t} 适用于 {s}"),
    ("ChildProfile", "BrainRegion", "FUNCTIONAL_INVOLVED_IN", "{s} 涉及 {t}"),
    ("ChildProfile", "Risk", "CAUSAL_CONTRIBUTES_TO", "{s} 面临 {t}"),
    ("ChildProfile", "Exercise", "THERAPEUTIC_IMPROVES", "{t} 改善 {s}"),
    ("ChildProfile", "RootCause", "CAUSAL_CONTRIBUTES_TO", "{s} 面临 {t}"),
    ("ChildProfile", "Prescription", "THERAPEUTIC_TREATS", "{t} 用于 {s}"),
    ("ChildProfile", "CognitiveProcess", "FUNCTIONAL_INVOLVED_IN", "{s} 涉及 {t}"),
    ("ChildProfile", "Theory", "EVIDENCE_SUPPORTS", "{t} 支持对 {s} 的理解"),
    ("ChildProfile", "Mechanism", "FUNCTIONAL_INVOLVED_IN", "{s} 涉及 {t}"),
    ("ChildProfile", "DevelopmentalStage", "TEMPORAL_DEVELOPS_INTO", "{s} 处于 {t}"),
    ("ChildProfile", "Strategy", "THERAPEUTIC_IMPROVES", "{t} 改善 {s}"),
    ("ChildProfile", "KeyInsight", "EVIDENCE_DEMONSTRATES", "{t} 揭示 {s}"),
    ("ChildProfile", "ResearchFinding", "EVIDENCE_DEMONSTRATES", "{t} 证实 {s}"),
    ("ChildProfile", "BookTitle", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 在 {t} 中被讨论"),
    ("ChildProfile", "Concept", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 与 {t} 相关"),
    ("ChildProfile", "Fact", "EVIDENCE_DEMONSTRATES", "{t} 证实 {s}"),
    ("ChildProfile", "Quote", "ATTRIBUTE_ASSOCIATED_WITH", "{t} 描述 {s}"),
    ("ChildProfile", "DataPoint", "ATTRIBUTE_MEASURED_BY", "{s} 通过 {t} 评估"),
    # ── CognitiveProcess → ... ──
    ("CognitiveProcess", "Problem", "FUNCTIONAL_INVOLVED_IN", "{s} 与 {t} 相关"),
    ("CognitiveProcess", "Solution", "THERAPEUTIC_IMPROVES", "{t} 改善 {s}"),
    ("CognitiveProcess", "BrainRegion", "FUNCTIONAL_INVOLVED_IN", "{s} 涉及 {t}"),
    ("CognitiveProcess", "Risk", "CAUSAL_CONTRIBUTES_TO", "{s} 受 {t} 影响"),
    ("CognitiveProcess", "Exercise", "THERAPEUTIC_IMPROVES", "{t} 改善 {s}"),
    ("CognitiveProcess", "RootCause", "FUNCTIONAL_INVOLVED_IN", "{s} 与 {t} 相关"),
    ("CognitiveProcess", "Prescription", "THERAPEUTIC_IMPROVES", "{t} 改善 {s}"),
    ("CognitiveProcess", "ChildProfile", "FUNCTIONAL_INVOLVED_IN", "{s} 与 {t} 相关"),
    ("CognitiveProcess", "Theory", "EVIDENCE_SUPPORTS", "{t} 支持对 {s} 的理解"),
    ("CognitiveProcess", "Mechanism", "FUNCTIONAL_INVOLVED_IN", "{s} 涉及 {t}"),
    ("CognitiveProcess", "DevelopmentalStage", "TEMPORAL_DEVELOPS_INTO", "{t} 阶段发展 {s}"),
    ("CognitiveProcess", "Strategy", "THERAPEUTIC_IMPROVES", "{t} 改善 {s}"),
    ("CognitiveProcess", "KeyInsight", "EVIDENCE_DEMONSTRATES", "{t} 揭示 {s}"),
    ("CognitiveProcess", "ResearchFinding", "EVIDENCE_DEMONSTRATES", "{t} 证实 {s}"),
    ("CognitiveProcess", "BookTitle", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 在 {t} 中被讨论"),
    ("CognitiveProcess", "Concept", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 与 {t} 相关"),
    ("CognitiveProcess", "Fact", "EVIDENCE_DEMONSTRATES", "{t} 证实 {s}"),
    ("CognitiveProcess", "Quote", "ATTRIBUTE_ASSOCIATED_WITH", "{t} 提到 {s}"),
    ("CognitiveProcess", "DataPoint", "ATTRIBUTE_MEASURED_BY", "{s} 通过 {t} 测量"),
    # ── Theory → ... ──
    ("Theory", "Problem", "EVIDENCE_SUPPORTS", "{s} 支持对 {t} 的理解"),
    ("Theory", "Solution", "EVIDENCE_SUPPORTS", "{s} 支持 {t}"),
    ("Theory", "BrainRegion", "EVIDENCE_SUPPORTS", "{s} 支持对 {t} 的理解"),
    ("Theory", "Risk", "EVIDENCE_SUPPORTS", "{s} 支持 {t} 的存在"),
    ("Theory", "Exercise", "EVIDENCE_SUPPORTS", "{s} 支持 {t}"),
    ("Theory", "RootCause", "EVIDENCE_SUPPORTS", "{s} 支持对 {t} 的理解"),
    ("Theory", "Prescription", "EVIDENCE_SUPPORTS", "{s} 支持 {t}"),
    ("Theory", "ChildProfile", "EVIDENCE_SUPPORTS", "{s} 支持对 {t} 的理解"),
    ("Theory", "CognitiveProcess", "EVIDENCE_SUPPORTS", "{s} 支持 {t} 的理解"),
    ("Theory", "Mechanism", "EVIDENCE_SUPPORTS", "{s} 支持 {t}"),
    ("Theory", "DevelopmentalStage", "EVIDENCE_SUPPORTS", "{s} 支持 {t} 的发展观"),
    ("Theory", "Strategy", "EVIDENCE_SUPPORTS", "{s} 支持 {t}"),
    ("Theory", "KeyInsight", "EVIDENCE_BASED_ON", "{s} 基于 {t}"),
    ("Theory", "ResearchFinding", "EVIDENCE_BASED_ON", "{s} 基于 {t}"),
    ("Theory", "BookTitle", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 在 {t} 中被阐述"),
    ("Theory", "Concept", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 涵盖 {t}"),
    ("Theory", "Fact", "EVIDENCE_DEMONSTRATES", "{s} 演绎出 {t}"),
    ("Theory", "Quote", "ATTRIBUTE_ASSOCIATED_WITH", "{t} 阐述 {s}"),
    ("Theory", "DataPoint", "EVIDENCE_DEMONSTRATES", "{s} 通过 {t} 验证"),
    # ── Mechanism → ... ──
    ("Mechanism", "Problem", "CAUSAL_CAUSES", "{s} 导致 {t}"),
    ("Mechanism", "Solution", "FUNCTIONAL_INVOLVED_IN", "{s} 参与 {t}"),
    ("Mechanism", "BrainRegion", "FUNCTIONAL_REGULATES", "{s} 调节 {t}"),
    ("Mechanism", "Risk", "CAUSAL_CONTRIBUTES_TO", "{s} 促成 {t}"),
    ("Mechanism", "Exercise", "FUNCTIONAL_INVOLVED_IN", "{s} 参与 {t}"),
    ("Mechanism", "RootCause", "CAUSAL_CAUSES", "{s} 导致 {t}"),
    ("Mechanism", "Prescription", "FUNCTIONAL_INVOLVED_IN", "{s} 参与 {t}"),
    ("Mechanism", "ChildProfile", "FUNCTIONAL_INVOLVED_IN", "{s} 影响 {t}"),
    ("Mechanism", "CognitiveProcess", "FUNCTIONAL_MEDIATES", "{s} 介导 {t}"),
    ("Mechanism", "Theory", "EVIDENCE_SUPPORTS", "{t} 支持 {s}"),
    ("Mechanism", "DevelopmentalStage", "FUNCTIONAL_INVOLVED_IN", "{s} 在 {t} 阶段起作用"),
    ("Mechanism", "Strategy", "FUNCTIONAL_INVOLVED_IN", "{s} 通过 {t} 起作用"),
    ("Mechanism", "KeyInsight", "EVIDENCE_DEMONSTRATES", "{t} 揭示 {s}"),
    ("Mechanism", "ResearchFinding", "EVIDENCE_DEMONSTRATES", "{t} 证实 {s}"),
    ("Mechanism", "BookTitle", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 在 {t} 中被讨论"),
    ("Mechanism", "Concept", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 通过 {t} 体现"),
    ("Mechanism", "Fact", "EVIDENCE_DEMONSTRATES", "{t} 证实 {s}"),
    ("Mechanism", "Quote", "ATTRIBUTE_ASSOCIATED_WITH", "{t} 提到 {s}"),
    ("Mechanism", "DataPoint", "ATTRIBUTE_MEASURED_BY", "{s} 通过 {t} 测量"),
    # ── DevelopmentalStage → ... ──
    ("DevelopmentalStage", "Problem", "CAUSAL_CONTRIBUTES_TO", "{s} 阶段易出现 {t}"),
    ("DevelopmentalStage", "Solution", "THERAPEUTIC_IMPROVES", "{s} 阶段 {t} 有效"),
    ("DevelopmentalStage", "BrainRegion", "FUNCTIONAL_INVOLVED_IN", "{s} 阶段涉及 {t}"),
    ("DevelopmentalStage", "Risk", "CAUSAL_CONTRIBUTES_TO", "{s} 阶段增加 {t}"),
    ("DevelopmentalStage", "Exercise", "THERAPEUTIC_IMPROVES", "{s} 阶段 {t} 有益"),
    ("DevelopmentalStage", "RootCause", "CAUSAL_CONTRIBUTES_TO", "{s} 阶段 {t} 出现"),
    ("DevelopmentalStage", "Prescription", "THERAPEUTIC_IMPROVES", "{s} 阶段 {t} 有效"),
    ("DevelopmentalStage", "ChildProfile", "TEMPORAL_DEVELOPS_INTO", "{s} 阶段发展 {t}"),
    ("DevelopmentalStage", "CognitiveProcess", "TEMPORAL_DEVELOPS_INTO", "{s} 阶段发展 {t}"),
    ("DevelopmentalStage", "Theory", "EVIDENCE_SUPPORTS", "{t} 支持 {s} 的发展观"),
    ("DevelopmentalStage", "Mechanism", "FUNCTIONAL_INVOLVED_IN", "{s} 阶段涉及 {t}"),
    ("DevelopmentalStage", "Strategy", "THERAPEUTIC_IMPROVES", "{s} 阶段 {t} 有效"),
    ("DevelopmentalStage", "KeyInsight", "EVIDENCE_DEMONSTRATES", "{t} 揭示 {s}"),
    ("DevelopmentalStage", "ResearchFinding", "EVIDENCE_DEMONSTRATES", "{t} 证实 {s}"),
    ("DevelopmentalStage", "BookTitle", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 在 {t} 中被讨论"),
    ("DevelopmentalStage", "Concept", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 与 {t} 相关"),
    ("DevelopmentalStage", "Fact", "EVIDENCE_DEMONSTRATES", "{t} 证实 {s}"),
    ("DevelopmentalStage", "Quote", "ATTRIBUTE_ASSOCIATED_WITH", "{t} 提到 {s}"),
    ("DevelopmentalStage", "DataPoint", "ATTRIBUTE_MEASURED_BY", "{s} 通过 {t} 评估"),
    # ── Strategy → ... ──
    ("Strategy", "Problem", "THERAPEUTIC_ALLEVIATES", "{s} 缓解 {t}"),
    ("Strategy", "Solution", "STRUCTURAL_BELONGS_TO", "{s} 属于 {t}"),
    ("Strategy", "BrainRegion", "FUNCTIONAL_REGULATES", "{s} 调节 {t}"),
    ("Strategy", "Risk", "THERAPEUTIC_ALLEVIATES", "{s} 降低 {t}"),
    ("Strategy", "Exercise", "STRUCTURAL_CONTAINS", "{s} 包含 {t}"),
    ("Strategy", "RootCause", "THERAPEUTIC_INHIBITS", "{s} 应对 {t}"),
    ("Strategy", "Prescription", "STRUCTURAL_CONTAINS", "{s} 包含 {t}"),
    ("Strategy", "ChildProfile", "THERAPEUTIC_IMPROVES", "{s} 改善 {t}"),
    ("Strategy", "CognitiveProcess", "THERAPEUTIC_IMPROVES", "{s} 改善 {t}"),
    ("Strategy", "Theory", "EVIDENCE_BASED_ON", "{s} 基于 {t}"),
    ("Strategy", "Mechanism", "FUNCTIONAL_INVOLVED_IN", "{s} 通过 {t} 起作用"),
    ("Strategy", "DevelopmentalStage", "THERAPEUTIC_ALLEVIATES", "{s} 在 {t} 阶段有效"),
    ("Strategy", "KeyInsight", "EVIDENCE_SUPPORTS", "{t} 支持 {s}"),
    ("Strategy", "ResearchFinding", "EVIDENCE_BASED_ON", "{s} 基于 {t}"),
    ("Strategy", "BookTitle", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 在 {t} 中被介绍"),
    ("Strategy", "Concept", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 涉及 {t}"),
    ("Strategy", "Fact", "EVIDENCE_BASED_ON", "{s} 基于 {t}"),
    ("Strategy", "Quote", "EVIDENCE_SUPPORTS", "{t} 支持 {s}"),
    ("Strategy", "DataPoint", "EVIDENCE_BASED_ON", "{s} 基于 {t} 数据"),
    # ── KeyInsight → ... ──
    ("KeyInsight", "Problem", "EVIDENCE_DEMONSTRATES", "{s} 揭示 {t}"),
    ("KeyInsight", "Solution", "EVIDENCE_SUPPORTS", "{s} 支持 {t}"),
    ("KeyInsight", "BrainRegion", "EVIDENCE_DEMONSTRATES", "{s} 揭示 {t}"),
    ("KeyInsight", "Risk", "EVIDENCE_DEMONSTRATES", "{s} 揭示 {t}"),
    ("KeyInsight", "Exercise", "EVIDENCE_SUPPORTS", "{s} 支持 {t}"),
    ("KeyInsight", "RootCause", "EVIDENCE_DEMONSTRATES", "{s} 揭示 {t}"),
    ("KeyInsight", "Prescription", "EVIDENCE_SUPPORTS", "{s} 支持 {t}"),
    ("KeyInsight", "ChildProfile", "EVIDENCE_DEMONSTRATES", "{s} 揭示 {t} 的特征"),
    ("KeyInsight", "CognitiveProcess", "EVIDENCE_SUPPORTS", "{s} 支持 {t}"),
    ("KeyInsight", "Theory", "EVIDENCE_BASED_ON", "{s} 基于 {t}"),
    ("KeyInsight", "Mechanism", "EVIDENCE_DEMONSTRATES", "{s} 揭示 {t}"),
    ("KeyInsight", "DevelopmentalStage", "EVIDENCE_DEMONSTRATES", "{s} 揭示 {t} 的发展"),
    ("KeyInsight", "Strategy", "EVIDENCE_SUPPORTS", "{s} 支持 {t}"),
    ("KeyInsight", "ResearchFinding", "EVIDENCE_BASED_ON", "{s} 基于 {t}"),
    ("KeyInsight", "BookTitle", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 来自 {t}"),
    ("KeyInsight", "Concept", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 涉及 {t}"),
    ("KeyInsight", "Fact", "EVIDENCE_DEMONSTRATES", "{s} 揭示 {t}"),
    ("KeyInsight", "Quote", "ATTRIBUTE_ASSOCIATED_WITH", "{t} 阐述 {s}"),
    ("KeyInsight", "DataPoint", "EVIDENCE_DEMONSTRATES", "{s} 通过 {t} 揭示"),
    # ── ResearchFinding → ... ──
    ("ResearchFinding", "Problem", "EVIDENCE_DEMONSTRATES", "{s} 证实 {t}"),
    ("ResearchFinding", "Solution", "EVIDENCE_SUPPORTS", "{s} 支持 {t}"),
    ("ResearchFinding", "BrainRegion", "EVIDENCE_DEMONSTRATES", "{s} 证实 {t} 的功能"),
    ("ResearchFinding", "Risk", "EVIDENCE_DEMONSTRATES", "{s} 证实 {t}"),
    ("ResearchFinding", "Exercise", "EVIDENCE_DEMONSTRATES", "{s} 证实 {t} 的效果"),
    ("ResearchFinding", "RootCause", "EVIDENCE_DEMONSTRATES", "{s} 证实 {t}"),
    ("ResearchFinding", "Prescription", "EVIDENCE_SUPPORTS", "{s} 支持 {t}"),
    ("ResearchFinding", "ChildProfile", "EVIDENCE_DEMONSTRATES", "{s} 证实 {t} 的特征"),
    ("ResearchFinding", "CognitiveProcess", "EVIDENCE_DEMONSTRATES", "{s} 证实 {t}"),
    ("ResearchFinding", "Theory", "EVIDENCE_BASED_ON", "{t} 基于 {s}"),
    ("ResearchFinding", "Mechanism", "EVIDENCE_SUPPORTS", "{s} 支持 {t}"),
    ("ResearchFinding", "DevelopmentalStage", "EVIDENCE_DEMONSTRATES", "{s} 证实 {t} 的发展特征"),
    ("ResearchFinding", "Strategy", "EVIDENCE_SUPPORTS", "{s} 支持 {t}"),
    ("ResearchFinding", "KeyInsight", "EVIDENCE_BASED_ON", "{t} 基于 {s}"),
    ("ResearchFinding", "BookTitle", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 来自 {t}"),
    ("ResearchFinding", "Concept", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 涉及 {t}"),
    ("ResearchFinding", "Fact", "EVIDENCE_BASED_ON", "{s} 包含 {t}"),
    ("ResearchFinding", "Quote", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 引用 {t}"),
    ("ResearchFinding", "DataPoint", "EVIDENCE_BASED_ON", "{s} 包含 {t}"),
    # ── BookTitle → ... ──
    ("BookTitle", "Problem", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 讨论 {t}"),
    ("BookTitle", "Solution", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 介绍 {t}"),
    ("BookTitle", "BrainRegion", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 讨论 {t}"),
    ("BookTitle", "Risk", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 讨论 {t}"),
    ("BookTitle", "Exercise", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 介绍 {t}"),
    ("BookTitle", "RootCause", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 讨论 {t}"),
    ("BookTitle", "Prescription", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 介绍 {t}"),
    ("BookTitle", "ChildProfile", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 讨论 {t}"),
    ("BookTitle", "CognitiveProcess", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 讨论 {t}"),
    ("BookTitle", "Theory", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 阐述 {t}"),
    ("BookTitle", "Mechanism", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 讨论 {t}"),
    ("BookTitle", "DevelopmentalStage", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 讨论 {t}"),
    ("BookTitle", "Strategy", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 介绍 {t}"),
    ("BookTitle", "KeyInsight", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 包含 {t}"),
    ("BookTitle", "ResearchFinding", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 包含 {t}"),
    ("BookTitle", "Concept", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 涵盖 {t}"),
    ("BookTitle", "Fact", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 包含 {t}"),
    ("BookTitle", "Quote", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 包含 {t}"),
    ("BookTitle", "DataPoint", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 包含 {t}"),
    # ── Concept → ... ──
    ("Concept", "Problem", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 与 {t} 相关"),
    ("Concept", "Solution", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 与 {t} 相关"),
    ("Concept", "BrainRegion", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 涉及 {t}"),
    ("Concept", "Risk", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 与 {t} 相关"),
    ("Concept", "Exercise", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 与 {t} 相关"),
    ("Concept", "RootCause", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 与 {t} 相关"),
    ("Concept", "Prescription", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 与 {t} 相关"),
    ("Concept", "ChildProfile", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 与 {t} 相关"),
    ("Concept", "CognitiveProcess", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 与 {t} 相关"),
    ("Concept", "Theory", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 与 {t} 相关"),
    ("Concept", "Mechanism", "FUNCTIONAL_MEDIATES", "{s} 通过 {t} 体现"),
    ("Concept", "DevelopmentalStage", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 与 {t} 相关"),
    ("Concept", "Strategy", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 与 {t} 相关"),
    ("Concept", "KeyInsight", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 与 {t} 相关"),
    ("Concept", "ResearchFinding", "EVIDENCE_BASED_ON", "{s} 基于 {t}"),
    ("Concept", "BookTitle", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 在 {t} 中被讨论"),
    ("Concept", "Fact", "EVIDENCE_BASED_ON", "{s} 基于 {t}"),
    ("Concept", "Quote", "ATTRIBUTE_ASSOCIATED_WITH", "{t} 阐述 {s}"),
    ("Concept", "DataPoint", "EVIDENCE_BASED_ON", "{s} 基于 {t} 数据"),
    # ── Fact → ... ──
    ("Fact", "Problem", "EVIDENCE_DEMONSTRATES", "{s} 证实 {t}"),
    ("Fact", "Solution", "EVIDENCE_SUPPORTS", "{s} 支持 {t}"),
    ("Fact", "BrainRegion", "EVIDENCE_DEMONSTRATES", "{s} 证实 {t} 的功能"),
    ("Fact", "Risk", "EVIDENCE_DEMONSTRATES", "{s} 证实 {t}"),
    ("Fact", "Exercise", "EVIDENCE_DEMONSTRATES", "{s} 证实 {t} 的效果"),
    ("Fact", "RootCause", "EVIDENCE_DEMONSTRATES", "{s} 证实 {t}"),
    ("Fact", "Prescription", "EVIDENCE_SUPPORTS", "{s} 支持 {t}"),
    ("Fact", "ChildProfile", "EVIDENCE_DEMONSTRATES", "{s} 证实 {t}"),
    ("Fact", "CognitiveProcess", "EVIDENCE_SUPPORTS", "{s} 支持 {t}"),
    ("Fact", "Theory", "EVIDENCE_DEMONSTRATES", "{s} 证实 {t}"),
    ("Fact", "Mechanism", "EVIDENCE_SUPPORTS", "{s} 支持 {t}"),
    ("Fact", "DevelopmentalStage", "EVIDENCE_DEMONSTRATES", "{s} 证实 {t}"),
    ("Fact", "Strategy", "EVIDENCE_SUPPORTS", "{s} 支持 {t}"),
    ("Fact", "KeyInsight", "EVIDENCE_DEMONSTRATES", "{s} 证实 {t}"),
    ("Fact", "ResearchFinding", "EVIDENCE_BASED_ON", "{s} 基于 {t}"),
    ("Fact", "BookTitle", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 来自 {t}"),
    ("Fact", "Concept", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 与 {t} 相关"),
    ("Fact", "Quote", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 与 {t} 相关"),
    ("Fact", "DataPoint", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 与 {t} 相关"),
    # ── Quote → ... ──
    ("Quote", "Problem", "EVIDENCE_DEMONSTRATES", "{s} 说明 {t}"),
    ("Quote", "Solution", "EVIDENCE_SUPPORTS", "{s} 支持 {t}"),
    ("Quote", "BrainRegion", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 提到 {t}"),
    ("Quote", "Risk", "EVIDENCE_DEMONSTRATES", "{s} 说明 {t}"),
    ("Quote", "Exercise", "EVIDENCE_SUPPORTS", "{s} 支持 {t}"),
    ("Quote", "RootCause", "EVIDENCE_DEMONSTRATES", "{s} 说明 {t}"),
    ("Quote", "Prescription", "EVIDENCE_SUPPORTS", "{s} 支持 {t}"),
    ("Quote", "ChildProfile", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 描述 {t}"),
    ("Quote", "CognitiveProcess", "EVIDENCE_SUPPORTS", "{s} 支持 {t}"),
    ("Quote", "Theory", "EVIDENCE_BASED_ON", "{s} 阐述 {t}"),
    ("Quote", "Mechanism", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 提到 {t}"),
    ("Quote", "DevelopmentalStage", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 提到 {t}"),
    ("Quote", "Strategy", "EVIDENCE_SUPPORTS", "{s} 支持 {t}"),
    ("Quote", "KeyInsight", "EVIDENCE_SUPPORTS", "{s} 阐述 {t}"),
    ("Quote", "ResearchFinding", "EVIDENCE_DEMONSTRATES", "{s} 支持 {t}"),
    ("Quote", "BookTitle", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 来自 {t}"),
    ("Quote", "Concept", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 阐述 {t}"),
    ("Quote", "Fact", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 与 {t} 相关"),
    ("Quote", "DataPoint", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 与 {t} 相关"),
    # ── DataPoint → ... ──
    ("DataPoint", "Problem", "EVIDENCE_DEMONSTRATES", "{s} 数据支持 {t}"),
    ("DataPoint", "Solution", "EVIDENCE_SUPPORTS", "{s} 数据支持 {t}"),
    ("DataPoint", "BrainRegion", "EVIDENCE_DEMONSTRATES", "{s} 数据支持 {t}"),
    ("DataPoint", "Risk", "EVIDENCE_DEMONSTRATES", "{s} 数据证实 {t}"),
    ("DataPoint", "Exercise", "EVIDENCE_DEMONSTRATES", "{s} 数据证实 {t}"),
    ("DataPoint", "RootCause", "EVIDENCE_DEMONSTRATES", "{s} 数据支持 {t}"),
    ("DataPoint", "Prescription", "EVIDENCE_SUPPORTS", "{s} 数据支持 {t}"),
    ("DataPoint", "ChildProfile", "EVIDENCE_DEMONSTRATES", "{s} 数据反映 {t}"),
    ("DataPoint", "CognitiveProcess", "EVIDENCE_SUPPORTS", "{s} 数据支持 {t}"),
    ("DataPoint", "Theory", "EVIDENCE_DEMONSTRATES", "{s} 数据支持 {t}"),
    ("DataPoint", "Mechanism", "EVIDENCE_SUPPORTS", "{s} 数据支持 {t}"),
    ("DataPoint", "DevelopmentalStage", "EVIDENCE_DEMONSTRATES", "{s} 数据支持 {t}"),
    ("DataPoint", "Strategy", "EVIDENCE_SUPPORTS", "{s} 数据支持 {t}"),
    ("DataPoint", "KeyInsight", "EVIDENCE_DEMONSTRATES", "{s} 数据揭示 {t}"),
    ("DataPoint", "ResearchFinding", "EVIDENCE_BASED_ON", "{s} 数据基于 {t}"),
    ("DataPoint", "BookTitle", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 数据来自 {t}"),
    ("DataPoint", "Concept", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 数据涉及 {t}"),
    ("DataPoint", "Fact", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 与 {t} 相关"),
    ("DataPoint", "Quote", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 与 {t} 相关"),
    # ── Person → ... (v2 扩展: 人名实体) ──
    ("Person", "Problem", "EVIDENCE_DEMONSTRATES", "{s} 的研究揭示了 {t}"),
    ("Person", "Solution", "EVIDENCE_SUPPORTS", "{s} 提出了 {t}"),
    ("Person", "BrainRegion", "EVIDENCE_DEMONSTRATES", "{s} 研究了 {t}"),
    ("Person", "Risk", "EVIDENCE_DEMONSTRATES", "{s} 研究了 {t}"),
    ("Person", "Exercise", "EVIDENCE_SUPPORTS", "{s} 研究了 {t} 的效果"),
    ("Person", "RootCause", "EVIDENCE_DEMONSTRATES", "{s} 的研究涉及 {t}"),
    ("Person", "Prescription", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 与 {t} 相关"),
    ("Person", "ChildProfile", "EVIDENCE_DEMONSTRATES", "{s} 研究了 {t}"),
    ("Person", "CognitiveProcess", "EVIDENCE_DEMONSTRATES", "{s} 研究了 {t}"),
    ("Person", "Theory", "EVIDENCE_SUPPORTS", "{s} 提出/支持 {t}"),
    ("Person", "Mechanism", "EVIDENCE_DEMONSTRATES", "{s} 研究了 {t}"),
    ("Person", "DevelopmentalStage", "EVIDENCE_DEMONSTRATES", "{s} 研究了 {t}"),
    ("Person", "Strategy", "EVIDENCE_SUPPORTS", "{s} 提出/支持 {t}"),
    ("Person", "KeyInsight", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 提出了 {t}"),
    ("Person", "ResearchFinding", "EVIDENCE_DEMONSTRATES", "{s} 发现了 {t}"),
    ("Person", "BookTitle", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 是 {t} 的作者/贡献者"),
    ("Person", "Concept", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 与 {t} 相关"),
    ("Person", "Fact", "EVIDENCE_DEMONSTRATES", "{s} 的研究揭示了 {t}"),
    ("Person", "Quote", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 说了 {t}"),
    ("Person", "DataPoint", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 的研究产生了 {t}"),
    ("Person", "Location", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 在 {t} 工作/研究"),
    ("Person", "Object", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 使用/开发了 {t}"),
    # ── … → Person ──
    ("Problem", "Person", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 被 {t} 研究"),
    ("Solution", "Person", "EVIDENCE_BASED_ON", "{s} 基于 {t} 的研究"),
    ("BrainRegion", "Person", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 被 {t} 研究"),
    ("Risk", "Person", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 被 {t} 研究"),
    ("Exercise", "Person", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 被 {t} 研究"),
    ("RootCause", "Person", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 被 {t} 研究"),
    ("Prescription", "Person", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 与 {t} 相关"),
    ("ChildProfile", "Person", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 被 {t} 研究"),
    ("CognitiveProcess", "Person", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 被 {t} 研究"),
    ("Theory", "Person", "EVIDENCE_BASED_ON", "{s} 基于 {t} 的研究"),
    ("Mechanism", "Person", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 被 {t} 研究"),
    ("DevelopmentalStage", "Person", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 被 {t} 研究"),
    ("Strategy", "Person", "EVIDENCE_BASED_ON", "{s} 基于 {t} 的研究"),
    ("KeyInsight", "Person", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 由 {t} 提出"),
    ("ResearchFinding", "Person", "EVIDENCE_BASED_ON", "{s} 基于 {t} 的研究"),
    ("BookTitle", "Person", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 的作者包括 {t}"),
    ("Concept", "Person", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 由 {t} 提出"),
    ("Fact", "Person", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 被 {t} 发现"),
    ("Quote", "Person", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 是 {t} 说的"),
    ("DataPoint", "Person", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 来自 {t} 的研究"),
    ("Location", "Person", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 是 {t} 的工作/研究地点"),
    ("Object", "Person", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 由 {t} 开发/使用"),
    # ── Location → ... (v2 扩展: 地名实体) ──
    ("Location", "Problem", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 的研究涉及 {t}"),
    ("Location", "Solution", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 的研究涉及 {t}"),
    ("Location", "BrainRegion", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 与 {t} 研究相关"),
    ("Location", "Risk", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 的研究涉及 {t}"),
    ("Location", "Exercise", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 是 {t} 的实施/研究地点"),
    ("Location", "Prescription", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 是 {t} 的实施地点"),
    ("Location", "ChildProfile", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 的研究涉及 {t}"),
    ("Location", "CognitiveProcess", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 的研究涉及 {t}"),
    ("Location", "Theory", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 是 {t} 的研究/发源地"),
    ("Location", "Mechanism", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 的研究涉及 {t}"),
    ("Location", "DevelopmentalStage", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 的研究涉及 {t}"),
    ("Location", "Strategy", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 是 {t} 的实施/研究地点"),
    ("Location", "KeyInsight", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 的研究产生了 {t}"),
    ("Location", "ResearchFinding", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 是 {t} 的研究地点"),
    ("Location", "BookTitle", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 在 {t} 中被提及"),
    ("Location", "Concept", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 与 {t} 相关"),
    ("Location", "Fact", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 与 {t} 相关"),
    ("Location", "Quote", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 在 {t} 中被提及"),
    ("Location", "DataPoint", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 是 {t} 的数据来源地"),
    ("Location", "Object", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 是 {t} 的使用/研究地点"),
    # ── … → Location ──
    ("Problem", "Location", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 的研究在 {t} 进行"),
    ("Solution", "Location", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 在 {t} 实施/研究"),
    ("BrainRegion", "Location", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 的研究在 {t} 进行"),
    ("Risk", "Location", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 的研究在 {t} 进行"),
    ("Exercise", "Location", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 在 {t} 实施/研究"),
    ("Prescription", "Location", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 在 {t} 实施"),
    ("ChildProfile", "Location", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 的研究在 {t} 进行"),
    ("CognitiveProcess", "Location", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 的研究在 {t} 进行"),
    ("Theory", "Location", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 起源于 {t}"),
    ("Mechanism", "Location", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 的研究在 {t} 进行"),
    ("DevelopmentalStage", "Location", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 的研究在 {t} 进行"),
    ("Strategy", "Location", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 在 {t} 实施/研究"),
    ("KeyInsight", "Location", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 来自 {t} 的研究"),
    ("ResearchFinding", "Location", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 来自 {t} 的研究"),
    ("BookTitle", "Location", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 提到 {t}"),
    ("Concept", "Location", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 与 {t} 相关"),
    ("Fact", "Location", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 与 {t} 相关"),
    ("Quote", "Location", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 在 {t} 被记录"),
    ("DataPoint", "Location", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 的数据来自 {t}"),
    ("Object", "Location", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 在 {t} 使用/研究"),
    # ── Object → ... (v2 扩展: 物品/工具实体) ──
    ("Object", "Problem", "THERAPEUTIC_ALLEVIATES", "{s} 用于缓解 {t}"),
    ("Object", "Solution", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 是 {t} 的组成部分"),
    ("Object", "BrainRegion", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 用于评估/调节 {t}"),
    ("Object", "Risk", "THERAPEUTIC_ALLEVIATES", "{s} 用于降低 {t}"),
    ("Object", "Exercise", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 用于 {t}"),
    ("Object", "RootCause", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 用于应对 {t}"),
    ("Object", "Prescription", "STRUCTURAL_CONTAINS", "{s} 是 {t} 中使用的工具"),
    ("Object", "ChildProfile", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 用于评估/干预 {t}"),
    ("Object", "CognitiveProcess", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 用于评估/训练 {t}"),
    ("Object", "Theory", "EVIDENCE_BASED_ON", "{s} 基于 {t} 设计"),
    ("Object", "Mechanism", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 通过 {t} 起作用"),
    ("Object", "DevelopmentalStage", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 适用于 {t} 阶段"),
    ("Object", "Strategy", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 是 {t} 中使用的工具"),
    ("Object", "KeyInsight", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 与 {t} 相关"),
    ("Object", "ResearchFinding", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 与 {t} 相关"),
    ("Object", "BookTitle", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 在 {t} 中被提及"),
    ("Object", "Concept", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 与 {t} 相关"),
    ("Object", "Fact", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 与 {t} 相关"),
    ("Object", "Quote", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 在 {t} 中被提及"),
    ("Object", "DataPoint", "ATTRIBUTE_MEASURED_BY", "{t} 通过 {s} 测量"),
    # ── … → Object ──
    ("Problem", "Object", "THERAPEUTIC_ALLEVIATES", "{t} 缓解 {s}"),
    ("Solution", "Object", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 包含 {t}"),
    ("BrainRegion", "Object", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 通过 {t} 评估/调节"),
    ("Risk", "Object", "THERAPEUTIC_ALLEVIATES", "{t} 降低 {s}"),
    ("Exercise", "Object", "STRUCTURAL_CONTAINS", "{s} 使用 {t}"),
    ("RootCause", "Object", "ATTRIBUTE_ASSOCIATED_WITH", "{t} 应对 {s}"),
    ("Prescription", "Object", "STRUCTURAL_CONTAINS", "{s} 包含 {t}"),
    ("ChildProfile", "Object", "ATTRIBUTE_ASSOCIATED_WITH", "{t} 评估/干预 {s}"),
    ("CognitiveProcess", "Object", "ATTRIBUTE_ASSOCIATED_WITH", "{t} 评估/训练 {s}"),
    ("Theory", "Object", "EVIDENCE_SUPPORTS", "{s} 支持 {t} 的设计"),
    ("Mechanism", "Object", "ATTRIBUTE_ASSOCIATED_WITH", "{t} 通过 {s} 起作用"),
    ("DevelopmentalStage", "Object", "ATTRIBUTE_ASSOCIATED_WITH", "{t} 适用于 {s} 阶段"),
    ("Strategy", "Object", "STRUCTURAL_CONTAINS", "{s} 使用 {t}"),
    ("KeyInsight", "Object", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 与 {t} 相关"),
    ("ResearchFinding", "Object", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 与 {t} 相关"),
    ("BookTitle", "Object", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 提到 {t}"),
    ("Concept", "Object", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 与 {t} 相关"),
    ("Fact", "Object", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 与 {t} 相关"),
    ("Quote", "Object", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 提到 {t}"),
    ("DataPoint", "Object", "ATTRIBUTE_MEASURED_BY", "{s} 通过 {t} 测量"),
    # ── Person ↔ Person、Location ↔ Location、Object ↔ Object ──
    ("Person", "Person", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 与 {t} 有合作关系"),
    ("Location", "Location", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 与 {t} 相关"),
    ("Object", "Object", "COMPARISON_SIMILAR_TO", "{s} 与 {t} 属于同类工具"),
    # ══════════════════════════════════════════════════════════════
    # v3 扩展: 9 种新实体类型的规则矩阵
    # ══════════════════════════════════════════════════════════════
    # ── AssessmentTool → ... ──
    ("AssessmentTool", "Problem", "ASSESSMENT_ASSESSES", "{s} 评估 {t}"),
    ("AssessmentTool", "Symptom", "ASSESSMENT_ASSESSES", "{s} 评估 {t}"),
    ("AssessmentTool", "CognitiveProcess", "ASSESSMENT_MEASURES", "{s} 测量 {t}"),
    ("AssessmentTool", "Diagnosis", "ASSESSMENT_DIAGNOSES", "{s} 用于诊断 {t}"),
    ("AssessmentTool", "ChildProfile", "ASSESSMENT_ASSESSES", "{s} 评估 {t}"),
    ("AssessmentTool", "Exercise", "ASSESSMENT_MEASURES", "{s} 测量 {t} 的效果"),
    ("AssessmentTool", "Intervention", "ASSESSMENT_MEASURES", "{s} 评估 {t} 的效果"),
    ("AssessmentTool", "Milestone", "ASSESSMENT_ASSESSES", "{s} 评估 {t} 的达成"),
    ("AssessmentTool", "Theory", "EVIDENCE_BASED_ON", "{s} 基于 {t} 设计"),
    ("AssessmentTool", "Study", "EVIDENCE_BASED_ON", "{s} 基于 {t} 验证"),
    ("AssessmentTool", "Environment", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 适用于 {t}"),
    ("AssessmentTool", "Object", "STRUCTURAL_CONTAINS", "{s} 包含 {t} 作为器材"),
    # ── … → AssessmentTool ──
    ("Problem", "AssessmentTool", "ASSESSMENT_ASSESSES", "{t} 评估 {s}"),
    ("Symptom", "AssessmentTool", "ASSESSMENT_MEASURES", "{t} 测量 {s}"),
    ("Diagnosis", "AssessmentTool", "ASSESSMENT_DIAGNOSES", "{t} 用于诊断 {s}"),
    ("CognitiveProcess", "AssessmentTool", "ATTRIBUTE_MEASURED_BY", "{s} 通过 {t} 测量"),
    ("Person", "AssessmentTool", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 开发/使用 {t}"),
    ("Organization", "AssessmentTool", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 开发/使用 {t}"),
    # ── Symptom → ... ──
    ("Symptom", "Problem", "STRUCTURAL_PART_OF", "{s} 是 {t} 的症状表现"),
    ("Symptom", "Diagnosis", "STRUCTURAL_BELONGS_TO", "{s} 是 {t} 的诊断标准之一"),
    ("Symptom", "BrainRegion", "FUNCTIONAL_INVOLVED_IN", "{s} 涉及 {t}"),
    ("Symptom", "Mechanism", "CAUSAL_CAUSES", "{s} 由 {t} 引起"),
    ("Symptom", "Neurotransmitter", "FUNCTIONAL_INVOLVED_IN", "{s} 与 {t} 水平相关"),
    ("Symptom", "Risk", "CAUSAL_CONTRIBUTES_TO", "{s} 增加 {t}"),
    ("Symptom", "Intervention", "THERAPEUTIC_ALLEVIATES", "{t} 缓解 {s}"),
    ("Symptom", "ChildProfile", "STRUCTURAL_BELONGS_TO", "{s} 在 {t} 中常见"),
    ("Symptom", "DevelopmentalStage", "DEVELOPMENTAL_EMERGES_AT", "{s} 在 {t} 出现"),
    ("Symptom", "Exercise", "THERAPEUTIC_ALLEVIATES", "{t} 缓解 {s}"),
    # ── … → Symptom ──
    ("Problem", "Symptom", "STRUCTURAL_CONTAINS", "{s} 的表现为 {t}"),
    ("Diagnosis", "Symptom", "STRUCTURAL_CONTAINS", "{s} 的诊断标准包括 {t}"),
    ("BrainRegion", "Symptom", "FUNCTIONAL_INVOLVED_IN", "{s} 的功能异常导致 {t}"),
    ("Mechanism", "Symptom", "CAUSAL_CAUSES", "{s} 导致 {t}"),
    ("Neurotransmitter", "Symptom", "CAUSAL_CONTRIBUTES_TO", "{s} 失衡导致 {t}"),
    ("Intervention", "Symptom", "THERAPEUTIC_ALLEVIATES", "{s} 缓解 {t}"),
    ("Risk", "Symptom", "CAUSAL_CAUSES", "{s} 导致 {t}"),
    # ── Intervention → ... ──
    ("Intervention", "Problem", "THERAPEUTIC_TREATS", "{s} 治疗 {t}"),
    ("Intervention", "Symptom", "THERAPEUTIC_ALLEVIATES", "{s} 缓解 {t}"),
    ("Intervention", "Diagnosis", "THERAPEUTIC_TREATS", "{s} 用于治疗 {t}"),
    ("Intervention", "CognitiveProcess", "THERAPEUTIC_IMPROVES", "{s} 改善 {t}"),
    ("Intervention", "BrainRegion", "FUNCTIONAL_REGULATES", "{s} 调节 {t}"),
    ("Intervention", "ChildProfile", "THERAPEUTIC_IMPROVES", "{s} 改善 {t}"),
    ("Intervention", "Mechanism", "FUNCTIONAL_INVOLVED_IN", "{s} 通过 {t} 起作用"),
    ("Intervention", "Risk", "THERAPEUTIC_PREVENTS", "{s} 预防 {t}"),
    ("Intervention", "Strategy", "STRUCTURAL_BELONGS_TO", "{s} 属于 {t}"),
    ("Intervention", "Exercise", "STRUCTURAL_CONTAINS", "{s} 包含 {t}"),
    ("Intervention", "Environment", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 在 {t} 中实施"),
    ("Intervention", "Milestone", "THERAPEUTIC_IMPROVES", "{s} 促进 {t} 的达成"),
    ("Intervention", "Study", "EVIDENCE_BASED_ON", "{s} 基于 {t} 的实证"),
    ("Intervention", "Organization", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 由 {t} 提供/实施"),
    # ── … → Intervention ──
    ("Problem", "Intervention", "THERAPEUTIC_TREATS", "{t} 治疗 {s}"),
    ("Symptom", "Intervention", "THERAPEUTIC_ALLEVIATES", "{t} 缓解 {s}"),
    ("Diagnosis", "Intervention", "THERAPEUTIC_TREATS", "{t} 用于治疗 {s}"),
    ("CognitiveProcess", "Intervention", "THERAPEUTIC_IMPROVES", "{t} 改善 {s}"),
    ("Strategy", "Intervention", "STRUCTURAL_CONTAINS", "{s} 包含 {t}"),
    ("Study", "Intervention", "EVIDENCE_SUPPORTS", "{s} 支持 {t} 的有效性"),
    ("Person", "Intervention", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 提出/开发了 {t}"),
    ("AssessmentTool", "Intervention", "ASSESSMENT_MEASURES", "{s} 评估 {t} 的效果"),
    # ── Diagnosis → ... ──
    ("Diagnosis", "Problem", "HIERARCHICAL_SUBCLASS_OF", "{s} 是 {t} 的一种"),
    ("Diagnosis", "Symptom", "STRUCTURAL_CONTAINS", "{s} 的症状包括 {t}"),
    ("Diagnosis", "BrainRegion", "FUNCTIONAL_INVOLVED_IN", "{s} 涉及 {t} 异常"),
    ("Diagnosis", "Risk", "CAUSAL_CONTRIBUTES_TO", "{s} 增加 {t} 风险"),
    ("Diagnosis", "Intervention", "THERAPEUTIC_TREATS", "{t} 治疗 {s}"),
    ("Diagnosis", "Mechanism", "FUNCTIONAL_INVOLVED_IN", "{s} 的机制涉及 {t}"),
    ("Diagnosis", "ChildProfile", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 常见于 {t}"),
    ("Diagnosis", "DevelopmentalStage", "DEVELOPMENTAL_EMERGES_AT", "{s} 常在 {t} 被识别"),
    ("Diagnosis", "Neurotransmitter", "FUNCTIONAL_INVOLVED_IN", "{s} 涉及 {t} 异常"),
    ("Diagnosis", "AssessmentTool", "ASSESSMENT_DIAGNOSES", "{t} 诊断 {s}"),
    ("Diagnosis", "Study", "EVIDENCE_DEMONSTRATES", "{t} 研究了 {s}"),
    ("Diagnosis", "Milestone", "DEVELOPMENTAL_PREREQUISITE_FOR", "{s} 影响 {t} 的达成"),
    # ── … → Diagnosis ──
    ("Problem", "Diagnosis", "HIERARCHICAL_SUBCLASS_OF", "{t} 是 {s} 的一种诊断"),
    ("Symptom", "Diagnosis", "STRUCTURAL_BELONGS_TO", "{s} 指向 {t}"),
    ("BrainRegion", "Diagnosis", "FUNCTIONAL_INVOLVED_IN", "{s} 异常导致 {t}"),
    ("Neurotransmitter", "Diagnosis", "CAUSAL_CONTRIBUTES_TO", "{s} 失衡与 {t} 相关"),
    ("Intervention", "Diagnosis", "THERAPEUTIC_TREATS", "{s} 用于治疗 {t}"),
    ("Study", "Diagnosis", "EVIDENCE_DEMONSTRATES", "{s} 研究了 {t}"),
    ("Person", "Diagnosis", "EVIDENCE_DEMONSTRATES", "{s} 研究了 {t}"),
    # ── Organization → ... ──
    ("Organization", "Study", "AUTHORSHIP_PUBLISHED_BY", "{t} 由 {s} 发表"),
    ("Organization", "Intervention", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 实施 {t}"),
    ("Organization", "Person", "SPATIAL_LOCATED_IN", "{t} 在 {s} 工作"),
    ("Organization", "Location", "SPATIAL_LOCATED_IN", "{s} 位于 {t}"),
    ("Organization", "AssessmentTool", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 开发/使用 {t}"),
    ("Organization", "Theory", "EVIDENCE_SUPPORTS", "{s} 的研究支持 {t}"),
    ("Organization", "Diagnosis", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 专注于 {t}"),
    ("Organization", "ChildProfile", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 服务 {t} 人群"),
    ("Organization", "Strategy", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 推行 {t}"),
    # ── … → Organization ──
    ("Person", "Organization", "SPATIAL_LOCATED_IN", "{s} 在 {t} 工作"),
    ("Study", "Organization", "AUTHORSHIP_PUBLISHED_BY", "{s} 由 {t} 发表"),
    ("Location", "Organization", "SPATIAL_LOCATED_IN", "{t} 位于 {s}"),
    ("Intervention", "Organization", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 由 {t} 实施"),
    # ── Study → ... ──
    ("Study", "Theory", "EVIDENCE_SUPPORTS", "{s} 支持 {t}"),
    ("Study", "Intervention", "EVIDENCE_SUPPORTS", "{s} 验证了 {t} 的有效性"),
    ("Study", "ResearchFinding", "EVIDENCE_BASED_ON", "{t} 基于 {s}"),
    ("Study", "Diagnosis", "EVIDENCE_DEMONSTRATES", "{s} 揭示了 {t} 的特征"),
    ("Study", "Problem", "EVIDENCE_DEMONSTRATES", "{s} 证实了 {t}"),
    ("Study", "Person", "AUTHORSHIP_PUBLISHED_BY", "{s} 由 {t} 发表"),
    ("Study", "Organization", "AUTHORSHIP_PUBLISHED_BY", "{s} 由 {t} 发表"),
    ("Study", "AssessmentTool", "EVIDENCE_SUPPORTS", "{s} 验证了 {t}"),
    ("Study", "Mechanism", "EVIDENCE_DEMONSTRATES", "{s} 揭示了 {t}"),
    ("Study", "KeyInsight", "EVIDENCE_BASED_ON", "{t} 基于 {s}"),
    ("Study", "DataPoint", "STRUCTURAL_CONTAINS", "{s} 包含 {t}"),
    ("Study", "Neurotransmitter", "EVIDENCE_DEMONSTRATES", "{s} 研究了 {t} 的作用"),
    ("Study", "Milestone", "EVIDENCE_DEMONSTRATES", "{s} 记录了 {t} 的发展轨迹"),
    # ── … → Study ──
    ("Theory", "Study", "EVIDENCE_PROVEN_BY", "{s} 被 {t} 验证"),
    ("Person", "Study", "AUTHORSHIP_PUBLISHED_BY", "{t} 由 {s} 发表"),
    ("Organization", "Study", "AUTHORSHIP_PUBLISHED_BY", "{t} 由 {s} 发表"),
    ("Intervention", "Study", "EVIDENCE_PROVEN_BY", "{s} 被 {t} 验证"),
    ("AssessmentTool", "Study", "EVIDENCE_PROVEN_BY", "{s} 被 {t} 验证"),
    ("ResearchFinding", "Study", "EVIDENCE_BASED_ON", "{s} 基于 {t}"),
    # ── Neurotransmitter → ... ──
    ("Neurotransmitter", "BrainRegion", "FUNCTIONAL_REGULATES", "{s} 调节 {t}"),
    ("Neurotransmitter", "CognitiveProcess", "FUNCTIONAL_MODULATES", "{s} 调制 {t}"),
    ("Neurotransmitter", "Mechanism", "FUNCTIONAL_MEDIATES", "{s} 介导 {t}"),
    ("Neurotransmitter", "Symptom", "CAUSAL_CONTRIBUTES_TO", "{s} 失衡导致 {t}"),
    ("Neurotransmitter", "Diagnosis", "FUNCTIONAL_INVOLVED_IN", "{s} 异常参与 {t}"),
    ("Neurotransmitter", "Exercise", "FUNCTIONAL_REGULATES", "{t} 影响 {s} 释放"),
    ("Neurotransmitter", "Intervention", "FUNCTIONAL_MEDIATES", "{s} 介导 {t} 的效果"),
    ("Neurotransmitter", "Object", "FUNCTIONAL_MODULATES", "{t} 影响 {s}"),
    ("Neurotransmitter", "Problem", "CAUSAL_CONTRIBUTES_TO", "{s} 异常与 {t} 相关"),
    # ── … → Neurotransmitter ──
    ("BrainRegion", "Neurotransmitter", "FUNCTIONAL_REGULATES", "{s} 调节 {t} 的释放"),
    ("CognitiveProcess", "Neurotransmitter", "FUNCTIONAL_MODULATES", "{s} 依赖 {t}"),
    ("Exercise", "Neurotransmitter", "FUNCTIONAL_REGULATES", "{s} 调节 {t} 水平"),
    ("Mechanism", "Neurotransmitter", "FUNCTIONAL_INVOLVED_IN", "{s} 涉及 {t}"),
    ("Object", "Neurotransmitter", "FUNCTIONAL_MODULATES", "{s} 影响 {t}"),
    ("Symptom", "Neurotransmitter", "CAUSAL_CAUSES", "{s} 由 {t} 失衡引起"),
    ("Intervention", "Neurotransmitter", "FUNCTIONAL_REGULATES", "{s} 调节 {t}"),
    ("Study", "Neurotransmitter", "EVIDENCE_DEMONSTRATES", "{s} 研究了 {t}"),
    # ── Milestone → ... ──
    ("Milestone", "DevelopmentalStage", "DEVELOPMENTAL_EMERGES_AT", "{s} 出现在 {t}"),
    ("Milestone", "CognitiveProcess", "DEVELOPMENTAL_PREREQUISITE_FOR", "{s} 是 {t} 发展的前提"),
    ("Milestone", "ChildProfile", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 是 {t} 的评估指标"),
    ("Milestone", "Diagnosis", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 的延迟与 {t} 相关"),
    ("Milestone", "Exercise", "THERAPEUTIC_IMPROVES", "{t} 促进 {s}"),
    ("Milestone", "Intervention", "THERAPEUTIC_IMPROVES", "{t} 促进 {s} 的达成"),
    ("Milestone", "Environment", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 在 {t} 中更容易达成"),
    ("Milestone", "Risk", "CAUSAL_CONTRIBUTES_TO", "{s} 的延迟提示 {t}"),
    ("Milestone", "AssessmentTool", "ASSESSMENT_ASSESSES", "{t} 评估 {s}"),
    ("Milestone", "Symptom", "CAUSAL_CONTRIBUTES_TO", "{s} 的延迟可能表现为 {t}"),
    # ── … → Milestone ──
    ("DevelopmentalStage", "Milestone", "TEMPORAL_DURING", "{s} 期的里程碑包括 {t}"),
    ("CognitiveProcess", "Milestone", "TEMPORAL_DEVELOPS_INTO", "{s} 的发展达成 {t}"),
    ("ChildProfile", "Milestone", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 的评估包括 {t}"),
    ("Exercise", "Milestone", "THERAPEUTIC_IMPROVES", "{s} 促进 {t}"),
    ("Intervention", "Milestone", "THERAPEUTIC_IMPROVES", "{s} 促进 {t}"),
    ("Environment", "Milestone", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 支持 {t} 的达成"),
    ("Diagnosis", "Milestone", "DEVELOPMENTAL_PREREQUISITE_FOR", "{s} 影响 {t}"),
    # ── Environment → ... ──
    ("Environment", "ChildProfile", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 影响 {t} 的发展"),
    ("Environment", "Intervention", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 是 {t} 的实施场所"),
    ("Environment", "Problem", "CAUSAL_CONTRIBUTES_TO", "{s} 因素影响 {t}"),
    ("Environment", "Exercise", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 是 {t} 的实施场所"),
    ("Environment", "Strategy", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 影响 {t} 的效果"),
    ("Environment", "Milestone", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 支持 {t} 的达成"),
    ("Environment", "CognitiveProcess", "FUNCTIONAL_INVOLVED_IN", "{s} 影响 {t} 的表现"),
    ("Environment", "Symptom", "CAUSAL_CONTRIBUTES_TO", "{s} 可能诱发 {t}"),
    ("Environment", "Risk", "CAUSAL_CONTRIBUTES_TO", "{s} 包含 {t} 因素"),
    ("Environment", "Organization", "SPATIAL_LOCATED_IN", "{s} 位于 {t}"),
    # ── … → Environment ──
    ("Intervention", "Environment", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 在 {t} 中实施"),
    ("ChildProfile", "Environment", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 所处 {t} 影响发展"),
    ("Problem", "Environment", "CAUSAL_CONTRIBUTES_TO", "{t} 因素影响 {s}"),
    ("Strategy", "Environment", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 在 {t} 中应用"),
    ("Organization", "Environment", "SPATIAL_LOCATED_IN", "{t} 位于 {s}"),
    ("AssessmentTool", "Environment", "ATTRIBUTE_ASSOCIATED_WITH", "{s} 在 {t} 中施测"),
    # ── 新类型之间的连接 ──
    ("Diagnosis", "Symptom", "STRUCTURAL_CONTAINS", "{s} 的诊断标准包括 {t}"),
    ("Intervention", "Intervention", "COMPARISON_ALTERNATIVE_TO", "{s} 是 {t} 的替代方案"),
    ("Study", "Study", "AUTHORSHIP_CITED_BY", "{s} 引用 {t}"),
    ("Neurotransmitter", "Neurotransmitter", "FUNCTIONAL_MODULATES", "{s} 调节 {t} 的释放"),
    ("Milestone", "Milestone", "DEVELOPMENTAL_PREREQUISITE_FOR", "{s} 是 {t} 的前提"),
    ("Environment", "Environment", "COMPARISON_DIFFERENT_FROM", "{s} 与 {t} 不同"),
]


def infer_relations_by_type_rules(
    master: MasterGraph,
    max_conn_per_orphan: int = 3,
) -> list[ExtractedRelationship]:
    """基于 entity_type 组合的启发式规则推断关系。

    连接策略：
    - 仅当实体对中**至少有一方当前是孤立的**（degree=0）时才建立新边
    - 每个孤立实体最多获得 max_conn_per_orphan 条规则边（防止爆炸）
    - 同一条规则内优先连接高度数 hub（让孤立实体融入主干）
    - 允许跨章连接

    标记 confidence=0.5, relation_source="heuristic_rule"。
    """
    G = master.graph
    nodes = list(G.nodes)
    added: list[ExtractedRelationship] = []
    seen_keys: set[tuple] = set()

    # 预构建类型索引（按 degree 降序，优先连 hub）
    type_index: dict[str, list[str]] = {}
    for n in nodes:
        ntype = G.nodes[n].get("entity_type", "AutoEntity")
        type_index.setdefault(ntype, []).append(n)
    for ntype in type_index:
        type_index[ntype].sort(key=lambda n: G.degree(n), reverse=True)

    # 每个实体的连接配额（只对当前孤立的实体生效）
    orphan_conn_count: dict[str, int] = {}

    for src_type, tgt_type, rel_type, desc_tpl in TYPE_RULES:
        src_nodes = type_index.get(src_type, [])
        tgt_nodes = type_index.get(tgt_type, [])

        for s_name in src_nodes:
            s_degree = G.degree(s_name)
            s_is_orphan = s_degree == 0

            for t_name in tgt_nodes:
                if s_name == t_name:
                    continue
                if t_name not in G:
                    continue

                t_is_orphan = G.degree(t_name) == 0
                if not s_is_orphan and not t_is_orphan:
                    continue
                # 配额检查：孤立方的已连接数已达上限则跳过
                orphan_name = s_name if s_is_orphan else t_name
                if orphan_conn_count.get(orphan_name, 0) >= max_conn_per_orphan:
                    continue
                # 当双方都孤立时，source 方消耗配额
                if s_is_orphan and t_is_orphan:
                    if orphan_conn_count.get(s_name, 0) >= max_conn_per_orphan:
                        continue

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
                # 更新配额
                if s_is_orphan:
                    orphan_conn_count[s_name] = orphan_conn_count.get(s_name, 0) + 1
                if t_is_orphan:
                    orphan_conn_count[t_name] = orphan_conn_count.get(t_name, 0) + 1

    logger.info(
        "类型规则推断: 新增 %d 条关系（每孤立实体 ≤%d 条，共 %d 个孤立被连接）",
        len(added), max_conn_per_orphan, len(orphan_conn_count),
    )
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
    threshold: float = 0.45,
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

### 关系类型（从以下大类中选择）
- **因果**：CAUSAL_CAUSES / CAUSAL_LEADS_TO / CAUSAL_CONTRIBUTES_TO / CAUSAL_TRIGGERS / CAUSAL_RESULTS_IN
- **治疗/干预**：THERAPEUTIC_TREATS / THERAPEUTIC_PREVENTS / THERAPEUTIC_ALLEVIATES / THERAPEUTIC_IMPROVES / THERAPEUTIC_INHIBITS / THERAPEUTIC_ENHANCES
- **结构/组成**：STRUCTURAL_PART_OF / STRUCTURAL_CONTAINS / STRUCTURAL_CONSISTS_OF / STRUCTURAL_BELONGS_TO
- **功能/参与**：FUNCTIONAL_REGULATES / FUNCTIONAL_MODULATES / FUNCTIONAL_PARTICIPATES_IN / FUNCTIONAL_INVOLVED_IN / FUNCTIONAL_PLAYS_ROLE_IN / FUNCTIONAL_MEDIATES / FUNCTIONAL_TRANSFORMS
- **证据/研究**：EVIDENCE_SUPPORTS / EVIDENCE_PROVEN_BY / EVIDENCE_BASED_ON / EVIDENCE_CONTRADICTS / EVIDENCE_DEMONSTRATES
- **时间/发展**：TEMPORAL_PRECEDES / TEMPORAL_FOLLOWS / TEMPORAL_DURING / TEMPORAL_DEVELOPS_INTO / DEVELOPMENTAL_EMERGES_AT / DEVELOPMENTAL_PREREQUISITE_FOR
- **评估/诊断**：ASSESSMENT_ASSESSES / ASSESSMENT_DIAGNOSES / ASSESSMENT_MEASURES
- **空间/归属**：SPATIAL_LOCATED_IN / SPATIAL_CONNECTS_TO
- **层级/分类**：HIERARCHICAL_SUBCLASS_OF / HIERARCHICAL_INSTANCE_OF
- **发布/创作**：AUTHORSHIP_PUBLISHED_BY / AUTHORSHIP_CITED_BY
- **属性/关联**：ATTRIBUTE_ASSOCIATED_WITH / ATTRIBUTE_HAS_PROPERTY / ATTRIBUTE_CHARACTERIZED_BY / ATTRIBUTE_MEASURED_BY
- **兜底**：RELATES_TO

### 规则
1. 只输出你有把握的关系（基于领域知识）
2. source 必须是孤立实体之一，target 必须是核心实体之一
3. 每个孤立实体至少输出 1 条关系
4. 根据实体类型选择最合适的关系类型（如 Person → Study 用 AUTHORSHIP_PUBLISHED_BY，Symptom → Diagnosis 用 STRUCTURAL_BELONGS_TO）

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
    hub_count: int = 100,
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

    # Step 1.5: 共现关系推断
    cooccur_rels = infer_cooccurrence_relations(master)
    for rel in cooccur_rels:
        master.add_relationship(rel, chapter_id="__cooccurrence__")

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

    # Step 3: LLM 全局补全
    llm_rels = []
    remaining_orphans = sum(1 for n in G.nodes if G.degree(n) == 0)
    if llm_client and remaining_orphans > 0:
        llm_rels = await infer_relations_by_llm_global(master, llm_client, model=model)
        for rel in llm_rels:
            master.add_relationship(rel, chapter_id="__llm_global__")

    # Step 4: 星型兜底（embedding 最近邻）
    fallback_rels = []
    if embedding_client:
        remaining_after_llm = sum(1 for n in G.nodes if G.degree(n) == 0)
        if remaining_after_llm > 0:
            fallback_rels = await star_fallback(master, embedding_client)
            for rel in fallback_rels:
                master.add_relationship(rel, chapter_id="__star_fallback__")

    # Step 5: 类型匹配兜底（零依赖，确保最终零孤立）
    type_fallback_rels = infer_type_based_relations(master)
    for rel in type_fallback_rels:
        master.add_relationship(rel, chapter_id="__type_fallback__")

    final_orphans = sum(1 for n in G.nodes if G.degree(n) == 0)
    final_edges = G.number_of_edges()

    result = {
        "initial_orphans": initial_orphans,
        "final_orphans": final_orphans,
        "relation_types_merged": len([k for k, v in relation_type_mapping.items() if k != v]),
        "relation_type_mapping": relation_type_mapping,
        "relations_added": {
            "heuristic_rule": len(rule_rels),
            "cooccurrence": len(cooccur_rels),
            "embedding_sim": len(embed_rels),
            "component_bridge": len(bridge_rels),
            "llm_global_fix": len(llm_rels),
            "star_fallback": len(fallback_rels),
            "type_fallback": len(type_fallback_rels),
            "total": (len(rule_rels) + len(cooccur_rels) + len(embed_rels)
                      + len(bridge_rels) + len(llm_rels) + len(fallback_rels)
                      + len(type_fallback_rels)),
        },
        "total_relations_before": initial_edges,
        "total_relations_after": final_edges,
    }

    logger.info(
        "Phase 2.5 完成: 孤立实体 %d → %d, 关系数 %d → %d "
        "(规则 +%d, 共现 +%d, Embedding +%d, 桥接 +%d, LLM +%d, 星型 +%d, 类型兜底 +%d)",
        initial_orphans, final_orphans,
        initial_edges, final_edges,
        len(rule_rels), len(cooccur_rels), len(embed_rels),
        len(bridge_rels), len(llm_rels), len(fallback_rels), len(type_fallback_rels),
    )

    return result


# ──────────────────────────────────────────────────────────────
# Step 1.5: 共现关系推断（段落级共现 → RELATES_TO）
# ──────────────────────────────────────────────────────────────


def infer_cooccurrence_relations(
    master: MasterGraph,
    min_cooccurrence: int = 2,
) -> list[ExtractedRelationship]:
    """基于段落共现推断关系。

    如果两个实体在多个段落中共同出现，它们之间很可能存在某种关系。
    仅处理目前孤立的实体对，避免重复。

    Args:
        master: 主图
        min_cooccurrence: 最少共现段落数

    Returns:
        新增的共现关系列表
    """
    G = master.graph
    added: list[ExtractedRelationship] = []

    # 构建段落 → 实体集合的反向索引
    para_entities: dict[tuple[str, int], set[str]] = {}  # (chapter_id, para_id) → {entity_names}
    for node in G.nodes:
        if G.degree(node) > 0:
            continue  # 只处理孤立实体
        source_para_ids = G.nodes[node].get("source_para_ids", {})
        if not source_para_ids:
            continue
        for ch_id, pids in source_para_ids.items():
            for pid in pids:
                key = (ch_id, pid)
                if key not in para_entities:
                    para_entities[key] = set()
                para_entities[key].add(node)

    # 统计孤立实体对的共现次数
    pair_counts: dict[tuple[str, str], int] = {}
    for entities in para_entities.values():
        entity_list = list(entities)
        for i in range(len(entity_list)):
            for j in range(i + 1, len(entity_list)):
                key = tuple(sorted([entity_list[i], entity_list[j]]))
                pair_counts[key] = pair_counts.get(key, 0) + 1

    # 过滤满足阈值的共现对
    for (src, tgt), count in pair_counts.items():
        if count >= min_cooccurrence:
            if not G.has_edge(src, tgt):
                rel = ExtractedRelationship(
                    source=src,
                    target=tgt,
                    relation_type=RelationType.RELATES_TO,
                    evidence=f"段落共现 {count} 次",
                    source_para_ids=[],
                    relation_source="cooccurrence",
                    confidence=min(0.3 + count * 0.1, 0.7),
                )
                added.append(rel)

    logger.info("共现关系推断: 为 %d 个孤立实体对新增 %d 条关系", len(pair_counts), len(added))
    return added


# ──────────────────────────────────────────────────────────────
# Step 4: 星型兜底（剩余孤立实体 → 最近实体）
# ──────────────────────────────────────────────────────────────


async def star_fallback(
    master: MasterGraph,
    embedding_client: EmbeddingClient,
    max_connections: int = 3,
    min_similarity: float = 0.35,
) -> list[ExtractedRelationship]:
    """星型兜底：为经过所有补全步骤后仍孤立的实体，强制连接最近的非孤立实体。

    这是最后的兜底策略，确保没有实体完全孤立。
    标记 confidence=0.2, relation_source="star_fallback"。

    Args:
        master: 主图
        embedding_client: embedding 客户端
        max_connections: 每个孤立实体最多连接数
        min_similarity: 最低相似度阈值（低于此值不连接）

    Returns:
        新增的兜底关系列表
    """
    G = master.graph
    if G.number_of_nodes() == 0:
        return []

    orphans = [n for n in G.nodes if G.degree(n) == 0]
    if not orphans:
        logger.info("星型兜底: 无孤立实体，跳过")
        return []

    # 选连接目标：优先选非孤立实体，如果没有（全部孤立），选所有实体
    non_orphans = [n for n in G.nodes if G.degree(n) > 0]
    targets = non_orphans if non_orphans else list(G.nodes)

    logger.info("星型兜底: %d 个孤立实体, %d 个候选目标", len(orphans), len(targets))

    # 获取 embedding
    orphan_embs = await embedding_client.embed(orphans)
    target_embs = await embedding_client.embed(targets)
    target_map = {name: i for i, name in enumerate(targets)}

    added: list[ExtractedRelationship] = []

    for i, o_name in enumerate(orphans):
        o_emb = orphan_embs[i]
        # 计算与所有目标的相似度
        sims = [(j, _cosine_similarity(o_emb, t_emb)) for j, t_emb in enumerate(target_embs)]
        sims.sort(key=lambda x: x[1], reverse=True)

        count = 0
        for j, sim in sims:
            if sim < min_similarity:
                break  # 排序后后续更小，直接终止
            if count >= max_connections:
                break
            target_name = targets[j]
            if target_name == o_name:
                continue
            # 跳过已连接的
            if G.has_edge(o_name, target_name):
                continue

            rel = ExtractedRelationship(
                source=o_name,
                target=target_name,
                relation_type=RelationType.RELATES_TO,
                evidence=f"星型兜底 (embedding sim={sim:.3f})",
                source_para_ids=[],
                relation_source="star_fallback",
                confidence=round(max(0.1, sim * 0.4), 3),
            )
            added.append(rel)
            count += 1

    # 兜底：如果有孤立实体完全没连上，强制连接最相似的一个（不设阈值）
    connected_orphans = {r.source for r in added}
    for i, o_name in enumerate(orphans):
        if o_name in connected_orphans:
            continue
        o_emb = orphan_embs[i]
        sims = [(j, _cosine_similarity(o_emb, t_emb)) for j, t_emb in enumerate(target_embs)]
        sims.sort(key=lambda x: x[1], reverse=True)
        for j, sim in sims:
            target_name = targets[j]
            if target_name == o_name:
                continue
            if G.has_edge(o_name, target_name):
                continue
            rel = ExtractedRelationship(
                source=o_name,
                target=target_name,
                relation_type=RelationType.RELATES_TO,
                evidence=f"星型兜底-强制 (embedding sim={sim:.3f})",
                source_para_ids=[],
                relation_source="star_fallback",
                confidence=round(max(0.05, sim * 0.3), 3),
            )
            added.append(rel)
            break  # 每个孤立实体只强制连一个

    logger.info("星型兜底: 为 %d 个孤立实体新增 %d 条关系", len(orphans), len(added))
    return added

# ──────────────────────────────────────────────────────────────
# Step 3.5: 纯类型匹配兜底（不依赖 embedding，确保零孤立）
# ──────────────────────────────────────────────────────────────

# 相邻类型映射：当孤立实体没有同类型目标时，退而连接这些类型
_RELATED_TYPES: dict[str, list[str]] = {
    "Exercise": ["CognitiveProcess", "BrainRegion", "Mechanism", "Problem", "Object"],
    "Problem": ["Risk", "RootCause", "BrainRegion", "Mechanism", "CognitiveProcess"],
    "BrainRegion": ["CognitiveProcess", "Mechanism", "Exercise"],
    "CognitiveProcess": ["BrainRegion", "Mechanism", "Exercise", "Problem"],
    "Risk": ["Problem", "BrainRegion", "CognitiveProcess", "Mechanism"],
    "RootCause": ["Problem", "Mechanism", "BrainRegion"],
    "Mechanism": ["BrainRegion", "CognitiveProcess", "Problem", "Exercise"],
    "Theory": ["ResearchFinding", "Concept", "CognitiveProcess", "Person"],
    "ResearchFinding": ["Theory", "Fact", "DataPoint", "Concept", "Person", "Location"],
    "Strategy": ["Exercise", "Problem", "Prescription", "Object"],
    "Prescription": ["Exercise", "Strategy", "Problem", "Object"],
    "Concept": ["CognitiveProcess", "Theory", "ResearchFinding", "Fact"],
    "Fact": ["ResearchFinding", "DataPoint", "Concept"],
    "DataPoint": ["Fact", "ResearchFinding", "Concept"],
    "Quote": ["Theory", "KeyInsight", "ResearchFinding", "Person"],
    "KeyInsight": ["Theory", "ResearchFinding", "Concept", "Person"],
    "BookTitle": ["Theory", "Concept", "ResearchFinding", "Person"],
    "DevelopmentalStage": ["CognitiveProcess", "Problem", "ChildProfile"],
    "ChildProfile": ["Problem", "DevelopmentalStage", "CognitiveProcess"],
    "Solution": ["Problem", "Strategy", "Exercise"],
    "AssessmentTool": ["Problem", "CognitiveProcess", "Mechanism", "Symptom", "Diagnosis", "ChildProfile"],
    # v2 新增: 人名/地名/物品的类型相邻映射
    "Person": ["Theory", "ResearchFinding", "Concept", "Strategy", "KeyInsight", "BookTitle", "Study", "Diagnosis", "Intervention"],
    "Location": ["ResearchFinding", "Concept", "Strategy", "Theory", "Person", "Organization", "Study"],
    "Object": ["Exercise", "Strategy", "Prescription", "Problem", "Concept", "AssessmentTool", "Neurotransmitter"],
    # v3 新增: 9 种新类型的相邻映射
    "Symptom": ["Problem", "Diagnosis", "BrainRegion", "Mechanism", "Neurotransmitter", "Intervention", "ChildProfile"],
    "Intervention": ["Problem", "Symptom", "Diagnosis", "CognitiveProcess", "Strategy", "Exercise", "Study", "Organization"],
    "Diagnosis": ["Problem", "Symptom", "BrainRegion", "Intervention", "AssessmentTool", "Neurotransmitter", "ChildProfile", "DevelopmentalStage"],
    "Organization": ["Person", "Study", "Location", "Intervention", "Strategy"],
    "Study": ["Theory", "Intervention", "Diagnosis", "Person", "Organization", "ResearchFinding", "AssessmentTool"],
    "Neurotransmitter": ["BrainRegion", "CognitiveProcess", "Mechanism", "Symptom", "Diagnosis", "Exercise"],
    "Milestone": ["DevelopmentalStage", "CognitiveProcess", "ChildProfile", "Exercise", "Intervention", "Environment", "Diagnosis"],
    "Environment": ["ChildProfile", "Intervention", "Problem", "Exercise", "Strategy", "Milestone", "Organization"],
    "AutoEntity": [],  # AutoEntity 尝试所有类型
}


def infer_type_based_relations(master: MasterGraph) -> list[ExtractedRelationship]:
    """纯类型匹配兜底：为仍然孤立的实体，按 entity_type 匹配连接目标。

    不依赖 embedding，零成本。连接策略：
    1. 优先连同类型的最高 degree 实体
    2. 没有同类型目标时，连相邻类型的最高 degree 实体
    3. 都没有时，连全局最高 degree 实体（兜底）

    标记 confidence=0.15, relation_source="type_fallback"。
    """
    G = master.graph
    orphans = [n for n in G.nodes if G.degree(n) == 0]
    if not orphans:
        logger.info("类型匹配兜底: 无孤立实体，跳过")
        return []

    # 按类型分组所有实体，同时记录每个实体的 degree
    type_index: dict[str, list[str]] = {}
    for n in G.nodes:
        ntype = G.nodes[n].get("entity_type", "AutoEntity")
        type_index.setdefault(ntype, []).append(n)

    # 按 degree 降序排列每个类型的实体
    for ntype in type_index:
        type_index[ntype].sort(key=lambda n: G.degree(n), reverse=True)

    # 全局 top-20 高 degree 实体（最终兜底）
    global_hubs = sorted(G.nodes, key=lambda n: G.degree(n), reverse=True)[:20]

    added: list[ExtractedRelationship] = []

    for o_name in orphans:
        o_type = G.nodes[o_name].get("entity_type", "AutoEntity")
        connected = False

        # 策略 1: 同类型最高 degree 实体
        same_type_targets = [n for n in type_index.get(o_type, []) if n != o_name]
        if same_type_targets:
            target = same_type_targets[0]
            rel = ExtractedRelationship(
                source=o_name,
                target=target,
                relation_type=RelationType.ATTRIBUTE_ASSOCIATED_WITH,
                evidence=f"类型匹配兜底 (同类型 {o_type})",
                source_para_ids=[],
                relation_source="type_fallback",
                confidence=0.15,
            )
            added.append(rel)
            connected = True

        # 策略 2: 相邻类型最高 degree 实体
        if not connected:
            related = _RELATED_TYPES.get(o_type, [])
            # AutoEntity 尝试所有非空类型
            if not related and o_type == "AutoEntity":
                related = [t for t, targets in type_index.items() if targets and t != "AutoEntity"]
            for rtype in related:
                targets = [n for n in type_index.get(rtype, []) if n != o_name]
                if targets:
                    target = targets[0]
                    rel = ExtractedRelationship(
                        source=o_name,
                        target=target,
                        relation_type=RelationType.ATTRIBUTE_ASSOCIATED_WITH,
                        evidence=f"类型匹配兜底 ({o_type} → {rtype})",
                        source_para_ids=[],
                        relation_source="type_fallback",
                        confidence=0.10,
                    )
                    added.append(rel)
                    connected = True
                    break

        # 策略 3: 全局最高 degree 实体
        if not connected:
            for hub in global_hubs:
                if hub != o_name and not G.has_edge(o_name, hub):
                    rel = ExtractedRelationship(
                        source=o_name,
                        target=hub,
                        relation_type=RelationType.RELATES_TO,
                        evidence="类型匹配兜底 (全局 hub)",
                        source_para_ids=[],
                        relation_source="type_fallback",
                        confidence=0.05,
                    )
                    added.append(rel)
                    break

    logger.info("类型匹配兜底: 为 %d 个孤立实体新增 %d 条关系", len(orphans), len(added))
    return added


# ──────────────────────────────────────────────────────────────
# Step 2.5: 跨分量桥接（连接孤立的连通分量）
# ──────────────────────────────────────────────────────────────

async def bridge_components(
    master: MasterGraph,
    embedding_client: EmbeddingClient,
    threshold: float = 0.40,
    top_k: int = 3,
    max_rounds: int = 3,
    target_components: int = 10,
) -> list[ExtractedRelationship]:
    """跨分量桥接：多轮多桥，连接所有孤立的连通分量。

    改进策略:
    1. 全分量对桥接（不仅限于主分量）
    2. 每对分量取 Top-K 最相似实体对（而非仅 Top-1）
    3. 多轮迭代，直到分量数 <= target_components 或不再收敛

    Args:
        master: 主图
        embedding_client: embedding 客户端
        threshold: 桥接阈值（低于消歧阈值，因为是跨分量）
        top_k: 每对分量最多桥接数
        max_rounds: 最大迭代轮数
        target_components: 目标分量数

    Returns:
        新增的桥接关系列表
    """
    import networkx as nx

    G = master.graph
    if G.number_of_nodes() == 0:
        return []

    # 预计算所有实体 embedding（只算一次）
    all_names = list(G.nodes)
    all_embs = await embedding_client.embed(all_names)
    emb_map = dict(zip(all_names, all_embs))

    added: list[ExtractedRelationship] = []

    for round_idx in range(max_rounds):
        undirected = G.to_undirected()
        components = list(nx.connected_components(undirected))
        n_comp = len(components)

        if n_comp <= target_components:
            logger.info(
                "跨分量桥接: 第 %d 轮, 分量 %d <= 目标 %d, 结束",
                round_idx + 1, n_comp, target_components,
            )
            break

        logger.info(
            "跨分量桥接: 第 %d 轮, %d 个分量 (目标 %d)",
            round_idx + 1, n_comp, target_components,
        )

        # 按分量大小排序
        components.sort(key=len, reverse=True)

        round_added = 0
        # 对每对分量找 top-k 桥接（跳过已连通的）
        for ci in range(len(components)):
            for cj in range(ci + 1, len(components)):
                # 检查这两个分量是否已经连通（前几轮可能已桥接）
                comp_i = components[ci]
                comp_j = components[cj]
                # 用并查集或直接检查：取两个分量各一个代表节点
                rep_i = next(iter(comp_i))
                rep_j = next(iter(comp_j))
                if nx.has_path(undirected, rep_i, rep_j):
                    continue

                # 找 top-k 最相似实体对
                names_i = list(comp_i)
                names_j = list(comp_j)
                pairs = []
                for ni in names_i:
                    ei = emb_map.get(ni)
                    if ei is None:
                        continue
                    for nj in names_j:
                        ej = emb_map.get(nj)
                        if ej is None:
                            continue
                        sim = _cosine_similarity(ei, ej)
                        if sim >= threshold:
                            pairs.append((sim, ni, nj))

                pairs.sort(reverse=True)
                for sim, src, tgt in pairs[:top_k]:
                    rel = ExtractedRelationship(
                        source=src,
                        target=tgt,
                        relation_type=RelationType.RELATES_TO,
                        evidence=f"跨分量桥接 (embedding sim={sim:.3f}, round {round_idx + 1})",
                        source_para_ids=[],
                        relation_source="component_bridge",
                        confidence=sim,
                    )
                    master.add_relationship(rel, chapter_id="__bridge__")
                    added.append(rel)
                    round_added += 1

        logger.info("  第 %d 轮新增 %d 条桥接关系", round_idx + 1, round_added)

        if round_added == 0:
            logger.info("  第 %d 轮无新桥接, 提前终止", round_idx + 1)
            break

    final_comp = len(list(nx.connected_components(G.to_undirected())))
    logger.info(
        "跨分量桥接完成: %d 条桥接关系, 分量 %d → %d",
        len(added), len(list(nx.connected_components(
            # 重新计算初始分量数（approximate, 用 added 条数估算）
            G.to_undirected()
        ))), final_comp,
    )
    return added
