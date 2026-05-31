"""Phase 2 核心: 内存主图（NetworkX 封装）。

放置位置: backend/src/core/knowledge_qa/d2g/master_graph.py
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

import networkx as nx

from .models import (
    ChapterExtraction,
    ExtractedEntity,
    ExtractedRelationship,
    GraphQualityMetrics,
    QualityThresholds,
)

logger = logging.getLogger(__name__)


@dataclass
class MasterGraph:
    """内存中的主图。所有章节审核通过后合入此图。"""

    book_id: str
    book_title: str
    graph: nx.DiGraph = field(default_factory=nx.DiGraph)

    # 段落覆盖追踪
    chapter_para_count: dict[str, int] = field(default_factory=dict)
    para_coverage: dict[str, set[int]] = field(default_factory=dict)

    # 章节实体索引
    chapter_entities: dict[str, list[str]] = field(default_factory=dict)

    # ──────────────────────────────────────────────────────
    # 实体操作
    # ──────────────────────────────────────────────────────

    def add_entity(
        self,
        entity: ExtractedEntity | dict,
        chapter_id: str,
    ) -> None:
        """添加实体到主图。"""
        if isinstance(entity, ExtractedEntity):
            name = entity.name
            etype = entity.entity_type
            desc = entity.description
            para_ids = entity.source_para_ids
        else:
            name = entity["name"]
            etype = entity.get("entity_type", "AutoEntity")
            desc = entity.get("description", "")
            para_ids = entity.get("source_para_ids", [])

        if name in self.graph.nodes:
            # 已存在：追加来源
            self.graph.nodes[name]["source_chapters"] = list(
                set(self.graph.nodes[name].get("source_chapters", [])) | {chapter_id}
            )
            # 合并 para_ids
            existing_pids = self.graph.nodes[name].get("source_para_ids", {})
            if chapter_id not in existing_pids:
                existing_pids[chapter_id] = []
            existing_pids[chapter_id] = sorted(set(existing_pids[chapter_id]) | set(para_ids))
            self.graph.nodes[name]["source_para_ids"] = existing_pids
            # 保留更长的描述
            if len(desc) > len(self.graph.nodes[name].get("description", "")):
                self.graph.nodes[name]["description"] = desc
        else:
            self.graph.add_node(
                name,
                entity_type=etype,
                description=desc,
                source_chapters=[chapter_id],
                source_para_ids={chapter_id: para_ids},
            )

        # 追踪章节实体
        if chapter_id not in self.chapter_entities:
            self.chapter_entities[chapter_id] = []
        if name not in self.chapter_entities[chapter_id]:
            self.chapter_entities[chapter_id].append(name)

        # 追踪段落覆盖
        for pid in para_ids:
            if chapter_id not in self.para_coverage:
                self.para_coverage[chapter_id] = set()
            self.para_coverage[chapter_id].add(pid)

    def merge_entity(self, canonical: str, alias: str) -> None:
        """将 alias 实体合并到 canonical 实体。"""
        if alias not in self.graph.nodes or canonical not in self.graph.nodes:
            logger.warning("合并失败: %s 或 %s 不在图中", canonical, alias)
            return

        alias_data = self.graph.nodes[alias]
        canonical_data = self.graph.nodes[canonical]

        # 合并描述（保留更长的）
        if len(alias_data.get("description", "")) > len(canonical_data.get("description", "")):
            canonical_data["description"] = alias_data["description"]

        # 合并来源章节
        canonical_data["source_chapters"] = list(
            set(canonical_data.get("source_chapters", []))
            | set(alias_data.get("source_chapters", []))
        )

        # 合并段落覆盖
        for ch_id, pids in alias_data.get("source_para_ids", {}).items():
            if ch_id not in canonical_data.get("source_para_ids", {}):
                canonical_data.setdefault("source_para_ids", {})[ch_id] = []
            canonical_data["source_para_ids"][ch_id] = sorted(
                set(canonical_data["source_para_ids"][ch_id]) | set(pids)
            )

        # 迁移边
        for pred in list(self.graph.predecessors(alias)):
            data = self.graph[pred][alias]
            if not self.graph.has_edge(pred, canonical):
                self.graph.add_edge(pred, canonical, **data)
        for succ in list(self.graph.successors(alias)):
            data = self.graph[alias][succ]
            if not self.graph.has_edge(canonical, succ):
                self.graph.add_edge(canonical, succ, **data)

        # 删除 alias
        self.graph.remove_node(alias)

        # 更新章节实体索引
        for ch_id, ents in self.chapter_entities.items():
            if alias in ents:
                ents.remove(alias)
                if canonical not in ents:
                    ents.append(canonical)

        logger.info("实体合并: '%s' → '%s'", alias, canonical)

    # ──────────────────────────────────────────────────────
    # 关系操作
    # ──────────────────────────────────────────────────────

    def add_relationship(
        self,
        rel: ExtractedRelationship | dict,
        chapter_id: str,
    ) -> None:
        """添加关系到主图。"""
        if isinstance(rel, ExtractedRelationship):
            src, tgt = rel.source, rel.target
            rtype = str(rel.relation_type)
            evidence = rel.evidence
            para_ids = rel.source_para_ids
            rel_source = rel.relation_source
            confidence = rel.confidence
        else:
            src = rel["source"]
            tgt = rel["target"]
            rtype = rel.get("relation_type", "RELATES_TO")
            evidence = rel.get("evidence", "")
            para_ids = rel.get("source_para_ids", [])
            rel_source = rel.get("relation_source", "unknown")
            confidence = rel.get("confidence", 1.0)

        # 确保节点存在
        if src not in self.graph.nodes:
            self.graph.add_node(src, entity_type="AutoEntity", description="", source_chapters=[], source_para_ids={})
        if tgt not in self.graph.nodes:
            self.graph.add_node(tgt, entity_type="AutoEntity", description="", source_chapters=[], source_para_ids={})

        if self.graph.has_edge(src, tgt):
            # 边已存在：保留更长的 evidence，保留较高置信度
            edge_data = self.graph[src][tgt]
            if len(evidence) > len(edge_data.get("evidence", "")):
                edge_data["evidence"] = evidence
            edge_data["source_chapters"] = list(
                set(edge_data.get("source_chapters", [])) | {chapter_id}
            )
            # 保留较高置信度和来源
            if confidence > edge_data.get("confidence", 0):
                edge_data["confidence"] = confidence
                edge_data["relation_source"] = rel_source
        else:
            self.graph.add_edge(
                src, tgt,
                relation_type=rtype,
                evidence=evidence,
                source_chapters=[chapter_id],
                relation_source=rel_source,
                confidence=confidence,
            )

        # 追踪段落覆盖
        for pid in para_ids:
            if chapter_id not in self.para_coverage:
                self.para_coverage[chapter_id] = set()
            self.para_coverage[chapter_id].add(pid)

    # ──────────────────────────────────────────────────────
    # 章节级操作
    # ──────────────────────────────────────────────────────

    def ingest_chapter(self, extraction: ChapterExtraction, para_count: int) -> None:
        """将一章的提取结果合入主图。"""
        ch_id = extraction.chapter_id
        self.chapter_para_count[ch_id] = para_count

        for entity in extraction.entities:
            self.add_entity(entity, ch_id)

        for rel in extraction.relationships:
            self.add_relationship(rel, ch_id)

    # ──────────────────────────────────────────────────────
    # 质量指标
    # ──────────────────────────────────────────────────────

    def get_quality_metrics(
        self,
        thresholds: QualityThresholds | None = None,
        skip_chapters: set[str] | None = None,
    ) -> GraphQualityMetrics:
        """计算图质量指标。

        Args:
            thresholds: 质量阈值（未使用，保留接口兼容）
            skip_chapters: 需要排除的章节 ID 集合（如目录、前言等非内容章节）
        """
        skip = skip_chapters or set()
        G = self.graph
        total = G.number_of_nodes()
        edges = G.number_of_edges()

        orphans = sum(1 for n in G.nodes if G.degree(n) == 0)

        undirected = G.to_undirected()
        components = list(nx.connected_components(undirected)) if total > 0 else []
        largest = max(len(c) for c in components) if components else 0

        # 章节覆盖率
        chapter_coverage = {}
        for ch_id, covered in self.para_coverage.items():
            if ch_id in skip:
                continue
            total_paras = self.chapter_para_count.get(ch_id, 1)
            chapter_coverage[ch_id] = len(covered) / total_paras * 100

        # 全书段落覆盖率（排除非内容章节）
        total_paras_all = sum(
            v for k, v in self.chapter_para_count.items() if k not in skip
        )
        covered_paras_all = sum(
            len(v) for k, v in self.para_coverage.items() if k not in skip
        )
        overall = covered_paras_all / total_paras_all * 100 if total_paras_all > 0 else 0

        return GraphQualityMetrics(
            total_entities=total,
            total_relationships=edges,
            orphan_entities=orphans,
            orphan_rate=orphans / total if total > 0 else 0,
            avg_degree=2 * edges / total if total > 0 else 0,
            connected_components=len(components),
            largest_component_ratio=largest / total if total > 0 else 0,
            chapter_coverage=chapter_coverage,
            overall_para_coverage=overall,
        )

    # ──────────────────────────────────────────────────────
    # 持久化（Redis）
    # ──────────────────────────────────────────────────────

    def to_json(self) -> str:
        """序列化为 JSON。"""
        data = nx.node_link_data(self.graph)
        return json.dumps(data, ensure_ascii=False)

    @classmethod
    def from_json(cls, book_id: str, book_title: str, json_str: str) -> MasterGraph:
        """从 JSON 反序列化。"""
        data = json.loads(json_str)
        graph = nx.node_link_graph(data)
        master = cls(book_id=book_id, book_title=book_title, graph=graph)
        # 重建索引
        for node in graph.nodes:
            for ch_id in graph.nodes[node].get("source_chapters", []):
                if ch_id not in master.chapter_entities:
                    master.chapter_entities[ch_id] = []
                master.chapter_entities[ch_id].append(node)
        return master
