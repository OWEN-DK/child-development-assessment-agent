"""评估模块模型

包含儿童发展评估相关的 Pydantic 模型：
- ChildProfile: 儿童基本画像
- Activity: 单项活动计划
- ProposedPlan: 拟定运动计划
- UserInput: API 总入口模型
- ChildState: 儿童综合发展状态评估
- FinalReport: 最终输出报告
- AgentState: LangGraph 状态定义
- 等中间状态模型
"""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

# --------------------------
# 基础枚举与类型定义
# --------------------------
GenderType = Literal["male", "female", "other"]
IntensityType = Literal["low", "medium", "high"]
ActivityCategory = Literal[
    "vestibular",  # 前庭 (旋转/平衡)
    "proprioception",  # 本体 (重力/挤压)
    "tactile",  # 触觉
    "fine_motor",  # 精细运动
    "gross_motor",  # 粗大运动
    "cardio",  # 心肺/有氧
    "other",
]
RiskLevel = Literal["Low", "Medium", "High"]
StatusType = Literal["normal", "weak", "deficit", "unstable", "strong", "unknown"]


# --------------------------
# 输入数据模型 (Input Models)
# --------------------------


class ChildProfile(BaseModel):
    """儿童基本画像"""

    name: str = Field(..., description="儿童姓名或昵称")
    age: int = Field(..., ge=0, le=18, description="年龄（岁）")
    gender: GenderType = Field(..., description="性别")
    issues: List[str] = Field(default_factory=list, description="家长关注的问题或症状")
    interests: List[str] = Field(default_factory=list, description="兴趣爱好")


class Activity(BaseModel):
    """单项活动计划"""

    name: str = Field(..., description="活动名称")
    duration_minutes: int = Field(..., gt=0, description="单次时长（分钟）")
    frequency_weekly: int = Field(..., gt=0, description="每周频次")
    intensity: Optional[IntensityType] = Field(None, description="运动强度")
    category: Optional[ActivityCategory] = Field(None, description="运动类别")
    description: Optional[str] = Field(None, description="活动描述或备注")


class ProposedPlan(BaseModel):
    """拟定运动计划"""

    plan_name: str = Field(..., description="计划名称")
    activities: List[Activity] = Field(..., min_length=1, description="包含的活动列表")
    goals: List[str] = Field(..., description="计划目标")


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
    is_streaming: bool = Field(False, description="是否启用流式输出")


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

    vestibular_system: Optional[DevelopmentStatus] = None
    proprioception: Optional[DevelopmentStatus] = None
    tactile_system: Optional[DevelopmentStatus] = None
    core_strength: Optional[DevelopmentStatus] = None
    emotional_regulation: Optional[DevelopmentStatus] = None
    overall_assessment: str = Field("", description="综合评估文本")


class KnowledgeItem(BaseModel):
    """检索到的知识条目"""

    id: Optional[str] = Field(default=None, description="知识项唯一标识")
    content: str
    source_book: str
    chapter_title: Optional[str] = None
    page_label: Optional[str] = None
    topics: List[str] = Field(default_factory=list)
    brain_regions: List[str] = Field(default_factory=list)
    benefits: List[str] = Field(default_factory=list)
    risk_level: RiskLevel = "Low"
    activity_type: Optional[str] = None
    relevance_score: float = Field(default=0.0, description="检索相关性分数")
    metadata: dict = Field(default_factory=dict, description="扩展元数据（如子查询来源等）")


class DimensionAnalysis(BaseModel):
    """单项维度分析详情"""

    score: float
    weight: float
    analysis: str
    issues: List[str] = Field(default_factory=list)


class EvaluationResult(BaseModel):
    """评分结果"""

    score: float = Field(..., ge=0, le=100, description="总分")
    reasoning: str = Field(..., description="评分理由")
    shap_explanation: Dict[str, float] = Field(default_factory=dict, description="SHAP 值解释")
    dimension_analysis: Dict[str, DimensionAnalysis] = Field(default_factory=dict, description="分项维度详细分析")
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
    history_context: Optional[List[HistoryRecord]] = Field(default_factory=list, description="原始历史记录")
    retrieved_docs: List[KnowledgeItem] = Field(default_factory=list)
    evaluation_result: Optional[EvaluationResult] = None
    final_report: Optional[FinalReport] = None
    messages: List[Dict[str, str]] = Field(default_factory=list, description="对话历史")
    report_prompts: Optional[List[str]] = Field(None, description="用于流式生成的 Prompt 列表")
    is_streaming: bool = Field(False, description="是否启用流式输出")
