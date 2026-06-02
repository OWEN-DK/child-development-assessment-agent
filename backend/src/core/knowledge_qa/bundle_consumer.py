"""Phase 2: Bundle 消费 — 从 Bundle 按需切片，构造优先级上下文

Section 节点只需调用 `extract_for_section` + `build_priority_context`，
不再执行任何 HTTP 搜索。

放置位置: backend/src/core/knowledge_qa/bundle_consumer.py
"""

from __future__ import annotations

import logging
from typing import Any

from src.core.knowledge_qa.bundle import (
    BookMeta, GraphEntity, GraphRelation, KnowledgeBundle, Passage,
    normalize_book_title,
)

logger = logging.getLogger(__name__)

# ── 各节 passage 配额 ──
SECTION_QUOTAS = {1: 0.20, 2: 0.20, 3: 0.25, 4: 0.25, 5: 0.10}

# ── 跨书关系类型的中文语义标签（用于 LLM prompt 渲染）──
_CROSS_RELATION_LABELS: dict[str, str] = {
    # ── 实体消歧 ──
    "SAME_AS":              "概念等价",
    "CROSS_BOOK_CONSENSUS": "观点一致",
    # ── Gen1 legacy ──
    "CROSS_BOOK_COMPLEMENTS": "互为补充",
    "CROSS_BOOK_CONFLICTS":   "观点矛盾",
    # ── 治疗/干预类 ──
    "CROSS_TREATS":           "治疗/干预",
    "CROSS_PREVENTS":         "预防",
    "CROSS_ALLEVIATES":       "缓解",
    "CROSS_ADDRESSES":        "针对解决",
    # ── 改善/增强类 ──
    "CROSS_IMPROVES":         "改善",
    "CROSS_ENHANCES":         "增强",
    # ── 因果/机制类 ──
    "CROSS_CAUSES":           "导致",
    "CROSS_CONTRIBUTES_TO":   "促成",
    "CROSS_AFFECTS":          "影响",
    "CROSS_INCREASES_RISK":   "增加风险",
    # ── 支持/解释类 ──
    "CROSS_SUPPORTS":         "支持",
    "CROSS_SUPPORTED_BY":     "依据来源",
    "CROSS_EXPLAINS":         "解释",
    "CROSS_EXPLAINED_BY":     "被解释为",
    # ── 时序/空间类 ──
    "CROSS_OCCURS_AT":        "发生于阶段",
    "CROSS_LOCALIZED_IN":     "定位于",
    # ── 关联/扩展类 ──
    "CROSS_ASSOCIATED_WITH":  "相关联",
    "CROSS_INVOLVES":         "涉及",
    "CROSS_EXTENDS":          "扩展",
    "CROSS_COMPLEMENTS":      "互补",
    "CROSS_ILLUMINATES":      "阐明",
    "CROSS_COMBINES_WITH":    "组合使用",
    "CROSS_CONTRADICTS":      "矛盾",
}


def _get_relevant_cross_types(section_index: int) -> set[str]:
    """返回指定节关注的跨书关系类型集合。"""
    all_types = set(_CROSS_RELATION_LABELS.keys())
    if section_index in (1, 2):
        # S1/S2: 关注因果、解释、支持
        return {"SAME_AS", "CROSS_BOOK_CONSENSUS",
                "CROSS_CAUSES", "CROSS_CONTRIBUTES_TO", "CROSS_AFFECTS",
                "CROSS_SUPPORTS", "CROSS_SUPPORTED_BY",
                "CROSS_EXPLAINS", "CROSS_EXPLAINED_BY",
                "CROSS_INCREASES_RISK", "CROSS_CONTRADICTS", "CROSS_BOOK_CONFLICTS"}
    elif section_index in (3, 4):
        # S3/S4: 关注治疗、改善、预防、增强
        return {"SAME_AS", "CROSS_BOOK_CONSENSUS", "CROSS_BOOK_COMPLEMENTS",
                "CROSS_TREATS", "CROSS_PREVENTS", "CROSS_ALLEVIATES", "CROSS_ADDRESSES",
                "CROSS_IMPROVES", "CROSS_ENHANCES",
                "CROSS_COMBINES_WITH", "CROSS_EXTENDS", "CROSS_COMPLEMENTS",
                "CROSS_CONTRADICTS", "CROSS_BOOK_CONFLICTS"}
    else:
        # S5: 全部展示
        return all_types


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 2a: Extract passages for a section
# ═══════════════════════════════════════════════════════════════════════════════


def extract_for_section(
    bundle: KnowledgeBundle,
    section_index: int,
    section_query: str = "",
) -> list[Passage]:
    """按节需求从 Bundle 中提取相关 passages。

    Args:
        bundle: 不可变知识产物
        section_index: 节号 1-5
        section_query: 该节的搜索 query（来自 state.section_queries）

    Returns:
        针对该节排序后的 Passage 列表
    """
    all_passages = list(bundle.passages)

    if not all_passages:
        logger.warning(
            "extract_for_section(S%d): bundle.passages 为空，跳过", section_index,
        )
        return []

    # 诊断日志：Bundle 全局概览
    neo4j_entity_counts = {k: len(v) for k, v in bundle.neo4j_entities.items() if v}
    logger.info(
        "extract_for_section(S%d): passages=%d, neo4j_entities=%s, section_query='%s'",
        section_index, len(all_passages), neo4j_entity_counts,
        (section_query or "")[:60],
    )

    if section_index == 1:  # S1: 儿童状态分析
        # 偏好：Neo4j 实体相关 + Behavior/Development 相关 passages
        passages = _retrieve_by_entity_types(
            bundle, ["Problem", "DevelopmentalStage", "RootCause", "Mechanism"],
            top_k=_section_quota(section_index, len(all_passages)),
        )
        # 实体检索不足时，补入关键词检索结果
        if len(passages) < 15:
            kw_passages = _retrieve_by_keywords(
                all_passages, section_query, top_k=20,
            )
            seen = {p.id for p in passages}
            for p in kw_passages:
                if p.id not in seen:
                    passages.append(p)
                    seen.add(p.id)
        return passages

    elif section_index == 2:  # S2: 问题识别
        # 偏好：Neo4j Problem + RootCause 实体相关 passages
        problem_entities = bundle.neo4j_entities.get("Problem", [])
        passages = _retrieve_by_entities(bundle, problem_entities, top_k=20)
        if len(passages) < 12:
            kw_passages = _retrieve_by_keywords(
                all_passages, section_query, top_k=20,
            )
            seen = {p.id for p in passages}
            for p in kw_passages:
                if p.id not in seen:
                    passages.append(p)
                    seen.add(p.id)
        return passages

    elif section_index == 3:  # S3: 运动类型推荐
        # 偏好：Neo4j Exercise + Solution + Strategy 实体相关 passages
        exercise_entities = (
            bundle.neo4j_entities.get("Exercise", [])
            + bundle.neo4j_entities.get("Solution", [])
            + bundle.neo4j_entities.get("Strategy", [])
        )
        logger.info(
            "S3 检索: Exercise=%d, Solution=%d, Strategy=%d, 实体总数=%d",
            len(bundle.neo4j_entities.get("Exercise", [])),
            len(bundle.neo4j_entities.get("Solution", [])),
            len(bundle.neo4j_entities.get("Strategy", [])),
            len(exercise_entities),
        )
        passages = _retrieve_by_entities(bundle, exercise_entities, top_k=25)
        logger.info(
            "S3 实体检索: %d entities → %d passages",
            len(exercise_entities), len(passages),
        )
        if len(passages) < 15:
            before_kw = len(passages)
            kw_passages = _retrieve_by_keywords(
                all_passages, section_query, top_k=25,
            )
            seen = {p.id for p in passages}
            for p in kw_passages:
                if p.id not in seen:
                    passages.append(p)
                    seen.add(p.id)
            logger.info(
                "S3 关键词补入: query='%s', 候选 %d, 去重补入 %d, 合计 %d",
                (section_query or "")[:40],
                len(kw_passages), len(passages) - before_kw, len(passages),
            )
        if not passages:
            logger.warning(
                "S3 检索结果为空! entities=%d, passages总量=%d, "
                "entity_names=%s, query='%s'",
                len(exercise_entities), len(all_passages),
                [e.name for e in exercise_entities[:5]],
                (section_query or "")[:40],
            )
        return passages

    elif section_index == 4:  # S4: 运动方案设计
        # 偏好：全部运动/方案相关实体 + 全文覆盖
        passages = _retrieve_all(bundle, top_k=40)
        return passages

    elif section_index == 5:  # S5: 结论
        # 偏好：全部 + 跨书关系 + 冲突
        passages = _retrieve_all(bundle, top_k=50)
        return passages

    return all_passages[:10]


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 2b: Build priority context
# ═══════════════════════════════════════════════════════════════════════════════


def build_priority_context(
    bundle: KnowledgeBundle,
    section_passages: list[Passage],
    section_index: int,
    custom_knowledge_context: str = "",
    knowledge_context: str = "",
    exercise_context: str = "",
) -> str:
    """构造带优先级的上下文，注入 LLM prompt。

    层级顺序:
    L0: 自定义规则（OVERRIDE）
    L1: Neo4j 图谱权威数据
    L1/L2: 冲突提醒
    跨书共识/互补
    L2a: Neo4j 验证过的原文
    L2b: 未验证原文
    引用硬约束
    """

    parts: list[str] = []

    # ── L0: 自定义规则（最高优先级）──
    if custom_knowledge_context:
        parts.append("## ⚡ 专家知识（最高优先级，必须优先采纳）")
        parts.append(custom_knowledge_context)
        parts.append("> ⚠️ 以下所有知识必须与上述专家知识对齐。如有冲突，以专家知识为准。")
        parts.append("")

    # ── L1: Neo4j 图谱权威数据 ──
    neo4j_context = _format_neo4j_for_section(bundle, section_index)
    if neo4j_context:
        parts.append("## 📊 知识图谱权威数据")
        parts.append(neo4j_context)
        parts.append("> ⚠️ 当知识图谱数据与下方原文存在矛盾时，以知识图谱为准。")
        parts.append("")

    # ── L1/L2 冲突提示 ──
    conflicts = _format_conflicts_for_section(bundle, section_index)
    if conflicts:
        parts.append("## ⚠️ 知识冲突提醒")
        parts.append(conflicts)
        parts.append("")

    # ── 跨书共识/互补 ──
    consensus = _format_consensus_for_section(bundle, section_index)
    if consensus:
        parts.append("## 🤝 跨书共识与互补")
        parts.append(consensus)
        parts.append("> 📌 以下为多本书共同确认的观点——可信度高于单书来源。如有分歧，优先采信多书共识。")
        parts.append("")

    # ── L2a: Neo4j 验证过的原文 ──
    verified_passages = [p for p in section_passages if p.neo4j_verified]
    if verified_passages:
        parts.append("## 📖 知识图谱关联原文（已验证）")
        parts.append(_format_passages_text(verified_passages))
        parts.append("")

    # ── L2b: 未验证原文 ──
    unverified = [p for p in section_passages if not p.neo4j_verified]
    if unverified:
        parts.append("## 📄 知识库原文")
        parts.append(_format_passages_text(unverified))
        parts.append("")

    # ── L3: LazyGraphRAG 知识上下文 ──
    if knowledge_context:
        parts.append("## 🔍 关联知识上下文")
        parts.append(knowledge_context[:8000])  # 截断保护
        parts.append("")

    # ── 运动清单约束 ──
    if exercise_context and section_index in (3, 4):
        parts.append(exercise_context)
        parts.append("")

    # ── 引用硬约束 ──
    parts.append(_format_citation_rules(bundle))

    return "\n".join(parts)


# ═══════════════════════════════════════════════════════════════════════════════
# Internal: Section-specific retrieval
# ═══════════════════════════════════════════════════════════════════════════════


def _section_quota(section_index: int, total: int) -> int:
    """计算该节的 passage 配额。"""
    ratio = SECTION_QUOTAS.get(section_index, 0.20)
    return max(10, int(total * ratio))


def _get_cross_rel_weight(rel_type: str) -> float:
    """获取关系类型的简化权重（用于 passage 排序）。"""
    high = {"CAUSES", "TREATS", "IMPROVES", "ALLEVIATES", "ADDRESSES", "ENHANCES",
            "CROSS_TREATS", "CROSS_IMPROVES", "CROSS_ALLEVIATES", "CROSS_ADDRESSES", "CROSS_ENHANCES"}
    medium = {"PREVENTS", "SUPPORTS", "SUPPORTED_BY", "EXPLAINS", "EXPLAINED_BY",
              "CROSS_PREVENTS", "CROSS_SUPPORTS", "CROSS_CAUSES"}
    if rel_type in high:
        return 0.9
    if rel_type in medium:
        return 0.7
    return 0.5


def _retrieve_by_entity_types(
    bundle: KnowledgeBundle,
    entity_types: list[str],
    top_k: int,
) -> list[Passage]:
    """按实体类型偏好提取 passages，沿关系链扩展搜索词。"""
    preferred_entity_names: set[str] = set()
    for etype in entity_types:
        for entity in bundle.neo4j_entities.get(etype, []):
            preferred_entity_names.add(entity.name.lower())

    # ── 沿关系链扩展 1 跳邻居 ──
    if preferred_entity_names and bundle.neo4j_relations:
        expanded: set[str] = set()
        for rel in bundle.neo4j_relations:
            src = rel.source_entity.lower()
            tgt = rel.target_entity.lower()
            if src in preferred_entity_names and tgt not in preferred_entity_names:
                expanded.add(tgt)
            elif tgt in preferred_entity_names and src not in preferred_entity_names:
                expanded.add(src)
        preferred_entity_names.update(expanded)

    if not preferred_entity_names:
        return []

    scored: list[tuple[Passage, int]] = []
    for p in bundle.passages:
        content_lower = p.content.lower()
        hits = sum(
            1 for name in preferred_entity_names
            if name in content_lower
        )
        if hits > 0:
            scored.append((p, hits))

    scored.sort(key=lambda x: x[1], reverse=True)
    return [p for p, _ in scored[:top_k]]


def _retrieve_by_entities(
    bundle: KnowledgeBundle,
    entities: list[GraphEntity],
    top_k: int,
) -> list[Passage]:
    """按实体列表提取相关 passages，使用加权遍历得分排序。"""
    # ── 构建实体名 → relevance_score 映射 ──
    entity_scores: dict[str, float] = {}
    entity_names: set[str] = set()
    for e in entities:
        if e.name:
            key = e.name.lower()
            entity_names.add(key)
            entity_scores[key] = max(entity_scores.get(key, 0), e.relevance_score or 0.5)
        for alias in getattr(e, "aliases", []):
            if alias:
                entity_names.add(alias.lower())
                entity_scores[alias.lower()] = entity_scores.get(e.name.lower(), 0.5)

    # ── 沿 Neo4j 关系链扩展：找 1 跳邻居实体名 ──
    if entity_names and bundle.neo4j_relations:
        expanded: set[str] = set()
        for rel in bundle.neo4j_relations:
            src = rel.source_entity.lower()
            tgt = rel.target_entity.lower()
            if src in entity_names and tgt not in entity_names:
                expanded.add(tgt)
                # 邻居得分 = 源实体得分 × 关系权重 × 衰减
                w = _get_cross_rel_weight(rel.relation_type)
                entity_scores[tgt] = entity_scores.get(src, 0.5) * w * 0.5
            elif tgt in entity_names and src not in entity_names:
                expanded.add(src)
                w = _get_cross_rel_weight(rel.relation_type)
                entity_scores[src] = entity_scores.get(tgt, 0.5) * w * 0.5
        entity_names.update(expanded)

    if not entity_names:
        return []

    # ── 跨书关系实体集合（所有类型都参与 boost，包括冲突）──
    cross_book_names: set[str] = set()
    for c in bundle.cross_book_consensus:
        cross_book_names.add(c.entity_name.lower())
    for c in bundle.cross_book_conflicts:
        cross_book_names.add(c.entity_name.lower())

    # ── 加权 passage 评分 ──
    scored: list[tuple[Passage, float]] = []
    for p in bundle.passages:
        content_lower = p.content.lower()
        # 加权命中分：命中高 relevance_score 的实体得分更高
        hits = sum(entity_scores.get(name, 0.5) for name in entity_names if name in content_lower)
        if hits > 0:
            # 跨书关系 boost：有跨书关系的实体命中额外加分（上限 3）
            if cross_book_names:
                cross_hits = sum(1 for n in cross_book_names if n in content_lower)
                if cross_hits > 0:
                    hits += min(cross_hits, 3)
            scored.append((p, hits))

    scored.sort(key=lambda x: x[1], reverse=True)
    return [p for p, _ in scored[:top_k]]


def _retrieve_by_keywords(
    passages: list[Passage],
    query: str,
    top_k: int,
) -> list[Passage]:
    """按关键词匹配提取 passages（纯文本分词匹配）。"""
    if not query:
        return passages[:top_k]

    keywords = [w.strip().lower() for w in query.split() if len(w.strip()) >= 2]

    if not keywords:
        return passages[:top_k]

    scored: list[tuple[Passage, int]] = []
    for p in passages:
        content_lower = p.content.lower()
        hits = sum(1 for kw in keywords if kw in content_lower)
        if hits > 0:
            scored.append((p, hits))

    scored.sort(key=lambda x: (x[1], x[0].score), reverse=True)
    return [p for p, _ in scored[:top_k]]


def _retrieve_all(bundle: KnowledgeBundle, top_k: int) -> list[Passage]:
    """返回优先级排序后的全部 passages。"""
    # neo4j_verified 优先，然后按 score
    sorted_passages = sorted(
        bundle.passages,
        key=lambda p: (p.neo4j_verified, p.score), reverse=True,
    )
    return sorted_passages[:top_k]


# ═══════════════════════════════════════════════════════════════════════════════
# Internal: Context formatting
# ═══════════════════════════════════════════════════════════════════════════════


def _format_neo4j_for_section(
    bundle: KnowledgeBundle,
    section_index: int,
) -> str:
    """格式化 Neo4j 知识为 prompt 文本。"""
    lines: list[str] = []

    # S1/S2: 关注 Problem, RootCause, Mechanism, DevelopmentalStage
    if section_index in (1, 2):
        focus_types = ["Problem", "RootCause", "Mechanism", "DevelopmentalStage"]
        for etype in focus_types:
            entities = bundle.neo4j_entities.get(etype, [])
            if entities:
                lines.append(f"### {etype} 实体")
                for e in entities[:8]:
                    line = f"- {e.name}"
                    if e.description:
                        line += f": {e.description[:120]}"
                    if e.book_title:
                        line += f"（来源: 《{e.book_title}》）"
                    lines.append(line)

    # S3: 关注 Exercise, Solution, Strategy
    elif section_index == 3:
        focus_types = ["Exercise", "Solution", "Strategy"]
        for etype in focus_types:
            entities = bundle.neo4j_entities.get(etype, [])
            if entities:
                lines.append(f"### {etype} 实体")
                for e in entities[:10]:
                    line = f"- {e.name}"
                    if e.description:
                        line += f": {e.description[:150]}"
                    if e.book_title:
                        line += f"（来源: 《{e.book_title}》）"
                    lines.append(line)

    # S4: 全部实体
    elif section_index == 4:
        for etype, entities in bundle.neo4j_entities.items():
            if entities:
                lines.append(f"### {etype} ({len(entities)} 个)")
                for e in entities[:6]:
                    line = f"- {e.name}"
                    if e.description:
                        line += f": {e.description[:100]}"
                    lines.append(line)

    # S5: 全局视图 + 关系
    elif section_index == 5:
        # 跨书关系摘要
        if bundle.cross_book_consensus:
            lines.append("### 跨书共识")
            for cc in bundle.cross_book_consensus[:8]:
                books_str = "、".join(f"《{b}》" for b in cc.books)
                label = _CROSS_RELATION_LABELS.get(cc.relation_type, cc.relation_type)
                desc = f" — {cc.description[:100]}" if cc.description else ""
                lines.append(f"- {cc.entity_name} ({label}){desc} ({books_str})")
        if bundle.cross_book_conflicts:
            lines.append("### 跨书冲突")
            for cc2 in bundle.cross_book_conflicts[:5]:
                books_str = " vs ".join(f"《{b}》" for b in cc2.books)
                lines.append(f"- {cc2.entity_name}: {books_str}")

    return "\n".join(lines) if lines else ""


def _format_conflicts_for_section(
    bundle: KnowledgeBundle,
    section_index: int,
) -> str:
    """格式化 L1/L2 优先级冲突。"""
    if not bundle.priority_conflicts:
        return ""

    lines = ["以下实体在图谱（L1）与原文（L2）之间存在矛盾："]
    for pc in bundle.priority_conflicts[:5]:
        lines.append(f"- **{pc.entity_name}**: L1={pc.l1_position[:100]} | L2={pc.l2_position[:100]}")
    return "\n".join(lines)


def _format_consensus_for_section(
    bundle: KnowledgeBundle,
    section_index: int,
) -> str:
    """为指定节格式化跨书关系数据（全类型覆盖）。

    渲染策略：
    1. 按节过滤相关关系类型（S1/S2 偏因果解释，S3/S4 偏治疗改善，S5 全部）
    2. 同一实体只保留 1 条（去重）
    3. entity_name 长度 < 2 的跳过（噪声实体）
    """
    if not bundle.cross_book_consensus:
        return ""

    relevant_types = _get_relevant_cross_types(section_index)
    lines: list[str] = []
    seen_entities: set[str] = set()

    for c in bundle.cross_book_consensus:
        if len(c.entity_name) < 2 or c.entity_name in seen_entities:
            continue
        if c.relation_type not in relevant_types:
            continue

        label = _CROSS_RELATION_LABELS.get(c.relation_type, c.relation_type)
        books_str = "、".join(f"《{b}》" for b in c.books)

        if c.description:
            lines.append(f"- 「{c.entity_name}」({label})：{books_str} — {c.description[:150]}")
        else:
            lines.append(f"- 「{c.entity_name}」({label})：{books_str}")
        seen_entities.add(c.entity_name)

    return "\n".join(lines) if lines else ""


def _format_passages_text(passages: list[Passage]) -> str:
    """格式化 Passage 列表为 LLM 可读文本。"""
    if not passages:
        return ""

    lines: list[str] = []
    current_book = ""

    for p in passages:
        # 书籍头
        if p.book_title != current_book:
            current_book = p.book_title
            lines.append(f"\n### 📖 {current_book}")

        source_tag = ""
        if p.source == "neo4j_source":
            source_tag = " [图谱关联]"
        elif p.neo4j_verified:
            source_tag = " [图谱验证]"

        lines.append(
            f"> **{p.chapter_title}**{source_tag}\n"
            f"> {p.content[:500]}\n"
        )

    return "\n".join(lines)


def _format_citation_rules(bundle: KnowledgeBundle) -> str:
    """构造引用硬约束规则。"""
    book_list = "、".join(
        f"《{meta.title}》" for meta in bundle.book_index.values()
    )
    return f"""## 🔒 引用规则（必须严格遵守）

合法书名（仅限以下 {len(bundle.book_index)} 本）：
{book_list}

每条 citation 必须：
1. book_title: 必须精确使用上方的书名（包括《》符号）
2. chapter: 必须来自下方原文中的章节名
3. excerpt: 必须从下方原文中逐字复制（≥10 字符）
4. 禁止编造书名、禁止编造章节名、禁止概括 excerpt
5. 如果某条 citation 无法在上方原文中找到依据，不要生成该条引用"""


# ═══════════════════════════════════════════════════════════════════════════════
# Bundle-aware section node runner
# ═══════════════════════════════════════════════════════════════════════════════


async def run_section_from_bundle(
    state: Any,
    bundle: KnowledgeBundle,
    section_index: int,
    section_label: str,
    prompt_key: str,
    response_format: Any,
    build_user_message_fn,
    step_label: str,
) -> dict[str, Any]:
    """从 Bundle 消费知识的通用节生成节点。

    替代 _run_section_node 中的搜索+格式化逻辑。
    Section 节点不再调用 _direct_search。

    Args:
        state: KnowledgeQAState
        bundle: 不可变知识产物
        section_index: 节号 1-5
        section_label: 节标题（中文）
        prompt_key: prompt 模板 key
        response_format: Pydantic 模型
        build_user_message_fn: (state, prompt) → user_message 的回调
        step_label: 步骤标识

    Returns:
        {"sections": {...}, "current_step": [...]}
    """
    import asyncio
    import json

    from src.core.knowledge_qa.nodes.base import (
        _build_empty_search_fallback,
        _get_model_name,
        _get_prompt_pair,
        _get_temperature,
        get_timeout,
    )
    from src.schemas.knowledge_qa import SectionOutput, push_progress

    await push_progress(
        f"section_{section_index}_generating",
        f"正在生成第 {section_index} 节：{section_label}…（Bundle 模式）",
    )

    try:
        # 取消信号检查
        from src.schemas.knowledge_qa import get_progress_context
        ctx = get_progress_context()
        if ctx and ctx.get("cancellation_event") and ctx["cancellation_event"].is_set():
            raise asyncio.CancelledError("任务已被取消")

        # ── 从 Bundle 提取本节 passages ──
        section_query = getattr(state, "section_queries", {}).get(
            section_index, state.question,
        )
        section_passages = extract_for_section(bundle, section_index, section_query)

        # ── 空检查 ──
        if not section_passages:
            logger.warning(
                "第%d节 Bundle passages 为空，降级为空节", section_index,
            )
            return await _build_empty_search_fallback(state, section_index, section_label)

        # ── 构建优先级上下文 ──
        from src.core.llm.factory import LLMServiceFactoryCompat

        context = build_priority_context(
            bundle=bundle,
            section_passages=section_passages,
            section_index=section_index,
            custom_knowledge_context=getattr(state, "custom_knowledge_context", "") or "",
            knowledge_context=getattr(state, "knowledge_context", "") or "",
            exercise_context=getattr(state, "exercise_context", "")
            if section_index in (3, 4) else "",
        )

        # ── LLM 调用 ──
        prompt = await _get_prompt_pair(prompt_key)
        user_message = build_user_message_fn(state, prompt)
        full_message = f"{user_message}\n\n{context}"

        temperature = await _get_temperature(step_label)
        model = LLMServiceFactoryCompat.create_raw(
            model_name=await _get_model_name(step_label),
            temperature=temperature,
        )
        structured_model = model.with_structured_output(response_format)

        timeout = get_timeout(step_label)
        response = await asyncio.wait_for(
            structured_model.ainvoke([
                {"role": "system", "content": prompt["system"]},
                {"role": "user", "content": full_message},
            ]),
            timeout=timeout,
        )

        # ── 提取数据 ──
        data = response.model_dump() if hasattr(response, "model_dump") else response
        if isinstance(data, str):
            try:
                from json_repair import repair_json
                data = json.loads(repair_json(data))
            except Exception:
                data = {
                    "title": section_label, "content": data,
                    "citations": [], "structured_data": {},
                }

        # ── 引用白名单预校验 ──
        citations = data.get("citations", [])
        if citations:
            citations = _prefilter_citations(citations, bundle.book_index)

        section = SectionOutput(
            index=section_index,
            title=data.get("title", section_label),
            content=data.get("content", ""),
            citations=citations,
            structured_data=data.get("structured_data", {}),
        )

        await push_progress(
            f"section_{section_index}_done",
            f"第 {section_index} 节：{section_label}已完成（Bundle）",
            section=section.model_dump(),
        )

        sections = dict(state.sections)
        sections[section_index] = section
        logger.info(
            "第%d节 Bundle 模式生成完成: %d citations",
            section_index, len(citations),
        )
        return {
            "sections": sections,
            "current_step": [f"section_{section_index}_done"],
        }

    except asyncio.TimeoutError:
        logger.warning("第%d节生成超时 (%ds)", section_index, get_timeout(step_label))
        from src.core.knowledge_qa.nodes.base import _section_fallback
        return await _section_fallback(state, section_index, section_label, "生成超时")
    except Exception as e:
        logger.exception("第%d节生成失败 (Bundle)", section_index)
        from src.core.knowledge_qa.nodes.base import _section_fallback
        return await _section_fallback(state, section_index, section_label, str(e))


def _prefilter_citations(
    citations: list[dict],
    book_index: dict[str, BookMeta],
) -> list[dict]:
    """引用白名单预校验——剔除 book_title 不在白名单中的引用。"""
    valid_titles = {meta.normalized_title for meta in book_index.values()}
    valid_titles.update(meta.title for meta in book_index.values())
    valid_titles.update(f"《{meta.title}》" for meta in book_index.values())

    filtered: list[dict] = []
    for c in citations:
        bt = c.get("book_title", "")
        norm = normalize_book_title(bt)
        if norm in valid_titles or bt in valid_titles or f"《{norm}》" in valid_titles:
            filtered.append(c)
        else:
            logger.info("预过滤剔除 citation: book_title='%s' 不在白名单", bt)

    if len(filtered) < len(citations):
        logger.info(
            "引用白名单预校验: %d→%d 条通过",
            len(citations), len(filtered),
        )

    return filtered
