"""测试全局批量消歧（UnionFind + batch_resolve_entities）。"""

import pytest
from unittest.mock import AsyncMock

from src.core.knowledge_qa.d2g.entity_resolver import (
    UnionFind,
    batch_resolve_entities,
    _cosine,
    _ingest_to_graph,
)
from src.core.knowledge_qa.d2g.master_graph import MasterGraph
from src.core.knowledge_qa.d2g.models import (
    ChapterExtraction,
    EntityMatchJudgment,
    ExtractedEntity,
    ExtractedRelationship,
)


# ──────────────────────────────────────────────────────────────
# UnionFind
# ──────────────────────────────────────────────────────────────


class TestUnionFind:
    def test_basic_union(self):
        uf = UnionFind()
        uf.make("A")
        uf.make("B")
        uf.make("C")
        uf.union("A", "B")
        assert uf.find("A") == uf.find("B")
        assert uf.find("A") != uf.find("C")

    def test_transitive_union(self):
        uf = UnionFind()
        for x in ["A", "B", "C", "D"]:
            uf.make(x)
        uf.union("A", "B")
        uf.union("B", "C")
        assert uf.find("A") == uf.find("C")
        assert uf.find("A") != uf.find("D")

    def test_clusters(self):
        uf = UnionFind()
        for x in ["运动", "体育锻炼", "体能训练", "前额叶", "注意力"]:
            uf.make(x)
        uf.union("运动", "体育锻炼")
        uf.union("运动", "体能训练")
        clusters = uf.clusters()
        roots = {uf.find("运动"), uf.find("体育锻炼"), uf.find("体能训练")}
        assert len(roots) == 1
        assert uf.find("前额叶") != uf.find("运动")

    def test_union_same_element(self):
        uf = UnionFind()
        uf.make("A")
        uf.union("A", "A")
        assert uf.find("A") == "A"

    def test_empty(self):
        uf = UnionFind()
        assert uf.clusters() == {}


# ──────────────────────────────────────────────────────────────
# _cosine
# ──────────────────────────────────────────────────────────────


class TestCosine:
    def test_identical(self):
        assert abs(_cosine([1, 0, 0], [1, 0, 0]) - 1.0) < 1e-6

    def test_orthogonal(self):
        assert abs(_cosine([1, 0], [0, 1])) < 1e-6

    def test_opposite(self):
        assert abs(_cosine([1, 0], [-1, 0]) - (-1.0)) < 1e-6

    def test_zero_vector(self):
        assert _cosine([0, 0], [1, 2]) == 0.0


# ──────────────────────────────────────────────────────────────
# _ingest_to_graph
# ──────────────────────────────────────────────────────────────


class TestIngestToGraph:
    def test_no_merge(self):
        master = MasterGraph(book_id="test", book_title="Test")
        ext = ChapterExtraction(
            chapter_id="ch01", chapter_title="Ch1",
            entities=[
                ExtractedEntity(
                    name="运动", entity_type="Exercise",
                    description="身体活动", source_para_ids=[1, 2],
                ),
            ],
            relationships=[],
        )
        _ingest_to_graph({"ch01": ext}, master, {})
        assert "运动" in master.graph.nodes
        assert master.chapter_para_count["ch01"] == 2

    def test_with_merge(self):
        master = MasterGraph(book_id="test", book_title="Test")
        ext1 = ChapterExtraction(
            chapter_id="ch01", chapter_title="Ch1",
            entities=[
                ExtractedEntity(name="运动", entity_type="Exercise",
                                description="身体活动", source_para_ids=[1]),
            ],
            relationships=[],
        )
        ext2 = ChapterExtraction(
            chapter_id="ch02", chapter_title="Ch2",
            entities=[
                ExtractedEntity(name="体育锻炼", entity_type="Exercise",
                                description="有计划的运动", source_para_ids=[3]),
            ],
            relationships=[
                ExtractedRelationship(
                    source="体育锻炼", target="认知功能",
                    relation_type="THERAPEUTIC_IMPROVES",
                    evidence="证据", source_para_ids=[3]),
            ],
        )
        merge_map = {"体育锻炼": "运动", "运动": "运动"}
        _ingest_to_graph({"ch01": ext1, "ch02": ext2}, master, merge_map)
        assert "运动" in master.graph.nodes
        assert "体育锻炼" not in master.graph.nodes
        assert master.graph.has_edge("运动", "认知功能")

    def test_chapter_para_count_set(self):
        master = MasterGraph(book_id="test", book_title="Test")
        ext = ChapterExtraction(
            chapter_id="ch01", chapter_title="Ch1",
            entities=[
                ExtractedEntity(name="A", entity_type="Problem",
                                description="desc", source_para_ids=[1, 5, 10]),
            ],
            relationships=[],
        )
        _ingest_to_graph({"ch01": ext}, master, {})
        assert master.chapter_para_count["ch01"] == 10


# ──────────────────────────────────────────────────────────────
# batch_resolve_entities
# ──────────────────────────────────────────────────────────────


def _make_type_emb(entity_type: str) -> list[float]:
    """同类型实体共享基础向量，加小扰动。"""
    import hashlib
    h = int(hashlib.md5(entity_type.encode()).hexdigest()[:8], 16) % 1000
    dim = 16
    base = [0.0] * dim
    base[h % dim] = 1.0
    return base


def _make_entity_emb(name: str, entity_type: str) -> list[float]:
    """同类型实体的 embedding 相似（共享 base + 小扰动）。"""
    base = _make_type_emb(entity_type)
    import hashlib
    h = int(hashlib.md5(name.encode()).hexdigest()[:8], 16) % 1000
    # 在 base 基础上加小扰动（保持高相似度）
    perturbed = [v * 0.8 for v in base]
    perturbed[h % len(base)] += 0.2
    return perturbed


class TestBatchResolveEntities:
    @pytest.fixture
    def mock_embedding_client(self):
        """同类型实体的 embedding 相似度高（≥ 0.9）。"""
        client = AsyncMock()

        async def embed(texts):
            return [_make_entity_emb(t, "Exercise") for t in texts]

        client.embed = AsyncMock(side_effect=embed)
        return client

    @pytest.fixture
    def mock_llm_same(self):
        """LLM 总是判定 same=True。"""
        client = AsyncMock()

        async def gen(prompt, schema, model):
            return EntityMatchJudgment(same=True, reason="测试合并")

        client.generate_structured = AsyncMock(side_effect=gen)
        return client

    @pytest.fixture
    def mock_llm_different(self):
        """LLM 总是判定 same=False。"""
        client = AsyncMock()

        async def gen(prompt, schema, model):
            return EntityMatchJudgment(same=False, reason="不同实体")

        client.generate_structured = AsyncMock(side_effect=gen)
        return client

    @pytest.mark.asyncio
    async def test_no_entities(self, mock_embedding_client, mock_llm_same):
        master = MasterGraph(book_id="t", book_title="T")
        merge_map, merge_log = await batch_resolve_entities(
            {}, master, mock_embedding_client, mock_llm_same,
        )
        assert merge_map == {}
        assert merge_log == []

    @pytest.mark.asyncio
    async def test_no_merge_different_entities(self, mock_llm_different):
        """不同类型实体 → 不进同一桶 → 不比较 → 不合并。"""
        client = AsyncMock()

        async def embed(texts):
            # 不同类型 → 不同 base → 低相似度
            results = []
            for t in texts:
                if t == "运动":
                    results.append(_make_entity_emb(t, "Exercise"))
                else:
                    results.append(_make_entity_emb(t, "BrainRegion"))
            return results

        client.embed = AsyncMock(side_effect=embed)

        master = MasterGraph(book_id="t", book_title="T")
        ext = ChapterExtraction(
            chapter_id="ch01", chapter_title="Ch1",
            entities=[
                ExtractedEntity(name="运动", entity_type="Exercise",
                                description="desc", source_para_ids=[1]),
                ExtractedEntity(name="前额叶", entity_type="BrainRegion",
                                description="desc2", source_para_ids=[2]),
            ],
            relationships=[],
        )
        merge_map, merge_log = await batch_resolve_entities(
            {"ch01": ext}, master, client, mock_llm_different,
        )
        assert len(merge_log) == 0
        assert "运动" in master.graph.nodes
        assert "前额叶" in master.graph.nodes

    @pytest.mark.asyncio
    async def test_merge_same_type(self, mock_llm_same):
        """同类型实体 → Blocking 配对 → LLM 判定相同 → 合并。"""
        client = AsyncMock()

        async def embed(texts):
            return [_make_entity_emb(t, "Exercise") for t in texts]

        client.embed = AsyncMock(side_effect=embed)

        master = MasterGraph(book_id="t", book_title="T")
        ext1 = ChapterExtraction(
            chapter_id="ch01", chapter_title="Ch1",
            entities=[
                ExtractedEntity(name="运动", entity_type="Exercise",
                                description="身体活动和锻炼方式", source_para_ids=[1]),
            ],
            relationships=[],
        )
        ext2 = ChapterExtraction(
            chapter_id="ch02", chapter_title="Ch2",
            entities=[
                ExtractedEntity(name="体育锻炼", entity_type="Exercise",
                                description="有计划的体育运动训练", source_para_ids=[3]),
            ],
            relationships=[
                ExtractedRelationship(
                    source="体育锻炼", target="认知功能",
                    relation_type="THERAPEUTIC_IMPROVES",
                    evidence="研究证据", source_para_ids=[3]),
            ],
        )
        merge_map, merge_log = await batch_resolve_entities(
            {"ch01": ext1, "ch02": ext2}, master, client, mock_llm_same,
        )
        # 应有合并记录
        assert len(merge_log) > 0
        # 图中只有代表实体
        assert "运动" in master.graph.nodes
        assert "体育锻炼" not in master.graph.nodes
        # 关系被映射到代表实体
        assert master.graph.has_edge("运动", "认知功能")
        # chapter_para_count 被设置
        assert master.chapter_para_count["ch01"] == 1
        assert master.chapter_para_count["ch02"] == 3

    @pytest.mark.asyncio
    async def test_llm_failure_graceful(self):
        """LLM 调用失败时不崩溃，保留原始实体。"""
        emb_client = AsyncMock()

        async def embed(texts):
            return [_make_entity_emb(t, "Exercise") for t in texts]

        emb_client.embed = AsyncMock(side_effect=embed)

        llm_client = AsyncMock()

        async def gen(prompt, schema, model):
            raise RuntimeError("API 限流")

        llm_client.generate_structured = AsyncMock(side_effect=gen)

        master = MasterGraph(book_id="t", book_title="T")
        ext = ChapterExtraction(
            chapter_id="ch01", chapter_title="Ch1",
            entities=[
                ExtractedEntity(name="运动", entity_type="Exercise",
                                description="desc", source_para_ids=[1]),
                ExtractedEntity(name="体育锻炼", entity_type="Exercise",
                                description="desc2", source_para_ids=[2]),
            ],
            relationships=[],
        )
        merge_map, merge_log = await batch_resolve_entities(
            {"ch01": ext}, master, emb_client, llm_client,
        )
        # LLM 失败 → 不合并 → 两个实体都保留
        assert len(merge_log) == 0
        assert "运动" in master.graph.nodes
        assert "体育锻炼" in master.graph.nodes
