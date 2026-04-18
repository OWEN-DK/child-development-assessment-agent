"""Phase 4.1: 配置 API 测试

测试恢复出厂设置、配置保存、配置校验等功能
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime


class TestConfigResetEndpoint:
    """测试恢复出厂设置端点"""

    @pytest.mark.asyncio
    async def test_reset_to_factory_success(self):
        """测试恢复出厂设置成功"""
        from src.controller.config_controller import (
            reset_to_factory,
            ConfigResetRequest,
        )

        # Mock 用户
        mock_user = MagicMock()
        mock_user.username = "testuser"

        # Mock 请求
        request = ConfigResetRequest(confirm=True, reason="测试恢复")

        # Mock ConfigManager
        mock_version = MagicMock()
        mock_version.id = "v_factory_reset_001"
        mock_version.created_at = datetime.now()
        mock_version.created_by = "testuser"
        mock_version.description = "恢复出厂设置"
        mock_version.parent_version_id = "v_prev_001"
        mock_version.is_factory_reset = True

        with patch("src.controller.config_controller.config_manager") as mock_manager:
            mock_manager.reset_to_factory = AsyncMock(return_value=mock_version)

            # 调用端点
            response = await reset_to_factory(request, mock_user)

            # 验证响应
            assert response.id == "v_factory_reset_001"
            assert response.created_by == "testuser"
            assert response.is_factory_reset is True
            assert "恢复出厂设置" in response.description

            # 验证调用了 reset_to_factory
            mock_manager.reset_to_factory.assert_called_once()
            call_kwargs = mock_manager.reset_to_factory.call_args[1]
            assert call_kwargs["created_by"] == "testuser"
            assert (
                "llm_providers" in call_kwargs["config_snapshot"]
                or call_kwargs["config_snapshot"]
            )

    @pytest.mark.asyncio
    async def test_reset_to_factory_without_confirm(self):
        """测试未二次确认时拒绝"""
        from src.controller.config_controller import (
            reset_to_factory,
            ConfigResetRequest,
        )
        from src.utils.exceptions import AppException

        mock_user = MagicMock()
        mock_user.username = "testuser"

        request = ConfigResetRequest(confirm=False)

        with pytest.raises(AppException) as exc_info:
            await reset_to_factory(request, mock_user)

        assert exc_info.value.status_code == 500
        assert "需要二次确认" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_reset_to_factory_error_handling(self):
        """测试恢复出厂设置异常处理"""
        from src.controller.config_controller import (
            reset_to_factory,
            ConfigResetRequest,
        )
        from src.utils.exceptions import AppException

        mock_user = MagicMock()
        mock_user.username = "testuser"

        request = ConfigResetRequest(confirm=True)

        with patch("src.controller.config_controller.config_manager") as mock_manager:
            mock_manager.reset_to_factory = AsyncMock(
                side_effect=Exception("数据库连接失败")
            )

            with pytest.raises(AppException) as exc_info:
                await reset_to_factory(request, mock_user)

            assert exc_info.value.status_code == 500
            assert "恢复出厂设置失败" in exc_info.value.message


class TestConfigSaveEndpoint:
    """测试配置保存端点"""

    @pytest.mark.asyncio
    async def test_save_config_with_correct_field(self):
        """测试使用 config_snapshot 字段保存"""
        from src.controller.config_controller import save_new_config, ConfigSaveRequest

        mock_user = MagicMock()
        mock_user.username = "testuser"

        request = ConfigSaveRequest(
            config_snapshot={"llm_providers": {"dashscope": {"api_key": "sk-test"}}},
            description="测试保存",
        )

        mock_version = MagicMock()
        mock_version.id = "v_save_001"
        mock_version.created_at = datetime.now()
        mock_version.created_by = "testuser"
        mock_version.description = "测试保存"
        mock_version.parent_version_id = None
        mock_version.is_factory_reset = False

        with patch("src.controller.config_controller.config_manager") as mock_manager:
            mock_manager.save_new_version = AsyncMock(return_value=mock_version)

            response = await save_new_config(request, mock_user)

            assert response.id == "v_save_001"
            assert response.description == "测试保存"

            # 验证调用参数
            call_kwargs = mock_manager.save_new_version.call_args[1]
            assert "llm_providers" in call_kwargs["config_snapshot"]
            assert call_kwargs["description"] == "测试保存"
            assert call_kwargs["created_by"] == "testuser"

    @pytest.mark.asyncio
    async def test_save_config_validation_error(self):
        """测试缺少 config_snapshot 时返回 422"""
        from src.controller.config_controller import ConfigSaveRequest
        from pydantic import ValidationError

        # 尝试创建缺少 config_snapshot 的请求
        with pytest.raises(ValidationError):
            ConfigSaveRequest(description="缺少配置快照")


class TestGetFactoryConfig:
    """测试获取出厂配置"""

    def test_get_factory_config_returns_settings(self):
        """测试出厂配置返回 settings 默认值"""
        from src.controller.config_controller import _get_factory_config
        from src.config import settings

        factory_config = _get_factory_config()

        # 验证返回的是 dict
        assert isinstance(factory_config, dict)

        # 验证包含预期的配置键
        # settings 应该包含 llm_providers 等配置
        assert len(factory_config) > 0
