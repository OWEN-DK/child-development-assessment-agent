# 11 - API 契约与错误码

## 路由设计

统一前缀：`/rag/eval/`

### 草稿管理

| 端点 | 方法 | 功能 | 请求体 | 响应 |
|------|------|------|--------|------|
| `/rag/eval/source-documents/upload` | POST | 上传+生成草稿 | multipart/form-data | `APIResponse[SourceDocumentRead]` |
| `/rag/eval/source-documents` | GET | 列出源文档 | Query: page, page_size | `APIResponse[List[SourceDocumentRead]]` |
| `/rag/eval/source-documents/{id}` | GET | 获取源文档 | - | `APIResponse[SourceDocumentRead]` |
| `/rag/eval/source-documents/{id}` | DELETE | 删除源文档 | - | `APIResponse[None]` |
| `/rag/eval/drafts` | GET | 列出草稿 | Query: page, page_size, status, domain | `APIResponse[DraftList]` |
| `/rag/eval/drafts/{id}` | GET | 获取草稿 | - | `APIResponse[DraftRead]` |
| `/rag/eval/drafts/{id}` | PUT | 更新草稿 | `DraftUpdate` | `APIResponse[DraftRead]` |
| `/rag/eval/drafts/{id}/review` | POST | 审核草稿 | `DraftReview` | `APIResponse[TestCaseRead]` |
| `/rag/eval/drafts/batch-import` | POST | 批量导入 | `{draft_ids: List[str]}` | `APIResponse[List[TestCaseRead]]` |
| `/rag/eval/drafts/batch` | DELETE | 批量删除 | `{draft_ids: List[str]}` | `APIResponse[None]` |
| `/rag/eval/drafts/generation/{task_id}/stream` | GET | SSE 生成进度 | - | SSE EventStream |

### 测试用例与测试集

| 端点 | 方法 | 功能 |
|------|------|------|
| `/rag/eval/test-cases` | GET | 列出测试用例 (page, page_size, domain) |
| `/rag/eval/test-cases` | POST | 创建测试用例 |
| `/rag/eval/test-cases/{id}` | GET/PUT/DELETE | CRUD |
| `/rag/eval/test-cases/batch` | DELETE | 批量删除 |
| `/rag/eval/test-cases/import` | POST | 导入 JSON 测试用例 |
| `/rag/eval/test-sets` | GET/POST | 列出/创建测试集 |
| `/rag/eval/test-sets/{id}` | GET/PUT/DELETE | CRUD |
| `/rag/eval/test-sets/{id}/cases` | POST | 添加用例 |
| `/rag/eval/test-sets/{id}/cases` | DELETE | 移除用例 |
| `/rag/eval/test-sets/{id}/export` | GET | 导出 JSON |

### 测试运行

| 端点 | 方法 | 功能 |
|------|------|------|
| `/rag/eval/runs` | POST | 创建并执行 |
| `/rag/eval/runs` | GET | 列出运行 (status, test_set_ids) |
| `/rag/eval/runs/{id}` | GET/DELETE | 获取/删除 |
| `/rag/eval/runs/batch` | DELETE | 批量删除 |
| `/rag/eval/runs/{id}/execute/{case_id}` | POST | 执行单用例 |
| `/rag/eval/runs/{id}/stream` | GET | SSE 执行进度 |
| `/rag/eval/runs/compare` | GET | 比较两个运行 (run_id_1, run_id_2) |

### 指标与诊断（双轨）

| 端点 | 方法 | 功能 |
|------|------|------|
| `/rag/eval/runs/{id}/metrics` | GET | 获取三层指标 |
| `/rag/eval/runs/{id}/diagnosis` | GET | 获取六层诊断 |
| `/rag/eval/runs/{id}/evaluate` | POST | 触发双轨评估 |

### 报告

| 端点 | 方法 | 功能 |
|------|------|------|
| `/rag/eval/reports` | GET | 列出报告 (page, page_size) |
| `/rag/eval/reports/{id}` | GET | 获取报告详情 |
| `/rag/eval/reports/{id}/export` | GET | 导出 (format=pdf\|csv\|json) |
| `/rag/eval/trends` | GET | 获取趋势 (metric, limit) |

### 快照

| 端点 | 方法 | 功能 |
|------|------|------|
| `/rag/eval/snapshots` | POST | 创建快照 |
| `/rag/eval/snapshots` | GET | 列出快照 |
| `/rag/eval/snapshots/{id}` | GET | 获取快照 |
| `/rag/eval/snapshots/{id}/restore` | POST | 恢复快照 |

### 调优

| 端点 | 方法 | 功能 |
|------|------|------|
| `/rag/eval/runs/{id}/tuning` | GET | 获取调优建议 |
| `/rag/eval/tuning/{id}/adopt` | POST | 采纳建议 |
| `/rag/eval/tuning/{id}/reject` | POST | 拒绝建议 |
| `/rag/eval/tuning/{id}/ignore` | POST | 忽略建议 |
| `/rag/eval/config-versions` | GET | 列出配置版本 |
| `/rag/eval/config-versions/{id}/rollback` | POST | 回滚到指定版本 |

## 错误码

RAG 评估模块错误码范围：`13000-13999`

| 数字码 | 错误码标识 | HTTP | 含义 |
|--------|-----------|------|------|
| 13001 | `DRAFT_NOT_FOUND` | 404 | 草稿不存在 |
| 13002 | `TEST_CASE_NOT_FOUND` | 404 | 测试用例不存在 |
| 13003 | `TEST_SET_NOT_FOUND` | 404 | 测试集不存在 |
| 13004 | `TEST_RUN_NOT_FOUND` | 404 | 测试运行不存在 |
| 13005 | `SNAPSHOT_NOT_FOUND` | 404 | 快照不存在 |
| 13006 | `REPORT_NOT_FOUND` | 404 | 报告不存在 |
| 13007 | `TUNING_SUGGESTION_NOT_FOUND` | 404 | 调优建议不存在 |
| 13008 | `SOURCE_DOCUMENT_NOT_FOUND` | 404 | 源文档不存在 |
| 13009 | `CONFIG_VERSION_NOT_FOUND` | 404 | 配置版本不存在 |
| 13010 | `SNAPSHOT_RESTORE_FAILED` | 500 | 快照恢复失败 |
| 13011 | `DRAFT_GENERATION_FAILED` | 500 | 草稿生成失败 |
| 13012 | `TEST_EXECUTION_TIMEOUT` | 408 | 测试执行超时 |
| 13013 | `TEST_EXECUTION_FAILED` | 500 | 测试执行失败 |
| 13014 | `METRIC_CALCULATION_FAILED` | 500 | 指标计算失败 |
| 13015 | `DIAGNOSIS_FAILED` | 500 | 诊断执行失败 |
| 13016 | `INVALID_TEST_CASE_FORMAT` | 400 | 测试用例格式错误 |
| 13017 | `INVALID_IMPORT_DATA` | 400 | 导入数据格式错误 |
| 13018 | `DRAFT_ALREADY_REVIEWED` | 400 | 草稿已审核 |
| 13019 | `TEST_SET_EMPTY` | 400 | 测试集为空 |
| 13020 | `RUN_IN_PROGRESS` | 409 | 运行进行中 |
| 13021 | `METRIC_NOT_FOUND` | 404 | 指标计算器不存在 |
| 13022 | `REPORT_EXPORT_FAILED` | 500 | 报告导出失败 |
| 13023 | `LLM_SERVICE_UNAVAILABLE` | 503 | LLM 服务不可用 |
| 13024 | `CONFIG_ROLLBACK_FAILED` | 500 | 配置回滚失败 |
| 13025 | `SUGGESTION_CONFLICT` | 409 | 建议存在冲突 |
| 13026 | `RULE_CHECK_FAILED` | 500 | 规则检查引擎内部错误 |

## 配置 Key 命名规范

格式：`rag.eval.{模块}.{配置项}`

| 模块 | 示例 |
|------|------|
| `rag.eval.threshold.*` | 指标阈值 |
| `rag.eval.weight.*` | 指标权重 |
| `rag.eval.draft.*` | 草稿引擎 |
| `rag.eval.run.*` | 运行引擎 |
| `rag.eval.diagnosis.*` | 诊断引擎 |
| `rag.eval.tuning.*` | 调优引擎 |
| `rag.eval.report.*` | 报告引擎 |
