"""单元测试：全局图重建 (global_rebuild.py)

覆盖：跨书同名实体合并、关系去重重建、全局重建主流程
"""

import asyncio

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.core.knowledge_qa.graph.extractor import Entity, Relation
from src.core.knowledge_qa.graph.global_rebuild import (
    _merge_entities_by_name,
    _rebuild_relations_from_entities,
    rebuild_global_graph,
)


# ==================== 辅助函数 ====================


def _make_mock_entity(
    id: int,
    name: str,
    book_id: str,
    chunk_ids: list[str] | None = None,
    aliases: list[str] | None = None,
    description: str = "",
    entity_type: str = "symptom_behavior",
) -> MagicMock:
    """构造模拟 ORM 实体对象"""
    e = MagicMock()
    e.id = id
    e.name = name
    e.book_id = book_id
    e.chunk_ids = chunk_ids or []
    e.aliases = aliases or []
    e.description = description
    e.entity_type = entity_type
    return e


def _make_mock_relation(
    source_id: int,
    target_id: int,
    relation_type: str = "causes",
    description: str = "",
    confidence: float = 1.0,
) -> MagicMock:
    """构造模拟 ORM 关系对象"""
    r = MagicMock()
    r.source_entity_id = source_id
    r.target_entity_id = target_id
    r.relation_type = MagicMock(value=relation_type)
    r.description = description
    r.confidence = confidence
    return r


# ==================== _merge_entities_by_name 测试 ====================


class TestMergeEntitiesByName:
    """跨书同名实体合并测试"""

    def test_merge_entities_by_name_union(self):
        """同名实体的 chunk_ids 应合并去重，aliases 应合并，保留最长描述"""
        entities = [
            _make_mock_entity(
                id=1,
                name="前庭觉失调",
                book_id="book-A",
                chunk_ids=["c1", "c2"],
                aliases=["前庭功能障碍"],
                description="前庭系统功能异常",
            ),
            _make_mock_entity(
                id=2,
                name="前庭觉失调",
                book_id="book-B",
                chunk_ids=["c2", "c3"],
                aliases=["前庭功能异常"],
                description="前庭系统功能异常，表现为平衡和空间感知困难，影响注意力集中",
            ),
        ]

        merged = _merge_entities_by_name(entities)

        assert len(merged) == 1
        e = merged[0]
        assert e.name == "前庭觉失调"
        # chunk_ids 合并去重
        assert set(e.chunk_ids) == {"c1", "c2", "c3"}
        # aliases 合并去重
        assert set(e.aliases) == {"前庭功能障碍", "前庭功能异常"}
        # 保留最长描述
        assert "平衡和空间感知困难" in e.description
        # 全局实体无单一 book_id
        assert e.book_id == ""

    def test_merge_entities_by_name_different_names(self):
        """不同名称的实体应保持独立，不做合并"""
        entities = [
            _make_mock_entity(
                id=1,
                name="前庭觉失调",
                book_id="book-A",
                chunk_ids=["c1"],
                description="描述A",
            ),
            _make_mock_entity(
                id=2,
                name="注意力不集中",
                book_id="book-B",
                chunk_ids=["c2"],
                description="描述B",
            ),
        ]

        merged = _merge_entities_by_name(entities)

        assert len(merged) == 2
        names = {e.name for e in merged}
        assert names == {"前庭觉失调", "注意力不集中"}


# ==================== _rebuild_relations_from_entities 测试 ====================


class TestRebuildRelationsFromEntities:
    """关系去重与重建测试"""

    def test_rebuild_relations_from_entities_dedup(self):
        """重复关系（同源同目标同类型）应去重"""
        # 原始实体
        all_entities = [
            _make_mock_entity(id=1, name="A", book_id="b1"),
            _make_mock_entity(id=2, name="B", book_id="b1"),
        ]
        # 合并后实体（与原始同名）
        merged_entities = [
            Entity(name="A", entity_type="symptom_behavior", description="", book_id="", chunk_ids=[]),
            Entity(name="B", entity_type="symptom_behavior", description="", book_id="", chunk_ids=[]),
        ]
        # 两条重复关系（不同 source/target id 但指向同名实体）
        all_relations = [
            _make_mock_relation(source_id=1, target_id=2, relation_type="causes"),
            _make_mock_relation(source_id=1, target_id=2, relation_type="causes"),
        ]

        result = _rebuild_relations_from_entities(merged_entities, all_entities, all_relations)

        assert len(result) == 1
        assert result[0].source == "A"
        assert result[0].target == "B"
        assert result[0].relation_type == "causes"

    def test_rebuild_relations_unknown_name_skipped(self):
        """关系引用了未合并实体名时，该关系应被跳过"""
        # 原始实体中包含 id=3 的实体，但合并后的列表没有该实体名
        all_entities = [
            _make_mock_entity(id=1, name="A", book_id="b1"),
            _make_mock_entity(id=2, name="B", book_id="b1"),
            _make_mock_entity(id=3, name="C", book_id="b2"),
        ]
        # 合并后仅保留 A, B
        merged_entities = [
            Entity(name="A", entity_type="symptom_behavior", description="", book_id="", chunk_ids=[]),
            Entity(name="B", entity_type="symptom_behavior", description="", book_id="", chunk_ids=[]),
        ]
        # 关系 A→B 合法，A→C 不合法（C 不在合并列表中）
        all_relations = [
            _make_mock_relation(source_id=1, target_id=2, relation_type="causes"),
            _make_mock_relation(source_id=1, target_id=3, relation_type="treats"),
        ]

        result = _rebuild_relations_from_entities(merged_entities, all_entities, all_relations)

        # 只有 A→B 被保留，A→C 被跳过
        assert len(result) == 1
        assert result[0].target == "B"


# ==================== rebuild_global_graph 集成测试 ====================


class TestRebuildGlobalGraph:
    """全局图重建主流程测试"""

    @pytest.mark.asyncio
    async def test_rebuild_global_graph_empty_entities(self):
        """空仓库时应返回零计数结果且不报错"""
        mock_session_factory = MagicMock()

        with patch("src.core.knowledge_qa.graph.global_rebuild.GraphEntityRepository") as mock_entity_repo_cls, \
             patch("src.core.knowledge_qa.graph.global_rebuild.GraphRelationRepository") as mock_rel_repo_cls, \
             patch("src.core.knowledge_qa.graph.global_rebuild.GraphCommunityRepository") as mock_community_repo_cls:

            mock_entity_repo = MagicMock()
            mock_entity_repo.find_all = AsyncMock(return_value=[])
            mock_entity_repo_cls.return_value = mock_entity_repo

            mock_rel_repo = MagicMock()
            mock_rel_repo.find_all = AsyncMock(return_value=[])
            mock_rel_repo_cls.return_value = mock_rel_repo

            mock_community_repo = MagicMock()
            mock_community_repo_cls.return_value = mock_community_repo

            result = await rebuild_global_graph(mock_session_factory)

            # 空数据应返回零计数
            assert result["total_entities"] == 0
            assert result["merged_entities"] == 0
            assert result["total_relations"] == 0
            assert result["global_relations"] == 0
            assert result["error"] is None

    @pytest.mark.asyncio
    async def test_rebuild_global_graph_error_handling(self):
        """仓库抛出异常时，结果应包含 error 字段且函数不抛出"""
        mock_session_factory = MagicMock()

        with patch("src.core.knowledge_qa.graph.global_rebuild.GraphEntityRepository") as mock_entity_repo_cls, \
             patch("src.core.knowledge_qa.graph.global_rebuild.GraphRelationRepository") as mock_rel_repo_cls, \
             patch("src.core.knowledge_qa.graph.global_rebuild.GraphCommunityRepository") as mock_community_repo_cls:

            mock_entity_repo = MagicMock()
            # 模拟 find_all 抛出数据库异常
            mock_entity_repo.find_all = AsyncMock(side_effect=RuntimeError("数据库连接失败"))
            mock_entity_repo_cls.return_value = mock_entity_repo

            mock_rel_repo = MagicMock()
            mock_rel_repo.find_all = AsyncMock(return_value=[])
            mock_rel_repo_cls.return_value = mock_rel_repo

            mock_community_repo = MagicMock()
            mock_community_repo_cls.return_value = mock_community_repo

            result = await rebuild_global_graph(mock_session_factory)

            # 应捕获异常，result 包含 error 字段
            assert result["error"] is not None
            assert "数据库连接失败" in result["error"]
            # 函数本身不应抛出
