# 实施进度追踪

## 📊 总体进度

| Phase | 状态 | 进度 | 说明 |
|-------|------|------|------|
| Phase 0: 核心工作流修复 | ⏳ 待开始 | 0% | 书籍导入 + 批量测试 12 个根因修复 |
| Phase 1: 数据模型创建 | ⏳ 待开始 | 0% | 18 个数据模型 + 数据库表（主键 UUID）|
| Phase 2: SSE 工作流实现 | ⏳ 待开始 | 0% | 10 种 SSE 事件（含 heartbeat + export_ready）+ 运行工作流 |
| Phase 3: 前端页面实现 | ⏳ 待开始 | 0% | 测试集管理/运行历史/评估报告 + 删除 OneClickOptimize |
| Phase 4: 校验引擎实现 | ⏳ 待开始 | 0% | 6 层 13 种校验 + 生成质量指标扩展 (Layer 3) |
| Phase 5: 推荐模式面板 | ⏳ 待开始 | 0% | 推荐/向导/专家三种模式 |
| Phase 6: 趋势追踪与导出 | ⏳ 待开始 | 0% | 趋势图 + PDF/CSV/JSON 导出 |
| Phase 7: 提示词管理重构 | ⏳ 待开始 | 0% | 新增 PromptMetadata、删除 PromptABTest、前端页面重构、影响分析引擎 |
| Phase 8: 配置管理优化 | ⏳ 待开始 | 0% | 配置元数据补充（中文名称/取值范围）、前端分组展示、实时校验引擎 |

---

## Phase 0: 核心工作流修复

### 书籍导入修复 (5 个根因)

- [ ] **修复 1**: EventSource 相对路径 → 前端 SSE 连接使用绝对路径
- [ ] **修复 2**: PDF/EPUB 二进制读取 → 使用专用解析器 (pypdf2/ebooklib)
- [ ] **修复 3**: DASHSCOPE_API_KEY 未配置 → 启动时校验环境变量
- [ ] **修复 4**: Redis 依赖问题 → 降级到内存队列模式
- [ ] **修复 5**: asyncio.create_task 无引用 → 保持强引用防止 GC

### 批量测试修复 (7 个根因)

- [ ] **修复 6**: 前端无 SSE 监听 → 批量测试通过 SSE 推送进度
- [ ] **修复 7**: runSingleTest 调用 runAllTests → 严格只运行指定用例
- [ ] **修复 8**: RetrievalService 重复初始化 → 复用同一实例
- [ ] **修复 9**: 分布式锁对唯一 run_id 无意义 → 使用本地并发控制
- [ ] **修复 10**: complete_test_run 读到不完整数据 → 等待所有用例聚合
- [ ] **修复 11**: SSE 心跳队列内存泄漏 → 前端断开时清理队列
- [ ] **修复 12**: 前端 API 超时 30 秒 → 依赖 SSE 进度事件，不设 HTTP 超时

---

## Phase 1: 数据模型创建

- [ ] **Step 1**: 创建 TestSet 表 (主键 UUID)
- [ ] **Step 2**: 创建 TestSetCase 中间表 (主键 UUID)
- [ ] **Step 3**: 创建 TestCase 表 (主键 UUID)
- [ ] **Step 4**: 创建 TestRunResult 表 (主键 UUID, run_id FK, case_id FK, hit_at_1/3/5, matched_doc_ids/scores, status, duration_ms)
- [ ] **Step 5**: 创建 ConfigVersion 表 (主键 UUID, config_snapshot JSON, version_label)
- [ ] **Step 6**: 创建 PromptVersion 表 (主键 UUID, version_label VARCHAR + version_number INT)
- [ ] **Step 7**: 创建 ConfigChangeSet 表 (主键 UUID, 不含 prompt_version_ids)
- [ ] **Step 8**: 创建 ConfigChangeSetPrompt 关联表 (主键 UUID, change_set_id FK, prompt_version_id FK)
- [ ] **Step 9**: 创建 TestReport 表 (主键 UUID, validation_results 单列 JSON 数组, run_id 可选)
- [ ] **Step 10**: 创建 TuningSuggestionRecord 表 (主键 UUID)
- [ ] **Step 11**: 创建 PromptSuggestionRecord 表 (主键 UUID)
- [ ] **Step 12**: 创建 TestRun 表 (主键 UUID, 无 report_id FK)
- [ ] **Step 13**: 创建 TestCaseDraft 表 (主键 UUID)
- [ ] **Step 14**: 创建 IntentAnnotation 表 (主键 UUID)
- [ ] **Step 15**: 创建 PromptMetadata 表 (主键 UUID, prompt_key 唯一索引, name_zh, purpose, category, variables_schema)
- [ ] **Step 16**: 创建 IgnoredSuggestion 表 (主键 UUID, test_set_id FK, report_id FK 可选)
- [ ] **Step 17**: 创建 QueryIntentLog 表 (主键 UUID, run_id FK, case_id FK, 存储意图自动分类结果)
- [ ] **Step 18**: 创建 SynonymQueryPair 表 (主键 UUID, query_a, query_b, domain, source, active)

---

## Phase 2: SSE 工作流实现

- [ ] **Step 1**: 定义 10 种 SSE 事件 Pydantic 模型（含 heartbeat + export_ready）
- [ ] **Step 2**: 实现 SSE 发布器 (支持内存队列降级)
- [ ] **Step 3**: 实现心跳机制 (15s 间隔)
- [ ] **Step 4**: 实现断线重连查询 API (`GET /api/runs/{id}/status`)
- [ ] **Step 4.1**: 实现 SSE 连接端点 (`GET /api/runs/{run_id}/sse` 和 `GET /api/sse/exports`)
- [ ] **Step 5**: 实现 TestRun 创建与执行逻辑
- [ ] **Step 6**: 实现用例执行结果聚合
- [ ] **Step 7**: 实现 `test_completed` 事件触发
- [ ] **Step 8**: 实现 `report_ready` 事件触发
- [ ] **Step 9**: 实现导出任务 SSE 推送 (`export_ready` 事件)

---

## Phase 3: 前端页面实现

- [ ] **Step 1**: 创建 `/rag-eval/*` 路由结构
- [ ] **Step 2**: 实现测试集列表页 (含删除级联规则：TestSetCase/TestRun/TestReport/TestCaseDraft/IgnoredSuggestion 级联删除，TestCase 保留)
- [ ] **Step 3**: 实现测试集详情页 + 用例管理
- [ ] **Step 4**: 实现草稿审核页
- [ ] **Step 5**: 实现运行历史列表页
- [ ] **Step 6**: 实现运行详情页 + SSE 进度 (用例列表展示 hit@k，非 P/R/F1)
- [ ] **Step 7**: 实现评估报告页 (核心页面)
- [ ] **Step 8**: 删除 OneClickOptimize 组件及相关代码

---

## Phase 4: 校验引擎实现

- [ ] **Step 1**: 实现 ValidationOrchestrator 编排器
- [ ] **Step 2**: 实现 Layer 1 规则引擎 (自适应步长 + 冲突检测)
- [ ] **Step 3**: 实现 Layer 2 历史对比 (差分对比 + 失败模式匹配)
- [ ] **Step 4**: 实现 Layer 3 LLM 诊断 (7 种失败类型 + 8 种根因 + 降级)
- [ ] **Step 5**: 实现 Layer 4 数据质量 (Golden 覆盖 + 分块质量 + 文档时效)
- [ ] **Step 6**: 实现 Layer 5 检索链路 (Embedding 校验 + 意图识别 + 错误分组)
- [ ] **Step 7**: 实现 Layer 6 验证保障 (回归检测 + 交叉验证 + 成本效果 + A/B)

---

## Phase 5: 推荐模式面板

- [ ] **Step 1**: 实现推荐模式面板 (默认模式)
- [ ] **Step 2**: 实现审查面板 (采纳→审查→保存三步分离)
- [ ] **Step 3**: 实现对比视图 (配置对比/提示词对比/自定义值)
- [ ] **Step 4**: 实现已忽略列表 (report/test_set 双级别，使用 IgnoredSuggestion 独立表)
- [ ] **Step 5**: 实现 ConfigChangeSet 原子保存 (事务管理)
- [ ] **Step 6**: 实现向导模式
- [ ] **Step 7**: 实现专家模式
- [ ] **Step 8**: 实现面板布局适配 (固定/抽屉切换)

---

## Phase 6: 趋势追踪与导出

- [ ] **Step 1**: 实现趋势图 (时间轴 + 配置版本 hover)
- [ ] **Step 2**: 实现配置版本对比
- [ ] **Step 3**: 实现配置版本回滚 (配置+提示词同时回滚，创建 rolled_back 变更集)
- [ ] **Step 4**: 实现 PDF 导出
- [ ] **Step 5**: 实现 CSV 导出
- [ ] **Step 6**: 实现 JSON 导出

---

## Phase 7: 提示词管理重构

> **需求来源**: 07-prompt-management-overview.md, 07a-prompt-data-model.md, 07b-prompt-frontend-pages.md, 07c-prompt-impact-analysis.md, 07d-prompt-code-adaptation.md

### 7.1 数据模型变更

- [ ] **新建** `prompt_metadata` 表（主键 UUID，含 name_zh/purpose/category/variables_schema/code_references/config_dependencies 等字段）
- [ ] **修改** `prompt_versions` 表：id 改为 UUID、version 重命名为 version_label、新增 variables_extracted + change_impact 字段
- [ ] **删除** `prompt_versions.variables` 字段（所有读取改为 variables_extracted）
- [ ] **删除** `prompt_versions.tags` 字段
- [ ] **删除** `prompt_versions.fallback` 字段（降级逻辑由 prompts_fallback.py 文件独立处理）
- [ ] **删除** `prompt_ab_tests` 表（整个表删除）
- [ ] **初始化** 所有现有提示词的 PromptMetadata 记录（10 个系统内置提示词）

**PromptMetadata 初始化策略**:
- **执行方式**: 独立初始化脚本 `backend/scripts/init_prompt_metadata.py`，通过 `uv run python backend/scripts/init_prompt_metadata.py` 手动执行
- **数据来源**: 从 `prompts_fallback.py` 中提取 10 个系统内置提示词的 key 和 content，自动生成 `name_zh`（key 的中文翻译映射表硬编码在脚本中）、`purpose`（从 content 首段提取）、`category`（根据 key 前缀自动分类：`rag_` → RAG 检索，`generation_` → 内容生成，`assessment_` → 评估报告）
- **冲突处理**: 若 `prompt_metadata` 表中已存在某 key 的记录，脚本跳过该记录（不覆盖），输出日志提示"已存在，跳过"
- **不一致处理**: 若 `prompts_fallback.py` 中的提示词 content 与 `prompt_versions` 表中的 content 不一致，**以数据库为准**（数据库是权威来源，fallback 文件仅作为降级后备）
- **失败处理**: 初始化脚本执行失败（如数据库连接异常、字段缺失）**不阻塞系统启动**，但输出错误日志。系统启动时检查 `prompt_metadata` 表记录数，若少于 10 条，在日志中输出警告"PromptMetadata 初始化不完整，请运行 init_prompt_metadata.py"
- **后续维护**: 新增提示词时，必须同步在 `init_prompt_metadata.py` 的映射表中添加中文名称和分类，确保初始化脚本能正确处理

### 7.2 老代码删除清单

- [ ] **删除** `PromptABTest` 模型类 — `backend/src/core/prompt/models.py`
- [ ] **删除** A/B 测试 API 端点 — `backend/src/api/v1/prompts.py`：`/ab-tests` (GET/POST)、`/ab-tests/{test_id}/toggle` (POST)
- [ ] **删除** A/B 测试前端页面和组件 — `frontend/src/features/prompts/` 下所有 A/B 测试相关组件
- [ ] **删除** `PromptVersion.variables` 字段读取逻辑 — `backend/src/core/prompt/manager.py` 中所有 `.variables` 属性访问
- [ ] **删除** 旧 API 端点 `/api/v1/prompts/{prompt_key}`（原返回 A/B 测试参数，改为新端点 `/api/v1/prompts/metadata/:key`）

### 7.3 代码修改清单

- [ ] **修改** `PromptVersion.id` 查询 — 所有通过 ID 查询的代码改为 UUID 查询（`backend/src/core/prompt/manager.py` 及所有调用处）
- [ ] **修改** `PromptVersion.version` → `version_label` — 全局替换（所有引用 `.version` 属性的代码）
- [ ] **修改** `prompt_manager.get_prompt()` — 接口不变，内部逻辑适配新模型

### 7.4 前端页面实现

- [ ] **新建** 提示词列表页 `/prompt-management`（中文名称、分类、状态、搜索筛选）
- [ ] **新建** 提示词编辑页 `/prompt-management/:key`（内容编辑器、变量面板、影响分析面板）
- [ ] **新建** 版本管理页 `/prompt-management/:key/versions`（版本列表、对比、回滚）
- [ ] **新建** 测试沙箱页 `/prompt-management/:key/sandbox`（变量表单、LLM 输出预览、对比模式）

### 7.5 影响分析引擎

- [ ] **实现** 代码引用扫描器（AST + 正则混合扫描 `prompt_manager.get_prompt()` 调用）
- [ ] **实现** 变量校验器（检测新增/删除/缺失/未声明变量）
- [ ] **实现** 配置参数依赖检测器（正则匹配提示词中的 `{param_name}`）
- [ ] **实现** 影响分析 API（`GET /api/v1/prompts/:key/impact`、`POST /api/v1/prompts/:key/scan`）

### 7.6 降级文件同步

- [ ] **后续优化**: 实现 CI 钩子或运行时同步机制，确保 `prompts_fallback.py` 与数据库版本一致（当前阶段可手动同步）

---

## Phase 8: 配置管理优化

> **需求来源**: 08-config-management-overview.md, 08a-config-metadata.md, 08b-config-frontend-pages.md, 08c-config-validation.md

### 8.1 配置元数据补充

- [ ] **新增** `config_field_metadata` 表字段：id (UUID)、name_zh、description_zh、unit、min_value、max_value、recommended_range
- [ ] **初始化** 所有配置项的中文元数据（RAG 检索 ~30 项、RAG 分块 ~10 项、RAG 向量库 ~8 项、LLM 模型 ~15 项、数据库 ~5 项、Redis ~8 项、日志 ~5 项、业务规则 ~15 项、应用 ~5 项）

### 8.2 前端配置页重构

- [ ] **重构** 配置主页：按功能域分组展示（RAG 检索/RAG 分块/LLM 模型/数据库/Redis/日志/业务规则）
- [ ] **新增** 实时校验：输入时校验取值范围和推荐范围（前端表单 + 后端 API）
- [ ] **新增** 影响范围展示：编辑配置时展示"影响组件"和"重载方式"标签
- [ ] **新增** 配置版本管理：版本列表、对比、回滚

### 8.3 配置校验引擎

- [ ] **实现** 类型校验：数值型/布尔型/枚举型/字符串型
- [ ] **实现** 范围校验：min_value/max_value 硬拦截
- [ ] **实现** 推荐范围警告：recommended_range 超出时警告但不阻止保存
- [ ] **实现** 冲突检测：检测配置项之间的冲突（如 bm25_weight + vector_weight ≠ 1）

---

**最后更新:** 2026-04-16  
**文档版本:** v15.0  
**维护者:** AI Assistant
