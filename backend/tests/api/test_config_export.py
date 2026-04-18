"""Phase 4.4: 配置校验、导入导出 API 测试

测试 /validate, /export, /import 端点
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime
from fastapi import HTTPException


class TestConfigValidateEndpoint:
    """测试配置校验端点"""

    @pytest.mark.asyncio
    async def test_validate_config_valid(self):
        """测试配置校验通过"""
        from src.controller.config_controller import (
            validate_config,
            ConfigValidateRequest,
        )

        request = ConfigValidateRequest(
            config={
                "llm_providers": {"dashscope": {"api_key": "sk-test"}},
            }
        )

        with patch(
            "src.core.llm.config_validator.LLMConfigValidator"
        ) as mock_validator_class:
            mock_validator = MagicMock()
            mock_validator.validate = MagicMock(return_value=[])
            mock_validator_class.return_value = mock_validator

            response = await validate_config(request)

            assert response.valid is True
            assert len(response.errors) == 0

    @pytest.mark.asyncio
    async def test_validate_config_with_errors(self):
        """测试配置校验失败"""
        from src.controller.config_controller import (
            validate_config,
            ConfigValidateRequest,
        )

        request = ConfigValidateRequest(config={})

        with patch(
            "src.core.llm.config_validator.LLMConfigValidator"
        ) as mock_validator_class:
            mock_validator = MagicMock()
            mock_validator.validate = MagicMock(
                return_value=[
                    {
                        "field": "llm_providers",
                        "message": "LLM 提供商未配置",
                        "severity": "error",
                    }
                ]
            )
            mock_validator_class.return_value = mock_validator

            response = await validate_config(request)

            assert response.valid is False
            assert len(response.errors) == 1
            assert response.errors[0].field == "llm_providers"

    @pytest.mark.asyncio
    async def test_validate_config_exception(self):
        """测试配置校验异常"""
        from src.controller.config_controller import (
            validate_config,
            ConfigValidateRequest,
        )

        request = ConfigValidateRequest(config={})

        with patch(
            "src.core.llm.config_validator.LLMConfigValidator"
        ) as mock_validator_class:
            mock_validator = MagicMock()
            mock_validator.validate = MagicMock(
                side_effect=Exception("校验器初始化失败")
            )
            mock_validator_class.return_value = mock_validator

            response = await validate_config(request)

            assert response.valid is False
            assert len(response.errors) == 1
            assert response.errors[0].field == "config"


class TestConfigExportEndpoint:
    """测试配置导出端点"""

    @pytest.mark.asyncio
    async def test_export_current_config(self):
        """测试导出当前配置"""
        from src.controller.config_controller import export_config

        mock_user = MagicMock()
        mock_user.username = "testuser"

        mock_version = MagicMock()
        mock_version.id = "v_current_001"

        with patch("src.controller.config_controller.config_manager") as mock_manager:
            mock_manager.current_version = mock_version
            mock_manager.current_config = {"llm_providers": {"dashscope": {}}}
            mock_manager.current_version_id = "v_current_001"

            response = await export_config(version_id=None, current_user=mock_user)

            assert response.version_id == "v_current_001"
            assert "llm_providers" in response.config

    @pytest.mark.asyncio
    async def test_export_specific_version(self):
        """测试导出指定版本配置"""
        from src.controller.config_controller import export_config

        mock_user = MagicMock()
        mock_user.username = "testuser"

        with patch("src.controller.config_controller.config_manager") as mock_manager:
            mock_manager.get_version = AsyncMock(
                return_value={
                    "config_snapshot": {"llm_providers": {"openai": {}}},
                }
            )

            response = await export_config(
                version_id="v_old_001", current_user=mock_user
            )

            assert response.version_id == "v_old_001"
            assert "llm_providers" in response.config

    @pytest.mark.asyncio
    async def test_export_version_not_found(self):
        """测试导出不存在的版本"""
        from src.controller.config_controller import export_config

        mock_user = MagicMock()
        mock_user.username = "testuser"

        with patch("src.controller.config_controller.config_manager") as mock_manager:
            mock_manager.get_version = AsyncMock(return_value=None)

            with pytest.raises(HTTPException) as exc_info:
                await export_config(version_id="v_not_exist", current_user=mock_user)

            assert exc_info.value.status_code == 404
            assert "配置版本不存在" in exc_info.value.detail


class TestConfigImportEndpoint:
    """测试配置导入端点"""

    @pytest.mark.asyncio
    async def test_import_config_success(self):
        """测试配置导入成功"""
        from src.controller.config_controller import (
            import_config,
            ConfigImportRequest,
        )

        mock_user = MagicMock()
        mock_user.username = "testuser"

        request = ConfigImportRequest(
            config={"llm_providers": {"dashscope": {"api_key": "sk-test"}}},
            description="测试导入",
        )

        mock_version = MagicMock()
        mock_version.id = "v_import_001"
        mock_version.created_at = datetime.now()
        mock_version.created_by = "testuser"
        mock_version.description = "测试导入"
        mock_version.parent_version_id = None
        mock_version.is_factory_reset = False

        with patch("src.controller.config_controller.config_manager") as mock_manager:
            mock_manager.save_new_version = AsyncMock(return_value=mock_version)

            with patch(
                "src.core.llm.config_validator.LLMConfigValidator"
            ) as mock_validator_class:
                mock_validator = MagicMock()
                mock_validator.validate = MagicMock(return_value=[])
                mock_validator_class.return_value = mock_validator

                response = await import_config(request, mock_user)

                assert response.id == "v_import_001"
                assert response.description == "测试导入"

    @pytest.mark.asyncio
    async def test_import_config_validation_error(self):
        """测试配置导入校验失败"""
        from src.controller.config_controller import (
            import_config,
            ConfigImportRequest,
        )

        mock_user = MagicMock()
        mock_user.username = "testuser"

        request = ConfigImportRequest(config={})

        with patch(
            "src.core.llm.config_validator.LLMConfigValidator"
        ) as mock_validator_class:
            mock_validator = MagicMock()
            mock_validator.validate = MagicMock(
                return_value=[
                    {
                        "field": "llm_providers",
                        "message": "LLM 提供商未配置",
                        "severity": "error",
                    }
                ]
            )
            mock_validator_class.return_value = mock_validator

            with pytest.raises(HTTPException) as exc_info:
                await import_config(request, mock_user)

            assert exc_info.value.status_code == 400
            assert exc_info.value.detail["message"] == "配置校验失败"
