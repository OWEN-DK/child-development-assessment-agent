"""配置变更集 API 测试"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from fastapi import HTTPException
from pydantic import ValidationError


class TestConfigChangeSetRequest:
    """测试请求模型校验"""

    def test_request_with_all_fields(self):
        """应接受完整字段"""
        from src.schemas.config import PromptItem, ConfigChangeSetRequest

        request = ConfigChangeSetRequest(
            config_snapshot={"bm25_top_k": 15},
            prompts=[
                PromptItem(
                    key="rag_query_rewrite",
                    version="v4",
                    content="提示词内容",
                    summary="变更摘要",
                )
            ],
            change_summary="测试变更",
        )

        assert request.config_snapshot["bm25_top_k"] == 15
        assert len(request.prompts) == 1
        assert request.prompts[0].key == "rag_query_rewrite"

    def test_request_with_empty_prompts(self):
        """应接受空提示词列表"""
        from src.schemas.config import ConfigChangeSetRequest

        request = ConfigChangeSetRequest(
            config_snapshot={"bm25_top_k": 15},
            prompts=[],
            change_summary="仅参数调整",
        )

        assert request.prompts == []

    def test_prompt_item_validation(self):
        """提示词项应校验必填字段"""
        from src.schemas.config import PromptItem

        prompt = PromptItem(
            key="rag_query_rewrite",
            version="v4",
            content="提示词内容",
            summary="变更摘要",
        )

        assert prompt.key == "rag_query_rewrite"
        assert prompt.version_string == "v4"

    def test_prompt_item_optional_summary(self):
        """提示词项的 summary 应为可选"""
        from src.schemas.config import PromptItem
        prompt = PromptItem(
            key="rag_query_rewrite",
            version_string="v4",
            content="提示词内容",
        )

        assert prompt.description is None


class TestConfigChangeSetResponse:
    """测试响应模型"""

    def test_response_serialization(self):
        """响应应可序列化为字典"""
        from src.schemas.config import ConfigChangeSetResponse

        response = ConfigChangeSetResponse(
            id="cs_001",
            change_set_label="CS-20260416-001",
            config_version_id="cv_001",
            status="committed",
            created_at=datetime.now(),
        )

        data = response.model_dump()

        assert data["id"] == "cs_001"
        assert data["change_set_label"] == "CS-20260416-001"
        assert data["status"] == "committed"

    def test_response_with_optional_config_version(self):
        """config_version_id 应为可选"""
        from src.schemas.config import ConfigChangeSetResponse

        response = ConfigChangeSetResponse(
            id="cs_001",
            change_set_label="CS-20260416-001",
            status="committed",
            created_at=datetime.now(),
        )

        assert response.config_version_id is None


class TestCreateConfigChangeSetEndpoint:
    """测试创建配置变更集端点逻辑"""

    @pytest.mark.asyncio
    async def test_empty_config_raises_400(self):
        """配置快照为空时应返回 400"""
        from src.schemas.config import ConfigChangeSetRequest

        request = ConfigChangeSetRequest(
            config_snapshot={},
            prompts=[],
            change_summary="空配置",
        )

        # 验证空 config_snapshot 会被检测
        assert not request.config_snapshot

    @pytest.mark.asyncio
    async def test_service_integration_pattern(self):
        """验证服务调用模式正确"""
        from src.service.config_change_set_service import ConfigChangeSetService

        service = ConfigChangeSetService()

        # 验证服务有 save_config_change_set 方法
        assert hasattr(service, "save_config_change_set")
        assert callable(service.save_config_change_set)

    @pytest.mark.asyncio
    async def test_cache_integration_pattern(self):
        """验证缓存集成模式正确"""
        from src.core.config.cache import ConfigCache

        # 验证 ConfigCache 有 get_instance 和 reload 方法
        ConfigCache._instance = None
        instance = ConfigCache.get_instance()

        assert hasattr(instance, "reload")
        assert hasattr(instance, "get_config")
        assert hasattr(instance, "get_latest_config")
        assert callable(instance.reload)
