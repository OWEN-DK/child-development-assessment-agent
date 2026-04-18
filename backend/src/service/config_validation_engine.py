"""配置校验引擎 - Phase 8"""

from pydantic import BaseModel, Field
from typing import Optional


class ValidationResult(BaseModel):
    """校验结果"""

    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ConfigValidationEngine:
    """配置校验引擎 - 类型校验 + 范围校验 + 推荐范围警告"""

    def __init__(self, metadata_store: dict | None = None):
        self._metadata_store = metadata_store or {}

    async def validate(self, config_updates: dict) -> ValidationResult:
        """校验配置更新"""
        errors = []
        warnings = []

        for key, value in config_updates.items():
            metadata = self._metadata_store.get(key)
            if not metadata:
                errors.append(f"配置项 {key} 不存在")
                continue

            # 1. 类型校验
            type_error = self._validate_type(value, metadata["value_type"])
            if type_error:
                errors.append(f"{metadata['name_zh']}: {type_error}")
                continue

            # 2. 取值范围校验
            range_error = self._validate_range(value, metadata)
            if range_error:
                errors.append(f"{metadata['name_zh']}: {range_error}")
                continue

            # 3. 推荐范围校验
            rec_warning = self._validate_recommended_range(value, metadata)
            if rec_warning:
                warnings.append(f"{metadata['name_zh']}: {rec_warning}")

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    def _validate_type(self, value, value_type: str) -> Optional[str]:
        """类型校验"""
        if value_type == "number":
            if not isinstance(value, (int, float)):
                return "值必须为数字"
        elif value_type == "boolean":
            if not isinstance(value, bool):
                return "值必须为布尔类型"
        elif value_type == "json":
            if not isinstance(value, (dict, list)):
                return "值必须为 JSON 对象"
        return None

    def _validate_range(self, value, metadata: dict) -> Optional[str]:
        """取值范围校验"""
        if not isinstance(value, (int, float)):
            return None

        if metadata.get("min_value") is not None and value < metadata["min_value"]:
            return f"值不能小于 {metadata['min_value']}"
        if metadata.get("max_value") is not None and value > metadata["max_value"]:
            return f"值不能大于 {metadata['max_value']}"
        return None

    def _validate_recommended_range(self, value, metadata: dict) -> Optional[str]:
        """推荐范围校验"""
        if not isinstance(value, (int, float)):
            return None

        warnings = []
        if (
            metadata.get("recommended_min") is not None
            and value < metadata["recommended_min"]
        ):
            warnings.append(f"推荐值不低于 {metadata['recommended_min']}")
        if (
            metadata.get("recommended_max") is not None
            and value > metadata["recommended_max"]
        ):
            warnings.append(f"推荐值不超过 {metadata['recommended_max']}")
        return " ".join(warnings) if warnings else None
