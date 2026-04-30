"""FaithfulnessChecker 测试 — 验证 answer_points 优先作为对比文本"""
import pytest
from unittest.mock import AsyncMock
from src.schemas.rag_eval.draft import DraftCreate


class TestFaithfulnessChecker:
    """验证 check() 优先使用 answer_points 拼接作为对比文本"""

    @pytest.mark.asyncio
    async def test_answer_points_used_as_compare_text(self):
        """answer_points 非空时应作为对比文本"""
        from src.service.rag_eval.draft.faithfulness_checker import FaithfulnessChecker
        checker = FaithfulnessChecker()
        checker._embedding_faithfulness_async = AsyncMock(return_value=0.85)

        draft = DraftCreate(
            query="测试问题",
            answer_points=["要点一", "要点二"],
            description="描述文本",
        )
        score = await checker.check(draft, "原文内容" * 100)

        call_args = checker._embedding_faithfulness_async.call_args
        compare_text = call_args[0][0]
        assert "要点一" in compare_text
        assert "要点二" in compare_text
        assert score == 0.85

    @pytest.mark.asyncio
    async def test_fallback_to_description(self):
        """answer_points 为空时应回退到 description"""
        from src.service.rag_eval.draft.faithfulness_checker import FaithfulnessChecker
        checker = FaithfulnessChecker()
        checker._embedding_faithfulness_async = AsyncMock(return_value=0.7)

        draft = DraftCreate(
            query="测试问题",
            answer_points=None,
            description="这是描述",
        )
        score = await checker.check(draft, "原文内容" * 100)

        call_args = checker._embedding_faithfulness_async.call_args
        compare_text = call_args[0][0]
        assert "这是描述" in compare_text

    @pytest.mark.asyncio
    async def test_empty_source_returns_default(self):
        """原文为空时返回默认分数 0.5"""
        from src.service.rag_eval.draft.faithfulness_checker import FaithfulnessChecker
        checker = FaithfulnessChecker()

        draft = DraftCreate(query="测试问题", answer_points=["要点"])
        score = await checker.check(draft, "")
        assert score == 0.5
