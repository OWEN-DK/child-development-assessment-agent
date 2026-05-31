"""知识问答系统 Schema 定义

包含：
- API 请求/响应模型
- LangGraph State 定义
- 业务实体模型（MatchedBook, Citation, SectionOutput）
- response_format Schema（Agent 结构化输出）
- 逐节 structured_data 模型
- 异常类定义
- 进度推送 ContextVar
"""

import contextvars
import operator
from enum import Enum, IntEnum
from typing import Annotated, Any, Awaitable, Callable, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


def _parse_list_field(v):
    """qwen 模型有时将列表字段输出为 JSON 字符串，需自动解析"""
    if isinstance(v, str):
        try:
            import json
            from json_repair import repair_json
            return json.loads(repair_json(v))
        except Exception:
            return []
    return v

from src.utils.exceptions import (
    AppException,
    NoMatchingBooksException,
    RAGUnavailableException,
    KnowledgeQATooManyRequestsException,
)


# ==================== 错误码枚举 ====================


class ErrorCode(IntEnum):
    """知识问答业务错误码"""

    SUCCESS = 0
    NO_MATCHING_BOOKS = 17001
    RAG_UNAVAILABLE = 17002
    TASK_NOT_FOUND = 17004
    TOO_MANY_REQUESTS = 17003
    VALIDATION_ERROR = 4220
    GENERATION_FAILED = 17005


# 向后兼容别名（与实现文档中的名称一致）
NoMatchingBooksError = NoMatchingBooksException
RAGUnavailableError = RAGUnavailableException
TooManyRequestsError = KnowledgeQATooManyRequestsException


# ==================== API 请求模型 ====================


class KnowledgeQARequest(BaseModel):
    """POST /api/v1/knowledge-qa 请求体"""

    question: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="用户自然语言问题",
    )
    book_ids: Optional[List[str]] = Field(
        default=None,
        description="指定书籍 ID，空数组或不传则自动匹配",
    )
    options: Optional[Dict[str, Any]] = Field(
        default=None,
        description="可选参数: language(默认 zh-CN), stream(默认 true)",
    )

    @field_validator("question")
    @classmethod
    def question_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("问题不能为空")
        return v


class TaskStatusResponse(BaseModel):
    """GET /api/v1/knowledge-qa/status/{task_id} 响应 data"""

    task_id: str
    status: str  # pending | running | completed | failed | cancelled
    progress: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None


# ==================== 业务实体模型 ====================


class MatchedBook(BaseModel):
    """匹配到的书籍信息"""

    book_id: str = Field(..., description="SourceDocument.id")
    title: str = Field(..., description="书名")
    author: Optional[str] = Field(default=None, description="作者")
    source_type: str = Field(
        default="book",
        description="文献类型: book / paper / guideline / manual",
    )
    match_reason: str = Field(
        ...,
        description="匹配理由，如 '用户明确提及书名' / '与问题中的注意力主题高度相关'",
    )
    is_primary: bool = Field(
        default=False,
        description="是否为主参考书。多匹配时取匹配度最高者",
    )


class Citation(BaseModel):
    """单条引用，所有节复用"""

    citation_id: str = Field(
        ...,
        description="全局唯一引用 ID，如 C1、C01、C001",
        pattern=r"^C\d+$",
    )
    book_title: str = Field(..., description="书名")
    chapter: str = Field(..., description="章节，如 '第3章' 或 '第3章 运动与注意力'")
    excerpt: str = Field(
        ...,
        max_length=300,
        description="内容摘要，允许概括，≤300 字",
    )
    relevance: str = Field(
        ...,
        description="与该节内容的关联说明，一句话",
    )


class SectionOutput(BaseModel):
    """单节生成结果"""

    index: int = Field(..., ge=1, le=5, description="节序号 1-5")
    title: str = Field(..., description="节标题")
    content: str = Field(
        ...,
        min_length=1,
        description="Markdown 正文",
    )
    citations: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="本节引用列表。正常模式至少 1 条，降级模式可为空",
    )
    structured_data: Dict[str, Any] = Field(
        default_factory=dict,
        description="结构化数据，字段因节而异，无值填 null",
    )


# ==================== response_format Schema ====================


class MatchedBookItem(BaseModel):
    """匹配到的单本书籍（match_books Agent 输出用）"""

    book_id: str = Field(..., description="SourceDocument.id")
    title: str = Field(..., description="书名")
    author: Optional[str] = Field(default=None, description="作者")
    source_type: str = Field(default="book", description="book/paper/guideline/manual")
    match_reason: str = Field(..., description="匹配理由")


class MatchedBookSchema(BaseModel):
    """match_books Agent 的 response_format"""

    matched_books: List[MatchedBookItem] = Field(
        default_factory=list,
        description="匹配到的书籍列表，按匹配度排序。无匹配时为空数组",
    )

    @field_validator("matched_books", mode="before")
    @classmethod
    def _parse_matched_books(cls, v):
        return _parse_list_field(v)


class Section1Response(BaseModel):
    """analyze_child Agent 的 response_format"""

    title: str = Field(default="孩子状态分析")
    content: str = Field(..., description="Markdown 正文")
    citations: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="引用列表。第 1 节会搜索知识库获取专业背景知识，citations 同样要求非空",
    )
    structured_data: Dict[str, Any] = Field(
        default_factory=dict, description="第 1 节结构化数据"
    )

    @field_validator("citations", mode="before")
    @classmethod
    def _parse_citations(cls, v):
        return _parse_list_field(v)


class ProblemItem(BaseModel):
    """识别出的问题项"""
    name: str = Field(default="", description="问题名称/简述")
    description: str = Field(default="", description="问题描述")
    severity: Literal["高", "中", "低", "待评估"] = Field(default="待评估", description="严重程度")
    category: str = Field(default="", description="问题分类（如：注意力、情绪、社交）")
    source_books: List[str] = Field(
        default_factory=list,
        description="此问题在哪些书籍中被提及（书名列表，从搜索结果 📖 前缀中提取）",
    )


class Section2StructuredData(BaseModel):
    """第 2 节结构化数据 — 问题识别"""
    problems: List[ProblemItem] = Field(default_factory=list, description="问题列表")


class Section2Response(BaseModel):
    """identify_problems Agent 的 response_format"""

    title: str = Field(default="问题识别")
    content: str = Field(..., description="Markdown 正文")
    citations: List[Dict[str, Any]] = Field(
        default_factory=list, description="引用列表"
    )
    structured_data: Section2StructuredData = Field(
        default_factory=Section2StructuredData, description="第 2 节结构化数据"
    )

    @field_validator("citations", mode="before")
    @classmethod
    def _parse_citations(cls, v):
        return _parse_list_field(v)


class ExerciseTypeItem(BaseModel):
    """运动类型推荐项 — 每项代表一种从权威运动清单中选出的运动类型。

    字段与 section_3 prompt 中的输出格式保持一致。
    """
    type_id: str = Field(
        ...,
        pattern=r"^ET\d{3}$",
        description="运动类型唯一ID，格式 ET001-ET999",
    )
    name: str = Field(
        ...,
        min_length=1,
        description="运动名称，必须精确匹配权威运动清单中的名称",
    )
    tier: Literal["primary", "secondary", "supplementary"] = Field(
        default="secondary",
        description="推荐层级：primary=核心推荐, secondary=辅助推荐, supplementary=补充推荐",
    )
    category: str = Field(
        default="",
        description="运动分类，必须与权威运动清单'运动类型'列一致（如：行走/跑步/力量训练/舞蹈）",
    )
    target_problem_ids: List[str] = Field(
        default_factory=list,
        description="针对的问题ID列表，引用第2节中的 problem_id",
    )
    target_skills: List[str] = Field(
        default_factory=list,
        description="主要训练的能力（如：专注力、身体协调、情绪调节）",
    )
    recommendation_rationale: str = Field(
        default="",
        description="推荐理由，包含脑区/神经机制说明",
    )
    citation_ids: List[str] = Field(
        default_factory=list,
        description="支持的引用ID列表，如 [\"C001\", \"C002\"]",
    )
    source_books: List[str] = Field(
        default_factory=list,
        description="此运动类型推荐的来源书籍（书名列表，从搜索结果 📖 前缀中提取）",
    )


class Section3StructuredData(BaseModel):
    """第 3 节结构化数据 — 运动类型推荐"""
    exercise_types: List[ExerciseTypeItem] = Field(
        default_factory=list,
        min_length=1,
        description="推荐的运动类型列表（至少 1 个）",
    )
    child_age_group: str = Field(default="", description="适用年龄段，如 '8-12岁男孩'")

    @field_validator("exercise_types")
    @classmethod
    def _check_non_empty(cls, v: list) -> list:
        if not v:
            raise ValueError("exercise_types 不能为空，至少需要 1 个运动类型推荐")
        seen = set()
        for item in v:
            if item.name in seen:
                raise ValueError(f"运动名称重复: {item.name}")
            seen.add(item.name)
        return v


class Section3Response(BaseModel):
    """recommend_types Agent 的 response_format"""

    title: str = Field(default="运动类型推荐")
    content: str = Field(..., description="Markdown 正文")
    citations: List[Dict[str, Any]] = Field(
        default_factory=list, description="引用列表"
    )
    structured_data: Section3StructuredData = Field(
        default_factory=Section3StructuredData, description="第 3 节结构化数据"
    )

    @field_validator("citations", mode="before")
    @classmethod
    def _parse_citations(cls, v):
        return _parse_list_field(v)


class S3SelectionItem(BaseModel):
    """S3 节点 LLM 轻量输出 — 只含需要判断力的 4 个字段。

    name/category/target_skills/citation_ids/source_books 由后端代码填充。
    """

    type_id: str = Field(pattern=r"^ET\d{3}$", description="运动类型 ID，必须来自候选运动表")
    tier: Literal["primary", "secondary", "supplementary"] = Field(
        description="推荐层级：primary=核心推荐, secondary=辅助推荐, supplementary=补充推荐",
    )
    target_problem_ids: List[str] = Field(
        default_factory=list,
        description="针对的问题 ID 列表，引用第 2 节的 problem_id",
    )
    recommendation_rationale: str = Field(
        default="",
        description="推荐理由（含脑区/神经机制说明）",
    )


class S3SelectionResponse(BaseModel):
    """S3 节点 LLM response_format — 轻量版，仅含选择结果。"""

    selections: List[S3SelectionItem] = Field(
        min_length=1, max_length=10,
        description="从候选运动表中选择的结果列表",
    )
    child_age_group: str = Field(default="", description="适用年龄段，如 '8-12岁男孩'")


class Section4OutlineResponse(BaseModel):
    """plan_outline Agent 的 response_format"""

    title: str = Field(default="运动方案大纲")
    content: str = Field(..., description="大纲 Markdown 正文")
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    phases: List[Dict[str, Any]] = Field(
        default_factory=list,
        min_length=1,
        description="阶段列表（顶层字段），至少 1 个阶段。每项含 phase_id(PH01)/name/goal/duration_weeks/weeks[]",
    )
    structured_data: Dict[str, Any] = Field(
        default_factory=dict, description="plan_summary/caution 等补充数据"
    )

    @field_validator("phases")
    @classmethod
    def _check_phases_non_empty(cls, v: list) -> list:
        if not v:
            raise ValueError("phases 不能为空，至少需要 1 个阶段")
        return v

    @field_validator("citations", mode="before")
    @classmethod
    def _parse_citations(cls, v):
        return _parse_list_field(v)

    @field_validator("phases", mode="before")
    @classmethod
    def _parse_phases(cls, v):
        return _parse_list_field(v)


class Section5Response(BaseModel):
    """conclusion Agent 的 response_format"""

    title: str = Field(default="最终结论")
    content: str = Field(..., description="结论 Markdown 正文")
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    structured_data: Dict[str, Any] = Field(
        default_factory=dict, description="第 5 节结构化数据"
    )

    @field_validator("citations", mode="before")
    @classmethod
    def _parse_citations(cls, v):
        return _parse_list_field(v)


# ==================== IntensityLevel 枚举 ====================


class IntensityLevel(str, Enum):
    """运动强度级别（标准化 5 级）"""
    LOW = "low"
    LOW_MODERATE = "low-moderate"
    MODERATE = "moderate"
    MODERATE_HIGH = "moderate-high"
    HIGH = "high"


INTENSITY_MAP: dict[str, IntensityLevel] = {
    "低强度": IntensityLevel.LOW,
    "零强度": IntensityLevel.LOW,
    "被动/低强度": IntensityLevel.LOW,
    "中低强度": IntensityLevel.LOW_MODERATE,
    "低-中强度": IntensityLevel.LOW_MODERATE,
    "中强度": IntensityLevel.MODERATE,
    "中-高强度": IntensityLevel.MODERATE_HIGH,
    "中高强度": IntensityLevel.MODERATE_HIGH,
    "高强度": IntensityLevel.HIGH,
    "高强度耐力": IntensityLevel.HIGH,
    "极高强度耐力": IntensityLevel.HIGH,
}


def map_intensity(raw: str | None) -> IntensityLevel | None:
    """中文强度描述 → IntensityLevel 枚举。

    策略：精确匹配 → 前缀匹配兜底。
    """
    if not raw:
        return None
    raw = raw.strip()
    result = INTENSITY_MAP.get(raw)
    if result:
        return result
    # 前缀匹配：处理 "中强度（最大心率65%-75%）" 等带括号描述
    for cn, enum_val in INTENSITY_MAP.items():
        if raw.startswith(cn[:2]) or cn.startswith(raw[:2]):
            return enum_val
    return None


# ==================== 第 4 节结构化数据 ====================


class ExerciseParamsItem(BaseModel):
    """单条运动完整参数 — plan_expand_parallel 分组的 LLM 输出单元。"""

    exercise_id: str = Field(..., description="EX001 格式唯一ID，使用大纲中的原始ID")
    name: str = Field(..., description="运动名称（必须来自大纲，不允许编造）")
    type_id: str = Field(..., description="关联第3节 exercise_type.type_id")
    category: str = Field(default="", description="运动分类")
    duration_min: int = Field(default=0, description="单次时长(分钟)")
    intensity: str = Field(default="中", description="强度等级: 低/中/中高/高")
    intensity_hint: str = Field(default="", description="强度感知描述")
    sets: Optional[int] = Field(default=None, description="组数")
    reps: Optional[str] = Field(default=None, description="每组次数")
    rest_seconds: Optional[int] = Field(default=None, description="组间休息(秒)")
    target_skill: str = Field(default="", description="主要训练目标")
    notes: str = Field(default="", description="执行要点/教练提示")
    alternatives: List[str] = Field(default_factory=list, description="替代运动")
    citation_ids: List[str] = Field(default_factory=list, description="引用的 citation_id 列表")


class ExerciseGroupResponse(BaseModel):
    """plan_expand_parallel 单组的 response_format — 多个运动的参数块。"""

    exercises: List[ExerciseParamsItem] = Field(..., description="本组所有运动的完整参数列表")

    @field_validator("exercises", mode="before")
    @classmethod
    def _parse_exercises(cls, v):
        return _parse_list_field(v)


class Exercise(BaseModel):
    """单条运动方案（保留，供 Section4StructuredData 使用）"""

    exercise_id: str = Field(..., description="EX001 格式唯一ID")
    name: str = Field(..., description="运动名称")
    type_id: str = Field(..., description="关联第3节 exercise_type.type_id")
    duration_min: int = Field(default=15, description="单次时长(分钟)")
    intensity: str = Field(default="中", description="强度等级: 低/中/高")
    intensity_hint: str = Field(default="", description="强度感知描述，如'能说话不能唱歌'")
    target_skill: str = Field(default="", description="主要训练目标，如'专注力'、'抑制控制'")
    sets: Optional[int] = Field(default=None, description="组数")
    reps: Optional[int] = Field(default=None, description="每组次数")
    description: str = Field(default="", description="执行要点和家长指导")


class Day(BaseModel):
    """单日计划"""

    day_index: int = Field(..., description="日序号，从1开始")
    main_exercises: List[Exercise] = Field(default_factory=list)


class Week(BaseModel):
    """单周计划"""

    week_index: int = Field(..., description="周序号，从1开始")
    days: List[Day] = Field(default_factory=list)


class Phase(BaseModel):
    """训练阶段"""
    model_config = {'populate_by_name': True}

    phase_name: str = Field(..., alias="name", description="阶段名称，如 '适应期'、'强化期'")
    weeks: List[Week] = Field(default_factory=list)


class PlanSummary(BaseModel):
    """方案摘要"""

    total_duration_days: int = Field(..., description="总天数")
    total_phases: int = Field(..., description="阶段数")
    daily_duration_min: int = Field(..., description="每日训练时长(分钟)")
    weekly_frequency: int = Field(..., description="每周训练频率(天)")
    intensity_overall: str = Field(default="中", description="整体强度: 低/中/高")


class Section4StructuredData(BaseModel):
    """第 4 节结构化数据 — plan_expand_content_node 的 response_format。
    所有字段均为必填，Pydantic 强制校验。Markdown 正文由 _render_s4_markdown 渲染。
    """

    exercise_types: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="方案中所有运动的扁平列表，每项与 S3 ExerciseTypeItem 同构（type_id/name/tier/category/target_skills/recommendation_rationale/citation_ids）",
    )
    phases: List[Phase] = Field(..., min_length=1, description="阶段计划，至少1个阶段")
    plan_summary: PlanSummary = Field(..., description="方案摘要")
    caution: str = Field(..., description="注意事项")

    @field_validator("phases", mode="before")
    @classmethod
    def _parse_phases(cls, v):
        return _parse_list_field(v)


# ==================== 最终响应模型 ====================


class GenerationMetadata(BaseModel):
    """生成元信息"""

    total_sections: int = Field(default=5)
    total_citations: int = Field(default=0)
    total_time_ms: int = Field(default=0)
    model_used: str = Field(default="qwen3.5-27b")
    review_model_used: str = Field(default="qwen3.5-27b")
    retries: Dict[str, int] = Field(default_factory=dict)
    partial: bool = Field(default=False)
    search_coverage: Dict[str, int] = Field(
        default_factory=dict,
        description="每本书的搜索命中条数，如 {'运动改变大脑': 12, '儿童发展心理学': 5}",
    )


class KnowledgeQAResponse(BaseModel):
    """最终 JSON 响应 data 部分"""

    question: str
    matched_books: List[MatchedBook]
    sections: List[SectionOutput]
    generation_metadata: GenerationMetadata
    contradictions: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="跨书籍矛盾发现列表",
    )


class KnowledgeQAError(BaseModel):
    """错误响应 data 部分"""

    error: str  # no_matching_books | rag_unavailable | generation_failed
    message: str


# ==================== LangGraph State ====================


class KnowledgeQAState(BaseModel):
    """LangGraph StateGraph 的状态定义。

    贯穿全流程，所有节点通过返回 Dict 更新此 State。
    中间状态仅在任务生命周期内有效（Redis + 内存），任务完成后清理。

    注意：prompt_manager 不在此 State 中，通过 ContextVar 传递，避免序列化问题。
    """

    # ===== 输入 =====
    question: str = Field(default="", description="用户原始问题")

    # ===== match_books 输出 =====
    matched_book_ids: List[str] = Field(
        default_factory=list,
        description="匹配到的书籍 ID。各 Agent 节点在调用 search_knowledge_base 工具时传入此列表以缩小检索范围",
    )
    matched_books_detail: List[MatchedBook] = Field(
        default_factory=list,
        description="完整书籍匹配信息，供 finalize 输出",
    )

    # ===== 逐节输出 =====
    sections: Dict[int, SectionOutput] = Field(
        default_factory=dict,
        description="各节生成结果，key 为节号 1-5",
    )

    # ===== 逐节搜索 query（section-specific） =====
    section_queries: Dict[int, str] = Field(
        default_factory=dict,
        description="每节的搜索查询词。match_books 根据查询分析结果构造，替代原始问题以避免关键词偏置。key 为节号 1-5",
    )

    # ===== 第 4 节大纲中间产物 =====
    section_4_outline: Optional[Dict[str, Any]] = Field(
        default=None,
        description="plan_outline 产出的大纲，plan_expand 以此为输入展开",
    )
    section_4_slots: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="plan_expand_parallel 从大纲提取的运动槽位列表（含定位信息）",
    )
    section_4_group_results: Optional[Dict[str, Any]] = Field(
        default=None,
        description="plan_expand_parallel 分组并行展开结果 {group_idx: [ExerciseParamsItem]}",
    )

    # ===== 知识上下文（LazyGraphRAG 预取） =====
    knowledge_context: str = Field(
        default="",
        description="Service 层在调用图前预取的知识上下文（Markdown），注入各节 user_message",
    )

    # ===== 运动清单约束（权威来源：《运动改变大脑》） =====
    exercise_context: str = Field(
        default="",
        description="Service 层加载的权威运动清单（Markdown），仅注入 S3/S4 的 user_message 作为硬约束",
    )

    # ===== S3 预筛选结果（调试/审计用） =====
    filtered_exercise_candidates: str = Field(
        default="",
        description="S3 预筛选后的运动候选 Markdown，仅供审计和调试。"
        "仅由 recommend_types_node 写入，其他节点不得依赖此字段作为输入。",
    )

    # ===== 进度 =====
    current_step: Annotated[List[str], operator.add] = Field(
        default_factory=list,
        description="当前执行步骤标识列表，供 SSE 进度推送",
    )

    # ===== 异常与降级 =====
    errors: List[str] = Field(
        default_factory=list,
        description="累积的非致命错误信息",
    )
    partial: bool = Field(
        default=False,
        description="是否为降级结果 (超时/部分失败)",
    )

    # ===== 重试计数 =====
    retry_counts: Dict[str, int] = Field(
        default_factory=dict,
        description="各 Agent 节点的 LLM 异常重试次数",
    )

    # ===== S4 方案生成重试 =====
    s4_retry_count: int = Field(
        default=0,
        description="plan_outline/plan_expand/plan_assemble 链路重试次数",
    )
    s4_needs_retry: bool = Field(
        default=False,
        description="S4 链路是否需要重试（由 plan_assemble 降级时设置，_route_after_s4_assemble 消费）",
    )

    # ===== 矛盾审计 =====
    contradictions: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="跨书籍矛盾发现列表（contradiction_audit_node 产出，conclusion_node 消费）",
    )

    # ===== 搜索缓存 =====
    search_cache: Dict[str, List[Dict[str, Any]]] = Field(
        default_factory=dict,
        description="RAG 搜索结果缓存，key=question|book_ids，避免重复搜索",
    )

    # ===== Neo4j 知识图谱 (Layer 1) =====
    neo4j_knowledge: Dict[str, Any] = Field(
        default_factory=dict,
        description="Neo4j 知识图谱查询结果 (query_neo4j_graph_node 写入)。keys: exercises, cross_book_relations, problem_context, source_coverage",
    )


    # ===== 自定义知识（最高优先级，引导下游搜索） =====
    custom_knowledge_context: str = Field(
        default="",
        description="自定义知识命中后注入的上下文 Markdown (fast_knowledge_match_node 写入)",
    )
    custom_knowledge_entities: List[str] = Field(
        default_factory=list,
        description="从自定义知识中提取的关键实体名，传递给下游搜索节点作为引导",
    )
    fast_knowledge_hit: bool = Field(
        default=False,
        description="自定义知识是否命中",
    )
    three_layer_synthesis: Dict[str, Any] = Field(
        default_factory=dict,
        description="三层知识综合结果 (knowledge_synthesis_v2_node 写入)。keys: consensus, complementary, conflicts",
    )

    class Config:
        arbitrary_types_allowed = True


# ==================== 进度推送 ContextVar ====================

_progress_callback: contextvars.ContextVar[Optional[Callable[..., Awaitable[None]]]] = (
    contextvars.ContextVar("knowledge_qa_progress_callback", default=None)
)

_progress_ctx: contextvars.ContextVar[Optional[Dict[str, Any]]] = (
    contextvars.ContextVar("knowledge_qa_progress_ctx", default=None)
)

_partial_collector: contextvars.ContextVar[Optional[Dict[str, Any]]] = (
    contextvars.ContextVar("knowledge_qa_partial_collector", default=None)
)


def set_progress_context(callback, task_id: str, task_type: str, cancellation_event=None):
    """由 Service 在 graph.ainvoke 前调用"""
    _progress_callback.set(callback)
    _progress_ctx.set({"task_id": task_id, "task_type": task_type, "cancellation_event": cancellation_event})


def get_progress_context() -> Optional[Dict[str, Any]]:
    """Agent 节点内调用，获取当前进度上下文"""
    return _progress_ctx.get()


def clear_progress_context():
    """由 Service 在 graph.ainvoke 后调用"""
    _progress_callback.set(None)
    _progress_ctx.set(None)


async def push_progress(step: str, message: str, **meta):
    """Agent 节点内调用，线程安全"""
    cb = _progress_callback.get()
    if cb:
        try:
            await cb(step, message, **meta)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"push_progress 失败: step={step}, error={e}", exc_info=True)
    else:
        import logging
        logging.getLogger(__name__).warning(f"push_progress 回调为空: step={step}")


def init_partial_collector():
    """兼容旧测试脚本的占位初始化。"""
    _partial_collector.set({})


def clear_partial_collector():
    """兼容旧测试脚本的占位清理。"""
    _partial_collector.set(None)


# ==================== Prompt Manager ContextVar ====================

_prompt_manager: contextvars.ContextVar[Optional[Any]] = (
    contextvars.ContextVar("knowledge_qa_prompt_manager", default=None)
)


def set_prompt_manager(prompt_manager):
    """由 Service 在 graph.ainvoke 前调用"""
    _prompt_manager.set(prompt_manager)


def clear_prompt_manager():
    """由 Service 在 graph.ainvoke 后调用"""
    _prompt_manager.set(None)


def get_prompt_manager():
    """Agent 节点内调用，获取 prompt_manager 实例"""
    pm = _prompt_manager.get()
    if pm is None:
        raise RuntimeError("prompt_manager 未设置，请确保 Service 已调用 set_prompt_manager()")
    return pm
