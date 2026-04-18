from typing import Any, Dict, List

from src.config import settings
from src.config.rules import rules
from src.core.llm.factory import LLMFramework, LLMServiceFactory
from src.core.nodes.base import BaseNode
from src.core.prompt.manager import prompt_manager
from src.schemas import Activity, AgentState, LLMMessage, LLMRequest
from src.utils.logger import logger

# 全局工厂实例（延迟初始化）
_llm_factory = None


def _get_llm_factory() -> LLMServiceFactory:
    """获取 LLM 工厂实例（延迟初始化）"""
    global _llm_factory
    if _llm_factory is None:
        from src.config.core.manager import config_manager
        from src.core.llm.provider_registry import ProviderRegistry

        provider_registry = ProviderRegistry()
        _llm_factory = LLMServiceFactory(config_manager, provider_registry)
    return _llm_factory


class ValidationNode(BaseNode):
    """数据校验与标准化"""

    async def __call__(self, state: AgentState) -> Dict[str, Any]:
        logger.info("Executing Validation Node...")

        # Pydantic 已经在入口处校验了，这里主要做业务规则校验和智能填补
        proposed_plan = state.proposed_plan
        child_profile = state.child_profile

        updated_activities: List[Activity] = []

        # 本地简单规则库，避免频繁调用 LLM
        simple_intensity_rules = rules.validation.activity_intensity_map
        simple_category_rules = rules.validation.activity_category_map

        for activity in proposed_plan.activities:
            # 1. 智能填补强度 (Intensity Imputation)
            inferred_intensity = activity.intensity
            if not inferred_intensity:
                inferred_intensity = rules.validation.default_intensity  # Default

                # Try simple rules first
                activity_name_lower = activity.name.lower()
                matched = False
                for key, val in simple_intensity_rules.items():
                    if key in activity_name_lower:
                        inferred_intensity = val
                        matched = True
                        break

                # If no match, use LLM
                if not matched and settings.dashscope_api_key:
                    try:
                        # 使用新的异步工厂创建 LLM 实例
                        factory = _get_llm_factory()
                        llm = await factory.create("validation", framework="llamaindex")

                        # 通过 PromptManager 获取提示词并渲染
                        system_prompt = await prompt_manager.get_prompt(
                            "intensity_inference"
                        )
                        user_prompt = await prompt_manager.get_prompt(
                            "intensity_inference",
                            variables={
                                "age": child_profile.age,
                                "activity_name": activity.name,
                            },
                        )

                        # 构建提示词
                        messages = [
                            LLMMessage(
                                role="system",
                                content=system_prompt,
                            ),
                            LLMMessage(role="user", content=user_prompt),
                        ]

                        # 调用 LLM（temperature/max_tokens 由工厂从配置自动读取）
                        response = await llm.chat(
                            LLMRequest(
                                messages=messages,
                                model_name=settings.model_validation,
                                scenario="validation",
                                prompt_key="intensity_inference",
                            )
                        )
                        llm_intensity = response.content.strip().lower()
                        if llm_intensity in ["low", "medium", "high"]:
                            inferred_intensity = llm_intensity
                            logger.info(
                                f"LLM inferred intensity for '{activity.name}': {inferred_intensity}"
                            )

                        # 释放引用
                        await factory.release("validation", framework="llamaindex")
                    except Exception as e:
                        logger.error(f"Failed to infer intensity with LLM: {e}")

                if not matched:
                    logger.info(
                        f"Imputed intensity for '{activity.name}': {inferred_intensity}"
                    )

            # 2. 智能填补类别 (Category Imputation)
            inferred_category = activity.category
            if not inferred_category:
                inferred_category = rules.validation.default_category  # Default

                # Try simple rules first
                activity_name_lower = activity.name.lower()
                matched = False
                for key, val in simple_category_rules.items():
                    if key in activity_name_lower:
                        inferred_category = val
                        matched = True
                        break

                # If no match, use LLM
                if not matched and settings.dashscope_api_key:
                    try:
                        # 使用新的异步工厂创建 LLM 实例
                        factory = _get_llm_factory()
                        llm = await factory.create("validation", framework="llamaindex")

                        # 通过 PromptManager 获取提示词并渲染
                        system_prompt = await prompt_manager.get_prompt(
                            "category_inference"
                        )
                        user_prompt = await prompt_manager.get_prompt(
                            "category_inference",
                            variables={
                                "age": child_profile.age,
                                "activity_name": activity.name,
                            },
                        )

                        # 构建提示词
                        messages = [
                            LLMMessage(
                                role="system",
                                content=system_prompt,
                            ),
                            LLMMessage(role="user", content=user_prompt),
                        ]

                        # 调用 LLM（temperature/max_tokens 由工厂从配置自动读取）
                        response = await llm.chat(
                            LLMRequest(
                                messages=messages,
                                model_name=settings.model_validation,
                                scenario="validation",
                                prompt_key="category_inference",
                            )
                        )
                        llm_category = response.content.strip().lower()
                        # Simple validation
                        if llm_category in [
                            "vestibular",
                            "proprioception",
                            "tactile",
                            "fine_motor",
                            "gross_motor",
                            "cardio",
                            "other",
                        ]:
                            inferred_category = llm_category
                            logger.info(
                                f"LLM inferred category for '{activity.name}': {inferred_category}"
                            )

                        # 释放引用
                        await factory.release("validation", framework="llamaindex")
                    except Exception as e:
                        logger.error(f"Failed to infer category with LLM: {e}")

                if not matched:
                    logger.info(
                        f"Imputed category for '{activity.name}': {inferred_category}"
                    )

            # Create new activity with inferred values
            updated_activity = activity.model_copy(
                update={"intensity": inferred_intensity, "category": inferred_category}
            )
            updated_activities.append(updated_activity)

        # Update the plan with validated activities
        proposed_plan.activities = updated_activities

        return {"proposed_plan": proposed_plan}
