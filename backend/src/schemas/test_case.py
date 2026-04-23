"""测试模块模型

包含 RAG 测试相关的 Pydantic 模型：
- TestCase: 测试用例
- TestCaseDraft: 测试用例草稿
- TestSet: 测试集
- TestRun: 测试运行批次
- TestResult: 测试结果
- GenerationParams: 生成参数
- 等请求/响应 DTO
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

# --------------------------
# 枚举定义
# --------------------------


class DraftStatus(str, Enum):
    """草稿状态"""

    DRAFT = "draft"
    REVIEWED = "reviewed"
    REJECTED = "rejected"
    IMPORTED = "imported"


class DocumentStatus(str, Enum):
    """文档状态"""

    UPLOADED = "uploaded"
    PARSING = "parsing"
    READY = "ready"
    ARCHIVED = "archived"


class TestRunStatus(str, Enum):
    """测试运行状态"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TestDomain(str, Enum):
    """测试领域"""

    GROSS_MOTOR = "gross_motor"
    FINE_MOTOR = "fine_motor"
    LANGUAGE = "language"
    COGNITIVE = "cognitive"
    SOCIAL_EMOTIONAL = "social_emotional"
    SENSORY_INTEGRATION = "sensory_integration"


class DifficultyLevel(str, Enum):
    """难度等级"""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class TestSourceType(str, Enum):
    """测试来源类型"""

    MANUAL = "manual"
    JSON_IMPORT = "json_import"
    BOOK_GENERATED = "book_generated"
    MIXED = "mixed"


class ReportExportFormat(str, Enum):
    """报告导出格式"""

    MARKDOWN = "markdown"
    PDF = "pdf"
    JSON = "json"


# --------------------------
# 核心模型
# --------------------------


class ChapterInfo(BaseModel):
    """章节信息"""

    title: str
    page_start: int
    page_end: int
    level: int


class QualityReport(BaseModel):
    """文档质量报告"""

    content_completeness: float
    text_extractability: float
    chapter_clarity: float
    suggested_domains: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    raw_text_length: int


class SourceDocument(BaseModel):
    """源文档"""

    id: str
    title: str
    file_type: str
    file_path: str
    file_hash: str
    content_summary: str = ""
    page_count: int = 0
    chapter_structure: List[ChapterInfo] = Field(default_factory=list)
    quality_report: Optional[QualityReport] = None
    status: DocumentStatus = DocumentStatus.UPLOADED
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class GenerationParams(BaseModel):
    """测试用例生成参数"""

    # 维度选择
    target_domains: List[str] = Field(default_factory=list, description="选中的发展领域")
    age_stages: List[str] = Field(default_factory=list, description="选中的年龄段标签（如 '3-6岁'）")

    # 每组合草稿数（替代旧 count）
    drafts_per_combination: int = Field(default=3, ge=1, le=10, description="每个组合生成草稿数")

    # 查询类型与难度
    query_types: List[str] = Field(
        default_factory=lambda: ["事实性查询", "比较性查询", "方案性查询"],
        description="选中的查询类型",
    )
    difficulty_levels: List[str] = Field(
        default_factory=lambda: ["入门级", "中级", "高级"],
        description="选中的难度级别",
    )

    # LLM 参数
    llm_model: str = Field(default="qwen-plus", description="使用的 LLM 模型")
    temperature: float = Field(default=0.8, ge=0.0, le=1.0, description="温度参数")

    # 执行模式
    mode: str = Field(default="append", pattern="^(append|overwrite)$", description="入库模式：追加/覆盖")

    # ========== 向后兼容字段（已废弃，仅用于旧 API 调用降级） ==========
    age_range: Optional[Tuple[int, int]] = Field(default=None, deprecated=True)
    count: Optional[int] = Field(default=None, deprecated=True)
    difficulty: Optional[str] = Field(default=None, deprecated=True)


class TestCaseDraft(BaseModel):
    """测试用例草稿"""

    id: str
    source_document_id: str
    source_document_name: Optional[str] = None
    query: str
    age: float  # 月龄（与 ORM DECIMAL(4,1) 一致，前端展示时取整）
    domain: str = ""
    age_stage_label: str = Field(default="", description="年龄段标签（如 '3-6岁'）")
    draft_index: int = Field(default=0, description="组合内草稿索引（0, 1, 2...）")
    batch_id: Optional[str] = Field(default=None, description="生成批次 ID")
    version: int = Field(default=1, description="乐观锁版本号")
    expected_knowledge_ids: List[str] = Field(default_factory=list)
    expected_keywords: List[str] = Field(default_factory=list)
    description: str = ""
    answer_points: List[str] = Field(default_factory=list)
    professional_terms: List[str] = Field(default_factory=list)
    age_requirement: str = ""
    generation_params: Optional[GenerationParams] = None
    status: DraftStatus = DraftStatus.DRAFT
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class TestSet(BaseModel):
    """测试集"""

    id: str
    name: str
    description: str = ""
    source_type: str = "manual"
    test_case_ids: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class TestCase(BaseModel):
    """测试用例"""

    id: str
    query: str
    age: int
    expected_knowledge_ids: List[str] = Field(default_factory=list)
    expected_keywords: List[str] = Field(default_factory=list)
    description: str = ""
    domain: str = Field(default="", description="测试领域")
    answer_points: List[str] = Field(default_factory=list, description="答题要点")
    professional_terms: List[str] = Field(default_factory=list, description="专业术语")
    age_requirement: str = Field(default="", description="年龄要求")
    relevance_scores: Dict[str, float] = Field(default_factory=dict, description="相关性评分")
    source_document_id: str = Field(default="", description="来源文档 ID")
    test_set_id: str = Field(default="", description="所属测试集 ID")
    version: int = Field(default=1, description="版本号")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class TestResultItem(BaseModel):
    """单个测试结果项"""

    test_case_id: str
    passed: bool
    precision: float
    recall: float
    f1: float
    execution_time_ms: int
    expected_knowledge_ids: List[str]
    actual_knowledge_ids: List[str]
    error_message: Optional[str] = None


class TestResult(BaseModel):
    """测试结果"""

    test_case_id: str
    query: str
    age: int
    precision: float
    recall: float
    f1_score: float
    mrr: float
    ndcg_at_k: float = 0.0
    results: List[TestResultItem] = Field(default_factory=list)
    executed_at: datetime = Field(default_factory=datetime.now)
    execution_time_ms: int = 0


class TestRun(BaseModel):
    """测试运行批次"""

    id: str
    name: str
    description: str = ""
    test_results: List[TestResult] = Field(default_factory=list)
    overall_precision: float = 0.0
    overall_recall: float = 0.0
    overall_f1: float = 0.0
    overall_mrr: float = 0.0
    overall_ndcg: float = 0.0
    total_test_cases: int = 0
    passed_test_cases: int = 0
    status: str = "pending"
    created_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    snapshot_id: Optional[str] = None
    config_version_id: Optional[str] = None
    config_snapshot: Optional[Dict[str, Any]] = None
    previous_config_version_id: Optional[str] = None


class KnowledgeSnapshot(BaseModel):
    """知识库快照"""

    id: str
    name: str
    description: str = ""
    document_count: int = 0
    document_hashes: List[str] = Field(default_factory=list)
    index_size_bytes: int = 0
    created_at: datetime = Field(default_factory=datetime.now)
    storage_path: str = ""


# --------------------------
# 请求 DTO
# --------------------------


class CreateTestCaseRequest(BaseModel):
    """创建测试用例请求"""

    query: str
    age: int
    expected_knowledge_ids: List[str] = []
    expected_keywords: List[str] = []
    description: str = ""


class UpdateTestCaseRequest(BaseModel):
    """更新测试用例请求"""

    query: Optional[str] = None
    age: Optional[int] = None
    expected_knowledge_ids: Optional[List[str]] = None
    expected_keywords: Optional[List[str]] = None
    description: Optional[str] = None


class CreateSnapshotRequest(BaseModel):
    """创建快照请求"""

    name: str = ""
    description: str = ""


class BatchImportRequest(BaseModel):
    """批量导入请求"""

    cases: List[dict]
    test_set_id: Optional[str] = None


class BatchDeleteRequest(BaseModel):
    """批量删除请求"""

    ids: List[str]


class RunTestsRequest(BaseModel):
    """运行测试请求"""

    name: str
    description: str = ""
    test_case_ids: List[str] = None
    test_set_id: str = None
    concurrency: int = 5


class GenerateDraftsRequest(BaseModel):
    """生成草稿请求"""

    params: GenerationParams


class CreateDraftRequest(BaseModel):
    """创建草稿请求"""

    source_document_id: str
    query: str
    age: int
    domain: str
    expected_knowledge_ids: List[str] = Field(default_factory=list)
    expected_keywords: List[str] = Field(default_factory=list)
    description: str = ""
    answer_points: List[str] = Field(default_factory=list)
    professional_terms: List[str] = Field(default_factory=list)
    age_requirement: str = ""


class UpdateDraftRequest(BaseModel):
    """更新草稿请求"""

    query: Optional[str] = None
    age: Optional[int] = None
    domain: Optional[str] = None
    expected_knowledge_ids: Optional[List[str]] = None
    expected_keywords: Optional[List[str]] = None
    description: Optional[str] = None
    answer_points: Optional[List[str]] = None
    professional_terms: Optional[List[str]] = None
    age_requirement: Optional[str] = None


class ImportDraftsRequest(BaseModel):
    """导入草稿请求"""

    draft_ids: List[str]


class CreateTestSetRequest(BaseModel):
    """创建测试集请求"""

    name: str
    description: str = ""


class UpdateTestSetRequest(BaseModel):
    """更新测试集请求"""

    name: Optional[str] = None
    description: Optional[str] = None


class AddCasesToSetRequest(BaseModel):
    """添加用例到测试集请求"""

    case_ids: List[str]
