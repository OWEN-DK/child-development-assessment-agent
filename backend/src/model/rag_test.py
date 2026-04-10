from typing import Dict, List, Optional, Any, Tuple
from pydantic import BaseModel, Field
from datetime import datetime
from nanoid import generate
from src.constants.test_case import TEST_CASE_DOMAINS
from enum import Enum


class DocumentStatus(str, Enum):
    UPLOADED = "uploaded"
    PARSING = "parsing"
    READY = "ready"
    ARCHIVED = "archived"


class DraftStatus(str, Enum):
    DRAFT = "draft"
    REVIEWED = "reviewed"
    REJECTED = "rejected"
    IMPORTED = "imported"


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
    """原始文档"""

    id: str = Field(default_factory=lambda: f"doc_{generate(size=10)}")
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

    target_domains: List[str] = Field(default_factory=list)
    age_range: Tuple[int, int] = Field(default=(0, 18))
    count: int = 10
    difficulty: str = "medium"
    llm_model: str = "qwen-plus"
    temperature: float = 0.7


class TestCaseDraft(BaseModel):
    """测试用例草稿"""

    id: str = Field(default_factory=lambda: f"draft_{generate(size=10)}")
    source_document_id: str
    query: str
    age: int
    domain: str = ""
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

    id: str = Field(default_factory=lambda: f"set_{generate(size=10)}")
    name: str
    description: str = ""
    source_type: str = "manual"
    test_case_ids: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class TestCase(BaseModel):
    """测试用例模型"""

    id: str = Field(default_factory=lambda: f"tc_{generate(size=10)}")
    query: str  # 查询文本
    age: int  # 儿童年龄
    expected_knowledge_ids: List[str] = Field(
        default_factory=list
    )  # 预期的知识点ID列表
    expected_keywords: List[str] = Field(default_factory=list)  # 预期包含的关键词
    description: str = ""  # 测试用例描述
    
    # 新增字段（向后兼容）
    domain: str = Field(default="", description=f"领域，可选值：{TEST_CASE_DOMAINS}")
    answer_points: List[str] = Field(default_factory=list, description="答题要点")
    professional_terms: List[str] = Field(default_factory=list, description="专业术语")
    age_requirement: str = Field(default="", description="年龄要求")
    relevance_scores: Dict[str, float] = Field(default_factory=dict, description="相关性评分")
    source_document_id: str = Field(default="", description="来源文档ID")
    test_set_id: str = Field(default="", description="所属测试集ID")
    version: int = Field(default=1, description="版本号")
    
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class TestResultItem(BaseModel):
    """单个测试结果项"""

    knowledge_id: str
    content: str
    score: float
    expected: bool  # 是否是预期结果
    rank: int  # 排名（从1开始）


class TestResult(BaseModel):
    """测试结果模型"""

    test_case_id: str
    query: str
    age: int
    precision: float  # 准确率 = 检索到的相关结果数 / 检索到的总结果数
    recall: float  # 召回率 = 检索到的相关结果数 / 总相关结果数
    f1_score: float  # F1分数
    mrr: float  # 平均倒数排名
    ndcg_at_k: float = 0.0  # NDCG@K，归一化折损累计增益
    results: List[TestResultItem] = Field(default_factory=list)
    executed_at: datetime = Field(default_factory=datetime.now)
    execution_time_ms: int = 0  # 执行时间（毫秒）


class TestRun(BaseModel):
    """测试运行批次"""

    id: str = Field(
        default_factory=lambda: f"run_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    )
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
    status: str = "pending"  # pending, running, completed, failed
    created_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    snapshot_id: Optional[str] = None  # 关联的知识库快照ID
    config_version_id: Optional[str] = None  # 运行时的配置版本
    config_snapshot: Optional[Dict[str, Any]] = None  # 完整配置快照
    previous_config_version_id: Optional[str] = None  # 上一次运行的配置版本（用于对比）


class KnowledgeSnapshot(BaseModel):
    """知识库快照模型"""

    id: str = Field(
        default_factory=lambda: f"snap_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    )
    name: str
    description: str = ""
    document_count: int = 0
    document_hashes: List[str] = Field(default_factory=list)
    index_size_bytes: int = 0
    created_at: datetime = Field(default_factory=datetime.now)
    storage_path: str = ""  # 快照存储路径


class TestCaseStore(BaseModel):
    """测试用例存储"""

    test_cases: Dict[str, TestCase] = Field(default_factory=dict)


class SourceDocumentStore(BaseModel):
    """源文档存储"""

    documents: Dict[str, SourceDocument] = Field(default_factory=dict)


class TestCaseDraftStore(BaseModel):
    """测试用例草稿存储"""

    drafts: Dict[str, TestCaseDraft] = Field(default_factory=dict)


class TestSetStore(BaseModel):
    """测试集存储"""

    test_sets: Dict[str, TestSet] = Field(default_factory=dict)
