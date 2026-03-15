from typing import Dict, Any, List
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
import json
from src.utils.logger import logger

# 获取当前文件所在目录的绝对路径
BASE_DIR = Path(__file__).parent.parent.parent.resolve()

# 尝试加载 rules.json
RULES_JSON_PATH = BASE_DIR / "src/config/rules.json"
GLOBAL_RULES_CONFIG = {}
if RULES_JSON_PATH.exists():
    try:
        with open(RULES_JSON_PATH, "r", encoding="utf-8") as f:
            GLOBAL_RULES_CONFIG = json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load rules.json: {e}")


class ValidationRules(BaseModel):
    """Validation Node Rules"""

    default_intensity: str = "medium"
    default_category: str = "gross_motor"
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
        }
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
        }
    )


class AssessmentRules(BaseModel):
    """Assessment Node Rules"""

    age_milestones: Dict[str, str] = Field(
        default_factory=lambda: {
            "0-3": "- 能双脚跳离地面\n- 能走直线\n- 开始尝试单脚站立",
            "3-5": "- 能单脚站立 5-10 秒\n- 能接住反弹球\n- 能交替上下楼梯\n- 前庭系统对旋转刺激开始整合",
            "5-7": "- 能熟练跳绳\n- 能闭眼单脚站立\n- 左右手分化完成\n- 注意力能集中 15-20 分钟",
            "7+": "- 具备复杂的动作规划能力\n- 团队运动规则理解\n- 情绪控制能力显著增强",
        }
    )


class ScoringRules(BaseModel):
    """Scoring Node Rules"""

    # AHP Weights (Total should be 1.0)
    weight_scientific: float = 0.4
    weight_age: float = 0.3
    weight_safety: float = 0.3

    # Thresholds
    max_weekly_duration_preschool: int = 300  # Age < 5
    max_single_duration_preschool: int = 30  # Age < 6

    # Penalties (positive values that will be subtracted)
    penalty_duration_overlimit: int = 20
    penalty_single_duration_overlimit: int = 10
    penalty_high_intensity_preschool: int = 30  # Age < 4
    penalty_risk_high: int = 20
    penalty_vestibular_mismatch: int = 10


class PreprocessingRules(BaseModel):
    """Preprocessing Node Rules"""

    trend_threshold: float = 0.5
    min_records_for_trend: int = 3
    recent_feedback_limit: int = 3


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

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env.rules"), env_file_encoding="utf-8", extra="ignore"
    )


# Global instance
rules = RuleSettings()
