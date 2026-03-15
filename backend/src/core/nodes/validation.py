from typing import Dict, Any, List
from llama_index.llms.dashscope import DashScope
from src.config.settings import settings
from src.model.schemas import AgentState, Activity
from src.config.rules import rules
from src.core.nodes.base import BaseNode
from src.core.prompts import INTENSITY_INFERENCE_PROMPT, CATEGORY_INFERENCE_PROMPT
from src.utils.logger import logger


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
                        llm = DashScope(
                            model=settings.llm_models["validation"],
                            api_key=settings.dashscope_api_key,
                        )
                        prompt = INTENSITY_INFERENCE_PROMPT.format(
                            age=child_profile.age, activity_name=activity.name
                        )
                        response = await llm.acomplete(prompt)
                        llm_intensity = response.text.strip().lower()
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
                        llm = DashScope(
                            model=settings.llm_models["validation"],
                            api_key=settings.dashscope_api_key,
                        )
                        prompt = CATEGORY_INFERENCE_PROMPT.format(
                            age=child_profile.age, activity_name=activity.name
                        )
                        response = await llm.acomplete(prompt)
                        llm_category = response.text.strip().lower()
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
