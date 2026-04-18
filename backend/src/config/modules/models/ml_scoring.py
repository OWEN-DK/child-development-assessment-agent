from pydantic import Field
from pydantic_settings import BaseSettings


class MLScoringSettings(BaseSettings):
    ml_scoring_enabled: bool = Field(False, validation_alias="ML_SCORING_ENABLED",
        description="是否启用ML智能评分功能"
    )
    ml_scoring_mode: str = Field(
        "qwen", validation_alias="ML_SCORING_MODE",
        description="评分模式：qwen(大模型评分)/xgboost(机器学习模型评分)"
    )
    ml_scoring_model_path: str = Field(
        "./models/scoring_xgb.model", validation_alias="ML_SCORING_MODEL_PATH",
        description="XGBoost评分模型文件路径"
    )
    ml_scoring_weight_ahp: float = Field(0.7, validation_alias="ML_SCORING_WEIGHT_AHP",
        description="层次分析法评分权重"
    )
    ml_scoring_weight_ml: float = Field(0.3, validation_alias="ML_SCORING_WEIGHT_ML",
        description="机器学习评分权重"
    )
