"""配置模块模型

包含系统配置相关的 Pydantic 模型：
- ConfigSaveRequest: 配置保存请求
- ConfigRollbackRequest: 配置回滚请求
- ConfigVersionResponse: 配置版本响应
- LLMProviderConfig: LLM 提供商配置
- 等配置管理 DTO
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# --------------------------
# 配置管理请求/响应
# --------------------------


class ConfigSaveRequest(BaseModel):
    """配置保存请求"""

    config_snapshot: dict[str, Any]
    description: str


class ConfigRollbackRequest(BaseModel):
    """配置回滚请求"""

    version_id: str


class ConfigResetRequest(BaseModel):
    """恢复出厂设置请求"""

    confirm: bool
    reason: Optional[str] = None


class ConfigValidateRequest(BaseModel):
    """配置校验请求"""

    config: dict[str, Any]


class ConfigImportRequest(BaseModel):
    """配置导入请求"""

    config: dict[str, Any]
    description: Optional[str] = None


class ValidationError(BaseModel):
    """校验错误"""

    field: str
    message: str
    severity: str  # error/warning/info


class ConfigValidateResponse(BaseModel):
    """配置校验响应"""

    valid: bool
    errors: list[ValidationError]


class ConfigExportResponse(BaseModel):
    """配置导出响应"""

    version_id: str
    exported_at: str
    config: dict[str, Any]


class ConfigVersionResponse(BaseModel):
    """配置版本响应"""

    id: str
    created_at: str
    created_by: Optional[str]
    description: Optional[str]
    parent_version_id: Optional[str]
    is_factory_reset: bool


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


class RollbackRequest(BaseModel):
    """回滚请求"""

    user_id: str = "anonymous"
    reason: str


class HealthDiagnosticRequest(BaseModel):
    """健康诊断请求"""

    config: dict[str, Any] = Field(..., description="当前配置")


class DiagnosticSuggestion(BaseModel):
    """诊断建议"""

    priority: str  # high/medium/low
    issue: str
    suggestion: str
    config_path: str
    current_value: str
    recommended_value: str


class HealthDiagnosticResponse(BaseModel):
    """健康诊断响应"""

    score: int = Field(..., ge=0, le=100)
    score_basis: str
    suggestions: list[DiagnosticSuggestion]


# --------------------------
# LLM 配置
# --------------------------


class LLMProviderConfig(BaseModel):
    """LLM 提供商配置"""

    provider: str
    api_key: str
    base_url: Optional[str] = None
    models: List[str] = Field(default_factory=list)
    default_model: Optional[str] = None
    enabled: bool = True


# --------------------------
# 调参建议相关
# --------------------------


class PreviewRequest(BaseModel):
    """预览请求"""

    run_id: str
    param_name: str
    suggested_value: float


class PreviewResponse(BaseModel):
    """预览响应"""

    predicted_metrics: Optional[dict] = None
    based_on_history: bool = False
    message: str


class ApplyRequest(BaseModel):
    """应用请求"""

    run_id: str
    suggestion_ids: Optional[List[str]] = None


class ApplyResponse(BaseModel):
    """应用响应"""

    new_config_version_id: str
    applied_params: dict


class SuggestionResponse(BaseModel):
    """调优建议响应"""

    id: str
    param_name: str
    current_value: Optional[dict] = None
    suggested_value: Optional[dict] = None
    action: Optional[str] = None
    reason: Optional[str] = None
    expected_effect: Optional[dict] = None
    priority: Optional[str] = None
    source: Optional[str] = None
    applied: bool = False


class IgnoreSuggestionRequest(BaseModel):
    """忽略调优建议请求"""

    scope: str  # RagEvalIgnoreScope 枚举值
    reason: Optional[str] = None
    test_set_id: str
    report_id: Optional[str] = None
    param_name: str


class IgnoreSuggestionResponse(BaseModel):
    """忽略建议响应"""

    message: str
    suggestion_id: str


class IgnoredSuggestionItem(BaseModel):
    """已忽略建议项"""

    id: str
    param_name: str
    name_zh: Optional[str] = None
    suggestion_type: str
    ignore_scope: str
    ignored_at: Optional[datetime] = None
    ignored_by: Optional[str] = None
    ignore_reason: Optional[str] = None
    restored: bool
    restored_at: Optional[datetime] = None


class IgnoredSuggestionsResponse(BaseModel):
    """已忽略建议列表响应"""

    items: List[IgnoredSuggestionItem]
    total: int


class RestoreIgnoredSuggestionResponse(BaseModel):
    """恢复忽略建议响应"""

    id: str
    restored: bool
    restored_at: Optional[datetime] = None
    message: str


class DeleteIgnoredSuggestionResponse(BaseModel):
    """删除忽略建议响应"""

    id: str
    message: str


class PromptItem(BaseModel):
    """提示词变更项"""

    key: str
    version_string: str
    content: str
    summary: Optional[str] = None


class ConfigChangeSetRequest(BaseModel):
    """创建配置变更集请求"""

    config_snapshot: dict
    prompts: List[PromptItem] = []
    change_summary: Optional[str] = None


class ConfigChangeSetResponse(BaseModel):
    """配置变更集响应"""

    id: str
    change_set_label: str
    config_version_id: Optional[str] = None
    status: str
    created_at: datetime


# --------------------------
# 配置校验与冲突检测
# --------------------------


class Conflict(BaseModel):
    """配置冲突"""

    level: str  # error | warning
    rule: str
    message: str
    affected_configs: list[str] = Field(default_factory=list)


class ValidationResult(BaseModel):
    """校验结果"""

    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
