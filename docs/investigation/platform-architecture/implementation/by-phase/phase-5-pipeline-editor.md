# Phase 5：管道编辑器前端——实施文档

> **依赖**：Phase 4（搜索 API）完成后启动。后端 API 已就绪，前端构建可视化编辑体验。
> **产出**：管道列表页、React Flow 画布编辑器（节点面板 + 属性面板）、三视图工作台（编辑 / 评估 / 发布）。
> **参考规范**：[02-pipeline-editor.md](../../requirements/02-pipeline-editor.md)、[01-pipeline-model-and-engine.md](../../requirements/01-pipeline-model-and-engine.md)
> **最后更新**：2026-05-14

---

## 1. 阶段目标

构建管道编辑器的前端完整交互链路，实现从零搭建、配置、保存到评估/发布联动的全流程：

- **管道列表页**：卡片视图展示当前租户所有管道，支持新建（空白/复制/导入 JSON）、搜索、筛选
- **管道工作台**：三视图（编辑 / 评估 / 发布）无缝切换，WorkbenchToolbar 统一顶部导航
- **编辑视图**：
  - React Flow 画布：自定义 nodeTypes（域容器、通用节点、聚合节点、复合节点）、edgeTypes（数据流/条件/降级）
  - NodePanel：左侧面板，28 种节点按分类折叠，拖拽放置到画布
  - PropertyPanel：右侧面板，选中节点后按 nodeType 动态渲染对应参数表单（28 种不同表单）
  - DomainContainer：域容器折叠/展开、域内节点防越界拖拽、外部节点防入侵拖拽
  - 撤销/重做：快照式，最大深度 50 步
  - 保存：自动自增版本号，弹窗输入变更日志
- **评估视图**：复用 Phase 7 RAG 评估组件，从编辑视图切换时自动加载该管道评估历史
- **发布视图**：复用 Phase 4 发布配置面板，配置搜索端点发布

---

## 2. 任务清单

### 2.1 状态管理（5.1 状态管理）

#### `features/pipeline/stores/pipelineWorkbenchStore.ts`

- [ ] **基础状态定义**：`PipelineWorkbenchState` 接口（如下字段）
  - `pipelineId: string | null`——当前编辑的管道 ID
  - `pipelineName: string`——管道名称
  - `pipelineVersion: number`——当前版本号
  - `activeView: 'edit' | 'evaluate' | 'publish'`——当前视图
- [ ] **编辑视图状态**
  - `domains: DomainConfig[]`——域列表（含 nodeId 列表、折叠/展开态、绑定的 knowledgeBaseId）
  - `aggregationNodes: AggregationNodeConfig[]`——聚合层节点（不属于任何域）
  - `edges: EdgeConfig[]`——全部边（含条件边、降级边元数据）
  - `selectedNodeId: string | null`——当前选中的节点 ID
  - `selectedDomainId: string | null`——当前选中的域 ID
  - `isDirty: boolean`——是否有未保存的变更
- [ ] **撤销/重做**
  - `undoStack: PipelineSnapshot[]`——最大深度 50（超出丢弃最早快照）
  - `redoStack: PipelineSnapshot[]`——执行新操作时清空
  - `snapshot()`——创建当前状态快照（JSON 深拷贝 nodes + edges + domains）
  - `undo()`——弹出 undoStack 最后一项 → 恢复状态 → 推入 redoStack
  - `redo()`——弹出 redoStack 最后一项 → 恢复状态 → 推入 undoStack
  - 快照时机：每次 `addNode`、`removeNode`、`updateNodeConfig`、`addEdge`、`removeEdge`、`addDomain`、`removeDomain` 执行后自动 snapshot
- [ ] **复合节点库**
  - `compoundNodeLibrary: CompoundNodeConfig[]`——从后端 `/api/v1/compound-nodes` 加载
  - `loadCompoundNodeLibrary()`——初始化时加载
  - `addToLibrary()`——拖拽到画布后可选保存为复合节点
- [ ] **操作方法**
  - `switchView(view)`——切换 activeView，离开编辑视图前检查 `isDirty` 提示
  - `addNode(domainId, nodeType, position)`——在指定域或画布空白处创建节点
  - `removeNode(nodeId)`——删除节点及其关联边
  - `updateNodeConfig(nodeId, config)`——更新节点配置（触发 snapshot）
  - `addEdge(edge)`——添加边（检查循环引用）
  - `removeEdge(edgeId)`——删除边
  - `addDomain(domainConfig)`——添加业务域（创建空域容器）
  - `removeDomain(domainId)`——删除域及其内部所有节点（二次确认）
  - `updateDomainConfig(domainId, config)`——更新域属性（名称、知识库、权重、关键词）
  - `moveNodeToDomain(nodeId, targetDomainId)`——节点在域间迁移
  - `save()`——调用后端 API，成功返回新版本号
  - `validate()`——调用后端校验 API，返回 `ValidationResult`
  - `dryRun()`——调用后端干运行 API，返回 `DryRunResult`
  - `loadPipeline(pipelineId)`——从后端加载管道数据初始化 store
- [ ] **性能约束强制检查**
  - `checkDomainLimit()`：域数超过 20 个时阻止添加
  - `checkNodeLimit(domainId)`：单域节点数超过 30 个时阻止
  - `checkTotalNodeLimit()`：总节点数超过 100 个时阻止保存
  - `checkCompoundNesting(compoundId)`：复合节点嵌套超过 3 层时阻止

#### `features/pipeline/stores/pipelineListStore.ts`

- [ ] **管道列表状态**
  - `pipelines: PipelineListItem[]`——当前租户管道列表
  - `searchQuery: string`——搜索关键词
  - `statusFilter: string | null`——状态筛选
  - `page: number`、`pageSize: number`
  - `loadPipelines()`——从后端加载，带租户过滤
  - `deletePipeline(id)`——删除管道

### 2.2 API 客户端（5.2 API 客户端）

#### `api/pipeline/pipeline.ts`

- [ ] **管道 CRUD**
  - `getPipelines(params: PipelineListParams) → PipelineListItem[]`——GET `/api/v1/pipelines`
  - `getPipeline(id: string) → PipelineDetail`——GET `/api/v1/pipelines/:id`
  - `createPipeline(data: PipelineCreate) → PipelineDetail`——POST `/api/v1/pipelines`
  - `updatePipeline(id: string, data: PipelineUpdate) → PipelineDetail`——PUT `/api/v1/pipelines/:id`
  - `deletePipeline(id: string) → void`——DELETE `/api/v1/pipelines/:id`
  - `importPipeline(data: PipelineImport) → PipelineDetail`——POST `/api/v1/pipelines/import`（JSON 导入）
- [ ] **版本管理**
  - `getVersions(pipelineId: string) → PipelineVersionRead[]`——GET `/api/v1/pipelines/:id/versions`
  - `getVersion(pipelineId: string, version: number) → PipelineDetail`——GET `/api/v1/pipelines/:id/versions/:version`
  - `rollbackVersion(pipelineId: string, version: number) → PipelineDetail`——POST `/api/v1/pipelines/:id/versions/:version/rollback`
  - `compareVersions(pipelineId, v1, v2) → VersionCompareResult`——GET `/api/v1/pipelines/:id/versions/compare?v1=X&v2=Y`
- [ ] **保存（自动自增版本）**
  - `savePipeline(id, data: PipelineSaveRequest) → PipelineDetail`——PUT `/api/v1/pipelines/:id/save`
  - 请求体含 `config_snapshot`（完整管道 JSON）、`change_log`（变更日志字符串）、`version`（前端持有版本号做乐观锁检查）
- [ ] **校验与干运行**
  - `validatePipeline(id, config) → ValidationResult`——POST `/api/v1/pipelines/:id/validate`
  - `dryRunPipeline(id, config, input) → DryRunResult`——POST `/api/v1/pipelines/:id/dry-run`
- [ ] **复合节点**
  - `getCompoundNodes() → CompoundNodeRead[]`——GET `/api/v1/compound-nodes`
  - `createCompoundNode(data) → CompoundNodeRead`——POST `/api/v1/compound-nodes`
  - `deleteCompoundNode(id) → void`——DELETE `/api/v1/compound-nodes/:id`
  - `importCompoundNode(data) → CompoundNodeRead`——POST `/api/v1/compound-nodes/import`
  - `exportCompoundNode(id) → CompoundNodeExport`——GET `/api/v1/compound-nodes/:id/export`
- [ ] **类型定义**
  - `PipelineListItem`：`{ id, name, version, domain_count, node_count, last_eval_score, published_endpoints, status, created_at, updated_at }`
  - `PipelineDetail`：`{ id, name, version, config_snapshot: PipelineConfig, created_at, updated_at, versions: PipelineVersionRead[] }`
  - `PipelineConfig`：`{ domains: DomainConfig[], aggregation_nodes: AggregationNodeConfig[], edges: EdgeConfig[] }`
  - `PipelineSaveRequest`：`{ config_snapshot, change_log, version }`
  - `ValidationResult`：`{ valid: boolean, errors: ValidationError[] }`
  - `DryRunResult`：`{ success: boolean, execution_plan: NodeExecutionStep[], errors: DryRunError[] }`

### 2.3 管道列表页（5.3 管道列表页）

#### `features/pipeline/pages/PipelineListPage.tsx`

- [ ] **页面布局**：顶部标题"管道" + `[+ 新建管道]` 按钮 + `[导入...]` 下拉按钮
- [ ] **搜索/筛选栏**：搜索输入框（按名称模糊搜索）+ 状态下拉筛选（全部/草稿/已发布/已归档）
- [ ] **卡片网格**：响应式 grid（3 列 → 2 列 → 1 列），每张卡片为 `PipelineCard`
- [ ] **新建管道对话框**
  - 选项 1：空白管道（创建空管道 → 直接进入编辑视图）
  - 选项 2：从已有管道复制（选择源管道下拉 → 复制 config_snapshot → 命名 → 进入编辑视图）
  - 选项 3：从 JSON 导入（上传/粘贴 JSON → 校验格式 → 命名 → 进入编辑视图）
- [ ] **空状态**：无管道时显示引导文案 + 新建按钮
- [ ] **加载态**：卡片区域骨架屏（Ant Design Skeleton card）
- [ ] **错误态**：加载失败显示重试按钮
- [ ] **路由**：`/pipelines`，点击卡片或新建后 navigate 到 `/pipelines/:id/edit`

#### `features/pipeline/components/PipelineCard.tsx`

- [ ] **卡片内容**
  - 管道名称 + 版本号（如 `v3`）
  - 域数和节点数（如 `3 域 · 15 节点`）
  - 最近评估得分（如 `0.84 ✅`，绿色/黄色/灰色区分有/无评估）
  - 发布状态（如 `已发布: /search/med`，或 `已发布: 3 个端点`，或 `—`）
  - 底部操作按钮：`[编辑] [评估] [发布]`（三个快捷入口跳转到对应工作台视图）
- [ ] **交互**
  - hover 显示卡片阴影加深
  - 点击卡片标题跳转到编辑视图
  - 更多操作下拉菜单：`[重命名] [复制] [导出 JSON] [删除]`
  - 删除前确认弹窗："确定删除管道「XXX」及其全部版本历史？此操作不可撤销。"

### 2.4 管道工作台（5.4 管道工作台）

#### `features/pipeline/pages/PipelineWorkbench.tsx`

- [ ] **三视图切换容器**
  - 顶部 `WorkbenchToolbar`：`← 管道列表` + 管道名称 + 版本号 + 视图切换按钮 `[编辑] [评估] [发布]` + 右侧操作按钮
  - 根据 `activeView` 渲染对应视图组件：`EditView` | `EvaluateView` | `PublishView`
  - 切换视图不卸载未显示的视图组件（用 `display: none` 隐藏），保持编辑状态
  - 从编辑视图切出前如果 `isDirty=true`，弹出提示"有未保存的更改，是否保存？"
- [ ] **URL 路由匹配**
  - `/pipelines/:id/edit` → `activeView='edit'`
  - `/pipelines/:id/evaluate` → `activeView='evaluate'`
  - `/pipelines/:id/publish` → `activeView='publish'`
  - 直接访问 `/pipelines/:id` 默认跳转到 `/pipelines/:id/edit`
- [ ] **数据加载**
  - `useEffect` 中调用 `loadPipeline(id)` 初始化 store
  - 加载失败显示错误提示 + 返回列表按钮

#### `features/pipeline/components/WorkbenchToolbar.tsx`

- [ ] **左侧区域**
  - `← 管道列表` 返回按钮（navigate to `/pipelines`）
  - 管道名称（可双击内联编辑）+ 版本号标签
- [ ] **中央区域**
  - 三按钮组：`[编辑]` `[评估]` `[发布]`，高亮当前视图
- [ ] **右侧区域（编辑视图可见）**
  - `[保存]` 按钮（有未保存变更时显示蓝点提示）
  - `[干运行]` 按钮
  - 更多下拉：`[版本历史] [回滚...] [版本对比] [导出 JSON]`
  - 保存交互：点击 `[保存]` → 弹出变更日志输入对话框 → 确认后调用 `save()` API → 成功后显示新版本号 → 重置 `isDirty`
- [ ] **右侧区域（评估/发布视图）**：根据各自视图需要显示对应按钮

### 2.5 编辑视图（5.5 编辑视图）

#### `features/pipeline/components/Canvas/PipelineCanvas.tsx`

- [ ] **React Flow 集成**
  - 使用 `@xyflow/react` (≥12.0) 的 `<ReactFlow>` 组件
  - 传入自定义 `nodeTypes` 映射（见下方）
  - 传入自定义 `edgeTypes` 映射（见下方）
  - 使用 `useNodesState` + `useEdgesState` 管理 React Flow 节点和边
- [ ] **nodeTypes 映射**

  ```typescript
  const nodeTypes = {
    // 域容器
    domainContainer: DomainContainerNode,

    // 域内节点（查询理解 7 个 —— 使用 GenericNode + 类型参数）
    queryRewrite: GenericNode,
    synonymExpand: GenericNode,
    queryDecompose: GenericNode,
    termNormalize: GenericNode,
    intentClassify: GenericNode,
    stopwordFilter: GenericNode,
    queryExpand: GenericNode,

    // 域内节点（检索策略 5 个）
    bm25Search: GenericNode,
    vectorSearch: GenericNode,
    hybridSearch: GenericNode,
    multimodalSearch: GenericNode,
    resultFusion: GenericNode,

    // 域内节点（安全合规 3 个）
    sensitiveFilter: GenericNode,
    piiMask: GenericNode,
    contentAudit: GenericNode,

    // 域内节点（质量增强 4 个）
    rerank: GenericNode,
    dedup: GenericNode,
    hallucinationCheck: GenericNode,
    citationVerify: GenericNode,

    // 域内节点（性能优化 2 个）
    semanticCache: GenericNode,
    rateLimiter: GenericNode,

    // 域内节点（答案合成 1 个）
    structuredOutput: GenericNode,

    // 聚合层节点 6 个 —— 使用 AggregationNode
    queryAnalyzer: AggregationNode,    // 查询分析
    domainDispatch: AggregationNode,   // 域分发
    crossFusion: AggregationNode,      // 跨域融合
    crossDedup: AggregationNode,       // 跨域去重
    conflictDetect: AggregationNode,   // 冲突检测
    unifiedGenerate: AggregationNode,  // 统一生成

    // 复合节点
    compound: CompoundNode,
  };
  ```

- [ ] **edgeTypes 映射**

  ```typescript
  const edgeTypes = {
    dataFlow: DataFlowEdge,          // 数据流边（灰色实线）
    conditional: ConditionalEdge,    // 条件边（灰色虚线 + 条件标签）
    degradation: DegradationEdge,    // 降级边（橙色虚线 + 策略标签）
  };
  ```

- [ ] **画布功能**
  - `<Background />`——网格背景
  - `<MiniMap />`——缩略图导航
  - `<Controls />`——缩放/居中对齐/锁定控件
  - `fitView`——初始加载时自动适配视口
  - 缩放范围限制：25%–200%
- [ ] **事件处理**
  - `onNodesChange`——节点移动/删除/选中，同步到 store
  - `onEdgesChange`——边的增删改，同步到 store
  - `onConnect`——连线时创建边（检查合法性：聚合节点不可连入域容器、域内节点不可跨域直连）
  - `onDrop`——从 NodePanel 拖放节点到画布时创建节点
  - `onDragOver`——允许拖放到画布
  - `onNodeClick`——设置 `selectedNodeId`
  - `onPaneClick`——取消选中
  - `onNodeDoubleClick`——双击域容器折叠/展开；双击节点跳转属性面板
- [ ] **聚合管道特有**：画布顶部渲染 `[+ 添加业务域]` 按钮（仅当 `domains.length > 0` 或初次进入时可见）
- [ ] **性能**：React Flow 虚拟化渲染（仅渲染视口内节点），域容器折叠时不渲染内部子节点 DOM

#### `features/pipeline/components/NodePanel/NodePanel.tsx`

- [ ] **左侧面板布局**
  - 固定宽度约 240px，可折叠/展开（由右侧小箭头按钮控制）
  - 顶部搜索框：按名称过滤节点
- [ ] **节点分类折叠面板**（Ant Design Collapse）

  每个分类使用 Ant Design Collapse，拖拽标签使用 `draggable`：

  | 分类 | 包含节点 | 可拖入位置 |
  |------|---------|-----------|
  | **域内节点** | （折叠分组标题） | 不可直接拖入，展开后子项可拖 |
  | ↳ 查询理解 | query_rewrite, synonym_expand, query_decompose, term_normalize, intent_classify, stopword_filter, query_expand | 域容器内 |
  | ↳ 检索策略 | bm25_search, vector_search, hybrid_search, multimodal_search, result_fusion | 域容器内 |
  | ↳ 安全合规 | sensitive_filter, pii_mask, content_audit | 域容器内 |
  | ↳ 质量增强 | rerank, dedup, hallucination_check, citation_verify | 域容器内 |
  | ↳ 性能优化 | semantic_cache, rate_limiter | 域容器内 |
  | ↳ 答案合成 | structured_output | 域容器内 |
  | **聚合节点** | query_analyzer, domain_dispatch, cross_fusion, cross_dedup, conflict_detect, unified_generate | 画布空白区域（域外） |
  | **我的复合节点** | 从 compoundNodeLibrary 渲染 | 画布空白区域（域外） |

- [ ] **拖拽机制**
  - `onDragStart` 设置 `dataTransfer`：`{ nodeType, category: 'intra_domain' | 'aggregation' | 'compound', compoundId }`
  - 拖拽过程中高亮可放置区域（域容器高亮/聚合区域高亮）
  - 不可放置区域标红
- [ ] **节点标签**：每种节点显示中文名称 + 小图标 + 描述 tooltip

#### `features/pipeline/components/PropertyPanel/PropertyPanel.tsx`

- [ ] **右侧面板布局**
  - 固定宽度约 320px，可折叠/展开
  - 无选中节点时显示 "选择节点查看属性" 占位
- [ ] **动态表单渲染**
  - 根据 `selectedNodeId` 获取节点，再根据 `node.type` 选择对应的参数表单组件
  - 表单组件映射表 `NODE_PARAMETER_FORMS`（28 种）：

  | 节点类型 | 表单组件 | 文件路径 |
  |---------|---------|---------|
  | query_rewrite | QueryRewriteForm | `PropertyPanel/forms/QueryRewriteForm.tsx` |
  | synonym_expand | SynonymExpandForm | `PropertyPanel/forms/SynonymExpandForm.tsx` |
  | query_decompose | QueryDecomposeForm | `PropertyPanel/forms/QueryDecomposeForm.tsx` |
  | term_normalize | TermNormalizeForm | `PropertyPanel/forms/TermNormalizeForm.tsx` |
  | intent_classify | IntentClassifyForm | `PropertyPanel/forms/IntentClassifyForm.tsx` |
  | stopword_filter | StopwordFilterForm | `PropertyPanel/forms/StopwordFilterForm.tsx` |
  | query_expand | QueryExpandForm | `PropertyPanel/forms/QueryExpandForm.tsx` |
  | bm25_search | BM25SearchForm | `PropertyPanel/forms/BM25SearchForm.tsx` |
  | vector_search | VectorSearchForm | `PropertyPanel/forms/VectorSearchForm.tsx` |
  | hybrid_search | HybridSearchForm | `PropertyPanel/forms/HybridSearchForm.tsx` |
  | multimodal_search | MultimodalSearchForm | `PropertyPanel/forms/MultimodalSearchForm.tsx` |
  | result_fusion | ResultFusionForm | `PropertyPanel/forms/ResultFusionForm.tsx` |
  | sensitive_filter | SensitiveFilterForm | `PropertyPanel/forms/SensitiveFilterForm.tsx` |
  | pii_mask | PIIMaskForm | `PropertyPanel/forms/PIIMaskForm.tsx` |
  | content_audit | ContentAuditForm | `PropertyPanel/forms/ContentAuditForm.tsx` |
  | rerank | RerankForm | `PropertyPanel/forms/RerankForm.tsx` |
  | dedup | DedupForm | `PropertyPanel/forms/DedupForm.tsx` |
  | hallucination_check | HallucinationCheckForm | `PropertyPanel/forms/HallucinationCheckForm.tsx` |
  | citation_verify | CitationVerifyForm | `PropertyPanel/forms/CitationVerifyForm.tsx` |
  | semantic_cache | SemanticCacheForm | `PropertyPanel/forms/SemanticCacheForm.tsx` |
  | rate_limiter | RateLimiterForm | `PropertyPanel/forms/RateLimiterForm.tsx` |
  | structured_output | StructuredOutputForm | `PropertyPanel/forms/StructuredOutputForm.tsx` |
  | query_analyzer | QueryAnalyzerForm | `PropertyPanel/forms/QueryAnalyzerForm.tsx` |
  | domain_dispatch | DomainDispatchForm | `PropertyPanel/forms/DomainDispatchForm.tsx` |
  | cross_fusion | CrossFusionForm | `PropertyPanel/forms/CrossFusionForm.tsx` |
  | cross_dedup | CrossDedupForm | `PropertyPanel/forms/CrossDedupForm.tsx` |
  | conflict_detect | ConflictDetectForm | `PropertyPanel/forms/ConflictDetectForm.tsx` |
  | unified_generate | UnifiedGenerateForm | `PropertyPanel/forms/UnifiedGenerateForm.tsx` |

- [ ] **表单共性**
  - 每个表单组件接收 `{ config: NodeConfig, onChange: (config) => void }` props
  - 各类参数控件：
    - `model` 字段 → LLM 模型下拉选择器（从 `/api/v1/config/llm-models` 动态加载）
    - `prompt_template` 字段 → 提示词模板下拉选择器（从 `/api/v1/config/prompts` 加载，按节点类型过滤）
    - 数值参数 → InputNumber 或 Slider
    - 枚举参数 → Select 或 Radio.Group
    - 列表参数（如 `stop_words`）→ Tag + Input 组合
    - 开关参数 → Switch
    - JSON 参数 → Monaco Editor 代码编辑器（如 `routing_rules`）
  - 输入校验：实时验证参数合法性（范围、格式），非法时字段标红并显示错误提示
  - 帮助提示：每个参数旁显示 `Tooltip` 图标，hover 显示参数说明和默认值
  - 重置按钮：每个字段旁可一键恢复默认值（从 NODE_DEFAULTS 读取）
- [ ] **降级路径配置**（PropertyPanel 下统一区域）
  - Collapse 折叠面板："降级路径"
  - `DegradationConfig` 组件：
    - 允许选择降级策略：`skip`（跳过该节点）/ `use_cache`（使用缓存结果）/ `fallback_node`（回退到指定节点，下拉选择当前域其他节点）
    - 允许配置触发条件：超时阈值（ms）、最大重试次数、错误类型匹配
    - 降级策略选择后，画布上自动生成 DegradationEdge（橙色虚线）

#### `features/pipeline/components/DomainContainer/DomainContainerNode.tsx`

- [ ] **域容器节点**
  - 基于 React Flow 自定义节点实现
  - **折叠态**：显示域名称 + 节点数 badge + 状态灯（绿色=就绪/黄色=有警告/红色=有错误）+ 健康分数
  - **展开态**：显示域内子节点（子节点是独立 React Flow node，通过 `parentId` 绑定到域容器）
  - 双击标题区域切换折叠/展开
  - 宽度自适应内容（展开时最小 400px，折叠时约 200px）
- [ ] **防越界拖拽**
  - 域内节点的 `extent` 设置为 `'parent'`，React Flow 自动限制移动范围
  - 域内节点的 z-index 高于域容器，确保正确渲染
  - 聚合节点拖拽到域容器内 → 阻止（`isValidConnection` 检查 + 标红提示）
  - 域内节点拖拽到域容器外 → 阻止（extent: 'parent' + 标红提示）
- [ ] **域容器操作**
  - 右上角 `×` 删除按钮（点击弹出确认弹窗）
  - 双击标题栏弹出域属性编辑面板：域名称、绑定知识库下拉（过滤用户无权访问的库）、域权重（0–1 slider）、激活关键词（Tag + Input）
  - 更换知识库后，域内所有检索节点的 `knowledge_base_id` 自动更新
- [ ] **内部节点布局**
  - 展开时域内节点垂直排列，自动连线（根据节点添加顺序或手动连线）
  - 节点之间自动间距，超出域容器范围时域容器自动扩展高度

#### `features/pipeline/components/nodes/GenericNode.tsx`

- [ ] **通用节点模板**（域内 22 种节点共用）
  - 节点外观：圆角矩形、左侧颜色条（按分类着色）、中间图标 + 节点名称
  - 颜色映射（按分类区分）：查询理解=蓝色、检索策略=绿色、安全合规=红色、质量增强=紫色、性能优化=橙色、答案合成=金色
  - 节点类型标签（小字）：显示在节点名称下方，如 "查询改写" / "BM25 检索"
  - 输入/输出连接桩（Handle）：顶部 Source Handle、底部 Target Handle
  - 选中态：蓝色边框高亮
  - 错误态：红色边框 + 错误图标（校验失败时）
  - 降级态：左侧显示降级图标（绿色=已配置降级路径 / 灰色=未配置）
  - hover 态：显示节点类型详情 tooltip（输入 → 输出 + 主要参数摘要）

#### `features/pipeline/components/nodes/AggregationNode.tsx`

- [ ] **聚合层节点**（6 种聚合节点）
  - 与 GenericNode 外观一致，但：
    - 尺寸略大（聚合节点包含全局逻辑）
    - 左侧颜色条统一使用深蓝/青色（区分于域内节点）
    - 多个 Target Handle（每个域一个输入连接点，动态根据 `domains` 生成）
    - 单个 Source Handle（输出到下游聚合节点或最终合成）
  - 双击跳转属性面板

#### `features/pipeline/components/nodes/CompoundNode.tsx`

- [ ] **复合节点**
  - **折叠态**：显示复合节点名称 + 内部节点数 badge + 展开图标
  - **展开态**：显示内部子管道（域内节点 mini 版 + 连线），在 Group 节点内部渲染
  - 双击切换折叠/展开
  - 输入/输出 Handle 数量由内部子管道决定
  - 拖拽到画布前检查嵌套深度（≤3）
  - 右键菜单：`[展开/折叠] [编辑内部节点] [保存为复合节点] [从库中移除]`

#### `features/pipeline/components/edges/DataFlowEdge.tsx`

- [ ] **数据流边**
  - 灰色实线（`#8c8c8c`）、线宽 2px
  - 末端带方向箭头
  - hover 高亮蓝色
  - 选中态：线宽加粗 + 蓝色
  - 可选 delete 删除（选中后按 Delete 键或右键删除）
  - 右键菜单：`[删除边] [设为条件边] [设为降级边]`

#### `features/pipeline/components/edges/ConditionalEdge.tsx`

- [ ] **条件边**
  - 灰色虚线（`strokeDasharray: "5,5"`、颜色 `#8c8c8c`）
  - 中间显示条件标签（小型徽章显示条件表达式，hover 显示完整条件）
  - 标签背景色：白色底 + 边框
  - 选中条件边后，属性面板显示条件编辑器：支持 AND/OR 逻辑组合、数值比较、字符串匹配
  - 右键菜单：`[编辑条件] [删除边] [设为数据流边]`

#### `features/pipeline/components/edges/DegradationEdge.tsx`

- [ ] **降级边**
  - 橙色虚线（`strokeDasharray: "8,4"`、颜色 `#fa8c16`）
  - 中间显示降级策略标签（如 "降级: skip" / "降级: cache" / "降级: fallback → xxx"）
  - 标签背景色：浅橙色底 + 橙色边框
  - hover 显示完整降级配置摘要
  - 右键菜单：`[编辑降级配置] [删除降级边]`

#### 参数表单组件（`PropertyPanel/forms/` 下 28 个表单）

- [ ] 每个节点类型一个独立表单文件（见上表 `PropertyPanel/forms/XXXForm.tsx`）
- [ ] 共性要求见 PropertyPanel "表单共性" 一节
- [ ] 每个表单导出为默认组件，Props 类型：`{ config: NodeConfig; onChange: (config: NodeConfig) => void }`
- [ ] 表单布局：垂直排列，分组标题 + 分割线
- [ ] 参数标注层级标签：`[L0]` / `[L1]` / `[L2]` / `[L3]`（来自 01-pipeline-model 定义，仅 L2/L3 参数可编辑）

### 2.6 评估视图（嵌入，5.6）

- [ ] `features/pipeline/components/EvaluateView.tsx`
  - 复用 Phase 7 RAG 评估组件（`features/rag-eval/` 下的页面和组件）
  - 切换到评估视图时，自动以 `pipelineId` 作为筛选条件加载评估历史
  - 新建评估时，自动关联当前管道和当前版本
  - URL 路由：`/pipelines/:id/evaluate` + 可选子路由 `/pipelines/:id/evaluate/:runId`

### 2.7 发布视图（嵌入，5.7）

- [ ] `features/pipeline/components/PublishView.tsx`
  - 复用 Phase 4 发布配置面板
  - 配置搜索端点：自定义路径、认证方式、速率限制
  - 发布后生成搜索 URL，显示在发布视图中
  - URL 路由：`/pipelines/:id/publish`

---

## 3. 关键实现细节

### 3.1 React Flow 集成

- **依赖**：`@xyflow/react` ≥12.0（在 `package.json` 中声明）
- **自定义 nodeTypes**：通过 `nodeTypes` prop 传入映射对象，React Flow 根据节点 data 中的 `type` 字段选择渲染组件
- **自定义 edgeTypes**：通过 `edgeTypes` prop 传入映射对象
- **内置组件**：`<Background variant="dots" gap={12} size={1} />`、`<MiniMap nodeStrokeWidth={3} zoomable pannable />`、`<Controls showZoom showFitView showInteractive={false} />`
- **性能**：React Flow ≥12 内置虚拟化渲染（`onlyRenderVisibleElements`），域容器折叠时通过 `hidden` 属性隐藏内部节点（减少 DOM 渲染）
- **数据转换**：使用 `useConvertToFlow` 自定义 hook，将 store 中的 `domains + aggregationNodes + edges` 转换为 React Flow 的 `Node[] + Edge[]` 格式，包含 `position`、`type`、`data`、`parentId` 字段
- **undo/redo 与 React Flow 状态同步**：undo/redo 时通过 `setNodes` / `setEdges` 批量恢复 React Flow 内部状态

### 3.2 域容器（DomainContainer）

- **实现方式**：React Flow 自定义节点，type 为 `domainContainer`
- **折叠/展开**：
  - 折叠态：子节点的 `hidden: true`，域容器 `data.collapsed: true`，渲染紧凑标题
  - 展开态：子节点的 `hidden: false`，域容器 `data.collapsed: false`，渲染完整容器框
  - 切换通过双击事件触发，更新 store 中 `DomainConfig.collapsed` 字段
- **防越界**：
  - 域内节点设置 `extent: 'parent'`（React Flow 12 支持）
  - `isValidConnection` 回调中检查：源节点和目标节点是否在同一域内，或均不在域内（聚合节点连接聚合节点）
  - 拖拽 Overlay 标红：`onDragOver` 中根据 `dataTransfer` 中的 `category` 判断是否允许放置
- **域删除**：
  - 点击 × → Modal 确认："将同时移除该域的 X 个节点。此操作不可恢复，确认删除？"
  - 确认后删除域容器节点、域内所有子节点、及与这些节点关联的所有边
- **知识库绑定**：域属性面板中的知识库下拉调用 `getKnowledgeBases()` API，过滤用户无权访问的库

### 3.3 属性面板（PropertyPanel）

- **动态表单渲染**：`NODE_PARAMETER_FORMS[node.type]` 映射选择组件，React 动态渲染
- **表单组件模式**：每个表单文件导出默认组件，统一 Props 接口
- **配置变更传播**：表单 `onChange` → `pipelineWorkbenchStore.updateNodeConfig(nodeId, newConfig)` → 触发 snapshot
- **降级配置**：PropertyPanel 底部固定区域，不随节点类型变化，统一 `DegradationConfig` 组件
- **知识库下拉**：检索类节点的 `knowledge_base_id` 下拉调用 API，按租户 + 用户权限过滤
- **LLM 模型下拉**：`model` 参数的下拉选项从系统配置 API 动态加载
- **提示词模板下拉**：`prompt_template` 参数从系统配置 API 加载，按节点类型过滤可用模板列表

### 3.4 条件边渲染

- **实现**：React Flow 自定义 Edge 组件，type 为 `conditional`
- **虚线**：SVG `<path>` 使用 `strokeDasharray="5,5"`
- **条件标签**：`<EdgeLabelRenderer>` 渲染居中的 `<div>`，内容为条件表达式（如 `score > 0.8`），白色背景 + 灰色边框的小型徽章
- **条件编辑**：选中条件边后，PropertyPanel 显示条件编辑器：
  - 左侧字段下拉（从源节点输出字段中选择）
  - 中间操作符下拉（`>`, `<`, `==`, `>=`, `<=`, `!=`, `contains`, `in`）
  - 右侧值输入（数值输入框 或 文本输入）
  - 支持 AND/OR 组合多个条件
  - 实时预览生成的条件标签文本

### 3.5 降级边渲染

- **实现**：React Flow 自定义 Edge 组件，type 为 `degradation`
- **虚线**：SVG `<path>` 使用 `strokeDasharray="8,4"`、颜色 `#fa8c16`
- **策略标签**：`<EdgeLabelRenderer>` 渲染居中标签，如 `降级: skip` / `降级: cache` / `降级: fallback → query_rewrite`，浅橙色背景 + 橙色边框

### 3.6 撤销/重做

- **快照式实现**：
  - 每次操作（addNode, removeNode, updateNodeConfig, addEdge, removeEdge, addDomain, removeDomain, moveNodeToDomain）完成后调用 `snapshot()`
  - `snapshot()` 内部：`JSON.parse(JSON.stringify({ domains, aggregationNodes, edges }))` 深拷贝当前状态 → push 到 `undoStack`
  - 连续文本输入（如 PropertyPanel 中修改参数）使用防抖（300ms），防止频繁快照
- **undo**：`undoStack.pop()` → 恢复状态 → `redoStack.push(原状态)` → 更新 React Flow nodes/edges
- **redo**：`redoStack.pop()` → 恢复状态 → `undoStack.push(原状态)` → 更新 React Flow nodes/edges
- **栈深度限制**：`undoStack.length > 50` 时 `undoStack.shift()`（丢弃最早快照）
- **新操作重置 redo**：任何非 undo/redo 操作触发后清空 `redoStack`
- **键盘快捷键**：`Ctrl+Z` / `Cmd+Z` → undo，`Ctrl+Shift+Z` / `Cmd+Shift+Z` → redo

### 3.7 保存

- **保存流程**：
  1. 点击 `[保存]` 按钮（或 `Ctrl+S`）
  2. 前端校验：
     - 总节点数 ≤ 100（超限拒绝并高亮）
     - 管道配置 JSON 大小 ≤ 500 KB（超限提示精简）
     - 至少有一个域和一个节点（空管道可保存，但提示警告）
  3. 弹出变更日志输入对话框（Modal，多行文本输入框，非必填）
  4. 确认后调用 `savePipeline(pipelineId, { config_snapshot, change_log, version: currentVersion })`
  5. 后端做乐观锁检查：`version` 必须匹配数据库最新版本，不匹配则返回冲突错误，前端弹出 "其他用户已修改此管道，请刷新后重试"
  6. 保存成功后：更新 `pipelineVersion`、重置 `isDirty`、清空 `undoStack` 和 `redoStack`（只保留刚保存这一版）
- **自动增量版本号**：后端在保存时自动 `version+1`，前端不需要传期望版本号，仅传当前版本号做乐观锁锚点
- **变更日志**：保存对话框中可填写此次修改的简要说明，存入 `pipeline_versions.change_log`

### 3.8 干运行

- **交互**：
  1. 点击 `[干运行]` 按钮
  2. 弹出输入对话框：输入测试查询文本（单行或多行）
  3. 可选项：输入 API 参数覆盖（L3 白名单参数）
  4. 调用 `dryRunPipeline(pipelineId, config_snapshot, { query, params })`
  5. 结果显示：
     - 编译成功 → 绿色提示 + 执行计划列表（节点顺序 + 预估耗时）
     - 编译失败 → 红色提示 + 错误节点列表 + 画布上高亮问题节点（红色边框 + 闪烁动画）
     - 执行超时 → 黄色警告 + 部分执行结果
- **Loading 态**：干运行期间显示进度条（节点逐个执行动画）

### 3.9 版本历史与对比

- **版本历史面板**：从 WorkbenchToolbar 更多菜单进入，抽屉/Modal 展示版本列表（时间倒序）
- **版本对比**：选择两个版本 → 并排显示差异：
  - 新增节点（绿色高亮）
  - 删除节点（红色删除线）
  - 参数变更（节点下方显示旧值 → 新值，黄色底色）
  - 新增/删除边（绿色/红色高亮）
- **回滚**：选择历史版本 → 确认 → 创建新版本（复制历史版本 config_snapshot + version+1），而不是覆盖

### 3.10 聚合管道域管理

- **[+ 添加业务域] 按钮位置**：画布顶部居中（或画布空白区域 overlay 引导按钮）
- **域创建抽屉**：从右侧滑入，表单字段：
  - 域名称（必填，文本输入，max 32 字符）
  - 绑定知识库（下拉，调用 `/api/v1/knowledge-bases` 加载，按用户权限过滤）
  - 域权重（Slider，默认 1.0，聚合融合时使用）
  - 激活关键词（Tag + Input，用于域路由匹配，如 `["心血管", "心脏", "血压"]`）
- **域创建后行为**：
  - `pipelineWorkbenchStore.addDomain(domainConfig)` → 画布新增空域容器（折叠态）
  - 聚合层自动添加该域对应的连接点（`domainDispatch` 节点增加一个 Target Handle）
- **域删除二次确认**：提示 "将同时移除该域的 X 个节点"，并高亮受影响的聚合边
- **知识库变更自动更新**：更换知识库后，遍历该域内所有检索节点，设置 `config.knowledge_base_id = newKbId`

---

## 4. 测试策略

### 4.1 组件测试（Vitest + React Testing Library）

#### PipelineCard 渲染

- [ ] **TC-5.1.1**：卡片显示管道名称、版本号、域数/节点数、评估得分、发布状态
- [ ] **TC-5.1.2**：无评估记录时显示 "最近评估: —"
- [ ] **TC-5.1.3**：无发布时显示 "已发布: —"
- [ ] **TC-5.1.4**：点击 `[编辑]` 按钮 → navigate 到 `/pipelines/:id/edit`
- [ ] **TC-5.1.5**：点击 `[评估]` 按钮 → navigate 到 `/pipelines/:id/evaluate`
- [ ] **TC-5.1.6**：点击 `[发布]` 按钮 → navigate 到 `/pipelines/:id/publish`
- [ ] **TC-5.1.7**：更多菜单中点击 `[删除]` → 弹出确认弹窗 → 确认后调用删除 API

#### NodePanel 拖拽

- [ ] **TC-5.2.1**：28 种节点全部渲染，分类折叠面板展开/收起正常
- [ ] **TC-5.2.2**：拖拽节点标签时 `dataTransfer` 正确设置 `nodeType` 和 `category`
- [ ] **TC-5.2.3**：搜索框中输入 "BM25" → 节点列表仅显示 BM25 检索，其他节点隐藏
- [ ] **TC-5.2.4**："我的复合节点"分类从 store 加载，无复合节点时显示"暂无复合节点"

#### PropertyPanel 动态表单

- [ ] **TC-5.3.1**：选中 BM25 检索节点 → 右侧显示 BM25SearchForm（top_k、k1、b 参数输入）
- [ ] **TC-5.3.2**：选中向量检索节点 → 右侧显示 VectorSearchForm（embedding_model 下拉、top_k、similarity_threshold slider）
- [ ] **TC-5.3.3**：修改参数 → `onChange` 触发 → store 中节点 config 更新
- [ ] **TC-5.3.4**：输入非法参数值（top_k = -1）→ 字段标红 + 错误提示
- [ ] **TC-5.3.5**：点击参数旁 Tooltip → 显示参数说明和默认值
- [ ] **TC-5.3.6**：无选中节点时 → 显示 "选择节点查看属性" 占位

#### GenericNode / AggregationNode / CompoundNode

- [ ] **TC-5.4.1**：GenericNode 渲染正确节点名称、分类颜色条、图标
- [ ] **TC-5.4.2**：AggregationNode 渲染多个 Target Handle（动态根据域数量）
- [ ] **TC-5.4.3**：CompoundNode 折叠态显示内部节点数 badge，展开态显示内部节点
- [ ] **TC-5.4.4**：所有节点 hover 时显示详情 tooltip

#### 边渲染

- [ ] **TC-5.5.1**：DataFlowEdge 渲染灰色实线 + 方向箭头
- [ ] **TC-5.5.2**：ConditionalEdge 渲染灰色虚线 + 条件标签
- [ ] **TC-5.5.3**：DegradationEdge 渲染橙色虚线 + 策略标签
- [ ] **TC-5.5.4**：选中边后出现删除选项（Delete 键或右键菜单）

### 4.2 集成测试

#### 完整编辑工作流

- [ ] **TC-5.6.1**：从管道列表页新建空白管道 → 自动进入编辑视图 → 画布为空
- [ ] **TC-5.6.2**：添加域容器（点击 `[+ 添加业务域]`）→ 画布出现域容器 → 聚合节点自动添加连接点
- [ ] **TC-5.6.3**：从 NodePanel 拖拽 "BM25 检索" 到域容器内 → 节点创建成功
- [ ] **TC-5.6.4**：拖拽 "向量检索" 到域容器内 → 从 BM25 节点连线到向量检索节点 → 边创建成功
- [ ] **TC-5.6.5**：选中 BM25 节点 → 修改 top_k=20 → 保存 → 验证后端存储的 config_snapshot 中 top_k=20
- [ ] **TC-5.6.6**：保存后版本号从 v1 变为 v2，变更日志写入数据库
- [ ] **TC-5.6.7**：撤销 (Ctrl+Z) → BM25 节点回到 top_k=10 → isDirty=true
- [ ] **TC-5.6.8**：重做 (Ctrl+Shift+Z) → BM25 节点 top_k=20 → isDirty=true

#### 域容器交互

- [ ] **TC-5.7.1**：双击域容器 → 折叠/展开切换
- [ ] **TC-5.7.2**：拖拽域内节点到域外 → 阻止 + 画布标红提示
- [ ] **TC-5.7.3**：拖拽聚合节点到域内 → 阻止 + 域容器标红提示
- [ ] **TC-5.7.4**：点击域容器 × 删除 → 弹出确认弹窗（显示节点数量）→ 确认 → 域和内部节点全部删除
- [ ] **TC-5.7.5**：双击域容器标题 → 弹出域属性面板 → 更换知识库 → 域内检索节点 knowledge_base_id 自动更新

#### 干运行

- [ ] **TC-5.8.1**：构建完整管道 → 点击干运行 → 输入测试查询 → 编译成功显示执行计划
- [ ] **TC-5.8.2**：构建有环管道（A→B→A）→ 干运行 → 编译失败 → 画布上 A 和 B 节点标红

#### 性能约束

- [ ] **TC-5.9.1**：添加第 21 个域 → 阻止 + 提示 "单管道最多 20 个业务域"
- [ ] **TC-5.9.2**：向单域添加第 31 个节点 → 阻止 + 提示 "单个域最多 30 个节点"
- [ ] **TC-5.9.3**：管道总节点数超过 100 → 保存时校验失败，拒绝保存

### 4.3 Canvas 交互测试

- [ ] **TC-5.10.1**：从 NodePanel 拖拽节点到画布空白区域（聚合节点） → 创建成功
- [ ] **TC-5.10.2**：从 NodePanel 拖拽节点到域容器内（域内节点） → 创建成功
- [ ] **TC-5.10.3**：圈选多个节点 → 拖动 → 多节点一起移动
- [ ] **TC-5.10.4**：从节点 Handle 拖线到另一个节点 Handle → 创建 DataFlowEdge
- [ ] **TC-5.10.5**：选中节点 → 按 Delete → 节点和关联边一起删除
- [ ] **TC-5.10.6**：选中边 → 按 Delete → 边删除
- [ ] **TC-5.10.7**：Ctrl+Z 撤销删除节点 → 节点和边恢复
- [ ] **TC-5.10.8**：Ctrl+Z 撤销添加边 → 边消失

### 4.4 关键测试场景（至少 8 个）

| # | 场景 | 步骤 | 验证点 |
|---|------|------|--------|
| 1 | **新建完整管道并保存** | 新建管道 → 添加域 → 添加检索节点 → 添加聚合节点 → 连线 → 保存 | 保存成功、版本 v1、变更日志已记录 |
| 2 | **多域聚合管道** | 添加 3 个域 → 每个域内添加检索节点 → 聚合节点连接所有域 → 保存 | 3 个域容器并存、聚合节点有 3 个输入 Handle |
| 3 | **参数修改 + 撤销 + 重做** | 选中节点 → 修改 3 个参数 → Ctrl+Z×3 → Ctrl+Shift+Z×3 | 逐次撤销/重做、参数值正确恢复 |
| 4 | **条件边配置** | 添加 2 个节点 → 连线 → 右键 "设为条件边" → 编辑条件 score>0.8 | 边变为虚线、标签显示 "score > 0.8" |
| 5 | **降级路径配置** | 选中节点 → 属性面板配置降级路径 "skip" → 保存 | 画布出现橙色虚线降级边、标签显示 "降级: skip" |
| 6 | **域删除** | 创建包含 5 个节点的域 → 点击删除域 → 确认弹窗 → 确认 | 域和 5 个节点全部删除、聚合节点 Handle 同步移除 |
| 7 | **版本对比** | 保存 v1 → 添加节点 → 保存 v2 → 版本对比工具选择 v1 vs v2 | 高亮显示新增节点和参数变更差异 |
| 8 | **三视图切换不丢失状态** | 编辑视图修改参数 → 切到评估视图 → 切回编辑视图 | 修改的参数值保持、isDirty=true |
| 9 | **干运行验证** | 构建管道 → 点击干运行 → 输入查询 → 等待结果 | 编译成功显示执行计划、失败标红节点 |
| 10 | **乐观锁冲突** | 用户 A 加载 v1 → 用户 B 保存 v2 → 用户 A 尝试保存 | 后端拒绝、前端提示冲突 |

---

## 5. 验收检查点

### 5.1 管道列表页

- [ ] 管道列表页卡片视图展示正确，管道名/版本/域数/最近评估得分/发布状态均可见
- [ ] 新建管道后自动进入编辑视图，画布为空（或选中模板）
- [ ] 搜索功能按名称过滤管道
- [ ] 状态筛选（全部/草稿/已发布）正常工作
- [ ] 管道卡片操作菜单（重命名/复制/导出 JSON/删除）功能正常

### 5.2 三视图工作台

- [ ] 编辑/评估/发布三视图通过顶部工具栏切换，切换不丢失编辑状态
- [ ] 从编辑视图点击"评估"→ 切换到评估视图，自动加载该管道的评估历史
- [ ] 从编辑视图点击"发布"→ 切换到发布视图
- [ ] URL 路径与视图状态同步：`/pipelines/:id/edit` / `/evaluate` / `/publish`
- [ ] 编辑视图有未保存变更时切换到其他视图，弹出提示

### 5.3 编辑视图——画布

- [ ] React Flow 画布正常渲染：nodes、edges、background、minimap、controls
- [ ] 缩放范围限制在 25%–200%
- [ ] Minimap 显示管道全貌缩略图
- [ ] 域容器折叠/展开正常
- [ ] 域内节点不可拖到域外（阻止并标红）
- [ ] 聚合节点不可拖到域内（阻止并标红）
- [ ] 条件边以虚线渲染，条件标签正确显示
- [ ] 降级边以橙色虚线渲染，策略标签正确显示
- [ ] 聚合管道画布顶部显示 `[+ 添加业务域]` 按钮
- [ ] 域创建时知识库下拉自动过滤用户无权访问的库
- [ ] 删除域时二次确认，提示将同时移除的节点数
- [ ] 更换域的绑定知识库后，域内检索节点自动更新 knowledge_base_id

### 5.4 编辑视图——节点面板

- [ ] 28 种节点全部渲染，按分类折叠
- [ ] 节点可拖拽放置到画布（域内节点 → 域容器内，聚合节点 → 空白区域，复合节点 → 空白区域）
- [ ] 搜索框过滤节点列表
- [ ] "我的复合节点"列表从后端加载

### 5.5 编辑视图——属性面板

- [ ] 选中节点后右侧属性面板显示该节点类型的所有可配置参数
- [ ] 28 种节点类型均有对应参数表单
- [ ] 参数修改实时生效、实时校验
- [ ] 降级路径配置区域正确渲染
- [ ] LLM 模型下拉、知识库下拉、提示词模板下拉选项从后端 API 动态加载
- [ ] 参数旁 Tooltip 显示参数说明和默认值
- [ ] 重置按钮恢复默认值

### 5.6 保存与版本

- [ ] 管道保存后版本号自增
- [ ] 保存时变更日志对话框可输入说明并持久化
- [ ] 乐观锁冲突时前端提示用户刷新重试
- [ ] 版本历史面板显示所有历史版本
- [ ] 版本对比高亮两个版本的节点差异和参数差异
- [ ] 回滚功能创建新版本（不覆盖历史版本）

### 5.7 干运行

- [ ] 干运行结果显示编译成功/失败
- [ ] 失败时高亮问题节点
- [ ] 成功时显示执行顺序

### 5.8 撤销/重做

- [ ] Ctrl+Z 撤销最近操作，Ctrl+Shift+Z 重做
- [ ] 撤销栈最大深度 50 步
- [ ] 新操作清空重做栈
- [ ] 连续文本输入防抖 300ms 后创建快照

### 5.9 性能约束

- [ ] 单管道域数超过 20 时阻止添加
- [ ] 单域节点数超过 30 时阻止添加
- [ ] 总节点数超过 100 时拒绝保存
- [ ] 复合节点嵌套超过 3 层时阻止创建
- [ ] 管道配置 JSON 超过 500KB 时提示精简
- [ ] 大管道（>50 节点）时画布不卡顿（React Flow 虚拟化生效）
- [ ] 域容器折叠时内部节点不渲染 DOM

### 5.10 异常处理

- [ ] 管道加载失败时显示错误提示 + 返回列表按钮
- [ ] 保存失败时显示错误详情 + 保留编辑内容
- [ ] 网络断开时操作按钮置灰 + 提示 "网络不可用"
- [ ] API 超时时提示 "请求超时，请重试"

### 5.11 前端代码规范

- [ ] 所有组件遵循前端目录结构约定（`features/pipeline/` 下按 pages/components/hooks/stores 组织）
- [ ] 无直接 Pydantic/BaseModel 定义（前端实体类型在 `entities/` 目录下使用 TypeScript interface）
- [ ] 无 `any` 类型（TypeScript 严格模式）
- [ ] API 客户端在 `api/pipeline/` 下集中管理
- [ ] 状态管理使用 Zustand（`pipelineWorkbenchStore` + `pipelineListStore`）
- [ ] 所有注释全中文

---

## 附录 A：文件清单

| # | 文件 | 类型 |
|---|------|------|
| 1 | `features/pipeline/stores/pipelineWorkbenchStore.ts` | 新建 |
| 2 | `features/pipeline/stores/pipelineListStore.ts` | 新建 |
| 3 | `api/pipeline/pipeline.ts` | 新建 |
| 4 | `features/pipeline/pages/PipelineListPage.tsx` | 新建 |
| 5 | `features/pipeline/components/PipelineCard.tsx` | 新建 |
| 6 | `features/pipeline/pages/PipelineWorkbench.tsx` | 新建 |
| 7 | `features/pipeline/components/WorkbenchToolbar.tsx` | 新建 |
| 8 | `features/pipeline/components/Canvas/PipelineCanvas.tsx` | 新建 |
| 9 | `features/pipeline/components/Canvas/useConvertToFlow.ts` | 新建 |
| 10 | `features/pipeline/components/NodePanel/NodePanel.tsx` | 新建 |
| 11 | `features/pipeline/components/PropertyPanel/PropertyPanel.tsx` | 新建 |
| 12 | `features/pipeline/components/DomainContainer/DomainContainerNode.tsx` | 新建 |
| 13 | `features/pipeline/components/nodes/GenericNode.tsx` | 新建 |
| 14 | `features/pipeline/components/nodes/AggregationNode.tsx` | 新建 |
| 15 | `features/pipeline/components/nodes/CompoundNode.tsx` | 新建 |
| 16 | `features/pipeline/components/edges/DataFlowEdge.tsx` | 新建 |
| 17 | `features/pipeline/components/edges/ConditionalEdge.tsx` | 新建 |
| 18 | `features/pipeline/components/edges/DegradationEdge.tsx` | 新建 |
| 19 | `features/pipeline/components/EvaluateView.tsx` | 新建 |
| 20 | `features/pipeline/components/PublishView.tsx` | 新建 |
| 21–48 | `features/pipeline/components/PropertyPanel/forms/*Form.tsx` (28 个) | 新建 |
| 49 | `entities/pipeline/types.ts` | 新建 |
| 50 | `router/` 路由新增 `/pipelines` 相关路由 | 改造 |
| 51 | `package.json` 新增 `@xyflow/react` 依赖 | 改造 |

**合计**：约 25 个新建文件 + 2 个改造文件

## 附录 B：关键技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| `@xyflow/react` | ≥12.0 | 管道编辑器画布 |
| `zustand` | 5.x | 状态管理（pipelineWorkbenchStore, pipelineListStore） |
| `antd` | 6.x | UI 组件库（Card, Collapse, Modal, Form, Select, Slider, Tag 等） |
| `@ant-design/icons` | — | 节点图标 |
| `react-router-dom` | 7.x | SPA 路由（/pipelines...） |
| `@tanstack/react-query` | 5.x | 服务端状态管理（管道列表/详情的缓存和重新获取） |
| `@monaco-editor/react` | — | JSON 参数编辑（routing_rules 等复杂参数） |

## 附录 C：与后端 Phase 3/4 的接口契约

| 前端功能 | 后端端点 | Phase |
|---------|---------|-------|
| 管道 CRUD | `GET/POST/PUT/DELETE /api/v1/pipelines` | Phase 3 §3.14 |
| 保存（自增版本） | `PUT /api/v1/pipelines/:id/save` | Phase 3 §3.14 |
| 版本历史 | `GET /api/v1/pipelines/:id/versions` | Phase 3 §3.14 |
| 版本对比 | `GET /api/v1/pipelines/:id/versions/compare` | Phase 3 §3.14 |
| 回滚 | `POST /api/v1/pipelines/:id/versions/:version/rollback` | Phase 3 §3.14 |
| 校验 | `POST /api/v1/pipelines/:id/validate` | Phase 3 §3.14 |
| 干运行 | `POST /api/v1/pipelines/:id/dry-run` | Phase 3 §3.14 |
| 复合节点 CRUD | `GET/POST/DELETE /api/v1/compound-nodes` | Phase 3 §3.14 |
| 知识库列表 | `GET /api/v1/knowledge-bases` | Phase 2 §2.11 |
| LLM 模型列表 | `GET /api/v1/config/llm-models` | Phase 1 基础设施 |
| 提示词模板列表 | `GET /api/v1/config/prompts` | Phase 1 基础设施 |
| 搜索 API | `POST /api/v1/search` | Phase 4 §4.5 |
| 发布端点管理 | `POST /api/v1/pipelines/:id/publish` | Phase 4 §4.5 |
| 评估历史 | `GET /api/v1/pipelines/:id/evaluations` | Phase 7 |
