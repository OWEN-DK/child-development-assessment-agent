"""Embedding 配置模块测试"""

import pytest


def test_embedding_provider_config():
    """验证 Embedding 配置包含 provider 字段"""
    from src.config import settings

    # 验证 provider 字段存在
    assert hasattr(settings, "embedding_provider"), "embedding_provider 字段不存在"
    assert settings.embedding_provider in ["dashscope", "openai", "ollama", "local"]

    # 验证旧字段仍然存在（向后兼容）
    assert hasattr(settings, "embedding_model_name")
    assert settings.embedding_model_name == "text-embedding-v4"
    assert settings.embedding_batch_size == 10

    # 验证 embedding_config 属性
    config = settings.embedding_config
    assert config["provider"] == "dashscope"
    assert config["model"] == "text-embedding-v4"
    assert config["batch_size"] == 10
    assert config["max_length"] == 1536
