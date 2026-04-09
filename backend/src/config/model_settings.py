from pydantic import Field
from pydantic_settings import BaseSettings

class ModelSettings(BaseSettings):
    dashscope_api_key: str = Field(default="", validation_alias="DASHSCOPE_API_KEY", description="阿里云百炼API密钥")
    model_report_generation: str = Field(
        "qwen3.5-plus", validation_alias="MODEL_REPORT_GENERATION", description="评估报告生成使用的模型"
    )
    model_assessment: str = Field("qwen3.5-plus", validation_alias="MODEL_ASSESSMENT", description="儿童发展评估使用的模型")
    model_validation: str = Field("qwen3.5-turbo", validation_alias="MODEL_VALIDATION", description="结果校验使用的模型")
    model_query_rewrite: str = Field(
        "qwen3-omni-flash", validation_alias="MODEL_QUERY_REWRITE", description="查询重写使用的模型"
    )
    model_metadata_extraction: str = Field(
        "qwen3-omni-flash", validation_alias="MODEL_METADATA_EXTRACTION", description="元数据提取使用的模型"
    )
    model_vl_parsing: str = Field(
        "qwen3-omni-flash", validation_alias="MODEL_VL_PARSING", description="多模态内容解析使用的模型"
    )
    model_query_classification: str = Field(
        default="qwen3-omni-flash",
        validation_alias="MODEL_QUERY_CLASSIFICATION",
        description="查询分类使用的模型名称"
    )
    ml_scoring_qwen_model: str = Field(
        "qwen3.5-turbo", validation_alias="ML_SCORING_QWEN_MODEL",
        description="大模型评分使用的模型名称"
    )
