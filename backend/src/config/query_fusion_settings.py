from pydantic import Field
from pydantic_settings import BaseSettings

class QueryFusionSettings(BaseSettings):
    query_router_llm_enabled: bool = Field(
        default=True,
        validation_alias="QUERY_ROUTER_LLM_ENABLED",
        description="是否启用LLM查询路由分类功能"
    )
    query_router_confidence_threshold: float = Field(
        default=0.8,
        validation_alias="QUERY_ROUTER_CONFIDENCE_THRESHOLD",
        description="查询分类置信度阈值，低于此值使用 fallback 策略"
    )
    query_router_llm_max_retries: int = Field(
        default=2,
        validation_alias="QUERY_ROUTER_LLM_MAX_RETRIES",
        description="查询分类LLM调用最大重试次数"
    )
    fusion_score_boost_for_pageindex: float = Field(
        default=1.2,
        validation_alias="FUSION_SCORE_BOOST_FOR_PAGEINDEX",
        description="PageIndex结果的分数提升系数"
    )
    fusion_hybrid_supplement_limit: int = Field(
        default=5,
        validation_alias="FUSION_HYBRID_SUPPLEMENT_LIMIT",
        description="混合检索补充结果的最大数量"
    )
    fusion_dedup_normalize: bool = Field(
        default=True,
        validation_alias="FUSION_DEDUP_NORMALIZE",
        description="是否启用融合结果的去重和分数归一化"
    )
