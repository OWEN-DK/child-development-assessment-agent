from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from pydantic_core import PydanticUndefined
from typing import Any, Optional
from src.config import config_manager, settings
from src.core.auth import get_current_user
from src.utils.logger import logger


def _sanitize_for_json(value: Any) -> Any:
    """将 PydanticUndefined 等不可序列化类型转换为 None"""
    if value is PydanticUndefined:
        return None
    if isinstance(value, dict):
        return {k: _sanitize_for_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_for_json(item) for item in value]
    return value


router = APIRouter(prefix="/api/v1/config", tags=["Configuration"])


class ConfigSaveRequest(BaseModel):
    """配置保存请求"""

    config_snapshot: dict[str, Any]
    description: str


class ConfigRollbackRequest(BaseModel):
    """配置回滚请求"""

    version_id: str


class ConfigVersionResponse(BaseModel):
    """配置版本响应"""

    id: str
    created_at: str
    created_by: Optional[str]
    description: Optional[str]
    parent_version_id: Optional[str]
    is_factory_reset: bool


# 初始化加载配置
@router.on_event("startup")
async def startup_load_config():
    await config_manager.load_latest_version()


@router.get("/current", response_model=dict[str, Any])
async def get_current_config():
    """获取当前配置及其元数据"""
    try:
        # Fallback: load config if not already loaded
        if config_manager.current_config is None:
            await config_manager.load_latest_version()

        current_config = config_manager.current_config
        metadata = settings.get_all_config_metadata()

        # Transform metadata to match frontend expectations
        config_fields = []
        for field_name, field_meta in metadata.items():
            default_val = _sanitize_for_json(field_meta.default_value)
            current_val = _sanitize_for_json(
                current_config.get(field_name, field_meta.default_value)
            )
            config_fields.append(
                {
                    "key": field_meta.key,
                    "type": field_meta.field_type,
                    "default_value": default_val,
                    "current_value": current_val,
                    "description": field_meta.description,
                    "category": field_meta.category,
                    "hot_reloadable": field_meta.hot_reloadable,
                    "requires_restart": field_meta.requires_restart,
                    "affected_components": field_meta.affected_components,
                }
            )

        return {
            "active_version": config_manager.current_version_id,
            "config": config_fields,
        }
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/versions", response_model=list[ConfigVersionResponse])
async def list_config_versions(limit: int = 50):
    """列出配置版本"""
    versions = await config_manager.list_versions(limit)
    return [
        ConfigVersionResponse(
            id=v["id"],
            created_at=v["created_at"].isoformat()
            if hasattr(v["created_at"], "isoformat")
            else str(v["created_at"]),
            created_by=v.get("created_by"),
            description=v.get("description"),
            parent_version_id=v.get("parent_version_id"),
            is_factory_reset=v.get("is_factory_reset", False),
        )
        for v in versions
    ]


@router.get("/versions/{version_id}", response_model=dict[str, Any])
async def get_config_version(version_id: str):
    """获取指定版本配置"""
    version = await config_manager.get_version(version_id)
    if not version:
        raise HTTPException(status_code=404, detail=f"配置版本不存在: {version_id}")
    return version["config_snapshot"]


@router.post("/save", response_model=ConfigVersionResponse)
async def save_new_config(
    request: ConfigSaveRequest, current_user=Depends(get_current_user)
):
    """保存新配置版本"""
    try:
        created_by = current_user.username if current_user else "system"
        new_version = await config_manager.save_new_version(
            config_snapshot=request.config_snapshot,
            description=request.description,
            created_by=created_by,
        )
        return ConfigVersionResponse(
            id=new_version.id,
            created_at=new_version.created_at.isoformat(),
            created_by=new_version.created_by,
            description=new_version.description,
            parent_version_id=new_version.parent_version_id,
            is_factory_reset=new_version.is_factory_reset,
        )
    except Exception as e:
        logger.error(f"保存配置失败: {e}")
        raise HTTPException(status_code=500, detail=f"保存配置失败: {str(e)}")


@router.post("/rollback", response_model=ConfigVersionResponse)
async def rollback_config(
    request: ConfigRollbackRequest, current_user=Depends(get_current_user)
):
    """回滚到指定配置版本"""
    try:
        created_by = current_user.username if current_user else "system"
        rollback_version = await config_manager.rollback_to_version(
            version_id=request.version_id, created_by=created_by
        )
        return ConfigVersionResponse(
            id=rollback_version.id,
            created_at=rollback_version.created_at.isoformat(),
            created_by=rollback_version.created_by,
            description=rollback_version.description,
            parent_version_id=rollback_version.parent_version_id,
            is_factory_reset=rollback_version.is_factory_reset,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"回滚配置失败: {e}")
        raise HTTPException(status_code=500, detail=f"回滚配置失败: {str(e)}")


@router.get("/schema", response_model=dict[str, Any])
async def get_config_schema():
    """获取配置JSON Schema，用于前端动态渲染表单"""
    return settings.model_json_schema()
