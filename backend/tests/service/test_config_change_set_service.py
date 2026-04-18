"""配置变更集服务测试"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession


def make_execute_mock(return_value):
    """创建正确的 execute mock：execute 是 async，但返回结果的方法是同步的"""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = return_value
    return AsyncMock(return_value=mock_result)


class TestSaveConfigChangeSet:
    """测试原子保存配置变更集"""

    @pytest.mark.asyncio
    async def test_save_config_change_set_rollback_on_failure(self):
        """数据库操作失败时应自动回滚"""
        from src.service.config_change_set_service import ConfigChangeSetService

        mock_session = MagicMock(spec=AsyncSession)

        # 模拟 begin 上下文管理器抛出异常
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(side_effect=Exception("数据库连接失败"))
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session.begin.return_value = mock_ctx

        # 设置 execute mock（虽然 begin 会先失败，但需要避免其他问题）
        mock_session.execute = make_execute_mock(0)

        service = ConfigChangeSetService()

        config_data = {"bm25_top_k": 15}
        prompt_data = []

        with pytest.raises(Exception, match="数据库连接失败"):
            await service.save_config_change_set(
                config_data=config_data,
                prompt_data=prompt_data,
                user_id="user_123",
                session=mock_session,
                change_summary="测试回滚",
            )

    @pytest.mark.asyncio
    async def test_save_config_change_set_transaction_flow(self):
        """验证服务方法签名和事务结构正确"""
        from src.service.config_change_set_service import ConfigChangeSetService
        import inspect

        service = ConfigChangeSetService()

        # 验证 save_config_change_set 方法存在且是 async
        assert hasattr(service, "save_config_change_set")
        assert inspect.iscoroutinefunction(service.save_config_change_set)

        # 验证方法签名包含必需参数
        sig = inspect.signature(service.save_config_change_set)
        params = list(sig.parameters.keys())
        assert "config_data" in params
        assert "prompt_data" in params
        assert "user_id" in params
        assert "session" in params

        # 验证使用了 async with session.begin() 模式
        # 通过检查源码确认事务结构
        source = inspect.getsource(service.save_config_change_set)
        assert "async with session.begin()" in source


class TestGenerateVersionLabel:
    """测试版本号生成"""

    @pytest.mark.asyncio
    async def test_generates_next_version_label(self):
        """应基于最大版本号生成下一个语义版本号"""
        from src.service.config_change_set_service import ConfigChangeSetService

        mock_session = MagicMock(spec=AsyncSession)
        mock_session.execute = make_execute_mock(3)

        service = ConfigChangeSetService()
        label = await service.generate_version_label(mock_session)

        assert label == "v4"

    @pytest.mark.asyncio
    async def test_generates_first_version_label(self):
        """无历史版本时应生成 v1"""
        from src.service.config_change_set_service import ConfigChangeSetService

        mock_session = MagicMock(spec=AsyncSession)
        mock_session.execute = make_execute_mock(None)

        service = ConfigChangeSetService()
        label = await service.generate_version_label(mock_session)

        assert label == "v1"


class TestGenerateConfigSummary:
    """测试配置变更摘要生成"""

    def test_generates_summary_for_param_changes(self):
        """应生成可读的参数变更摘要"""
        from src.service.config_change_set_service import ConfigChangeSetService

        service = ConfigChangeSetService()

        old_config = {"bm25_top_k": 10, "reranker_top_k": 5}
        new_config = {"bm25_top_k": 15, "reranker_top_k": 5}

        summary = service.generate_config_summary(new_config, old_config)

        assert "bm25_top_k" in summary
        assert "10" in summary
        assert "15" in summary

    def test_generates_summary_for_new_config(self):
        """无旧配置时应生成创建摘要"""
        from src.service.config_change_set_service import ConfigChangeSetService

        service = ConfigChangeSetService()

        new_config = {"bm25_top_k": 15}

        summary = service.generate_config_summary(new_config, None)

        assert "初始化" in summary or "bm25_top_k" in summary

    def test_generates_summary_for_no_changes(self):
        """配置无变更时应返回无变更提示"""
        from src.service.config_change_set_service import ConfigChangeSetService

        service = ConfigChangeSetService()

        config = {"bm25_top_k": 10}

        summary = service.generate_config_summary(config, config)

        assert "无变更" in summary


class TestNextPromptVersionNumber:
    """测试提示词版本号获取"""

    @pytest.mark.asyncio
    async def test_returns_next_version_number(self):
        """应返回该 prompt_key 下的下一个版本号"""
        from src.service.config_change_set_service import ConfigChangeSetService

        mock_session = MagicMock(spec=AsyncSession)
        mock_session.execute = make_execute_mock(4)

        service = ConfigChangeSetService()
        next_num = await service.next_prompt_version_number(
            mock_session, "rag_query_rewrite"
        )

        assert next_num == 5

    @pytest.mark.asyncio
    async def test_returns_one_for_new_prompt(self):
        """新 prompt_key 应返回 1"""
        from src.service.config_change_set_service import ConfigChangeSetService

        mock_session = MagicMock(spec=AsyncSession)
        mock_session.execute = make_execute_mock(None)

        service = ConfigChangeSetService()
        next_num = await service.next_prompt_version_number(
            mock_session, "new_prompt_key"
        )

        assert next_num == 1


class TestGenerateChangeSetLabel:
    """测试变更集标签生成"""

    @pytest.mark.asyncio
    async def test_generates_label_with_today_date(self):
        """应生成包含今天日期的标签"""
        from src.service.config_change_set_service import ConfigChangeSetService

        mock_session = MagicMock(spec=AsyncSession)
        mock_session.execute = make_execute_mock(0)

        service = ConfigChangeSetService()
        label = await service._generate_change_set_label(mock_session)

        today = datetime.now().strftime("%Y%m%d")
        assert label.startswith(f"CS-{today}-")
        assert label.endswith("001")

    @pytest.mark.asyncio
    async def test_generates_sequential_label(self):
        """已有变更集时应生成递增序号"""
        from src.service.config_change_set_service import ConfigChangeSetService

        mock_session = MagicMock(spec=AsyncSession)
        mock_session.execute = make_execute_mock(5)

        service = ConfigChangeSetService()
        label = await service._generate_change_set_label(mock_session)

        today = datetime.now().strftime("%Y%m%d")
        assert label == f"CS-{today}-006"
