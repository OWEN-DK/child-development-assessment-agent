# 实施计划：顺序、风险、验收

**文档版本**: v1.0  
**最后更新**: 2026-04-18  

---

## 一、实施顺序与时间估算

### 阶段 1：核心 Bug 修复（2.5h）

**目标**：修复阻断性 Bug，确保系统可正常运行

| 步骤 | 任务 | 文件 | 工作量 |
|------|------|------|--------|
| 1.1 | 修复 `config_health_service.py` 导入错误 | `backend/src/service/config_health_service.py` | 0.5h |
| 1.2 | 修复 LLM 工厂调用签名错误（9 个文件） | 见 [04-phase0-root-cause-fixes.md](./04-phase0-root-cause-fixes.md) | 1h |
| 1.3 | 修复 Phase 0 的 12 个根因 | 见 [04-phase0-root-cause-fixes.md](./04-phase0-root-cause-fixes.md) | 1h |

**验收**：
- [ ] 系统启动无报错
- [ ] LLM 调用正常（无 `TypeError`）
- [ ] 书籍导入正常
- [ ] 批量测试正常

---

### 阶段 2：RAG 流水线接入（6h）

**目标**：删除硬编码链路，直接接入声明式流水线

| 步骤 | 任务 | 文件 | 工作量 |
|------|------|------|--------|
| 2.1 | 删除硬编码链路，直接接入 `PipelineOrchestrator` | `backend/src/service/retrieval/facade.py` | 3h |
| 2.2 | 修改 `_classify_query()` 逻辑 | `backend/src/core/pipeline/orchestrator.py` | 1h |
| 2.3 | 补充监控日志 | `backend/src/core/pipeline/orchestrator.py` | 0.5h |
| 2.4 | 编写集成测试 | `backend/tests/test_pipeline_integration.py` | 1.5h |

**验收**：
- [ ] 请求走声明式流水线
- [ ] 硬编码链路代码已删除
- [ ] Pipeline 执行失败时抛出异常

**详细方案**：见 [01-p0-bug-fixes.md](./01-p0-bug-fixes.md)

---

### 阶段 3：提示词迁移（2h）

**目标**：消除绕过 `PromptManager` 的直接导入

| 步骤 | 任务 | 文件 | 工作量 |
|------|------|------|--------|
| 3.1 | 修改 3 处直接导入为 `prompt_manager.get_prompt()` | 见 [02-p1-prompt-migration.md](./02-p1-prompt-migration.md) | 1h |
| 3.2 | 调用处改为异步（`await`） | 3 处文件 | 0.5h |
| 3.3 | 验证降级逻辑（PromptManager 已内置） | - | 0.5h |

**验收**：
- [ ] 3 处文件不再直接导入 `prompts_fallback.py`
- [ ] 所有提示词通过 `await prompt_manager.get_prompt()` 加载
- [ ] 数据库故障时降级到 `prompts_fallback.py`

**详细方案**：见 [02-p1-prompt-migration.md](./02-p1-prompt-migration.md)

---

### 阶段 4：12 种认知维度矩阵（3h）

**目标**：实现多样化草稿生成

| 步骤 | 任务 | 文件 | 工作量 |
|------|------|------|--------|
| 4.1 | 实现 `TestCaseDraftGenerator` | `backend/src/service/rag_test/draft_generator.py` | 2h |
| 4.2 | 编写 50+ 提问角度模板 | `backend/src/service/rag_test/question_templates.json` | 0.5h |
| 4.3 | 实现去重机制 | `backend/src/service/rag_test/draft_generator.py` | 0.5h |

**验收**：
- [ ] 支持 12 种认知维度
- [ ] 生成 500 条用例时去重率 < 15%
- [ ] 单次生成耗时 < 60s

**详细方案**：见 [02-p1-prompt-migration.md](./02-p1-prompt-migration.md)

---

### 阶段 5：前端 Tab 重构（8h）

**目标**：重构为 Tab 聚合布局，实施工作流约束（前端 + 后端双重验证）

| 步骤 | 任务 | 文件 | 工作量 |
|------|------|------|--------|
| 5.1 | 新建 `RagEvalMainPage.tsx` 主布局 | `frontend/src/features/rag-eval/pages/RagEvalMainPage.tsx` | 1h |
| 5.2 | 重构草稿管理页 | `frontend/src/features/rag-eval/pages/DraftManagementPage.tsx` | 1.5h |
| 5.3 | 新建测试用例管理页 | `frontend/src/features/rag-eval/pages/TestCaseManagementPage.tsx` | 1h |
| 5.4 | 重构测试集管理页 | `frontend/src/features/rag-eval/pages/TestSetManagementPage.tsx` | 1.5h |
| 5.5 | 新建评估报告列表页 | `frontend/src/features/rag-eval/pages/ReportListPage.tsx` | 1h |
| 5.6 | **后端增加工作流约束验证** | `backend/src/service/rag_test/facade.py` | 2h |

**验收**：
- [ ] 四个 Tab 页面可正常切换
- [ ] 工作流约束严格（前端 + 后端双重验证）
- [ ] URL 与 Tab 状态同步
- [ ] 后端 API 拒绝非法操作（如直接创建用例）

**详细方案**：见 [03-frontend-tab-refactor.md](./03-frontend-tab-refactor.md)

---

### 阶段 6：配置系统重构（19h）
**目标**：消除重复混乱，实现配置热加载，复用现有EventBus，竞态保护，迁移备份
| 步骤 | 任务 | 文件 | 工作量 |
|------|------|------|--------|
| 6.1 | 重构配置三层架构，消除重复代码 | `backend/src/config/` | 4h |
| 6.2 | 实现配置热加载，订阅ConfigChangedEvent | `backend/src/core/config/` | 3h |
| 6.3 | 实现配置版本管理与回滚功能 | `backend/src/service/config/` | 2h |
| 6.4 | LLM服务热切换（竞态保护+版本号来源明确） | `backend/src/core/llm/factory.py` | 5h |
| 6.5 | 迁移脚本（带备份+验证+自动恢复） | `backend/src/config/core/migrate_categories.py` | 3h |
| 6.6 | 编写集成测试 | `backend/tests/test_config.py` | 2h |
**验收**：
- [ ] 配置修改后实时生效，无需重启
- [ ] 配置版本记录完整，支持回滚
- [ ] 无重复代码，架构清晰
**详细方案**：见 [06-config-system-refactor.md](./06-config-system-refactor.md)
---
### 阶段 7：提示词页面重构（6.5h）
**目标**：合并两套页面，删除A/B测试，实现三层编辑模式
| 步骤 | 任务 | 文件 | 工作量 |
|------|------|------|--------|
| 7.1 | 删除旧A/B测试页面与相关代码 | `frontend/src/features/prompts/` | 1h |
| 7.2 | 迁移路由到/prompt-management/*，修改参数为:key | `frontend/src/router/index.tsx` | 1h |
| 7.3 | 修正API端点路径与需求对齐 | `frontend/src/api/rag-eval/prompts.ts` | 1h |
| 7.4 | 实现三层编辑模式（推荐/向导/专家） | `frontend/src/features/rag-eval/pages/PromptEditPage.tsx` | 2h |
| 7.5 | 实现版本对比、回滚、测试沙箱功能 | `frontend/src/features/rag-eval/pages/` | 1.5h |
**验收**：
- [ ] 所有A/B测试代码已删除
- [ ] 三层编辑模式功能正常
- [ ] 提示词版本管理、回滚、测试功能正常
**详细方案**：见 [07-prompt-management-refactor.md](./07-prompt-management-refactor.md)
---
### 【新增】阶段 8：数据模型增强（20h）
**目标**：实现缺失的三个核心数据模型（修正外键约束+补充索引）
| 步骤 | 任务 | 文件 | 工作量 |
|------|------|------|--------|
| 8.1 | 实现TestReport、TuningSuggestionRecord、IntentAnnotation模型（无外键） | `backend/src/models/rag_eval/` | 6h |
| 8.2 | 补充对应的Pydantic Schema | `backend/src/schemas/rag_eval.py` | 4h |
| 8.3 | 实现CRUD API接口 | `backend/src/api/rag_eval/` | 4h |
| 8.4 | 更新DDL脚本，添加索引，测试建表 | `.ai/full_init_script_mysql57.sql` | 6h |
**验收**：
- [ ] 三个模型CRUD接口正常
- [ ] 字段符合需求规范
- [ ] DDL脚本可正常执行
**详细方案**：见 [08-data-model-enhancement.md](./08-data-model-enhancement.md)
---
### 【新增】阶段 9：6层校验引擎实现（183h）
**目标**：完整实现6层递进式校验引擎（已细化每层设计+全局超时+Prompt动态加载+并行优化）
| 步骤 | 任务 | 文件 | 工作量 |
|------|------|------|--------|
| 9.1 | 实现Layer1规则引擎（阈值配置化） | `backend/src/core/rag/validation/layer1_rules.py` | 23h |
| 9.2 | 实现Layer2历史对比（时间衰减） | `backend/src/core/rag/validation/layer2_history.py` | 22h |
| 9.3 | 实现Layer3 LLM诊断（PromptManager加载+降级策略+Token预算） | `backend/src/core/rag/validation/layer3_llm.py` | 45h |
| 9.4 | 实现Layer4数据质量检查 | `backend/src/core/rag/validation/layer4_data.py` | 28h |
| 9.5 | 实现Layer5检索链路检查 | `backend/src/core/rag/validation/layer5_retrieval.py` | 30h |
| 9.6 | 实现Layer6验证保障 | `backend/src/core/rag/validation/layer6_verification.py` | 25h |
| 9.7 | 实现统一调度引擎（全局超时+Layer4-6并行+SSE进度） | `backend/src/core/rag/validation/engine.py` | 25h |
**验收**：
- [ ] 每层校验逻辑独立可测试，单元测试覆盖率≥80%
- [ ] 校验100用例耗时<5分钟
- [ ] 每个建议包含原因、对比、影响分析、预期提升
**详细方案**：见 [09-validation-engine.md](./09-validation-engine.md)
---
### 【新增】阶段 10：评估报告高级功能（72h）
**目标**：实现报告的诊断展示、调优交互、趋势追踪功能
| 步骤 | 任务 | 文件 | 工作量 |
|------|------|------|--------|
| 10.1 | 实现6层校验结果展示组件 | `frontend/src/features/rag-eval/components/ValidationResult/` | 24h |
| 10.2 | 实现调优建议面板与操作流程 | `frontend/src/features/rag-eval/components/SuggestionPanel/` | 24h |
| 10.3 | 实现趋势追踪页面 | `frontend/src/features/rag-eval/pages/TrendPage.tsx` | 16h |
| 10.4 | 实现报告导出功能 | `frontend/src/features/rag-eval/utils/export.ts` | 8h |
**验收**：
- [ ] 6层校验结果清晰展示，支持筛选
- [ ] 调优建议操作流程符合三步确认原则
- [ ] 趋势图与导出功能正常
**详细方案**：见 [10-report-enhancement.md](./10-report-enhancement.md)
---
### 【新增】阶段 11：调优交互功能完善（32h）
**目标**：实现对比展示、影响分析、回滚、审计功能
| 步骤 | 任务 | 文件 | 工作量 |
|------|------|------|--------|
| 11.1 | 实现通用DiffViewer组件 | `frontend/src/components/DiffViewer/` | 8h |
| 11.2 | 实现影响分析预览组件 | `frontend/src/features/rag-eval/components/ImpactPreview/` | 8h |
| 11.3 | 实现版本回滚流程与组件 | `frontend/src/features/rag-eval/components/RollbackConfirm/` | 8h |
| 11.4 | 实现后端操作审计日志功能 | `backend/src/service/audit/` | 8h |
**验收**：
- [ ] 所有变更操作都有Diff对比展示
- [ ] 影响分析与回滚功能正常
- [ ] 所有操作都有审计日志记录
**详细方案**：见 [11-tuning-interaction.md](./11-tuning-interaction.md)
---
### 总工作量汇总
| 阶段 | 工作量 | 优先级 | 说明 |
|------|--------|--------|----------|
| 阶段 1：核心 Bug 修复 | 2.5h | 🔴 P0 | +1h（LLM 工厂签名修复） |
| 阶段 2：RAG 流水线接入 | 6h | 🔴 P0 | +2h（适配实际签名 + 集成测试） |
| 阶段 3：提示词迁移 | 2h | 🟡 P1 | +1h（改为异步调用 + 验证降级） |
| 阶段 4：认知维度矩阵 | 3h | 🟡 P1 | 无变化 |
| 阶段 5：前端 Tab 重构 | 8h | 🟢 P2 | +2h（后端工作流约束验证） |
| 阶段 6：配置系统重构 | 19h | 🔴 P0 | +9h（竞态保护+迁移备份+版本号来源明确） |
| 阶段 7：提示词页面重构 | 6.5h | 🟡 P1 | 无变化 |
| 【新增】阶段 8：数据模型增强 | 20h | 🟡 P1 | 新增3个核心数据模型（修正外键+索引） |
| 【新增】阶段 9：6层校验引擎 | 183h | 🟡 P1 | 新增6层诊断校验核心功能（已细化设计+全局超时+Prompt动态加载+并行优化） |
| 【新增】阶段10：评估报告高级功能 | 72h | 🟢 P2 | 新增报告展示、调优交互、趋势追踪 |
| 【新增】阶段11：调优交互完善 | 32h | 🟢 P2 | 新增对比展示、影响分析、回滚功能 |
| **总计（小时）** | **357h** | - | 约45人天，含新增4个模块+修复 |
**注**：实际执行建议预留15%缓冲，总工作量约80-100人天

---

## 二、风险分析

### 2.1 技术风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| LLMServiceFactory 签名不匹配 | 核心 LLM 调用全部失败 | 高（已确认并修复） | 已修复 9 个文件，改用 `LLMServiceFactoryCompat.create()` |
| PipelineOrchestrator 签名不匹配 | 无法接入调用链路 | 高（已确认） | 已在方案中修正，使用实际 `execute(query, age, limit)` 签名 |
| ConfigChangedEvent 重复定义导致事件监听失效 | 配置热加载失败 | 高 | **实施前必须先修复**：删除 `event_bus.py` 中的简化版 |
| 12 种维度模板生成质量不稳定 | 草稿重复率高 | 中 | 引入 LLM 多样性提示词 + difflib 去重 |
| 前端 Tab 切换导致路由嵌套复杂 | URL 与 Tab 状态不同步 | 低 | 使用 `useSearchParams` 同步 Tab 状态到 URL |
| SSE 内存队列模式性能不足 | 高并发时消息延迟 | 低 | 监控队列长度，超阈值时告警 |
| 工作流约束被 API 绕过 | 数据完整性受损 | 高 | 后端增加验证逻辑（已在阶段 5.6 补充） |
| 配置热加载缓存失效逻辑错误 | 配置更新不生效 | 中 | 使用优雅失效策略，复用现有 EventBus |
| LLM 热加载频繁清除缓存 | 高并发时服务重复创建 | 中 | 使用版本号标记旧实例，等待活跃请求完成后再清理 |

### 2.2 业务风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| 工作流约束过严 | 用户无法快速测试 | 中 | 提供"快速模式"开关（管理员权限） |
| 草稿审核流程过长 | 用户耐心下降 | 中 | 支持批量审核 + 智能推荐通过 |
| 测试集无法直接创建用例 | 老用户不适应 | 低 | 添加引导提示，说明新工作流 |

### 2.3 回滚策略

**项目未上线，不存在回滚需求。所有变更直接替换。**

---

## 三、验收清单

### 3.1 后端验收

#### LLM 工厂修复
- [ ] 9 个文件全部改为 `LLMServiceFactoryCompat.create()`
- [ ] 测试用例草稿生成正常（无 `TypeError`）
- [ ] 元数据提取、流式报告、RAG 流水线步骤正常
- [ ] 记忆提取、分层内容生成正常

#### 核心 Bug 修复
- [ ] `config_health_service.py` 无导入错误
- [ ] 系统启动无 `ModuleNotFoundError`
- [ ] 健康检查端点正常返回

#### RAG 流水线
- [ ] 请求走声明式流水线（`orchestrator.execute(query, age, limit)` 签名）
- [ ] 硬编码链路代码已删除
- [ ] Pipeline 执行失败时抛出异常
- [ ] 监控日志正常记录（执行耗时、结果数量）
- [ ] 查询分类逻辑准确（simple/complex 路由正确）

#### 提示词迁移
- [ ] 3 处提示词直接导入已迁移至 `prompt_manager.get_prompt()`
- [ ] 调用处改为异步（`await`）
- [ ] `prompts_fallback.py` 保留作为兜底（类似 `.env`）
- [ ] 变量替换正常工作（使用 `.format(**variables)` 语法）

#### 认知维度矩阵
- [ ] `TestCaseDraftGenerator` 支持 12 种维度、50+ 模板
- [ ] 生成 500 条用例时，去重率 < 15%
- [ ] 单次生成耗时 < 60s（batch_size=5）

#### Phase 0 根因修复
- [ ] EventSource 使用绝对路径
- [ ] PDF/EPUB 解析无乱码
- [ ] 启动时校验环境变量
- [ ] Redis 未启动时 SSE 使用内存队列
- [ ] asyncio.create_task 保持强引用
- [ ] 前端通过 SSE 监听批量测试进度
- [ ] runSingleTest 仅运行指定用例
- [ ] RetrievalService 复用单例
- [ ] 移除分布式锁，使用本地并发控制
- [ ] complete_test_run 等待所有用例聚合
- [ ] SSE 心跳队列无内存泄漏
- [ ] 前端 API 无 30 秒超时
- [ ] `prompts_fallback.py` 保留作为兜底
#### 新增模块验收
- [ ] TestReport、TuningSuggestionRecord、IntentAnnotation三个模型CRUD正常
- [ ] 6层校验引擎功能正常，每个建议包含原因、对比、影响分析、预期提升
- [ ] 配置/提示词版本管理与回滚功能正常
- [ ] 操作审计日志功能正常，所有操作可追溯

---

### 3.2 前端验收

#### Tab 重构
- [ ] 四个 Tab 页面可正常切换
- [ ] URL 与 Tab 状态同步（`?tab=drafts` 等）
- [ ] 旧路由已删除（遵循零迁移原则，不保留重定向）

#### 工作流约束
- [ ] 草稿管理页支持书籍/JSON 导入
- [ ] 测试用例管理页**无法**直接创建用例
- [ ] 测试集管理页**无法**导入书籍/JSON
- [ ] 测试集添加用例仅能从已有用例库选择
- [ ] 草稿审核通过后自动流入测试用例库

#### SSE 进度
- [ ] SSE 进度推送正常（无 30 秒超时）
- [ ] 断线重连正常
- [ ] 心跳队列无内存泄漏
#### 新增模块验收
- [ ] 6层校验结果展示正常，支持按问题类型、严重程度筛选
- [ ] 调优建议面板功能正常，符合"展示对比→说明原因→用户确认"三步原则
- [ ] 趋势追踪页面正常，支持多版本对比和指标趋势查看
- [ ] Diff对比组件功能正常，清晰展示配置/提示词变更差异
- [ ] 影响分析预览功能正常，准确展示变更影响范围
- [ ] 版本回滚功能正常，操作流程清晰
- [ ] 报告导出功能正常，支持PDF和JSON格式

---

### 3.3 集成验收

| 场景 | 预期结果 |
|------|----------|
| 导入书籍 → 生成草稿 → 审核通过 → 添加到测试集 → 运行测试 | 全流程正常 |
| 测试集页尝试直接创建用例 | 按钮不存在或禁用（前端）+ API 拒绝（后端） |
| Pipeline 执行失败 | 抛出异常，记录日志 |
| Redis 未启动 | SSE 使用内存队列，功能正常 |
| 环境变量缺失 | 启动时警告，LLM 功能禁用，系统不崩溃 |
| 直接调用 `POST /api/rag/cases` 创建用例 | 返回 403 错误（后端验证） |
| 测试运行完成 → 自动生成校验报告 → 查看调优建议 → 采纳建议 → 保存配置 → 复测 | 全流程正常，无自动应用 |
| 修改配置/提示词 → 查看前后Diff对比 → 查看影响分析 → 确认保存 → 生成新版本记录 | 全流程正常 |
| 查看版本列表 → 选择历史版本 → 查看Diff对比 → 确认回滚 → 配置恢复到旧版本 | 全流程正常 |
| 查看报告趋势 → 选择两个历史版本 → 查看指标差异和配置变更对比 | 功能正常 |
| LLM诊断生成建议 → 查看原因和影响分析 → 忽略建议 → 建议标记为已忽略 | 功能正常 |

---

## 四、实施检查清单

### 实施前
- [ ] 备份数据库
- [ ] 创建功能分支：`git checkout -b feature/rag-eval-system-fix`
- [ ] 确认所有依赖已安装（`pypdf2`, `ebooklib`, `json-repair` 等）

### 实施中
- [ ] 每完成一个阶段，运行测试确认通过
- [ ] 提交代码时编写清晰的 commit message
- [ ] 遇到阻塞问题及时沟通

### 实施后
- [ ] 全量回归测试
- [ ] 更新 PROGRESS.md 文档
- [ ] 通知相关人员进行验收

---

**实施计划制定完成，等待执行指令**。
