"""提示词模块模型

包含提示词管理相关的 Pydantic 模型：
- CreateVersionRequest: 创建版本请求
- PromptVersionResponse: 提示词版本响应
- ImpactAnalysisResponse: 影响分析响应
- 等提示词管理 DTO
"""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field

# --------------------------
# 提示词管理请求/响应
# --------------------------


class CreateVersionRequest(BaseModel):
    """创建版本请求"""

    content: str
    description: Optional[str] = None
    created_by: Optional[str] = None
    variables: Optional[list] = None
    tags: Optional[list] = None
    fallback: Optional[str] = None


class CreateABTestRequest(BaseModel):
    """创建 A/B 测试请求"""

    name: str
    variant_a_version: str
    variant_b_version: str
    variant_a_ratio: float = 0.5


class ToggleABTestRequest(BaseModel):
    """切换 A/B 测试请求"""

    is_active: bool


class PromptMetadataResponse(BaseModel):
    """提示词元数据响应"""

    id: str
    prompt_key: str
    name_zh: str
    purpose: str
    category: str
    subcategory: Optional[str] = None
    is_active: bool
    is_system: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class PromptVersionResponse(BaseModel):
    """提示词版本响应"""

    id: str
    prompt_key: str
    version_label: str
    version_number: int
    content: str
    variables_extracted: Optional[list] = None
    change_impact: Optional[dict] = None
    change_summary: Optional[str] = None
    created_at: Optional[str] = None
    created_by: Optional[str] = None


class PromptListResponse(BaseModel):
    """提示词列表响应"""

    items: list[PromptMetadataResponse]
    total: int


class PromptDetailResponse(BaseModel):
    """提示词详情响应"""

    metadata: PromptMetadataResponse
    current_version: Optional[PromptVersionResponse] = None
    versions: list[PromptVersionResponse] = []


class UpdatePromptRequest(BaseModel):
    """更新提示词请求"""

    content: str
    change_summary: Optional[str] = None
    created_by: Optional[str] = None


class ImpactAnalysisResponse(BaseModel):
    """影响分析响应"""

    code_references: list[dict] = Field(default_factory=list)
    variable_changes: dict = Field(default_factory=dict)
    config_dependencies: list[dict] = Field(default_factory=list)
    affected_files: list[str] = Field(default_factory=list)
    risk_level: str = "low"


class PromptTestRequest(BaseModel):
    """提示词测试请求"""

    prompt_key: str
    version: Optional[str] = None
    variables: dict = Field(default_factory=dict)


class PromptTestResponse(BaseModel):
    """提示词测试响应"""

    rendered_prompt: str
    variables_used: list[str] = Field(default_factory=list)
    variables_missing: list[str] = Field(default_factory=list)


class PromptComparisonResponse(BaseModel):
    """提示词对比响应"""

    version_1: PromptVersionResponse
    version_2: PromptVersionResponse
    diff: dict


class PromptItem(BaseModel):
    """提示词项"""

    key: str
    content: str
    version: Optional[str] = None
    description: Optional[str] = None


# --------------------------
# 提示词影响分析
# --------------------------


class CodeReference(BaseModel):
    """代码引用位置"""

    file: str
    line: int
    function: Optional[str] = None


class VariableChanges(BaseModel):
    """变量变更"""

    added: list[str] = Field(default_factory=list)
    removed: list[str] = Field(default_factory=list)
    modified: list[str] = Field(default_factory=list)


class ConfigDependency(BaseModel):
    """配置依赖"""

    param: str
    category: str
    description: str = ""
    current_value: Optional[str] = None


class ImpactAnalysisResult(BaseModel):
    """影响分析结果"""

    code_references: list[CodeReference] = Field(default_factory=list)
    variable_changes: VariableChanges = Field(default_factory=VariableChanges)
    config_dependencies: list[ConfigDependency] = Field(default_factory=list)
    affected_files: list[str] = Field(default_factory=list)
    risk_level: str = "low"
