from typing import List, Dict, Optional, Literal, Union, Any
from pydantic import BaseModel, Field, conlist, constr

# --------------------------
# 基础枚举与类型定义
# --------------------------
GenderType = Literal["male", "female", "other"]
IntensityType = Literal["low", "medium", "high"]
RiskLevel = Literal["Low", "Medium", "High"]
StatusType = Literal["normal", "weak", "deficit", "unstable", "strong"]

# --------------------------
# 输入数据模型 (Input Models)
# --------------------------

class ChildProfile(BaseModel):
    """儿童基本画像"""
    name: str = Field(..., description="儿童姓名或昵称")
    age: int = Field(..., ge=0, le=18, description="年龄（岁）")
    gender: GenderType = Field(..., description="性别")
    issues: List[str] = Field(default_factory=list, description="家长关注的问题或症状，如'注意力不集中'")
    interests: List[str] = Field(default_factory=list, description="兴趣爱好")

class Activity(BaseModel):
    """单项活动计划"""
    name: str = Field(..., description="活动名称")
    duration_minutes: int = Field(..., gt=0, description="单次时长（分钟）")
    frequency_weekly: int = Field(..., gt=0, description="每周频次")
    intensity: Optional[IntensityType] = Field(None, description="运动强度（可选，由系统推断）")
    description: Optional[str] = Field(None, description="活动描述或备注")

class ProposedPlan(BaseModel):
    """拟定运动计划"""
    plan_name: str = Field(..., description="计划名称")
    activities: List[Activity] = Field(..., min_items=1, description="包含的活动列表")
    goals: List[str] = Field(..., description="计划目标，如'提升平衡感'")

class HistoryActivity(BaseModel):
    """历史活动记录"""
    name: str
    duration_minutes: int
    intensity: Optional[IntensityType] = None
    feedback: Optional[str] = None

class HistoryRecord(BaseModel):
    """单日历史记录"""
    date: str = Field(..., description="日期 YYYY-MM-DD")
    activities: List[HistoryActivity]
    notes: Optional[str] = None

class UserInput(BaseModel):
    """API 总入口模型"""
    child_profile: ChildProfile
    proposed_plan: ProposedPlan
    history_context: Optional[List[HistoryRecord]] = Field(default_factory=list, description="原始历史记录")

# --------------------------
# 中间状态模型 (Intermediate State Models)
# --------------------------

class CondensedContext(BaseModel):
    """压缩后的上下文特征"""
    weekly_avg_duration: float = Field(0.0, description="周平均时长")
    frequency_consistency: float = Field(0.0, description="频率一致性得分")
    intensity_trend: str = Field("stable", description="强度趋势")
    diversity_score: float = Field(0.0, description="多样性得分")
    recent_feedbacks: List[str] = Field(default_factory=list, description="最近的关键反馈摘要")

class DevelopmentStatus(BaseModel):
    """单项能力发展状态"""
    status: StatusType
    level: int = Field(..., ge=1, le=5, description="等级 1-5")
    description: str

class ChildState(BaseModel):
    """儿童综合发展状态评估"""
    vestibular_system: Optional[DevelopmentStatus] = None # 前庭
    proprioception: Optional[DevelopmentStatus] = None    # 本体
    tactile_system: Optional[DevelopmentStatus] = None    # 触觉
    core_strength: Optional[DevelopmentStatus] = None     # 核心力量
    emotional_regulation: Optional[DevelopmentStatus] = None # 情绪调节
    # 可扩展其他维度
    overall_assessment: str = Field("", description="综合评估文本")

class KnowledgeItem(BaseModel):
    """检索到的知识条目"""
    content: str
    source_book: str
    chapter_title: Optional[str] = None
    page_label: Optional[str] = None
    topics: List[str] = Field(default_factory=list)
    brain_regions: List[str] = Field(default_factory=list)
    benefits: List[str] = Field(default_factory=list)
    risk_level: RiskLevel = "Low"
    target_age_min: int = 0
    target_age_max: int = 18
    activity_type: Optional[str] = None
    relevance_score: float = 0.0

class EvaluationResult(BaseModel):
    """评分结果"""
    score: float = Field(..., ge=0, le=100, description="总分")
    reasoning: str = Field(..., description="评分理由")
    shap_explanation: Dict[str, float] = Field(default_factory=dict, description="SHAP 值解释")
    suggestions: List[str] = Field(default_factory=list, description="改进建议")

class FinalReport(BaseModel):
    """最终输出报告"""
    markdown_content: str = Field(..., description="完整的 Markdown 报告内容")
    structured_data: Dict[str, Any] = Field(default_factory=dict, description="用于前端可视化的结构化数据")

# --------------------------
# LangGraph State
# --------------------------

class AgentState(BaseModel):
    """LangGraph 状态定义"""
    input_text: Optional[str] = None
    child_profile: ChildProfile
    proposed_plan: ProposedPlan
    child_state: Optional[ChildState] = None
    condensed_context: Optional[CondensedContext] = None
    retrieved_docs: List[KnowledgeItem] = Field(default_factory=list)
    evaluation_result: Optional[EvaluationResult] = None
    final_report: Optional[FinalReport] = None
    messages: List[Dict[str, str]] = Field(default_factory=list, description="对话历史")
