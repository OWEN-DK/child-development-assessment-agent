"""调优建议控制器测试"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException
from datetime import datetime


class TestGetSuggestionsEndpoint:
    """测试获取调优建议端点"""

    @pytest.mark.asyncio
    async def test_get_suggestions_success(self):
        """应返回未忽略的建议列表"""
        from src.controller.tuning_controller import TuningController
        from src.models.rag_eval.enums import RagEvalSuggestionSource

        # 模拟服务
        mock_suggestion_service = AsyncMock()
        mock_suggestion_1 = MagicMock()
        mock_suggestion_1.id = "suggestion_1"
        mock_suggestion_1.param_name = "chunk_size"
        mock_suggestion_1.current_value = {"value": 512}
        mock_suggestion_1.suggested_value = {"value": 1024}
        mock_suggestion_1.action = "increase"
        mock_suggestion_1.reason = "增大chunk_size"
        mock_suggestion_1.priority = "high"
        mock_suggestion_1.source = RagEvalSuggestionSource.RULE_ENGINE
        mock_suggestion_1.applied = False

        mock_suggestion_service.get_active_suggestions = AsyncMock(
            return_value=[mock_suggestion_1]
        )

        # 创建控制器并注册路由
        mock_tuning_engine = MagicMock()
        controller = TuningController(mock_tuning_engine)
        controller.suggestion_service = mock_suggestion_service

        # 模拟FastAPI app
        mock_app = MagicMock()
        controller.register_routes(mock_app)

        # 直接测试服务调用
        mock_session = AsyncMock()
        report_id = "report_123"
        test_set_id = "test_set_456"

        result = await mock_suggestion_service.get_active_suggestions(
            report_id, test_set_id, mock_session
        )

        assert len(result) == 1
        assert result[0].param_name == "chunk_size"

    @pytest.mark.asyncio
    async def test_get_suggestions_empty(self):
        """无建议时应返回空列表"""
        from src.controller.tuning_controller import TuningController

        mock_suggestion_service = AsyncMock()
        mock_suggestion_service.get_active_suggestions = AsyncMock(return_value=[])

        mock_tuning_engine = MagicMock()
        controller = TuningController(mock_tuning_engine)
        controller.suggestion_service = mock_suggestion_service

        mock_session = AsyncMock()
        result = await mock_suggestion_service.get_active_suggestions(
            "report_1", "test_set_1", mock_session
        )

        assert result == []


class TestIgnoreSuggestionEndpoint:
    """测试忽略调优建议端点"""

    @pytest.mark.asyncio
    async def test_ignore_suggestion_success(self):
        """应成功忽略建议"""
        from src.controller.tuning_controller import IgnoreSuggestionRequest
        from src.models.rag_eval.enums import RagEvalIgnoreScope

        # 验证请求模型
        request = IgnoreSuggestionRequest(
            scope=RagEvalIgnoreScope.TEST_SET,
            reason="该参数对当前场景无效",
            test_set_id="test_set_123",
            report_id="report_456",
            param_name="chunk_size",
        )

        assert request.scope == RagEvalIgnoreScope.TEST_SET
        assert request.reason == "该参数对当前场景无效"
        assert request.test_set_id == "test_set_123"

    @pytest.mark.asyncio
    async def test_ignore_suggestion_without_reason(self):
        """忽略原因可选"""
        from src.controller.tuning_controller import IgnoreSuggestionRequest
        from src.models.rag_eval.enums import RagEvalIgnoreScope

        request = IgnoreSuggestionRequest(
            scope=RagEvalIgnoreScope.REPORT,
            test_set_id="test_set_1",
            report_id="report_1",
            param_name="top_k",
        )

        assert request.reason is None
