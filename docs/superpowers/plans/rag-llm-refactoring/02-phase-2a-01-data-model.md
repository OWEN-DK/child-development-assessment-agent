# Phase 2A.1: 数据模型扩展

> **前置文档:** [Overview](./02-phase-2a-00-overview.md)
> **状态:** ⏳ 完全待实现
> **预计工期:** 0.5人天

### 🔴 2.1 数据模型扩展（⏳ 完全待实现，0.5人天）
> 技术方案： Alembic 在线迁移，无停机部署，字段新增完全向后兼容

#### Task 2.1.1: TestRunResult新增指标字段
**Files:**
- Modify: `src/models/rag.py`
- Create: `alembic/versions/[timestamp]_add_rag_metrics_fields.py`
- Test: `tests/models/test_rag_models.py`

- [ ] **Step 1: 编写测试用例**
```python
def test_test_run_result_metrics_fields():
    from src.models.rag import TestRunResult
    from datetime import datetime, timezone

    result = TestRunResult(
        test_run_id=1,
        test_case_id=1,
        mrr=0.5,
        ndcg=0.75,
        precision=0.8,
        recall=0.6,
        hit_rate_1=1.0,
        hit_rate_3=0.8,
        hit_rate_5=0.6,
        retrieved_doc_ids=["doc1", "doc2"],
        relevant_doc_ids=["doc1"],
        created_at=datetime.now(timezone.utc)
    )

    assert result.mrr == 0.5
    assert result.ndcg == 0.75
    assert result.precision == 0.8
    assert result.recall == 0.6
    assert result.hit_rate_1 == 1.0
    assert result.hit_rate_3 == 0.8
    assert result.hit_rate_5 == 0.6
```

- [ ] **Step 2: 运行测试验证失败**
Run: `pytest tests/models/test_rag_models.py::test_test_run_result_metrics_fields -v`
Expected: FAIL - 字段不存在

- [ ] **Step 3: 实现模型扩展**
修改`src/models/rag.py`中的TestRunResult类：
```python
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, DECIMAL, JSON
from sqlalchemy.orm import relationship
from src.models.base import Base
from datetime import datetime, timezone
import enum

class TestRunStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class ReportExportFormat(str, enum.Enum):
    MARKDOWN = "markdown"
    PDF = "pdf"
    JSON = "json"

class TestRunResult(Base):
    __tablename__ = "test_run_results"
    
    id = Column(Integer, primary_key=True, index=True)
    test_run_id = Column(Integer, ForeignKey("test_runs.id"), nullable=False)
    test_case_id = Column(Integer, ForeignKey("test_cases.id"), nullable=False)
    
    mrr = Column(DECIMAL(10, 4), nullable=False, default=0.0)
    ndcg = Column(DECIMAL(10, 4), nullable=True, default=None)
    precision = Column(DECIMAL(10, 4), nullable=True, default=None)
    recall = Column(DECIMAL(10, 4), nullable=True, default=None)
    hit_rate_1 = Column(DECIMAL(10, 4), nullable=False, default=0.0)
    hit_rate_3 = Column(DECIMAL(10, 4), nullable=False, default=0.0)
    hit_rate_5 = Column(DECIMAL(10, 4), nullable=False, default=0.0)
    
    retrieved_doc_ids = Column(JSON, nullable=False, default=list)
    relevant_doc_ids = Column(JSON, nullable=False, default=list)
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    
    test_run = relationship("TestRun", back_populates="results")
    test_case = relationship("TestCase", back_populates="run_results")
```

- [ ] **Step 4: 生成并执行Alembic迁移**
Run: `alembic revision --autogenerate -m "add metrics fields to test_run_results"`
Run: `alembic upgrade head`
Expected: Migration executed successfully

- [ ] **Step 5: 运行测试验证通过**
Run: `pytest tests/models/test_rag_models.py::test_test_run_result_metrics_fields -v`
Expected: PASS

---

#### Task 2.1.2: TestRun新增状态字段
**Files:**
- Modify: `src/models/rag.py`
- Create: `alembic/versions/[timestamp]_add_test_run_status_field.py`
- Test: `tests/models/test_rag_models.py`

- [ ] **Step 1: 编写测试用例**
```python
def test_test_run_status_field():
    from src.models.rag import TestRun, TestRunStatus, ReportExportFormat
    
    test_run = TestRun(
        test_set_ids=[1, 2],
        status=TestRunStatus.COMPLETED,
        report_export_format=ReportExportFormat.MARKDOWN,
        report_storage_path="/reports/run_1.md",
        created_at=datetime.now(timezone.utc)
    )
    
    assert test_run.status == TestRunStatus.COMPLETED
    assert test_run.report_export_format == ReportExportFormat.MARKDOWN
```

- [ ] **Step 2: 运行测试验证失败**
Run: `pytest tests/models/test_rag_models.py::test_test_run_status_field -v`
Expected: FAIL - 字段不存在

- [ ] **Step 3: 实现模型扩展**
修改`src/models/rag.py`中的TestRun类：
```python
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, DECIMAL, JSON, Enum as SAEnum
from sqlalchemy.orm import relationship
from src.models.base import Base
from datetime import datetime, timezone

class TestRun(Base):
    __tablename__ = "test_runs"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=True)
    description = Column(String, nullable=True)
    test_set_ids = Column(JSON, nullable=False, default=list)
    custom_case_ids = Column(JSON, nullable=True, default=list)
    
    status = Column(SAEnum(TestRunStatus), nullable=False, default=TestRunStatus.PENDING)
    report_export_format = Column(SAEnum(ReportExportFormat), nullable=True, default=ReportExportFormat.MARKDOWN)
    report_storage_path = Column(String, nullable=True)
    
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(String, nullable=True)
    created_by = Column(Integer, nullable=True, comment="创建人用户ID，弱关联无需外键")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    
    results = relationship("TestRunResult", back_populates="test_run", cascade="all, delete-orphan")

> 注意：需要同步修改`src/models/rag.py`中的SourceDocument模型，新增反向关联：
> ```python
> drafts = relationship("TestCaseDraft", back_populates="source_document", cascade="all, delete-orphan")
> ```
```

- [ ] **Step 4: 生成并执行Alembic迁移**
Run: `alembic revision --autogenerate -m "add status field to test_runs"`
Run: `alembic upgrade head`
Expected: Migration executed successfully

- [ ] **Step 5: 运行测试验证通过**
Run: `pytest tests/models/test_rag_models.py::test_test_run_status_field -v`
Expected: PASS

---

#### Task 2.1.4: TestCaseDraft新增批次标识字段
**Files:**
- Modify: `src/models/rag.py`
- Create: `alembic/versions/[timestamp]_add_generation_batch_id_to_drafts.py`
- Test: `tests/models/test_rag_models.py`

- [ ] **Step 1: 编写测试用例**
```python
def test_test_case_draft_batch_id_field():
    from src.models.rag import TestCaseDraft
    from datetime import datetime, timezone
    
    draft = TestCaseDraft(
        source_document_id=1,
        query="1岁宝宝走路正常吗",
        domain="粗大动作",
        age_min=1.0,
        age_max=1.5,
        generation_batch_id="doc_1_a1b2c3d4_20240101_1200",
        status="draft",
        created_at=datetime.now(timezone.utc)
    )
    
    assert draft.generation_batch_id == "doc_1_a1b2c3d4_20240101_1200"
```

- [ ] **Step 2: 实现模型扩展**
修改`src/models/rag.py`中的TestCaseDraft类：
```python
class TestCaseDraft(Base):
    __tablename__ = "test_case_drafts"
    
    id = Column(Integer, primary_key=True, index=True)
    source_document_id = Column(Integer, ForeignKey("source_documents.id"), nullable=False)
    query = Column(String, nullable=False)
    domain = Column(String, nullable=False)
    age_min = Column(DECIMAL(5, 2), nullable=True)
    age_max = Column(DECIMAL(5, 2), nullable=True)
    
    generation_batch_id = Column(String(64), nullable=True, index=True)
    
    expected_keywords = Column(JSON, nullable=True, default=list)
    description = Column(String, nullable=True)
    status = Column(String, nullable=False, default="draft")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    
    source_document = relationship("SourceDocument", back_populates="drafts")
```

- [ ] **Step 3: 生成并执行Alembic迁移**
Run: `alembic revision --autogenerate -m "add generation_batch_id to test_case_drafts"`
Run: `alembic upgrade head`
Expected: Migration executed successfully

---

#### Task 2.1.5: 补充Repository查询方法
**Files:**
- Modify: `src/repository/test_run_result_repository.py`
- Modify: `src/repository/test_case_draft_repository.py`

- [ ] **Step 1: 实现 list_by_test_run_id 方法**
```python
# src/repository/test_run_result_repository.py
from typing import List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.rag import TestRunResult

class TestRunResultRepository:
    async def list_by_test_run_id(self, session: AsyncSession, test_run_id: int) -> List[TestRunResult]:
        """根据测试运行ID获取所有结果"""
        result = await session.execute(
            select(TestRunResult).where(TestRunResult.test_run_id == test_run_id)
        )
        return list(result.scalars().all())
```

- [ ] **Step 2: 实现 list_by_batch 方法**
```python
# src/repository/test_case_draft_repository.py
from typing import List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.rag import TestCaseDraft

class TestCaseDraftRepository:
    async def list_by_batch(self, session: AsyncSession, document_id: int, generation_batch_id: str) -> List[TestCaseDraft]:
        """根据文档ID和批次ID查询草稿"""
        result = await session.execute(
            select(TestCaseDraft).where(
                TestCaseDraft.source_document_id == document_id,
                TestCaseDraft.generation_batch_id == generation_batch_id
            )
        )
        return list(result.scalars().all())
```

> **完整使用示例**:
> ```python
> async with async_session() as session:
>     results = await test_run_result_repo.list_by_test_run_id(session, run_id=1)
>     drafts = await test_case_draft_repo.list_by_batch(session, document_id=1, generation_batch_id="batch_123")
> ```

---

#### Task 2.1.3: 新增测试用例生成配置模块
**Files:**
- Create: `src/config/modules/rag/testing.py`
- Modify: `src/config/__init__.py` (导出配置)
- Test: `tests/config/test_rag_test_case_config.py`

- [ ] **Step 1: 编写测试用例**
```python
def test_test_case_generation_config():
    from src.config.modules.rag.testing import TestCaseGenerationConfig

    # 验证 Pydantic 模型默认值正确
    config = TestCaseGenerationConfig()
    assert config.test_case_draft_default_count == 100
    assert config.test_case_draft_max_count == 200
    assert config.test_case_draft_min_count == 20
    assert config.test_case_draft_concurrency == 20
    assert config.test_case_draft_batch_size == 10
    assert config.test_case_draft_deduplication_threshold == 0.8

def test_test_case_generation_config_from_config_manager():
    """验证通过 ConfigManager 加载配置"""
    from src.config import ConfigManager
    from src.config.modules.rag.testing import TestCaseGenerationConfig

    config_manager = ConfigManager()
    full_config = config_manager.get_full_config()
    testing_data = full_config.get("rag_testing", {})
    config = TestCaseGenerationConfig(**testing_data) if testing_data else TestCaseGenerationConfig()
    assert config.test_case_draft_default_count >= config.test_case_draft_min_count
```

- [ ] **Step 2: 运行测试验证失败**
Run: `pytest tests/config/test_rag_test_case_config.py -v`
Expected: FAIL - 配置模块不存在

- [ ] **Step 3: 实现配置模块**
创建`src/config/modules/rag/testing.py`:
```python
from pydantic import BaseModel, Field
from typing import List

class TestCaseGenerationConfig(BaseModel):
    """测试用例草稿生成配置（通过 ConfigManager 从 MySQL 读取，.env 兜底，支持热更新）"""
    # 数量控制
    test_case_draft_default_count: int = Field(default=100, ge=1, description="单篇文档默认生成草稿数量")
    test_case_draft_max_count: int = Field(default=200, ge=1, description="单篇文档最大生成草稿数量")
    test_case_draft_min_count: int = Field(default=20, ge=1, description="单篇文档最小生成草稿数量")

    # 性能控制
    test_case_draft_concurrency: int = Field(default=20, ge=1, description="草稿生成并发数")
    test_case_draft_batch_size: int = Field(default=10, ge=5, le=15, description="单次LLM调用生成草稿数量（10-15条）")

    # 质量控制
    test_case_draft_deduplication_threshold: float = Field(default=0.8, ge=0.0, le=1.0, description="草稿去重相似度阈值")
    test_case_draft_relevance_threshold: float = Field(default=0.6, ge=0.0, le=1.0, description="草稿相关性阈值，低于此值自动丢弃")

    # 多维度差异化覆盖配置
    supported_domains: List[str] = Field(
        default_factory=lambda: ["粗大动作", "精细动作", "语言发展", "认知能力", "社交情感", "感觉统合"],
        description="支持的发展领域列表"
    )
    age_stages: List[dict] = Field(
        default_factory=lambda: [
            {"name": "0-1岁", "age_min": 0, "age_max": 1, "min_count": 10},
            {"name": "1-3岁", "age_min": 1, "age_max": 3, "min_count": 10},
            {"name": "3-6岁", "age_min": 3, "age_max": 6, "min_count": 10},
            {"name": "6-12岁", "age_min": 6, "age_max": 12, "min_count": 10},
        ],
        description="年龄段划分及最小生成数量"
    )
    query_types: List[dict] = Field(
        default_factory=lambda: [
            {"name": "事实性查询", "description": "是什么/有什么", "min_count": 15},
            {"name": "比较性查询", "description": "区别/对比", "min_count": 15},
            {"name": "方案性查询", "description": "怎么做/如何", "min_count": 15},
            {"name": "原因分析性查询", "description": "为什么/原因", "min_count": 15},
        ],
        description="查询类型及最小生成数量"
    )
    difficulty_levels: List[dict] = Field(
        default_factory=lambda: [
            {"name": "入门级", "description": "基础概念", "min_count": 20},
            {"name": "中级", "description": "应用场景", "min_count": 20},
            {"name": "高级", "description": "复杂问题", "min_count": 20},
        ],
        description="难度级别及最小生成数量"
    )

    # 功能开关
    enable_breakpoint_resume: bool = Field(default=True, description="是否启用断点续传")
    enable_quality_check: bool = Field(default=True, description="是否启用质量校验")
    enable_relevance_check: bool = Field(default=True, description="是否启用相关性校验")


def calculate_draft_count_by_pages(page_count: int, config: TestCaseGenerationConfig) -> int:
    """根据文档页数动态计算草稿生成数量"""
    if page_count < 50:
        return max(config.test_case_draft_min_count, config.test_case_draft_default_count // 5)
    elif page_count <= 200:
        return config.test_case_draft_default_count
    else:
        return min(config.test_case_draft_max_count, config.test_case_draft_default_count * 2)
```

> **⚠️ 配置加载路径**: 业务代码中通过 `ConfigManager.get_full_config()` 获取 `rag_testing` 键，再用 `TestCaseGenerationConfig.model_validate()` 实例化。不通过 `settings.rag.testing` 访问。

- [ ] **Step 4: 运行测试验证通过**
Run: `pytest tests/config/test_rag_test_case_config.py -v`
Expected: PASS

---

**上一阶段：** [Overview](./02-phase-2a-00-overview.md)  
**下一阶段：** [执行路径统一](./02-phase-2a-02-execution-path.md)
