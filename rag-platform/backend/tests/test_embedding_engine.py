"""Embedding 引擎单元测试"""
import pytest

from src.core.knowledge_base.embedding.engine import (
    DashScopeEmbeddingProvider,
    EmbeddingEngine,
    OpenAIEmbeddingProvider,
)


class TestDashScopeEmbeddingProvider:
    """DashScope 提供者测试"""

    def test_dimension(self):
        """向量维度"""
        provider = DashScopeEmbeddingProvider(api_key="test", dimension=1024)
        assert provider.dimension == 1024

    def test_sanitize_empty_text(self):
        """空文本替换为 empty"""
        provider = DashScopeEmbeddingProvider(api_key="test")
        result = provider._sanitize_text("")
        assert result == "empty"

    def test_sanitize_whitespace_text(self):
        """空白文本替换为 empty"""
        provider = DashScopeEmbeddingProvider(api_key="test")
        result = provider._sanitize_text("   ")
        assert result == "empty"

    def test_sanitize_long_text(self):
        """超长文本截断"""
        provider = DashScopeEmbeddingProvider(api_key="test")
        long_text = "a" * 10000
        result = provider._sanitize_text(long_text)
        assert len(result) == 8192

    def test_sanitize_normal_text(self):
        """正常文本不变"""
        provider = DashScopeEmbeddingProvider(api_key="test")
        result = provider._sanitize_text("hello world")
        assert result == "hello world"

    def test_sanitize_texts_batch(self):
        """批量文本处理"""
        provider = DashScopeEmbeddingProvider(api_key="test")
        texts = ["hello", "", "world"]
        result = provider._sanitize_texts(texts)
        assert result == ["hello", "empty", "world"]


class TestOpenAIEmbeddingProvider:
    """OpenAI 提供者测试"""

    def test_dimension(self):
        """向量维度"""
        provider = OpenAIEmbeddingProvider(api_key="test", dimension=1536)
        assert provider.dimension == 1536

    def test_default_dimension(self):
        """默认维度"""
        provider = OpenAIEmbeddingProvider(api_key="test")
        assert provider.dimension == 1536


class TestEmbeddingEngine:
    """Embedding 引擎门面测试"""

    def test_from_config_dashscope(self):
        """从配置创建 DashScope 引擎"""
        engine = EmbeddingEngine.from_config(
            provider="dashscope",
            api_key="test",
            dimension=1024,
        )
        assert engine.dimension == 1024

    def test_from_config_openai(self):
        """从配置创建 OpenAI 引擎"""
        engine = EmbeddingEngine.from_config(
            provider="openai",
            api_key="test",
            dimension=1536,
        )
        assert engine.dimension == 1536

    def test_from_config_unsupported(self):
        """不支持的提供者抛出异常"""
        with pytest.raises(ValueError, match="不支持的 Embedding 提供者"):
            EmbeddingEngine.from_config(provider="unsupported", api_key="test")
