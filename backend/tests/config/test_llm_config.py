"""LLM 配置模块测试"""

import pytest


def test_llm_providers_config():
    """验证 LLM 提供商配置和场景配置包含 provider 字段"""
    from src.config import settings

    # 验证 dashscope_api_key 存在（向后兼容）
    assert hasattr(settings, "dashscope_api_key"), "dashscope_api_key 字段不存在"
    assert settings.dashscope_api_key is not None, "dashscope_api_key 未配置"

    # 验证场景配置（当前为字符串字段，向后兼容）
    assert settings.model_report_generation == "qwen-plus"
    assert settings.model_assessment == "qwen-plus"
    assert settings.model_validation == "qwen-plus"

    # 验证 llm_scene_configs 属性（新增的嵌套配置）
    assert hasattr(settings, "llm_scene_configs"), "llm_scene_configs 属性不存在"
    scene_configs = settings.llm_scene_configs
    assert "report_generation" in scene_configs
    assert scene_configs["report_generation"].provider == "dashscope"
    assert scene_configs["report_generation"].model == "qwen-plus"
    assert scene_configs["validation"].model == "qwen-plus"


def test_llm_scene_config_structure():
    """验证 LLM 场景配置结构"""
    from src.config import settings

    # 验证所有 9 大场景都存在（通过 llm_scene_configs 属性）
    expected_scenes = [
        "report_generation",
        "assessment",
        "validation",
        "metadata_extraction",
        "query_rewrite",
        "query_classification",
        "vl_parsing",
        "ml_scoring",
        "content_generation",
    ]

    scene_configs = settings.llm_scene_configs
    for scene in expected_scenes:
        assert scene in scene_configs, f"场景 {scene} 未定义"
        # 验证每个场景配置都有 provider 和 model 字段
        assert hasattr(scene_configs[scene], "provider")
        assert hasattr(scene_configs[scene], "model")


def test_model_pricing_config():
    """验证模型定价配置（如果已实现）"""
    from src.config import settings

    # 定价配置是可选的，如果存在则验证结构
    if hasattr(settings, "model_pricing"):
        assert isinstance(settings.model_pricing, dict)
        # 验证至少有一个模型的定价
        if settings.model_pricing:
            first_key = list(settings.model_pricing.keys())[0]
            pricing = settings.model_pricing[first_key]
            assert hasattr(pricing, "input_per_million")
            assert hasattr(pricing, "output_per_million")
            assert hasattr(pricing, "currency")
