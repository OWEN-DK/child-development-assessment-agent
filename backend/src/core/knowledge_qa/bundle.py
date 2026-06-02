"""KnowledgeBundle 数据模型 — 一次检索的完整知识产物，不可变。

设计原则:
- 检索与生成解耦——检索一次产出不可变 Bundle，后续 LLM 节点只消费不搜索
- 三层优先级: L0 自定义规则 > L1 Neo4j 图谱 > L2 原文证据
- frozen=True 强制不可变——构建后任何修改触发 FrozenInstanceError

放置位置: backend/src/core/knowledge_qa/bundle.py
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


# ═══════════════════════════════════════════════════════════════════════════════
# Core Bundle
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class KnowledgeBundle:
    """一次检索的完整知识产物，不可变。

    构建后任何字段赋值都会触发 FrozenInstanceError。
    子对象（Passage 等）在加入 Bundle 前完成构造，之后不再修改引用。
    """

    # ── 元数据 ──
    question: str
    matched_book_ids: list[str]
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # ── Layer 0: 自定义规则（最高优先级）──
    custom_rules: list[CustomRuleMatch] = field(default_factory=list)

    # ── Layer 1: Neo4j 图谱（权威源）──
    neo4j_entities: dict[str, list[GraphEntity]] = field(default_factory=dict)
    # key: entity_type (e.g. "Problem", "Solution", "Exercise")
    neo4j_relations: list[GraphRelation] = field(default_factory=list)
    cross_book_conflicts: list[CrossBookConflict] = field(default_factory=list)
    cross_book_consensus: list[CrossBookConsensus] = field(default_factory=list)

    # ── Layer 2: 原文证据 ──
    passages: list[Passage] = field(default_factory=list)

    # ── 白名单索引（硬约束）──
    book_index: dict[str, BookMeta] = field(default_factory=dict)
    # "跑步改造大脑" → BookMeta(title, chapters, entity_count)
    passage_index: dict[str, Passage] = field(default_factory=dict)
    # passage_id → Passage（O(1) lookup）

    # ── 冲突标记 ──
    priority_conflicts: list[PriorityConflict] = field(default_factory=list)

    # ── 质量元数据 ──
    retrieval_stats: RetrievalStats = field(default_factory=lambda: RetrievalStats())


# ═══════════════════════════════════════════════════════════════════════════════
# Layer 1: Neo4j Types
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class GraphEntity:
    """Neo4j 中的实体。"""

    name: str
    entity_type: str
    description: str = ""
    book_id: str = ""
    book_title: str = ""
    source_chapter: str = ""
    source_para_ids: list[str] = field(default_factory=list)
    relations: list[str] = field(default_factory=list)  # 相邻实体名
    aliases: list[str] = field(default_factory=list)  # 跨书合并实体的别名列表


@dataclass(frozen=True)
class GraphRelation:
    """Neo4j 中的关系。"""

    source_entity: str
    target_entity: str
    relation_type: str  # CAUSES, TREATS, CROSS_TREATS, SAME_AS, …
    source_book: str = ""
    target_book: str = ""
    evidence: str = ""
    is_cross_book: bool = False


@dataclass(frozen=True)
class CrossBookConflict:
    """跨书矛盾。"""

    entity_name: str
    books: list[str]  # 涉及的书
    positions: list[str]  # 各自立场
    neo4j_relation_type: str = "CROSS_BOOK_CONFLICTS"


@dataclass(frozen=True)
class CrossBookConsensus:
    """跨书共识/互补。

    SAME_AS → 两书对同一实体观点一致
    CROSS_BOOK_COMPLEMENTS → 一书补充另一书的视角
    CROSS_TREATS → 跨书治疗方案关系
    """

    entity_name: str
    books: list[str]
    relation_type: str  # SAME_AS | CROSS_BOOK_COMPLEMENTS | CROSS_TREATS
    description: str = ""


# ═══════════════════════════════════════════════════════════════════════════════
# Layer 2: Evidence Types
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class Passage:
    """原文段落。"""

    id: str  # chunk_id
    book_id: str
    book_title: str  # 规范化后的书名
    chapter_title: str
    content: str  # 完整原文，不截断
    score: float
    source: str  # "chroma" | "neo4j_source" | "lazy_graph_rag"
    neo4j_verified: bool = False  # 是否被 Neo4j 实体关联

    def __hash__(self) -> int:
        return hash(self.id)


@dataclass(frozen=True)
class BookMeta:
    """书籍元数据（白名单用）。"""

    book_id: str
    title: str
    normalized_title: str  # 去扩展名 + trim
    chapter_list: list[str] = field(default_factory=list)
    entity_count: int = 0


@dataclass(frozen=True)
class PriorityConflict:
    """优先级冲突——L1 与 L2 矛盾之处。"""

    entity_name: str
    l1_position: str  # Neo4j 说法
    l2_position: str  # Chroma 原文说法
    l2_passage_id: str = ""


# ═══════════════════════════════════════════════════════════════════════════════
# Layer 0: Custom Rule Types
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class CustomRuleMatch:
    """自定义规则命中。"""

    rule_id: str
    title: str
    content: str
    match_channel: str  # "keyword" | "regex" | "semantic"
    priority: int = 0
    associated_entities: list[str] = field(default_factory=list)
    # OVERRIDES / ENHANCES / RELATES_TO 指向的 Neo4j 实体名


# ═══════════════════════════════════════════════════════════════════════════════
# Quality Metadata
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class RetrievalStats:
    """检索质量统计。"""

    neo4j_entity_count: int = 0
    neo4j_relation_count: int = 0
    chroma_passage_count: int = 0
    lazy_graph_hit_count: int = 0
    total_passage_chars: int = 0
    retrieval_duration_ms: int = 0
    pruned_book_ids: list[str] = field(default_factory=list)
    seed_source: str = ""  # "question_embedding" | "s2_problems"


# ═══════════════════════════════════════════════════════════════════════════════
# Citation verification types
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class CitationVerdict:
    """单条引用校验结果。"""

    passed: bool
    reason: str = "ok"
    corrected_book_title: str = ""
    source_passage_id: str = ""
    neo4j_verified_entities: list[str] = field(default_factory=list)
    fuzzy_matched: bool = False
    semantic_mismatch: bool = False

    @property
    def trust_level(self) -> str:
        """校验信任层级标记。

        Returns:
            "verified" — 五层全通过
            "semantic_questionable" — L1-L4 通过，L5 语义存疑
            "text_verified" — L1-L3 通过，L4 图谱未验证
            "corrected" — book_title 被模糊修正
            "failed" — L1-L3 任一失败
        """
        if not self.passed:
            return "failed"
        if self.semantic_mismatch:
            return "semantic_questionable"
        if self.corrected_book_title:
            return "corrected"
        if self.neo4j_verified_entities:
            return "verified"
        return "text_verified"


# ═══════════════════════════════════════════════════════════════════════════════
# Book title normalization (shared utility)
# ═══════════════════════════════════════════════════════════════════════════════


def normalize_book_title(raw: str) -> str:
    """规范化书名：去文件扩展名 + trim。

    "运动改变大脑 .epub" → "运动改变大脑"
    "学习如何学习.epub" → "学习如何学习"
    """
    if not raw:
        return "未知"
    name = raw.strip()
    for ext in (".epub", ".pdf", ".txt", ".md", ".docx", ".html", ".mobi"):
        if name.lower().endswith(ext):
            name = name[: -len(ext)]
            break
    return name.strip()
