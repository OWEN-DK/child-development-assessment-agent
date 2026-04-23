# RAG 评估系统统一 API 路由表

**文档版本**: v1.0  
**创建日期**: 2026-04-18  
**状态**: ✅ 已统一，解决 08/10/11 文档路径重叠问题

---

## 一、路由设计原则

| 原则 | 说明 |
|------|------|
| **RESTful 风格** | 资源名复数形式，HTTP 方法表达操作语义 |
| **路径唯一** | 每个端点路径唯一，不重叠 |
| **前缀统一** | 所有 RAG 评估 API 使用 `/api/v1/rag-eval` 前缀 |
| **嵌套合理** | 子资源通过父资源路径嵌套（如 `/reports/{id}/suggestions`） |

---

## 二、完整 API 路由表

### 2.1 测试报告 (TestReport)

| 方法 | 路径 | 说明 | 请求参数 | 响应格式 | 来源文档 |
|------|------|------|----------|----------|----------|
| GET | `/api/v1/rag-eval/reports` | 分页查询报告列表 | `test_run_id?`, `page=1`, `page_size=20` | `APIResponse.success(PaginatedResponse)` | 08-1, 10 |
| GET | `/api/v1/rag-eval/reports/{report_id}` | 获取报告详情 | - | `APIResponse.success(TestReportResponse)` | 08-1, 10 |
| POST | `/api/v1/rag-eval/reports` | 创建报告（内部调用） | `TestReportCreate` | `APIResponse.success(TestReportResponse)` | 08-1 |
| DELETE | `/api/v1/rag-eval/reports/{report_id}` | 删除报告 | - | `APIResponse.success()` | 08-1 |
| GET | `/api/v1/rag-eval/reports/{report_id}/validation/{layer}` | 获取单层校验详情 | `layer`: layer1_rules/layer2_history/... | `APIResponse.success(ValidationLayerResult)` | 10 |
| GET | `/api/v1/rag-eval/reports/{report_id}/suggestions` | 获取报告的调优建议列表 | `status?`: pending/applied/ignored | `APIResponse.success(List[TuningSuggestionResponse])` | 10 |
| POST | `/api/v1/rag-eval/reports/{report_id}/export` | 异步导出报告 | `{format: "pdf/json", include_validation: true}` | `APIResponse.success({task_id, status})` | 10 |

### 2.2 调优建议 (TuningSuggestion)

| 方法 | 路径 | 说明 | 请求参数 | 响应格式 | 来源文档 |
|------|------|------|----------|----------|----------|
| PUT | `/api/v1/rag-eval/suggestions/{suggestion_id}/status` | 更新建议状态 | `{status: "applied/ignored", ignore_reason?}` | `APIResponse.success(TuningSuggestionResponse)` | 08-2, 10 |
| POST | `/api/v1/rag-eval/suggestions/{suggestion_id}/apply` | 应用建议 | - | `APIResponse.success(result)` | 08-2 |
| PATCH | `/api/v1/rag-eval/suggestions/batch-update` | 批量更新建议状态 | `{ids: [...], status: "applied/ignored"}` | `APIResponse.success({updated_count: int})` | 10 |
| GET | `/api/v1/rag-eval/suggestions/stats` | 获取建议统计 | `report_id?` | `APIResponse.success({pending, applied, ignored})` | 10 |

### 2.3 意图标注 (IntentAnnotation)

| 方法 | 路径 | 说明 | 请求参数 | 响应格式 | 来源文档 |
|------|------|------|----------|----------|----------|
| GET | `/api/v1/rag-eval/intent-annotations` | 分页查询标注列表 | `intent?`, `query?`, `source?`, `page`, `page_size` | `APIResponse.success(PaginatedResponse)` | 08-3 |
| GET | `/api/v1/rag-eval/intent-annotations/{annotation_id}` | 获取标注详情 | - | `APIResponse.success(IntentAnnotationResponse)` | 08-3 |
| POST | `/api/v1/rag-eval/intent-annotations` | 创建标注 | `IntentAnnotationCreate` | `APIResponse.success(IntentAnnotationResponse)` | 08-3 |
| PUT | `/api/v1/rag-eval/intent-annotations/{annotation_id}` | 更新标注 | `IntentAnnotationUpdate` | `APIResponse.success(IntentAnnotationResponse)` | 08-3 |
| DELETE | `/api/v1/rag-eval/intent-annotations/{annotation_id}` | 删除标注 | - | `APIResponse.success()` | 08-3 |
| POST | `/api/v1/rag-eval/intent-annotations/batch-import` | 批量导入标注 | `List[IntentAnnotationCreate]` | `APIResponse.success({count})` | 08-3 |

### 2.4 趋势与对比 (Trends & Comparison)

| 方法 | 路径 | 说明 | 请求参数 | 响应格式 | 来源文档 |
|------|------|------|----------|----------|----------|
| GET | `/api/v1/rag-eval/reports/trends` | 获取趋势数据 | `test_set_id`, `from`, `to`, `metrics[]` | `APIResponse.success({timestamps, series})` | 10 |
| GET | `/api/v1/rag-eval/reports/compare` | 对比两个版本报告 | `report_id_1`, `report_id_2` | `APIResponse.success({metrics_diff, config_diff})` | 10 |
| GET | `/api/v1/rag-eval/reports/config-history` | 查询配置变更历史 | `from`, `to`, `target_type?` | `APIResponse.success(List[AuditLogResponse])` | 10 |

### 2.5 导出任务 (Export Task)

| 方法 | 路径 | 说明 | 请求参数 | 响应格式 | 来源文档 |
|------|------|------|----------|----------|----------|
| GET | `/api/v1/rag-eval/reports/exports/{task_id}/status` | 查询导出任务状态 | - | `APIResponse.success({status, download_url?})` | 10 |
| GET | `/api/v1/rag-eval/reports/exports/{task_id}/download` | 下载导出文件 | - | 文件流（PDF/JSON） | 10 |

### 2.6 版本管理与回滚 (Version & Rollback)

| 方法 | 路径 | 说明 | 请求参数 | 响应格式 | 来源文档 |
|------|------|------|----------|----------|----------|
| GET | `/api/v1/rag-eval/configs/{key}/versions` | 获取配置版本列表 | `page`, `page_size` | `APIResponse.success(PaginatedResponse)` | 11 |
| GET | `/api/v1/rag-eval/configs/{key}/versions/{version}/diff` | 对比配置版本差异 | `compare_with?` | `APIResponse.success({before, after, diff})` | 11 |
| POST | `/api/v1/rag-eval/configs/{key}/versions/{version}/rollback` | 回滚配置到指定版本 | `{confirmed: true, reason}` | `APIResponse.success({new_version})` | 11 |
| GET | `/api/v1/rag-eval/prompts/{key}/versions` | 获取提示词版本列表 | `page`, `page_size` | `APIResponse.success(PaginatedResponse)` | 11 |
| POST | `/api/v1/rag-eval/prompts/{key}/versions/{version}/rollback` | 回滚提示词到指定版本 | `{confirmed: true, reason}` | `APIResponse.success({new_version})` | 11 |

### 2.7 影响分析 (Impact Analysis)

| 方法 | 路径 | 说明 | 请求参数 | 响应格式 | 来源文档 |
|------|------|------|----------|----------|----------|
| POST | `/api/v1/rag-eval/configs/{key}/preview-impact` | 预览配置变更影响 | `{proposed_value}` | `APIResponse.success({affected_test_sets, expected_metrics_change})` | 11 |
| POST | `/api/v1/rag-eval/prompts/{key}/preview-impact` | 预览提示词变更影响 | `{proposed_content, variables}` | `APIResponse.success({affected_test_sets, expected_metrics_change})` | 11 |
| GET | `/api/v1/rag-eval/configs/{key}/impact-history` | 查询历史影响记录 | `from`, `to` | `APIResponse.success(List[{version, change_summary, actual_impact}])` | 11 |

### 2.8 审计日志 (AuditLog)

| 方法 | 路径 | 说明 | 请求参数 | 响应格式 | 来源文档 |
|------|------|------|----------|----------|----------|
| GET | `/api/v1/rag-eval/audit-logs` | 查询审计日志列表 | `operator?`, `action?`, `target_type?`, `target_id?`, `from`, `to`, `page`, `page_size` | `APIResponse.success(PaginatedResponse)` | 11 |
| GET | `/api/v1/rag-eval/audit-logs/{log_id}` | 获取审计日志详情 | - | `APIResponse.success(AuditLogResponse)` | 11 |
| GET | `/api/v1/rag-eval/audit-logs/target/{target_type}/{target_id}` | 查询特定目标变更历史 | - | `APIResponse.success(List[AuditLogResponse])` | 11 |

---

## 三、路径冲突解决记录

| 冲突路径 | 解决方案 | 影响文档 |
|----------|----------|----------|
| `08: /api/v1/suggestions` vs `10: /api/v1/reports/{id}/suggestions` | 统一使用 `/api/v1/rag-eval/suggestions` 作为独立资源，报告下的建议通过 `/api/v1/rag-eval/reports/{report_id}/suggestions` 访问 | 08-2, 10 |
| `08: /api/v1/reports` vs `10: /api/v1/reports/{id}/validation/{layer}` | 统一前缀为 `/api/v1/rag-eval/reports`，所有报告相关端点在此前缀下 | 08-1, 10 |
| `08: /api/v1/intent-annotations` vs `10: 未定义` | 统一使用 `/api/v1/rag-eval/intent-annotations` | 08-3 |
| `11: /api/v1/configs/{key}/versions` vs 配置系统原有路由 | 统一使用 `/api/v1/rag-eval/configs` 前缀，与配置管理系统隔离 | 11, 06 |

---

## 四、错误码规范

| 错误码 (code) | 错误标识 (error_code) | HTTP 状态 | 说明 |
|---------------|----------------------|-----------|------|
| 40401 | REPORT_NOT_FOUND | 404 | 报告不存在 |
| 40402 | SUGGESTION_NOT_FOUND | 404 | 建议不存在 |
| 40403 | ANNOTATION_NOT_FOUND | 404 | 标注不存在 |
| 40404 | AUDIT_LOG_NOT_FOUND | 404 | 审计日志不存在 |
| 40001 | IGNORE_REASON_REQUIRED | 400 | 忽略原因不能为空 |
| 40002 | SUGGESTION_NOT_PENDING | 400 | 建议状态不是待处理 |
| 40003 | DATA_SUGGESTION_MANUAL_ONLY | 400 | 数据类建议需手动处理 |
| 50001 | VALIDATION_ENGINE_ERROR | 500 | 校验引擎执行失败 |
| 50002 | EXPORT_TASK_FAILED | 500 | 导出任务失败 |

---

## 五、实施检查清单

- [ ] 所有 API 端点路径已统一，无重叠
- [ ] 所有响应使用 `APIResponse.success()` 包装
- [ ] 所有异常使用 `AppException` 及其子类
- [ ] 错误码符合双字段规范（code + error_code）
- [ ] 所有路径使用 `/api/v1/rag-eval` 前缀
- [ ] 08-1/08-2/08-3 文档已同步更新
- [ ] 10/11 文档 API 路径已对齐

---

**文档状态**: ✅ 已完成统一，可指导实施
