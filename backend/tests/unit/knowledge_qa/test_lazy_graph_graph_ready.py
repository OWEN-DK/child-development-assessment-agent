"""单元测试：LazyGraphRAG 图遍历的 graph_ready 过滤 + ID 转换

覆盖修复后的 5 个 bug:
  #1: file_hash → UUID 转换（通过 _filter_graph_ready）
  #2: graph_ready 过滤缺失 → 已补充
  #3: 0 实体时 graph_ready 误标 → 已设置 error
  #4: root.node_id 属性访问 dict → 已改为 dict 访问
  #5: 重复触发图构建 → 已加幂等检查
"""

from __future__ import annotations

import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from src.core.knowledge_qa.graph.traversal import TraversalHit


# ── 辅助构造 ──

def _make_root(node_id: str, book_id: str) -> dict:
    """模拟 get_roots 返回的社区根节点（dict 格式，与 HTTP 接口一致）"""
    return {
        "node_id": node_id,
        "label": f"root-{node_id}",
        "entity_names": [],
        "chunk_ids": [],
        "is_leaf": False,
        "scope": "book",
        "book_id": book_id,
    }


def _make_hit(node_id: str, chunk_ids: list[str] | None = None) -> TraversalHit:
    """模拟 explore_community_tree 返回的遍历命中"""
    return TraversalHit(
        node_id=node_id,
        label=f"hit-{node_id}",
        entity_names=["entity_a"],
        chunk_ids=chunk_ids or [f"chunk_{node_id}"],
    )


def _build_mock_community_repo(roots_by_book: dict) -> MagicMock:
    """构建 mock HttpGraphAdapter，按 book_id 返回不同 roots。"""
    mock_repo = MagicMock()

    async def get_roots(scope, book_id):
        return roots_by_book.get(book_id, [])

    mock_repo.get_roots = AsyncMock(side_effect=get_roots)
    mock_repo.close = AsyncMock()
    return mock_repo


# ══════════════════════════════════════════════════════════════════════════════
# Bug #1+#2: _filter_graph_ready 调用 + file_hash → UUID 转换
# ══════════════════════════════════════════════════════════════════════════════

class TestFilterGraphReadyInBundleBuilder:
    """验证 bundle_builder 现在正确调用 _filter_graph_ready。"""

    def test_bundle_builder_imports_filter_graph_ready(self):
        """bundle_builder 源码中已包含 _filter_graph_ready 调用。"""
        import inspect
        from src.core.knowledge_qa import bundle_builder

        source = inspect.getsource(bundle_builder._enhanced_lazy_graph_traversal)
        assert "_filter_graph_ready" in source

    @pytest.mark.asyncio
    async def test_filter_graph_ready_converts_hash_to_uuid(self):
        """_filter_graph_ready 将 file_hash 转换为 UUID 后再查询社区树。"""
        from src.core.knowledge_qa.bundle_builder import _enhanced_lazy_graph_traversal

        file_hash = "6399b9028564015952ff9ef948c72339"
        uuid = "35dc539d-d9dc-40eb-8f2c-e7e502a783cd"

        mock_repo = _build_mock_community_repo({
            uuid: [_make_root("root_1", uuid)],
        })

        mock_hit = _make_hit("root_1", ["chunk_1"])
        queried_ids: list[str] = []

        original_get_roots = mock_repo.get_roots

        async def tracking_get_roots(scope, book_id):
            queried_ids.append(book_id)
            return await original_get_roots(scope=scope, book_id=book_id)

        mock_repo.get_roots = AsyncMock(side_effect=tracking_get_roots)

        async def mock_filter_graph_ready(book_ids):
            return [uuid]  # file_hash → UUID

        async def mock_explore(question, root_id, community_repo,
                               max_tokens=12000, entity_boost_names=None):
            return [mock_hit]

        with patch(
            "src.utils.http_client.HttpGraphAdapter",
            return_value=mock_repo,
        ), patch(
            "src.utils.http_client.RagHttpClient",
        ), patch(
            "httpx.AsyncClient",
        ), patch(
            "src.core.knowledge_qa.nodes.prefetch_context._filter_graph_ready",
            side_effect=mock_filter_graph_ready,
        ), patch(
            "src.core.knowledge_qa.graph.traversal.explore_community_tree",
            side_effect=mock_explore,
        ), patch(
            "src.core.knowledge_qa.graph.traversal.build_knowledge_context",
            return_value="mocked context",
        ):
            context, hit_count = await _enhanced_lazy_graph_traversal(
                question="测试问题",
                entity_seeds=[],
                matched_book_ids=[file_hash],
                custom_entities=[],
            )

        # 查询时使用的是 UUID，不是 file_hash
        assert uuid in queried_ids
        assert file_hash not in queried_ids
        assert hit_count == 1

    @pytest.mark.asyncio
    async def test_no_graph_ready_books_returns_empty(self):
        """所有书 graph_ready=False 时，直接返回空。"""
        from src.core.knowledge_qa.bundle_builder import _enhanced_lazy_graph_traversal

        mock_repo = _build_mock_community_repo({})

        async def mock_filter_graph_ready(book_ids):
            return []  # 无 graph_ready 的书

        with patch(
            "src.utils.http_client.HttpGraphAdapter",
            return_value=mock_repo,
        ), patch(
            "src.utils.http_client.RagHttpClient",
        ), patch(
            "httpx.AsyncClient",
        ), patch(
            "src.core.knowledge_qa.nodes.prefetch_context._filter_graph_ready",
            side_effect=mock_filter_graph_ready,
        ):
            context, hit_count = await _enhanced_lazy_graph_traversal(
                question="测试问题",
                entity_seeds=[],
                matched_book_ids=["some_hash"],
                custom_entities=[],
            )

        assert context == ""
        assert hit_count == 0


# ══════════════════════════════════════════════════════════════════════════════
# Bug #3: 0 实体时 graph_ready 误标
# ══════════════════════════════════════════════════════════════════════════════

class TestGraphBuildZeroEntities:
    """0 实体时 build_graph_for_book 应设置 error，防止 graph_ready 被误标。"""

    @pytest.mark.asyncio
    async def test_zero_entities_sets_error(self):
        """extract_entities_relations 返回空 → result.error = 'no_entities'。"""
        from src.core.knowledge_qa.graph.pipeline import build_graph_for_book

        mock_http = MagicMock()
        mock_http.upsert_entities = AsyncMock(return_value=0)
        mock_http.insert_relations = AsyncMock(return_value=0)

        with patch(
            "src.core.knowledge_qa.graph.pipeline.extract_entities_relations",
            return_value=([], []),
        ):
            result = await build_graph_for_book(
                book_id="6399b902-aaaa",
                chunks=["chunk1"],
                topics_per_chunk=[["topic1"]],
                http_client=mock_http,
            )

        assert result["entity_count"] == 0
        assert result["error"] == "no_entities"
        mock_http.upsert_entities.assert_not_called()


# ══════════════════════════════════════════════════════════════════════════════
# Bug #4: root.node_id 属性访问 dict → dict key 访问
# ══════════════════════════════════════════════════════════════════════════════

class TestRootDictAccess:
    """验证 bundle_builder 对 root 使用 dict key 访问而非属性访问。"""

    def test_bundle_builder_uses_dict_access_on_root(self):
        """bundle_builder 对 root 使用 .get('node_id') 而非 .node_id。"""
        import inspect
        from src.core.knowledge_qa import bundle_builder

        source = inspect.getsource(bundle_builder._enhanced_lazy_graph_traversal)
        assert 'root.get("node_id")' in source
        assert "root.node_id" not in source

    @pytest.mark.asyncio
    async def test_dict_root_works_without_error(self):
        """get_roots 返回 dict 时，遍历正常工作不抛 AttributeError。"""
        from src.core.knowledge_qa.bundle_builder import _enhanced_lazy_graph_traversal

        uuid = "35dc539d-d9dc-40eb-8f2c-e7e502a783cd"
        # get_roots 返回纯 dict（与 HTTP 接口一致）
        mock_repo = _build_mock_community_repo({
            uuid: [_make_root("root_1", uuid)],
        })

        mock_hit = _make_hit("root_1", ["chunk_1"])

        async def mock_filter_graph_ready(book_ids):
            return [uuid]

        async def mock_explore(question, root_id, community_repo,
                               max_tokens=12000, entity_boost_names=None):
            return [mock_hit]

        with patch(
            "src.utils.http_client.HttpGraphAdapter",
            return_value=mock_repo,
        ), patch(
            "src.utils.http_client.RagHttpClient",
        ), patch(
            "httpx.AsyncClient",
        ), patch(
            "src.core.knowledge_qa.nodes.prefetch_context._filter_graph_ready",
            side_effect=mock_filter_graph_ready,
        ), patch(
            "src.core.knowledge_qa.graph.traversal.explore_community_tree",
            side_effect=mock_explore,
        ), patch(
            "src.core.knowledge_qa.graph.traversal.build_knowledge_context",
            return_value="mocked context",
        ):
            context, hit_count = await _enhanced_lazy_graph_traversal(
                question="测试问题",
                entity_seeds=[],
                matched_book_ids=[uuid],
                custom_entities=[],
            )

        # 不应抛出 AttributeError，正常返回结果
        assert hit_count == 1


# ══════════════════════════════════════════════════════════════════════════════
# Bug #5: 重复触发图构建 → 幂等检查
# ══════════════════════════════════════════════════════════════════════════════

class TestGraphBuildIdempotency:
    """验证 graph_ready=True 时跳过重复图构建。"""

    def test_run_graph_build_skips_when_graph_ready(self):
        """graph_ready=True 的文档不再触发图构建。"""
        import inspect
        from src.service.document_ingestion import chunking_indexing

        source = inspect.getsource(chunking_indexing._trigger_graph_build)
        assert "graph_ready" in source
        assert "跳过重复图构建" in source


# ══════════════════════════════════════════════════════════════════════════════
# 对比基线：prefetch_context 正确路径
# ══════════════════════════════════════════════════════════════════════════════

class TestPrefetchContextBaseline:
    """prefetch_context 作为正确实现的对比基线。"""

    def test_prefetch_context_has_graph_ready_filter(self):
        """prefetch_context.py 中正确调用了 _filter_graph_ready。"""
        import inspect
        from src.core.knowledge_qa.nodes import prefetch_context

        source = inspect.getsource(prefetch_context)
        assert "_filter_graph_ready" in source
        assert "await _filter_graph_ready" in source


# ══════════════════════════════════════════════════════════════════════════════
# SQL 查询条件完整性
# ══════════════════════════════════════════════════════════════════════════════

class TestGetRootsQueryCondition:
    """验证 get_roots 的查询条件覆盖了 parent_id + scope + book_id。"""

    def test_get_roots_filters_parent_id_null_scope_book_id(self):
        from src.repository.graph_repository import GraphCommunityRepository

        import inspect
        source = inspect.getsource(GraphCommunityRepository.get_roots)

        assert "parent_id" in source
        assert "scope" in source
        assert "book_id" in source
