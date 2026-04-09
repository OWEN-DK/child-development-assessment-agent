"""
动态年龄过滤器 - 根据儿童发展阶段调整过滤策略
"""
from enum import Enum
from typing import Tuple
from pydantic import BaseModel
from backend.src.config import settings


class DevelopmentStage(str, Enum):
    """儿童发展阶段"""
    INFANT = "infant"              # 婴儿期 (0-1 岁)
    TODDLER = "toddler"            # 幼儿期 (1-3 岁)
    PRESCHOOL = "preschool"        # 学龄前 (3-6 岁)
    SCHOOL_AGE = "school_age"      # 学龄期 (6-12 岁)


class AgeFilterConfig(BaseModel):
    """年龄过滤配置"""
    tolerance: int          # 年龄容忍范围（岁）
    strictness: float       # 严格程度 (0-1)
    weight: float           # 年龄适配度权重 (0-1)


class DynamicAgeFilter:
    """
    动态年龄过滤器
    
    根据不同发展阶段的特征调整过滤参数：
    - 婴儿期 (0-1 岁): 发展迅速，每月差异大，过滤严格
    - 幼儿期 (1-3 岁): 快速发展期，但仍需较严格过滤
    - 学龄前 (3-6 岁): 稳定发展期，适度放宽
    - 学龄期 (6-12 岁): 相对成熟，过滤更灵活
    """
    
    # 各阶段默认配置
    STAGE_CONFIGS = {
        DevelopmentStage.INFANT: AgeFilterConfig(
            tolerance=1,      # 婴儿期容忍 1 岁
            strictness=0.9,   # 非常严格
            weight=0.5        # 年龄权重高
        ),
        DevelopmentStage.TODDLER: AgeFilterConfig(
            tolerance=2,      # 幼儿期容忍 2 岁
            strictness=0.8,   # 较严格
            weight=0.4
        ),
        DevelopmentStage.PRESCHOOL: AgeFilterConfig(
            tolerance=2,      # 学龄前容忍 2 岁
            strictness=0.7,   # 适中
            weight=0.3
        ),
        DevelopmentStage.SCHOOL_AGE: AgeFilterConfig(
            tolerance=3,      # 学龄期容忍 3 岁
            strictness=0.6,   # 较灵活
            weight=0.25
        ),
    }
    
    @classmethod
    def get_stage(cls, age: float | int) -> DevelopmentStage:
        """根据年龄判断发展阶段"""
        if age <= 1:
            return DevelopmentStage.INFANT
        elif age <= 3:
            return DevelopmentStage.TODDLER
        elif age <= 6:
            return DevelopmentStage.PRESCHOOL
        else:
            return DevelopmentStage.SCHOOL_AGE
    
    @classmethod
    def get_config(cls, age: float | int) -> AgeFilterConfig:
        """获取指定年龄的过滤配置"""
        stage = cls.get_stage(age)
        return cls.STAGE_CONFIGS[stage]
    
    @classmethod
    def build_age_filters(cls, age: int):
        """构建年龄过滤器"""
        config = cls.get_config(age)
        
        min_age = max(0, age - config.tolerance)
        max_age = age + config.tolerance
        
        from llama_index.core.vector_stores import MetadataFilter, MetadataFilters, FilterOperator
        
        filters = MetadataFilters(
            filters=[
                MetadataFilter(
                    key="target_age_min", 
                    value=max_age, 
                    operator=FilterOperator.LTE
                ),
                MetadataFilter(
                    key="target_age_max", 
                    value=min_age, 
                    operator=FilterOperator.GTE
                ),
            ]
        )
        
        return filters, config
    
    @classmethod
    def calculate_age_fit_score(
        cls, 
        age: int, 
        target_min: float, 
        target_max: float
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
        base_score = max(0.5, 1 - diff * 0.1 * config.strictness)
        
        return base_score
