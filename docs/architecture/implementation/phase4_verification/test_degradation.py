"""降级路径测试 — 验证 Neo4j 不可用时系统行为。

放置位置: backend/tests/e2e/test_neo4j_degradation.py
运行: uv run pytest tests/e2e/test_neo4j_degradation.py -v
"""

from __future__ import annotations

import os
import pytest
from unittest.mock import patch, AsyncMock


# ── 测试 fixtures ──────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_neo4j_env():
    """每个测试前后重置 Neo4j 环境变量。"""
    original = os.environ.get("NEO4J_ENABLED")
    yield
    if original is not None:
        os.environ["NEO4J_ENABLED"] = original
    elif "NEO4J_ENABLED" in os.environ:
        del os.environ["NEO4J_ENABLED"]


# ── 降级场景测试 ───────────────────────────────────────────────

class TestNeo4jDegradation:
    """Neo4j 降级场景测试矩阵。"""

    @pytest.mark.asyncio
    async def test_neo4j_disabled_returns_empty(self):
        """NEO4J_ENABLED=False 时 query_neo4j_graph 返回空字典。"""
        os.environ["NEO4J_ENABLED"] = "False"

        from core.knowledge_qa.nodes_v2.query_neo4j_graph import query_neo4j_graph_node

        state = _make_mock_state()
        result = await query_neo4j_graph_node(state)
        assert result == {"neo4j_knowledge": {}}

    @pytest.mark.asyncio
    async def test_neo4j_connection_refused_graceful(self):
        """Neo4j 连接被拒绝时优雅降级。"""
        os.environ["NEO4J_ENABLED"] = "True"

        with patch("core.knowledge_qa.neo4j.driver.neo4j_available", return_value=False):
            from core.knowledge_qa.nodes_v2.query_neo4j_graph import query_neo4j_graph_node

            state = _make_mock_state()
            result = await query_neo4j_graph_node(state)
            assert result == {"neo4j_knowledge": {}}

    @pytest.mark.asyncio
    async def test_neo4j_query_timeout_returns_empty(self):
        """Neo4j 查询超时后返回空结果。"""
        os.environ["NEO4J_ENABLED"] = "True"

        with patch("core.knowledge_qa.neo4j.driver.neo4j_available", return_value=True):
            with patch(
                "core.knowledge_qa.neo4j.query_dispatcher.query_all",
                side_effect=TimeoutError("Query timeout"),
            ):
                from core.knowledge_qa.nodes_v2.query_neo4j_graph import query_neo4j_graph_node

                state = _make_mock_state()
                result = await query_neo4j_graph_node(state)
                assert result == {"neo4j_knowledge": {}}

    @pytest.mark.asyncio
    async def test_exercise_no_match_fallback(self):
        """Neo4j 中无匹配运动时返回空列表。"""
        os.environ["NEO4J_ENABLED"] = "True"

        with patch("core.knowledge_qa.neo4j.driver.neo4j_available", return_value=True):
            with patch(
                "core.knowledge_qa.neo4j.query_dispatcher.query_all",
                return_value={"exercises": [], "cross_book_relations": [], "problem_context": [], "source_coverage": {}},
            ):
                from core.knowledge_qa.nodes_v2.query_neo4j_graph import query_neo4j_graph_node

                state = _make_mock_state()
                result = await query_neo4j_graph_node(state)
                assert result["neo4j_knowledge"]["exercises"] == []

    @pytest.mark.asyncio
    async def test_cross_book_no_relations_returns_empty(self):
        """仅一本书时跨书关系为空。"""
        from core.knowledge_qa.neo4j.query_dispatcher import _query_cross_book

        mock_session = AsyncMock()
        mock_session.run.return_value.data.return_value = []

        result = _query_cross_book(mock_session, ["book_001"])
        assert result == []


# ── 灰度测试 ───────────────────────────────────────────────────

class TestRolloutPercentage:
    """灰度上线逻辑测试 — 基于 hash 的稳定路由。"""

    def _make_config(self, enabled: bool, percentage: int):
        """创建模拟 config_manager。"""
        from types import SimpleNamespace
        _config = {"neo4j.enabled": enabled, "neo4j.rollout_percentage": percentage}
        cm = SimpleNamespace()
        cm.get = lambda key, default=None: _config.get(key, default)
        return cm

    def test_rollout_0_percent_never_use(self):
        """ROLLOUT=0 永远不使用 Neo4j。"""
        from grayscale_rollout import should_use_neo4j

        cm = self._make_config(True, 0)
        # 任何 question_id 都应返回 False
        assert should_use_neo4j("any-question-id", cm) is False
        assert should_use_neo4j("", cm) is False

    def test_rollout_100_percent_always_use(self):
        """ROLLOUT=100 始终使用 Neo4j。"""
        from grayscale_rollout import should_use_neo4j

        cm = self._make_config(True, 100)
        assert should_use_neo4j("any-question-id", cm) is True

    def test_disabled_neo4j_never_uses(self):
        """NEO4J_ENABLED=False 时无论百分比如何都不使用。"""
        from grayscale_rollout import should_use_neo4j

        cm = self._make_config(False, 100)
        assert should_use_neo4j("any-question-id", cm) is False

    def test_hash_routing_is_deterministic(self):
        """同一 question_id 始终走同一路径。"""
        from grayscale_rollout import should_use_neo4j

        cm = self._make_config(True, 50)
        first = should_use_neo4j("test-q-123", cm)
        # 多次调用结果一致
        for _ in range(10):
            assert should_use_neo4j("test-q-123", cm) == first

    def test_percentage_distributes_across_questions(self):
        """50% 灰度下，不同 question_id 应有合理分布。"""
        from grayscale_rollout import should_use_neo4j

        cm = self._make_config(True, 50)
        results = [should_use_neo4j(f"q-{i}", cm) for i in range(200)]
        true_count = sum(results)
        # 50% ± 15% 的合理范围
        assert 70 < true_count < 130, f"Distribution skewed: {true_count}/200"


# ── Helper ─────────────────────────────────────────────────────

def _make_mock_state():
    """创建模拟的 KnowledgeQAState。"""
    from types import SimpleNamespace

    section = SimpleNamespace(
        structured_data={
            "problems": [{"name": "注意力不集中", "severity": "high"}],
            "root_causes": ["多巴胺不足"],
        }
    )

    return SimpleNamespace(
        question="孩子注意力不集中怎么办",
        child_profile={"age": 8, "gender": "男"},
        matched_books=[{"book_id": "exercise_book_001", "title": "运动改变大脑"}],
        sections=[section, section, section, section, section],
    )
