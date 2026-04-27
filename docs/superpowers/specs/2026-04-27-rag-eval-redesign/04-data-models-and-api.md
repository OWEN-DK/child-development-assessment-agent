# 04 - 数据模型与 API 契约

## 需求

定义统一的 Pydantic Schema、ORM 模型映射和 RESTful API 契约，消除当前 Schema 分散、deprecated 字段和类型不一致问题。

## 当前问题

1. Schema 分散在 `schemas/test_case.py`(404行)、`schemas/rag_eval.py`(156行)、`schemas/tuning.py`(66行) 等
2. `GenerationParams` 含 deprecated 字段，违反零迁移原则
3. `TestResultItem` 形状与 `test_executor.py` 实际产出不匹配
4. Controller 中有 4 个手动序列化器（`create_serializer`）
5. API 路由前缀不统一（`/rag/test/` vs `/api/v1/`）

## Schema 文件组织

```
backend/src/schemas/rag_eval/
├── __init__.py              # 统一导出
├── source_document.py       # SourceDocumentCreate/Read
├── draft.py                 # DraftCreate/Read/Update/Review
├── test_case.py             # TestCaseCreate/Read/Update
├── test_set.py              # TestSetCreate/Read/Update
├── test_run.py              # TestRunCreate/Read/Result
├── metrics.py               # 三层指标 Schema
├── report.py                # ReportRead/TrendData/Export
├── snapshot.py              # SnapshotCreate/Read
└── tuning.py                # TuningSuggestion/ImpactAnalysis
```

## 核心数据模型

### SourceDocument（源文档）

```python
class SourceDocumentCreate(BaseModel):
    filename: str
    content_type: str

class SourceDocumentRead(BaseModel):
    id: str
    filename: str
    content_type: str
    file_size: int
    page_count: int | None = None
    status: Literal['pending', 'processing', 'completed', 'failed']
    error_message: str | None = None
    created_at: datetime
    
class SourceDocumentList(BaseModel):
    items: List[SourceDocumentRead]
    total: int
```

### Draft（草稿）

```python
class DraftCreate(BaseModel):
    source_doc_id: str
    question: str
    expected_answer: str
    expected_doc_ids: List[str] = []
    domain: TestDomain
    age_stage: AgeStage
    difficulty: DifficultyLevel = 'medium'
    metadata: Dict[str, Any] = {}

class DraftRead(BaseModel):
    id: str
    source_doc_id: str
    question: str
    expected_answer: str
    expected_doc_ids: List[str]
    domain: TestDomain
    age_stage: AgeStage
    difficulty: DifficultyLevel
    faithfulness_score: float | None = None
    status: Literal['pending', 'approved', 'rejected', 'imported']
    metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

class DraftUpdate(BaseModel):
    question: str | None = None
    expected_answer: str | None = None
    expected_doc_ids: List[str] | None = None
    domain: TestDomain | None = None
    age_stage: AgeStage | None = None
    difficulty: DifficultyLevel | None = None

class DraftReview(BaseModel):
    action: Literal['approve', 'reject']
    reason: str | None = None

class DraftList(BaseModel):
    items: List[DraftRead]
    total: int
    page: int
    page_size: int
```

### TestCase（测试用例）

```python
class TestCaseCreate(BaseModel):
    question: str
    expected_answer: str
    expected_doc_ids: List[str] = []
    domain: TestDomain
    age_stage: AgeStage
    difficulty: DifficultyLevel = 'medium'
    metadata: Dict[str, Any] = {}

class TestCaseRead(BaseModel):
    id: str
    question: str
    expected_answer: str
    expected_doc_ids: List[str]
    domain: TestDomain
    age_stage: AgeStage
    difficulty: DifficultyLevel
    source: Literal['manual', 'draft', 'import']
    source_draft_id: str | None = None
    metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

class TestCaseList(BaseModel):
    items: List[TestCaseRead]
    total: int
    page: int
    page_size: int
```

### TestSet（测试集）

```python
class TestSetCreate(BaseModel):
    name: str
    description: str = ''
    case_ids: List[str] = []

class TestSetRead(BaseModel):
    id: str
    name: str
    description: str
    case_count: int
    case_ids: List[str]
    created_at: datetime
    updated_at: datetime

class TestSetUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
```

### TestRun（测试运行）

```python
class TestRunCreate(BaseModel):
    test_set_id: str
    snapshot_id: str | None = None  # None = 自动创建
    config: RunConfig | None = None

class RunConfig(BaseModel):
    concurrency: int = 3
    timeout_ms: int = 30000
    metrics_config: Dict[str, Any] = {}

class TestRunRead(BaseModel):
    id: str
    test_set_id: str
    snapshot_id: str
    config_version: str
    status: Literal['pending', 'running', 'completed', 'failed', 'cancelled']
    total_cases: int
    completed_cases: int
    progress: float
    metrics: RunMetrics | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime

class TestRunResultItem(BaseModel):
    case_id: str
    question: str
    expected_answer: str
    actual_answer: str
    retrieved_doc_ids: List[str]
    expected_doc_ids: List[str]
    retrieval_scores: Dict[str, float]
    execution_time_ms: int
    layer1_metrics: Dict[str, float]
    layer2_metrics: Dict[str, float]
    error: str | None = None
```

### Metrics（三层指标）

```python
class MetricScore(BaseModel):
    value: float              # 0-1 归一化
    passed: bool
    threshold: float
    details: Dict[str, Any] = {}

class Layer1Metrics(BaseModel):
    context_precision: MetricScore
    context_recall: MetricScore
    noise_sensitivity: MetricScore
    mrr: MetricScore
    ndcg: MetricScore

class Layer2Metrics(BaseModel):
    faithfulness: MetricScore
    answer_relevancy: MetricScore
    groundedness: MetricScore

class Layer3Metrics(BaseModel):
    rule_compliance: MetricScore
    regression_score: MetricScore
    cost_efficiency: MetricScore
    config_stability: MetricScore

class RunMetrics(BaseModel):
    l1: Layer1Metrics
    l2: Layer2Metrics
    l3: Layer3Metrics
    overall_score: float
    calculated_at: datetime
```

### Snapshot（快照）

```python
class SnapshotCreate(BaseModel):
    name: str | None = None
    description: str = ''

class SnapshotRead(BaseModel):
    id: str
    name: str
    description: str
    document_count: int
    chunk_count: int
    config_version: str
    created_at: datetime
```

### Report（报告）

```python
class ReportRead(BaseModel):
    id: str
    run_id: str
    metrics: RunMetrics
    bad_cases: List[TestRunResultItem]
    suggestions: List[TuningSuggestion]
    trend_data: TrendData | None = None
    created_at: datetime

class TrendData(BaseModel):
    run_ids: List[str]
    timestamps: List[datetime]
    overall_scores: List[float]
    metric_trends: Dict[str, List[float]]
```

### Tuning（调优）

```python
class TuningSuggestion(BaseModel):
    id: str
    run_id: str
    category: Literal['retrieval', 'generation', 'configuration', 'cost']
    severity: Literal['critical', 'warning', 'info']
    title: str
    description: str
    current_value: Any
    suggested_value: Any
    expected_impact: str
    status: Literal['pending', 'adopted', 'rejected', 'ignored']
    created_at: datetime

class TuningAdopt(BaseModel):
    suggestion_id: str

class TuningReject(BaseModel):
    suggestion_id: str
    reason: str | None = None
```

## API 路由设计

路由前缀: `/rag/eval/`

### 草稿管理

| 端点 | 方法 | 功能 | 请求体 | 响应 |
|---|---|---|---|---|
| `/rag/eval/source-documents/upload` | POST | 上传源文档+自动生成草稿 | multipart/form-data | `APIResponse[SourceDocumentRead]` |
| `/rag/eval/source-documents` | GET | 列出源文档 | - | `APIResponse[List[SourceDocumentRead]]` |
| `/rag/eval/source-documents/{id}` | GET | 获取源文档详情 | - | `APIResponse[SourceDocumentRead]` |
| `/rag/eval/source-documents/{id}` | DELETE | 删除源文档 | - | `APIResponse[None]` |
| `/rag/eval/drafts` | GET | 列出草稿(分页+过滤) | Query: page, page_size, status, domain | `APIResponse[DraftList]` |
| `/rag/eval/drafts/{id}` | GET | 获取草稿详情 | - | `APIResponse[DraftRead]` |
| `/rag/eval/drafts/{id}` | PUT | 更新草稿 | `DraftUpdate` | `APIResponse[DraftRead]` |
| `/rag/eval/drafts/{id}/review` | POST | 审核草稿→生成测试用例 | `DraftReview` | `APIResponse[TestCaseRead]` |
| `/rag/eval/drafts/batch-import` | POST | 批量导入已审核草稿 | `{draft_ids: List[str]}` | `APIResponse[List[TestCaseRead]]` |
| `/rag/eval/drafts/batch` | DELETE | 批量删除草稿 | `{draft_ids: List[str]}` | `APIResponse[None]` |
| `/rag/eval/drafts/generation/{task_id}/stream` | GET | SSE草稿生成进度 | - | SSE EventStream |

### 测试用例与测试集

| 端点 | 方法 | 功能 | 请求体 | 响应 |
|---|---|---|---|---|
| `/rag/eval/test-cases` | GET | 列出测试用例 | Query: page, page_size, domain | `APIResponse[TestCaseList]` |
| `/rag/eval/test-cases` | POST | 创建测试用例 | `TestCaseCreate` | `APIResponse[TestCaseRead]` |
| `/rag/eval/test-cases/{id}` | GET | 获取测试用例 | - | `APIResponse[TestCaseRead]` |
| `/rag/eval/test-cases/{id}` | PUT | 更新测试用例 | `TestCaseCreate` | `APIResponse[TestCaseRead]` |
| `/rag/eval/test-cases/{id}` | DELETE | 删除测试用例 | - | `APIResponse[None]` |
| `/rag/eval/test-cases/batch` | DELETE | 批量删除 | `{case_ids: List[str]}` | `APIResponse[None]` |
| `/rag/eval/test-cases/import` | POST | 导入JSON测试用例 | `{cases: List[TestCaseCreate]}` | `APIResponse[TestCaseList]` |
| `/rag/eval/test-sets` | GET | 列出测试集 | - | `APIResponse[List[TestSetRead]]` |
| `/rag/eval/test-sets` | POST | 创建测试集 | `TestSetCreate` | `APIResponse[TestSetRead]` |
| `/rag/eval/test-sets/{id}` | GET | 获取测试集详情 | - | `APIResponse[TestSetRead]` |
| `/rag/eval/test-sets/{id}` | PUT | 更新测试集 | `TestSetUpdate` | `APIResponse[TestSetRead]` |
| `/rag/eval/test-sets/{id}` | DELETE | 删除测试集 | - | `APIResponse[None]` |
| `/rag/eval/test-sets/{id}/cases` | POST | 添加测试用例 | `{case_ids: List[str]}` | `APIResponse[TestSetRead]` |
| `/rag/eval/test-sets/{id}/cases` | DELETE | 移除测试用例 | `{case_ids: List[str]}` | `APIResponse[TestSetRead]` |
| `/rag/eval/test-sets/{id}/export` | GET | 导出测试集JSON | - | `APIResponse[Dict]` |

### 测试运行

| 端点 | 方法 | 功能 | 请求体 | 响应 |
|---|---|---|---|---|
| `/rag/eval/runs` | POST | 创建并执行测试运行 | `TestRunCreate` | `APIResponse[TestRunRead]` |
| `/rag/eval/runs/{id}/execute/{case_id}` | POST | 执行单个用例 | - | `APIResponse[TestRunResultItem]` |
| `/rag/eval/runs` | GET | 列出测试运行 | Query: status, test_set_id | `APIResponse[List[TestRunRead]]` |
| `/rag/eval/runs/{id}` | GET | 获取测试运行详情 | - | `APIResponse[TestRunRead]` |
| `/rag/eval/runs/{id}` | DELETE | 删除测试运行 | - | `APIResponse[None]` |
| `/rag/eval/runs/batch` | DELETE | 批量删除 | `{run_ids: List[str]}` | `APIResponse[None]` |
| `/rag/eval/runs/{id}/stream` | GET | SSE执行进度 | - | SSE EventStream |
| `/rag/eval/runs/compare` | GET | 比较两个运行 | Query: run_id_1, run_id_2 | `APIResponse[RunComparison]` |

### 指标与报告

| 端点 | 方法 | 功能 | 请求体 | 响应 |
|---|---|---|---|---|
| `/rag/eval/runs/{id}/metrics` | GET | 获取三层指标 | - | `APIResponse[RunMetrics]` |
| `/rag/eval/reports` | GET | 列出报告 | Query: page, page_size | `APIResponse[List[ReportRead]]` |
| `/rag/eval/reports/{id}` | GET | 获取报告详情 | - | `APIResponse[ReportRead]` |
| `/rag/eval/reports/{id}/export` | GET | 导出报告 | Query: format=pdf\|csv\|json | FileResponse |
| `/rag/eval/trends` | GET | 获取趋势数据 | Query: metric, limit | `APIResponse[TrendData]` |

### 快照

| 端点 | 方法 | 功能 | 请求体 | 响应 |
|---|---|---|---|---|
| `/rag/eval/snapshots` | POST | 创建快照 | `SnapshotCreate` | `APIResponse[SnapshotRead]` |
| `/rag/eval/snapshots` | GET | 列出快照 | - | `APIResponse[List[SnapshotRead]]` |
| `/rag/eval/snapshots/{id}` | GET | 获取快照 | - | `APIResponse[SnapshotRead]` |
| `/rag/eval/snapshots/{id}/restore` | POST | 恢复快照 | - | `APIResponse[None]` |

### 调优建议

| 端点 | 方法 | 功能 | 请求体 | 响应 |
|---|---|---|---|---|
| `/rag/eval/runs/{id}/tuning` | GET | 获取调优建议 | - | `APIResponse[List[TuningSuggestion]]` |
| `/rag/eval/tuning/{id}/adopt` | POST | 采纳建议 | - | `APIResponse[None]` |
| `/rag/eval/tuning/{id}/reject` | POST | 拒绝建议 | `TuningReject` | `APIResponse[None]` |

### 配置对比

| 端点 | 方法 | 功能 | 请求体 | 响应 |
|---|---|---|---|---|
| `/rag/eval/config-compare/{v1}/{v2}` | GET | 对比配置版本 | - | `APIResponse[ConfigComparison]` |

## 统一响应格式

遵循 `.ai/unified-api-response-and-error-handling.md`：

```python
# 成功
APIResponse.success(data=TestRunRead(...))
# => {"code": 0, "message": "success", "data": {...}}

# 错误
raise AppException(error_code="DRAFT_NOT_FOUND", message="草稿不存在", status_code=404)
# => {"code": 404, "message": "草稿不存在", "error_code": "DRAFT_NOT_FOUND", "details": null}
```

## 错误码定义

| 错误码 | HTTP状态码 | 含义 |
|---|---|---|
| `DRAFT_NOT_FOUND` | 404 | 草稿不存在 |
| `TEST_CASE_NOT_FOUND` | 404 | 测试用例不存在 |
| `TEST_SET_NOT_FOUND` | 404 | 测试集不存在 |
| `TEST_RUN_NOT_FOUND` | 404 | 测试运行不存在 |
| `SNAPSHOT_NOT_FOUND` | 404 | 快照不存在 |
| `REPORT_NOT_FOUND` | 404 | 报告不存在 |
| `SNAPSHOT_RESTORE_FAILED` | 500 | 快照恢复失败 |
| `DRAFT_GENERATION_FAILED` | 500 | 草稿生成失败 |
| `TEST_EXECUTION_TIMEOUT` | 408 | 测试执行超时 |
| `TEST_EXECUTION_FAILED` | 500 | 测试执行失败 |
| `METRIC_CALCULATION_FAILED` | 500 | 指标计算失败 |
| `INVALID_TEST_CASE_FORMAT` | 400 | 测试用例格式错误 |
| `INVALID_IMPORT_DATA` | 400 | 导入数据格式错误 |
| `CONFIG_COMPARE_SAME_VERSION` | 400 | 不能对比相同版本 |

## 验收标准

1. 所有 Schema 在 `schemas/rag_eval/` 目录下，按实体分文件
2. 零 deprecated 字段
3. 所有 API 返回统一 `APIResponse` 格式
4. 所有业务异常使用 `AppException`，错误码定义完整
5. ORM-to-Pydantic 转换通过 `OrmMapper` 统一处理，零手动序列化器
6. 路由前缀统一为 `/rag/eval/`
