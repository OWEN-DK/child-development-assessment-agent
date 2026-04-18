"""配置校验器测试"""

import pytest
from src.core.llm.config_validator import LLMConfigValidator, llm_config_validator


def test_validate_scene_valid():
    """测试有效场景配置校验通过"""
    config = {
        "provider": "dashscope",
        "model": "qwen3.5-plus",
        "temperature": 0.7,
        "max_tokens": 2000,
        "top_p": 0.8,
        "presence_penalty": 0.0,
        "frequency_penalty": 0.0,
    }

    is_valid, errors = LLMConfigValidator.validate_scene("report_generation", config)
    assert is_valid is True
    assert len(errors) == 0


def test_validate_scene_invalid_provider():
    """测试无效提供商校验失败"""
    config = {
        "provider": "invalid_provider",
        "model": "test-model",
    }

    is_valid, errors = LLMConfigValidator.validate_scene("report_generation", config)
    assert is_valid is False
    assert any("Invalid provider" in e for e in errors)


def test_validate_scene_invalid_scene():
    """测试无效场景名校验失败"""
    config = {
        "provider": "dashscope",
        "model": "qwen3.5-plus",
    }

    is_valid, errors = LLMConfigValidator.validate_scene("unknown_scene", config)
    assert is_valid is False
    assert any("Unknown scene" in e for e in errors)


def test_validate_scene_temperature_out_of_range():
    """测试温度参数超出范围校验失败"""
    config = {
        "provider": "dashscope",
        "model": "qwen3.5-plus",
        "temperature": 3.0,  # 超出 0-2 范围
        "max_tokens": 2000,
    }

    is_valid, errors = LLMConfigValidator.validate_scene("report_generation", config)
    assert is_valid is False
    assert any("Pydantic validation failed" in e for e in errors)


def test_validate_all_scenes():
    """测试校验所有场景配置"""
    full_config = {
        "llm_report_generation": {
            "provider": "dashscope",
            "model": "qwen3.5-plus",
            "temperature": 0.7,
            "max_tokens": 2000,
            "top_p": 0.8,
            "presence_penalty": 0.0,
            "frequency_penalty": 0.0,
        },
        "llm_validation": {
            "provider": "dashscope",
            "model": "qwen3.5-turbo",
            "temperature": 0.5,
            "max_tokens": 1000,
            "top_p": 0.9,
            "presence_penalty": 0.0,
            "frequency_penalty": 0.0,
        },
    }

    is_valid, errors = LLMConfigValidator.validate_all_scenes(full_config)
    assert is_valid is True
    assert len(errors) == 0


def test_validate_provider_config_valid():
    """测试有效提供商凭证校验通过"""
    config = {
        "api_key": "sk-test-key",
        "base_url": "https://api.example.com/v1",
    }

    is_valid, errors = LLMConfigValidator.validate_provider_config("openai", config)
    assert is_valid is True
    assert len(errors) == 0


def test_validate_provider_config_missing_api_key():
    """测试缺少 API Key 校验失败"""
    config = {
        "base_url": "https://api.example.com/v1",
    }

    is_valid, errors = LLMConfigValidator.validate_provider_config("openai", config)
    assert is_valid is False
    assert any("API key required" in e for e in errors)


def test_validate_provider_config_invalid_url():
    """测试无效 base_url 格式校验失败"""
    config = {
        "api_key": "sk-test-key",
        "base_url": "invalid-url",
    }

    is_valid, errors = LLMConfigValidator.validate_provider_config("openai", config)
    assert is_valid is False
    assert any("Invalid base_url format" in e for e in errors)


def test_singleton_instance():
    """测试单例实例可用"""
    assert llm_config_validator is not None
    assert isinstance(llm_config_validator, LLMConfigValidator)
