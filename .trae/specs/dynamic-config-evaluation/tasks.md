# Tasks

- [ ] Task 1: 后端配置管理模块核心支持
  - [ ] SubTask 1.1: 改造 `backend/src/config/settings.py`，支持从 `.env.dev` 读取默认值，并支持从 `.env.override` 或内存中加载动态覆盖的配置。
  - [ ] SubTask 1.2: 在 `settings.py` 的 Pydantic 模型中完善所有字段的 `description` 属性，确保每个配置项都有清晰的作用说明。
  - [ ] SubTask 1.3: 实现配置元数据解析逻辑，能够提取字段的名称、类型、默认值、当前值和描述。
  - [ ] SubTask 1.4: 确保 LlamaIndex 等全局单例组件在相关配置（如 Embedding 模型）变更时能够被安全地重新初始化。

- [ ] Task 2: 后端配置管理 API 开发
  - [ ] SubTask 2.1: 创建 `backend/src/controller/config_controller.py`。
  - [ ] SubTask 2.2: 实现 `GET /api/v1/config` 接口，返回分组后的配置元数据列表。
  - [ ] SubTask 2.3: 实现 `PUT /api/v1/config` 接口，接收批量更新的配置，更新内存中的 `settings`，并持久化到 `.env.override`。
  - [ ] SubTask 2.4: 实现 `POST /api/v1/config/reset` 接口，清除指定或所有配置的覆盖状态，恢复为 `.env.dev` 的默认值。

- [ ] Task 3: 前端配置管理基础建设
  - [ ] SubTask 3.1: 在 `frontend/src/api` 下新增 `config` 模块，封装上述配置 API 的请求方法及类型定义。
  - [ ] SubTask 3.2: 在 `frontend/src/features` 下新增 `config` 业务模块，包含相应的 Store 或 Hooks (`useConfig.ts`) 来管理配置状态。

- [ ] Task 4: 前端全局系统配置页面开发
  - [ ] SubTask 4.1: 创建 `SystemConfigPage.tsx` 页面，包含左侧导航栏（分类）和右侧配置表单。
  - [ ] SubTask 4.2: 开发通用的配置项组件 `ConfigItem.tsx`，支持根据字段类型渲染 Switch、InputNumber、Input 等控件，并展示附带作用说明的 Tooltip。
  - [ ] SubTask 4.3: 实现配置的批量保存和恢复默认值交互逻辑。

- [ ] Task 5: 动态回撤测试与调优工作台开发
  - [ ] SubTask 5.1: 改造现有的回撤测试页面（如 `RagEvaluationPage.tsx`），将其布局升级为左右分栏或引入“调优面板”抽屉。
  - [ ] SubTask 5.2: 在调优面板中集成 RAG 相关的核心参数表单（复用 Task 4 中的配置组件），允许用户在当前页面直接修改参数。
  - [ ] SubTask 5.3: 实现“保存并重新测试”流程：先调用保存配置 API，成功后自动触发重新运行回撤测试。
  - [ ] SubTask 5.4: 在测试结果展示区域增加“当前参数快照”的展示，便于用户对比不同参数对测试结果的影响。

# Task Dependencies
- [Task 2] depends on [Task 1]
- [Task 3] depends on [Task 2]
- [Task 4] depends on [Task 3]
- [Task 5] depends on [Task 3]
