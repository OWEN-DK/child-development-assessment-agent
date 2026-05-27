"""单元测试：层级遍历与知识上下文构建 (traversal.py)

覆盖：build_knowledge_context（不依赖 LLM 的纯逻辑部分）
"""

import pytest

from src.core.knowledge_qa.graph.traversal import TraversalHit, build_knowledge_context


class TestBuildKnowledgeContext:
    """知识上下文构建测试"""

    @pytest.mark.asyncio
    async def test_empty_hits(self):
        """空命中列表应返回空字符串"""
        result = await build_knowledge_context(question="测试", hits=[])
        assert result == ""

    @pytest.mark.asyncio
    async def test_basic_context_structure(self):
        """应生成包含社区信息的 Markdown 上下文"""
        hits = [
            TraversalHit(
                node_id="leaf_0",
                label="[症状] 前庭觉失调 + 注意力不集中",
                entity_names=["前庭觉失调", "注意力不集中", "感觉统合"],
                chunk_ids=["c1", "c2"],
            ),
        ]

        result = await build_knowledge_context(
            question="4岁男孩注意力不集中怎么办",
            hits=hits,
        )

        assert "知识上下文" in result
        assert "前庭觉失调" in result
        assert "注意力不集中" in result
        assert "社区" in result

    @pytest.mark.asyncio
    async def test_multiple_communities(self):
        """多个社区应分别输出"""
        hits = [
            TraversalHit(
                node_id="leaf_0",
                label="社区A",
                entity_names=["概念A"],
                chunk_ids=["c1"],
            ),
            TraversalHit(
                node_id="leaf_1",
                label="社区B",
                entity_names=["概念B"],
                chunk_ids=["c2"],
            ),
        ]

        result = await build_knowledge_context(question="测试", hits=hits)

        assert "社区A" in result
        assert "社区B" in result

    @pytest.mark.asyncio
    async def test_with_chunk_loader(self):
        """提供 chunk_loader 时应输出原文片段"""
        hits = [
            TraversalHit(
                node_id="leaf_0",
                label="测试社区",
                entity_names=["概念A"],
                chunk_ids=["c1", "c2"],
            ),
        ]

        async def mock_loader(chunk_ids):
            return {
                "c1": "前庭系统是大脑的交通总指挥，负责整合来自全身的平衡信息。",
                "c2": "临床观察发现，约70%的注意力缺陷儿童伴有前庭功能异常。",
            }

        result = await build_knowledge_context(
            question="测试",
            hits=hits,
            chunk_loader=mock_loader,
        )

        assert "前庭系统" in result
        assert "70%" in result

    @pytest.mark.asyncio
    async def test_chunk_loader_failure_graceful(self):
        """chunk_loader 失败时应降级到仅社区元信息"""
        hits = [
            TraversalHit(
                node_id="leaf_0",
                label="测试社区",
                entity_names=["概念A"],
                chunk_ids=["c1"],
            ),
        ]

        async def failing_loader(chunk_ids):
            raise RuntimeError("模拟加载失败")

        result = await build_knowledge_context(
            question="测试",
            hits=hits,
            chunk_loader=failing_loader,
        )

        # 应仍然有社区信息，只是没有原文片段
        assert "测试社区" in result
        assert "概念A" in result

    @pytest.mark.asyncio
    async def test_many_entity_names_truncated(self):
        """实体名超过 8 个时应截断显示"""
        hits = [
            TraversalHit(
                node_id="leaf_0",
                label="大社区",
                entity_names=[f"概念{i}" for i in range(15)],
                chunk_ids=["c1"],
            ),
        ]

        result = await build_knowledge_context(question="测试", hits=hits)

        assert "等 15 个" in result

    @pytest.mark.asyncio
    async def test_no_entity_names(self):
        """无实体名时不应异常"""
        hits = [
            TraversalHit(
                node_id="leaf_0",
                label="空社区",
                entity_names=[],
                chunk_ids=["c1"],
            ),
        ]

        result = await build_knowledge_context(question="测试", hits=hits)
        assert "空社区" in result


class TestTraversalHit:
    """TraversalHit 数据类测试"""

    def test_default_values(self):
        """应有正确的默认值"""
        hit = TraversalHit(node_id="test", label="测试")
        assert hit.entity_names == []
        assert hit.chunk_ids == []

    def test_with_values(self):
        """应正确存储传入值"""
        hit = TraversalHit(
            node_id="leaf_0",
            label="测试社区",
            entity_names=["A", "B"],
            chunk_ids=["c1", "c2"],
        )
        assert hit.node_id == "leaf_0"
        assert len(hit.entity_names) == 2
        assert len(hit.chunk_ids) == 2
