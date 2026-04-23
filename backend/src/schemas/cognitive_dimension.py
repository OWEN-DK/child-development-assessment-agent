"""12 种认知维度枚举（实体类统一在 schemas/ 目录）"""

from enum import Enum


class CognitiveDimension(str, Enum):
    """12 种认知维度"""

    FACT_RETRIEVAL = "fact_retrieval"                    # 事实检索
    CONCEPT_COMPARISON = "concept_comparison"             # 概念对比
    INTERVENTION_DESIGN = "intervention_design"           # 干预设计
    SYMPTOM_IDENTIFICATION = "symptom_identification"     # 症状识别
    DEVELOPMENTAL_MILESTONE = "developmental_milestone"   # 发展里程碑
    ASSESSMENT_METHOD = "assessment_method"               # 评估方法
    CAUSE_ANALYSIS = "cause_analysis"                     # 原因分析
    PROGRESSION_PREDICTION = "progression_prediction"     # 进展预测
    ACTIVITY_PLANNING = "activity_planning"               # 活动规划
    RESOURCE_RECOMMENDATION = "resource_recommendation"   # 资源推荐
    RISK_EVALUATION = "risk_evaluation"                   # 风险评估
    PARENT_GUIDANCE = "parent_guidance"                   # 家长指导
