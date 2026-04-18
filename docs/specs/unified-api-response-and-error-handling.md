# 统一接口返回与统一异常处理需求文档

## 1. 背景与目标

### 1.1 现状问题

当前系统存在以下问题：

**后端接口返回格式不统一**
- 部分接口直接返回字典：`{"status": "ok"}`、`{"tasks": [...]}`、`{"documents": [...]}`
- 部分接口使用 Pydantic `response_model` 返回结构化对象
- 部分接口返回 `StreamingResponse` 或 `FileResponse`
- 成功响应没有统一包装，前端难以统一处理

**异常处理混乱**
- 大量使用 `HTTPException(status_code, detail)` 直接抛出
- 错误信息格式不一致：英文 `"Test case not found"` 与中文 `"文档不存在"` 混用
- 没有全局异常处理器，每个 Controller 自行处理异常
- 前端仅通过 `error.response?.data?.detail` 获取错误信息，缺乏结构化错误码

**前端错误处理薄弱**
- `client.ts` 中拦截器仅打印日志，未做统一错误提示
- 各业务模块自行处理错误，缺乏统一的错误码映射
- 没有用户友好的错误提示机制

### 1.2 改造目标

1. **后端统一响应格式**：所有正常接口返回统一包装结构
2. **后端统一异常处理**：全局异常拦截，标准化错误响应
3. **前端统一请求/响应拦截**：自动处理错误码，统一提示
4. **前后端错误码对齐**：建立统一的错误码字典
5. **实体类集中管理**：所有 Pydantic 实体类从 Service/Controller 抽离至统一目录
6. **类职责拆分**：所有类遵循单一职责，单类不超过 200 行
7. **冗余代码消除**：提取公共工具方法，消除 280+ 处重复代码

---

## 2. 实体类目录规范（强制）

### 2.1 现状问题

当前项目中 Pydantic 实体类（`BaseModel`）散落在多个位置：

| 当前位置 | 包含内容 | 问题 |
|---------|---------|------|
| `src/controller/*.py` | 大量 Request/Response DTO（约 40+ 个） | Controller 应只负责路由，不应承载数据模型 |
| `src/service/*.py` | 业务实体如 `Conflict`、`ValidationResult`、`ImpactAnalysisResult` | Service 层混入数据定义，违反单一职责 |
| `src/model/` | 部分业务模型 | 与 `src/models/` 职责不清 |
| `src/models/` | ORM 模型 + 部分业务模型 | ORM 与 Pydantic 混放 |
| `src/core/` | 配置模型如 `AgeFilterConfig` | 核心模块不应包含业务实体 |

### 2.2 目标目录结构

**绝对禁止**在 `service/`、`controller/`、`core/` 中定义 `class xxx(BaseModel)`。

所有 Pydantic 实体类必须统一放置在 `backend/src/schemas/` 目录下，**按业务模块组织**（而非按 request/response 分层）：

```
backend/src/schemas/
├── __init__.py              # 统一导出入口
├── common.py                # 通用模型（APIResponse、分页、基础异常等）
├── assessment.py            # 评估模块所有模型（UserInput, AgentState, FinalReport 等）
├── rag.py                   # RAG 模块所有模型（DocumentUploadResponse, SearchResult 等）
├── test_case.py             # 测试模块所有模型（CreateTestCaseRequest, TestCaseResponse 等）
├── config.py                # 配置模块所有模型（LLMProviderConfig, ConfigValidationResult 等）
├── prompt.py                # 提示词模块所有模型（PromptVersionResponse, ImpactAnalysisResult 等）
├── monitoring.py            # 监控模块所有模型（TraceResponse, MetricData 等）
└── events.py                # SSE 事件模型（RunStartedEvent, ProgressEvent 等）
```

### 2.3 分类规则

| 类型 | 命名规范 | 示例 | 说明 |
|------|---------|------|------|
| **请求 DTO** | `{Entity}{Action}Request` | `CreateTestCaseRequest` | 接口入参 |
| **响应 DTO** | `{Entity}Response` | `TestCaseResponse` | 接口出参 |
| **领域模型** | 业务实体名 | `ChildState`, `EvaluationResult` | 业务逻辑流转的实体 |
| **配置模型** | `{Module}Config` | `LLMProviderConfig` | 系统配置结构 |
| **事件模型** | `{EventName}Event` | `RunStartedEvent` | SSE 推送事件 |

### 2.4 迁移清单

需要从各模块抽离的实体类：

**从 `src/controller/` 迁移**：
- `rag_test_controller.py` → `schemas/request/test_case.py` + `schemas/response/test_case.py`
- `config_management_controller.py` → `schemas/request/config.py` + `schemas/response/config.py`
- `prompt_management_controller.py` → `schemas/request/prompt.py` + `schemas/response/prompt.py`
- `tuning_controller.py` → `schemas/request/config.py` + `schemas/response/tuning.py`
- `config_controller.py` → `schemas/request/config.py` + `schemas/response/config.py`
- `rollback_controller.py` → `schemas/request/config.py`
- `health_controller.py` → `schemas/response/common.py`
- `config_health_controller.py` → `schemas/response/config.py`

**从 `src/service/` 迁移**：
- `config_conflict_detector.py` → `schemas/config.py`
- `config_validation_engine.py` → `schemas/config.py`
- `prompt_impact_analyzer.py` → `schemas/prompt.py`
- `retrieval_service.py` → `schemas/rag.py`

**从 `src/core/` 迁移**：
- `age_filter.py` → `schemas/config.py`

**从 `src/model/` 整理**：
- `schemas.py` → `schemas/assessment.py`（Agent 工作流模型）
- `tuning.py` → `schemas/test_case.py`
- `document.py` → `schemas/rag.py`
- `rag_test.py` → `schemas/test_case.py`

**从 `src/models/` 整理**：
- `sse_events.py` → `schemas/events.py`
- `test_case.py` 中的 Pydantic 模型 → `schemas/test_case.py`

### 2.5 导入规范

迁移后，所有实体类通过统一入口导入：

```python
# 推荐：从 schemas 按模块导入
from src.schemas import CreateTestCaseRequest, TestCaseResponse
from src.schemas.assessment import ChildState, FinalReport
from src.schemas.config import LLMProviderConfig, ConfigValidationResult

# 禁止：从 controller 或 service 导入
# from src.controller.rag_test_controller import CreateTestCaseRequest  ❌
# from src.service.config_validation_engine import ValidationResult     ❌
```

---

## 3. 类职责拆分规范（强制）

### 3.1 现状问题

当前项目中存在大量**超长类**，违反单一职责原则（SRP），导致代码难以维护、测试和扩展：

| 类名 | 文件 | 行数 | 问题 |
|------|------|------|------|
| `RagTestManager` | `service/rag_test_manager.py` | 1799 | 混合了测试运行、用例 CRUD、测试集管理、草稿管理、快照管理、指标计算、文档管理等 7+ 职责 |
| `RetrievalService` | `service/retrieval_service.py` | 1060 | 混合了检索编排、检索器初始化、查询重写、同义词扩展、结果处理、缓存管理等职责 |
| `MetadataProcessor` | `core/metadata_processor.py` | 925 | 混合了元数据提取、章节分块、页面分块、父子分块、分块器工厂等职责 |
| `DocumentIngestionService` | `service/document_ingestion_service.py` | 637 | 混合了导入编排、任务状态、文档解析、流水线执行、去重等职责 |
| `IndexManagerService` | `service/index_manager_service.py` | 574 | 混合了索引生命周期、持久化、操作、查询等职责 |
| `CacheService` | `service/cache_service.py` | 447 | 混合了三级缓存管理、缓存键生成、统计等职责 |
| `PromptManager` | `core/prompt/manager.py` | 428 | 混合了版本管理、A/B 测试、缓存失效、影响分析等职责 |
| `TuningController` | `controller/tuning_controller.py` | 377 | Controller 过厚，应只负责路由和参数校验 |

**超过 200 行的类共 40+ 个**，需要系统性拆分。

### 3.2 拆分原则

| 原则 | 说明 | 示例 |
|------|------|------|
| **单一职责** | 每个类只负责一个明确的业务职责 | 检索编排 vs 查询重写 vs 结果处理分离 |
| **行数限制** | 单类不超过 **200 行**（含空行和注释） | 超过则必须拆分 |
| **门面模式** | 对外通过 Facade 提供统一 API，内部协调子服务 | `RagTestFacade` 协调 8 个子服务 |
| **依赖注入** | 子服务通过 DI 注入，而非直接实例化 | `__init__(self, executor: TestRunExecutor)` |
| **接口兼容** | 拆分后保持现有公开 API 不变 | 门面类转发调用，外部无感知 |

### 3.3 重点拆分方案

#### 3.3.1 RagTestManager（1799 行 → 8 个类）

```
backend/src/service/rag_test/
├── __init__.py
├── facade.py              # RagTestFacade（门面，协调各子服务）~150 行
├── test_run_executor.py   # TestRunExecutor（测试运行/批量并发/分布式锁）~350 行
├── test_case_repo.py      # TestCaseRepository（用例 CRUD/批量导入/预览）~300 行
├── test_set_manager.py    # TestSetManager（测试集 CRUD/用例关联/导出）~250 行
├── draft_generator.py     # DraftGenerator（LLM 草稿生成/审核/导入）~350 行
├── snapshot_manager.py    # SnapshotManager（知识库快照创建/恢复/列表）~200 行
├── metrics_calculator.py  # TestMetricsCalculator（指标计算/聚合/对比）~200 行
└── source_doc_manager.py  # SourceDocumentManager（源文档上传/删除/列表）~150 行
```

#### 3.3.2 RetrievalService（1060 行 → 5 个类）

```
backend/src/service/retrieval/
├── __init__.py
├── orchestrator.py        # RetrievalOrchestrator（主检索流程编排）~200 行
├── retriever_init.py      # RetrieverInitializer（检索器初始化/重载/状态）~150 行
├── query_processor.py     # QueryProcessor（查询重写/同义词扩展）~250 行
├── result_processor.py    # ResultProcessor（结果转换/去重/评分映射）~250 行
└── search_handler.py      # SearchResultHandler（搜索专用/分页/关键词加成）~200 行
```

#### 3.3.3 MetadataProcessor（925 行 → 7 个类）

```
backend/src/core/chunking/
├── __init__.py
├── metadata_extractor.py    # MetadataExtractor（节点元数据提取）~250 行
├── content_cleaner.py       # ContentCleaner（节点内容清理）~50 行
├── chapter_chunker.py       # ChapterChunker（章节级分块）~250 行
├── page_chunker.py          # PageChunker（页面级分块）~150 行
├── hierarchical_chunker.py  # HierarchicalChunker（父子块关联）~150 行
├── splitter_factory.py      # SplitterFactory（分块器工厂）~100 行
└── key_chunk_identifier.py  # KeyChunkIdentifier（关键分块识别）~80 行
```

#### 3.3.4 DocumentIngestionService（637 行 → 5 个类）

```
backend/src/service/ingestion/
├── __init__.py
├── orchestrator.py         # IngestionOrchestrator（导入流程编排/断点续传）~200 行
├── task_state.py           # TaskStateManager（任务状态持久化）~100 行
├── document_parser.py      # DocumentParser（文档解析/VL 降级/质检）~200 行
├── pipeline.py             # IngestionPipeline（分块→元数据→索引流水线）~150 行
└── deduplicator.py         # ContentDeduplicator（内容哈希去重）~80 行
```

#### 3.3.5 IndexManagerService（574 行 → 4 个类）

```
backend/src/service/index/
├── __init__.py
├── lifecycle.py       # IndexLifecycleManager（索引初始化/加载/重试）~200 行
├── persistor.py       # IndexPersistor（持久化/原子写入/备份）~150 行
├── operations.py      # IndexOperations（插入/删除/清空）~150 行
└── chunk_query.py     # ChunkQueryService（分块查询/分页/详情）~150 行
```

### 3.4 拆分优先级

| 优先级 | 类 | 行数 | 原因 |
|--------|-----|------|------|
| P0 | `RagTestManager` | 1799 | 最严重，混合 7+ 职责，测试用例管理核心 |
| P0 | `RetrievalService` | 1060 | RAG 检索核心，高频调用 |
| P1 | `MetadataProcessor` | 925 | 文档入库核心，逻辑复杂 |
| P1 | `DocumentIngestionService` | 637 | 文档导入核心 |
| P1 | `IndexManagerService` | 574 | 索引管理核心 |
| P2 | `CacheService` | 447 | 基础设施，影响性能 |
| P2 | `PromptManager` | 428 | 提示词管理核心 |
| P2 | `TuningController` | 377 | Controller 过厚，应瘦身 |
| P3 | 其他 30+ 个类 | 200-400 | 逐步拆分 |

---

## 4. 统一响应格式设计

### 3.1 响应格式策略

采用**国内常见双字段方案**：

- **HTTP 状态码**：保持 HTTP 语义（200 成功、4xx 客户端错误、5xx 服务端错误）
- **业务错误码**：`code`（数字）+ `error_code`（字符串）双字段，便于前端逻辑判断和国际化扩展

### 3.2 成功响应格式

**HTTP 200**
```json
{
  "code": 0,
  "message": "success",
  "data": { ... }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `code` | `int` | 业务状态码，`0` 表示成功 |
| `message` | `string` | 提示信息 |
| `data` | `any` | 业务数据（可为 null、对象、数组） |

**分页数据扩展格式**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [...],
    "total": 100,
    "page": 1,
    "page_size": 20
  }
}
```

### 3.3 错误响应格式

**HTTP 4xx / 5xx**
```json
{
  "code": 10001,
  "message": "请求参数校验失败",
  "error_code": "INVALID_PARAMS",
  "details": {
    "errors": ["child_profile: field required"]
  },
  "trace_id": "abc-123-def"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `code` | `int` | 业务错误码（数字），便于机器判断 |
| `message` | `string` | 用户可读的错误信息（中文），直接展示给用户 |
| `error_code` | `string` | 错误码标识（英文大写蛇形），供前端逻辑判断和国际化映射 |
| `details` | `object` | 可选，错误的额外上下文信息 |
| `trace_id` | `string` | 可选，请求追踪 ID，便于排查问题 |

### 3.4 HTTP 状态码与业务码映射

| HTTP 状态码 | 使用场景 | 业务码范围 |
|------------|---------|-----------|
| `200` | 请求成功 | `code: 0` |
| `400` | 参数校验失败、业务规则不通过 | `10001-10099` |
| `401` | 未认证或 Token 过期 | `10003` |
| `403` | 权限不足 | `10004` |
| `404` | 资源不存在 | `10005` + 模块特定码 |
| `409` | 资源冲突/重复 | `10006` |
| `429` | 请求频率超限 | `10009` |
| `500` | 服务端内部异常 | `10007` |
| `503` | 依赖服务不可用 | `10008` |

---

## 4. 冗余代码消除规范（强制）

### 4.1 现状问题

当前项目中存在大量**重复代码**，违反 DRY（Don't Repeat Yourself）原则，导致维护成本高、容易引入不一致的 bug：

| 重复模式 | 出现次数 | 影响范围 |
|---------|---------|---------|
| SQLAlchemy Session 获取 | 26 处 | 所有 Controller |
| try/except + logger + HTTPException 模板 | 100+ 处 | 所有 Controller/Service |
| ORM 模型转字典（datetime/enum 安全转换） | 30+ 处 | Controller/Service |
| 文件操作（exists/makedirs/read/write） | 70+ 处 | Service/Core |
| 时间处理（utcnow/now 混用） | 50+ 处 | 遍布全项目 |
| 内容哈希计算 | 7 处 | 多个模块 |
| JSON 序列化 | 15+ 处 | 多个模块 |

**总计可消除重复代码约 280+ 处**。

### 4.2 高频重复模式及提取方案

#### 4.2.1 数据库 Session 管理（26 处重复）

**当前模式**：
```python
# 在每个 controller 函数中重复
from src.core.database import async_session_factory

async def some_endpoint():
    async with async_session_factory() as session:
        # 业务逻辑
```

**提取方案**：`backend/src/utils/db.py`
```python
from contextlib import asynccontextmanager
from src.core.database import async_session_factory

@asynccontextmanager
async def get_db_session():
    """统一数据库会话获取"""
    async with async_session_factory() as session:
        yield session

async def execute_with_session(func, *args, **kwargs):
    """自动管理 session 生命周期的执行器"""
    async with async_session_factory() as session:
        return await func(session, *args, **kwargs)
```

**使用后**：
```python
from src.utils.db import get_db_session

async def some_endpoint():
    async with get_db_session() as session:
        # 业务逻辑
```

#### 4.2.2 错误处理模板（100+ 处重复）

**当前模式**（三种风格混用）：
```python
# 风格 1：带详情
except Exception as e:
    logger.error(f"XXX失败: {e}")
    raise HTTPException(status_code=500, detail=f"XXX失败: {str(e)}")

# 风格 2：不带详情
except Exception as e:
    logger.error("XXX失败")
    raise HTTPException(status_code=500, detail="XXX失败")

# 风格 3：裸错误
except Exception as e:
    raise HTTPException(status_code=500, detail=str(e))
```

**提取方案**：`backend/src/utils/response.py`
```python
from src.utils.logger import logger
from src.utils.exceptions import InternalServerErrorException

def handle_api_error(e: Exception, action: str, include_detail: bool = True):
    """统一错误处理"""
    logger.error(f"{action}失败: {e}", exc_info=True)
    if include_detail:
        raise InternalServerErrorException(f"{action}失败: {str(e)}")
    raise InternalServerErrorException(f"{action}失败")

# 快捷函数
def not_found(resource: str, detail: dict = None):
    from src.utils.exceptions import ResourceNotFoundException
    raise ResourceNotFoundException(
        error_code=f"{resource.upper()}_NOT_FOUND",
        message=f"{resource}不存在",
        details=detail
    )
```

**使用后**：
```python
from src.utils.response import handle_api_error, not_found

try:
    result = do_something()
except Exception as e:
    handle_api_error(e, "获取数据")

# 或直接抛出
if not item:
    not_found("测试用例", {"id": case_id})
```

#### 4.2.3 ORM 模型序列化（30+ 处重复）

**当前模式**：
```python
# 重复的 datetime 安全转换
"created_at": item.created_at.isoformat() if item.created_at else None,
"updated_at": item.updated_at.isoformat() if item.updated_at else None,

# 重复的 enum 安全转换
"status": item.status.value if item.status else None,
"source_type": item.source_type.value if item.source_type else None,
```

**提取方案**：`backend/src/utils/serializers.py`
```python
from datetime import datetime
from enum import Enum
from typing import Any

def safe_isoformat(dt: datetime | None) -> str | None:
    """安全转换 datetime 为 ISO 格式字符串"""
    return dt.isoformat() if dt else None

def safe_enum_value(enum_val: Enum | None) -> str | None:
    """安全转换 enum 为字符串值"""
    return enum_val.value if enum_val else None

def model_to_dict(model, fields: dict[str, callable] = None) -> dict:
    """
    ORM 模型转字典
    fields: 字段名 -> 转换函数的映射
    """
    if not fields:
        return {k: v for k, v in model.__dict__.items() if not k.startswith('_')}
    
    result = {}
    for field_name, converter in fields.items():
        value = getattr(model, field_name, None)
        result[field_name] = converter(value) if converter else value
    return result
```

**使用后**：
```python
from src.utils.serializers import safe_isoformat, safe_enum_value, model_to_dict

# 方式 1：手动转换
{
    "created_at": safe_isoformat(item.created_at),
    "status": safe_enum_value(item.status),
}

# 方式 2：使用 model_to_dict
model_to_dict(item, fields={
    "id": None,
    "name": None,
    "created_at": safe_isoformat,
    "status": safe_enum_value,
})
```

#### 4.2.4 文件操作（70+ 处重复）

**当前模式**：
```python
# 重复的目录检查与创建
if not os.path.exists(dir_path):
    os.makedirs(dir_path, exist_ok=True)

# 重复的文件读取
with open(file_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

# 重复的文件写入
with open(file_path, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
```

**提取方案**：`backend/src/utils/file_ops.py`
```python
import os
import json
from pathlib import Path
from typing import Any

def ensure_dir(path: str | Path) -> Path:
    """确保目录存在，不存在则创建"""
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path

def safe_remove(path: str | Path) -> bool:
    """安全删除文件，不存在则返回 False"""
    path = Path(path)
    if path.exists():
        path.unlink()
        return True
    return False

def read_json(path: str | Path, default: Any = None) -> Any:
    """读取 JSON 文件，失败返回默认值"""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default

def write_json(path: str | Path, data: Any, indent: int = 2) -> None:
    """写入 JSON 文件，自动创建目录"""
    path = Path(path)
    ensure_dir(path.parent)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)
```

#### 4.2.5 时间处理（50+ 处重复）

**当前模式**：
```python
# utcnow() 和 now() 混用，时区不一致
from datetime import datetime, timedelta

datetime.utcnow()  # 已标记为 deprecated (Python 3.12+)
datetime.now()     # 本地时区
datetime.now() - timedelta(days=7)
```

**提取方案**：`backend/src/utils/time_utils.py`
```python
from datetime import datetime, timezone, timedelta

def utc_now() -> datetime:
    """获取当前 UTC 时间（带时区信息）"""
    return datetime.now(timezone.utc)

def time_range(days: int = 0, hours: int = 0, minutes: int = 0) -> tuple[datetime, datetime]:
    """获取从 N 天前到现在的时间范围"""
    end = utc_now()
    start = end - timedelta(days=days, hours=hours, minutes=minutes)
    return start, end

def safe_timestamp(dt: datetime | None) -> str | None:
    """安全转换 datetime 为时间戳字符串"""
    return dt.isoformat() if dt else None
```

#### 4.2.6 其他重复模式

| 模式 | 出现次数 | 提取位置 | 函数名 |
|------|---------|---------|--------|
| 内容哈希 `hashlib.sha256()` | 7 处 | `utils/crypto.py` | `hash_content(content: str) -> str` |
| UUID 生成 `str(uuid.uuid4())` | 15 处 | `utils/id_generator.py` | `generate_id() -> str` |
| 用户获取 `current_user.username if current_user else "system"` | 4 处 | `utils/auth_helpers.py` | `get_user_id(current_user) -> str` |
| 服务检查 `if not self.service: raise 501` | 5 处 | `utils/service_checker.py` | `require_service(service, name)` |

### 4.3 新建工具模块清单

| 新文件 | 包含函数 | 可消除重复数 | 优先级 |
|--------|---------|-------------|--------|
| `utils/db.py` | `get_db_session()`, `execute_with_session()` | 26 处 | P0 |
| `utils/response.py` | `handle_api_error()`, `not_found()`, `server_error()` | 100+ 处 | P0 |
| `utils/serializers.py` | `safe_isoformat()`, `safe_enum_value()`, `model_to_dict()` | 30+ 处 | P0 |
| `utils/file_ops.py` | `ensure_dir()`, `safe_remove()`, `read_json()`, `write_json()` | 70+ 处 | P1 |
| `utils/time_utils.py` | `utc_now()`, `time_range()`, `safe_timestamp()` | 50+ 处 | P1 |
| `utils/crypto.py` | `hash_content()` | 7 处 | P2 |
| `utils/id_generator.py` | `generate_id()` | 15 处 | P2 |
| `utils/auth_helpers.py` | `get_user_id()` | 4 处 | P3 |

---

## 5. 代码引用规范（强制）

### 5.1 现状问题

当前项目中代码引用（import）存在以下混乱：

| 问题 | 严重性 | 影响范围 | 示例 |
|------|--------|---------|------|
| **`model/` vs `models/` 命名冲突** | 🔴 高 | 31 处引用 | `src.model.schemas`（Pydantic）vs `src.models.test_case`（SQLAlchemy） |
| **`__init__.py` 缺失** | 🟡 中 | `controller/`, `service/`, `core/`, `utils/` 无 `__init__.py` | `server.py` 依赖隐式命名空间包 |
| **循环导入** | 🟡 中 | `config/__init__.py` ↔ `config/core/manager.py` | 通过延迟导入勉强工作，脆弱 |
| **import 无分组/排序** | 🟢 低 | 170+ 文件 | stdlib/third-party/local 混杂 |
| **函数内 import 散布** | 🟢 低 | 364 处 | `import asyncio` 在函数内，部分合理部分冗余 |
| **重复 import** | 🟢 低 | 多处 | `from src.repository import TestCaseRepository` 在同一文件出现 6 次 |

### 5.2 业内最佳实践

基于 Python/FastAPI 项目的主流规范（如 FastAPI 官方模板、Cookiecutter、RealWorld 等）：

| 规范 | 说明 | 代表项目 |
|------|------|---------|
| **绝对导入为主** | 跨模块统一使用 `from src.xxx`，避免相对导入的路径混乱 | FastAPI 官方、Django |
| **相对导入仅限 `__init__.py`** | 仅在聚合导出时使用 `from .xxx` | Python 标准库 |
| **Import 分组排序** | stdlib → third-party → local，每组空行分隔，字母排序 | isort、PEP 8 |
| **禁止函数内 import** | 除非解决循环依赖或懒加载重型库 | Google Python Style |
| **`__init__.py` 显式导出** | 每个包都有 `__init__.py`，明确导出公共 API | 所有主流框架 |

### 5.3 改造方案

#### 5.3.1 重命名 `src/model/` → `src/schemas/`

**原因**：
- 消除 `model` vs `models` 仅差一个 `s` 的混淆
- 对齐 CLAUDE.md "实体类集中管理" 规范
- 符合 FastAPI 社区惯例（`schemas/` 存放 Pydantic 模型）

**影响范围**：31 处引用需要更新

**迁移映射**：
| 原路径 | 新路径 |
|--------|--------|
| `src.model.schemas` | `src.schemas.assessment` |
| `src.model.tuning` | `src.schemas.test_case` |
| `src.model.rag_test` | `src.schemas.test_case` |
| `src.model.document` | `src.schemas.rag` |

#### 5.3.2 补充缺失的 `__init__.py`

为以下目录创建 `__init__.py`，显式导出公共 API：

**`backend/src/controller/__init__.py`**：
```python
"""Controller 模块，导出所有路由路由器"""
from .task_controller import router as task_router
from .rag_controller import router as rag_router
from .rag_test_controller import router as rag_test_router
from .config_controller import router as config_router
from .monitoring_controller import router as monitoring_router
from .prompt_controller import router as prompt_router
from .health_controller import router as health_router

__all__ = [
    "task_router",
    "rag_router",
    "rag_test_router",
    "config_router",
    "monitoring_router",
    "prompt_router",
    "health_router",
]
```

**`backend/src/utils/__init__.py`**：
```python
"""工具模块，导出常用工具"""
from .logger import logger

__all__ = ["logger"]
```

**`backend/src/service/__init__.py`**：
```python
"""Service 模块，导出所有服务单例"""
from .rag_service import rag_service
from .rag_test_manager import rag_test_manager
from .cache_service import cache_service

__all__ = ["rag_service", "rag_test_manager", "cache_service"]
```

#### 5.3.3 统一 Import 分组格式

所有 Python 文件必须遵循以下格式：

```python
# 1. 标准库（按字母排序）
import asyncio
import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional

# 2. 第三方库（按字母排序）
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select

# 3. 本地应用（from src.xxx，按字母排序）
from src.config import settings
from src.schemas.assessment import UserInput, AgentState
from src.service.rag_test_manager import rag_test_manager
from src.utils.logger import logger
```

**规则**：
- 每组之间用一个空行分隔
- 组内按字母顺序排序
- 禁止混用绝对/相对导入（`__init__.py` 除外）
- 禁止函数内 import（除非解决循环依赖）

#### 5.3.4 解决循环导入

**当前循环链**：
```
config/__init__.py (line 592) → from .core.manager import ConfigManager
config/core/manager.py (line 10) → from src.config import settings
```

**解决方案**：
1. `config/core/manager.py` 中 `from src.config import settings` 改为从 `config/modules/app.py` 直接导入
2. `config/__init__.py` 中的 `config_manager` 导入移至 `server.py` lifespan 中初始化

#### 5.3.5 消除函数内冗余 import

**必须移至文件顶部**（非循环依赖场景）：
- `import asyncio`（在 `rag_test_controller.py:261` 等 15 处）
- `import uuid`（在 `prompt_manager.py:303` 等 8 处）
- `import json`（在多处）
- `import hashlib`（在多处）
- `import os`（在 `config/__init__.py:553` 等）

**允许保留函数内 import**（循环依赖/懒加载场景）：
- `config_manager._get_repos()` — 避免循环依赖
- `import weasyprint` — 重型第三方库
- `import chardet` — 条件加载

#### 5.3.6 拆分 `config/__init__.py`

当前 614 行的 `config/__init__.py` 违反单一职责，拆分为：

| 新文件 | 职责 | 预估行数 |
|--------|------|---------|
| `config/modules/app.py` | `Settings` 类定义 | ~200 |
| `config/core/singleton.py` | 单例管理（`get_settings`, `reload_settings`） | ~50 |
| `config/core/init.py` | 应用启动初始化（embedding init, watcher） | ~100 |
| `config/__init__.py` | 纯聚合导出 | ~30 |

### 5.4 工具化支持

**添加 `isort` 到项目**：

`pyproject.toml`：
```toml
[tool.isort]
profile = "black"
line_length = 88
sections = ["FUTURE", "STDLIB", "THIRDPARTY", "FIRSTPARTY", "LOCALFOLDER"]
known_first_party = ["src"]
force_single_line = false
combine_as_imports = true
```

**添加 `ruff` 检查**：
```toml
[tool.ruff.lint]
select = ["F401", "F811", "E402"]  # unused imports, redefined imports, module level import not at top
```

**CI 检查命令**：
```bash
isort backend/src/ --check --diff
ruff check backend/src/ --select F401,F811,E402
```

---

## 6. 前端架构重构规范（强制）

### 6.1 现状问题

当前前端代码存在以下混乱：

| 问题 | 严重性 | 影响范围 | 示例 |
|------|--------|---------|------|
| **组件位置混乱** | 🔴 高 | `components/` vs `features/*/components/` 并存 | `components/assessment/` 与 `features/rag-eval/components/` |
| **页面展示与逻辑混合** | 🔴 高 | 所有 Page 组件 | `RunListPage.tsx` 217 行混合数据获取、过滤、渲染 |
| **Store 过度膨胀** | 🔴 高 | `configStore.ts` 369 行 | 混合状态、业务逻辑、API 调用、定时器 |
| **API 调用不统一** | 🟡 中 | 部分页面直接调用 API | `RunListPage.tsx:49` 直接调用 `getTestRuns()` |
| **重复代码** | 🟡 中 | 95+ 处 `message.*` 调用 | 每个页面重复 loading/error/success 处理 |
| **类型定义重复** | 🟡 中 | `models/` vs `api/*/types.ts` | 循环 re-export 链 |
| **SSE 实现重复** | 🟡 中 | 2 个 SSE hook + 1 个 Service | `useSSE.ts`、`useSseClient.ts`、`SseClient` |
| **孤儿页面** | 🟢 低 | `src/pages/` | `SystemConfigPage.tsx`、`BookChunksPage.tsx` |

### 6.2 业内最佳实践

基于 React/TypeScript 项目的主流架构模式：

| 方案 | 特点 | 代表项目 |
|------|------|---------|
| **Feature-Sliced Design (FSD)** | 按业务特性分层，严格依赖规则 | 俄罗斯 Yandex、Sberbank |
| **Atomic Design** | 原子→分子→有机体→模板→页面 | Pattern Lab、Storybook |
| **Domain-Driven Structure** | 按业务领域组织，每个领域自包含 | Netflix、Spotify |

**推荐采用 FSD Lite**（简化版 Feature-Sliced Design），原因：
- 项目已部分采用 feature-based 结构（`features/rag-eval/` 最完整）
- FSD 提供清晰的层级依赖规则，防止循环依赖
- 适合中大型项目（当前 50+ 页面/组件文件）

### 6.3 目标目录结构

```
frontend/src/
├── app/                    # 应用启动层
│   ├── main.tsx            # 入口
│   ├── App.tsx             # 根组件
│   ├── providers/          # 全局 Provider（Router, QueryClient, Store）
│   └── styles/             # 全局样式
│
├── pages/                  # 路由页面层（组合 features/widgets）
│   ├── assessment/
│   │   └── index.tsx       # 评估页面
│   ├── knowledge-base/
│   │   └── index.tsx       # 知识库页面
│   └── system-config/
│       └── index.tsx       # 系统配置页面
│
├── widgets/                # 复合区块层（多 feature 组合）
│   ├── assessment-form-widget/
│   ├── report-viewer-widget/
│   └── sidebar-layout/
│
├── features/               # 业务特性层（自包含模块）
│   ├── assessment/
│   │   ├── components/     # 特性专属组件
│   │   ├── hooks/          # 特性专属 hooks
│   │   ├── stores/         # 特性专属 stores
│   │   ├── types/          # 特性专属类型
│   │   └── index.ts        # 公共导出
│   ├── rag-eval/
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── stores/
│   │   ├── utils/
│   │   └── index.ts
│   ├── documents/
│   ├── knowledge/
│   ├── monitoring/
│   ├── prompts/
│   └── config/
│
├── entities/               # 业务实体层（核心数据模型）
│   ├── test-run/
│   │   ├── types.ts        # TestRun 类型定义
│   │   ├── api.ts          # TestRun API 调用
│   │   └── components/     # TestRun 展示组件（StatusTag 等）
│   ├── test-case/
│   ├── document/
│   ├── prompt/
│   └── config/
│
└── shared/                 # 共享层（跨特性复用）
    ├── api/                # API 客户端、拦截器
    │   ├── client.ts
    │   └── interceptors/
    ├── ui/                 # 通用 UI 组件
    │   ├── Button/
    │   ├── Table/
    │   ├── Modal/
    │   ├── EmptyState/
    │   ├── ErrorBoundary/
    │   └── LoadingSpinner/
    ├── hooks/              # 通用 hooks
    │   ├── useModal.ts
    │   ├── usePagination.ts
    │   ├── useDebounce.ts
    │   └── useApiCall.ts
    ├── lib/                # 工具函数、常量
    │   ├── constants.ts
    │   ├── notification.ts
    │   └── formatters.ts
    └── types/              # 通用类型
        └── common.ts
```

### 6.4 分层依赖规则

```
pages → widgets → features → entities → shared
  ↓        ↓         ↓          ↓         ↓
  只能依赖下层，禁止跨层或反向依赖
```

| 层级 | 职责 | 禁止 |
|------|------|------|
| `pages/` | 路由组合、页面布局 | 直接写业务逻辑、API 调用 |
| `widgets/` | 多 feature 组合区块 | 直接调用 API |
| `features/` | 完整业务特性 | 依赖其他 feature |
| `entities/` | 核心数据模型+展示 | 包含页面路由逻辑 |
| `shared/` | 跨特性复用工具 | 包含业务逻辑 |

### 6.5 改造方案

#### 6.5.1 页面展示与逻辑分离

**当前模式**（混合）：
```tsx
// RunListPage.tsx — 217 行混合所有逻辑
const RunListPage = () => {
  const [loading, setLoading] = useState(false);
  const [runs, setRuns] = useState([]);
  
  // 数据获取（业务逻辑）
  useEffect(() => {
    setLoading(true);
    getTestRuns().then(setRuns).finally(() => setLoading(false));
  }, []);
  
  // 删除处理（业务逻辑）
  const handleDelete = async (id) => {
    await deleteTestRun(id);
    message.success('删除成功');
  };
  
  // 过滤计算（业务逻辑）
  const filteredRuns = runs.filter(r => r.status === statusFilter);
  
  // 列定义（UI 配置）
  const columns = [...];
  
  // JSX 渲染（展示）
  return <Table columns={columns} dataSource={filteredRuns} loading={loading} />;
};
```

**改造后**（分离）：

```tsx
// features/rag-eval/hooks/useRunList.ts
export function useRunList() {
  const { data: runs, isLoading, mutate } = useQuery({
    queryKey: ['test-runs'],
    queryFn: getTestRuns,
  });
  
  const deleteRun = useMutation({
    mutationFn: deleteTestRun,
    onSuccess: () => {
      mutate();
      notification.success('删除成功');
    },
  });
  
  return { runs, isLoading, deleteRun: deleteRun.mutate };
}

// features/rag-eval/components/RunListTable.tsx
export const RunListTable = ({ runs, onDelete }: Props) => {
  const columns = [...]; // 列定义
  return <Table columns={columns} dataSource={runs} />;
};

// pages/rag-eval/run-list.tsx
export const RunListPage = () => {
  const { runs, isLoading, deleteRun } = useRunList();
  return <RunListTable runs={runs} loading={isLoading} onDelete={deleteRun} />;
};
```

#### 6.5.2 拆分 `configStore.ts`（369 行）

**当前问题**：
- 混合状态定义、业务逻辑、API 调用、定时器
- 模块级可变状态 `healthDiagnosticTimer`

**拆分方案**：

| 新文件 | 职责 | 预估行数 |
|--------|------|---------|
| `features/config/stores/configStore.ts` | 纯状态管理 | ~100 |
| `features/config/services/diagnosticService.ts` | 健康诊断逻辑 | ~150 |
| `features/config/services/scoringService.ts` | 评分算法 | ~100 |
| `features/config/hooks/useConfig.ts` | 配置操作 hooks | ~100 |

#### 6.5.3 统一 API 调用模式

**规则**：
- 所有 API 调用通过 `entities/*/api.ts` 或 `features/*/hooks/` 封装
- 页面组件禁止直接调用 `apiClient.get/post`
- 使用 React Query 管理服务端状态

**当前**：
```tsx
// 直接调用
const runs = await getTestRuns();
```

**改造后**：
```tsx
// 通过 hook
const { data: runs } = useRunList();

// 或通过 mutation
const { mutate: createRun } = useCreateRun();
```

#### 6.5.4 消除重复代码

| 重复模式 | 出现次数 | 提取位置 | 方案 |
|---------|---------|---------|------|
| `message.success/error` | 95+ 处 | `shared/lib/notification.ts` | `handleApiCall(fn, messages)` |
| `STATUS_CONFIG` | 多处 | `entities/test-run/components/StatusTag.tsx` | 统一状态标签组件 |
| Loading/Error 状态 | 每页重复 | `shared/hooks/useApiCall.ts` | 封装通用 API 调用 hook |
| SSE 连接 | 2 hook + 1 service | `shared/hooks/useSSE.ts` | 统一为单一 hook |

**`handleApiCall` 工具函数**：
```tsx
// shared/lib/notification.ts
export async function handleApiCall<T>(
  fn: () => Promise<T>,
  options?: {
    successMsg?: string;
    errorMsg?: string;
    onSuccess?: (data: T) => void;
  }
): Promise<T | null> {
  try {
    const data = await fn();
    if (options?.successMsg) notification.success(options.successMsg);
    options?.onSuccess?.(data);
    return data;
  } catch (error) {
    notification.error(options?.errorMsg || '操作失败');
    return null;
  }
}
```

**使用后**：
```tsx
// 使用前（5 行）
try {
  await deleteTestRun(id);
  message.success('删除成功');
} catch {
  message.error('删除失败');
}

// 使用后（1 行）
await handleApiCall(() => deleteTestRun(id), {
  successMsg: '删除成功',
  errorMsg: '删除失败',
});
```

#### 6.5.5 统一类型定义

**规则**：
- API 响应类型定义在 `api/*/types.ts`
- 业务实体类型定义在 `entities/*/types.ts`
- 禁止循环 re-export

**迁移映射**：
| 当前路径 | 新路径 |
|---------|--------|
| `models/index.ts` | 删除，类型移至 `entities/*/types.ts` |
| `api/assessment/types.ts` | `entities/assessment/types.ts` |
| `api/rag-test/types.ts` | `entities/test-run/types.ts` + `entities/test-case/types.ts` |
| `types/sse-events.ts` | `shared/types/sse.ts` |

#### 6.5.6 迁移孤儿页面

| 当前路径 | 新路径 |
|---------|--------|
| `pages/SystemConfigPage.tsx` | `features/config/pages/SystemConfigPage.tsx` |
| `pages/BookChunksPage.tsx` | `features/documents/pages/BookChunksPage.tsx` |

#### 6.5.7 统一组件位置

**规则**：
- 特性专属组件放在 `features/*/components/`
- 删除空的 `components/rag-test/` 目录
- 迁移 `components/assessment/*` → `features/assessment/components/`
- 迁移 `components/documents/*` → `features/documents/components/`
- 迁移 `components/config/*`（19 个文件）→ `features/config/components/`

### 6.6 工具化支持

**添加 ESLint 规则**：
```json
{
  "rules": {
    "no-restricted-imports": [
      "error",
      {
        "patterns": [
          { "group": ["**/features/**"], "message": "禁止跨 feature 导入" },
          { "group": ["**/pages/**"], "message": "禁止从 pages 导入" }
        ]
      }
    ]
  }
}
```

**添加路径别名**（`tsconfig.json`）：
```json
{
  "compilerOptions": {
    "paths": {
      "@/*": ["./src/*"],
      "@app/*": ["./src/app/*"],
      "@pages/*": ["./src/pages/*"],
      "@features/*": ["./src/features/*"],
      "@entities/*": ["./src/entities/*"],
      "@widgets/*": ["./src/widgets/*"],
      "@shared/*": ["./src/shared/*"]
    }
  }
}
```

---

## 7. 统一响应格式设计

### 5.1 错误码分段

| 范围 | 模块 | 说明 |
|------|------|------|
| `0` | - | 成功 |
| `10000-10999` | 通用错误 | 参数校验、权限、系统异常等 |
| `11000-11999` | 评估模块 (Assessment) | 儿童评估相关 |
| `12000-12999` | RAG 知识库模块 | 文档上传、检索、分块等 |
| `13000-13999` | RAG 测试模块 | 测试集、用例、运行、报告等 |
| `14000-14999` | 配置管理模块 | 系统配置、校验、回滚等 |
| `15000-15999` | 提示词管理模块 | Prompt 版本、A/B 测试等 |
| `16000-16999` | 监控模块 | LLM 调用统计、追踪等 |

### 3.2 通用错误码定义

| 错误码 | error_code | message | 说明 |
|--------|-----------|---------|------|
| `0` | `SUCCESS` | 成功 | 操作成功 |
| `10001` | `INVALID_PARAMS` | 请求参数校验失败 | 参数格式或类型错误 |
| `10002` | `MISSING_REQUIRED_FIELD` | 缺少必填字段 | 必填参数未传 |
| `10003` | `UNAUTHORIZED` | 未授权，请先登录 | 未认证或 Token 过期 |
| `10004` | `FORBIDDEN` | 无权限执行此操作 | 权限不足 |
| `10005` | `RESOURCE_NOT_FOUND` | 请求的资源不存在 | 通用资源不存在 |
| `10006` | `DUPLICATE_RESOURCE` | 资源已存在 | 重复创建 |
| `10007` | `INTERNAL_ERROR` | 系统内部异常，请稍后重试 | 未预期的服务器错误 |
| `10008` | `SERVICE_UNAVAILABLE` | 服务暂时不可用 | 依赖服务异常 |
| `10009` | `REQUEST_TIMEOUT` | 请求超时 | 处理时间过长 |
| `10010` | `TASK_CANCELLED` | 任务已取消 | 异步任务被取消 |

### 3.3 各模块错误码示例

**RAG 知识库模块 (12000-12999)**：
| 错误码 | error_code | message |
|--------|-----------|---------|
| `12001` | `DOCUMENT_NOT_FOUND` | 文档不存在 |
| `12002` | `UNSUPPORTED_FILE_TYPE` | 不支持的文件类型 |
| `12003` | `DOCUMENT_PARSE_FAILED` | 文档解析失败 |
| `12004` | `INDEX_NOT_AVAILABLE` | 索引未就绪 |
| `12005` | `CHUNK_NOT_FOUND` | 分块不存在 |

**RAG 测试模块 (13000-13999)**：
| 错误码 | error_code | message |
|--------|-----------|---------|
| `13001` | `TEST_CASE_NOT_FOUND` | 测试用例不存在 |
| `13002` | `TEST_SET_NOT_FOUND` | 测试集不存在 |
| `13003` | `TEST_RUN_NOT_FOUND` | 测试运行记录不存在 |
| `13004` | `DRAFT_NOT_FOUND` | 测试草稿不存在 |
| `13005` | `REPORT_NOT_FOUND` | 评估报告不存在 |
| `13006` | `IMPORT_FAILED` | 导入失败 |

**配置管理模块 (14000-14999)**：
| 错误码 | error_code | message |
|--------|-----------|---------|
| `14001` | `CONFIG_VALIDATION_FAILED` | 配置校验失败 |
| `14002` | `CONFIG_CONFLICT` | 配置冲突 |
| `14003` | `ROLLBACK_FAILED` | 配置回滚失败 |

---

## 6. 后端实现方案

### 6.1 核心组件

#### 6.1.1 统一响应包装类

**文件位置**：`backend/src/utils/response.py`

```python
from typing import Any, Optional
from pydantic import BaseModel

class APIResponse(BaseModel):
    """统一 API 响应模型"""
    code: int = 0
    message: str = "success"
    data: Optional[Any] = None

    @classmethod
    def success(cls, data: Any = None, message: str = "success") -> "APIResponse":
        return cls(code=0, message=message, data=data)

    @classmethod
    def error(
        cls,
        code: int,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[dict] = None,
        trace_id: Optional[str] = None,
    ) -> dict:
        """返回错误字典（用于异常处理器）"""
        result = {
            "code": code,
            "message": message,
            "error_code": error_code or "UNKNOWN_ERROR",
        }
        if details:
            result["details"] = details
        if trace_id:
            result["trace_id"] = trace_id
        return result
```

#### 6.1.2 自定义业务异常

**文件位置**：`backend/src/utils/exceptions.py`（扩展已有文件）

```python
from typing import Optional

class AppException(Exception):
    """应用异常基类"""
    def __init__(
        self,
        status_code: int,
        code: int,
        message: str,
        error_code: str = "APP_ERROR",
        details: Optional[dict] = None,
    ):
        self.status_code = status_code  # HTTP 状态码
        self.code = code                # 业务错误码（数字）
        self.message = message          # 用户可读信息
        self.error_code = error_code    # 错误码标识（字符串）
        self.details = details          # 额外上下文
        super().__init__(message)

# 通用异常
class InvalidParamsException(AppException):
    def __init__(self, message: str = "请求参数校验失败", details: Optional[dict] = None):
        super().__init__(
            status_code=400,
            code=10001,
            message=message,
            error_code="INVALID_PARAMS",
            details=details,
        )

class ResourceNotFoundException(AppException):
    def __init__(self, message: str = "请求的资源不存在", error_code: str = "RESOURCE_NOT_FOUND", details: Optional[dict] = None):
        super().__init__(
            status_code=404,
            code=10005,
            message=message,
            error_code=error_code,
            details=details,
        )

class UnauthorizedException(AppException):
    def __init__(self, message: str = "未授权，请先登录"):
        super().__init__(
            status_code=401,
            code=10003,
            message=message,
            error_code="UNAUTHORIZED",
        )

class ForbiddenException(AppException):
    def __init__(self, message: str = "无权限执行此操作"):
        super().__init__(
            status_code=403,
            code=10004,
            message=message,
            error_code="FORBIDDEN",
        )

class InternalServerErrorException(AppException):
    def __init__(self, message: str = "系统内部异常，请稍后重试"):
        super().__init__(
            status_code=500,
            code=10007,
            message=message,
            error_code="INTERNAL_ERROR",
        )

# 各模块异常按同样模式定义...
```

#### 6.1.3 全局异常处理器

**文件位置**：`backend/src/middleware/exception_handler.py`（新建）

```python
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from src.utils.exceptions import AppException
from src.utils.logger import logger
from src.schemas.common import APIResponse

async def app_exception_handler(request: Request, exc: AppException):
    """处理自定义应用异常"""
    logger.warning(f"AppException: {exc.error_code} ({exc.code}) - {exc.message}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.code,
            "message": exc.message,
            "error_code": exc.error_code,
            "details": exc.details,
        },
    )

async def http_exception_handler(request: Request, exc: HTTPException):
    """处理 FastAPI HTTPException（兼容旧代码过渡期）"""
    logger.warning(f"HTTPException: {exc.status_code} - {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.status_code * 100,
            "message": str(exc.detail),
            "error_code": "HTTP_ERROR",
        },
    )

async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """处理请求参数校验异常"""
    errors = exc.errors()
    messages = [f"{e['loc'][-1]}: {e['msg']}" for e in errors]
    return JSONResponse(
        status_code=400,
        content={
            "code": 10001,
            "message": "请求参数校验失败",
            "error_code": "INVALID_PARAMS",
            "details": {"errors": messages},
        },
    )

async def global_exception_handler(request: Request, exc: Exception):
    """兜底处理所有未捕获异常"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "code": 10007,
            "message": "系统内部异常，请稍后重试",
            "error_code": "INTERNAL_ERROR",
        },
    )
```

#### 6.1.4 注册异常处理器

**文件位置**：`backend/src/server.py`（修改）

```python
from src.middleware.exception_handler import (
    app_exception_handler,
    http_exception_handler,
    validation_exception_handler,
    global_exception_handler,
)
from src.utils.exceptions import AppException

def create_app() -> FastAPI:
    app = FastAPI(...)
    
    # 注册异常处理器（按优先级从高到低）
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, global_exception_handler)
    
    # ... 其他配置
```

### 6.2 响应包装中间件

**文件位置**：`backend/src/middleware/response_wrapper.py`（新建）

```python
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from src.utils.response import APIResponse

class ResponseWrapperMiddleware(BaseHTTPMiddleware):
    """自动包装成功响应为统一格式"""
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # 跳过 SSE、文件下载等非标准响应
        if isinstance(response, StreamingResponse) or response.status_code in (204, 304):
            return response
        
        # 跳过已经是错误响应的情况
        if isinstance(response, JSONResponse) and response.status_code >= 400:
            return response
        
        # 对成功响应进行包装
        if response.status_code == 200:
            body = getattr(response, 'body', None)
            if body:
                import json
                try:
                    original_data = json.loads(body)
                    # 如果已经是 {code, message, data} 格式，不再包装
                    if isinstance(original_data, dict) and "code" in original_data:
                        return response
                    wrapped = APIResponse.success(data=original_data)
                    return JSONResponse(content=wrapped.model_dump())
                except (json.JSONDecodeError, AttributeError):
                    pass
        
        return response
```

### 6.3 改造策略

#### 6.3.1 渐进式改造

考虑到系统已有大量接口，采用**渐进式改造**策略：

**Phase 1：基础设施搭建**
- 创建 `APIResponse`、`AppException`、全局异常处理器
- 注册异常处理器到 FastAPI
- 新增接口直接使用新规范

**Phase 2：核心接口改造**
- 优先改造高频使用的接口：评估、RAG 搜索、文档管理
- 旧接口通过异常处理器兼容（HTTPException 自动映射）

**Phase 3：全量改造**
- 逐个 Controller 替换为 `BusinessException`
- 移除所有 `raise HTTPException` 调用
- 统一错误信息为中文

#### 6.3.2 Controller 改造示例

**改造前**：
```python
@router.get("/tasks/{task_id}")
async def get_task(task_id: str):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {"task": tasks[task_id]}
```

**改造后**：
```python
from src.schemas import APIResponse
from src.utils.exceptions import ResourceNotFoundException

@router.get("/tasks/{task_id}")
async def get_task(task_id: str):
    if task_id not in tasks:
        raise ResourceNotFoundException(
            error_code="TASK_NOT_FOUND",
            message="任务不存在",
            details={"task_id": task_id}
        )
    return APIResponse.success(data={"task": tasks[task_id]})
```

**响应示例（HTTP 404）**：
```json
{
  "code": 10005,
  "message": "任务不存在",
  "error_code": "TASK_NOT_FOUND",
  "details": { "task_id": "xxx" }
}
```

---

## 7. 前端实现方案

### 7.1 统一请求拦截器改造

**文件位置**：`frontend/src/api/client.ts`（修改）

```typescript
import axios from 'axios';
import { API_BASE_URL, API_TIMEOUT } from '../lib/constants';
import { message } from 'antd';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: API_TIMEOUT,
  headers: { 'Content-Type': 'application/json' },
});

// 请求拦截
apiClient.interceptors.request.use(
  (config) => {
    if (config.data instanceof FormData) {
      delete config.headers['Content-Type'];
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// 响应拦截
apiClient.interceptors.response.use(
  (response) => {
    const { code, message: msg, data, error_code } = response.data;
    
    // 成功响应（HTTP 200 + code 0）
    if (code === 0) {
      return { ...response, data };  // 解包 data
    }
    
    // 业务错误（HTTP 200 但 code 非 0，理论上不应出现）
    handleBusinessError(code, msg, error_code);
    return Promise.reject({ code, message: msg, errorCode: error_code, data });
  },
  (error) => {
    // HTTP 4xx/5xx 错误
    const responseData = error.response?.data;
    const msg = responseData?.message || error.message || '请求失败';
    const errorCode = responseData?.error_code;
    
    // 统一处理业务错误
    handleBusinessError(responseData?.code, msg, errorCode);
    
    return Promise.reject({
      code: responseData?.code,
      message: msg,
      errorCode,
      status: error.response?.status,
    });
  }
);

// 业务错误统一处理
function handleBusinessError(code: number, msg: string, errorCode?: string) {
  // 某些错误不需要全局提示（由业务层自行处理）
  const silentErrors = ['FORM_VALIDATION_FAILED', 'DRAFT_REVIEW_REJECTED'];
  if (silentErrors.includes(errorCode || '')) return;
  
  message.error(msg);
}
```

### 7.2 错误码映射表

**文件位置**：`frontend/src/constants/errorCodes.ts`（新建）

```typescript
export const ErrorCodes = {
  SUCCESS: 'SUCCESS',
  INVALID_PARAMS: 'INVALID_PARAMS',
  RESOURCE_NOT_FOUND: 'RESOURCE_NOT_FOUND',
  INTERNAL_ERROR: 'INTERNAL_ERROR',
  
  // RAG 知识库
  DOCUMENT_NOT_FOUND: 'DOCUMENT_NOT_FOUND',
  UNSUPPORTED_FILE_TYPE: 'UNSUPPORTED_FILE_TYPE',
  
  // RAG 测试
  TEST_CASE_NOT_FOUND: 'TEST_CASE_NOT_FOUND',
  TEST_SET_NOT_FOUND: 'TEST_SET_NOT_FOUND',
  
  // 配置管理
  CONFIG_VALIDATION_FAILED: 'CONFIG_VALIDATION_FAILED',
  CONFIG_CONFLICT: 'CONFIG_CONFLICT',
} as const;

export type ErrorCode = typeof ErrorCodes[keyof typeof ErrorCodes];

// 错误码与用户提示的映射（可覆盖后端默认提示）
export const ErrorMessageMap: Partial<Record<ErrorCode, string>> = {
  [ErrorCodes.UNAUTHORIZED]: '登录已过期，请重新登录',
  [ErrorCodes.INTERNAL_ERROR]: '系统繁忙，请稍后重试',
};
```

### 7.3 业务层调用改造

**改造前**：
```typescript
const response = await apiClient.get(`/rag/test/cases/${id}`);
const data = response.data;  // 需要自行判断结构
```

**改造后**：
```typescript
const data = await apiClient.get(`/rag/test/cases/${id}`);  // 拦截器已解包 data
// data 直接是业务数据
```

---

## 8. 特殊场景处理

### 8.1 SSE 流式响应

SSE 响应（如评估报告流式输出、测试进度推送）**不参与统一包装**，保持原有格式。

前端通过 `EventSource` 或 `fetch` + `ReadableStream` 处理。

### 8.2 文件下载

文件下载接口（如导出报告、下载文件）**不参与统一包装**，直接返回二进制流。

### 8.3 文件上传

文件上传接口返回统一格式：
```json
{
  "code": 0,
  "message": "文件已上传，正在后台处理",
  "data": {
    "task_id": "xxx",
    "filename": "xxx.pdf"
  }
}
```

---

## 10. 验收标准

### 10.1 实体类迁移验收

- [ ] `src/schemas/` 目录结构按规范创建完成
- [ ] 所有 `service/` 中的 `BaseModel` 已迁移至 `schemas/`
- [ ] 所有 `controller/` 中的 Request/Response DTO 已迁移至 `schemas/` 对应模块文件
- [ ] `src/service/`、`src/controller/`、`src/core/` 中无 `class xxx(BaseModel)` 定义
- [ ] 所有导入语句已更新为从 `src.schemas` 导入
- [ ] 原有功能回归测试通过

### 10.2 冗余代码消除验收

- [ ] `utils/db.py` 创建完成，26 处 Session 获取已替换
- [ ] `utils/response.py` 创建完成，100+ 处错误处理模板已替换
- [ ] `utils/serializers.py` 创建完成，30+ 处模型序列化已替换
- [ ] `utils/file_ops.py` 创建完成，70+ 处文件操作已替换
- [ ] `utils/time_utils.py` 创建完成，50+ 处时间处理已统一
- [ ] 无 `datetime.utcnow()` 调用（全部替换为 `utc_now()`）
- [ ] 原有功能回归测试通过

### 10.10 兼容性验收

- [ ] `src/model/` 目录已重命名为 `src/schemas/`
- [ ] 无 `from src.model.` 引用残留
- [ ] `controller/`, `service/`, `utils/` 均有 `__init__.py`
- [ ] `config/__init__.py` 已拆分，行数 < 50
- [ ] 无循环导入（`config` 模块依赖链清晰）
- [ ] 函数内 import 仅保留循环依赖/懒加载场景
- [ ] 所有文件 import 分组符合 stdlib → third-party → local 规范
- [ ] `isort` 检查通过
- [ ] `ruff` F401/F811/E402 检查通过
- [ ] 原有功能回归测试通过

### 10.8 代码引用规范化验收

- [ ] 单类行数不超过 200 行（含空行和注释）
- [ ] P0 优先级类完成拆分（`RagTestManager`、`RetrievalService`）
- [ ] P1 优先级类完成拆分（`MetadataProcessor`、`DocumentIngestionService`、`IndexManagerService`）
- [ ] 每个类职责单一，无混合职责
- [ ] 使用门面模式对外提供统一 API
- [ ] 子服务通过依赖注入获取
- [ ] 原有功能回归测试通过

### 10.4 类拆分验收

- [ ] 所有新增接口必须使用 `APIResponse.success()` 返回
- [ ] 所有业务异常必须继承 `AppException`
- [ ] 全局异常处理器能捕获并格式化所有异常类型
- [ ] 错误码文档完整覆盖所有业务场景
- [ ] 错误信息统一使用中文
- [ ] SSE 和文件下载接口不受影响

### 10.7 前端架构重构验收

- [ ] 目录结构按 FSD Lite 规范重组完成
- [ ] 无 `components/` 与 `features/*/components/` 并存
- [ ] 所有 Page 组件展示与逻辑分离（hook + 展示组件）
- [ ] `configStore.ts` 已拆分（369→4 个文件）
- [ ] 无页面直接调用 `apiClient.get/post`
- [ ] 95+ 处 `message.*` 调用已替换为 `handleApiCall`
- [ ] SSE 实现统一为单一 hook
- [ ] 类型定义无循环 re-export
- [ ] 原有功能回归测试通过

### 10.8 后端验收

- [ ] 请求拦截器自动解包 `data` 字段
- [ ] 业务错误自动弹出全局提示（可配置静默）
- [ ] 网络错误有友好提示
- [ ] 业务层可通过 `errorCode` 做特殊逻辑处理
- [ ] 现有业务功能不受影响

### 10.9 后端验收

- [ ] Phase 1 完成后，新旧接口可并存
- [ ] HTTPException 能被异常处理器正确映射
- [ ] 前端能同时处理新旧两种响应格式（过渡期）

---

## 11. 实施计划

### Phase 0：实体类迁移（预计 2-3 天）

| 任务 | 负责人 | 状态 |
|------|--------|------|
| 创建 `src/schemas/` 目录结构 | | ⬜ |
| 迁移 `service/` 中的实体类 | | ⬜ |
| 迁移 `controller/` 中的 DTO | | ⬜ |
| 迁移 `core/` 中的配置模型 | | ⬜ |
| 整理 `model/` 与 `models/` | | ⬜ |
| 更新所有导入语句 | | ⬜ |
| 运行全量测试验证 | | ⬜ |

### Phase 0.05：前端架构重构（预计 5-7 天）

| 任务 | 负责人 | 状态 |
|------|--------|------|
| 创建 FSD Lite 目录结构 | | ⬜ |
| 迁移孤儿页面至 `features/` | | ⬜ |
| 统一组件位置（`components/` → `features/*/components/`） | | ⬜ |
| 拆分 `configStore.ts`（369→4 个文件） | | ⬜ |
| 提取 `handleApiCall` 工具函数 | | ⬜ |
| 统一 SSE 实现 | | ⬜ |
| 消除类型循环 re-export | | ⬜ |
| 为所有 Page 组件创建对应 hooks | | ⬜ |
| 添加 ESLint 路径限制规则 | | ⬜ |
| 运行全量测试验证 | | ⬜ |

### Phase 0.1：代码引用规范化（预计 2-3 天）

| 任务 | 负责人 | 状态 |
|------|--------|------|
| 重命名 `src/model/` → `src/schemas/` | | ⬜ |
| 更新 31 处 `src.model.` 引用 | | ⬜ |
| 创建 `controller/__init__.py` | | ⬜ |
| 创建 `service/__init__.py` | | ⬜ |
| 创建 `utils/__init__.py` | | ⬜ |
| 拆分 `config/__init__.py`（614→4 个文件） | | ⬜ |
| 解决 `config` 循环导入 | | ⬜ |
| 消除函数内冗余 import（364→合理数量） | | ⬜ |
| 运行 `isort` 格式化全部文件 | | ⬜ |
| 运行全量测试验证 | | ⬜ |

### Phase 0.25：冗余代码消除（预计 3-4 天）

| 任务 | 负责人 | 状态 |
|------|--------|------|
| 创建 `utils/db.py`（Session 管理） | | ⬜ |
| 创建 `utils/response.py`（错误处理） | | ⬜ |
| 创建 `utils/serializers.py`（模型序列化） | | ⬜ |
| 创建 `utils/file_ops.py`（文件操作） | | ⬜ |
| 创建 `utils/time_utils.py`（时间处理） | | ⬜ |
| 创建其他工具模块（crypto/id_generator/auth） | | ⬜ |
| 替换所有重复代码为新工具函数 | | ⬜ |
| 运行全量测试验证 | | ⬜ |

### Phase 0.5：类职责拆分（预计 5-7 天）

| 任务 | 负责人 | 状态 |
|------|--------|------|
| 拆分 `RagTestManager`（1799→8 个类） | | ⬜ |
| 拆分 `RetrievalService`（1060→5 个类） | | ⬜ |
| 拆分 `MetadataProcessor`（925→7 个类） | | ⬜ |
| 拆分 `DocumentIngestionService`（637→5 个类） | | ⬜ |
| 拆分 `IndexManagerService`（574→4 个类） | | ⬜ |
| 拆分其他 P2/P3 类 | | ⬜ |
| 运行全量测试验证 | | ⬜ |

### Phase 1：基础设施（预计 2-3 天）

| 任务 | 负责人 | 状态 |
|------|--------|------|
| 创建 `APIResponse` 响应模型 | | ⬜ |
| 创建 `BusinessException` 异常体系 | | ⬜ |
| 创建全局异常处理器 | | ⬜ |
| 注册异常处理器到 FastAPI | | ⬜ |
| 创建前端错误码映射表 | | ⬜ |
| 改造前端请求拦截器 | | ⬜ |
| 编写单元测试 | | ⬜ |

### Phase 2：核心接口改造（预计 3-4 天）

| 任务 | 负责人 | 状态 |
|------|--------|------|
| 改造评估模块接口 | | ⬜ |
| 改造 RAG 知识库接口 | | ⬜ |
| 改造 RAG 搜索接口 | | ⬜ |
| 前端适配新响应格式 | | ⬜ |
| 功能回归测试 | | ⬜ |

### Phase 3：全量改造（预计 4-5 天）

| 任务 | 负责人 | 状态 |
|------|--------|------|
| 改造 RAG 测试模块 | | ⬜ |
| 改造配置管理模块 | | ⬜ |
| 改造提示词管理模块 | | ⬜ |
| 改造监控模块 | | ⬜ |
| 移除所有 HTTPException | | ⬜ |
| 全量回归测试 | | ⬜ |

---

## 12. 风险与注意事项

### 12.1 风险

1. **过渡期兼容性**：新旧接口并存期间，前端需同时处理两种响应格式
2. **SSE/文件下载误包装**：中间件需正确识别并跳过特殊响应类型
3. **错误码遗漏**：初期可能无法覆盖所有业务场景，需持续补充
4. **实体类迁移影响范围大**：约 130+ 个实体类需要迁移，涉及 20+ 文件的导入更新，需确保测试覆盖
5. **类拆分风险高**：超长类拆分涉及内部调用链重构，需充分测试覆盖，避免引入回归 bug
6. **代码引用规范化风险**：`model/` → `schemas/` 重命名影响 31 处引用，需确保无遗漏；循环导入解决可能暴露隐藏依赖
7. **前端架构重构风险**：FSD Lite 目录重组影响所有前端文件，需按 feature 逐步迁移，每迁移一个都需验证功能
8. **工具函数替换风险**：280+ 处重复代码替换需逐步进行，每替换一处都需运行测试验证

### 12.2 注意事项

1. **HTTP 状态码策略**：保持 HTTP 语义（200/4xx/5xx），业务错误码 `code` + `error_code` 双字段用于机器判断和国际化
2. **日志记录**：异常处理器需记录完整堆栈，便于排查问题
3. **国际化预留**：`error_code` 字段用于前端 i18n 映射，`message` 字段当前为中文
4. **Trace ID**：建议在请求中间件生成 `trace_id` 并注入响应，便于全链路追踪
5. **实体类迁移顺序**：先迁移 `service/` 和 `core/` 中的领域模型，再迁移 `controller/` 中的 DTO，最后统一更新导入
6. **循环依赖预防**：实体类抽离后，注意 `schemas/` 各模块文件之间不要产生循环导入，必要时使用 `TYPE_CHECKING`
7. **过渡期兼容**：`HTTPException` 处理器作为过渡期兼容，最终目标是全部替换为 `AppException`
8. **Import 分组工具化**：使用 `isort` 自动格式化，但需人工审查循环依赖场景的延迟导入是否合理
9. **FSD 依赖规则**：使用 ESLint `no-restricted-imports` 强制分层依赖，禁止跨层或反向依赖

---

## 13. 附录

### 13.1 现有接口响应格式统计

| 接口 | 当前返回格式 | 改造优先级 |
|------|-------------|-----------|
| `POST /assess` | 直接返回报告或 StreamingResponse | P0 |
| `POST /rag/upload` | `{"status": "accepted", "task_id": "..."}` | P0 |
| `GET /rag/search` | `{"status": "success", "total": N, "results": [...]}` | P0 |
| `GET /rag/documents` | `{"documents": [...]}` | P1 |
| `POST /rag/test/run` | 直接返回运行结果 | P1 |
| `GET /rag/config/metadata` | Pydantic response_model | P1 |
| `GET /api/v1/prompts` | Pydantic response_model | P2 |
| `GET /api/v1/monitoring/*` | 直接返回数据 | P2 |

### 13.2 参考项目

- 阿里巴巴 Java 开发手册 - 统一响应格式规范
- FastAPI 官方文档 - 异常处理最佳实践
- Axios 官方文档 - 拦截器使用指南
