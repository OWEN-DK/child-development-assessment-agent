"""实体消歧引擎单元测试

测试 cosine_similarity_matrix 和 resolve_and_merge。
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.core.knowledge_qa.d2g.entity_resolver import (
    cosine_similarity_matrix,
    resolve_and_merge,
)
from src.core.knowledge_qa.d2g.master_graph import MasterGraph
from src.core.knowledge_qa.d2g.models import (
    EntityType,
    ExtractedEntity,
    EntityMatchJudgment,
)


# ──────────────────────────────────────────────────────────────
# cosine_similarity_matrix 测试
# ──────────────────────────────────────────────────────────────


class TestCosineSimilarityMatrix:
    """cosine_similarity_matrix 函数测试"""

    def test_identical_vectors(self):
        """相同向量应返回 1.0"""
        v = [[1.0, 2.0, 3.0]]
        sims = cosine_similarity_matrix(v, v)
        assert sims[0][0] == pytest.approx(1.0, abs=1e-6)

    def test_orthogonal_vectors(self):
        """正交向量应返回 0.0"""
        a = [[1.0, 0.0]]
        b = [[0.0, 1.0]]
        sims = cosine_similarity_matrix(a, b)
        assert sims[0][0] == pytest.approx(0.0, abs=1e-6)

    def test_opposite_vectors(self):
        """反向向量应返回 -1.0"""
        a = [[1.0, 0.0]]
        b = [[-1.0, 0.0]]
        sims = cosine_similarity_matrix(a, b)
        assert sims[0][0] == pytest.approx(-1.0, abs=1e-6)

    def test_zero_vector(self):
        """零向量应返回 0.0（避免除零）"""
        a = [[0.0, 0.0]]
        b = [[1.0, 2.0]]
        sims = cosine_similarity_matrix(a, b)
        assert sims[0][0] == 0.0

    def test_multiple_vectors(self):
        """多向量应返回正确形状的矩阵"""
        a = [[1.0, 0.0], [0.0, 1.0]]
        b = [[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]]
        sims = cosine_similarity_matrix(a, b)
        assert len(sims) == 2
        assert len(sims[0]) == 3
        # a[0] 与 b[0] 相似度 = 1.0
        assert sims[0][0] == pytest.approx(1.0, abs=1e-6)
        # a[0] 与 b[1] 正交 = 0.0
        assert sims[0][1] == pytest.approx(0.0, abs=1e-6)
        # a[0] 与 b[2] = cos(45°) ≈ 0.707
        assert sims[0][2] == pytest.approx(0.707, abs=0.01)


# ──────────────────────────────────────────────────────────────
# resolve_and_merge 测试
# ──────────────────────────────────────────────────────────────


class TestResolveAndMerge:
    """resolve_and_merge 函数测试"""

    @pytest.mark.asyncio
    async def test_empty_master_graph(self):
        """主图为空时应直接添加所有实体"""
        master = MasterGraph(book_id="b", book_title="t")
        entities = [
            ExtractedEntity(
                name="实体A", entity_type=EntityType.Problem,
                description="实体A的详细描述文本内容用于测试验证场景", source_para_ids=[1],
            ),
        ]
        embedding_client = AsyncMock()
        llm_client = AsyncMock()

        merged = await resolve_and_merge(
            entities, "ch01", master, embedding_client, llm_client,
        )
        assert merged == 0
        assert master.graph.number_of_nodes() == 1
        # embedding_client 不应被调用（主图为空）
        embedding_client.embed.assert_not_called()

    @pytest.mark.asyncio
    async def test_new_entity_low_similarity(self):
        """低相似度实体应直接新增"""
        master = MasterGraph(book_id="b", book_title="t")
        master.add_entity(ExtractedEntity(
            name="完全不同的实体",
            entity_type=EntityType.Problem,
            description="这是一个实体的详细描述文本内容用于测试验证场景",
            source_para_ids=[1],
        ), "ch01")

        new_entity = ExtractedEntity(
            name="新实体",
            entity_type=EntityType.Solution,
            description="新实体的详细描述文本内容用于测试验证场景",
            source_para_ids=[2],
        )

        embedding_client = AsyncMock()
        # 返回低相似度的 embedding
        embedding_client.embed = AsyncMock(side_effect=[
            [[1.0, 0.0, 0.0]],  # 已有实体
            [[0.0, 0.0, 1.0]],  # 新实体（正交 = 0 相似度）
        ])

        llm_client = AsyncMock()

        merged = await resolve_and_merge(
            [new_entity], "ch01", master, embedding_client, llm_client,
            similarity_threshold=0.85,
        )
        assert merged == 0
        assert master.graph.number_of_nodes() == 2
        # 低相似度不应调用 LLM
        llm_client.generate_structured.assert_not_called()

    @pytest.mark.asyncio
    async def test_high_similarity_llm_confirms_merge(self):
        """高相似度 + LLM 确认 → 合并"""
        master = MasterGraph(book_id="b", book_title="t")
        master.add_entity(ExtractedEntity(
            name="注意力问题",
            entity_type=EntityType.Problem,
            description="儿童在学习或活动中难以持续关注目标刺激的表现",
            source_para_ids=[1],
        ), "ch01")

        new_entity = ExtractedEntity(
            name="注意力不集中",
            entity_type=EntityType.Problem,
            description="注意力缺陷问题，表现为难以集中注意力和容易分心",
            source_para_ids=[2],
        )

        embedding_client = AsyncMock()
        embedding_client.embed = AsyncMock(side_effect=[
            [[1.0, 0.9, 0.8]],  # 已有实体
            [[1.0, 0.9, 0.8]],  # 新实体（相同 = 1.0 相似度）
        ])

        llm_client = AsyncMock()
        llm_client.generate_structured = AsyncMock(return_value=EntityMatchJudgment(
            same=True,
            reason="都指注意力问题",
        ))

        merged = await resolve_and_merge(
            [new_entity], "ch01", master, embedding_client, llm_client,
            similarity_threshold=0.85,
        )
        assert merged == 1
        # 注意力不集中 应被合并到 注意力问题
        assert "注意力不集中" not in master.graph.nodes
        assert "注意力问题" in master.graph.nodes

    @pytest.mark.asyncio
    async def test_high_similarity_llm_rejects_merge(self):
        """高相似度 + LLM 否认 → 不合并"""
        master = MasterGraph(book_id="b", book_title="t")
        master.add_entity(ExtractedEntity(
            name="感觉统合",
            entity_type=EntityType.Theory,
            description="感觉统合理论认为大脑需要整合多种感觉信息",
            source_para_ids=[1],
        ), "ch01")

        new_entity = ExtractedEntity(
            name="感觉训练",
            entity_type=EntityType.Exercise,
            description="感觉训练方法通过特定刺激改善大脑整合能力",
            source_para_ids=[2],
        )

        embedding_client = AsyncMock()
        embedding_client.embed = AsyncMock(side_effect=[
            [[1.0, 0.9]],  # 已有
            [[1.0, 0.9]],  # 新（高相似度）
        ])

        llm_client = AsyncMock()
        llm_client.generate_structured = AsyncMock(return_value=EntityMatchJudgment(
            same=False,
            reason="前者是理论，后者是训练方法",
        ))

        merged = await resolve_and_merge(
            [new_entity], "ch01", master, embedding_client, llm_client,
            similarity_threshold=0.85,
        )
        assert merged == 0
        assert master.graph.number_of_nodes() == 2
