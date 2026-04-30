"""ResultProcessor 分数归一化单元测试

测试 per-query min-max 归一化逻辑：
- 多结果时分数有区分度（不再全部 98%）
- 分数分布极窄时统一给高分（不制造虚假区分）
- 单结果时取 max_display_score
- 所有结果保留 raw_score 供调试
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from src.service.retrieval.result_processor import ResultProcessor


def _make_node_with_score(score: float, content: str = "测试内容", file_name: str = "test.pdf"):
    """构造模拟的 NodeWithScore 对象"""
    node = MagicMock()
    node.score = score
    node.node.node_id = f"node-{score}"
    node.node.metadata = {"file_name": file_name, "file_hash": None}
    node.node.get_content.return_value = content
    return node


@pytest.fixture
def processor():
    return ResultProcessor()


@pytest.fixture
def mock_settings(monkeypatch):
    """模拟配置，使用默认值"""
    monkeypatch.setattr("src.service.retrieval.result_processor.settings.rag_scoring_base_display_score", 0.55)
    monkeypatch.setattr("src.service.retrieval.result_processor.settings.rag_scoring_max_display_score", 0.98)
    monkeypatch.setattr("src.service.retrieval.result_processor.settings.rag_scoring_keyword_bonus_log_weight", 0.08)
    monkeypatch.setattr("src.service.retrieval.result_processor.settings.rag_scoring_keyword_bonus_max", 0.12)
    monkeypatch.setattr("src.service.retrieval.result_processor.settings.rag_scoring_score_spread_min", 0.002)
    # 阈值设低，确保 RRF 分数（~0.03）能通过
    monkeypatch.setattr("src.service.retrieval.result_processor.settings.rag_search_score_threshold_hybrid", 0.003)
    monkeypatch.setattr("src.service.retrieval.result_processor.settings.rag_search_score_threshold_vector", 0.003)
    monkeypatch.setattr("src.service.retrieval.result_processor.settings.rag_search_relative_cutoff_ratio", 0.5)


class TestPerQueryMinMaxNormalization:
    """Per-Query Min-Max 归一化测试"""

    @pytest.mark.asyncio
    async def test_multiple_results_have_score_variation(self, processor, mock_settings):
        """多结果时分数应有区分度，不再全部 98%"""
        nodes = [
            _make_node_with_score(0.032, content="运动发展里程碑的第一阶段内容"),
            _make_node_with_score(0.025, content="感觉统合训练的具体方法指导"),
            _make_node_with_score(0.020, content="认知能力评估的参考标准说明"),
        ]

        with patch("src.service.document_manager.document_manager", new_callable=AsyncMock):
            results = await processor._process_search_results(
                nodes=nodes,
                original_query="测试查询",
                expanded_query="测试查询扩展",
                bm25_nodes=[],
                bm25_retriever=MagicMock(),
                vector_retriever=MagicMock(),
            )

        assert len(results) == 3
        scores = [r["score"] for r in results]
        assert all(s <= 0.98 + 0.001 for s in scores), f"分数超出上限: {scores}"
        assert all(s >= 0.55 - 0.001 for s in scores), f"分数低于下限: {scores}"
        assert len(set(round(s, 4) for s in scores)) > 1, f"分数无区分度: {scores}"
        assert scores[0] > scores[-1], f"分数未降序排列: {scores}"

    @pytest.mark.asyncio
    async def test_narrow_spread_gives_uniform_high_score(self, processor, mock_settings):
        """分数分布极窄时统一给高分，不制造虚假区分"""
        nodes = [
            _make_node_with_score(0.030, content="运动发展里程碑的第一阶段内容"),
            _make_node_with_score(0.031, content="感觉统合训练的具体方法指导"),
            _make_node_with_score(0.0305, content="认知能力评估的参考标准说明"),
        ]

        with patch("src.service.document_manager.document_manager", new_callable=AsyncMock):
            results = await processor._process_search_results(
                nodes=nodes,
                original_query="测试查询",
                expanded_query="测试查询扩展",
                bm25_nodes=[],
                bm25_retriever=MagicMock(),
                vector_retriever=MagicMock(),
            )

        assert len(results) == 3
        scores = [r["score"] for r in results]
        assert scores[0] == pytest.approx(scores[1], abs=0.01)
        assert scores[1] == pytest.approx(scores[2], abs=0.01)

    @pytest.mark.asyncio
    async def test_single_result_gets_max_display(self, processor, mock_settings):
        """单结果时给 max_display_score"""
        nodes = [_make_node_with_score(0.032, content="运动发展的阶段说明")]

        with patch("src.service.document_manager.document_manager", new_callable=AsyncMock):
            results = await processor._process_search_results(
                nodes=nodes,
                original_query="测试查询",
                expanded_query="测试查询扩展",
                bm25_nodes=[],
                bm25_retriever=MagicMock(),
                vector_retriever=MagicMock(),
            )

        assert len(results) == 1
        assert results[0]["score"] == pytest.approx(0.98, abs=0.01)

    @pytest.mark.asyncio
    async def test_raw_score_preserved(self, processor, mock_settings):
        """raw_score 保留原始值（含关键词加成），不受归一化影响"""
        nodes = [_make_node_with_score(0.032, content="运动发展的阶段说明")]

        with patch("src.service.document_manager.document_manager", new_callable=AsyncMock):
            results = await processor._process_search_results(
                nodes=nodes,
                original_query="认知评估",
                expanded_query="认知评估扩展",
                bm25_nodes=[],
                bm25_retriever=MagicMock(),
                vector_retriever=MagicMock(),
            )

        assert len(results) == 1
        # raw_score 应包含原始分数（不含关键词加成，因为查询词不匹配内容）
        assert results[0]["raw_score"] == pytest.approx(0.032, abs=0.001)

    @pytest.mark.asyncio
    async def test_below_threshold_filtered(self, processor, mock_settings):
        """低于阈值的结果被过滤"""
        # 构造一个高分和低分，低分应被相对截断过滤
        nodes = [
            _make_node_with_score(0.032, content="运动发展的阶段说明"),
            _make_node_with_score(0.001, content="感觉统合的训练方法"),  # 极低分
        ]

        with patch("src.service.document_manager.document_manager", new_callable=AsyncMock):
            results = await processor._process_search_results(
                nodes=nodes,
                original_query="测试查询",
                expanded_query="测试查询扩展",
                bm25_nodes=[],
                bm25_retriever=MagicMock(),
                vector_retriever=MagicMock(),
            )

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_keyword_bonus_affects_raw_not_display_order(self, processor, mock_settings):
        """关键词加成影响 raw_score，display_score 基于 raw_score 做归一化"""
        nodes = [
            _make_node_with_score(0.032, content="注意力训练的方法和技巧"),
            _make_node_with_score(0.032, content="完全不同的内容没有任何匹配"),
        ]

        with patch("src.service.document_manager.document_manager", new_callable=AsyncMock):
            results = await processor._process_search_results(
                nodes=nodes,
                original_query="注意力训练",
                expanded_query="注意力训练扩展",
                bm25_nodes=[],
                bm25_retriever=MagicMock(),
                vector_retriever=MagicMock(),
            )

        assert len(results) == 2
        # 含关键词匹配的结果 raw_score 应更高
        assert results[0]["raw_score"] >= results[1]["raw_score"]
