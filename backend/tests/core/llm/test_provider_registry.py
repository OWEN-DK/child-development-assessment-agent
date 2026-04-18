"""Provider Registry 测试"""

import pytest


def test_provider_registry():
    """验证 Provider Registry 注册了主要提供商"""
    from src.core.llm.provider_registry import ProviderRegistry

    registry = ProviderRegistry()

    # 验证 DashScope LangChain 适配器已注册
    dashscope_langchain_cls = registry.get("dashscope", "langchain")
    assert dashscope_langchain_cls is not None, "DashScope LangChain 适配器未注册"

    # 验证 DashScope LlamaIndex 适配器已注册
    dashscope_llamaindex_cls = registry.get("dashscope", "llamaindex")
    assert dashscope_llamaindex_cls is not None, "DashScope LlamaIndex 适配器未注册"

    # 验证未知提供商返回 None
    assert registry.get("unknown", "langchain") is None, "未知提供商应返回 None"

    # 验证大小写归一化
    assert registry.get("DashScope", "LangChain") is not None, "大小写应归一化"
