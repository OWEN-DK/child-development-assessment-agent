"""单元测试：引用核验节点 (verify_citations.py)

覆盖 verify_citations_node 的三条规则：
1. excerpt 非空且长度 >= 10 字符
2. chapter 非空
3. citation_id 格式正确（C + 3位数字），不规范自动补全
"""

import pytest
from unittest.mock import AsyncMock

from src.core.knowledge_qa.nodes.verify_citations import verify_citations_node
from src.schemas.knowledge_qa import (
    KnowledgeQAState,
    SectionOutput,
    clear_progress_context,
    set_progress_context,
)


def _make_section(
    index: int,
    title: str = "测试节",
    content: str = "正文内容",
    citations: list | None = None,
) -> SectionOutput:
    """快速构建测试用 SectionOutput"""
    return SectionOutput(
        index=index,
        title=title,
        content=content,
        citations=citations or [],
        structured_data={},
    )


def _make_citation(
    citation_id: str = "C001",
    excerpt: str = "这是一段足够长的引用内容，超过十个字符",
    chapter: str = "第3章",
    book_title: str = "测试书籍",
    **extra,
) -> dict:
    """快速构建测试用 citation 字典"""
    c = {
        "citation_id": citation_id,
        "excerpt": excerpt,
        "chapter": chapter,
        "book_title": book_title,
        "relevance": "与该节内容相关",
    }
    c.update(extra)
    return c


@pytest.fixture(autouse=True)
def _setup_context():
    """设置进度推送 ContextVar，防止 push_progress 失败"""
    set_progress_context(
        callback=AsyncMock(),
        task_id="test-task-id",
        task_type="test",
    )
    yield
    clear_progress_context()


# ==================== 引用核验测试 ====================


class TestVerifyCitationsNode:
    """verify_citations_node 测试"""

    @pytest.mark.asyncio
    async def test_valid_citations_pass_through(self):
        """所有引用均合规时，不应移除任何引用"""
        citations = [
            _make_citation(citation_id="C001", excerpt="合规引用内容，长度足够"),
            _make_citation(citation_id="C002", excerpt="另一段合规引用内容，同样足够长"),
        ]
        state = KnowledgeQAState(
            sections={1: _make_section(index=1, citations=citations)}
        )

        result = await verify_citations_node(state)

        assert len(result["sections"][1].citations) == 2
        assert result["sections"][1].citations[0]["citation_id"] == "C001"
        assert result["sections"][1].citations[1]["citation_id"] == "C002"
        # 不应有移除相关错误
        assert not any("核验剔除" in e for e in result["errors"])

    @pytest.mark.asyncio
    async def test_short_excerpt_removed(self):
        """excerpt 长度 < 10 字符的引用应被移除"""
        citations = [
            _make_citation(citation_id="C001", excerpt="合规的引用内容足够长"),
            _make_citation(citation_id="C002", excerpt="太短了"),  # 仅 3 字符
        ]
        state = KnowledgeQAState(
            sections={1: _make_section(index=1, citations=citations)}
        )

        result = await verify_citations_node(state)

        # 仅保留合规的 C001
        valid = result["sections"][1].citations
        assert len(valid) == 1
        assert valid[0]["citation_id"] == "C001"
        # errors 中应包含移除记录
        assert any("C002" in e for e in result["errors"])

    @pytest.mark.asyncio
    async def test_missing_chapter_removed(self):
        """chapter 为空的引用应被移除"""
        citations = [
            _make_citation(citation_id="C001", chapter="第2章", excerpt="合规的引用内容足够长"),
            _make_citation(citation_id="C002", chapter="", excerpt="章节为空但引用够长"),
            _make_citation(citation_id="C003", chapter="   ", excerpt="章节纯空格也应被移除"),
        ]
        state = KnowledgeQAState(
            sections={1: _make_section(index=1, citations=citations)}
        )

        result = await verify_citations_node(state)

        # 仅保留 chapter 非空的 C001
        valid = result["sections"][1].citations
        assert len(valid) == 1
        assert valid[0]["citation_id"] == "C001"

    @pytest.mark.asyncio
    async def test_citation_id_auto_fix(self):
        """不规范的 citation_id 应自动补全为 C1、C2 格式（放宽格式，不再要求 3 位数字）"""
        citations = [
            _make_citation(citation_id="ref1", excerpt="第一段合规引用内容足够长"),
            _make_citation(citation_id="1", excerpt="第二段合规引用内容同样足够长"),
        ]
        state = KnowledgeQAState(
            sections={1: _make_section(index=1, citations=citations)}
        )

        result = await verify_citations_node(state)

        # 节点仅在有引用被移除时才重建 SectionOutput；
        # 此处两条引用均有效（仅 ID 不规范），因此节点不会重建，
        # 但会在 errors 中记录自动补全信息
        assert any("自动补全" in e for e in result["errors"])
        # 验证自动补全映射正确：ref1 → C1, 1 → C2（无零填充）
        auto_fix_msg = next(e for e in result["errors"] if "自动补全" in e)
        assert "ref1 → C1" in auto_fix_msg
        assert "1 → C2" in auto_fix_msg

    @pytest.mark.asyncio
    async def test_section_with_all_citations_removed_gets_warning(self):
        """节内所有引用都被移除时，正文内容保持不变，仅记录错误日志"""
        citations = [
            _make_citation(citation_id="C001", excerpt="太短"),
            _make_citation(citation_id="C002", chapter=""),
        ]
        state = KnowledgeQAState(
            sections={1: _make_section(index=1, content="原始正文", citations=citations)}
        )

        result = await verify_citations_node(state)

        section = result["sections"][1]
        assert len(section.citations) == 0
        assert "原始正文" in section.content

    @pytest.mark.asyncio
    async def test_mixed_valid_invalid_citations(self):
        """混合有效和无效引用时，仅保留有效引用"""
        citations = [
            # 有效
            _make_citation(citation_id="C001", excerpt="合规引用，内容足够长", chapter="第1章"),
            # excerpt 太短
            _make_citation(citation_id="C002", excerpt="短", chapter="第2章"),
            # chapter 为空
            _make_citation(citation_id="C003", excerpt="足够长的引用内容", chapter=""),
            # 有效
            _make_citation(citation_id="C004", excerpt="另一段合规引用内容也足够长", chapter="第3章"),
        ]
        state = KnowledgeQAState(
            sections={1: _make_section(index=1, citations=citations)}
        )

        result = await verify_citations_node(state)

        valid = result["sections"][1].citations
        assert len(valid) == 2
        valid_ids = [c["citation_id"] for c in valid]
        assert "C001" in valid_ids
        assert "C004" in valid_ids
        # C002 和 C003 应被移除
        assert "C002" not in valid_ids
        assert "C003" not in valid_ids
