"""
提示词渲染测试

验证 PromptManager 的占位符渲染功能是否正确工作
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.core.prompt.manager import PromptManager


class TestPromptRendering:
    """测试提示词渲染功能"""

    @pytest.fixture
    def prompt_manager(self):
        """创建 PromptManager 实例"""
        manager = PromptManager()
        # Mock cache
        manager.cache = AsyncMock()
        manager.cache.get = AsyncMock(return_value=None)
        manager.cache.set_with_jitter = AsyncMock()
        return manager

    @pytest.mark.asyncio
    async def test_render_template_basic(self, prompt_manager):
        """测试基本占位符渲染"""
        template = "你好 {name}，你的年龄是 {age} 岁"
        variables = {"name": "小明", "age": 5}

        result = prompt_manager._render_template(template, variables)

        assert "你好 小明" in result
        assert "你的年龄是 5 岁" in result

    @pytest.mark.asyncio
    async def test_render_template_no_variables(self, prompt_manager):
        """测试不传变量时返回原始模板"""
        template = "你好 {name}，你的年龄是 {age} 岁"

        result = prompt_manager._render_template(template, None)

        assert result == template

    @pytest.mark.asyncio
    async def test_render_template_empty_variables(self, prompt_manager):
        """测试传空字典时返回原始模板"""
        template = "你好 {name}"

        result = prompt_manager._render_template(template, {})

        assert result == template

    @pytest.mark.asyncio
    async def test_render_template_missing_key(self, prompt_manager):
        """测试缺少变量时返回原始模板并记录警告"""
        template = "你好 {name}，你的年龄是 {age} 岁"
        variables = {"name": "小明"}  # 缺少 age

        # 应该返回原始模板而不是抛出异常
        result = prompt_manager._render_template(template, variables)

        # 由于缺少 key，应该返回原始模板
        assert result == template

    @pytest.mark.asyncio
    async def test_render_template_json_format(self, prompt_manager):
        """测试 JSON 格式模板渲染"""
        # 注意：JSON 的 {} 需要使用 {{}} 转义
        template = """
        {{
            "name": "{name}",
            "age": {age},
            "city": "{city}"
        }}
        """
        variables = {"name": "小明", "age": 5, "city": "北京"}

        result = prompt_manager._render_template(template, variables)

        assert '"name": "小明"' in result
        assert '"age": 5' in result
        assert '"city": "北京"' in result

    @pytest.mark.asyncio
    async def test_render_template_special_characters(self, prompt_manager):
        """测试特殊字符在变量中的处理"""
        template = "查询：{query}"
        variables = {"query": "前庭觉 & 本体感"}

        result = prompt_manager._render_template(template, variables)

        assert "查询：前庭觉 & 本体感" in result

    @pytest.mark.asyncio
    async def test_render_template_multiline_value(self, prompt_manager):
        """测试多行文本变量"""
        template = "内容：{content}"
        variables = {"content": "第一行\n第二行\n第三行"}

        result = prompt_manager._render_template(template, variables)

        assert "内容：第一行" in result
        assert "第二行" in result
        assert "第三行" in result

    @pytest.mark.asyncio
    async def test_render_template_numeric_values(self, prompt_manager):
        """测试数值类型变量"""
        template = "最小年龄：{min_age}，最大年龄：{max_age}"
        variables = {"min_age": 0, "max_age": 18}

        result = prompt_manager._render_template(template, variables)

        assert "最小年龄：0" in result
        assert "最大年龄：18" in result

    @pytest.mark.asyncio
    async def test_render_template_list_values(self, prompt_manager):
        """测试列表类型变量"""
        template = "关键词：{keywords}"
        variables = {"keywords": ["前庭觉", "本体感", "触觉"]}

        result = prompt_manager._render_template(template, variables)

        # 列表会被转换为字符串表示
        assert "前庭觉" in result
        assert "本体感" in result


class TestPromptManagerGetPrompt:
    """测试 PromptManager.get_prompt 方法"""

    @pytest.fixture
    def prompt_manager(self):
        """创建 PromptManager 实例"""
        manager = PromptManager()
        # Mock cache
        manager.cache = AsyncMock()
        manager.cache.get = AsyncMock(return_value=None)
        manager.cache.set_with_jitter = AsyncMock()
        return manager

    @pytest.mark.asyncio
    async def test_get_prompt_with_variables(self, prompt_manager):
        """测试 get_prompt 带变量渲染"""
        # Mock repository
        mock_version = MagicMock()
        mock_version.content = "你好 {name}，你的年龄是 {age} 岁"

        with patch.object(prompt_manager, "_get_repos") as mock_repos:
            mock_version_repo = AsyncMock()
            mock_version_repo.get_latest_version = AsyncMock(return_value=mock_version)
            mock_repos.return_value = (mock_version_repo, None)

            result = await prompt_manager.get_prompt(
                "test_prompt", variables={"name": "小明", "age": 5}
            )

            assert "你好 小明" in result
            assert "你的年龄是 5 岁" in result

    @pytest.mark.asyncio
    async def test_get_prompt_without_variables(self, prompt_manager):
        """测试 get_prompt 不带变量"""
        mock_version = MagicMock()
        mock_version.content = "这是一个固定提示词"

        with patch.object(prompt_manager, "_get_repos") as mock_repos:
            mock_version_repo = AsyncMock()
            mock_version_repo.get_latest_version = AsyncMock(return_value=mock_version)
            mock_repos.return_value = (mock_version_repo, None)

            result = await prompt_manager.get_prompt("test_prompt")

            assert result == "这是一个固定提示词"

    @pytest.mark.asyncio
    async def test_get_prompt_fallback(self, prompt_manager):
        """测试提示词不存在时使用 fallback"""
        with patch.object(prompt_manager, "_get_repos") as mock_repos:
            mock_version_repo = AsyncMock()
            mock_version_repo.get_latest_version = AsyncMock(return_value=None)
            mock_repos.return_value = (mock_version_repo, None)

            result = await prompt_manager.get_prompt("nonexistent_prompt")

            # 应该返回 fallback
            assert result == "You are a helpful assistant."

    @pytest.mark.asyncio
    async def test_get_prompt_cache_hit(self, prompt_manager):
        """测试缓存命中"""
        prompt_manager.cache.get = AsyncMock(return_value="缓存的内容")

        result = await prompt_manager.get_prompt("test_prompt")

        assert result == "缓存的内容"
        # 验证缓存被命中
        prompt_manager.cache.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_prompt_cache_hit_with_variables(self, prompt_manager):
        """测试缓存命中后渲染变量"""
        prompt_manager.cache.get = AsyncMock(return_value="你好 {name}")

        result = await prompt_manager.get_prompt(
            "test_prompt", variables={"name": "小明"}
        )

        assert result == "你好 小明"
