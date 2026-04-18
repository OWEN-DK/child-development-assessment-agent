"""Phase 4.4: 配置健康诊断 API 测试

测试 /health 端点和 ConfigHealthService 服务
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.controller.config_health_controller import (
    run_health_diagnostic,
    HealthDiagnosticRequest,
)
from src.service.config_health_service import ConfigHealthService


class TestHealthDiagnosticEndpoint:
    """测试健康诊断端点"""

    @pytest.mark.asyncio
    async def test_health_diagnostic_success(self):
        """测试健康诊断成功"""
        request = HealthDiagnosticRequest(
            config={
                "llm_providers": {"dashscope": {"api_key": "sk-test"}},
                "llm_scene_configs": {
                    "assessment": {"model": "qwen-plus", "provider": "dashscope"}
                },
                "rag_retrieval": {
                    "strategy": "hybrid",
                    "chunk_size": 512,
                    "score_threshold": 0.3,
                },
                "rules": {"validation": {}},
                "system": {"logging": {}, "paths": {}},
            }
        )

        with patch.object(
            ConfigHealthService, "diagnose", new_callable=AsyncMock
        ) as mock_diagnose:
            mock_diagnose.return_value = {
                "score": 85,
                "score_basis": "基于 LLM 诊断",
                "suggestions": [],
            }

            with patch("src.service.cache_service.cache_service") as mock_cache:
                mock_cache.get = AsyncMock(return_value=None)
                mock_cache.set = AsyncMock()

                response = await run_health_diagnostic(request)

                assert response.score == 85
                assert response.score_basis == "基于 LLM 诊断"
                assert response.suggestions == []

                # 验证缓存设置
                mock_cache.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_diagnostic_cache_hit(self):
        """测试健康诊断缓存命中"""
        request = HealthDiagnosticRequest(config={"llm_providers": {}})

        cached_result = {
            "score": 70,
            "score_basis": "缓存结果",
            "suggestions": [],
        }

        with patch("src.service.cache_service.cache_service") as mock_cache:
            import json

            mock_cache.get = AsyncMock(return_value=json.dumps(cached_result))

            response = await run_health_diagnostic(request)

            # 缓存命中时返回 dict，需要转换为响应对象
            assert response["score"] == 70
            assert response["score_basis"] == "缓存结果"

    @pytest.mark.asyncio
    async def test_health_diagnostic_fallback_to_local_score(self):
        """测试健康诊断降级到本地规则评分"""
        request = HealthDiagnosticRequest(config={})

        with patch.object(
            ConfigHealthService, "diagnose", new_callable=AsyncMock
        ) as mock_diagnose:
            mock_diagnose.side_effect = Exception("LLM 调用失败")

            with patch("src.service.cache_service.cache_service") as mock_cache:
                mock_cache.get = AsyncMock(return_value=None)

                response = await run_health_diagnostic(request)

                assert response.score == 0  # 空配置得 0 分
                assert "本地规则评分" in response.score_basis
