"""调优建议服务测试"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession


class TestGetActiveSuggestions:
    """测试获取未忽略的调优建议"""

    @pytest.mark.asyncio
    async def test_returns_suggestions_excluding_ignored(self):
        """应返回未被忽略的建议列表"""
        from src.service.tuning_suggestion_service import TuningSuggestionService
        from src.models.rag_eval.tuning_suggestion import RagEvalTuningSuggestionRecord
        from src.models.rag_eval.ignored_suggestion import RagEvalIgnoredSuggestion
        from src.models.rag_eval.enums import RagEvalSuggestionSource

        # 模拟数据库会话
        mock_session = AsyncMock(spec=AsyncSession)

        # 模拟查询结果：2条建议，其中1条被忽略
        mock_suggestion_1 = MagicMock(spec=RagEvalTuningSuggestionRecord)
        mock_suggestion_1.id = "suggestion_1"
        mock_suggestion_1.param_name = "chunk_size"
        mock_suggestion_1.current_value = {"value": 512}
        mock_suggestion_1.suggested_value = {"value": 1024}
        mock_suggestion_1.action = "increase"
        mock_suggestion_1.reason = "增大chunk_size以提升上下文完整性"
        mock_suggestion_1.priority = "high"
        mock_suggestion_1.source = RagEvalSuggestionSource.RULE_ENGINE
        mock_suggestion_1.applied = False

        mock_suggestion_2 = MagicMock(spec=RagEvalTuningSuggestionRecord)
        mock_suggestion_2.id = "suggestion_2"
        mock_suggestion_2.param_name = "top_k"
        mock_suggestion_2.current_value = {"value": 5}
        mock_suggestion_2.suggested_value = {"value": 10}
        mock_suggestion_2.action = "increase"
        mock_suggestion_2.reason = "增加top_k以提升召回率"
        mock_suggestion_2.priority = "medium"
        mock_suggestion_2.source = RagEvalSuggestionSource.LLM
        mock_suggestion_2.applied = False

        # 模拟查询返回所有建议
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            mock_suggestion_1,
            mock_suggestion_2,
        ]

        # 模拟忽略记录：suggestion_2被忽略
        mock_ignored_result = MagicMock()
        mock_ignored = MagicMock(spec=RagEvalIgnoredSuggestion)
        mock_ignored.param_name = "top_k"
        mock_ignored.restored = False
        from src.models.rag_eval.enums import RagEvalIgnoreScope

        mock_ignored.ignore_scope = RagEvalIgnoreScope.TEST_SET
        mock_ignored_result.scalars.return_value.all.return_value = [mock_ignored]

        mock_session.execute = AsyncMock(side_effect=[mock_result, mock_ignored_result])

        service = TuningSuggestionService()
        report_id = "report_123"
        test_set_id = "test_set_456"

        result = await service.get_active_suggestions(
            report_id, test_set_id, mock_session
        )

        # 应只返回未被忽略的建议
        assert len(result) == 1
        assert result[0].id == "suggestion_1"

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_suggestions(self):
        """无建议时应返回空列表"""
        from src.service.tuning_suggestion_service import TuningSuggestionService

        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []

        mock_ignored_result = MagicMock()
        mock_ignored_result.scalars.return_value.all.return_value = []

        mock_session.execute = AsyncMock(side_effect=[mock_result, mock_ignored_result])

        service = TuningSuggestionService()
        result = await service.get_active_suggestions(
            "report_1", "test_set_1", mock_session
        )

        assert result == []


class TestIgnoreSuggestion:
    """测试忽略调优建议"""

    @pytest.mark.asyncio
    async def test_creates_ignored_record(self):
        """应创建忽略记录"""
        from src.service import tuning_suggestion_service
        from src.models.rag_eval.enums import RagEvalIgnoreScope

        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        # Mock模型实例化
        mock_record = MagicMock()
        mock_record.test_set_id = "test_set_456"
        mock_record.report_id = "report_789"
        mock_record.param_name = "chunk_size"
        mock_record.ignore_scope = RagEvalIgnoreScope.TEST_SET
        mock_record.ignore_reason = "该参数调整对当前场景无效"
        mock_record.restored = False

        with patch.object(
            tuning_suggestion_service,
            "RagEvalIgnoredSuggestion",
            return_value=mock_record,
        ):
            service = tuning_suggestion_service.TuningSuggestionService()
            await service.ignore_suggestion(
                suggestion_id="suggestion_123",
                scope=RagEvalIgnoreScope.TEST_SET,
                reason="该参数调整对当前场景无效",
                session=mock_session,
                test_set_id="test_set_456",
                report_id="report_789",
                param_name="chunk_size",
            )

        # 验证调用了add和commit
        mock_session.add.assert_called_once()
        mock_session.commit.assert_awaited_once()

        # 验证添加的记录属性正确
        added_record = mock_session.add.call_args[0][0]
        assert added_record.test_set_id == "test_set_456"
        assert added_record.report_id == "report_789"
        assert added_record.param_name == "chunk_size"
        assert added_record.ignore_scope == RagEvalIgnoreScope.TEST_SET

    @pytest.mark.asyncio
    async def test_ignore_with_report_scope(self):
        """report级别忽略应正确设置"""
        from src.service import tuning_suggestion_service
        from src.models.rag_eval.enums import RagEvalIgnoreScope

        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        mock_record = MagicMock()
        mock_record.ignore_scope = RagEvalIgnoreScope.REPORT

        with patch.object(
            tuning_suggestion_service,
            "RagEvalIgnoredSuggestion",
            return_value=mock_record,
        ):
            service = tuning_suggestion_service.TuningSuggestionService()
            await service.ignore_suggestion(
                suggestion_id="suggestion_1",
                scope=RagEvalIgnoreScope.REPORT,
                reason="仅当前报告忽略",
                session=mock_session,
                test_set_id="test_set_1",
                report_id="report_1",
                param_name="top_k",
            )

        added_record = mock_session.add.call_args[0][0]
        assert added_record.ignore_scope == RagEvalIgnoreScope.REPORT
