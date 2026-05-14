"""BM25 索引管理器单元测试"""
import pytest
import tempfile
import shutil
from pathlib import Path

from src.core.knowledge_base.bm25_index import BM25IndexManager


@pytest.fixture
def bm25_manager():
    """创建临时目录的 BM25 管理器"""
    tmp_dir = tempfile.mkdtemp()
    manager = BM25IndexManager(storage_dir=tmp_dir)
    yield manager
    shutil.rmtree(tmp_dir, ignore_errors=True)


class TestBM25IndexManager:
    """BM25 索引测试"""

    @pytest.mark.asyncio
    async def test_add_and_search(self, bm25_manager):
        """添加分块后可搜索"""
        chunks = [
            {"chunk_id": "c1", "content": "机器学习是人工智能的一个分支"},
            {"chunk_id": "c2", "content": "深度学习是机器学习的子集"},
            {"chunk_id": "c3", "content": "自然语言处理是AI的重要应用"},
        ]
        await bm25_manager.add_chunks("kb1", "t1", chunks)

        results = await bm25_manager.search("kb1", "t1", "机器学习", top_k=2)
        assert len(results) > 0
        assert results[0]["chunk_id"] in ("c1", "c2")

    @pytest.mark.asyncio
    async def test_remove_chunks(self, bm25_manager):
        """删除分块后搜索不到"""
        chunks = [
            {"chunk_id": "c1", "content": "机器学习是人工智能的一个分支"},
            {"chunk_id": "c2", "content": "深度学习是机器学习的子集"},
        ]
        await bm25_manager.add_chunks("kb1", "t1", chunks)
        await bm25_manager.remove_chunks("kb1", "t1", ["c1"])

        results = await bm25_manager.search("kb1", "t1", "机器学习", top_k=10)
        chunk_ids = [r["chunk_id"] for r in results]
        assert "c1" not in chunk_ids

    @pytest.mark.asyncio
    async def test_rebuild(self, bm25_manager):
        """全量重建"""
        chunks = [
            {"chunk_id": "c1", "content": "新内容一"},
            {"chunk_id": "c2", "content": "新内容二"},
        ]
        await bm25_manager.rebuild("kb1", "t1", chunks)

        results = await bm25_manager.search("kb1", "t1", "新内容", top_k=10)
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_delete_index(self, bm25_manager):
        """删除索引目录"""
        chunks = [{"chunk_id": "c1", "content": "test"}]
        await bm25_manager.add_chunks("kb1", "t1", chunks)

        await bm25_manager.delete_index("kb1", "t1")

        info = await bm25_manager.get_info("kb1", "t1")
        assert info["exists"] is False

    @pytest.mark.asyncio
    async def test_get_info(self, bm25_manager):
        """获取索引信息"""
        chunks = [
            {"chunk_id": "c1", "content": "test1"},
            {"chunk_id": "c2", "content": "test2"},
        ]
        await bm25_manager.add_chunks("kb1", "t1", chunks)

        info = await bm25_manager.get_info("kb1", "t1")
        assert info["exists"] is True
        assert info["chunk_count"] == 2

    @pytest.mark.asyncio
    async def test_search_empty_index(self, bm25_manager):
        """空索引搜索返回空"""
        results = await bm25_manager.search("kb_nonexist", "t1", "query", top_k=10)
        assert results == []

    @pytest.mark.asyncio
    async def test_incremental_add(self, bm25_manager):
        """增量添加不影响已有索引"""
        chunks1 = [{"chunk_id": "c1", "content": "第一批次"}]
        await bm25_manager.add_chunks("kb1", "t1", chunks1)

        chunks2 = [{"chunk_id": "c2", "content": "第二批次"}]
        await bm25_manager.add_chunks("kb1", "t1", chunks2)

        info = await bm25_manager.get_info("kb1", "t1")
        assert info["chunk_count"] == 2
