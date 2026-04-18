from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic_core import PydanticUndefined

from src.config import config_manager, settings
from src.core.auth import get_current_user
from src.schemas import (ConfigExportResponse, ConfigImportRequest,
                         ConfigResetRequest, ConfigRollbackRequest,
                         ConfigSaveRequest, ConfigValidateRequest,
                         ConfigValidateResponse, ConfigVersionResponse,
                         ValidationError)
from src.utils.exceptions import (ConfigValidationFailedException,
                                    InvalidParamsException,
                                    ResourceNotFoundException)
from src.utils.logger import logger
from src.utils.response import api_handler


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


# 初始化加载配置
@router.on_event("startup")
async def startup_load_config():
    await config_manager.load_latest_version()


@router.get("/current", response_model=dict[str, Any])
@api_handler("获取当前配置")
async def get_current_config():
    """获取当前配置及其元数据"""
    # Fallback: load config if not already loaded
    if config_manager.current_config is None:
        await config_manager.load_latest_version()

    current_config = config_manager.current_config
    metadata = settings.get_all_config_metadata()

    # Transform metadata to match frontend expectations
    config_fields = []
    for field_name, field_meta in metadata.items():
        default_val = _sanitize_for_json(field_meta.default_value)

        # 对于嵌套配置（如 llm_scene_configs__report_generation__model），
        # 使用 field_meta.current_value（已在元数据生成时设置）
        # 对于普通配置，从 current_config 中获取
        if (
            hasattr(field_meta, "current_value")
            and field_meta.current_value is not None
        ):
            current_val = _sanitize_for_json(field_meta.current_value)
        else:
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
        raise ResourceNotFoundException(message=f"配置版本不存在: {version_id}")
    return version["config_snapshot"]


@router.post("/save", response_model=ConfigVersionResponse)
@api_handler("保存新配置")
async def save_new_config(
    request: ConfigSaveRequest, current_user=Depends(get_current_user)
):
    """保存新配置版本"""
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


@router.post("/rollback", response_model=ConfigVersionResponse)
@api_handler("回滚配置版本", exception_map={ValueError: InvalidParamsException})
async def rollback_config(
    request: ConfigRollbackRequest, current_user=Depends(get_current_user)
):
    """回滚到指定配置版本"""
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


@router.post("/reset", response_model=ConfigVersionResponse)
@api_handler("恢复出厂设置")
async def reset_to_factory(
    request: ConfigResetRequest, current_user=Depends(get_current_user)
):
    """
    恢复出厂设置

    - 二次确认校验
    - 加载出厂默认配置
    - 保存为新版本（is_factory_reset=True）
    - 记录 RESET 审计日志
    """
    if not request.confirm:
        raise InvalidParamsException(message="需要二次确认")

    # 获取出厂配置
    factory_config = _get_factory_config()

    # 恢复出厂设置（ConfigManager 内部处理审计日志）
    created_by = current_user.username if current_user else "system"
    new_version = await config_manager.reset_to_factory(
        config_snapshot=factory_config,
        created_by=created_by,
    )

    logger.info(f"配置已恢复出厂设置: {created_by}")

    return ConfigVersionResponse(
        id=new_version.id,
        created_at=new_version.created_at.isoformat(),
        created_by=new_version.created_by,
        description=new_version.description,
        parent_version_id=new_version.parent_version_id,
        is_factory_reset=new_version.is_factory_reset,
    )


def _get_factory_config() -> dict[str, Any]:
    """
    获取出厂默认配置

    从 settings 默认值加载
    """
    # 使用 settings 的默认值作为出厂配置
    factory_settings = settings.model_dump()
    return factory_settings


@router.get("/schema", response_model=dict[str, Any])
async def get_config_schema():
    """获取配置JSON Schema，用于前端动态渲染表单"""
    return settings.model_json_schema()


@router.post("/validate", response_model=ConfigValidateResponse)
@api_handler("配置校验", include_detail=False)
async def validate_config(request: ConfigValidateRequest):
    """
    配置实时校验

    - 复用 LLMConfigValidator
    - 返回校验错误列表
    """
    from src.core.llm.config_validator import LLMConfigValidator

    validator = LLMConfigValidator()
    errors = validator.validate(request.config)

    return ConfigValidateResponse(
        valid=len(errors) == 0,
        errors=[
            ValidationError(
                field=e.get("field", "unknown"),
                message=e.get("message", str(e)),
                severity=e.get("severity", "error"),
            )
            for e in errors
        ],
    )


@router.get("/export", response_model=ConfigExportResponse)
@api_handler("导出配置")
async def export_config(
    version_id: Optional[str] = None, current_user=Depends(get_current_user)
):
    """
    导出配置为 JSON

    - 支持指定版本
    - 默认导出当前版本
    """
    from datetime import datetime

    if version_id:
        version = await config_manager.get_version(version_id)
        if not version:
            raise ResourceNotFoundException(
                message=f"配置版本不存在: {version_id}"
            )
        config_snapshot = version["config_snapshot"]
        export_version_id = version_id
    else:
        if config_manager.current_version is None:
            await config_manager.load_latest_version()

        config_snapshot = config_manager.current_config
        export_version_id = config_manager.current_version_id or "unknown"

    return ConfigExportResponse(
        version_id=export_version_id,
        exported_at=datetime.now().isoformat(),
        config=config_snapshot or {},
    )


@router.post("/import", response_model=ConfigVersionResponse)
@api_handler("导入配置")
async def import_config(
    request: ConfigImportRequest, current_user=Depends(get_current_user)
):
    """
    从 JSON 导入配置

    - 校验配置格式
    - 保存为新版本
    - 记录审计日志
    """
    # 校验配置
    from src.core.llm.config_validator import LLMConfigValidator

    validator = LLMConfigValidator()
    errors = validator.validate(request.config)

    if errors:
        raise ConfigValidationFailedException(
            message="配置校验失败",
            details={
                "errors": [
                    {"field": e.get("field"), "message": e.get("message")}
                    for e in errors
                ],
            },
        )

    # 保存为新版本
    created_by = current_user.username if current_user else "system"
    description = request.description or "导入配置"
    new_version = await config_manager.save_new_version(
        config_snapshot=request.config,
        description=description,
        created_by=created_by,
    )

    logger.info(f"配置已导入: {new_version.id}")

    return ConfigVersionResponse(
        id=new_version.id,
        created_at=new_version.created_at.isoformat(),
        created_by=new_version.created_by,
        description=new_version.description,
        parent_version_id=new_version.parent_version_id,
        is_factory_reset=new_version.is_factory_reset,
    )
