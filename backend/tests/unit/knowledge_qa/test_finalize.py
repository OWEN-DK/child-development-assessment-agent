"""单元测试：finalize 汇总节点 (finalize.py)

覆盖：全部节完成、部分节缺失、partial 状态保留
"""

import pytest

from src.core.knowledge_qa.nodes.finalize import finalize_node
from src.schemas.knowledge_qa import KnowledgeQAState, SectionOutput


def _make_section(index: int) -> SectionOutput:
    """创建指定序号的测试节"""
    return SectionOutput(
        index=index,
        title=f"第{index}节",
        content=f"内容{index}",
        citations=[],
        structured_data={},
    )


def _make_state(sections: dict[int, SectionOutput] | None = None,
                errors: list[str] | None = None,
                partial: bool = False) -> KnowledgeQAState:
    """创建测试用 State 对象"""
    return KnowledgeQAState(
        question="测试问题",
        sections=sections or {},
        errors=errors or [],
        partial=partial,
    )


class TestFinalizeNode:
    """finalize 节点纯函数测试"""

    @pytest.mark.asyncio
    async def test_all_sections_present(self):
        """所有 5 节均存在时 → partial=False，errors 不新增"""
        sections = {i: _make_section(i) for i in range(1, 6)}
        state = _make_state(sections=sections)

        result = await finalize_node(state)

        assert result["partial"] is False
        assert result["errors"] == []
        assert result["current_step"] == ["completed"]

    @pytest.mark.asyncio
    async def test_missing_sections_partial(self):
        """缺少第 4、5 节时 → partial=True，errors 包含缺失信息"""
        sections = {i: _make_section(i) for i in range(1, 4)}
        state = _make_state(sections=sections)

        result = await finalize_node(state)

        assert result["partial"] is True
        assert len(result["errors"]) == 1
        assert "缺失节" in result["errors"][0]
        assert "4" in result["errors"][0]
        assert "5" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_already_partial_preserved(self):
        """state.partial=True 且所有节完整时 → partial=True（保留原状态）"""
        sections = {i: _make_section(i) for i in range(1, 6)}
        state = _make_state(sections=sections, partial=True)

        result = await finalize_node(state)

        # 即使无缺失节，partial=True 也应保留
        assert result["partial"] is True
        assert result["errors"] == []
