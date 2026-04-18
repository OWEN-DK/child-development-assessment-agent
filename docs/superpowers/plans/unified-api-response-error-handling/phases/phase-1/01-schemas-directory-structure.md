# Phase 1-1: schemas 目录结构创建

> **需求来源**: spec 文档 `unified-api-response-and-error-handling.md` 中 `2.2 目标目录结构` 节
> **所属 Phase**: Phase 1

## 需求定义

创建 `backend/src/schemas/` 目录，按业务模块组织所有 Pydantic 实体类。当前 `schemas/` 目录不存在，所有 136 个 BaseModel 散落在 controller(55)/model(37)/models(14)/service(7)/core(10)/config(10) 中。

## 验收标准

- [ ] `backend/src/schemas/` 目录创建
- [ ] 8 个模块文件创建：`__init__.py`, `common.py`, `assessment.py`, `rag.py`, `test_case.py`, `config.py`, `prompt.py`, `monitoring.py`, `events.py`
- [ ] 每个文件包含对应模块的实体类占位注释

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `backend/src/schemas/` | 新增目录 | 统一实体类目录 |
| `backend/src/schemas/__init__.py` | 新增 | 统一导出入口 |
| `backend/src/schemas/common.py` | 新增 | 通用模型（APIResponse、分页、基础异常等） |
| `backend/src/schemas/assessment.py` | 新增 | 评估模块所有模型 |
| `backend/src/schemas/rag.py` | 新增 | RAG 模块所有模型 |
| `backend/src/schemas/test_case.py` | 新增 | 测试模块所有模型 |
| `backend/src/schemas/config.py` | 新增 | 配置模块所有模型 |
| `backend/src/schemas/prompt.py` | 新增 | 提示词模块所有模型 |
| `backend/src/schemas/monitoring.py` | 新增 | 监控模块所有模型 |
| `backend/src/schemas/events.py` | 新增 | SSE 事件模型 |

## 实现方案

### 目录结构

```
backend/src/schemas/
├── __init__.py              # 统一导出入口
├── common.py                # 通用模型（APIResponse、分页、基础异常等）
├── assessment.py            # 评估模块（ChildProfile, UserInput, AgentState, FinalReport 等）
├── rag.py                   # RAG 模块（DocumentMetadata, SourceDocument 等）
├── test_case.py             # 测试模块（TestCase, TestSet, TestRun, Draft 等）
├── config.py                # 配置模块（LLMProviderConfig, ConfigSaveRequest 等）
├── prompt.py                # 提示词模块（PromptVersionResponse, ImpactAnalysisResult 等）
├── monitoring.py            # 监控模块（TraceMetadata, MetricData 等）
└── events.py                # SSE 事件模型（RunStartedEvent, ProgressEvent 等）
```

### 分类规则

| 模块文件 | 来源目录 | 包含实体类 |
|---------|---------|-----------|
| `common.py` | 新建 | APIResponse, PaginatedResponse, HealthResponse |
| `assessment.py` | `model/schemas.py` | ChildProfile, Activity, ProposedPlan, UserInput, ChildState, FinalReport, AgentState 等 14 个 |
| `rag.py` | `model/document.py`, `service/retrieval_service.py` | DocumentMetadata, DocumentRecord, SynonymExpansionResult 等 |
| `test_case.py` | `model/rag_test.py`, `controller/rag_test_controller.py`, `models/test_case.py` | TestCase, TestSet, TestRun, TestCaseDraft, CreateTestCaseRequest 等 30+ 个 |
| `config.py` | `controller/config_controller.py`, `controller/config_management_controller.py`, `core/age_filter.py`, `config/modules/models/` | ConfigSaveRequest, LLMProviderConfig, AgeFilterConfig 等 20+ 个 |
| `prompt.py` | `controller/prompt_controller.py`, `controller/prompt_management_controller.py`, `service/prompt_impact_analyzer.py` | CreateVersionRequest, ImpactAnalysisResult 等 15+ 个 |
| `monitoring.py` | `controller/monitoring_controller.py`, `core/tracing/schemas.py` | TraceMetadata 等 |
| `events.py` | `models/sse_events.py` | RunStartedEvent, ProgressEvent, HeartbeatEvent 等 14 个 |

## 测试方案

1. 验证目录结构正确创建
2. 验证每个文件可被 Python import（无语法错误）
3. 验证 `__init__.py` 导出路径正确

## 注意事项

- 本步骤仅创建目录结构和文件骨架，实体类迁移在后续需求点执行
- 文件内容先写入模块 docstring 和占位注释
- 遵循 CLAUDE.md 规范：代码注释全中文
