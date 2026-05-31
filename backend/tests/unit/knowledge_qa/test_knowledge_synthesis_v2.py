"""tests for knowledge_synthesis_v2_node — 三层知识综合"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.core.knowledge_qa.nodes_v2.knowledge_synthesis_v2 import (
    _extract_three_layers,
    knowledge_synthesis_v2_node,
)


# ── _extract_three_layers ──


class TestExtractThreeLayers:
    def test_empty_returns_empty(self):
        assert _extract_three_layers({}) == {}

    def test_no_cross_returns_empty(self):
        assert _extract_three_layers({"cross_book_relations": []}) == {}

    def test_consensus_extracted(self):
        data = {
            "cross_book_relations": [
                {
                    "relation_type": "CROSS_BOOK_CONSENSUS",
                    "source_entity": "BDNF",
                    "target_entity": "脑源性神经营养因子",
                    "source_book": "书1",
                    "target_book": "书2",
                    "explanation": "两书均认为BDNF促进神经发育",
                }
            ]
        }
        result = _extract_three_layers(data)
        assert len(result["consensus"]) == 1
        assert "BDNF" in result["consensus"][0]["topic"]
        assert result["consensus"][0]["confidence"] == "high"

    def test_complements_extracted(self):
        data = {
            "cross_book_relations": [
                {
                    "relation_type": "CROSS_BOOK_COMPLEMENTS",
                    "source_entity": "运动",
                    "target_entity": "运动",
                    "source_book": "书1",
                    "target_book": "书2",
                    "explanation": "书1关注有氧，书2关注力量",
                }
            ]
        }
        result = _extract_three_layers(data)
        assert len(result["complementary"]) == 1
        assert len(result["complementary"][0]["fragments"]) >= 1

    def test_conflicts_extracted(self):
        data = {
            "cross_book_relations": [
                {
                    "relation_type": "CROSS_BOOK_CONFLICTS",
                    "source_entity": "屏幕时间",
                    "target_entity": "屏幕时间",
                    "source_book": "书1",
                    "target_book": "书2",
                    "explanation": "书1建议<1h，书2建议<2h",
                }
            ]
        }
        result = _extract_three_layers(data)
        assert len(result["conflicts"]) == 1
        assert result["conflicts"][0]["severity"] == "moderate"

    def test_mixed_types(self):
        data = {
            "cross_book_relations": [
                {"relation_type": "CROSS_BOOK_CONSENSUS", "source_entity": "A", "target_entity": "B",
                 "source_book": "书1", "target_book": "书2", "explanation": "共识"},
                {"relation_type": "CROSS_BOOK_CONFLICTS", "source_entity": "C", "target_entity": "D",
                 "source_book": "书1", "target_book": "书2", "explanation": "冲突"},
            ]
        }
        result = _extract_three_layers(data)
        assert len(result["consensus"]) == 1
        assert len(result["conflicts"]) == 1
        assert result.get("complementary", []) == []

    def test_unknown_relation_type_ignored(self):
        data = {
            "cross_book_relations": [
                {"relation_type": "UNKNOWN_TYPE", "source_entity": "A", "target_entity": "B",
                 "source_book": "书1", "target_book": "书2", "explanation": "未知"}
            ]
        }
        result = _extract_three_layers(data)
        assert result == {}


# ── knowledge_synthesis_v2_node ──


class TestKnowledgeSynthesisV2Node:
    @pytest.fixture
    def mock_state(self):
        state = MagicMock()
        state.neo4j_knowledge = {}
        state.matched_books_detail = []
        state.sections = {}
        return state

    @pytest.mark.asyncio
    async def test_empty_neo4j_single_book_returns_empty(self, mock_state):
        mock_state.matched_books_detail = [{"book_id": "b1"}]
        with patch("src.core.knowledge_qa.nodes_v2.knowledge_synthesis_v2.push_progress", new_callable=AsyncMock):
            result = await knowledge_synthesis_v2_node(mock_state)
        assert result["three_layer_synthesis"] == {}

    @pytest.mark.asyncio
    async def test_neo4j_consensus_only(self, mock_state):
        mock_state.neo4j_knowledge = {
            "cross_book_relations": [
                {"relation_type": "CROSS_BOOK_CONSENSUS", "source_entity": "X", "target_entity": "Y",
                 "source_book": "书1", "target_book": "书2", "explanation": "一致"}
            ]
        }
        with patch("src.core.knowledge_qa.nodes_v2.knowledge_synthesis_v2.push_progress", new_callable=AsyncMock):
            result = await knowledge_synthesis_v2_node(mock_state)
        assert len(result["three_layer_synthesis"]["consensus"]) == 1
        assert result["contradictions"] == []

    @pytest.mark.asyncio
    async def test_conflicts_populate_contraditions(self, mock_state):
        mock_state.neo4j_knowledge = {
            "cross_book_relations": [
                {"relation_type": "CROSS_BOOK_CONFLICTS", "source_entity": "A", "target_entity": "B",
                 "source_book": "书1", "target_book": "书2", "explanation": "观点不同"}
            ]
        }
        with patch("src.core.knowledge_qa.nodes_v2.knowledge_synthesis_v2.push_progress", new_callable=AsyncMock):
            result = await knowledge_synthesis_v2_node(mock_state)
        assert len(result["contradictions"]) == 1
        assert result["contradictions"][0]["topic"] == "A ↔ B"

    @pytest.mark.asyncio
    async def test_multi_book_llm_fallback(self, mock_state):
        """多书场景且 Neo4j 无数据时，应尝试 LLM 推断。"""
        mock_state.matched_books_detail = [{"book_id": "b1"}, {"book_id": "b2"}]
        mock_state.sections = {
            1: MagicMock(content="内容1", title="标题1"),
            2: MagicMock(content="内容2", title="标题2"),
        }
        mock_llm_resp = MagicMock()
        mock_llm_resp.content = '{"consensus": [], "complementary": [], "conflicts": []}'

        with (
            patch("src.core.knowledge_qa.nodes_v2.knowledge_synthesis_v2.push_progress", new_callable=AsyncMock),
            patch("src.core.llm.factory.LLMServiceFactoryCompat.create_raw") as mock_factory,
        ):
            mock_model = AsyncMock()
            mock_model.ainvoke.return_value = mock_llm_resp
            mock_factory.return_value = mock_model
            result = await knowledge_synthesis_v2_node(mock_state)

        assert "three_layer_synthesis" in result
