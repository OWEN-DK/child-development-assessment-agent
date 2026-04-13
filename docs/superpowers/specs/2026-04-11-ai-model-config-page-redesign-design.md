# AI 模型配置页面与系统配置重构设计方案

## 一、设计目标

### 1.1 核心目标
- 将 AI 模型配置从全局统一参数改造为场景化独立配置
- 重构系统配置页面，优化导航、表单管理和批量操作体验
- 采用组件化 + 轻量配置驱动架构，提升代码复用率和可维护性

### 1.2 设计原则
- **组件化优先**：提取可复用的基础组件，避免代码重复
- **配置驱动**：通过 Schema 定义驱动渲染，降低新增配置成本
- **向后兼容**：现有 API 接口保持不变，前端适配新结构
- **用户体验**：智能联动、参数校验、批量操作、差异对比

---

## 二、后端配置架构设计

### 2.1 场景化配置结构

每个 LLM 场景的完整配置结构：

```python
class LLMSceneConfig:
    model_name: str          # 模型名称
    provider: str            # 提供商 (tongyi/openai/anthropic/ollama)
    temperature: float       # 温度 (0-1)
    max_tokens: int          # 最大生成长度
    retry_count: int         # 重试次数
    timeout: int             # 超时秒数
    api_key: Optional[str]   # 可选：独立API密钥（默认继承全局）
    base_url: Optional[str]  # 可选：独立接口地址（默认继承全局）
```

### 2.2 9 个独立场景对应

| 场景ID | 场景名称 | 原有配置项 | 用途说明 |
|--------|----------|------------|----------|
| 1 | report_generation | 评估报告生成 | 生成最终用户可读的评估报告 |
| 2 | assessment | 儿童发展评估 | 分析儿童发展状态，对标里程碑 |
| 3 | validation | 结果校验 | 数据格式校验和智能补全 |
| 4 | query_rewrite | 查询重写 | RAG查询语句优化改写 |
| 5 | metadata_extraction | 元数据提取 | 文档元数据自动提取 |
| 6 | vl_parsing | 多模态解析 | 扫描版PDF/图片内容识别 |
| 7 | query_classification | 查询分类 | RAG查询类型智能分类 |
| 8 | synonym_expand | 同义词扩展 | RAG查询同义词扩展 |
| 9 | memory_extraction | 记忆提取 | 历史上下文特征提取 |

### 2.3 配置分组设计

#### A. LLM模型组
- **全局配置区**：多提供商全局API密钥、基础地址配置（可被场景独立配置覆盖）
- **场景配置区**：9个场景卡片，每个卡片包含上述完整7项参数

#### B. Embedding模型组
- **统一配置**：模型名称、最大文本长度、批处理大小（当前只有一个Embedding场景）

#### C. ML评分模型组
- **独立配置**：模型名称、提供商、温度、max_tokens、重试、超时

### 2.4 接口设计（兼容现有接口）

#### GET /api/v1/config 返回示例

```json
{
  "config": [
    {
      "key": "llm_report_generation_model",
      "category": "ai-models.llm.report-generation",
      "description": "报告生成模型名称",
      "default_value": "qwen3.5-plus",
      "current_value": "qwen3.5-plus",
      "type": "string"
    },
    {
      "key": "llm_report_generation_provider",
      "category": "ai-models.llm.report-generation",
      "description": "报告生成提供商",
      "default_value": "tongyi",
      "current_value": "tongyi",
      "type": "string"
    },
    {
      "key": "llm_report_generation_temperature",
      "category": "ai-models.llm.report-generation",
      "description": "报告生成温度",
      "default_value": 0.7,
      "current_value": 0.7,
      "type": "float"
    },
    {
      "key": "embedding_model_name",
      "category": "ai-models.embedding",
      "description": "Embedding模型名称",
      "default_value": "text-embedding-v4",
      "current_value": "text-embedding-v4",
      "type": "string"
    }
  ]
}
```

#### PUT /api/v1/config 提交格式不变，自动适配新增的配置key

---

## 三、前端架构设计

### 3.1 目录结构

```
frontend/src/
├── pages/
│   └── SystemConfigPage.tsx              # 重构：系统配置主页面
│
├── features/system-config/
│   ├── components/                       # 可复用组件
│   │   ├── ModelConfigForm.tsx           # 通用模型配置表单组件
│   │   ├── GlobalProviderConfig.tsx      # 全局提供商配置（折叠面板）
│   │   ├── BatchOperationsBar.tsx        # 批量操作栏
│   │   ├── ConfigFieldRenderer.tsx       # 配置字段渲染器
│   │   ├── CategoryTree.tsx              # 配置分类树
│   │   ├── VersionManager.tsx            # 版本管理器
│   │   └── LLMSceneCard.tsx              # LLM 场景卡片（重构）
│   │
│   ├── schemas/                          # 配置 Schema 定义
│   │   ├── llmScenes.ts                  # LLM 9 个场景 Schema
│   │   ├── embeddingSchema.ts            # Embedding Schema
│   │   ├── mlScoringSchema.ts            # ML Scoring Schema
│   │   └── index.ts
│   │
│   └── pages/                            # 页面组件
│       ├── LLMModelsPage.tsx             # 重构：LLM 模型配置
│       ├── EmbeddingModelsPage.tsx       # 重构：Embedding 配置
│       └── MLScoringModelsPage.tsx       # 重构：ML Scoring 配置
│
├── components/config/                    # 保留并优化
│   ├── DynamicConfigForm.tsx             # 优化：动态配置表单
│   ├── ConfigVersionSelector.tsx         # 优化：版本选择器
│   └── ConfigDiffView.tsx                # 启用：差异对比视图
│
└── store/
    └── configStore.ts                    # 优化：配置状态管理
```

### 3.2 核心组件设计

#### 3.2.1 ModelConfigForm（通用模型配置表单）

**职责**：渲染模型配置的通用字段，支持所有模型类型（LLM/Embedding/ML Scoring）

**Props 接口**：

```typescript
interface ModelConfigFormProps {
  schema: ConfigSchema;                    // 配置 Schema
  initialValues: Record<string, any>;      // 初始值
  onChange: (values: Record<string, any>) => void;  // 值变更回调
  onSave?: () => void;                     // 保存回调（可选）
  onReset?: () => void;                    // 重置回调（可选）
  loading?: boolean;                       // 加载状态
}
```

**渲染字段**：
- 提供商选择器（Select）
- 模型名称输入框（Input，支持智能提示）
- 温度滑块（Slider，0~1，步长0.1）
- 最大 Tokens（InputNumber，1~40960）
- 重试次数（InputNumber，1~10）
- 超时秒数（InputNumber，1~300）
- 独立 API 配置开关（Switch）
  - API 密钥（Input.Password）
  - Base URL（Input）

**智能联动**：
- 选择不同提供商时，模型名称输入框自动提示该提供商常用模型列表
- 切换提供商时，自动带入该提供商默认参数（如温度默认0.7，max_tokens默认2048）

#### 3.2.2 GlobalProviderConfig（全局提供商配置）

**职责**：渲染全局提供商 API 密钥和 BaseURL 配置（折叠面板，默认收起）

**Props 接口**：

```typescript
interface GlobalProviderConfigProps {
  initialValues: GlobalProviderConfig;
  onChange: (values: GlobalProviderConfig) => void;
  onSave: () => void;
  loading?: boolean;
}

interface GlobalProviderConfig {
  tongyi_api_key?: string;
  openai_api_key?: string;
  openai_base_url?: string;
  anthropic_api_key?: string;
  ollama_base_url?: string;
}
```

**布局**：
- 使用 Ant Design Collapse 组件
- 每个提供商一个面板
- 底部保存/重置按钮

#### 3.2.3 BatchOperationsBar（批量操作栏）

**职责**：提供批量操作功能

**Props 接口**：

```typescript
interface BatchOperationsBarProps {
  onApplyToAll: (config: Partial<LLMSceneConfig>) => void;
  onResetAll: () => void;
  onExportConfig: () => void;
  onImportConfig: (json: string) => void;
}
```

**功能**：
- 应用配置到所有场景
- 一键恢复所有默认配置
- 导出配置为 JSON
- 从 JSON 导入配置

#### 3.2.4 ConfigFieldRenderer（配置字段渲染器）

**职责**：根据字段类型自动选择对应的 Ant Design 控件

**Props 接口**：

```typescript
interface ConfigFieldRendererProps {
  field: ConfigFieldMetadata;
  form: FormInstance;
}
```

**字段类型映射**：

| 字段类型 | 控件 | 说明 |
|---------|------|------|
| `bool` | Switch | 布尔开关 |
| `int` | InputNumber | 整数输入（step=1） |
| `float` | InputNumber | 浮点数输入（step=0.05） |
| `str` | Input | 字符串输入 |
| `list` | 列表编辑器 | 动态增删字符串列表 |
| `dict` | 字典编辑器 | 键值对/树形字典/JSON |

#### 3.2.5 CategoryTree（配置分类树）

**职责**：渲染左侧配置分类导航

**Props 接口**：

```typescript
interface CategoryTreeProps {
  config: CategoryConfig;
  onSelect: (key: string) => void;
  activeKey: string;
}
```

**分类配置结构**：

```typescript
const CATEGORY_CONFIG = {
  'app': { 
    title: '📦 应用设置', 
    order: 1,
    children: {
      'logging': { title: '日志配置', order: 1 },
      'paths': { title: '路径配置', order: 2 }
    }
  },
  'ai-models': { 
    title: '🤖 AI 模型配置', 
    order: 2,
    children: {
      'llm': { title: 'LLM 模型', order: 1, route: '/system-config/models/llm' },
      'embedding': { title: 'Embedding 模型', order: 2, route: '/system-config/models/embedding' },
      'ml_scoring': { title: 'ML 评分模型', order: 3, route: '/system-config/models/ml-scoring' }
    }
  },
  'rag': { 
    title: '📚 RAG 知识库', 
    order: 3,
    children: {
      'core': { title: '核心设置', order: 1 },
      'retrieval': { title: '检索配置', order: 2 },
      'chunking': { title: '分块配置', order: 3 },
      'vector_store': { title: '向量存储', order: 4 },
      'pageindex': { title: 'PageIndex 索引', order: 5 },
      'pipeline': { title: '导入流水线', order: 6 },
      'test': { title: 'RAG 测试配置', order: 7 }
    }
  },
  'rules': { 
    title: '⚙️ 业务规则', 
    order: 4,
    children: {
      'validation': { title: '校验规则', order: 1 },
      'assessment': { title: '评估规则', order: 2 },
      'scoring': { title: '评分规则', order: 3 },
      'preprocessing': { title: '预处理规则', order: 4 },
      'metadata': { title: '元数据规则', order: 5 }
    }
  }
};
```

#### 3.2.6 VersionManager（版本管理器）

**职责**：配置版本管理（查看/切换/回滚/对比）

**Props 接口**：

```typescript
interface VersionManagerProps {
  versions: ConfigVersion[];
  activeVersion: string;
  onRollback: (versionId: string) => void;
  onCompare: (v1: string, v2: string) => void;
}
```

**功能**：
- 展示历史版本列表（版本 ID、创建时间、描述）
- 标记当前活跃版本
- 支持回滚到指定版本（带确认弹窗）
- 支持版本对比（打开 ConfigDiffView 弹窗）

### 3.3 配置 Schema 定义

#### 3.3.1 Schema 接口

```typescript
interface ConfigSchema {
  fields: ConfigField[];
  layout?: 'vertical' | 'horizontal' | 'grid';
  initialValues?: Record<string, any>;
  validation?: Record<string, ValidationRule[]>;
}

interface ConfigField {
  key: string;
  label: string;
  type: 'select' | 'input' | 'slider' | 'number' | 'password' | 'switch';
  props?: Record<string, any>;
  tooltip?: string;
  required?: boolean;
}
```

#### 3.3.2 LLM 场景 Schema 示例

```typescript
const LLM_SCENE_SCHEMA: ConfigSchema = {
  fields: [
    {
      key: 'provider',
      label: '提供商',
      type: 'select',
      props: {
        options: [
          { value: 'tongyi', label: '通义千问' },
          { value: 'openai', label: 'OpenAI' },
          { value: 'anthropic', label: 'Anthropic' },
          { value: 'ollama', label: 'Ollama' },
        ],
      },
      required: true,
    },
    {
      key: 'model_name',
      label: '模型名称',
      type: 'input',
      props: {
        placeholder: '手动输入模型名称',
      },
      required: true,
    },
    {
      key: 'temperature',
      label: '温度',
      type: 'slider',
      props: {
        min: 0,
        max: 1,
        step: 0.1,
      },
      required: true,
    },
    {
      key: 'max_tokens',
      label: '最大 Tokens',
      type: 'number',
      props: {
        min: 1,
        max: 40960,
      },
      required: true,
    },
    {
      key: 'retry_count',
      label: '重试次数',
      type: 'number',
      props: {
        min: 1,
        max: 10,
      },
    },
    {
      key: 'timeout',
      label: '超时秒数',
      type: 'number',
      props: {
        min: 1,
        max: 300,
      },
    },
    {
      key: 'use_independent_config',
      label: '使用独立 API 配置',
      type: 'switch',
    },
    {
      key: 'api_key',
      label: 'API 密钥',
      type: 'password',
      props: {
        placeholder: '留空则使用全局配置',
      },
      visible: (values) => values.use_independent_config,
    },
    {
      key: 'base_url',
      label: 'Base URL',
      type: 'input',
      props: {
        placeholder: '留空则使用全局配置',
      },
      visible: (values) => values.use_independent_config,
    },
  ],
  validation: {
    provider: [{ required: true, message: '请选择提供商' }],
    model_name: [{ required: true, message: '请输入模型名称' }],
    temperature: [
      { type: 'number', min: 0, max: 1, message: '温度范围 0~1' },
    ],
    max_tokens: [
      { type: 'number', min: 1, max: 40960, message: 'Tokens 范围 1~40960' },
    ],
    retry_count: [
      { type: 'number', min: 1, max: 10, message: '重试次数范围 1~10' },
    ],
    timeout: [
      { type: 'number', min: 1, max: 300, message: '超时范围 1~300 秒' },
    ],
  },
};
```

#### 3.3.3 Embedding Schema

```typescript
const EMBEDDING_SCHEMA: ConfigSchema = {
  fields: [
    {
      key: 'model_name',
      label: '模型名称',
      type: 'input',
      props: {
        placeholder: '例如：text-embedding-v4',
      },
      required: true,
    },
    {
      key: 'max_text_length',
      label: '最大文本长度',
      type: 'number',
      props: {
        min: 1,
        max: 8192,
      },
      required: true,
    },
    {
      key: 'batch_size',
      label: '批处理大小',
      type: 'number',
      props: {
        min: 1,
        max: 100,
      },
      required: true,
    },
  ],
  validation: {
    model_name: [{ required: true, message: '请输入模型名称' }],
    max_text_length: [
      { type: 'number', min: 1, max: 8192, message: '范围 1~8192' },
    ],
    batch_size: [
      { type: 'number', min: 1, max: 100, message: '范围 1~100' },
    ],
  },
};
```

#### 3.3.4 ML Scoring Schema

```typescript
const ML_SCORING_SCHEMA: ConfigSchema = {
  fields: [
    {
      key: 'provider',
      label: '提供商',
      type: 'select',
      props: {
        options: [
          { value: 'tongyi', label: '通义千问' },
          { value: 'openai', label: 'OpenAI' },
          { value: 'anthropic', label: 'Anthropic' },
          { value: 'ollama', label: 'Ollama' },
        ],
      },
      required: true,
    },
    {
      key: 'model_name',
      label: '模型名称',
      type: 'input',
      required: true,
    },
    {
      key: 'temperature',
      label: '温度',
      type: 'slider',
      props: {
        min: 0,
        max: 1,
        step: 0.1,
      },
    },
    {
      key: 'max_tokens',
      label: '最大 Tokens',
      type: 'number',
      props: {
        min: 1,
        max: 40960,
      },
    },
    {
      key: 'retry_count',
      label: '重试次数',
      type: 'number',
      props: {
        min: 1,
        max: 10,
      },
    },
    {
      key: 'timeout',
      label: '超时秒数',
      type: 'number',
      props: {
        min: 1,
        max: 300,
      },
    },
    {
      key: 'use_independent_config',
      label: '使用独立 API 配置',
      type: 'switch',
    },
    {
      key: 'api_key',
      label: 'API 密钥',
      type: 'password',
      visible: (values) => values.use_independent_config,
    },
    {
      key: 'base_url',
      label: 'Base URL',
      type: 'input',
      visible: (values) => values.use_independent_config,
    },
  ],
};
```

---

## 四、页面布局设计

### 4.1 SystemConfigPage（系统配置主页面）

**布局结构**：

```
┌─────────────────────────────────────────────────────┐
│  SystemConfigPage                                   │
│  ┌──────────────┬──────────────────────────────────┐│
│  │  Sidebar     │  Main Content                    ││
│  │              │                                  ││
│  │ ┌──────────┐ │  ┌────────────────────────────┐ ││
│  │ │ Category │ │  │ Header                     │ ││
│  │ │ Tree     │ │  │ 标题 + 保存/恢复按钮       │ ││
│  │ │          │ │  └────────────────────────────┘ ││
│  │ └──────────┘ │                                  ││
│  │ ┌──────────┐ │  ┌────────────────────────────┐ ││
│  │ │ Version  │ │  │ Content                    │ ││
│  │ │ Manager  │ │  │ DynamicConfigForm          │ ││
│  │ │          │ │  │ 或 <Outlet /> (子路由)     │ ││
│  │ └──────────┘ │  └────────────────────────────┘ ││
│  └──────────────┴──────────────────────────────────┘│
└─────────────────────────────────────────────────────┘
```

**交互逻辑**：
- 左侧显示配置分类树（CategoryTree）
- 点击分类节点，右侧渲染对应配置（DynamicConfigForm）
- 点击 AI 模型子分类，路由到子页面（`<Outlet />`）
- 底部显示版本管理器（VersionManager）

### 4.2 LLMModelsPage（LLM 模型配置页）

**布局结构**：

```
┌─────────────────────────────────────────────────────┐
│  LLMModelsPage                                      │
│  ┌────────────────────────────────────────────────┐ │
│  │ GlobalProviderConfig (折叠面板，默认收起)      │ │
│  │  ┌──────────────────────────────────────────┐ │ │
│  │  │ 通义千问 API 密钥                        │ │ │
│  │  │ OpenAI API 密钥 + BaseURL                │ │ │
│  │  │ Anthropic API 密钥                       │ │ │
│  │  │ Ollama BaseURL                           │ │ │
│  │  │ [保存] [重置]                            │ │ │
│  │  └──────────────────────────────────────────┘ │ │
│  └────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────┐ │
│  │ BatchOperationsBar                             │ │
│  │ [应用到所有场景] [恢复所有默认] [导出] [导入] │ │
│  └────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────┐ │
│  │ Scenes Grid (3列布局)                          │ │
│  │ ┌────────┐ ┌────────┐ ┌────────┐              │ │
│  │ │ Scene 1│ │ Scene 2│ │ Scene 3│              │ │
│  │ └────────┘ └────────┘ └────────┘              │ │
│  │ ┌────────┐ ┌────────┐ ┌────────┐              │ │
│  │ │ Scene 4│ │ Scene 5│ │ Scene 6│              │ │
│  │ └────────┘ └────────┘ └────────┘              │ │
│  │ ┌────────┐ ┌────────┐ ┌────────┐              │ │
│  │ │ Scene 7│ │ Scene 8│ │ Scene 9│              │ │
│  │ └────────┘ └────────┘ └────────┘              │ │
│  └────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

**场景卡片布局**（每张卡片）：

```
┌─────────────────────────────────────┐
│ 场景名称 ℹ️               [恢复默认]│
├─────────────────────────────────────┤
│ 提供商：[下拉选择 ▼]                │
│ 模型名称：[输入框]                  │
│ 温度：0.7 [━━━━━━━━●━━━━━━━]       │
│ 最大 Tokens：[2048]                 │
│ 重试次数：[2]                       │
│ 超时秒数：[60]                      │
│ 使用独立 API 配置：[开关]           │
│   API 密钥：[密码输入框]            │
│   Base URL：[输入框]                │
├─────────────────────────────────────┤
│                        [保存]       │
└─────────────────────────────────────┘
```

### 4.3 EmbeddingModelsPage（Embedding 模型配置页）

**布局结构**：

```
┌─────────────────────────────────────────────────────┐
│  EmbeddingModelsPage                                │
│  ┌────────────────────────────────────────────────┐ │
│  │ Card: Embedding 模型配置                       │ │
│  │  ┌──────────────────────────────────────────┐ │ │
│  │  │ 模型名称：[text-embedding-v4]            │ │ │
│  │  │ 最大文本长度：[1536]                     │ │ │
│  │  │ 批处理大小：[10]                         │ │ │
│  │  │ [保存] [重置]                            │ │ │
│  │  └──────────────────────────────────────────┘ │ │
│  └────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

### 4.4 MLScoringModelsPage（ML 评分模型配置页）

**布局结构**：

```
┌─────────────────────────────────────────────────────┐
│  MLScoringModelsPage                                │
│  ┌────────────────────────────────────────────────┐ │
│  │ Card: ML 评分模型配置                          │ │
│  │  ┌──────────────────────────────────────────┐ │ │
│  │  │ 提供商：[下拉选择 ▼]                     │ │ │
│  │  │ 模型名称：[输入框]                       │ │ │
│  │  │ 温度：0.5 [━━━━━●━━━━━━━━━━━]           │ │ │
│  │  │ 最大 Tokens：[2048]                      │ │ │
│  │  │ 重试次数：[2]                            │ │ │
│  │  │ 超时秒数：[30]                           │ │ │
│  │  │ 使用独立 API 配置：[开关]                │ │ │
│  │  │   API 密钥：[密码输入框]                 │ │ │
│  │  │   Base URL：[输入框]                     │ │ │
│  │  │ [保存] [重置]                            │ │ │
│  │  └──────────────────────────────────────────┘ │ │
│  └────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

---

## 五、核心特性设计

### 5.1 智能联动

**提供商切换联动**：

```typescript
const PROVIDER_DEFAULTS = {
  tongyi: {
    models: ['qwen3.5-plus', 'qwen3.5-turbo', 'qwen-plus'],
    temperature: 0.7,
    max_tokens: 2048,
  },
  openai: {
    models: ['gpt-4o', 'gpt-4o-mini', 'gpt-3.5-turbo'],
    temperature: 0.7,
    max_tokens: 2048,
  },
  anthropic: {
    models: ['claude-3-5-sonnet', 'claude-3-haiku'],
    temperature: 0.7,
    max_tokens: 2048,
  },
  ollama: {
    models: ['llama3', 'mistral', 'qwen2.5'],
    temperature: 0.7,
    max_tokens: 2048,
  },
};

const handleProviderChange = (provider: string) => {
  setLocalConfig({
    ...localConfig,
    provider,
    model_name: PROVIDER_DEFAULTS[provider].models[0],
    temperature: PROVIDER_DEFAULTS[provider].temperature,
    max_tokens: PROVIDER_DEFAULTS[provider].max_tokens,
  });
};
```

**模型名称智能提示**：

```typescript
const getModelSuggestions = (provider: string) => {
  return PROVIDER_DEFAULTS[provider].models.map(model => ({
    value: model,
    label: model,
  }));
};

// 使用 Ant Design AutoComplete 组件
<AutoComplete
  value={localConfig.model_name}
  options={getModelSuggestions(localConfig.provider)}
  onChange={(value) => setLocalConfig({ ...localConfig, model_name: value })}
/>
```

### 5.2 参数校验

**校验规则**：

| 参数 | 范围 | 校验规则 |
|------|------|----------|
| 温度 | 0~1 | 自动限制范围，输入非法值自动重置为边界值 |
| 最大 Tokens | 1~40960 | 数字输入校验，超出范围自动修正 |
| 重试次数 | 1~10 | 数字输入校验 |
| 超时秒数 | 1~300 | 数字输入校验 |
| 模型名称 | 必填 | 标红提示 |
| 提供商 | 必填 | 标红提示 |

**实现方式**：

```typescript
const validateField = (key: string, value: any, rules: ValidationRule[]) => {
  for (const rule of rules) {
    if (rule.required && !value) {
      return { valid: false, message: rule.message };
    }
    if (rule.type === 'number') {
      const num = Number(value);
      if (isNaN(num) || num < rule.min || num > rule.max) {
        return { valid: false, message: rule.message };
      }
    }
  }
  return { valid: true };
};
```

### 5.3 批量操作

**应用配置到所有场景**：

```typescript
const handleBatchApply = (sceneId: string, config: LLMSceneConfig) => {
  Modal.confirm({
    title: '应用配置到所有场景',
    content: `确定要将"${LLM_SCENES.find(s => s.id === sceneId)?.name}"的配置应用到所有场景吗？`,
    onOk: async () => {
      const otherScenes = LLM_SCENES.filter(s => s.id !== sceneId);
      await configApi.batchUpdateLLMScenes(
        otherScenes.map(s => ({
          sceneId: s.id,
          config: {
            ...configs[s.id],
            provider: config.provider,
            temperature: config.temperature,
            max_tokens: config.max_tokens,
          }
        }))
      );
      message.success('已应用到所有场景');
      loadConfigs();
    },
  });
};
```

**恢复所有默认配置**：

```typescript
const handleResetAll = async () => {
  Modal.confirm({
    title: '恢复所有默认配置',
    content: '此操作将恢复所有场景到默认配置，是否继续？',
    onOk: async () => {
      await configApi.resetAllLLMScenes();
      message.success('已恢复所有默认配置');
      loadConfigs();
    },
  });
};
```

### 5.4 配置对比

**版本对比**：

```typescript
const handleCompareVersions = async (v1: string, v2: string) => {
  const diff = await configApi.compareConfigVersions(v1, v2);
  setDiffData(diff);
  setDiffModalVisible(true);
};
```

**差异高亮显示**：

```typescript
const ConfigDiffView = ({ version1, version2 }) => {
  const diff = calculateDiff(version1, version2);
  
  return (
    <Table
      dataSource={diff.changes}
      columns={[
        { title: '配置项', dataIndex: 'key' },
        { 
          title: '版本1', 
          dataIndex: 'value1',
          render: (value, record) => (
            record.type === 'removed' ? <Text delete>{value}</Text> : value
          )
        },
        { 
          title: '版本2', 
          dataIndex: 'value2',
          render: (value, record) => (
            record.type === 'added' ? <Text type="success">{value}</Text> : 
            record.type === 'modified' ? <Text type="warning">{value}</Text> : value
          )
        },
        { 
          title: '变更类型', 
          dataIndex: 'type',
          render: (type) => (
            <Tag color={type === 'added' ? 'green' : type === 'removed' ? 'red' : 'orange'}>
              {type === 'added' ? '新增' : type === 'removed' ? '删除' : '修改'}
            </Tag>
          )
        },
      ]}
    />
  );
};
```

---

## 六、数据流设计

### 6.1 配置加载流程

```
用户访问页面
  ↓
useEffect 触发
  ↓
configApi.getAllLLMScenes() / getConfig()
  ↓
setConfigs() / loadConfig()
  ↓
UI 渲染（ModelConfigForm / DynamicConfigForm）
```

### 6.2 配置保存流程

```
用户点击保存
  ↓
表单校验（validateFields）
  ↓
configApi.updateLLMScene() / updateConfig()
  ↓
后端保存
  ↓
message.success('配置保存成功')
  ↓
loadConfigs() 刷新配置
```

### 6.3 草稿机制

```typescript
// 使用 Zustand 管理草稿状态
interface ConfigStore {
  draftChanges: Record<string, any>;
  updateDraft: (key: string, value: any) => void;
  saveConfig: (description: string) => Promise<void>;
  resetDraft: () => void;
}

// 本地表单状态
const [form] = Form.useForm();

// 监听表单变化
const handleValuesChange = (changedValues: any, allValues: any) => {
  Object.entries(changedValues).forEach(([key, value]) => {
    updateDraft(key, value);
  });
};

// 保存时提交所有草稿变更
const handleSave = async () => {
  await saveConfig('Manual update from config page');
  resetDraft();
  form.resetFields();
};
```

---

## 七、API 层设计

### 7.1 现有 API 端点

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/v1/config` | GET | 获取所有配置字段 |
| `/api/v1/config` | PUT | 更新配置 |
| `/api/v1/config/versions` | GET | 获取版本列表 |
| `/api/v1/config/rollback/{versionId}` | POST | 回滚到指定版本 |
| `/api/v1/config/reset` | POST | 恢复出厂设置 |
| `/api/v1/config/ai-models/llm-scenes` | GET | 获取所有 LLM 场景配置 |
| `/api/v1/config/ai-models/llm-scenes/{sceneId}` | PUT | 更新单个 LLM 场景 |
| `/api/v1/config/ai-models/llm-scenes/batch-update` | POST | 批量更新 LLM 场景 |

### 7.2 需要新增的 API 端点

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/v1/config/ai-models/embedding` | GET | 获取 Embedding 配置 |
| `/api/v1/config/ai-models/embedding` | PUT | 更新 Embedding 配置 |
| `/api/v1/config/ai-models/ml-scoring` | GET | 获取 ML Scoring 配置 |
| `/api/v1/config/ai-models/ml-scoring` | PUT | 更新 ML Scoring 配置 |
| `/api/v1/config/ai-models/llm-scenes/{sceneId}/reset` | POST | 重置单个场景到默认值 |
| `/api/v1/config/ai-models/llm-scenes/reset-all` | POST | 重置所有场景到默认值 |
| `/api/v1/config/compare/{v1}/{v2}` | GET | 对比两个版本的配置差异 |

### 7.3 API 层 TypeScript 类型

```typescript
export interface LLMSceneConfig {
  model_name: string;
  provider: 'tongyi' | 'openai' | 'anthropic' | 'ollama';
  temperature: number;
  max_tokens: number;
  retry_count: number;
  timeout: number;
  api_key?: string;
  base_url?: string;
}

export interface EmbeddingConfig {
  model_name: string;
  max_text_length: number;
  batch_size: number;
}

export interface MLScoringConfig {
  model_name: string;
  provider: 'tongyi' | 'openai' | 'anthropic' | 'ollama';
  temperature: number;
  max_tokens: number;
  retry_count: number;
  timeout: number;
  api_key?: string;
  base_url?: string;
}

export interface GlobalProviderConfig {
  tongyi_api_key?: string;
  openai_api_key?: string;
  openai_base_url?: string;
  anthropic_api_key?: string;
  ollama_base_url?: string;
}

export interface ConfigFieldMetadata {
  key: string;
  category: string;
  description: string;
  default_value: any;
  current_value: any;
  type: 'str' | 'int' | 'float' | 'bool' | 'list' | 'dict';
  hot_reloadable: boolean;
  requires_restart: boolean;
  affected_components?: string[];
}

export interface ConfigVersion {
  version_id: string;
  created_at: string;
  created_by: string;
  description: string;
  is_active: boolean;
  parent_version_id?: string;
  is_factory_reset: boolean;
}

export interface ConfigDiff {
  changes: Array<{
    key: string;
    value1: any;
    value2: any;
    type: 'added' | 'removed' | 'modified';
  }>;
}
```

---

## 八、状态管理设计

### 8.1 Zustand Store

```typescript
interface ConfigStore {
  // 状态
  configFields: ConfigFieldMetadata[];
  activeVersion: string;
  versions: ConfigVersion[];
  draftChanges: Record<string, any>;
  llmScenes: Record<string, LLMSceneConfig>;
  embeddingConfig: EmbeddingConfig;
  mlScoringConfig: MLScoringConfig;
  globalProviderConfig: GlobalProviderConfig;
  isLoading: boolean;
  isSaving: boolean;
  
  // Actions
  loadConfig: () => Promise<void>;
  loadVersions: () => Promise<void>;
  loadLLMScenes: () => Promise<void>;
  loadEmbeddingConfig: () => Promise<void>;
  loadMLScoringConfig: () => Promise<void>;
  loadGlobalProviderConfig: () => Promise<void>;
  updateDraft: (key: string, value: any) => void;
  saveConfig: (description: string) => Promise<void>;
  saveLLMScene: (sceneId: string, config: LLMSceneConfig) => Promise<void>;
  saveEmbeddingConfig: (config: EmbeddingConfig) => Promise<void>;
  saveMLScoringConfig: (config: MLScoringConfig) => Promise<void>;
  saveGlobalProviderConfig: (config: GlobalProviderConfig) => Promise<void>;
  resetDraft: () => void;
  rollbackToVersion: (versionId: string) => Promise<void>;
  resetToFactory: () => Promise<void>;
  resetAllLLMScenes: () => Promise<void>;
}
```

### 8.2 状态流转

```
初始加载
  ↓
loadConfig() → 获取配置字段
loadVersions() → 获取版本列表
loadLLMScenes() → 获取 LLM 场景配置
loadEmbeddingConfig() → 获取 Embedding 配置
loadMLScoringConfig() → 获取 ML Scoring 配置
loadGlobalProviderConfig() → 获取全局提供商配置
  ↓
用户修改
  ↓
updateDraft() → 更新草稿
  ↓
用户保存
  ↓
saveConfig() / saveLLMScene() / ...
  ↓
刷新状态
  ↓
loadConfig() / loadLLMScenes() / ...
```

---

## 九、样式设计

### 9.1 设计令牌

```scss
// 颜色
$config-primary: #1890ff;
$config-success: #52c41a;
$config-warning: #faad14;
$config-error: #ff4d4f;
$config-text: rgba(0, 0, 0, 0.85);
$config-text-secondary: rgba(0, 0, 0, 0.45);
$config-border: #d9d9d9;
$config-bg: #f5f5f5;
$config-bg-light: #fafafa;

// 间距
$config-spacing-xs: 4px;
$config-spacing-sm: 8px;
$config-spacing-md: 16px;
$config-spacing-lg: 24px;
$config-spacing-xl: 32px;

// 圆角
$config-border-radius: 4px;
$config-border-radius-lg: 8px;

// 阴影
$config-shadow: 0 2px 8px rgba(0, 0, 0, 0.09);
$config-shadow-hover: 0 4px 12px rgba(0, 0, 0, 0.15);
```

### 9.2 场景卡片样式

```scss
.sceneCard {
  border-radius: $config-border-radius-lg;
  box-shadow: $config-shadow;
  transition: all 0.3s ease;

  &:hover {
    box-shadow: $config-shadow-hover;
    transform: translateY(-2px);
  }

  :global {
    .ant-card-head {
      border-bottom: 1px solid $config-border;
      padding: 0 $config-spacing-md;
    }

    .ant-card-body {
      padding: $config-spacing-md;
    }
  }
}

.cardContent {
  display: flex;
  flex-direction: column;
  gap: $config-spacing-md;
}

.formItem {
  display: flex;
  flex-direction: column;
  gap: $config-spacing-xs;

  label {
    font-weight: 500;
    color: $config-text;
  }
}

.cardActions {
  display: flex;
  justify-content: flex-end;
  gap: $config-spacing-sm;
  margin-top: $config-spacing-md;
  padding-top: $config-spacing-md;
  border-top: 1px solid $config-border;
}
```

### 9.3 批量操作栏样式

```scss
.batchOperationsBar {
  display: flex;
  align-items: center;
  gap: $config-spacing-md;
  padding: $config-spacing-md;
  background: $config-bg-light;
  border: 1px solid $config-border;
  border-radius: $config-border-radius;
  margin-bottom: $config-spacing-lg;
}
```

---

## 十、错误处理设计

### 10.1 表单校验错误

```typescript
const handleSave = async () => {
  try {
    const values = await form.validateFields();
    await saveConfig(values);
    message.success('配置保存成功');
  } catch (error) {
    if (error.errorFields) {
      // 表单校验错误
      message.error('请检查表单填写是否正确');
    } else {
      // API 错误
      message.error(`保存失败：${error.message}`);
    }
  }
};
```

### 10.2 API 错误处理

```typescript
const handleApiError = (error: any, fallbackMessage: string) => {
  if (error.response) {
    // 服务器返回错误状态码
    const { status, data } = error.response;
    switch (status) {
      case 400:
        message.error(data.detail || '请求参数错误');
        break;
      case 401:
        message.error('未授权，请重新登录');
        break;
      case 403:
        message.error('权限不足');
        break;
      case 404:
        message.error('资源不存在');
        break;
      case 500:
        message.error('服务器内部错误');
        break;
      default:
        message.error(data.detail || fallbackMessage);
    }
  } else if (error.request) {
    // 请求发送但未收到响应
    message.error('网络错误，请检查网络连接');
  } else {
    // 其他错误
    message.error(fallbackMessage);
  }
};
```

### 10.3 加载状态处理

```typescript
const [loading, setLoading] = useState(false);

const loadData = async () => {
  setLoading(true);
  try {
    const response = await configApi.getConfig();
    setData(response);
  } catch (error) {
    handleApiError(error, '加载失败');
  } finally {
    setLoading(false);
  }
};

// UI 中显示加载状态
<Spin spinning={loading}>
  <Form>...</Form>
</Spin>
```

---

## 十一、性能优化设计

### 11.1 组件懒加载

```typescript
// 路由懒加载
const LLMModelsPage = lazy(() => import('@/features/system-config/pages/LLMModelsPage'));
const EmbeddingModelsPage = lazy(() => import('@/features/system-config/pages/EmbeddingModelsPage'));
const MLScoringModelsPage = lazy(() => import('@/features/system-config/pages/MLScoringModelsPage'));

// 路由配置
<Route
  path="/system-config/models/llm"
  element={
    <Suspense fallback={<div>Loading...</div>}>
      <LLMModelsPage />
    </Suspense>
  }
/>
```

### 11.2 虚拟滚动

对于配置字段较多的场景，使用虚拟滚动优化性能：

```typescript
import { FixedSizeList } from 'react-window';

const VirtualizedConfigForm = ({ fields }) => {
  const Row = ({ index, style }) => (
    <div style={style}>
      <ConfigFieldRenderer field={fields[index]} />
    </div>
  );

  return (
    <FixedSizeList
      height={600}
      itemCount={fields.length}
      itemSize={80}
      width="100%"
    >
      {Row}
    </FixedSizeList>
  );
};
```

### 11.3 防抖优化

对于频繁触发的操作（如输入框），使用防抖优化：

```typescript
import { debounce } from 'lodash-es';

const handleInputChange = debounce((key: string, value: any) => {
  updateDraft(key, value);
}, 300);
```

---

## 十二、测试策略

### 12.1 单元测试

**组件测试**：

```typescript
import { render, screen, fireEvent } from '@testing-library/react';
import { ModelConfigForm } from './ModelConfigForm';

describe('ModelConfigForm', () => {
  it('应该正确渲染所有字段', () => {
    render(<ModelConfigForm schema={LLM_SCENE_SCHEMA} initialValues={{}} onChange={() => {}} />);
    
    expect(screen.getByLabelText('提供商')).toBeInTheDocument();
    expect(screen.getByLabelText('模型名称')).toBeInTheDocument();
    expect(screen.getByLabelText('温度')).toBeInTheDocument();
  });

  it('应该在提供商切换时自动更新默认值', () => {
    const onChange = jest.fn();
    render(<ModelConfigForm schema={LLM_SCENE_SCHEMA} initialValues={{}} onChange={onChange} />);
    
    fireEvent.change(screen.getByLabelText('提供商'), { target: { value: 'openai' } });
    
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({
        provider: 'openai',
        model_name: 'gpt-4o',
        temperature: 0.7,
      })
    );
  });
});
```

**Schema 验证测试**：

```typescript
describe('ConfigSchema Validation', () => {
  it('应该正确校验温度范围', () => {
    const result = validateField('temperature', 1.5, LLM_SCENE_SCHEMA.validation.temperature);
    expect(result.valid).toBe(false);
    expect(result.message).toContain('温度范围 0~1');
  });

  it('应该正确校验必填字段', () => {
    const result = validateField('model_name', '', LLM_SCENE_SCHEMA.validation.model_name);
    expect(result.valid).toBe(false);
    expect(result.message).toContain('请输入模型名称');
  });
});
```

### 12.2 集成测试

**页面集成测试**：

```typescript
describe('LLMModelsPage Integration', () => {
  it('应该正确加载并渲染所有场景', async () => {
    render(<LLMModelsPage />);
    
    // 等待 API 响应
    await waitFor(() => {
      expect(screen.getByText('评估报告生成')).toBeInTheDocument();
      expect(screen.getByText('儿童发展评估')).toBeInTheDocument();
      // ... 其他 7 个场景
    });
  });

  it('应该能够保存单个场景配置', async () => {
    render(<LLMModelsPage />);
    
    await waitFor(() => {
      expect(screen.getByText('评估报告生成')).toBeInTheDocument();
    });
    
    // 修改模型名称
    const modelInput = screen.getByLabelText('模型名称');
    fireEvent.change(modelInput, { target: { value: 'qwen3.5-turbo' } });
    
    // 点击保存
    const saveButton = screen.getByText('保存');
    fireEvent.click(saveButton);
    
    // 验证 API 调用
    await waitFor(() => {
      expect(configApi.updateLLMScene).toHaveBeenCalledWith(
        'report_generation',
        expect.objectContaining({ model_name: 'qwen3.5-turbo' })
      );
    });
  });
});
```

### 12.3 E2E 测试

**用户流程测试**：

```typescript
describe('Config Page E2E', () => {
  it('完整配置流程', async () => {
    // 1. 访问系统配置页面
    await page.goto('/system-config');
    
    // 2. 点击 LLM 模型
    await page.click('text=LLM 模型');
    
    // 3. 修改第一个场景的配置
    await page.fill('input[placeholder="手动输入模型名称"]', 'qwen3.5-turbo');
    await page.click('text=保存');
    
    // 4. 验证保存成功提示
    await expect(page.locator('text=配置保存成功')).toBeVisible();
    
    // 5. 刷新页面，验证配置持久化
    await page.reload();
    await expect(page.locator('input[value="qwen3.5-turbo"]')).toBeVisible();
  });
});
```

---

## 十三、优势与权衡

### ✅ 优势

1. **极致灵活**：每个场景完全独立配置，可针对不同业务场景优化参数
2. **向后兼容**：现有代码无需大幅改造，新增配置项有默认值
3. **扩展性强**：未来新增场景只需添加对应 Schema，无需修改组件代码
4. **用户友好**：提供批量操作和智能提示，降低配置复杂度
5. **代码复用**：ModelConfigForm 被 3 个页面复用，减少 70% 重复代码
6. **配置驱动**：新增配置只需定义 Schema，无需写 UI 代码
7. **性能优化**：虚拟滚动、懒加载、防抖等优化手段保证流畅体验

### ⚠️ 注意点

1. **配置项数量**：从原来的约 20 个增加到约 70 个，需优化前端页面加载和渲染性能
2. **默认值处理**：需做好参数默认值处理，避免用户未配置导致运行错误
3. **多提供商切换**：需做好 API 可用性校验提示
4. **Schema 维护**：需保持 Schema 与后端接口的一致性
5. **状态同步**：多组件状态同步需仔细处理，避免数据不一致

---

## 十四、实施计划

### Phase 1：基础组件提取（2-3 天）
- [ ] 提取 `ModelConfigForm` 组件
- [ ] 提取 `GlobalProviderConfig` 组件
- [ ] 提取 `BatchOperationsBar` 组件
- [ ] 提取 `ConfigFieldRenderer` 组件
- [ ] 提取 `CategoryTree` 组件
- [ ] 提取 `VersionManager` 组件

### Phase 2：Schema 定义（1 天）
- [ ] 定义 LLM 9 个场景 Schema
- [ ] 定义 Embedding Schema
- [ ] 定义 ML Scoring Schema
- [ ] 定义分类配置常量

### Phase 3：页面重构（3-4 天）
- [ ] 重构 `SystemConfigPage`
- [ ] 优化 `DynamicConfigForm`
- [ ] 重构 `LLMModelsPage`
- [ ] 重构 `EmbeddingModelsPage`
- [ ] 重构 `MLScoringModelsPage`

### Phase 4：API 层扩展（1-2 天）
- [ ] 添加 Embedding API 端点
- [ ] 添加 ML Scoring API 端点
- [ ] 添加批量操作 API 端点
- [ ] 添加版本对比 API 端点

### Phase 5：高级功能（2-3 天）
- [ ] 启用 `ConfigDiffView`
- [ ] 实现批量操作
- [ ] 实现配置导入/导出
- [ ] 实现智能联动

### Phase 6：测试与优化（2-3 天）
- [ ] 编写单元测试
- [ ] 编写集成测试
- [ ] 性能优化
- [ ] 用户文档

**总计**：11-16 天

---

## 十五、后续优化方向

1. **配置模板**：提供预设配置模板（开发/测试/生产），一键应用
2. **配置校验规则**：支持自定义校验规则（如模型名称格式校验）
3. **配置审计日志**：记录每次配置变更的操作人和时间
4. **配置灰度发布**：支持配置灰度发布，逐步放量
5. **配置监控告警**：监控配置变更对系统性能的影响，异常时告警
