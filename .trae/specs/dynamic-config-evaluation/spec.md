# 动态配置与回撤测试系统需求文档 (Spec)

## Why (背景与目的)
当前系统的所有核心参数（如 RAG 权重、大模型选择、各种阈值和开关）都硬编码在 `.env.dev` 中，调整参数需要手动修改文件并重启后端服务。在进行 RAG 效果调优和回撤测试（Backtesting）时，这种方式效率极低，无法直观对比不同参数组合对最终效果的影响。
为提升调优效率，我们需要实现一个“动态配置与回撤测试”系统，允许开发者或业务人员在前端页面可视化地调整系统配置，并能够在测试页面中边改配置边重新运行回撤测试，实现所见即所得的调优体验。

## What Changes (核心变更)
- **新增配置管理 API**: 后端提供 `/api/v1/config` 的 GET 和 PUT 接口，用于读取和动态更新系统配置。配置的元数据（默认值、描述、类型）由 Pydantic Schema 自动生成。
- **配置持久化机制**: 将 `.env.dev` 作为默认和基础配置文件。前端修改的动态配置将持久化到 `.env.override` 文件中（或直接覆盖更新环境变量），以确保重启后配置不丢失，并支持恢复默认设置。
- **新增前端全局配置管理页面**: 在前端新增一个独立的「系统配置」页面，按模块（如模型设置、混合检索、阈值控制、分块策略等）分类展示所有配置项。每个配置项均带有详细的作用说明（Tooltip 或副文本）。
- **新增/改造动态回撤测试工作台 (Playground)**: 改造现有的 RAG 评估/测试页面，或者新增一个调优工作台。该页面采用左右分栏或抽屉式设计：一侧用于运行和展示回撤测试（评估测试）的结果，另一侧允许用户直接修改关键的 RAG 参数。每次修改后点击“重新测试”，系统会应用最新配置并给出新的评估结果。

## Impact (影响范围)
- Affected specs: RAG 评估功能、系统参数配置、后端 `settings.py`。
- Affected code:
  - 后端：`backend/src/config/settings.py` (需支持动态重载或 `.env.override`)，新增 `backend/src/controller/config_controller.py`。
  - 前端：新增 `frontend/src/features/config` 模块，更新 `frontend/src/features/rag-evaluation` 模块以支持内嵌配置面板。

## Implementation Solution (实施方案)

### 1. 后端配置持久化与动态加载机制
- **数据源设计**: 
  - 基础配置源：读取 `.env.dev`（只读，作为默认回退值）。
  - 动态配置源：读取 `.env.override` 文件（可写，保存用户在前端动态修改的值）。
- **配置合并逻辑**:
  - `pydantic-settings` 默认支持多个 `.env` 文件的优先级合并。可以在 `SettingsConfigDict` 中配置 `env_file=(".env.dev", ".env.override")`。
- **动态热更新机制**:
  - 内存更新：在 API `PUT /api/v1/config` 接口接收到修改后，首先将 K-V 写入 `.env.override`。
  - 实例重载：重写并重新实例化全局的 `settings` 对象，将最新的配置加载到内存。
  - 依赖更新处理：对于单例对象（如 LlamaIndex 的 `Settings.embed_model`，或提前初始化的 `DashScopeEmbedding`），后端配置服务需要触发一个 `EventBus` 的 `ConfigChangedEvent`。各业务模块监听到该事件后，重新初始化自身依赖。

### 2. 后端配置反射与 API 暴露
- **配置项自省 (Reflection)**:
  - 利用 Pydantic 的 `model_fields` 获取所有配置项的定义（字段名、类型、默认值、别名、`description` 等）。
  - 提供 `GET /api/v1/config`，返回结构化列表。为了前端分类，可在 `Field(json_schema_extra={"category": "RAG Configuration"})` 中加入分类标签。
- **重置功能**:
  - 提供 `POST /api/v1/config/reset` 接口，清空 `.env.override` 文件或移除特定 Key，然后重新加载。

### 3. 前端配置中心与调优工作台设计
- **状态管理**: 
  - 使用 Zustand 或 Context API 在全局维护一份 Config State，并在应用启动时获取。
- **动态表单渲染引擎**: 
  - 开发 `DynamicForm` 组件，根据后端下发的配置类型（boolean 渲染 Switch，number 渲染 Slider/InputNumber，string 渲染 Input/Select）自动生成表单。
  - 增加 Tooltip 悬浮提示，展示配置项的 `description`。
- **回撤调优交互流程**:
  - **布局**: 左侧占据 60% 屏幕宽度，展示测试用例集、评估进度和结果指标（准确率、召回率、相关性得分等）；右侧占据 40%，展示 RAG 相关的动态配置表单。
  - **一键重测**: 右侧参数修改并点击“应用并重测”时，先触发 `PUT /api/v1/config`，成功后再触发 `POST /api/v1/rag-test/run`。
  - **对比视图**: 在左侧的评估报告中，记录每次运行对应的“参数快照”（Config Snapshot），支持将本次得分与历史得分以图表（如雷达图或折线图）对比，直观反映参数修改带来的正负面影响。

## ADDED Requirements (新增需求)

### Requirement: 配置管理后端支持
系统应提供配置信息的自省与修改能力。
- **元数据暴露**: API 应返回每个配置项的 `key`、`type`、`current_value`、`default_value`（来自 `.env.dev`）以及 `description`（配置作用说明）。
- **动态生效**: 修改配置后，后端应立即在内存中更新 `settings` 实例，确保后续的请求（如大模型调用、检索等）使用最新配置，无需重启服务。
- **持久化与回滚**: 支持将修改持久化，并提供“恢复默认值”（即清除自定义修改，回退至 `.env.dev`）的功能。

### Requirement: 前端全局配置页面
系统应提供一个友好的可视化配置界面。
- **表单生成**: 根据后端返回的配置元数据动态渲染表单。布尔值渲染为 Switch 开关，数字渲染为数字输入框，字符串渲染为输入框或下拉框。
- **分类与搜索**: 配置项较多，需按业务逻辑进行分组（如：大模型配置、检索配置、向量存储配置等），并提供前端搜索过滤功能。

### Requirement: 动态调优回撤测试页面
系统应提供沉浸式的回撤测试与参数调优工作台。
- **分栏布局**: 左侧/上方展示回撤测试的数据集选择、运行进度和测试结果；右侧/下方展示可供快速调节的核心配置项（如 `RAG_HYBRID_BM25_WEIGHT`, `RAG_SIMILARITY_THRESHOLD` 等）。
- **参数快照与对比**: 支持记录每次测试运行时的参数快照。用户可以在多次“重新测试”后，对比不同参数组合下的指标变化（如准确率、召回率等）。

#### Scenario: 动态调优流程
- **WHEN** 用户在调优工作台页面完成一次基线测试后，发现召回率较低。
- **THEN** 用户在右侧配置面板将 `RAG_HYBRID_BM25_WEIGHT` 从 0.5 调整为 0.7，并点击“保存并重测”。
- **THEN** 前端调用 PUT API 更新配置，紧接着调用回撤测试 API。测试完成后，页面展示新的结果，并标识出与上一次基线结果的指标差异。

## MODIFIED Requirements (修改需求)
### Requirement: 现有回撤测试功能
现有的 `rag_test_controller` 在执行评估时，应确保读取的是最新的动态配置。评估报告中应包含当时运行的参数快照，以便于溯源。
