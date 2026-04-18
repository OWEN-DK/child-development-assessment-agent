"""
提示词 Fallback 机制测试

验证 PromptManager 在数据库不可用时的降级能力
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.core.prompt.manager import PromptManager


class TestPromptFallback:
    """测试提示词 Fallback 机制"""

    @pytest.fixture
    def prompt_manager(self):
        """创建 PromptManager 实例"""
        manager = PromptManager()
        # Mock cache
        manager.cache = AsyncMock()
        manager.cache.get = AsyncMock(return_value=None)
        manager.cache.set_with_jitter = AsyncMock()
        return manager

    def test_get_fallback_prompt_known_key(self, prompt_manager):
        """测试已知 key 的 fallback 提示词"""
        # 测试 assessment_system
        result = prompt_manager._get_fallback_prompt("assessment_system")
        assert "儿童发展评估专家" in result

        # 测试 reporting_system
        result = prompt_manager._get_fallback_prompt("reporting_system")
        assert "资深儿童发展专家" in result or "感觉统合" in result

        # 测试 validation
        result = prompt_manager._get_fallback_prompt("validation")
        assert "儿童发展数据校验" in result

    def test_get_fallback_prompt_unknown_key(self, prompt_manager):
        """测试未知 key 返回默认 fallback"""
        result = prompt_manager._get_fallback_prompt("nonexistent_key")
        assert result == "You are a helpful assistant."

    def test_get_fallback_prompt_all_keys(self, prompt_manager):
        """测试所有已配置的 fallback key"""
        known_keys = [
            "rag_query_rewrite",
            "synonym_expansion",
            "metadata_extraction",
            "test_case_generation",
            "validation",
            "intensity_inference",
            "category_inference",
            "child_assessment",
            "assessment_system",
            "scoring",
            "scoring_system",
            "report_generation",
            "reporting_system",
        ]

        for key in known_keys:
            result = prompt_manager._get_fallback_prompt(key)
            # 不应该返回默认英文提示词
            assert result != "You are a helpful assistant.", (
                f"Key '{key}' 没有配置 fallback"
            )

    @pytest.mark.asyncio
    async def test_fallback_when_database_unavailable(self, prompt_manager):
        """测试数据库不可用时降级到 fallback"""
        # Mock repository 抛出异常
        with patch.object(prompt_manager, "_get_repos") as mock_repos:
            mock_version_repo = AsyncMock()
            mock_version_repo.get_latest_version = AsyncMock(
                side_effect=Exception("Database connection failed")
            )
            mock_repos.return_value = (mock_version_repo, None)

            # 应该降级到 fallback
            result = await prompt_manager.get_prompt("assessment_system")

            # 验证返回了 fallback 内容
            assert "儿童发展评估专家" in result

    @pytest.mark.asyncio
    async def test_fallback_with_variables(self, prompt_manager):
        """测试 fallback 提示词也能渲染变量"""
        # Mock repository 返回 None（提示词不存在）
        with patch.object(prompt_manager, "_get_repos") as mock_repos:
            mock_version_repo = AsyncMock()
            mock_version_repo.get_latest_version = AsyncMock(return_value=None)
            mock_repos.return_value = (mock_version_repo, None)

            # 使用 intensity_inference 的 fallback，它包含 {age} 和 {activity_name}
            result = await prompt_manager.get_prompt(
                "intensity_inference", variables={"age": 5, "activity_name": "跑步"}
            )

            # 验证变量被渲染
            assert "5" in result
            assert "跑步" in result

    @pytest.mark.asyncio
    async def test_fallback_preserves_formatting(self, prompt_manager):
        """测试 fallback 提示词保留原始格式"""
        with patch.object(prompt_manager, "_get_repos") as mock_repos:
            mock_version_repo = AsyncMock()
            mock_version_repo.get_latest_version = AsyncMock(return_value=None)
            mock_repos.return_value = (mock_version_repo, None)

            result = await prompt_manager.get_prompt("assessment_system")

            # 验证保留了 JSON 格式说明
            assert "{" in result
            assert "}" in result
            assert "vestibular_system" in result

    def test_fallback_prompts_not_empty(self, prompt_manager):
        """测试所有 fallback 提示词非空"""
        known_keys = [
            "rag_query_rewrite",
            "synonym_expansion",
            "metadata_extraction",
            "test_case_generation",
            "validation",
            "intensity_inference",
            "category_inference",
            "child_assessment",
            "assessment_system",
            "scoring",
            "scoring_system",
            "report_generation",
            "reporting_system",
        ]

        for key in known_keys:
            result = prompt_manager._get_fallback_prompt(key)
            assert len(result) > 10, f"Key '{key}' 的 fallback 提示词过短"

    def test_fallback_prompts_in_chinese(self, prompt_manager):
        """测试 fallback 提示词包含中文内容"""
        known_keys = [
            "assessment_system",
            "reporting_system",
            "validation",
            "intensity_inference",
            "category_inference",
        ]

        for key in known_keys:
            result = prompt_manager._get_fallback_prompt(key)
            # 检查是否包含中文字符
            has_chinese = any("\u4e00" <= char <= "\u9fff" for char in result)
            assert has_chinese, f"Key '{key}' 的 fallback 提示词不包含中文"
