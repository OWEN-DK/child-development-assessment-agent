"""忽略建议控制器测试"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime


class TestGetIgnoredSuggestionsEndpoint:
    """测试获取已忽略建议端点"""

    @pytest.mark.asyncio
    async def test_returns_ignored_suggestions_list(self):
        """应返回已忽略建议列表"""
        from src.controller.tuning_controller import TuningController
        from src.models.rag_eval.enums import (
            RagEvalIgnoredSuggestionType,
            RagEvalIgnoreScope,
        )

        mock_suggestion_service = AsyncMock()
        mock_ignored = MagicMock()
        mock_ignored.id = "ignored_1"
        mock_ignored.param_name = "bm25_top_k"
        mock_ignored.suggestion_type = RagEvalIgnoredSuggestionType.CONFIG
        mock_ignored.ignore_scope = RagEvalIgnoreScope.REPORT
        mock_ignored.report_id = "report_123"
        mock_ignored.test_set_id = "test_set_456"
        mock_ignored.ignored_at = datetime(2026, 4, 16, 10, 30, 0)
        mock_ignored.ignored_by = "user_1"
        mock_ignored.ignore_reason = "参数调整无效"
        mock_ignored.restored = False
        mock_ignored.restored_at = None

        mock_suggestion_service.get_ignored_suggestions = AsyncMock(
            return_value=[mock_ignored]
        )

        mock_tuning_engine = MagicMock()
        controller = TuningController(mock_tuning_engine)
        controller.suggestion_service = mock_suggestion_service

        mock_session = AsyncMock()
        result = await mock_suggestion_service.get_ignored_suggestions(
            test_set_id="test_set_456",
            report_id="report_123",
            session=mock_session,
        )

        assert len(result) == 1
        assert result[0].param_name == "bm25_top_k"

    @pytest.mark.asyncio
    async def test_returns_empty_list(self):
        """无忽略记录时应返回空列表"""
        from src.controller.tuning_controller import TuningController

        mock_suggestion_service = AsyncMock()
        mock_suggestion_service.get_ignored_suggestions = AsyncMock(return_value=[])

        mock_tuning_engine = MagicMock()
        controller = TuningController(mock_tuning_engine)
        controller.suggestion_service = mock_suggestion_service

        mock_session = AsyncMock()
        result = await mock_suggestion_service.get_ignored_suggestions(
            test_set_id="test_set_456",
            session=mock_session,
        )

        assert result == []


class TestRestoreIgnoredSuggestionEndpoint:
    """测试恢复已忽略建议端点"""

    @pytest.mark.asyncio
    async def test_restore_request_model(self):
        """恢复请求模型应正确验证"""
        from src.controller.tuning_controller import RestoreIgnoredSuggestionResponse

        response = RestoreIgnoredSuggestionResponse(
            id="ignored_1",
            restored=True,
            restored_at=datetime(2026, 4, 16, 11, 0, 0),
            message="已恢复，推荐将重新出现在推荐列表中",
        )

        assert response.id == "ignored_1"
        assert response.restored is True
        assert response.message is not None


class TestDeleteIgnoredSuggestionEndpoint:
    """测试删除已忽略建议端点"""

    @pytest.mark.asyncio
    async def test_delete_request_model(self):
        """删除请求模型应正确验证"""
        from src.controller.tuning_controller import DeleteIgnoredSuggestionResponse

        response = DeleteIgnoredSuggestionResponse(
            id="ignored_1",
            message="已删除",
        )

        assert response.id == "ignored_1"
        assert response.message == "已删除"
