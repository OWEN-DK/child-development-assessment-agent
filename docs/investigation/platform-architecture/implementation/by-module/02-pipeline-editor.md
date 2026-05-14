# 02 — 管道编辑器 · 实现规格

> **关联需求**：[02-pipeline-editor.md](../requirements/02-pipeline-editor.md)
> **依赖模块**：[01-pipeline-model-and-engine.md](../requirements/01-pipeline-model-and-engine.md)（节点定义、配置格式、API 端点）
> **联动模块**：[05-publishing](./05-search-api.md)（发布视图消费）、[06-rag-evaluation](./06-rag-evaluation.md)（评估视图消费）
> **目标文件**：
> - `frontend/src/features/pipeline/` — 管道编辑器全部前端代码
> - `frontend/src/api/pipeline.ts` — 管道 API 客户端
> - `frontend/src/entities/pipeline/types.ts` — 管道实体类型

---

## 1. 前端路由与页面树

### 1.1 路由注册

```typescript
// frontend/src/router/index.tsx 中注册
{
  path: '/pipelines',
  element: <PipelineListPage />,
}
{
  path: '/pipelines/:id',
  element: <PipelineWorkbench />,
}
{
  path: '/pipelines/:id/evaluate/:runId',
  element: <EvalDetailPage />,
}
```

`PipelineWorkbench` 内部根据 URL 查询参数 `?view=edit|evaluate|publish` 控制当前激活视图。无参数时默认 `edit`。

### 1.2 页面层级与组件树

```
PipelineListPage                      # 路由 /pipelines
├── PageHeader                        # 页面标题 + [新建管道] [导入]
├── PipelineSearchFilter              # 搜索框 + 状态下拉过滤
└── PipelineCardGrid                  # CSS Grid 卡片布局
    └── PipelineCard[]                # 单张管道卡片

PipelineWorkbench                     # 路由 /pipelines/:id
├── WorkbenchToolbar                  # 顶部工具栏：左侧面包屑/管道名/版本号，右侧视图切换 + 操作按钮
├── EditView                          # view=edit
│   ├── NodePanel                     # 左侧节点面板（可折叠）
│   │   ├── PanelSearch               # 节点搜索过滤
│   │   └── NodeCategoryGroup[]       # 分类折叠面板
│   │       └── DraggableNodeItem[]   # 可拖拽节点项
│   ├── PipelineCanvas                # 中间 React Flow 画布
│   │   ├── DomainContainer[]         # 域容器（展开/折叠）
│   │   │   ├── DomainHeader          # 域名称 + 节点数 + 状态灯 + 折叠/删除按钮
│   │   │   └── 域内节点 (GenericNode[])
│   │   ├── AggregationNode[]         # 聚合层节点（独立于域容器）
│   │   ├── CompoundNode[]            # 复合节点（展开/折叠）
│   │   ├── Edge[]                    # 数据流边 / 条件边 / 降级边
│   │   ├── MiniMap                   # 小地图
│   │   ├── Background                # 背景网格
│   │   └── Controls                  # 缩放控件
│   └── PropertyPanel                 # 右侧属性面板（可折叠）
│       ├── NodePropertyForm          # 选中节点时的动态配置表单
│       ├── EdgePropertyForm          # 选中边时的边类型/条件/降级表单
│       ├── DomainPropertyForm        # 域属性配置表单
│       ├── DegradationTab            # 节点降级路径配置
│       └── EmptyState                # 未选中时的"点击节点查看属性"
├── EvaluateView                      # view=evaluate → 见 06-rag-evaluation 实现规格
│   ├── EvalRunList                   # 评估历史表格
│   └── EvalRunDrawer                 # 新建评估抽屉
└── PublishView                       # view=publish → 见 05-search-api 实现规格
    ├── PublishConfigForm             # 发布配置表单
    └── CurlExample                   # 调用示例

EvalDetailPage                        # 路由 /pipelines/:id/evaluate/:runId
├── EvalDetailHeader                  # 面包屑 + 评估名称 + 管道版本 + 角色 + 得分 + [导出] [对比]
├── EvalScoreOverview                 # 综合得分 + 通过率 + MRR + NDCG + P95 延迟
├── DomainContribChart                # 域贡献度柱状图
├── LayerScorePanel[]                 # L1/L2/L3 指标展开面板
├── DiagnosisPanel                    # 六层诊断，每层可展开
├── InlineTuningCard[]                # 内联调优建议卡片
└── BadCaseTable                      # 失败用例表格
```

---

## 2. 组件规格

### 2.1 PipelineCard

卡片组件，展示管道摘要信息。

```typescript
interface PipelineCardProps {
  pipeline: PipelineSummary;
  onEdit: (id: string) => void;
  onEvaluate: (id: string) => void;
  onPublish: (id: string) => void;
  onDelete: (id: string) => void;
}

interface PipelineSummary {
  id: string;
  name: string;
  version: number;
  type: 'aggregation' | 'single_domain';
  domainCount: number;
  nodeCount: number;
  lastEvalScore: number | null;
  publishedUrl: string | null;
  updatedAt: string;
}
```

**内部状态**：`deleteConfirmVisible: boolean`

**行为规格**：
- 卡片为 Ant Design `Card`，`onClick` 进入编辑视图
- 显示管道名称（粗体）、版本徽章（`v3`）、域数/节点数、最近评估得分（绿色 if ≥0.7，黄色 if ≥0.4，红色 < 0.4）、发布状态（已发布显示 URL 路径，未发布显示 `—`）
- 底部 3 个操作按钮：`[编辑]` `[评估]` `[发布]`，分别触发 `onEdit`/`onEvaluate`/`onPublish`
- 卡片右上角 `Dropdown` 菜单：删除（二次确认）、复制管道、导出 JSON
- 评分小于 0.4 时卡片边框显示警告色

---

### 2.2 PipelineCanvas

React Flow 画布包装器。

```typescript
interface PipelineCanvasProps {
  nodes: Node[];
  edges: Edge[];
  domains: DomainConfig[];
  selectedNodeId: string | null;
  selectedDomainId: string | null;
  onNodesChange: OnNodesChange;
  onEdgesChange: OnEdgesChange;
  onConnect: OnConnect;
  onNodeClick: (nodeId: string) => void;
  onDomainClick: (domainId: string) => void;
  onNodeDragStop: (nodeId: string, position: XYPosition) => void;
  onDomainPositionChange: (domainId: string, position: XYPosition) => void;
  onAddDomain: () => void;       // 聚合管道才有
  zoomRange: [number, number];   // [0.25, 2.0]
}
```

**内部状态**：无（受控组件，状态由 store 管理）

**行为规格**：
- 使用 `@xyflow/react` 的 `<ReactFlow>` 组件
- 注册自定义 `nodeTypes`：`{ domainContainer: DomainContainer, genericNode: GenericNode, aggregationNode: AggregationNode, compoundNode: CompoundNode }`
- 注册自定义 `edgeTypes`：`{ dataFlow: DataFlowEdge, conditional: ConditionalEdge, degradation: DegradationEdge }`
- 内嵌 `<MiniMap>`（右下角）、`<Background>`（网格）、`<Controls>`（缩放）
- 聚合管道类型时，画布顶部渲染 `[+ 添加业务域]` 按钮（非 React Flow 节点，是画布上层的绝对定位元素）
- `onConnect` 回调中校验边类型兼容性：数据流边 → 来源和目标不能跨层级（域内→域内、聚合→聚合），条件边 → 来源节点支持条件路由的节点类型，降级边 → 任意节点都可出降级边
- 连线时显示可用端口（source handle 为右侧圆点，target handle 为左侧圆点）
- 删除边：点击边 → 弹出删除确认（显示边类型和条件/降级策略）→ 确认后移除
- 拖拽节点时校验域约束：域内节点不可拖到域容器外，聚合节点不可拖到域容器内；拖拽到非法区域时节点回弹到原始位置并短暂标红（300ms）

---

### 2.3 NodePanel

左侧节点面板。

```typescript
interface NodePanelProps {
  collapsed: boolean;
  onToggleCollapse: () => void;
  compoundNodeLibrary: CompoundNode[];
}

interface DraggableNodeItemProps {
  nodeTypeId: string;         // 如 "bm25_search"
  nodeTypeLabel: string;      // 如 "BM25 检索"
  nodeCategory: string;       // 如 "检索策略"
  icon: ReactNode;
}
```

**内部状态**：`searchKeyword: string`、`expandedCategories: Set<string>`

**行为规格**：
- 顶部搜索框：输入关键词实时过滤节点项（匹配 `nodeTypeId` 或 `nodeTypeLabel`）
- 按 7 个分类分组，每组为可折叠面板：
  1. **域内节点**（默认展开）
  2. **查询理解**（7 种）
  3. **检索策略**（5 种）
  4. **安全合规**（3 种）
  5. **质量增强**（4 种）
  6. **性能优化**（2 种）
  7. **答案合成**（1 种）
  8. **聚合节点**（6 种）
  9. **我的复合节点**（默认折叠，无复合节点时隐藏）
- 每个 `DraggableNodeItem` 支持 HTML5 drag，`onDragStart` 设置 `dataTransfer`：
  ```typescript
  event.dataTransfer.setData('application/reactflow-node-type', nodeTypeId);
  event.dataTransfer.effectAllowed = 'move';
  ```
- 聚合节点拖入域容器内时阻止；域内节点拖到聚合区域时阻止
- `我的复合节点` 分组从 store 的 `compoundNodeLibrary` 中读取，每个复合节点也支持拖拽到画布（拖入后展开为内部节点组）
- 面板宽度 240px，可通过拖拽右侧边界调整宽度（180px–360px），默认折叠到 0（点击面板外的缩进按钮展开）

---

### 2.4 PropertyPanel

右侧属性面板。

```typescript
interface PropertyPanelProps {
  selectedNodeId: string | null;
  selectedEdgeId: string | null;
  selectedDomainId: string | null;
  nodes: Node[];
  edges: Edge[];
  domains: DomainConfig[];
  onNodeConfigChange: (nodeId: string, config: Record<string, unknown>) => void;
  onEdgeConfigChange: (edgeId: string, config: Record<string, unknown>) => void;
  onDomainConfigChange: (domainId: string, config: Record<string, unknown>) => void;
  onDeleteNode: (nodeId: string) => void;
  onDeleteEdge: (edgeId: string) => void;
  collapsed: boolean;
  onToggleCollapse: () => void;
}
```

**内部状态**：无（受控组件，由 store 管理实际值，面板仅渲染表单并触发回调）

**行为规格**：
- `selectedNodeId` 非空 → 渲染 `NodePropertyForm`
- `selectedEdgeId` 非空 → 渲染 `EdgePropertyForm`
- `selectedDomainId` 非空 → 渲染 `DomainPropertyForm`
- 都为 null → 渲染 `EmptyState`："点击画布上的节点查看属性"
- 面板宽度 280px，可通过拖拽左侧边界调整（220px–400px），默认折叠到 0
- 节点属性表单为动态表单：根据 `nodeTypeId` 从节点定义列表中查找该类型的 `config_fields`，动态生成表单项
  - 每个字段包含：`name`、`type`（string/number/boolean/enum/object）、`default`、`description`、`validation`
  - `model` 类型字段渲染为下拉选择（从 LLM 模型列表加载）
  - `prompt_template` 类型字段渲染为下拉选择（从提示词模板列表加载）
  - 枚举类型渲染为 `Select`
  - 对象类型渲染为 JSON 编辑器（`TextArea` + JSON 校验）
- 节点属性表单底部显示节点 ID、节点类型标签、[删除节点]（红色按钮，二次确认）
- 边属性表单显示：边类型（数据流/条件/降级）、条件表达式（仅条件边可见）、降级策略（仅降级边可见，4 个选项：skip_node/reroute/degrade_cache/abort）
- 域属性表单（见 `DomainPropertyForm` 子组件）：域名称、知识库选择、域权重（0-1 slider）、激活关键词编辑

**NodePropertyForm 子组件**：

```typescript
interface NodePropertyFormProps {
  nodeId: string;
  nodeType: string;
  nodeConfig: Record<string, unknown>;
  onChange: (config: Record<string, unknown>) => void;
  onDelete: () => void;
}
```

动态渲染逻辑：从 `NODE_TYPE_DEFINITIONS`（常量）中查找 `nodeType` 对应的 `config_fields` 数组，遍历字段生成对应 Ant Design `Form.Item`：

| 字段类型 | 渲染控件 | 校验规则 |
|---------|---------|---------|
| `string` | `Input` | 非空 + 长度限制 |
| `integer` | `InputNumber` | 最小/最大值 |
| `float` | `InputNumber` step=0.01 | 最小/最大值 |
| `boolean` | `Switch` | — |
| `enum` | `Select` | `options` 为 `field.enum_values` |
| `model` | `Select` + 异步加载 LLM 模型列表 | — |
| `prompt_template` | `Select` + 异步加载提示词模板列表 | — |
| `list` | `Select` mode="tags" | — |
| `json` | `Input.TextArea` + JSON 实时校验 | JSON 合法 |

---

### 2.5 DomainContainer

域容器节点（React Flow 自定义节点）。

```typescript
interface DomainContainerProps {
  data: {
    domainId: string;
    name: string;
    knowledgeBaseId: string;
    weight: number;
    nodeCount: number;
    expanded: boolean;
    status: 'ok' | 'warning' | 'error';
    childNodes: Node[];         // 仅 expanded=true 时渲染
    onToggleExpand: (domainId: string) => void;
    onDelete: (domainId: string) => void;
    onDoubleClickTitle: (domainId: string) => void;  // 打开域属性面板
  };
}
```

**内部状态**：无（React Flow 节点数据由 `useReactFlow` + store 管理）

**行为规格**：
- 折叠态：显示域名称 + 节点数量徽章 + 状态灯（绿/黄/红），宽度 200px，高度 60px
  - 双击名称 → 切换展开
  - 点击 → 选中域（`selectedDomainId`）
- 展开态：显示域名称标题栏 + 内部节点列表 + 连线，宽度 500px，高度自动（根据内部节点数量）
  - 标题栏右侧：折叠按钮（`<`）、删除按钮（`×`，二次确认）
  - 内部节点使用 React Flow `<ReactFlow>` 的子画布（`<ReactFlowProvider>` 嵌套），仅渲染 `childNodes` + `childEdges`，禁止拖出
  - 双击标题 → 弹出域属性面板（调用 `onDoubleClickTitle`）
- 状态灯逻辑：
  - `ok`（绿）：域内所有节点配置合法，知识库可访问
  - `warning`（黄）：域内至少一个节点配置有警告（如使用了默认模型）、或知识库快照过期
  - `error`（红）：域内至少一个节点配置非法、或知识库不存在/无权访问
- 域容器通过 `onDragOver` 拒绝聚合节点类型拖入（标红边框 + 提示）

---

### 2.6 WorkbenchToolbar

工作台顶部工具栏。

```typescript
interface WorkbenchToolbarProps {
  pipelineName: string;
  pipelineVersion: number;
  activeView: 'edit' | 'evaluate' | 'publish';
  isDirty: boolean;
  isSaving: boolean;
  isDryRunning: boolean;
  dryRunResult: DryRunResult | null;
  onSwitchView: (view: 'edit' | 'evaluate' | 'publish') => void;
  onSave: () => void;
  onDryRun: () => void;
  onBackToList: () => void;
}
```

**内部状态**：`saveModalVisible: boolean`、`changeLog: string`

**行为规格**：
- 左侧：`← 管道列表` 面包屑 + 管道名称 + 版本徽章 `v3`
- 右侧：视图切换 `Radio.Group`（`edit`/`evaluate`/`publish`）+ `[干运行]` 按钮 + `[保存]` 按钮
- 视图切换：调用 `onSwitchView` 触发 store 的 `switchView` action
- `[保存]` 按钮：
  - 管道无修改（`!isDirty`）时按钮 disabled
  - 有修改时按钮显示橙色圆点（dirty indicator）
  - 点击弹出保存对话框：变更说明输入（`TextArea`，最多 500 字符，必填）+ 版本预览（如 `v3 → v4`）
  - 保存中按钮显示 loading + "保存中..."
  - 保存成功后 toast "管道已保存，版本 v4" + `isDirty` 重置为 false
- `[干运行]` 按钮（仅编辑视图可见）：
  - 点击后发送当前画布配置到 `POST /api/v1/pipelines/{id}/dry-run`
  - 执行中按钮显示 loading + "编译中..."
  - 成功：画布左上角弹出成功通知，显示执行顺序节点列表
  - 失败：高亮问题节点（红色边框闪烁 3 次）+ 右侧属性面板显示错误详情
- 操作防抖：保存/干运行按钮在请求未完成时 disabled，防止重复点击

---

### 2.7 GenericNode

默认节点渲染（域内节点）。

```typescript
interface GenericNodeProps {
  data: {
    nodeId: string;
    nodeType: string;
    label: string;
    iconKey: string;            // 图标标识，映射到 @ant-design/icons 的图标组件
    status: 'ok' | 'warning' | 'error';
    config: Record<string, unknown>;
    hasDegradation: boolean;    // 是否配置了降级边
  };
  selected: boolean;
  sourcePosition: Position;
  targetPosition: Position;
}
```

**行为规格**：
- 渲染为标准矩形卡片（160px × 80px），圆角 8px
- 顶部行：图标（24px）+ 节点类型标签（小字灰色）
- 中间行：节点 label（粗体）
- 底部行：状态灯（绿/黄/红）+ 有降级边则显示橙色 `⚠` 图标
- 选中态：边框蓝色 2px + 轻微阴影
- 错误态：边框红色 2px，底部显示错误图标
- 左侧 `Handle`（target）：`Position.Left`
- 右侧 `Handle`（source）：`Position.Right`
- 右侧下半部额外 `Handle`（降级 source）：`Position.Right`，`id: 'degradation'`，较小尺寸
- 左侧下半部额外 `Handle`（条件 target）：`Position.Left`，`id: 'condition'`，较小尺寸

---

### 2.8 AggregationNode

聚合层节点，视觉区别于域内节点。

```typescript
interface AggregationNodeProps {
  data: {
    nodeId: string;
    nodeType: string;
    label: string;
    iconKey: string;
    status: 'ok' | 'warning' | 'error';
    config: Record<string, unknown>;
    hasDegradation: boolean;
  };
  selected: boolean;
  sourcePosition: Position;
  targetPosition: Position;
}
```

**行为规格**：
- 与 `GenericNode` 相同的布局结构，但背景色为浅蓝色（`#E8F4FD`），边框 2px 蓝色虚线
- 左上角显示"聚合"徽章（小蓝底白字标签）
- 尺寸统一 180px × 90px
- Handle 布局与 `GenericNode` 一致

---

### 2.9 CompoundNode

复合节点，支持展开/折叠。

```typescript
interface CompoundNodeProps {
  data: {
    compoundId: string;
    name: string;
    expanded: boolean;
    internalNodeCount: number;
    exposedPorts: { input: string; output: string };
    internalNodes: Node[];     // 仅 expanded=true 时渲染
    internalEdges: Edge[];
    onToggleExpand: () => void;
  };
  selected: boolean;
  sourcePosition: Position;
  targetPosition: Position;
}
```

**行为规格**：
- 折叠态：显示复合节点名称 + 内部节点数徽章（如 `3 nodes`）+ 展开图标，尺寸 180px × 80px，紫色边框虚线
- 展开态：显示内部节点 + 内部边（类似 `DomainContainer` 展开态，但使用子 React Flow 画布），尺寸自动扩大
- 内部节点不可独立连线到外部——只能通过 `exposed_ports.input`（target handle）和 `exposed_ports.output`（source handle）与外部节点连线
- 连接复合节点内部子节点时编辑器阻止并提示："请连接到复合节点的外部端口，不可穿透到内部"
- 嵌套层数校验：拖入复合节点到画布时，若当前已有 3 层嵌套（父复合节点内包含当前复合节点），阻止并提示"复合节点最多嵌套 3 层"
- 左侧 Handle：`id: 'compound-input'`
- 右侧 Handle：`id: 'compound-output'`

---

### 2.10 DataFlowEdge

数据流边：灰色实线。

```typescript
interface DataFlowEdgeProps {
  // 继承 @xyflow/react 的 EdgeProps
  id: string;
  source: string;
  target: string;
  sourceX: number;
  sourceY: number;
  targetX: number;
  targetY: number;
  selected: boolean;
}
```

**行为规格**：
- `stroke="#8C8C8C"`（灰色）
- `strokeWidth={2}`
- `type="smoothstep"` 或 `type="bezier"`
- 选中态：`stroke="#1677FF"`（蓝色）+ `strokeWidth={3}`
- 边中间可显示标签（无标签时不显示）
- 鼠标悬停显示删除按钮（`EdgeLabelRenderer` 中渲染 `×`）

---

### 2.11 ConditionalEdge

条件边：灰色虚线 + 条件标签。

```typescript
interface ConditionalEdgeProps extends DataFlowEdgeProps {
  data?: {
    label: string;             // 条件标签，如 "cache_hit" / "cache_miss" / "intent:心血管"
  };
}
```

**行为规格**：
- `stroke="#8C8C8C"`，`strokeDasharray="5,5"`（虚线）
- 边中间渲染条件标签（白色背景 pill 标签，字号 11px）
- 标签内容：条件类型缩写（`cache_hit` → "命中"、`cache_miss` → "未命中"、`intent_route:xxx` → "→ xxx"）
- 选中态：`stroke="#1677FF"` + `strokeWidth={3}`

---

### 2.12 DegradationEdge

降级边：橙色虚线 + 降级策略标签。

```typescript
interface DegradationEdgeProps extends DataFlowEdgeProps {
  data?: {
    label: string;             // 降级策略标签，如 "skip_node" / "reroute" / "degrade_cache"
  };
}
```

**行为规格**：
- `stroke="#FA8C16"`（橙色），`strokeDasharray="5,5"`（虚线）
- 边中间渲染降级策略标签（白色背景 pill 标签，字号 11px，橙色边框）
- 标签内容：`skip_node` → "跳过"、`reroute` → "切换"、`degrade_cache` → "缓存兜底"、`abort` → "中断"
- 选中态：`stroke="#FA541C"` + `strokeWidth={3}`

---

## 3. 状态管理

### 3.1 PipelineWorkbenchState（主 Store）

```typescript
// frontend/src/features/pipeline/stores/pipelineWorkbenchStore.ts

interface DomainConfig {
  id: string;
  name: string;
  knowledgeBaseId: string;
  weight: number;
  position: { x: number; y: number };
  expanded: boolean;
}

interface PipelineSnapshot {
  nodes: Node[];
  edges: Edge[];
  domains: DomainConfig[];
  timestamp: number;
}

interface CompoundNode {
  id: string;
  name: string;
  configSnapshot: PipelineConfig;
  internalNodeCount: number;
  createdAt: string;
}

interface DryRunResult {
  success: boolean;
  executionOrder?: string[];        // 节点 ID 执行顺序列表
  errors?: Array<{
    nodeId: string;
    field: string;
    issue: string;
  }>;
}

interface PipelineWorkbenchState {
  // —— 管道基础信息 ——
  pipelineId: string;
  pipelineName: string;
  pipelineVersion: number;
  pipelineType: 'aggregation' | 'single_domain';
  activeView: 'edit' | 'evaluate' | 'publish';

  // —— 编辑视图状态 ——
  domains: DomainConfig[];
  nodes: Node[];
  edges: Edge[];
  selectedNodeId: string | null;
  selectedEdgeId: string | null;
  selectedDomainId: string | null;
  isDirty: boolean;
  isSaving: boolean;
  isDryRunning: boolean;
  dryRunResult: DryRunResult | null;
  undoStack: PipelineSnapshot[];
  redoStack: PipelineSnapshot[];
  compoundNodeLibrary: CompoundNode[];
  highlightedNodeIds: string[];       // 从评估视图跳转时高亮的节点 ID 列表

  // —— 评估视图状态 ——
  evalRuns: EvalRunSummary[];
  evalRunsLoading: boolean;

  // —— 发布视图状态 ——
  publishConfig: PublishConfig | null;
  publishConfigLoading: boolean;

  // —— 操作 ——
  // 管道加载
  loadPipeline: (id: string) => Promise<void>;

  // 视图切换
  switchView: (view: 'edit' | 'evaluate' | 'publish') => void;

  // 编辑区 Mutation
  addDomain: (name: string, knowledgeBaseId: string, keywords: string[]) => void;
  updateDomain: (domainId: string, updates: Partial<DomainConfig>) => void;
  deleteDomain: (domainId: string) => void;
  toggleDomainExpand: (domainId: string) => void;

  addNode: (nodeType: string, position: XYPosition, targetDomainId?: string) => void;
  updateNode: (nodeId: string, updates: Partial<Node>) => void;
  updateNodeConfig: (nodeId: string, config: Record<string, unknown>) => void;
  deleteNode: (nodeId: string) => void;

  addEdge: (edge: Omit<Edge, 'id'>) => void;
  updateEdge: (edgeId: string, updates: Partial<Edge>) => void;
  deleteEdge: (edgeId: string) => void;

  setSelectedNode: (nodeId: string | null) => void;
  setSelectedEdge: (edgeId: string | null) => void;
  setSelectedDomain: (domainId: string | null) => void;
  setHighlightedNodeIds: (nodeIds: string[]) => void;

  // 保存与校验
  save: () => Promise<void>;
  dryRun: () => Promise<void>;

  // 撤销/重做
  pushSnapshot: () => void;
  undo: () => void;
  redo: () => void;
  canUndo: () => boolean;
  canRedo: () => boolean;

  // 复合节点库
  loadCompoundNodes: () => Promise<void>;
  addCompoundNode: (compound: CompoundNode) => void;
  removeCompoundNode: (id: string) => void;

  // 重置
  reset: () => void;
}
```

### 3.2 Store 实现要点

**`pushSnapshot`**：
- 每次 `addNode`/`updateNode`/`deleteNode`/`addEdge`/`updateEdge`/`deleteEdge`/`addDomain`/`deleteDomain` 操作前自动调用 `pushSnapshot`
- 快照内容：`{ nodes, edges, domains, timestamp }` 深拷贝
- 压入 `undoStack`，同时清空 `redoStack`

**`undo`**：
```
1. 当前状态 → push 到 redoStack
2. undoStack.pop() → 还原 nodes/edges/domains
3. isDirty = true
```

**`redo`**：
```
1. 当前状态 → push 到 undoStack
2. redoStack.pop() → 还原 nodes/edges/domains
3. isDirty = true
```

**撤销栈上限**：50 步。`pushSnapshot` 时若 `undoStack.length >= 50`，`shift()` 丢弃最早的快照。

**快照时机**：
- `addNode`、`updateNode`（onDragStop）、`updateNodeConfig`（debounce 500ms 后）、`deleteNode`
- `addEdge`、`updateEdge`、`deleteEdge`
- `addDomain`、`deleteDomain`、`updateDomain`
- 不记录快照的操作：`setSelectedNode`、`setSelectedEdge`、`setSelectedDomain`、`toggleDomainExpand`

### 3.3 pipelineListStore（列表 Store）

```typescript
// frontend/src/features/pipeline/stores/pipelineListStore.ts

interface PipelineListState {
  pipelines: PipelineSummary[];
  total: number;
  page: number;
  pageSize: number;
  keyword: string;
  statusFilter: 'all' | 'published' | 'unpublished' | 'draft';
  loading: boolean;

  loadPipelines: (params?: { page?: number; keyword?: string; status?: string }) => Promise<void>;
  deletePipeline: (id: string) => Promise<void>;
  duplicatePipeline: (id: string, newName: string) => Promise<void>;
  createPipeline: (name: string, templateId?: string) => Promise<string>; // 返回新管道 ID
}
```

### 3.4 跨视图状态共享

`PipelineWorkbenchState` 中的 `highlightedNodeIds` 用于评估视图跳转到编辑视图时高亮问题节点。流程：
1. 用户在评估详情页点击"🔧 去编辑器中打开"
2. 调用 `navigate('/pipelines/${pipelineId}?view=edit&highlight=n_001,n_002')`
3. `PipelineWorkbench` 挂载时解析 `highlight` 参数 → 调用 `setHighlightedNodeIds(['n_001', 'n_002'])`
4. `PipelineCanvas` 监听到 `highlightedNodeIds` 变化 → 执行 `fitView({ nodes: [{ id: 'n_001' }, { id: 'n_002' }] })` + 高亮节点动画（缩放+闪烁边框）

---

## 4. API 客户端

```typescript
// frontend/src/api/pipeline.ts

import { apiClient } from '@shared/api/client';
import type {
  PipelineDetail,
  PipelineSummary,
  PipelineCreateRequest,
  PipelineUpdateRequest,
  PipelineValidateResult,
  DryRunResult,
  VersionList,
  VersionDetail,
  VersionCompareRequest,
  VersionCompareResult,
  CompoundNodeCreateRequest,
  CompoundNodeDetail,
  PublishConfig,
  PublishConfigRequest,
  NodeDefinition,
  PaginatedResponse,
  KnowledgeBaseSummary,
} from '@entities/pipeline/types';

// ======================== 管道 CRUD ========================

/** 创建管道 */
export async function createPipeline(data: PipelineCreateRequest): Promise<{ pipelineId: string; versionNumber: number }>;

/** 管道列表 */
export async function listPipelines(params?: {
  page?: number;
  pageSize?: number;
  keyword?: string;
  type?: 'aggregation' | 'single_domain';
}): Promise<PaginatedResponse<PipelineSummary>>;

/** 获取管道详情（含当前版本完整配置） */
export async function getPipeline(id: string): Promise<PipelineDetail>;

/** 更新管道配置（触发版本递增） */
export async function updatePipeline(id: string, data: {
  configSnapshot: object;
  changeLog: string;
}): Promise<{ versionNumber: number }>;

/** 删除管道及其所有版本 */
export async function deletePipeline(id: string): Promise<void>;

/** 复制管道 */
export async function duplicatePipeline(id: string, newName: string): Promise<{ pipelineId: string }>;

// ======================== 版本管理 ========================

/** 版本列表 */
export async function listVersions(pipelineId: string): Promise<VersionList>;

/** 获取指定版本配置 */
export async function getVersion(pipelineId: string, versionNumber: number): Promise<VersionDetail>;

/** 回滚到指定版本 */
export async function rollbackVersion(pipelineId: string, versionNumber: number, changeLog: string): Promise<{ newVersionNumber: number }>;

/** 对比两个版本 */
export async function compareVersions(data: VersionCompareRequest): Promise<VersionCompareResult>;

// ======================== 校验与干运行 ========================

/** 校验管道配置（不保存，仅返回错误列表） */
export async function validatePipeline(id: string, configSnapshot: object): Promise<PipelineValidateResult>;

/** 干运行（编译检查 + 模拟执行顺序） */
export async function dryRunPipeline(id: string, configSnapshot: object): Promise<DryRunResult>;

// ======================== 复合节点 ========================

/** 复合节点列表 */
export async function listCompoundNodes(): Promise<CompoundNodeDetail[]>;

/** 创建复合节点 */
export async function createCompoundNode(data: CompoundNodeCreateRequest): Promise<{ id: string }>;

/** 删除复合节点 */
export async function deleteCompoundNode(id: string): Promise<void>;

/** 导入复合节点 JSON */
export async function importCompoundNode(jsonString: string): Promise<{ id: string }>;

/** 导出复合节点 JSON */
export async function exportCompoundNode(id: string): Promise<object>;

// ======================== 发布 ========================

/** 获取管道发布配置 */
export async function getPublishConfig(pipelineId: string): Promise<PublishConfig | null>;

/** 保存/更新发布配置 */
export async function updatePublishConfig(pipelineId: string, data: PublishConfigRequest): Promise<void>;

/** 停用发布 URL */
export async function unpublishPipeline(pipelineId: string): Promise<void>;

/** 已发布端点列表 */
export async function listPublishedEndpoints(): Promise<PaginatedResponse<PublishedEndpoint>>;

// ======================== 节点定义 ========================

/** 获取所有可用节点类型定义（28 种） */
export async function listNodeDefinitions(): Promise<NodeDefinition[]>;

// ======================== 知识库 ========================

/** 获取用户可访问的知识库列表（域创建时选择知识库） */
export async function listAccessibleKnowledgeBases(): Promise<KnowledgeBaseSummary[]>;

// ======================== 导出/导入 ========================

/** 导出完整管道配置 JSON */
export async function exportPipeline(id: string, version?: number): Promise<object>;

/** 导入管道 JSON */
export async function importPipeline(jsonString: string): Promise<{ pipelineId: string }>;
```

### 4.1 API 实现（`apiClient` 调用）

每个函数通过 `apiClient` 发起请求，基础路径 `/api/v1`：

```typescript
// 示例：getPipeline
export async function getPipeline(id: string): Promise<PipelineDetail> {
  const res = await apiClient.get(`/api/v1/pipelines/${id}`);
  return res.data.data;
}

// 示例：updatePipeline
export async function updatePipeline(id: string, data: {
  configSnapshot: object;
  changeLog: string;
}): Promise<{ versionNumber: number }> {
  const res = await apiClient.put(`/api/v1/pipelines/${id}`, data);
  return res.data.data;
}

// 示例：dryRunPipeline
export async function dryRunPipeline(id: string, configSnapshot: object): Promise<DryRunResult> {
  const res = await apiClient.post(`/api/v1/pipelines/${id}/dry-run`, { config_snapshot: configSnapshot });
  return res.data.data;
}
```

---

## 5. 交互流程

### 5.1 创建管道流程

```
用户点击 [+ 新建管道]
  → 弹出 CreatePipelineModal 对话框
    ├── 输入管道名称（必填，1-100 字符）
    ├── 选择初始模板：
    │   ├── 空白管道（默认）
    │   ├── 从已有管道复制（下拉选择已有管道列表）
    │   └── 从 JSON 导入（文件上传 + 预览 + 校验）
    └── [取消] [创建]
  → 调用 createPipeline API
  → 成功：toast "管道创建成功" → navigate(`/pipelines/${newId}`)
  → 失败：toast 错误信息
```

### 5.2 添加业务域流程（仅聚合管道）

```
点击画布顶部 [+ 添加业务域] 按钮
  → 右侧滑出 DomainCreateDrawer（600px 宽）
    ├── 域名称（Input，必填，1-50 字符）
    ├── 选择知识库（Select，异步加载 listAccessibleKnowledgeBases）
    │   ├── 下拉列表显示：知识库名称 + 文档数 + 向量后端类型
    │   ├── 自动过滤用户无权访问的知识库
    │   └── 选中后预览知识库的激活关键词建议（若有）
    ├── 激活关键词（Select mode="tags"，可选，域内查询分析节点使用）
    ├── 域权重预览（默认 1/域总数，显示计算逻辑，创建后可在属性面板修改）
    └── [取消] [确认添加]
  → 前端校验：域数量上限 20，超限提示
  → 确认 → store.addDomain(name, kbId, keywords)
    ├── 画布上新增 DomainContainer 节点（默认折叠态，自动布局位置）
    ├── 聚合层自动添加该域的连接点（domain_dispatch 节点的 target handle 自动增加）
    ├── 域内节点初始化：根据知识库类型自动添加默认检索节点（vector_search，top_k=10）
    └── pushSnapshot + isDirty = true
  → 关闭 Drawer
```

### 5.3 拖拽节点到画布流程

```
用户从 NodePanel 拖拽 DraggableNodeItem
  → onDragStart:
    event.dataTransfer.setData('application/reactflow-node-type', nodeTypeId)
    event.dataTransfer.effectAllowed = 'move'

  → onDrop (in PipelineCanvas):
    1. 获取 nodeType = event.dataTransfer.getData('application/reactflow-node-type')
    2. 获取画布坐标 position = reactFlowInstance.screenToFlowPosition(...)
    3. 判断节点类别：
       a) 聚合节点 (prefix='query_analyzer'|'domain_dispatch'|'cross_fusion'|'cross_dedup'|'conflict_detect'|'unified_generate'):
          - 判断 drop 位置是否在某个域容器内
            → 是：阻止，画布标红 + toast "聚合层节点不可放入业务域内"
            → 否：store.addNode(nodeType, position)  ← 无 targetDomainId
       b) 域内节点（默认）:
          - 判断 drop 位置是否在某个域容器内
            → 是：store.addNode(nodeType, position, targetDomainId)
                  若域容器处于折叠态，自动展开
            → 否：阻止，画布标红 + toast "域内节点必须放入业务域容器内"
       c) 复合节点：
          - 等同域内节点规则（可放入域内或聚合层，取决于复合节点类型）

    4. 校验节点数量上限：
       - 单域节点数 ≤ 30，超限阻止 + toast
       - 管道总节点数 ≤ 100，超限阻止 + toast
    5. 自动生成唯一 ID：`n_{nodeType}_{timestamp}_{random4}`
    6. addNode → pushSnapshot → isDirty = true
```

### 5.4 连接节点流程

```
用户从节点 A 的 source handle 拖出连线到节点 B 的 target handle
  → onConnect 回调触发

  1. 类型兼容性校验（CAN_CONNECT_MAP 查找）：
     - 聚合节点 → 聚合节点：允许（数据流边）
     - 聚合节点 → 域容器/域内节点：阻止
     - 域内节点 → 域内节点（同域）：允许（数据流边）
     - 域内节点 → 域内节点（跨域）：阻止
     - 域内节点 → 聚合节点：允许（数据流边）
     - 聚合节点 → 域内节点：阻止

  2. 连接方式校验：
     - 普通 source handle → 普通 target handle：数据流边
       - 约束：一个 source handle 最多出 1 条数据流边；已有一条时阻止 + toast "该节点已有一条数据流输出，可添加条件边"
     - degradation source handle → degradation target handle：降级边
       - 允许任意节点出降级边，任意节点收降级边

  3. 条件边创建：
     - 需用户在边属性面板选择条件类型（cache_hit/cache_miss/intent_route:xxx）
     - 条件边不占用普通 source handle 的"唯一数据流边"名额

  4. 复合节点约束：
     - 连线目标在复合节点内部（且该复合节点处于折叠态）→ 阻止 + toast "请连接到复合节点的外部端口"
     - 连线目标在复合节点内部（且该复合节点处于展开态）→ 自动连接到复合节点的 exposed_ports

  5. 添加边 → store.addEdge → pushSnapshot → isDirty = true
```

### 5.5 保存流程

```
用户点击 [保存] 按钮（前提：isDirty = true）
  → 弹出 SaveConfirmModal
    ├── 版本变更预览：v{current} → v{current + 1}
    ├── 变更说明（TextArea，必填，最多 500 字符）
    ├── 可选：[x] 保存前执行校验（默认勾选）
    └── [取消] [确认保存]

  → 确认保存：
    1. 若勾选校验 → 先调用 validatePipeline API
       → 有错误：显示错误列表（节点ID + 字段 + 问题），禁止保存，[忽略并保存] 按钮可选
       → 无错误：继续
    2. 序列化当前画布为 configSnapshot JSON
    3. 调用 updatePipeline API → { versionNumber }
    4. 成功：
       - toast "管道已保存，当前版本 v{versionNumber}"
       - 更新 pipelineVersion 状态
       - isDirty = false
       - 清空 undoStack/redoStack
    5. 失败：
       - toast 错误信息
```

### 5.6 干运行流程

```
用户点击 [干运行] 按钮
  → isDryRunning = true
  → 序列化当前画布为 configSnapshot
  → 调用 dryRunPipeline API
  → 成功（success: true）：
    - 画布左上角弹出 DryRunSuccessPanel（绝对定位，不超过画布边界）
      显示：编译成功 + 执行顺序列表（有序号节点 ID + 节点名称）
      5 秒后自动消失，或点击关闭
    - 画布无高亮
  → 失败（success: false）：
    - 画布上高亮问题节点：红色边框闪烁 3 次（animation: blink-red-border 0.5s 3）
    - 右侧属性面板（如有选中问题节点）显示错误详情
    - 若无选中节点 → 弹出 DryRunErrorPanel（包含所有错误的可点击列表，点击条目 → 选中对应节点 + 滚动到视口内）
  → isDryRunning = false
```

### 5.7 视图切换流程

```
用户点击 [编辑] / [评估] / [发布]
  → store.switchView(targetView)
  → 更新 URL query: ?view={targetView}

  edit → evaluate:
    - 检查 isDirty → 弹出确认 "管道有未保存的修改，是否先保存？" [保存并切换] [不保存] [取消]
    - 切换后：EvaluateView 挂载 → 自动加载该管道的评估历史 (loadEvalRuns)

  edit → publish:
    - 同上 isDirty 检查
    - 切换后：PublishView 挂载 → 自动加载该管道的发布配置 (loadPublishConfig)

  evaluate → edit:
    - 保留编辑状态（不重新加载管道），直接切换视图

  publish → edit:
    - 同上

  **关键保障**：视图切换不丢失编辑状态。编辑视图的 nodes/edges/domains 在 switchView 后保留，仅隐藏视图组件。
```

### 5.8 版本对比流程

```
在版本管理面板（工具栏下拉或独立入口）：
  → 选择版本 v1（左）和版本 v2（右）
  → 调用 compareVersions API → 返回差异详情
  → DiffPanel 渲染：
    ├── 新增节点（绿色背景，列出节点 ID + 类型）
    ├── 删除节点（红色背景，列出节点 ID + 类型）
    ├── 节点参数变更：
    │   每个变更项：节点 ID + 类型 + 字段名 + v1值 → v2值（红色删除线 + 绿色高亮）
    └── 边变更（新增/删除/类型变更）
```

---

## 6. 性能约束

### 6.1 画布虚拟化

- 使用 `@xyflow/react` 内置的 `onlyRenderVisibleElements` 属性（需确认版本支持的 API），仅渲染视口内可见的节点和边
- 若 `@xyflow/react` 版本不支持内置虚拟化，则通过 `getIntersectingNodes` + `getIntersectingEdges` API 手动过滤，仅渲染与视口有交集的节点和边
- 视口外节点不创建 DOM，但保留在 React Flow 的内部状态中

### 6.2 域容器折叠优化

- 折叠态：`childNodes` 数组保留在 store 中但不传递给 React Flow 渲染。`DomainContainer` 折叠态仅渲染标题栏（60px），内部无子组件树
- 展开态：内部节点渲染在 `DomainContainer` 的子 React Flow 实例中
- 折叠/展开切换通过 `store.toggleDomainExpand` 控制，不触发整个画布重渲染（React.memo + shallow equal）

### 6.3 撤销栈限制

```typescript
const MAX_UNDO_STACK = 50;

pushSnapshot: () => {
  const { nodes, edges, domains, undoStack } = get();
  const snapshot: PipelineSnapshot = {
    nodes: structuredClone(nodes),
    edges: structuredClone(edges),
    domains: structuredClone(domains),
    timestamp: Date.now(),
  };
  const nextStack = [...undoStack, snapshot];
  if (nextStack.length > MAX_UNDO_STACK) {
    nextStack.shift(); // 丢弃最早快照
  }
  set({ undoStack: nextStack, redoStack: [] });
};
```

### 6.4 节点/域数量上限

| 约束项 | 上限 | 校验时机 | 超限行为 |
|--------|------|---------|---------|
| 单管道域数 | 20 | `addDomain` 时 | 阻止 + toast "业务域数量已达上限（20个）" |
| 单域内节点数 | 30 | `addNode` 时 | 阻止 + toast "该域内节点数已达上限（30个）" |
| 单管道总节点数 | 100 | `addNode` 时 + `save` 时 | 阻止 + toast "管道总节点数已达上限（100个）" |
| 复合节点嵌套层数 | 3 | 拖入画布时 | 阻止 + toast "复合节点最多嵌套 3 层" |

前端上限校验早于 API 调用，API 层也有校验（双重保障）。

### 6.5 画布缩放范围

```typescript
// PipelineCanvas 内部
<ReactFlow
  minZoom={0.25}
  maxZoom={2.0}
  // Controls 组件的 zoom 步进 = 0.1
>
  <Controls />
</ReactFlow>
```

### 6.6 配置序列化大小

| 约束项 | 上限 | 校验时机 | 超限行为 |
|--------|------|---------|---------|
| configSnapshot JSON | 500 KB | `save` 前 | 阻止 + toast "管道配置过大（超过 500KB），请精简节点或参数" |

```typescript
// save 时：
const configJson = JSON.stringify(configSnapshot);
if (new Blob([configJson]).size > 500 * 1024) {
  message.warning('管道配置过大（超过 500KB），请精简节点或参数');
  return;
}
```

### 6.7 防抖与并发控制

| 操作 | 防抖策略 |
|------|---------|
| `updateNodeConfig` | 500ms debounce（每次属性面板表单值变更） |
| `save` | 按钮点击后 disabled 直到请求完成，阻止重复提交 |
| `dryRun` | 同上 |
| `pushSnapshot` | 不防抖，但 `updateNodeConfig` 的 debounce 也控制了快照频率 |
| 画布拖拽 `onNodesChange` | 不防抖（React Flow 内部优化），`onNodeDragStop` 时触发 `pushSnapshot` |

### 6.8 组件渲染优化

- `PipelineCard`：`React.memo` + 仅 `pipeline` props 变化时重渲染
- `DomainContainer`：`React.memo` + 仅 `data.name`/`data.nodeCount`/`data.expanded`/`data.status`/`selected` 变化时重渲染
- `GenericNode`：`React.memo` + 仅 `data.label`/`data.status`/`selected` 变化时重渲染
- `PropertyPanel`：`React.memo` + `useMemo` 缓存表单渲染（`nodeTypeId` + `nodeConfig` 不变则不复算）

---

## 7. 测试策略

### 7.1 组件测试（Vitest + React Testing Library）

**测试文件位置**：`frontend/src/features/pipeline/__tests__/`

#### TC-COMP-01：PipelineCard 渲染
```
Given: PipelineSummary { name: "测试管道", version: 3, domainCount: 2, nodeCount: 15, lastEvalScore: 0.84, publishedUrl: "/search/test" }
When: 渲染 <PipelineCard pipeline={...} />
Then: 卡片显示管道名称 "测试管道"
Then: 版本徽章显示 "v3"
Then: 显示 "2 域 · 15 节点"
Then: 评估得分显示 "0.84" + 绿色指示
Then: 发布状态显示已发布 URL "/search/test"
Then: 底部渲染 3 个操作按钮 [编辑] [评估] [发布]
Then: 无评分时显示 "—"（无颜色指示器）
Then: 未发布时显示 "—"（无颜色指示器）
```

#### TC-COMP-02：PipelineCard 操作按钮回调
```
Given: 渲染 <PipelineCard onEdit={mockEdit} onEvaluate={mockEval} onPublish={mockPub} />
When: 点击 [编辑]
Then: mockEdit 被调用，参数为 pipeline.id
When: 点击 [评估]
Then: mockEval 被调用，参数为 pipeline.id
When: 点击 [发布]
Then: mockPub 被调用，参数为 pipeline.id
```

#### TC-COMP-03：NodePanel 拖拽
```
Given: 渲染 <NodePanel />
When: 在搜索框输入 "BM25"
Then: 仅显示 "BM25 检索" 节点项，其他节点项隐藏
When: 清空搜索框
Then: 所有节点项恢复显示
When: 拖拽一个域内节点项
Then: dataTransfer 的 'application/reactflow-node-type' 被设置为正确的 nodeTypeId
When: 拖拽一个聚合节点项
Then: dataTransfer 设置正确
```

#### TC-COMP-04：PropertyPanel 动态表单（节点选中）
```
Given: store 中 selectedNodeId = "n_001"，节点类型为 "bm25_search"
When: 渲染 <PropertyPanel />
Then: 显示节点属性表单，包含字段：top_k (number), k1 (number), b (number), field_weights (json), score_threshold (number)
When: 修改 top_k 值为 20
Then: onNodeConfigChange 被调用，{ top_k: 20 }
When: 点击 [删除节点]
Then: 弹出确认对话框；确认后 onDeleteNode 被调用
```

#### TC-COMP-05：PropertyPanel 动态表单（边选中）
```
Given: store 中 selectedEdgeId = "e_001"，边类型为 "conditional"
When: 渲染 <PropertyPanel />
Then: 显示边属性表单，包含：边类型（条件边）、条件表达式（Select，含 cache_hit/cache_miss/intent_route 选项）
When: 修改条件表达式为 "cache_miss"
Then: onEdgeConfigChange 被调用，{ condition: "cache_miss" }
```

#### TC-COMP-06：PropertyPanel 域属性表单
```
Given: store 中 selectedDomainId = "d_001"
When: 渲染 <PropertyPanel />
Then: 显示域属性表单：域名称、知识库选择、域权重 slider、激活关键词 tags
When: 修改域权重为 0.5
Then: onDomainConfigChange 被调用，{ weight: 0.5 }
When: 更换知识库
Then: 下拉列表仅显示用户有权访问的知识库
```

#### TC-COMP-07：WorkbenchToolbar 视图切换
```
Given: 渲染 <WorkbenchToolbar activeView="edit" />
When: 点击 [评估]
Then: onSwitchView('evaluate') 被调用
When: 点击 [发布]
Then: onSwitchView('publish') 被调用
When: 点击 [编辑]
Then: onSwitchView('edit') 被调用
```

#### TC-COMP-08：WorkbenchToolbar 保存按钮状态
```
Given: isDirty = true, isSaving = false
When: 渲染 <WorkbenchToolbar />
Then: [保存] 按钮可点击 + 显示橙色圆点 dirty indicator
When: isDirty = false
Then: [保存] 按钮 disabled + 无 dirty indicator
When: isSaving = true
Then: 按钮显示 loading + "保存中..."
```

### 7.2 集成测试

#### TC-INTEG-01：完整编辑工作流
```
Given: 新建空白管道
When: 添加业务域 "心血管域"（知识库 = kb_cardio）
Then: 画布上出现 DomainContainer（折叠态），显示名称 + 0 节点
When: 拖入 "BM25 检索" 节点到心血管域内
Then: 域容器自动展开，内部显示 BM25 节点；节点数更新为 1
When: 拖入 "重排序" 节点 → 连接 "BM25 检索" → "重排序"
Then: 出现数据流边（灰色实线）
When: 为 "BM25 检索" 配置降级边（skip_node）
Then: 出现橙色虚线 + "跳过" 标签
When: 点击 [保存] → 输入变更说明 "初始配置"
Then: Pipe 版本号从 1 变为 2（创建时为 v1，首次保存为 v2）
Then: isDirty = false
```

#### TC-INTEG-02：域操作完整流程
```
Given: 聚合管道，已有 1 个域
When: 点击 [+ 添加业务域]
Then: 弹出 DomainCreateDrawer 抽屉
When: 输入名称 "内分泌域" → 选择知识库 kb_endo → 添加关键词 ["血糖", "激素"]
Then: 确认 → 抽屉关闭，画布上新增 DomainContainer（折叠态）
When: 双击域容器标题
Then: 弹出域属性面板，显示当前配置
When: 修改域权重大小为 0.4 → 确认
Then: 域权重更新
When: 点击域容器 × 删除 → 二次确认（提示将移除该域内 X 个节点）
Then: 确认 → 域容器和内部节点被移除
```

#### TC-INTEG-03：拖拽约束
```
Given: 聚合管道，有 1 个域容器，聚合区域有空位
When: 拖拽聚合节点 "跨域融合" 到域容器内
Then: 阻止拖入，域容器显示红色边框，toast "聚合层节点不可放入业务域内"
When: 拖拽域内节点 "敏感词过滤" 到聚合区域（域容器外）
Then: 阻止放置，画布标红，toast "域内节点必须放入业务域容器内"
```

#### TC-INTEG-04：节点数量上限
```
Given: 域内有 30 个节点（已达上限）
When: 拖入第 31 个节点
Then: 阻止 + toast "该域内节点数已达上限（30个）"
Given: 管道总节点数 = 99
When: 拖入 2 个节点
Then: 第 1 个成功，第 2 个阻止 + toast "管道总节点数已达上限（100个）"
```

#### TC-INTEG-05：撤销/重做
```
Given: 画布有 3 个节点
When: 删除 1 个节点
Then: 画布剩 2 个节点 + isDirty = true
When: 执行 undo（Ctrl+Z 或按钮）
Then: 删除的节点恢复 + isDirty = true
When: 执行 redo（Ctrl+Shift+Z 或按钮）
Then: 节点再次被删除 + isDirty = true
Given: undoStack 已有 50 步
When: 执行新的操作（pushSnapshot）
Then: undoStack 保持 50 步（最早快照被丢弃）
```

#### TC-INTEG-06：干运行
```
Given: 配置合法的管道
When: 点击 [干运行]
Then: API 调用 /pipelines/{id}/dry-run
When: 返回 success: true, executionOrder: [nodes]
Then: 画布左上角显示成功面板（执行顺序列表），5 秒后消失
Given: 配置非法的管道（节点的 top_k = 0）
When: 点击 [干运行]
Then: API 返回 success: false, errors: [{nodeId: "n_001", field: "top_k", issue: "top_k 必须在 1-100 之间"}]
Then: 问题节点 "n_001" 红色边框闪烁 3 次
Then: 弹出 DryRunErrorPanel 显示错误详情
```

#### TC-INTEG-07：视图切换不丢状态
```
Given: 编辑视图中有 3 个节点、2 个域、5 条边，isDirty = true
When: 切换到评估视图
Then: 评估视图正常渲染，无报错
When: 切回编辑视图
Then: 3 个节点、2 个域、5 条边全部恢复原样，isDirty 仍然为 true
Given: isDirty = true
When: 从编辑切换到评估
Then: 弹出 "有未保存修改" 确认对话框
When: 点击 [不保存]
Then: 切换到评估视图，编辑状态的脏数据仍保留（不保存但也不丢弃）
```

#### TC-INTEG-08：版本对比
```
Given: 管道有 v1（3 节点）和 v3（5 节点，某些参数不同）
When: 在版本管理面板选择 v1 vs v3
Then: DiffPanel 显示：新增 2 个节点 + 参数变更项高亮
```

#### TC-INTEG-09：复合节点拖入展开
```
Given: 复合节点库中有 "标准医学检索组"（3 内部节点）
When: 拖拽到画布上
Then: 画布上出现 CompoundNode（折叠态），显示名称 + "3 nodes" 徽章
When: 点击展开
Then: 内部 3 个节点和内部边可见
When: 尝试从外部节点连线到复合节点内部子节点
Then: 阻止 + toast "请连接到复合节点的外部端口"
```

#### TC-INTEG-10：从评估跳转到编辑高亮
```
Given: 评估详情页显示了问题节点 "n_001"
When: 点击 "🔧 去编辑器中打开"
Then: 路由跳转到 /pipelines/{id}?view=edit&highlight=n_001
Then: 编辑视图加载，画布自动缩放到节点 n_001 可见
Then: 节点 n_001 高亮动画（蓝色边框闪烁 3 次）
Then: 自动选中节点 n_001（属性面板显示其配置）
```

### 7.3 Canvas 交互测试

#### TC-CANVAS-01：节点拖拽
```
Given: 画布有节点 "BM25 检索" 在位置 (100, 200)
When: 用户拖拽节点到 (150, 220)
Then: onNodeDragStop 被调用，更新节点位置
Then: pushSnapshot 被触发
Given: 节点在域容器内
When: 拖拽到域容器外
Then: 节点回弹到原位置 + 标红 300ms
```

#### TC-CANVAS-02：连线兼容性校验
```
Given: 域内节点 A 在同一域内
When: 从 A 连线到同域内节点 B
Then: 数据流边创建成功
Given: 域内节点 A 在心血管域，节点 C 在内分泌域
When: 从 A 连线到 C
Then: 阻止 + toast "不可跨域连线"
Given: 节点 A 已有一条数据流输出边
When: 从 A 再连线到节点 D
Then: 阻止 + toast "该节点已有一条数据流输出，可添加条件边"
```

#### TC-CANVAS-03：边删除
```
Given: 节点 A 和 B 之间有一条数据流边
When: 点击该边 → 点击删除按钮
Then: 弹出确认对话框（显示边的类型和连接信息）
When: 确认删除
Then: 边被移除 + pushSnapshot + isDirty = true
```

#### TC-CANVAS-04：域容器折叠
```
Given: 展开态域容器，内部有 5 个节点
When: 点击折叠按钮
Then: 域容器缩小为折叠态（200px × 60px），内部节点不渲染
Then: 显示域名称 + "5 nodes" 徽章 + 状态灯
When: 双击折叠态域容器
Then: 切换为展开态，内部节点恢复可见
```

#### TC-CANVAS-05：缩放范围
```
Given: 画布缩放为 100%
When: 用户缩小到 25%
Then: 画布缩放控件显示 25%，节点和边按比例缩小
When: 用户继续缩小
Then: 缩放停止在 25%，不再缩小
When: 用户放大到 200%
Then: 停止在 200%，不再放大
```

---

## 8. 第三方依赖

### 8.1 @xyflow/react

- **版本要求**：`^12.0.0` （React Flow 的下一代包，替代已弃用的 `reactflow` 包）
- **安装**：`npm install @xyflow/react`
- **核心用法**：

```typescript
import {
  ReactFlow,
  ReactFlowProvider,
  useNodesState,
  useEdgesState,
  addEdge,
  MiniMap,
  Controls,
  Background,
  BackgroundVariant,
  type Node,
  type Edge,
  type OnNodesChange,
  type OnEdgesChange,
  type OnConnect,
  type Connection,
  type XYPosition,
  Handle,
  Position,
  useReactFlow,
  getNodesBounds,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';  // 必需导入样式
```

- **自定义节点注册**：
```typescript
const nodeTypes = {
  domainContainer: DomainContainer,
  genericNode: GenericNode,
  aggregationNode: AggregationNode,
  compoundNode: CompoundNode,
};

const edgeTypes = {
  dataFlow: DataFlowEdge,
  conditional: ConditionalEdge,
  degradation: DegradationEdge,
};

<ReactFlow
  nodes={nodes}
  edges={edges}
  nodeTypes={nodeTypes}
  edgeTypes={edgeTypes}
  minZoom={0.25}
  maxZoom={2.0}
  onNodesChange={onNodesChange}
  onEdgesChange={onEdgesChange}
  onConnect={onConnect}
  onNodeClick={(_, node) => onNodeClick(node.id)}
  onNodeDragStop={(_, node) => onNodeDragStop(node.id, node.position)}
  fitView
>
  <MiniMap />
  <Controls />
  <Background variant={BackgroundVariant.Dots} gap={12} size={1} />
</ReactFlow>
```

- **虚拟化渲染**：`@xyflow/react` 内置节点视口裁剪，默认仅渲染视口内及附近节点。
- **注意事项**：
  - 节点 `id` 需全局唯一（域内节点、聚合节点、复合节点不共享 ID 命名空间）
  - `Handle` 的 `id` 用于区分不同类型的连接点（普通 source、degradation source、condition target 等）
  - 子画布（DomainContainer 内部、CompoundNode 内部）使用独立 `ReactFlowProvider` 包装，避免状态冲突

### 8.2 其他 npm 依赖

| 包名 | 版本 | 用途 |
|------|------|------|
| `zustand` | `^5.0.11` | 状态管理（已安装） |
| `@tanstack/react-query` | `^5.90.21` | 服务端状态缓存（管道列表、管道详情、评估历史）（已安装） |
| `antd` | `^6.3.2` | UI 组件库：Card、Form、Select、Drawer、Modal、Button、Input、Slider、Switch、Dropdown、Table、Tag、Badge、Tooltip、message、Tabs、Radio、Skeleton 等（已安装） |
| `@ant-design/icons` | `^5.3.0` | 图标库（节点图标、操作图标）（已安装） |
| `lodash-es` | `^4.17.23` | `debounce`、`cloneDeep`（已安装） |
| `react-router-dom` | `^7.13.1` | 路由导航、URL 参数解析（已安装） |
| `clsx` | `^2.1.1` | 条件 className（已安装） |

### 8.3 无需额外安装的依赖

以上依赖除了 `@xyflow/react` 外，其余全部已在 `frontend/package.json` 中声明。仅需执行：

```bash
cd frontend && npm install @xyflow/react
```

---

## 9. 实体类型定义

```typescript
// frontend/src/entities/pipeline/types.ts

/** 管道摘要（列表卡片使用） */
export interface PipelineSummary {
  id: string;
  name: string;
  type: 'aggregation' | 'single_domain';
  activeVersion: number;
  domainCount: number;
  nodeCount: number;
  lastEvalScore: number | null;
  publishedUrl: string | null;
  publishedStatus: 'active' | 'inactive' | null;
  createdAt: string;
  updatedAt: string;
}

/** 管道详情（工作台加载使用） */
export interface PipelineDetail {
  id: string;
  name: string;
  type: 'aggregation' | 'single_domain';
  tenantId: string;
  activeVersion: number;
  configSnapshot: PipelineConfig;
  createdAt: string;
  updatedAt: string;
}

/** 管道配置（完整 JSON） */
export interface PipelineConfig {
  pipeline: {
    id: string;
    name: string;
    type: 'aggregation' | 'single_domain';
    version: number;
    changeLog: string | null;
    tenantId: string;
  };
  domains: DomainNodeConfig[];
  aggregation: AggregationConfig;
}

export interface DomainNodeConfig {
  id: string;
  name: string;
  knowledgeBaseId: string;
  weight: number;
  activationRules: {
    keywords: string[];
    minConfidence: number;
  };
  pipeline: {
    nodes: NodeConfig[];
    edges: EdgeConfig[];
    conditionalEdges: EdgeConfig[];
    degradationEdges: EdgeConfig[];
  };
}

export interface NodeConfig {
  id: string;
  type: string;
  config: Record<string, unknown>;
  display: { x: number; y: number };
}

export interface EdgeConfig {
  id: string;
  source: string;
  target: string;
  type: 'data' | 'conditional' | 'degradation';
  condition?: string;
  strategy?: 'skip_node' | 'reroute' | 'degrade_cache' | 'abort';
}

export interface AggregationConfig {
  nodes: NodeConfig[];
  edges: EdgeConfig[];
  shortcutEdge: { source: string; target: string } | null;
}

/** 管道创建请求 */
export interface PipelineCreateRequest {
  name: string;
  type?: 'aggregation';
  configSnapshot?: PipelineConfig;
  changeLog?: string;
}

/** 管道更新请求 */
export interface PipelineUpdateRequest {
  configSnapshot: PipelineConfig;
  changeLog: string;
}

/** 版本列表 */
export interface VersionList {
  pipelineId: string;
  versions: VersionItem[];
}

export interface VersionItem {
  versionNumber: number;
  changeLog: string;
  createdAt: string;
  isActive: boolean;
  isPublished: boolean;
}

export interface VersionDetail {
  versionNumber: number;
  changeLog: string;
  configSnapshot: PipelineConfig;
  createdAt: string;
}

/** 版本对比 */
export interface VersionCompareRequest {
  pipelineId: string;
  v1: number;
  v2: number;
}

export interface VersionCompareResult {
  newNodeIds: string[];
  removedNodeIds: string[];
  configChanges: Array<{
    nodeId: string;
    nodeType: string;
    fieldName: string;
    oldValue: unknown;
    newValue: unknown;
  }>;
  edgeChanges: Array<{
    edgeId: string;
    type: 'added' | 'removed' | 'type_changed';
    oldType?: string;
    newType?: string;
  }>;
}

/** 校验结果 */
export interface PipelineValidateResult {
  valid: boolean;
  errors: Array<{
    nodeId: string;
    field: string;
    issue: string;
    severity: 'error' | 'warning';
  }>;
}

/** 干运行结果 */
export interface DryRunResult {
  success: boolean;
  executionOrder?: string[];
  errors?: Array<{
    nodeId: string;
    field: string;
    issue: string;
  }>;
}

/** 节点类型定义（用于面板渲染和属性表单） */
export interface NodeDefinition {
  typeId: string;
  label: string;
  category: 'query_understanding' | 'retrieval' | 'security' | 'quality' | 'performance' | 'synthesis' | 'aggregation';
  description: string;
  iconKey: string;
  isDomainNode: boolean;       // true = 域内节点，false = 聚合节点
  configFields: ConfigField[];
}

export interface ConfigField {
  name: string;
  label: string;
  type: 'string' | 'integer' | 'float' | 'boolean' | 'enum' | 'model' | 'prompt_template' | 'list' | 'json';
  default: unknown;
  description: string;
  required: boolean;
  validation?: {
    min?: number;
    max?: number;
    maxLength?: number;
    pattern?: string;
  };
  enumValues?: Array<{ label: string; value: string }>;
}

/** 复合节点 */
export interface CompoundNodeCreateRequest {
  name: string;
  expandedNodes: NodeConfig[];
  internalEdges: EdgeConfig[];
  exposedPorts: { input: string; output: string };
}

export interface CompoundNodeDetail {
  id: string;
  name: string;
  configSnapshot: object;
  internalNodeCount: number;
  createdAt: string;
}

/** 发布配置 */
export interface PublishConfig {
  urlPath: string;
  boundVersion: number;
  method: 'POST' | 'GET';
  authRequired: ('jwt' | 'api_key')[];
  rateLimitQps: number;
  enabled: boolean;
  allowedParams: string[];
  responseFormat: 'json' | 'sse';
  publishedAt: string;
}

export interface PublishConfigRequest {
  urlPath: string;
  boundVersion: number;
  method: 'POST' | 'GET';
  authRequired: ('jwt' | 'api_key')[];
  rateLimitQps: number;
  enabled: boolean;
  allowedParams: string[];
  responseFormat: 'json' | 'sse';
}

/** 已发布端点 */
export interface PublishedEndpoint {
  pipelineId: string;
  pipelineName: string;
  urlPath: string;
  boundVersion: number;
  enabled: boolean;
  requestCount24h: number;
  avgLatencyMs: number;
}

/** 知识库摘要（域创建时选择） */
export interface KnowledgeBaseSummary {
  id: string;
  name: string;
  documentCount: number;
  vectorBackend: string;
}
```

---

## 10. 文件结构清单

```
frontend/src/
├── api/
│   └── pipeline.ts                          # 管道 API 客户端（第 4 节全部函数）
├── entities/
│   └── pipeline/
│       └── types.ts                         # 管道实体类型（第 9 节全部 interface）
├── features/
│   └── pipeline/
│       ├── pages/
│       │   ├── PipelineListPage.tsx          # 管道列表页
│       │   ├── PipelineWorkbench.tsx         # 管道工作台（三视图容器）
│       │   └── EvalDetailPage.tsx            # 评估详情页（占位，具体见 06-rag-evaluation 规格）
│       ├── components/
│       │   ├── PipelineCard.tsx              # §2.1
│       │   ├── PipelineCardGrid.tsx          # 卡片网格容器
│       │   ├── PipelineSearchFilter.tsx      # 搜索过滤栏
│       │   ├── PipelineCanvas.tsx            # §2.2
│       │   ├── NodePanel.tsx                 # §2.3
│       │   ├── DraggableNodeItem.tsx
│       │   ├── NodeCategoryGroup.tsx
│       │   ├── PropertyPanel.tsx             # §2.4
│       │   ├── NodePropertyForm.tsx
│       │   ├── EdgePropertyForm.tsx
│       │   ├── DomainPropertyForm.tsx
│       │   ├── DegradationTab.tsx
│       │   ├── DomainContainer.tsx           # §2.5
│       │   ├── WorkbenchToolbar.tsx          # §2.6
│       │   ├── GenericNode.tsx               # §2.7
│       │   ├── AggregationNode.tsx           # §2.8
│       │   ├── CompoundNode.tsx              # §2.9
│       │   ├── DataFlowEdge.tsx              # §2.10
│       │   ├── ConditionalEdge.tsx           # §2.11
│       │   ├── DegradationEdge.tsx           # §2.12
│       │   ├── DomainCreateDrawer.tsx
│       │   ├── CreatePipelineModal.tsx
│       │   ├── SaveConfirmModal.tsx
│       │   ├── DryRunResultPanel.tsx
│       │   ├── DiffPanel.tsx
│       │   └── EditView.tsx                  # 编辑视图三栏布局容器
│       ├── stores/
│       │   ├── pipelineWorkbenchStore.ts     # §3.1 主 Store
│       │   └── pipelineListStore.ts          # §3.3 列表 Store
│       ├── hooks/
│       │   ├── usePipelineCanvas.ts          # 画布交互逻辑 Hook
│       │   ├── useNodeDragValidation.ts      # 节点拖拽校验 Hook
│       │   └── useEdgeValidation.ts          # 边兼容性校验 Hook
│       ├── constants/
│       │   ├── nodeDefinitions.ts            # 28 种节点定义常量（NODE_TYPE_DEFINITIONS）
│       │   ├── edgeValidation.ts             # 边类型兼容性映射（CAN_CONNECT_MAP）
│       │   └── limits.ts                     # 上限常量（MAX_DOMAINS, MAX_NODES_PER_DOMAIN 等）
│       └── __tests__/
│           ├── PipelineCard.test.tsx
│           ├── NodePanel.test.tsx
│           ├── PropertyPanel.test.tsx
│           ├── WorkbenchToolbar.test.tsx
│           ├── PipelineEditWorkflow.test.tsx
│           ├── DomainOperations.test.tsx
│           ├── DragDropConstraints.test.tsx
│           ├── NodeLimits.test.tsx
│           ├── UndoRedo.test.tsx
│           ├── DryRun.test.tsx
│           ├── ViewSwitching.test.tsx
│           ├── CanvasInteractions.test.tsx
│           └── CompoundNode.test.tsx
```

---

## 附录 A：验收标准覆盖（来自需求文档）

| 验收标准 | 实现位置 |
|---------|---------|
| AC-2.1 卡片视图展示正确 | `PipelineCard` (§2.1) + `PipelineListPage` |
| AC-2.2 新建管道后自动进入编辑视图 | 交互流程 §5.1 |
| AC-2.3 三视图切换不丢失编辑状态 | 交互流程 §5.7 + store `activeView` + `switchView` |
| AC-2.4 编辑→评估，自动加载评估历史 | 交互流程 §5.7 + `switchView` 中的 `loadEvalRuns` |
| AC-2.5 编辑→发布，切换到发布视图 | 交互流程 §5.7 |
| AC-2.6 域内节点拖到域外阻止 | `onNodeDragStop` + `useNodeDragValidation` + TC-CANVAS-01 |
| AC-2.7 聚合节点拖到域内阻止 | `onDrop` + 拖拽流程 §5.3 + TC-INTEG-03 |
| AC-2.8 条件边/降级边正确渲染 | `ConditionalEdge` (§2.11) + `DegradationEdge` (§2.12) |
| AC-2.9 属性面板显示可配置参数 | `PropertyPanel` (§2.4) + `NodePropertyForm` 动态表单 |
| AC-2.10 保存后版本号自增 | 保存流程 §5.5 + API `updatePipeline` |
| AC-2.11 干运行结果显示成功/失败 | 干运行流程 §5.6 + `DryRunResultPanel` |
| AC-2.12 撤销/重做正常工作 | Store `undoStack`/`redoStack` + `undo()` / `redo()` (§3.2) |
| AC-2.13 版本对比高亮差异 | `DiffPanel` + 版本对比流程 §5.8 |
| AC-2.14 [+ 添加业务域] 按钮+抽屉 | `DomainCreateDrawer` + 添加域流程 §5.2 |
| AC-2.15 知识库下拉过滤无权限库 | `listAccessibleKnowledgeBases` API + 下拉渲染 |
| AC-2.16 删除域二次确认 | `DomainContainer` × 按钮 + 二次确认弹窗 |
| AC-2.17 更换知识库自动更新检索节点 | `DomainPropertyForm` 知识库更换 → `updateDomain` → 遍历域内检索节点更新 `knowledgeBaseId` |
