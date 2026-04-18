"""调参建议数据模型"""

from pydantic import BaseModel
from typing import Any, Dict, List, Optional, Tuple


class TuningSuggestion(BaseModel):
    """单条调参建议"""

    id: Optional[str] = None
    param_name: str
    current_value: Any
    suggested_value: Any
    action: str
    reason: str
    expected_effect: str
    priority: str
    source: str
    safe_range: Optional[Tuple[Any, Any]] = None


class HistoryReference(BaseModel):
    """历史参考"""

    run_id: str
    date: str
    changed_params: Dict[str, Dict[str, Any]]
    metric_changes: Dict[str, Dict[str, Any]]
    conclusion: str


class LLMFinding(BaseModel):
    """LLM 诊断发现"""

    category: str
    description: str
    confidence: float


class LLMDiagnosis(BaseModel):
    """LLM 深度诊断结果"""

    summary: str
    findings: List[LLMFinding]
    recommendations: List["TuningSuggestion"]


class TuningSuggestionResponse(BaseModel):
    """调参建议完整响应"""

    run_id: str
    generated_at: str
    rule_engine_suggestions: List[TuningSuggestion]
    history_references: List[HistoryReference]
    llm_diagnosis: Optional[LLMDiagnosis] = None
    conflict_filtered_count: int = 0
    total_suggestions: int
