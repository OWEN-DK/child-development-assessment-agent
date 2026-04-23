# 11 - 调优交互功能完善模块
**优先级**：🟢 P2
**工作量**：32h（4 人天）
**依赖**：06-config-system-refactor、07-prompt-management-refactor、08-data-model-enhancement（审计日志模型）
---
## 一、需求背景
现有调优交互缺少对比展示、影响分析、回滚等核心功能，不符合需求文档要求的"禁止隐藏决策依据、禁止跳过对比环节、禁止省略影响分析"三大原则。

## 二、后端 API 设计

### 2.0 版本管理与回滚 API

| 方法 | 路径 | 说明 | 请求参数 | 响应格式 |
|------|------|------|----------|----------|
| GET | `/api/v1/configs/{key}/versions` | 获取配置版本列表 | `page`, `page_size` | `APIResponse.success(PaginatedResponse)` |
| GET | `/api/v1/configs/{key}/versions/{version}/diff` | 对比两个版本差异 | `compare_with`: version（与哪个版本对比） | `APIResponse.success({before: {...}, after: {...}, diff: {...}})` |
| POST | `/api/v1/configs/{key}/versions/{version}/rollback` | 回滚到指定版本 | `{confirmed: true, reason: "回滚原因"}` | `APIResponse.success({new_version: "vX", rolled_back_at: "..."})` |
| GET | `/api/v1/prompts/{key}/versions` | 获取提示词版本列表 | `page`, `page_size` | `APIResponse.success(PaginatedResponse)` |
| POST | `/api/v1/prompts/{key}/versions/{version}/rollback` | 回滚提示词到指定版本 | `{confirmed: true, reason: "回滚原因"}` | `APIResponse.success({new_version: "vX", rolled_back_at: "..."})` |

### 2.1 影响分析 API

| 方法 | 路径 | 说明 | 请求参数 | 响应格式 |
|------|------|------|----------|----------|
| POST | `/api/v1/configs/{key}/preview-impact` | 预览配置变更影响 | `{proposed_value: {...}}` | `APIResponse.success({affected_test_sets: [...], expected_metrics_change: {...}, risks: [...], historical_similar_changes: [...]})` |
| POST | `/api/v1/prompts/{key}/preview-impact` | 预览提示词变更影响 | `{proposed_content: "...", variables: {...}}` | `APIResponse.success({affected_test_sets: [...], expected_metrics_change: {...}, risks: [...], historical_similar_changes: [...]})` |
| GET | `/api/v1/configs/{key}/impact-history` | 查询历史影响记录 | `from`, `to` | `APIResponse.success(List[{version, change_summary, actual_impact}])` |

### 2.2 审计日志 API

| 方法 | 路径 | 说明 | 请求参数 | 响应格式 |
|------|------|------|----------|----------|
| GET | `/api/v1/audit-logs` | 查询审计日志列表 | `operator`, `action`, `target_type`, `target_id`, `from`, `to`, `page`, `page_size` | `APIResponse.success(PaginatedResponse)` |
| GET | `/api/v1/audit-logs/{id}` | 获取审计日志详情 | - | `APIResponse.success(AuditLogResponse)` |
| GET | `/api/v1/audit-logs/target/{target_type}/{target_id}` | 查询特定目标的变更历史 | - | `APIResponse.success(List[AuditLogResponse])` |

---

## 三、实施步骤

### 3.1 前后对比 Diff 展示
**文件路径**：`frontend/src/shared/ui/DiffViewer/`（修正：遵循 FSD 分层，放在 shared/ui）
- 配置变更 diff 展示：JSON 格式对比，高亮差异
- 提示词内容 diff 展示：文本格式对比，高亮增删改
- 指标预期变化对比：表格展示修改前后预期指标值
- 支持切换统一/分栏对比模式

### 3.2 影响分析预览
**文件路径**：`frontend/src/features/rag-eval/components/ImpactPreview/`
- 展示配置/提示词变更影响的测试集范围
- 展示预期指标提升预测值（基于历史数据）
- 展示风险提示（如可能导致的副作用、影响范围）
- 展示参考历史案例（如有同类修改记录）

### 3.3 回滚确认流程
**文件路径**：`frontend/src/features/rag-eval/components/RollbackConfirm/`
- 版本列表展示，包含版本号、修改时间、修改人、变更内容摘要
- 选择回滚版本后展示前后 diff 对比
- 二次确认流程：显示回滚影响范围，用户确认后执行
- 回滚成功后跳转对应页面，显示回滚结果

### 3.4 操作审计日志
**文件路径**：`backend/src/service/audit/`
- 记录所有配置/提示词变更操作（修改人、时间、前后值）
- 记录调优建议采纳/忽略操作
- 记录回滚操作
- 支持查询操作历史
- **数据模型**：使用 `08-data-model-enhancement.md` 中定义的 `AuditLog` 模型

## 四、核心原则遵循
所有交互严格符合需求文档要求：
✅ 禁止替用户做决策：所有修改必须用户手动确认
✅ 禁止隐藏决策依据：所有建议必须展示原因
✅ 禁止跳过对比环节：所有修改必须展示前后 diff
✅ 禁止省略影响分析：所有修改必须展示影响范围
✅ 支持回溯：所有修改留版本记录，可一键回滚

## 五、验收标准
- [ ] 所有变更操作都有前后diff对比展示，差异清晰
- [ ] 影响分析预览功能正常，准确展示变更影响范围和预期效果
- [ ] 版本回滚功能正常，操作简单可靠
- [ ] 所有操作都有审计日志记录，可追溯
- [ ] 交互流程符合核心原则，无自动应用、无隐藏逻辑
---
**注意**：A/B测试功能已完全删除，所有相关交互不保留
