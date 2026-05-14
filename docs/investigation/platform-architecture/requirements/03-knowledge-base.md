# 03 — 知识库管理

> **定位**：管理多个独立知识库的完整生命周期——创建、文档上传、分块、向量化、索引维护。知识库是管道的数据源，但管理逻辑完全独立于管道。
> **与核心目标的关系**：实现 [核心目标 §二](./core-objectives.md#二多知识库管理创建多个独立知识库通过搜索链接)。

---

## 配置层级

| 层级 | 谁配置 | 存储位置 | 示例 |
|------|--------|---------|------|
| **L2: 知识库配置** | 租户 editor | MySQL `knowledge_bases` 表 + 向量存储 metadata | 分块策略、Embedding 模型、向量后端、文档 ACL |
| **L1: 租户覆盖** | 租户 admin | MySQL 全局配置表 | 租户默认分块参数、可用 Embedding 模型列表 |
| **L0: 平台默认** | 超管 / 系统内置 | 代码常量 + `.env` | 默认 chunk_size=512、默认 overlap=10%、默认后端=Chroma |

**覆盖规则**：L2 > L1 > L0。每个知识库独立配置分块/Embedding/后端——知识库之间互不影响。L1 控制租户可用的后端类型和模型列表。

---

## 1. 功能清单

### 1.1 知识库 CRUD

| 功能 | 描述 |
|------|------|
| 创建知识库 | 命名 + 描述 + 向量存储后端 + 分块策略 + Embedding 配置 + 权限设置（`visibility` + `visible_roles`） |
| 查看列表 | 按租户过滤，支持按名称搜索、按后端/状态筛选 |
| 查看详情 | 文档数、分块数、向量数、索引状态、存储大小 |
| 更新配置 | 修改名称/描述/权限（不触发重建） |
| 删除 | 确认后删除知识库及其所有文档、分块、向量索引。删除前检查：是否有管道引用此知识库？如有，警告并阻止 |
| **修改分块策略** | 修改后自动触发全量索引重建 |
| **修改 Embedding 配置** | 修改后自动触发全量索引重建（向量维度变了必须重建） |
| **修改向量后端** | 迁移到不同后端 → 触发全量重新向量化+索引（不删除旧数据，迁移完成后再清理） |

### 1.2 文档上传与解析

| 功能 | 描述 |
|------|------|
| 支持格式 | PDF、TXT、Markdown、HTML、EPUB |
| 上传方式 | 拖拽批量上传（最多 50 个文件/次）、API 上传 |
| 文本提取 | 自动提取文本内容、保留标题层级结构 |
| OCR 支持 | 图片 PDF 自动 OCR 识别（可选，默认关闭以减少资源消耗） |
| 进度追踪 | 上传进度、解析进度实时展示 |
| 重复处理 | 检测已存在的文档（MD5），返回已存在文档引用，不创建重复 |
| 文档元数据 | 文件名、大小、页数、上传时间、上传者、解析状态 |

**解析失败重试策略**：

| 场景 | 自动重试 | 手动重试 |
|------|---------|---------|
| **格式不支持**（文件扩展名与内容不匹配） | 不重试。状态 → `error`，错误信息：`"不支持的文件格式"` | 不可重试，需重新上传正确格式文件 |
| **文件损坏**（PDF 无法打开、EPUB 结构异常） | 不重试。状态 → `error`，错误信息：`"文件损坏，无法解析"` | 不可重试，需重新上传完好文件 |
| **文本提取失败**（解析器异常、内存不足） | 自动重试 1 次（间隔 5 秒）。仍失败 → 状态 → `error` | 可手动触发"重新解析"（调用 `POST /documents/{doc_id}/reparse`） |
| **OCR 失败**（图片 PDF 的 OCR 引擎异常） | 自动重试 1 次。仍失败 → 状态 → `error`，错误信息：`"OCR 识别失败"` | 可手动触发重新解析 |
| **解析超时**（单文档解析超过 5 分钟） | 自动终止并重试 1 次。仍超时 → 状态 → `error` | 可手动触发重新解析 |

**不可妥协**：
- 解析状态机：`pending → parsing → parsed` 或 `pending → parsing → error`
- `error` 状态的文档不参与分块和向量化
- 手动重试次数不限，但每次重试覆盖前一次的解析结果
- 批量上传中部分文档失败不影响其他文档的解析

### 1.3 分块策略

每个知识库独立配置，创建后修改触发全量重建。

| 分块方式 | 适用场景 | 参数 |
|---------|---------|------|
| **固定大小** | 通用文档 | `chunk_size` (128-4096 字符)、`overlap` (0-50%)、`separator` (paragraph/sentence/custom) |
| **语义分块** | 技术文档、论文 | `similarity_threshold` (0.5-0.95)、`min_chunk_size`、`max_chunk_size`、`embedding_model` |
| **按段落** | 法律文书、合同 | `paragraph_separator_regex`、`max_chunk_size`（合并短段落）、`min_sentences_per_chunk` |
| **按标题层级** | 手册、指南 | `heading_levels` (H1/H2/H3)、`preserve_heading_path` (是否保留标题路径如"§3.2.1") |
| **递归分块** | 混合格式 | `separator_priority_list` (如 `\n\n` → `\n` → `。` → `. ` → ` `) |

**通用参数**（所有分块方式都有的配置项）：
- `min_chunk_size`：最小块大小（字符数），低于此大小的块合并到相邻块
- `max_chunk_size`：最大块大小（字符数），超过此大小的块强制切分
- `chunk_metadata`：是否在分块中保留源文档元数据（文件名、页码、章节）

**分块预览**：上传文档后，用户可选择 1 个文档 → 预览当前分块策略将文档切成多少块、每块的内容片段。

### 1.4 Embedding 向量化

每个知识库独立配置，创建后修改触发全量重建。

| 配置项 | 可选值 | 默认值 |
|--------|--------|--------|
| Embedding 模型 | DashScope text-embedding-v3 / OpenAI text-embedding-3-large / 自定义模型 | DashScope |
| 向量维度 | 模型默认 / 256 / 512 / 768 / 1024 | 模型默认 |
| 批量大小 | 16 / 32 / 64 / 128 | 32 |
| 相似度度量 | cosine / euclidean / dot_product | cosine |
| 多语言模式 | auto / 指定语言 / 不启用 | auto |

**向量化进度追踪**：实时显示 `已完成分块数 / 总分块数`、预计剩余时间、失败分块列表（可重试）。

### 1.5 向量存储后端

每个知识库独立选择，创建后支持迁移。

| 后端 | 适用场景 | 限制 |
|------|---------|------|
| **Chroma**（默认） | < 10 万文档、单机部署 | 需独立维护 BM25 索引；生产环境建议至少 4GB 内存 |
| **Elasticsearch** | 中等规模、需要强全文搜索 | 版本 ≥ 8.0；选 ES 的知识库不需独立 BM25 索引 |
| **Milvus** | > 100 万文档、高 QPS | Milvus ≥ 2.3；BM25 仍需独立索引 |

**后端选择对管道的影响**：
- `bm25_search` 节点检测到 ES 后端 → 直接用 ES 内置 BM25 查询
- `bm25_search` 节点检测到 Chroma/Milvus 后端 → 走独立的 BM25 关键词索引
- `vector_search` 节点根据知识库的 `similarity_metric` 配置使用对应的距离计算

**迁移流程**：
1. 用户选择新后端 → 系统显示预计迁移时间（基于文档量）
2. 确认后开始迁移（后台异步任务）
3. 迁移期间知识库可读不可写
4. 迁移完成后自动切换到新后端，清理旧数据
5. 迁移失败时回滚到旧后端，知识库恢复正常可读可写

### 1.6 文档管理

| 功能 | 描述 |
|------|------|
| 文档列表 | 按名称、上传时间、类型、上传者筛选，分页 |
| 文档详情 | 元数据 + 分块预览（前 10 块）+ 向量状态 |
| 删除文档 | 确认后删除文档、所有分块和向量 |
| 重新解析 | 强制重新提取文本 + 重新分块（修改分块策略后批量触发） |
| 文档权限 | 设置 `access_level`（inherit/restricted）+ `doc_acl`，详见 [04-permission](./04-permission-and-multi-tenancy.md) |

### 1.7 索引重建

触发条件（任一满足自动触发全量重建）：
- 分块策略变更
- Embedding 配置变更
- 向量后端迁移

**重建流程**：
1. 知识库状态 → `rebuilding`
2. 按分块策略重新分块所有文档
3. 按 Embedding 配置重新向量化
4. 写入新向量存储后端
5. 重建完成后知识库状态 → `ready`
6. 重建失败 → 知识库状态 → `error`，保留旧索引继续服务

**约束**：
- 重建期间知识库可读（使用旧索引），不可修改文档
- 重建后台异步执行，前端 SSE 推送进度
- 重建完成后自动清理旧索引（不含向量后端迁移场景的旧数据）

---

## 2. 数据模型

### 2.1 数据库表

| 表名 | 关键字段 |
|------|---------|
| `knowledge_bases` | id, tenant_id, name, description, vector_backend (chroma/es/milvus), chunk_strategy (JSON), embedding_config (JSON), visibility (public/role_scoped/private), visible_roles (JSON), owner_id, status (ready/rebuilding/indexing/error), document_count, chunk_count, storage_size_bytes, created_at, updated_at |
| `kb_documents` | id, kb_id, filename, file_type, file_size, page_count, md5_hash, parse_status (pending/parsing/parsed/error), text_content, metadata (JSON), access_level (inherit/restricted), doc_acl (JSON), owner_id, chunk_count, uploaded_at |
| `kb_chunks` | id, kb_id, doc_id, chunk_index, content, token_count, metadata (JSON), vector_id |
| `kb_rebuild_tasks` | id, kb_id, trigger (chunk_change/embedding_change/backend_migration), status (running/completed/failed), progress_pct, started_at, completed_at, error_message |

### 2.2 向量存储映射

各后端的知识库映射：

| 后端 | 知识库 → 存储单元 | 分块 → 存储单元 | 命名约定 |
|------|------------------|----------------|---------|
| Chroma | 1 KB = 1 Collection | 1 Chunk = 1 Embedding | `{tenant_id}_{kb_id}` |
| Elasticsearch | 1 KB = 1 Index | 1 Chunk = 1 Document | `rag_{tenant_id}_{kb_id}`（全小写，符合 ES index 命名规范） |
| Milvus | 1 KB = 1 Collection | 1 Chunk = 1 Entity | `rag_{tenant_id}_{kb_id}`（全小写，符合 Milvus collection 命名规范） |

**多租户隔离**：三种后端均通过命名约定实现租户隔离——每个租户的知识库存储在独立的 Collection/Index 中，物理上互不干扰。Repository 基类自动注入 `tenant_id` 前缀，业务代码不直接构造存储单元名称。

### 2.3 BM25 独立索引

当向量后端为 Chroma 或 Milvus 时，系统为每个知识库维护一个独立的 BM25 关键词索引：

| 属性 | 说明 |
|------|------|
| 存储位置 | `storage/bm25/{kb_id}/` |
| 索引字段 | chunk_id, content, doc_id, kb_id |
| 更新策略 | 文档增删时增量更新；索引重建时全量重建 |
| 参数 | k1 (默认 1.5), b (默认 0.75) |

---

## 3. API 端点

| 方法 | 路径 | 描述 |
|------|------|------|
| `POST` | `/api/v1/knowledge-bases` | 创建知识库 |
| `GET` | `/api/v1/knowledge-bases` | 知识库列表（按租户过滤，支持搜索/筛选） |
| `GET` | `/api/v1/knowledge-bases/{id}` | 知识库详情（含文档数/分块数/存储大小） |
| `PUT` | `/api/v1/knowledge-bases/{id}` | 更新知识库配置（名称/描述/权限） |
| `PUT` | `/api/v1/knowledge-bases/{id}/chunk-strategy` | 更新分块策略（触发重建） |
| `PUT` | `/api/v1/knowledge-bases/{id}/embedding-config` | 更新 Embedding 配置（触发重建） |
| `POST` | `/api/v1/knowledge-bases/{id}/migrate-backend` | 迁移向量后端（触发重建） |
| `DELETE` | `/api/v1/knowledge-bases/{id}` | 删除知识库（检查管道引用） |
| `POST` | `/api/v1/knowledge-bases/{id}/documents` | 上传文档（批量） |
| `GET` | `/api/v1/knowledge-bases/{id}/documents` | 文档列表 |
| `GET` | `/api/v1/knowledge-bases/{id}/documents/{doc_id}` | 文档详情 + 分块预览 |
| `DELETE` | `/api/v1/knowledge-bases/{id}/documents/{doc_id}` | 删除文档 |
| `POST` | `/api/v1/knowledge-bases/{id}/documents/{doc_id}/reparse` | 重新解析文档 |
| `PUT` | `/api/v1/knowledge-bases/{id}/documents/{doc_id}/acl` | 更新文档 ACL |
| `GET` | `/api/v1/knowledge-bases/{id}/rebuild/status` | 重建任务状态（SSE 推送进度） |
| `GET` | `/api/v1/knowledge-bases/{id}/chunk-preview` | 按当前分块策略预览某文档的分块结果 |

---

## 4. 前端页面

### 4.1 知识库列表页 `/knowledge`

卡片网格视图（非表格），每张卡片展示关键信息和快捷操作。

```
┌──────────────────────────────────────────────────────────────────┐
│  知识库                                              [+ 创建知识库] │
├──────────────────────────────────────────────────────────────────┤
│  [搜索...]  [后端 ▾]  [状态 ▾]                                     │
│                                                                  │
│  ┌──────────────────────┐ ┌──────────────────────┐               │
│  │ 心血管指南库          │ │ 内分泌指南库          │               │
│  │ Milvus · 12,500 文档  │ │ ES · 8,200 文档       │               │
│  │ 🔒 公开 · 156 万块    │ │ 🔒 角色可见 · 89 万块   │               │
│  │ ✅ 就绪 · 2.3 GB     │ │ 🔄 重建中 · 1.1 GB    │               │
│  │ [打开]               │ │ [打开]               │               │
│  └──────────────────────┘ └──────────────────────┘               │
│                                                                  │
│  ┌──────────────────────┐                                        │
│  │ 药学知识库            │                                        │
│  │ Chroma · 3,100 文档   │                                        │
│  │ 🔒 私有 · 12 万块     │                                        │
│  │ ✅ 就绪 · 0.4 GB     │                                        │
│  │ [打开]               │                                        │
│  └──────────────────────┘                                        │
└──────────────────────────────────────────────────────────────────┘
```

### 4.2 知识库详情页 `/knowledge/:id`

4 选项卡布局。所有操作在页内完成，不弹模态框。

```
┌─ ← 知识库  │  心血管指南库  │  Milvus · 12,500 文档 · ✅ 就绪  ────────┐
│                                                                        │
│  [文档] [分块&向量] [权限] [设置]                                         │
│                                                                        │
│  ──────────────────────────────────────────────────────────────────    │
│                                                                        │
│  【文档 选项卡】                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  ▐▐▐  拖拽 PDF / TXT / Markdown / HTML / EPUB 到此处上传          │  │
│  │      或 [选择文件]                                                 │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                        │
│  上传进度: ████████████░░░░ 高血压指南2024.pdf (完成)                      │
│                                                                        │
│  [搜索文档...]  [类型 ▾]  [批量删除]                                       │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ ☐│ 文件名              │ 类型 │ 大小  │ 分块 │ 上传时间 │ 操作      │  │
│  │  │ 高血压指南2024.pdf   │ PDF  │ 2.3M │ 156  │ 05-12   │ 查看 删除 │  │
│  │  │ 药物相互作用表.pdf   │ PDF  │ 1.1M │ 89   │ 05-10   │ 查看 删除 │  │
│  │  │ ...                                                          │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                        │
│  【分块&向量 选项卡】                                                      │
│  分块策略: [固定大小 ▾]  chunk_size: [512]  overlap: [10%]               │
│            [预览分块结果] — 选一个文档看被切成什么样                         │
│  Embedding: [DashScope v3 ▾]  维度: [1024]  度量: [cosine ▾]             │
│  向量后端: [Chroma ▾]  当前后端，[迁移到 ES...] [迁移到 Milvus...]          │
│  重建历史: 最近 5 次重建记录（触发原因、状态、耗时）                            │
│                                                                        │
│  【权限 选项卡】                                                          │
│  可见性: [公开 ▾]                                                        │
│  角色可见: (当 visibility=role_scoped 时显示)  [药师] [管理员] [+ 添加]     │
│  文档 ACL 总览:                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ 文档              │ access_level │ doc_acl           │ 操作      │  │
│  │ 高血压指南2024.pdf │ inherit      │ 继承自知识库        │ —         │  │
│  │ 内部审核稿.pdf     │ restricted   │ [药师] [管理员]     │ 编辑      │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                        │
│  【设置 选项卡】                                                          │
│  名称: [心血管指南库          ]                                           │
│  描述: [覆盖高血压、冠心病等心血管内科常见疾病的诊疗指南...]                    │
│                                                                        │
│  ⚠️ 危险区域                                                            │
│  删除知识库: [⚠️ 删除此知识库]  — 检查管道引用，有引用时阻止并列出管道名          │
└────────────────────────────────────────────────────────────────────────┘
```

**设计要点**：
- 文档上传拖拽到页面上传区域，进度在区域下方实时显示，不弹窗
- 分块预览按钮 → 选择文档 → 侧边滑出预览面板，展示被切成多少块、每块内容片段
- 权限选项卡直接看到文档 ACL 总览，可逐个文档修改 access_level
- 删除知识库前自动检查管道引用，有引用时弹窗列出管道名并阻止

### 4.3 测试数据页 `/knowledge/test-data`

3 选项卡合一：用例 | 测试集 | 草稿。详见 [06-rag-evaluation](./06-rag-evaluation.md#12-前端页面)。

---

## 5. 验收标准

- [ ] AC-3.1：创建知识库时三种后端均可选，创建后对应 Collection/Index 成功生成
- [ ] AC-3.2：上传 PDF/TXT/Markdown/HTML/EPUB 文档均正确解析为文本
- [ ] AC-3.3：批量拖拽上传 50 个文件全部成功，进度实时更新
- [ ] AC-3.4：上传已存在的文档（MD5 相同）→ 返回已存在引用，不创建重复
- [ ] AC-3.5：修改分块策略后自动触发全量索引重建，重建完成后新分块策略生效
- [ ] AC-3.6：修改 Embedding 配置后自动触发全量索引重建
- [ ] AC-3.7：向量后端迁移（Chroma → ES）→ 迁移完成后可正常检索
- [ ] AC-3.8：迁移失败 → 回滚到旧后端，知识库状态恢复 ready
- [ ] AC-3.9：重建期间知识库可正常读取（用旧索引），不可修改文档
- [ ] AC-3.10：ES 后端的知识库，BM25 检索节点自动使用 ES 内置 BM25
- [ ] AC-3.11：Chroma/Milvus 后端的知识库，BM25 检索使用独立索引
- [ ] AC-3.12：删除被管道引用的知识库 → 警告并阻止，列出引用管道名称
- [ ] AC-3.13：分块预览正确展示某文档在当前策略下的分块结果
- [ ] AC-3.14：文档权限设置为 restricted 时，doc_acl 不能超出知识库 visible_roles 范围
- [ ] AC-3.15：重建进度 SSE 实时推送，前端显示百分比和预计剩余时间

---

## 6. 与其他模块的接口

| 被依赖 | 接口 |
|--------|------|
| [01-pipeline-model](./01-pipeline-model-and-engine.md) | 管道通过 `knowledge_base_id` 引用知识库；检索节点根据后端类型选择检索路径 |
| [02-pipeline-editor](./02-pipeline-editor.md) | 域配置中知识库下拉列表来自本模块 API；受权限过滤 |
| [04-permission](./04-permission-and-multi-tenancy.md) | 知识库 `visibility` + `visible_roles`；文档 `access_level` + `doc_acl`；搜索时注入文档级过滤 |
| [06-rag-evaluation](./06-rag-evaluation.md) | 知识库快照（评估运行前冻结知识库状态） |
