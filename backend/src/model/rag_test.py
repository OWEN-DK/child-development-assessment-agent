from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime


class TestCase(BaseModel):
    """测试用例模型"""

    id: str = Field(default_factory=lambda: datetime.now().strftime("%Y%m%d%H%M%S%f"))
    query: str  # 查询文本
    age: int  # 儿童年龄
    expected_knowledge_ids: List[str] = Field(
        default_factory=list
    )  # 预期的知识点ID列表
    expected_keywords: List[str] = Field(default_factory=list)  # 预期包含的关键词
    description: str = ""  # 测试用例描述
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
