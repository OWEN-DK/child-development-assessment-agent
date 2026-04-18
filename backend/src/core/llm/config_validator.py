"""配置校验层 - 复用 Pydantic 模型校验"""

from typing import Any, Dict, List, Tuple

from src.config.modules.models.llm import LLMSceneConfig
from src.utils.logger import logger


class LLMConfigValidator:
    """LLM 配置校验器

    复用 LLMSceneConfig 的 Pydantic 约束进行配置校验，
    避免手动维护双重校验规则。
    """

    # 所有支持的场景名称
    VALID_SCENES = [
        "report_generation",
        "assessment",
        "validation",
        "metadata_extraction",
        "query_rewrite",
        "query_routing",
        "content_generation",
        "vl_parsing",
        "ml_scoring",
    ]

    # 支持的提供商列表
    VALID_PROVIDERS = ["dashscope", "openai", "anthropic", "ollama", "deepseek"]

    @classmethod
    def validate_scene(
        cls, scene: str, config: Dict[str, Any]
    ) -> Tuple[bool, List[str]]:
        """校验单个场景配置

        Args:
            scene: 场景名称
            config: 配置字典

        Returns:
            (是否通过, 错误列表)
        """
        errors = []

        # 校验场景名称
        if scene not in cls.VALID_SCENES:
            errors.append(f"Unknown scene: {scene}")
            return False, errors

        # 校验提供商
        provider = config.get("provider", "dashscope")
        if provider not in cls.VALID_PROVIDERS:
            errors.append(f"Invalid provider: {provider}")
            return False, errors

        # 使用 Pydantic model_validate 进行完整校验
        try:
            LLMSceneConfig.model_validate(config)
        except Exception as e:
            errors.append(f"Pydantic validation failed: {str(e)}")

        return len(errors) == 0, errors

    @classmethod
    def validate_all_scenes(
        cls, full_config: Dict[str, Any]
    ) -> Tuple[bool, Dict[str, List[str]]]:
        """校验所有场景配置

        Args:
            full_config: 完整配置字典（来自 ConfigManager.get_full_config()）

        Returns:
            (是否全部通过, {场景名: [错误列表]})
        """
        all_valid = True
        all_errors = {}

        for scene in cls.VALID_SCENES:
            config_key = f"llm_{scene}"
            config_data = full_config.get(config_key, {})

            if config_data:
                is_valid, errors = cls.validate_scene(scene, config_data)
                if not is_valid:
                    all_valid = False
                    all_errors[scene] = errors

        return all_valid, all_errors

    @classmethod
    def validate_provider_config(
        cls, provider: str, config: Dict[str, Any]
    ) -> Tuple[bool, List[str]]:
        """校验提供商凭证配置

        Args:
            provider: 提供商名称
            config: 提供商配置字典

        Returns:
            (是否通过, 错误列表)
        """
        errors = []

        if provider not in cls.VALID_PROVIDERS:
            errors.append(f"Unknown provider: {provider}")
            return False, errors

        # API Key 校验（某些提供商需要）
        if provider in ("dashscope", "openai", "anthropic"):
            api_key = config.get("api_key")
            if not api_key:
                errors.append(f"API key required for provider: {provider}")

        # Base URL 格式校验
        base_url = config.get("base_url")
        if base_url and not base_url.startswith(("http://", "https://")):
            errors.append(f"Invalid base_url format: {base_url}")

        return len(errors) == 0, errors


# 单例实例
llm_config_validator = LLMConfigValidator()
