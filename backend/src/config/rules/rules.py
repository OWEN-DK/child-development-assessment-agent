import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# 获取当前文件所在目录的绝对路径
BASE_DIR = Path(__file__).parent.parent.parent.resolve()

# 尝试加载 rules.json
RULES_JSON_PATH = Path(__file__).parent / "rules.json"
GLOBAL_RULES_CONFIG = {}
if RULES_JSON_PATH.exists():
    try:
        with open(RULES_JSON_PATH, "r", encoding="utf-8") as f:
            GLOBAL_RULES_CONFIG = json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load rules.json: {e}")


class ValidationRules(BaseModel):
    """Validation Node Rules"""

    default_intensity: str = Field("medium", description="活动默认强度等级")
    default_category: str = Field("gross_motor", description="活动默认分类")
    activity_intensity_map: Dict[str, str] = Field(
        default_factory=lambda: {
            "画画": "low",
            "绘画": "low",
            "串珠": "low",
            "积木": "low",
            "阅读": "low",
            "drawing": "low",
            "painting": "low",
            "reading": "low",
            "快走": "medium",
            "拍球": "medium",
            "平衡木": "medium",
            "骑车": "medium",
            "walking": "medium",
            "balance": "medium",
            "cycling": "medium",
            "跳绳": "high",
            "跑步": "high",
            "游泳": "high",
            "蹦床": "high",
            "篮球": "high",
            "running": "high",
            "jumping": "high",
            "swimming": "high",
            "basketball": "high",
        },
        description="活动名称到强度的映射关系"
    )
    activity_category_map: Dict[str, str] = Field(
        default_factory=lambda: {
            "画画": "fine_motor",
            "绘画": "fine_motor",
            "串珠": "fine_motor",
            "积木": "fine_motor",
            "drawing": "fine_motor",
            "painting": "fine_motor",
            "平衡木": "vestibular",
            "balance": "vestibular",
            "旋转": "vestibular",
            "秋千": "vestibular",
            "快走": "cardio",
            "跑步": "cardio",
            "游泳": "cardio",
            "跳绳": "cardio",
            "running": "cardio",
            "swimming": "cardio",
            "cycling": "cardio",
            "拍球": "proprioception",
            "ball": "proprioception",
            "推球": "proprioception",
            "蹦床": "vestibular",
            "trampoline": "vestibular",
        },
        description="活动名称到分类的映射关系"
    )


class AssessmentRules(BaseModel):
    """Assessment Node Rules"""

    age_milestones: Dict[str, str] = Field(
        default_factory=lambda: {
            "0-3": "- 能双脚跳离地面\n- 能走直线\n- 开始尝试单脚站立",
            "3-5": "- 能单脚站立 5-10 秒\n- 能接住反弹球\n- 能交替上下楼梯\n- 前庭系统对旋转刺激开始整合",
            "5-7": "- 能熟练跳绳\n- 能闭眼单脚站立\n- 左右手分化完成\n- 注意力能集中 15-20 分钟",
            "7+": "- 具备复杂的动作规划能力\n- 团队运动规则理解\n- 情绪控制能力显著增强",
        },
        description="不同年龄段的发展里程碑说明"
    )


class ScoringRules(BaseModel):
    """Scoring Node Rules"""

    # AHP Weights (Total should be 1.0)
    weight_scientific: float = Field(0.4, description="评分科学性维度权重")
    weight_age: float = Field(0.3, description="评分年龄适配维度权重")
    weight_safety: float = Field(0.3, description="评分安全性维度权重")

    # Thresholds
    max_weekly_duration_preschool: int = Field(300, description="学龄前儿童每周活动最大时长（分钟）")
    max_single_duration_preschool: int = Field(30, description="学龄前儿童单次活动最大时长（分钟）")

    # Penalties (positive values that will be subtracted)
    penalty_duration_overlimit: int = Field(20, description="周时长超标的扣分")
    penalty_single_duration_overlimit: int = Field(10, description="单次时长超标的扣分")
    penalty_high_intensity_preschool: int = Field(30, description="低龄儿童高强度活动的扣分")
    penalty_risk_high: int = Field(20, description="高风险活动的扣分")
    penalty_vestibular_mismatch: int = Field(10, description="前庭刺激不匹配的扣分")


class PreprocessingRules(BaseModel):
    """Preprocessing Node Rules"""

    trend_threshold: float = Field(0.5, description="趋势判断阈值")
    min_records_for_trend: int = Field(3, description="趋势分析需要的最少记录数")
    recent_feedback_limit: int = Field(3, description="最近反馈考虑的数量")


class MetadataRules(BaseModel):
    """Metadata Extraction Rules"""
    
    theme_keywords: Dict[str, List[str]] = Field(
        default_factory=lambda: {
            "粗大动作": ["粗大动作", "大运动", "跑", "跳", "爬", "走", "平衡", "协调性"],
            "精细动作": ["精细动作", "小肌肉", "手部", "手指", "画画", "剪纸", "搭积木", "握笔"],
            "认知能力": ["认知", "思维", "记忆", "注意力", "观察力", "想象力", "逻辑", "推理", "数感"],
            "语言发展": ["语言", "说话", "表达", "倾听", "阅读", "识字", "沟通", "交流"],
            "社交情感": ["社交", "情感", "情绪", "交往", "合作", "分享", "自信心", "同理心"],
            "感觉统合": ["感觉统合", "感官", "触觉", "听觉", "视觉", "前庭觉", "本体觉"]
        },
        description="主题分类关键词映射"
    )
    
    brain_regions_map: Dict[str, List[str]] = Field(
        default_factory=lambda: {
            "粗大动作": ["额叶", "小脑", "运动皮层"],
            "精细动作": ["顶叶", "小脑", "运动皮层"],
            "认知能力": ["前额叶", "海马体", "顶叶"],
            "语言发展": ["布洛卡区", "韦尼克区", "颞叶"],
            "社交情感": ["杏仁核", "前额叶", "岛叶"],
            "感觉统合": ["顶叶", "颞叶", "枕叶"]
        },
        description="发展领域对应脑区映射"
    )
    
    activity_type_keywords: Dict[str, List[str]] = Field(
        default_factory=lambda: {
            "Assessment": ["评估", "测试", "检查", "测评", "量表"],
            "Game/Activity": ["游戏", "活动", "玩法", "练习", "训练", "互动"],
            "Advice": ["建议", "指南", "方法", "策略", "技巧", "注意事项"],
            "CaseStudy": ["案例", "实例", "个案", "例子", "分享"]
        },
        description="活动类型关键词映射"
    )
    
    age_patterns: List[str] = Field(
        default_factory=lambda: [
            r"(\d+\.?\d*)~(\d+\.?\d*)岁",
            r"(\d+\.?\d*)-(\d+\.?\d*)岁",
            r"适合(\d+\.?\d*)到(\d+\.?\d*)岁",
            r"(\d+)月龄",
            r"(\d+\.?\d*)岁以上"
        ],
        description="年龄提取正则表达式列表"
    )


class RuleSettings(BaseSettings):
    """Centralized Rule Configuration"""

    validation: ValidationRules = Field(
        default_factory=lambda: ValidationRules(
            **GLOBAL_RULES_CONFIG.get("validation", {})
        )
    )
    assessment: AssessmentRules = Field(
        default_factory=lambda: AssessmentRules(
            **GLOBAL_RULES_CONFIG.get("assessment", {})
        )
    )
    scoring: ScoringRules = Field(
        default_factory=lambda: ScoringRules(**GLOBAL_RULES_CONFIG.get("scoring", {}))
    )
    preprocessing: PreprocessingRules = Field(
        default_factory=lambda: PreprocessingRules(
            **GLOBAL_RULES_CONFIG.get("preprocessing", {})
        )
    )
    metadata: MetadataRules = Field(
        default_factory=lambda: MetadataRules(
            **GLOBAL_RULES_CONFIG.get("metadata", {})
        )
    )

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env.rules"), env_file_encoding="utf-8", extra="ignore"
    )


# Global instance
rules = RuleSettings()
