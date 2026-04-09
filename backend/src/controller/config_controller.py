from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from src.config.config_manager import config_manager
from src.config import settings, ConfigFieldMetadata
from src.config.rules import rules
from src.utils.logger import logger

router = APIRouter(prefix="/api/v1/config", tags=["Configuration"])


class ConfigUpdateRequest(BaseModel):
    config: Dict[str, Any]
    description: str = ""
    created_by: str = "user"


class ConfigVersionResponse(BaseModel):
    version_id: str
    created_at: str
    created_by: str
    description: str
    is_active: bool
    parent_version_id: Optional[str] = None


@router.get("/")
async def get_config():
    current_config = config_manager.get_full_config()
    metadata = settings.get_all_config_metadata()
    
    # Add rule config metadata
    rule_configs = [
        ("validation", rules.validation),
        ("assessment", rules.assessment),
        ("scoring", rules.scoring),
        ("preprocessing", rules.preprocessing),
        ("metadata", rules.metadata),
    ]
    
    for rule_name, rule_instance in rule_configs:
        for field_name, field_info in rule_instance.model_fields.items():
            full_field_name = f"rule_{rule_name}_{field_name}"
            
            # Infer category
            if full_field_name.startswith("rule_validation_"):
                category = "校验规则配置"
            elif full_field_name.startswith("rule_assessment_"):
                category = "评估规则配置"
            elif full_field_name.startswith("rule_scoring_"):
                category = "评分规则配置"
            elif full_field_name.startswith("rule_preprocessing_"):
                category = "预处理规则配置"
            elif full_field_name.startswith("rule_metadata_"):
                category = "元数据提取规则配置"
            else:
                category = "其他配置"
            
            annotation = field_info.annotation
            type_name = annotation.__name__ if hasattr(annotation, '__name__') else str(annotation)
            current_value = current_config.get(full_field_name, getattr(rule_instance, field_name))
            
            metadata[full_field_name] = ConfigFieldMetadata(
                key=full_field_name,
                category=category,
                description=field_info.description or "",
                hot_reloadable=True,
                requires_restart=False,
                affected_components=["规则引擎"],
                field_type=type_name,
                default_value=getattr(rule_instance, field_name)
            )

    result = []
    for key, meta in metadata.items():
        result.append({
            "key": key,
            "type": meta.field_type,
            "default_value": meta.default_value,
            "current_value": current_config.get(key, meta.default_value),
            "description": meta.description,
            "category": meta.category,
            "hot_reloadable": meta.hot_reloadable,
            "requires_restart": meta.requires_restart,
            "affected_components": meta.affected_components
        })

    return {
        "active_version": config_manager.get_active_version(),
        "config": result
    }


@router.put("/")
async def update_config(request: ConfigUpdateRequest):
    try:
        result = await config_manager.update_config(
            config_updates=request.config,
            description=request.description,
            created_by=request.created_by
        )
        return {
            "status": "success",
            "version_id": result["version_id"],
            "previous_version": result["previous_version"],
            "changed_keys": result["changed_keys"]
        }
    except Exception as e:
        logger.error(f"Failed to update config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/versions")
async def list_versions(limit: int = 50):
    versions = await config_manager._repository.list_versions(limit=limit)
    active_version = config_manager.get_active_version()

    return [
        {
            "version_id": v["version_id"],
            "created_at": v["created_at"],
            "created_by": v.get("created_by", "system"),
            "description": v.get("description", ""),
            "is_active": v["version_id"] == active_version,
            "parent_version_id": v.get("parent_version_id"),
            "is_factory_reset": v.get("is_factory_reset", False)
        }
        for v in versions
    ]


@router.post("/rollback/{version_id}")
async def rollback_to_version(version_id: str):
    try:
        result = await config_manager.rollback_to_version(version_id)
        return {
            "status": "success",
            "version_id": result["version_id"],
            "previous_version": result["previous_version"]
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to rollback config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reset")
async def reset_to_factory():
    try:
        result = await config_manager.reset_to_factory()
        return {
            "status": "success",
            "version_id": result["version_id"],
            "message": "已恢复到出厂设置"
        }
    except Exception as e:
        logger.error(f"Failed to reset config: {e}")
        raise HTTPException(status_code=500, detail=str(e))
