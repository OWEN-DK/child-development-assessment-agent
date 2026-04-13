from typing import Dict, Any, List
from src.config import settings
from src.model.schemas import AgentState, Activity
from src.config.rules import rules
from src.core.nodes.base import BaseNode
from src.core.prompts import INTENSITY_INFERENCE_PROMPT, CATEGORY_INFERENCE_PROMPT
from src.utils.logger import logger
from src.core.llm.factory import LLMServiceFactory, LLMFramework
from src.core.llm.base import LLMRequest, LLMMessage


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
                        # 使用工厂创建 LLM 实例
                        llm = LLMServiceFactory.create(
                            framework=LLMFramework.LLAMAINDEX,
                            model_name=settings.llm_models["validation"],
                            scenario="validation",
                            temperature=0.3,
                        )

                        # 构建提示词
                        messages = [
                            LLMMessage(
                                role="system",
                                content="你是一个儿童运动活动分类专家，根据活动名称和儿童年龄推断活动的强度级别（low/medium/high），直接返回结果即可，不需要额外解释。",
                            ),
                            LLMMessage(
                                role="user",
                                content=INTENSITY_INFERENCE_PROMPT.format(
                                    age=child_profile.age, activity_name=activity.name
                                ),
                            ),
                        ]

                        # 调用 LLM
                        response = await llm.chat(
                            LLMRequest(
                                messages=messages,
                                model_name=settings.llm_models["validation"],
                                temperature=0.3,
                                max_tokens=512,
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
                        # 使用工厂创建 LLM 实例
                        llm = LLMServiceFactory.create(
                            framework=LLMFramework.LLAMAINDEX,
                            model_name=settings.llm_models["validation"],
                            scenario="validation",
                            temperature=0.3,
                        )

                        # 构建提示词
                        messages = [
                            LLMMessage(
                                role="system",
                                content="你是一个儿童运动活动分类专家，根据活动名称和儿童年龄推断活动的类别（vestibular/proprioception/tactile/fine_motor/gross_motor/cardio/other），直接返回结果即可，不需要额外解释。",
                            ),
                            LLMMessage(
                                role="user",
                                content=CATEGORY_INFERENCE_PROMPT.format(
                                    age=child_profile.age, activity_name=activity.name
                                ),
                            ),
                        ]

                        # 调用 LLM
                        response = await llm.chat(
                            LLMRequest(
                                messages=messages,
                                model_name=settings.llm_models["validation"],
                                temperature=0.3,
                                max_tokens=512,
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
