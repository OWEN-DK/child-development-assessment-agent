"""
年龄过滤器 - 支持严格/宽松模式的年龄过滤逻辑
"""

from enum import Enum
from typing import Tuple
from pydantic import BaseModel
from src.config import settings


class AgeFilterMode(str, Enum):
    """年龄过滤模式"""

    STRICT = "strict"  # 严格模式：用户年龄必须在内容年龄范围内（含小 tolerance）
    LOOSE = "loose"  # 宽松模式：允许用户年龄与内容年龄范围有部分重叠


class DevelopmentStage(str, Enum):
    """儿童发展阶段"""

    INFANT = "infant"  # 婴儿期 (0-1 岁)
    TODDLER = "toddler"  # 幼儿期 (1-3 岁)
    PRESCHOOL = "preschool"  # 学龄前 (3-6 岁)
    SCHOOL_AGE = "school_age"  # 学龄期 (6-12 岁)


class AgeFilterConfig(BaseModel):
    """年龄过滤配置"""

    tolerance: int  # 年龄容忍范围（岁）
    strictness: float  # 严格程度 (0-1)
    weight: float  # 年龄适配度权重 (0-1)


class AgeFilter:
    """
    年龄过滤器

    根据用户年龄和内容目标年龄范围，判断内容是否应该被过滤。
    支持严格模式和宽松模式切换。
    """

    # 无明确年龄内容的默认范围
    DEFAULT_AGE_MIN = 0
    DEFAULT_AGE_MAX = 18

    @classmethod
    def should_filter(
        cls,
        target_age_min: int,
        target_age_max: int,
        user_age: int,
        mode: AgeFilterMode = AgeFilterMode.STRICT,
    ) -> bool:
        """
        判断内容是否应该被过滤

        Args:
            target_age_min: 内容目标年龄下限
            target_age_max: 内容目标年龄上限
            user_age: 用户年龄
            mode: 过滤模式（严格/宽松）

        Returns:
            bool: True 表示应该过滤（不展示），False 表示通过（展示）
        """
        # 边界情况：用户年龄无效
        if user_age < 0:
            return True  # 过滤

        # 无明确年龄内容：默认通过
        if cls._is_unspecified_age(target_age_min, target_age_max):
            return False  # 通过

        if mode == AgeFilterMode.STRICT:
            return cls._should_filter_strict(target_age_min, target_age_max, user_age)
        else:
            return cls._should_filter_loose(target_age_min, target_age_max, user_age)

    @classmethod
    def _is_unspecified_age(cls, target_min: int, target_max: int) -> bool:
        """判断是否为无明确年龄内容"""
        return target_min == cls.DEFAULT_AGE_MIN and target_max == cls.DEFAULT_AGE_MAX

    @classmethod
    def _should_filter_strict(
        cls, target_min: int, target_max: int, user_age: int
    ) -> bool:
        """
        严格模式过滤逻辑

        规则：用户年龄必须在 [target_min, target_max] 范围内
        """
        return not (target_min <= user_age <= target_max)

    @classmethod
    def _should_filter_loose(
        cls, target_min: int, target_max: int, user_age: int
    ) -> bool:
        """
        宽松模式过滤逻辑

        规则：
        - 用户年龄与内容年龄范围有重叠即可通过
        - 单年龄内容（min == max）：tolerance = 1
        - 范围内容（min < max）：tolerance = 2
        """
        # 获取 tolerance
        is_single_age = target_min == target_max
        tolerance = 1 if is_single_age else 2

        # 扩展后的内容范围
        effective_min = target_min - tolerance
        effective_max = target_max + tolerance

        # 判断用户年龄是否在扩展范围内
        return not (effective_min <= user_age <= effective_max)

    @classmethod
    def build_metadata_filters(
        cls, user_age: int, mode: AgeFilterMode = AgeFilterMode.STRICT
    ):
        """
        构建 LlamaIndex MetadataFilter（用于向量检索阶段过滤）

        注意：由于 MetadataFilter 的限制，复杂逻辑需要在检索后二次过滤
        此方法仅提供基础的范围过滤

        Args:
            user_age: 用户年龄
            mode: 过滤模式

        Returns:
            MetadataFilters 对象
        """
        from llama_index.core.vector_stores import (
            MetadataFilter,
            MetadataFilters,
            FilterOperator,
        )

        if mode == AgeFilterMode.STRICT:
            tolerance = 1
        else:
            tolerance = 2

        min_age = max(0, user_age - tolerance)
        max_age = user_age + tolerance

        return MetadataFilters(
            filters=[
                MetadataFilter(
                    key="target_age_min", value=max_age, operator=FilterOperator.LTE
                ),
                MetadataFilter(
                    key="target_age_max", value=min_age, operator=FilterOperator.GTE
                ),
            ]
        )


class DynamicAgeFilter:
    """
    动态年龄过滤器（保留向后兼容）

    根据不同发展阶段的特征调整过滤参数：
    - 婴儿期 (0-1 岁): 发展迅速，每月差异大，过滤严格
    - 幼儿期 (1-3 岁): 快速发展期，但仍需较严格过滤
    - 学龄前 (3-6 岁): 稳定发展期，适度放宽
    - 学龄期 (6-12 岁): 相对成熟，过滤更灵活
    """

    # 各阶段默认配置（从 settings 读取）
    @classmethod
    def _get_stage_configs(cls):
        """从配置获取各阶段配置"""
        return {
            DevelopmentStage.INFANT: AgeFilterConfig(
                tolerance=1, strictness=0.9, weight=0.5
            ),
            DevelopmentStage.TODDLER: AgeFilterConfig(
                tolerance=2, strictness=0.8, weight=0.4
            ),
            DevelopmentStage.PRESCHOOL: AgeFilterConfig(
                tolerance=2, strictness=0.7, weight=0.3
            ),
            DevelopmentStage.SCHOOL_AGE: AgeFilterConfig(
                tolerance=3, strictness=0.6, weight=0.25
            ),
        }

    @classmethod
    def get_stage(cls, age: float | int) -> DevelopmentStage:
        """根据年龄判断发展阶段"""
        boundaries = settings.rag_age_filter_stage_boundaries
        if age <= boundaries.get("infant", 1):
            return DevelopmentStage.INFANT
        elif age <= boundaries.get("toddler", 3):
            return DevelopmentStage.TODDLER
        elif age <= boundaries.get("preschool", 6):
            return DevelopmentStage.PRESCHOOL
        else:
            return DevelopmentStage.SCHOOL_AGE

    @classmethod
    def get_config(cls, age: float | int) -> AgeFilterConfig:
        """获取指定年龄的过滤配置"""
        stage = cls.get_stage(age)
        return cls._get_stage_configs()[stage]

    @classmethod
    def build_age_filters(cls, age: int):
        """构建年龄过滤器"""
        config = cls.get_config(age)

        min_age = max(0, age - config.tolerance)
        max_age = age + config.tolerance

        from llama_index.core.vector_stores import (
            MetadataFilter,
            MetadataFilters,
            FilterOperator,
        )

        filters = MetadataFilters(
            filters=[
                MetadataFilter(
                    key="target_age_min", value=max_age, operator=FilterOperator.LTE
                ),
                MetadataFilter(
                    key="target_age_max", value=min_age, operator=FilterOperator.GTE
                ),
            ]
        )

        return filters, config

    @classmethod
    def calculate_age_fit_score(
        cls, age: int, target_min: float, target_max: float
    ) -> float:
        """
        计算年龄适配度得分

        Args:
            age: 儿童实际年龄
            target_min: 内容目标年龄下限
            target_max: 内容目标年龄上限

        Returns:
            float: 适配度得分 (0-1)
        """
        config = cls.get_config(age)

        # 完全适配
        if target_min <= age <= target_max:
            return 1.0

        # 超出范围，计算适配度
        if age < target_min:
            diff = target_min - age
        else:
            diff = age - target_max

        # 根据发展阶段严格程度计算
        base_score = max(
            settings.rag_age_fit_base_score,
            1 - diff * settings.rag_age_fit_decay_factor * config.strictness,
        )

        return base_score
