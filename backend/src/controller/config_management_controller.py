"""配置管理 API 控制器 - Phase 8"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from src.utils.logger import logger
from src.service.config_validation_engine import (
    ConfigValidationEngine,
    ValidationResult,
)
from src.service.config_conflict_detector import ConfigConflictDetector, Conflict

router = APIRouter(prefix="/api/v1/rag/config", tags=["配置管理"])


class ConfigMetadataResponse(BaseModel):
    """配置元数据响应"""

    id: str
    config_key: str
    name_zh: str
    description_zh: str
    category: str
    value_type: str
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    recommended_min: Optional[float] = None
    recommended_max: Optional[float] = None
    unit: Optional[str] = None
    affected_components: Optional[list] = None
    reload_type: str
    is_system: bool


class ConfigMetadataListResponse(BaseModel):
    """配置元数据列表响应"""

    items: list[ConfigMetadataResponse]
    total: int


class ConfigValidationRequest(BaseModel):
    """配置校验请求"""

    config_updates: dict = Field(default_factory=dict)


class ConfigConflictRequest(BaseModel):
    """配置冲突检测请求"""

    config_updates: dict = Field(default_factory=dict)
    current_config: dict = Field(default_factory=dict)


class ConfigGroupResponse(BaseModel):
    """配置分组响应"""

    name: str
    key: str
    description: str
    configs: list[ConfigMetadataResponse]


# 配置分组定义
CONFIG_GROUPS = [
    {
        "key": "rag_retrieval",
        "name": "RAG 检索配置",
        "description": "BM25 权重、向量权重、融合模式、重排序、查询路由、年龄过滤",
    },
    {
        "key": "rag_chunking",
        "name": "RAG 分块配置",
        "description": "PDF 分块大小、语义分割器、分块重叠",
    },
    {
        "key": "llm",
        "name": "LLM 模型配置",
        "description": "凭证管理、场景配置、定价配置",
    },
    {
        "key": "database",
        "name": "数据库配置",
        "description": "连接池配置、慢查询阈值",
    },
    {
        "key": "redis",
        "name": "Redis 配置",
        "description": "连接配置、缓存配置",
    },
    {
        "key": "logging",
        "name": "日志配置",
        "description": "日志级别、日志格式",
    },
    {
        "key": "business_rule",
        "name": "业务规则配置",
        "description": "发展领域、年龄模式、难度阈值",
    },
]


class ConfigManagementController:
    """配置管理 API 控制器"""

    def __init__(self):
        self._validation_engine = ConfigValidationEngine()
        self._conflict_detector = ConfigConflictDetector()

    def register_routes(self, app):
        """注册路由"""

        @router.get("/metadata", response_model=ConfigMetadataListResponse)
        async def get_config_metadata(category: Optional[str] = None):
            """获取配置元数据列表"""
            try:
                from src.models.rag_eval.config_metadata import RagEvalConfigMetadata
                from src.models.rag_eval.config_metadata import ConfigCategory
                from sqlalchemy import select

                from src.core.database import async_session_factory

                async with async_session_factory() as session:
                    query = select(RagEvalConfigMetadata)

                    if category:
                        try:
                            cat_enum = ConfigCategory(category)
                            query = query.where(
                                RagEvalConfigMetadata.category == cat_enum
                            )
                        except ValueError:
                            raise HTTPException(
                                status_code=400, detail=f"无效的分类: {category}"
                            )

                    query = query.order_by(RagEvalConfigMetadata.config_key)
                    result = await session.execute(query)
                    configs = result.scalars().all()

                    items = [
                        ConfigMetadataResponse(
                            id=c.id,
                            config_key=c.config_key,
                            name_zh=c.name_zh,
                            description_zh=c.description_zh,
                            category=c.category.value,
                            value_type=c.value_type.value,
                            min_value=c.min_value,
                            max_value=c.max_value,
                            recommended_min=c.recommended_min,
                            recommended_max=c.recommended_max,
                            unit=c.unit,
                            affected_components=c.affected_components,
                            reload_type=c.reload_type.value,
                            is_system=c.is_system,
                        )
                        for c in configs
                    ]

                    return ConfigMetadataListResponse(items=items, total=len(items))
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"获取配置元数据失败: {e}")
                raise HTTPException(status_code=500, detail="获取配置元数据失败")

        @router.post("/validate", response_model=ValidationResult)
        async def validate_config(req: ConfigValidationRequest):
            """校验配置"""
            try:
                result = await self._validation_engine.validate(req.config_updates)
                return result
            except Exception as e:
                logger.error(f"配置校验失败: {e}")
                raise HTTPException(status_code=500, detail="配置校验失败")

        @router.post("/conflicts")
        async def detect_conflicts(req: ConfigConflictRequest):
            """检测配置冲突"""
            try:
                conflicts = await self._conflict_detector.detect(
                    req.config_updates, req.current_config
                )
                return [c.model_dump() for c in conflicts]
            except Exception as e:
                logger.error(f"配置冲突检测失败: {e}")
                raise HTTPException(status_code=500, detail="配置冲突检测失败")

        @router.get("/groups", response_model=list[ConfigGroupResponse])
        async def get_config_groups():
            """获取配置分组"""
            try:
                from src.models.rag_eval.config_metadata import RagEvalConfigMetadata
                from sqlalchemy import select

                from src.core.database import async_session_factory

                async with async_session_factory() as session:
                    result = await session.execute(select(RagEvalConfigMetadata))
                    all_configs = result.scalars().all()

                    groups = []
                    for group_def in CONFIG_GROUPS:
                        configs = [
                            c
                            for c in all_configs
                            if c.category.value == group_def["key"]
                        ]
                        if configs:
                            groups.append(
                                ConfigGroupResponse(
                                    name=group_def["name"],
                                    key=group_def["key"],
                                    description=group_def["description"],
                                    configs=[
                                        ConfigMetadataResponse(
                                            id=c.id,
                                            config_key=c.config_key,
                                            name_zh=c.name_zh,
                                            description_zh=c.description_zh,
                                            category=c.category.value,
                                            value_type=c.value_type.value,
                                            min_value=c.min_value,
                                            max_value=c.max_value,
                                            recommended_min=c.recommended_min,
                                            recommended_max=c.recommended_max,
                                            unit=c.unit,
                                            affected_components=c.affected_components,
                                            reload_type=c.reload_type.value,
                                            is_system=c.is_system,
                                        )
                                        for c in configs
                                    ],
                                )
                            )

                    return groups
            except Exception as e:
                logger.error(f"获取配置分组失败: {e}")
                raise HTTPException(status_code=500, detail="获取配置分组失败")

        app.include_router(router)
