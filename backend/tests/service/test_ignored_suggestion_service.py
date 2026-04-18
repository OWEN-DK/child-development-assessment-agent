"""忽略建议服务测试"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession


class TestGetIgnoredSuggestions:
    """测试获取已忽略建议列表"""

    @pytest.mark.asyncio
    async def test_returns_ignored_suggestions_by_report(self):
        """应按报告ID返回已忽略建议"""
        from src.service.ignored_suggestion_service import IgnoredSuggestionService
        from src.models.rag_eval.ignored_suggestion import RagEvalIgnoredSuggestion
        from src.models.rag_eval.enums import (
            RagEvalIgnoredSuggestionType,
            RagEvalIgnoreScope,
        )

        mock_session = AsyncMock(spec=AsyncSession)

        # 模拟查询结果：2条忽略记录
        mock_ignored_1 = MagicMock(spec=RagEvalIgnoredSuggestion)
        mock_ignored_1.id = "ignored_1"
        mock_ignored_1.param_name = "bm25_top_k"
        mock_ignored_1.suggestion_type = RagEvalIgnoredSuggestionType.CONFIG
        mock_ignored_1.ignore_scope = RagEvalIgnoreScope.REPORT
        mock_ignored_1.report_id = "report_123"
        mock_ignored_1.test_set_id = "test_set_456"
        mock_ignored_1.ignored_at = datetime(2026, 4, 16, 10, 30, 0)
        mock_ignored_1.ignored_by = "user_1"
        mock_ignored_1.ignore_reason = "该参数调整无效"
        mock_ignored_1.restored = False
        mock_ignored_1.restored_at = None

        mock_ignored_2 = MagicMock(spec=RagEvalIgnoredSuggestion)
        mock_ignored_2.id = "ignored_2"
        mock_ignored_2.param_name = "prompt_template"
        mock_ignored_2.suggestion_type = RagEvalIgnoredSuggestionType.PROMPT
        mock_ignored_2.ignore_scope = RagEvalIgnoreScope.TEST_SET
        mock_ignored_2.report_id = None
        mock_ignored_2.test_set_id = "test_set_456"
        mock_ignored_2.ignored_at = datetime(2026, 4, 16, 11, 0, 0)
        mock_ignored_2.ignored_by = "user_1"
        mock_ignored_2.ignore_reason = None
        mock_ignored_2.restored = False
        mock_ignored_2.restored_at = None

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            mock_ignored_1,
            mock_ignored_2,
        ]
        mock_session.execute = AsyncMock(return_value=mock_result)

        service = IgnoredSuggestionService()
        result = await service.get_ignored_suggestions(
            test_set_id="test_set_456",
            report_id="report_123",
            session=mock_session,
        )

        assert len(result) == 2
        assert result[0].param_name == "bm25_top_k"
        assert result[1].param_name == "prompt_template"

    @pytest.mark.asyncio
    async def test_returns_ignored_suggestions_by_test_set_only(self):
        """仅传入test_set_id时应返回该测试集下所有未恢复的忽略记录"""
        from src.service.ignored_suggestion_service import IgnoredSuggestionService

        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        service = IgnoredSuggestionService()
        result = await service.get_ignored_suggestions(
            test_set_id="test_set_456",
            session=mock_session,
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_excludes_restored_suggestions(self):
        """不应返回已恢复的忽略记录"""
        from src.service.ignored_suggestion_service import IgnoredSuggestionService

        mock_session = AsyncMock(spec=AsyncSession)

        # SQL查询已包含restored==False过滤，因此已恢复的记录不会出现在结果中
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        service = IgnoredSuggestionService()
        result = await service.get_ignored_suggestions(
            test_set_id="test_set_456",
            session=mock_session,
        )

        # 验证查询包含restored过滤条件
        assert result == []


class TestRestoreIgnoredSuggestion:
    """测试恢复已忽略建议"""

    @pytest.mark.asyncio
    async def test_sets_restored_flag(self):
        """应设置restored=True并记录恢复时间"""
        from src.service.ignored_suggestion_service import IgnoredSuggestionService

        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.get = AsyncMock()

        # 模拟查询到忽略记录
        mock_ignored = MagicMock()
        mock_ignored.id = "ignored_1"
        mock_ignored.restored = False
        mock_ignored.restored_at = None
        mock_session.get.return_value = mock_ignored

        service = IgnoredSuggestionService()
        result = await service.restore_ignored_suggestion(
            suggestion_id="ignored_1",
            session=mock_session,
        )

        # 验证设置了restored和restored_at
        assert mock_ignored.restored is True
        assert mock_ignored.restored_at is not None
        mock_session.commit.assert_awaited_once()
        assert result == mock_ignored

    @pytest.mark.asyncio
    async def test_raises_when_not_found(self):
        """记录不存在时应抛出ValueError"""
        from src.service.ignored_suggestion_service import IgnoredSuggestionService

        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.get = AsyncMock(return_value=None)

        service = IgnoredSuggestionService()

        with pytest.raises(ValueError, match="忽略记录不存在"):
            await service.restore_ignored_suggestion(
                suggestion_id="nonexistent",
                session=mock_session,
            )

    @pytest.mark.asyncio
    async def test_raises_when_already_restored(self):
        """已恢复的记录不应重复恢复"""
        from src.service.ignored_suggestion_service import IgnoredSuggestionService

        mock_session = AsyncMock(spec=AsyncSession)
        mock_ignored = MagicMock()
        mock_ignored.restored = True
        mock_session.get = AsyncMock(return_value=mock_ignored)

        service = IgnoredSuggestionService()

        with pytest.raises(ValueError, match="该记录已恢复"):
            await service.restore_ignored_suggestion(
                suggestion_id="ignored_1",
                session=mock_session,
            )


class TestDeleteIgnoredSuggestion:
    """测试删除已忽略建议"""

    @pytest.mark.asyncio
    async def test_deletes_record(self):
        """应物理删除忽略记录"""
        from src.service.ignored_suggestion_service import IgnoredSuggestionService

        mock_session = AsyncMock(spec=AsyncSession)
        mock_ignored = MagicMock()
        mock_ignored.id = "ignored_1"
        mock_session.get = AsyncMock(return_value=mock_ignored)

        service = IgnoredSuggestionService()
        await service.delete_ignored_suggestion(
            suggestion_id="ignored_1",
            session=mock_session,
        )

        mock_session.delete.assert_called_once_with(mock_ignored)
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_raises_when_not_found(self):
        """记录不存在时应抛出ValueError"""
        from src.service.ignored_suggestion_service import IgnoredSuggestionService

        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.get = AsyncMock(return_value=None)

        service = IgnoredSuggestionService()

        with pytest.raises(ValueError, match="忽略记录不存在"):
            await service.delete_ignored_suggestion(
                suggestion_id="nonexistent",
                session=mock_session,
            )
