# 动态配置与回撤测试系统需求及实施方案 (Spec)

## 1. 背景与目的 (Why)
当前系统的核心参数（如 RAG 权重、大模型选择、各类阈值等）均硬编码在 `.env.dev` 中。调整参数需要修改文件并重启服务，无法在前端直观对比不同参数对 RAG 检索和生成的具体影响。
为提升系统调优效率，参考业内通用 LLMOps / RAGOps 平台（如 LangSmith, Dify, Promptflow）的架构实践，我们需要设计并实现一套“动态配置与回撤测试”系统。该系统需支持配置的可视化管理、热更新加载、配置版本化（版本快照），以及在测试工作台中的边调边测与 A/B 对比能力。

## 2. 业内通用方案核心理念 (Industry Standard Practices)
- **配置版本化与快照 (Configuration Versioning & Snapshots)**：配置不再是简单的覆盖，而是带有版本号的快照。每一次运行回撤测试，都会与一个明确的“配置版本”绑定，确保测试结果的绝对可复现与可追溯。
- **持久化到数据库/结构化存储 (Database Storage)**：环境变量（`.env.dev`）仅作为系统的出厂默认值（Seed/Fallback），动态配置应持久化至数据库（如 SQLite `system_configs` 表）或结构化 JSON 中，支持高并发读取和历史版本追溯。
- **动态热加载与依赖注入 (Hot Reload & DI)**：引入统一的 `ConfigManager`（配置中心），通过观察者模式（Observer/Pub-Sub）在配置变更时动态刷新单例依赖（如 LlamaIndex 模型实例），而非暴力重启服务。
- **沉浸式评估工作台 (Evaluation Playground)**：提供数据、参数、结果的三段式或分栏工作台，支持快速修改参数并运行评估，同时支持多版本基线对比（A/B Testing）。

## 3. 核心变更 (What Changes)
- **引入数据库配置表/存储**: 新增系统配置存储结构，记录 `config_key`, `config_value`, `version_id`, `updated_at` 等信息。
- **配置管理中心后端模块**: 封装 `ConfigManager`，实现 `GET /api/v1/config` (获取当前配置及元数据)，`PUT /api/v1/config` (生成新版本并热更新内存配置)。
- **前端配置管理与调优中心**: 
  - 新增独立的「系统全局配置」页面，按模块分类展示参数。
  - 重构「RAG 评估工作台」，左侧为测试用例与评估报告（包含当前配置版本快照），右侧为参数调优面板。
- **重测与对比机制**: 支持在调优面板修改参数后一键触发“应用并重测”，在结果页生成新旧版本的各项指标（如准确率、召回率）差异对比图表。

## 4. 详细需求与实施方案 (Requirements & Implementation Solution)

### 4.1. 后端架构：基于版本的动态配置中心
- **数据源与优先级**:
  1. `ConfigManager` 启动时，先解析 `.env.dev` 获取出厂默认值及 Pydantic Schema 的元数据（类型、描述 `description`）。
  2. 从 JSON 持久化存储读取激活的最新版本（Active Version）配置，覆盖默认值，加载到内存。
- **JSON 存储方案（Phase 1）**:
  - **存储路径**: `backend/data/configs/` 目录（需确保该目录存在且可读写）
  - **文件结构**:
    ```
    backend/data/configs/
    ├── active_version.json          # 当前激活的版本元信息
    ├── versions/
    │   ├── v_20260408_120101.json   # 版本快照文件
    │   ├── v_20260408_143022.json
    │   └── ...
    └── config_schema.json           # 从 Pydantic 反射生成的 Schema（缓存）
    ```
  - **版本快照格式** (`versions/{version_id}.json`):
    ```json
    {
      "version_id": "v_20260408_120101",
      "created_at": "2026-04-08T12:01:01Z",
      "created_by": "user@example.com",
      "description": "调整 BM25 权重至 0.3",
      "config_snapshot": {
        "rag_hybrid_bm25_weight": 0.3,
        "rag_search_score_threshold_hybrid": 0.75,
        "model_report_generation": "qwen-max"
        // ... 所有配置项的完整快照
      },
      "parent_version_id": "v_20260408_100000",
      "is_factory_reset": false
    }
    ```
  - **激活版本元信息** (`active_version.json`):
    ```json
    {
      "active_version_id": "v_20260408_143022",
      "activated_at": "2026-04-08T14:30:22Z",
      "total_versions": 15
    }
    ```
  - **并发控制**: 使用 `asyncio.Lock` 保护配置写入操作，读取操作无锁（JSON 文件读取是原子操作）
  - **性能优化**: 启动时加载活跃版本到内存缓存，后续读取优先从内存获取，避免频繁磁盘 I/O
- **版本控制 (Versioning)**:
  - 每次调用 `PUT /api/v1/config`，系统不仅更新当前值，还会生成一个新的 `version_id`（如 `v_20260408_120101`），并将此次的所有配置快照打包归档到 `versions/` 目录。
  - 回撤测试 API (`POST /api/v1/rag-test/run`) 运行时，将当前的 `version_id` 写入到测试报告 `Report` 中，实现数据溯源。
- **热更新机制 (Hot Reload)**:
  - 采用**惰性加载模式（Lazy Loading）**而非主动推送。配置变更后，`ConfigManager` 更新内存缓存并派发 `ConfigChangedEvent`。
  - 监听者（如 `RAGService`, `VectorStore`）收到事件后，**标记自身配置为过期**，在下次调用时重新从 `ConfigManager` 获取最新配置并初始化。
  - **配置分类**:
    - **热更新配置**（支持运行时刷新）：权重、阈值、开关、缓存设置等
    - **冷更新配置**（需重启服务）：API Key、模型名称、数据库连接等
  - **配置元数据增强**:
    ```python
    class ConfigFieldMetadata:
        key: str
        category: str
        description: str
        hot_reloadable: bool  # 是否支持热更新
        requires_restart: bool  # 是否需要重启
        affected_components: list[str]  # 影响的组件列表
    ```
- **后续 SQL 迁移扩展点（Phase 2）**:
  - `ConfigManager` 采用**仓储模式（Repository Pattern）**，定义 `ConfigRepository` 抽象接口
  - Phase 1 实现 `JsonConfigRepository`，Phase 2 实现 `SqlConfigRepository`
  - 通过依赖注入切换存储后端，业务逻辑无需修改

### 4.2. 后端 API 暴露与反射 (Reflection)
- **元数据暴露**: 
  - `GET /api/v1/config`: 利用 Pydantic 的 `model_fields` 返回完整结构，包含：`key`、`type`、`default_value`、`current_value`、`description`（前端 Tooltip 使用）、`category`（所属分类，如"模型设置"、"混合检索权重"等）。
- **历史与回滚**:
  - `GET /api/v1/config/versions`: 获取配置的历史版本列表（按时间倒序，包含 `version_id`、`created_at`、`description`、`is_active`）。
  - `POST /api/v1/config/rollback/{version_id}`: 回滚到指定的历史版本。
    - **回滚流程**:
      1. 验证目标版本存在且文件完整
      2. 创建回滚审计记录（记录 `from_version`、`to_version`、`rollback_at`）
      3. 应用目标版本配置到内存缓存
      4. 更新 `active_version.json`
      5. 派发 `ConfigChangedEvent` 触发惰性刷新
      6. 返回回滚结果（成功/失败 + 审计日志 ID）
  - `POST /api/v1/config/reset`: 恢复到 `.env.dev` 的出厂状态。
    - 生成新版本快照，标记 `is_factory_reset: true`
    - 清空所有用户自定义配置，重新从 `.env.dev` 加载
- **配置审计日志**:
  - 存储路径: `backend/data/configs/audit_log.jsonl`（JSON Lines 格式，追加写入）
  - 每条记录: `{"timestamp": "...", "action": "UPDATE|ROLLBACK|RESET", "from_version": "...", "to_version": "...", "user": "..."}`

### 4.3. 前端交互：全局配置与评估工作台
- **全局配置页面 (System Settings)**:
  - 使用动态表单引擎，依据 `type` 自动渲染组件（Boolean -> Switch, Float -> Slider/InputNumber, String -> Select/Input）。
  - 根据 `category` 实现侧边栏导航锚点，配置项旁增加问号图标悬浮展示 `description`。
  - 对于标记为 `requires_restart: true` 的配置项，显示橙色警告图标提示"修改后需重启服务"。
- **RAG 调优工作台 (Playground / Evaluation)**:
  - **沉浸式布局**: 左侧展示测试集列表与最新评估报告（含雷达图、指标卡）；右侧提供常驻的"核心参数调优面板"（如修改 `RAG_HYBRID_BM25_WEIGHT`）。
  - **所见即所得调优**: 
    - 用户在右侧修改参数 → 参数进入"草稿状态"（未保存）
    - 点击"应用并重测" → 前端依次调用 `PUT /api/v1/config`（生成新版本）→ `POST /api/v1/rag-test/run`
    - 评估运行期间，调优面板锁定（`disabled` 状态），防止并发修改
  - **前端状态管理**:
    ```typescript
    interface ConfigPlaygroundState {
      baseVersion: ConfigVersion;      // 当前激活版本
      draftChanges: Partial<Config>;   // 未保存的修改
      isRunning: boolean;              // 是否正在运行评估
      lastResult: EvaluationResult;    // 上次评估结果
      comparisonBaseline: string;      // 对比基线版本 ID
    }
    ```
  - **A/B 对比视图**: 
    - 在测试完成后的报告中，前端自动拉取上一次测试的指标（基于历史版本）与本次结果进行 Diff 对比
    - 展示形式：指标卡 + 上升/下降箭头 + 百分比变化（如"召回率 +5% ↑"、"准确率 -2% ↓"）
    - 支持手动选择任意两个历史版本进行对比

---

## 5. 任务拆解 (Tasks)

- **Task 1: 后端动态配置核心与版本化存储**
  - 1.1 在 `settings.py` 的 Pydantic 模型中补充完整的 `description`、`category`、`hot_reloadable` 元数据。
  - 1.2 定义 `ConfigRepository` 抽象接口（仓储模式），实现 `JsonConfigRepository`（Phase 1）。
  - 1.3 实现 `ConfigManager` 类，负责合并 `.env.dev` 与 JSON 持久化存储，管理 `version_id` 历史记录，提供内存缓存。
  - 1.4 实现 EventBus 机制，采用惰性加载模式：配置变更时派发事件，监听者标记自身配置过期，下次调用时重新初始化。
  - 1.5 创建 `backend/data/configs/` 目录结构，实现版本快照读写、激活版本管理、审计日志追加写入。

- **Task 2: 后端配置管理 API 开发**
  - 2.1 开发 `GET /api/v1/config`，通过 Pydantic 反射生成结构化元数据列表（含 `hot_reloadable`、`requires_restart` 标识）。
  - 2.2 开发 `PUT /api/v1/config`，实现配置更新、新版本生成（写入 JSON 快照）、审计日志记录、事件触发。
  - 2.3 开发 `GET /api/v1/config/versions` 与 `POST /api/v1/config/reset`，支持版本查询与出厂重置。
  - 2.4 开发 `POST /api/v1/config/rollback/{version_id}`，实现版本回滚（含审计日志、配置应用、事件派发）。

- **Task 3: 后端回撤测试链路集成**
  - 3.1 改造回撤测试控制器，确保每次运行的报告数据结构中记录当前的 `config_version_id` 以及配置快照。
  - 3.2 在测试报告中增加配置版本对比字段，支持前端 Diff 展示。

- **Task 4: 前端配置管理基础与全局页面**
  - 4.1 在 `src/api` 和 `src/store` 中封装配置请求与全局状态管理（含 `ConfigPlaygroundState`）。
  - 4.2 开发通用的 `DynamicConfigForm` 组件，支持 Switch、Slider、InputNumber、Tooltip 渲染，根据 `hot_reloadable` 显示警告图标。
  - 4.3 创建 `SystemConfigPage.tsx`，实现分类导航、批量修改保存、草稿状态管理。

- **Task 5: 调优工作台与 A/B 对比视图开发**
  - 5.1 重构 `RagEvaluationPage.tsx`，采用 60/40 分栏布局，右侧嵌入核心参数调优面板。
  - 5.2 实现“保存配置并重新测试”的串联交互逻辑（草稿 → 应用 → 运行 → 锁定面板 → 展示结果）。
  - 5.3 在评估报告组件中增加“参数快照记录”与“多版本 Diff 对比”（展示指标的上升/下降箭头、百分比变化）。
  - 5.4 实现版本选择器，支持手动选择任意两个历史版本进行对比。

---

## 6. 验收标准 (Checklist)

- [ ] `settings.py` 的所有配置项均已具备完善的 `description`（作用说明）、`category`（分类）和 `hot_reloadable`（是否支持热更新）元数据。
- [ ] `ConfigRepository` 抽象接口已定义，`JsonConfigRepository` 实现完成（Phase 1），为后续 SQL 迁移预留扩展点。
- [ ] `ConfigManager` 能够生成并记录带有 `version_id` 的配置快照（JSON 文件），而不是简单的文件覆盖。
- [ ] `backend/data/configs/` 目录结构正确创建，包含 `active_version.json`、`versions/` 子目录、`audit_log.jsonl`。
- [ ] 后端采用惰性加载模式（Lazy Loading）实现热更新：配置变更时派发事件，监听者标记过期，下次调用时重新初始化。
- [ ] `GET /api/v1/config` 返回包含名称、类型、默认值、当前值、描述、`hot_reloadable`、`requires_restart` 的元数据结构。
- [ ] 提供了"恢复默认值（回退至 `.env.dev`）"、"历史版本查询"及"版本回滚（含审计日志）"的接口支持。
- [ ] 前端成功集成了"系统全局配置"页面，能动态渲染各类表单控件，并带有悬浮的作用说明和热更新警告图标。
- [ ] RAG 评估工作台实现了分栏式的调优面板，可以在测试页中直接修改核心配置，支持草稿状态管理。
- [ ] 在工作台中修改配置并触发"重测"后，后端使用新版本配置完成测试，报告中准确记录了 `version_id`。
- [ ] 评估报告页面能够展示当前运行版本与历史基线版本的指标 Diff（如准确率变化），支持手动选择任意两个版本对比。