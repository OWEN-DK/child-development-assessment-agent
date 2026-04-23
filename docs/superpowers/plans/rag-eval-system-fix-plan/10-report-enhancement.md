# 10 - 评估报告高级功能模块
**优先级**：🟢 P2
**工作量**：72h（9 人天）
**依赖**：09-validation-engine（校验引擎）、08-data-model-enhancement（数据模型）
---
## 一、需求背景
现有报告页面仅展示基础指标，缺少 6 层校验结果展示、调优建议交互、趋势追踪等核心功能，无法支撑报告驱动调优的设计目标。

## 二、后端 API 设计

**注意**：本模块扩展自 `08-data-model-enhancement.md` 第 4 章定义的 API。
- `08-data-model-enhancement.md` 定义了基础 CRUD API（TestReport、TuningSuggestion、IntentAnnotation）
- 本模块定义高级功能 API（趋势查询、版本对比、异步导出等）
- 两处 API 定义互补，不冲突

### 2.0 报告查询 API（扩展）

| 方法 | 路径 | 说明 | 请求参数 | 响应格式 |
|------|------|------|----------|----------|
| GET | `/api/v1/reports/{id}` | 获取报告详情（含 6 层校验结果） | - | `APIResponse.success(TestReportResponse)` |
| GET | `/api/v1/reports?test_run_id=xxx` | 按测试运行查询报告 | `test_run_id` | `APIResponse.success(List[TestReportResponse])` |
| GET | `/api/v1/reports?from=xxx&to=xxx&page=1&page_size=20` | 按时间范围查询报告列表 | `from`, `to`, `page`, `page_size` | `APIResponse.success(PaginatedResponse)` |
| GET | `/api/v1/reports/{id}/validation/{layer}` | 获取单层校验详情 | `layer`: layer1_rules/layer2_history/... | `APIResponse.success(ValidationLayerResult)` |

### 2.1 调优建议 API

| 方法 | 路径 | 说明 | 请求参数 | 响应格式 |
|------|------|------|----------|----------|
| GET | `/api/v1/reports/{report_id}/suggestions` | 获取报告的调优建议列表 | `status`: pending/applied/ignored（可选） | `APIResponse.success(List[TuningSuggestionRecordResponse])` |
| PATCH | `/api/v1/suggestions/{id}` | 更新建议状态（采纳/忽略） | `{status: "applied/ignored", applied_by: "用户名"}` | `APIResponse.success(TuningSuggestionRecordResponse)` |
| POST | `/api/v1/suggestions/batch-update` | 批量更新建议状态 | `{ids: [...], status: "applied/ignored", applied_by: "用户名"}` | `APIResponse.success({updated_count: int})` |
| GET | `/api/v1/suggestions/stats` | 获取建议统计 | `report_id`（可选） | `APIResponse.success({pending: int, applied: int, ignored: int})` |

### 2.2 趋势数据 API

| 方法 | 路径 | 说明 | 请求参数 | 响应格式 |
|------|------|------|----------|----------|
| GET | `/api/v1/reports/trends` | 获取趋势数据（指标时间序列） | `test_set_id`, `from`, `to`, `metrics`: ["precision_at_5", "f1_score", ...] | `APIResponse.success({timestamps: [...], series: {metric_name: [...]}})` |
| GET | `/api/v1/reports/compare` | 对比两个版本的报告 | `report_id_1`, `report_id_2` | `APIResponse.success({metrics_diff: {...}, config_diff: {...}, suggestions_diff: {...}})` |
| GET | `/api/v1/reports/config-history` | 查询配置变更历史 | `from`, `to`, `target_type`: config/prompt | `APIResponse.success(List[AuditLogResponse])` |

### 2.3 报告导出 API

| 方法 | 路径 | 说明 | 请求参数 | 响应格式 |
|------|------|------|----------|----------|
| POST | `/api/v1/reports/{id}/export` | 异步导出报告（触发后台任务） | `{format: "pdf/json", include_validation: true, include_suggestions: true}` | `APIResponse.success({task_id: "xxx", status: "processing"})` |
| GET | `/api/v1/reports/exports/{task_id}/status` | 查询导出任务状态 | - | `APIResponse.success({status: "processing/completed/failed", download_url: "..."})` |
| GET | `/api/v1/reports/exports/{task_id}/download` | 下载导出文件 | - | 文件流（PDF/JSON） |

---

## 三、实施步骤

### 3.1 6 层校验结果展示
**文件路径**：`frontend/src/features/rag-eval/components/ValidationResult/`
- 每层结果独立 Tab 页展示
- 支持按问题类型、严重程度筛选
- 问题详情卡片展示：原因、影响、优化建议、前后对比
- 建议操作按钮：采纳/忽略/详情

### 3.2 调优建议面板
**文件路径**：`frontend/src/features/rag-eval/components/SuggestionPanel/`
- 建议列表展示，按优先级排序
- 采纳建议自动跳转对应配置/提示词编辑页面，自动填充建议值
- 支持批量采纳/忽略建议
- 支持查看已处理建议历史

### 3.3 趋势追踪页面
**文件路径**：`frontend/src/features/rag-eval/pages/TrendPage.tsx`
- 历史运行指标趋势图（折线图，支持多指标对比）
- 配置/提示词变更标记与指标变化关联展示
- 版本对比功能：选择两个版本查看指标差异和配置变更
- 支持按测试集、时间范围筛选

### 3.4 报告导出功能
**文件路径**：`frontend/src/features/rag-eval/utils/export.ts`
- 支持导出完整报告为 PDF 格式（包含指标、校验结果、建议）
- 支持导出原始数据为 JSON 格式
- 导出文件包含版本、时间、测试集信息
- **异步导出模式**：大报告导出使用后台任务 + SSE 推送进度，避免 HTTP 超时

## 四、交互规范
严格遵循核心流程：
```
查看问题 → 查看前后对比 → 查看影响分析 → 手动确认采纳 → 保存为新版本
```
禁止自动应用任何建议，所有修改必须用户手动确认。

## 五、验收标准
- [ ] 6层校验结果清晰展示，支持筛选和详情查看
- [ ] 调优建议操作流程符合三步确认原则，无自动应用
- [ ] 趋势图可直观查看指标变化与版本关联，支持对比分析
- [ ] 报告导出功能正常，文件内容完整格式正确
- [ ] 页面响应时间<2s，无明显卡顿
---
**注意**：遵循零迁移原则，直接替换原有报告页面，不保留旧版本
