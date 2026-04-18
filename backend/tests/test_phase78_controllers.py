"""Phase 7-8: API 控制器测试"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.controller.prompt_management_controller import PromptController
from src.controller.config_management_controller import ConfigManagementController


class TestPromptController:
    """测试提示词管理控制器"""

    def test_controller_init(self):
        """测试控制器初始化"""
        controller = PromptController()
        assert controller._impact_analyzer is not None

    def test_register_routes(self):
        """测试路由注册"""
        controller = PromptController()
        mock_app = MagicMock()
        controller.register_routes(mock_app)
        # 验证 include_router 被调用
        mock_app.include_router.assert_called_once()


class TestConfigManagementController:
    """测试配置管理控制器"""

    def test_controller_init(self):
        """测试控制器初始化"""
        controller = ConfigManagementController()
        assert controller._validation_engine is not None
        assert controller._conflict_detector is not None

    def test_register_routes(self):
        """测试路由注册"""
        controller = ConfigManagementController()
        mock_app = MagicMock()
        controller.register_routes(mock_app)
        # 验证 include_router 被调用
        mock_app.include_router.assert_called_once()
