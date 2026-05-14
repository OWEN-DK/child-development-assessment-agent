# Phase 6：知识库前端——实施文档

> **依赖**：Phase 2（知识库管理后端）完成后启动。后端 API 已就绪，前端构建知识库全生命周期管理界面。
> **产出**：知识库列表页、知识库详情页（4 选项卡）、测试数据页（3 选项卡）。
> **参考规范**：[03-knowledge-base.md](../../requirements/03-knowledge-base.md)、[06-rag-evaluation.md](../../requirements/06-rag-evaluation.md)
> **最后更新**：2026-05-14

---

## 1. 阶段目标

构建知识库管理的完整前端交互链路，覆盖从创建、配置、文档上传、分块预览、权限管理到知识库删除的全生命周期，同时将现有 RAG 评估的测试数据组件迁移到统一路由下：

- **知识库列表页**：卡片网格视图展示当前租户所有知识库，支持按名称搜索、向量后端筛选、状态筛选、权限标识展示
- **知识库详情页**：4 选项卡布局（文档 / 分块&向量 / 权限 / 设置），所有操作在页内完成
  - **文档 Tab**：拖拽上传区域 + 上传进度条 + MD5 去重检测 + 文档列表（搜索/筛选/分页/批量删除）
  - **分块&向量 Tab**：分块策略配置 + Embedding 配置 + 向量后端迁移 UI + 分块预览侧滑面板
  - **权限 Tab**：可见性设置 + 角色可见列表 + 文档 ACL 总览（可逐文档修改 access_level）
  - **设置 Tab**：名称/描述编辑 + 危险区域删除（管道引用检查）
- **测试数据页**：3 选项卡——测试用例 / 测试集 / 草稿，复用现有 rag-eval 组件并适配新路由 `/knowledge/test-data`

---

## 2. 任务清单

### 2.1 状态管理（6.1 状态管理）

#### `features/knowledge/stores/knowledgeBaseStore.ts`

- [ ] **基础状态定义**：`KnowledgeBaseStore` 接口
  - `knowledgeBases: KnowledgeBaseListItem[]`——当前租户的知识库列表
  - `loading: boolean`——列表加载状态
  - `error: string | null`——列表加载错误
- [ ] **列表筛选状态**
  - `searchQuery: string`——按名称模糊搜索
  - `backendFilter: 'all' | 'chroma' | 'elasticsearch' | 'milvus'`——向量后端筛选
  - `statusFilter: 'all' | 'ready' | 'rebuilding' | 'indexing' | 'error'`——状态筛选
  - `visibilityFilter: 'all' | 'public' | 'role_scoped' | 'private'`——可见性筛选
- [ ] **详情页状态**
  - `currentKB: KnowledgeBaseDetail | null`——当前查看的知识库详情
  - `activeTab: 'documents' | 'chunks' | 'permissions' | 'settings'`——当前激活的选项卡
  - `documents: KBDocument[]`——当前知识库的文档列表
  - `documentsLoading: boolean`
  - `documentsTotal: number`
  - `documentsPage: number`、`documentsPageSize: number`
  - `uploadProgress: UploadProgressItem[]`——正在上传的文件进度列表（每项含 filename、percentage、status: 'pending' | 'uploading' | 'parsing' | 'done' | 'error'、errorMessage）
  - `selectedDocumentId: string | null`——分块预览时选中的文档 ID
  - `chunkPreview: ChunkPreview[]`——当前选中文档的分块预览结果
  - `chunkPreviewLoading: boolean`
- [ ] **权限 Tab 状态**
  - `visibility: 'public' | 'role_scoped' | 'private'`
  - `visibleRoles: string[]`——角色可见列表（visibility=role_scoped 时生效）
  - `docAcls: DocAclEntry[]`——文档 ACL 总览列表
- [ ] **配置状态**
  - `chunkStrategy: ChunkStrategyConfig`——当前分块策略
  - `embeddingConfig: EmbeddingConfig`——当前 Embedding 配置
  - `vectorBackend: 'chroma' | 'elasticsearch' | 'milvus'`
  - `configDirty: boolean`——配置是否有未保存的变更
  - `rebuildStatus: RebuildStatus | null`——重建任务状态（含 progress_pct、estimated_remaining_seconds）
- [ ] **操作方法**
  - `loadKnowledgeBases()`——从后端加载知识库列表，带筛选参数
  - `loadKnowledgeBase(id)`——加载知识库详情，包含文档列表
  - `createKnowledgeBase(data)`——创建知识库（弹窗表单提交）
  - `deleteKnowledgeBase(id)`——删除知识库（含管道引用检查）
  - `updateKnowledgeBaseInfo(id, data)`——更新名称/描述
  - `updateVisibility(id, visibility)`——更新可见性
  - `updateVisibleRoles(id, roles)`——更新角色可见列表
  - `uploadDocuments(kbId, files)`——上传文档（批量，带进度回调）
  - `deleteDocument(kbId, docId)`——删除文档
  - `batchDeleteDocuments(kbId, docIds)`——批量删除文档
  - `reparseDocument(kbId, docId)`——重新解析文档
  - `previewChunks(kbId, docId)`——预览某文档的分块结果
  - `updateChunkStrategy(kbId, strategy)`——更新分块策略（自动触发重建）
  - `updateEmbeddingConfig(kbId, config)`——更新 Embedding 配置（自动触发重建）
  - `migrateBackend(kbId, target)`——迁移向量后端
  - `subscribeRebuildProgress(kbId)`——SSE 订阅重建进度
  - `updateDocAcl(kbId, docId, acl)`——更新文档 ACL

### 2.2 API 客户端（6.2 API 客户端）

#### `api/knowledge/knowledge-base.ts`

现有 `api/knowledge/` 为搜索 API。需新增知识库管理 API 客户端。

- [ ] **知识库 CRUD**
  - `getKnowledgeBases(params: KBListParams) → KnowledgeBaseListItem[]`——GET `/api/v1/knowledge-bases`，参数含 `search`、`backend`、`status`、`visibility`、`page`、`page_size`
  - `getKnowledgeBase(id: string) → KnowledgeBaseDetail`——GET `/api/v1/knowledge-bases/:id`
  - `createKnowledgeBase(data: KBCreateRequest) → KnowledgeBaseDetail`——POST `/api/v1/knowledge-bases`
  - `updateKnowledgeBase(id: string, data: KBUpdateRequest) → KnowledgeBaseDetail`——PUT `/api/v1/knowledge-bases/:id`
  - `deleteKnowledgeBase(id: string) → DeleteCheckResult`——DELETE `/api/v1/knowledge-bases/:id`（返回管道引用检查结果，有引用时抛特定错误码）
- [ ] **文档管理**
  - `uploadDocuments(kbId: string, files: File[], onProgress?: (pct: number) => void) → DocumentUploadResult[]`——POST `/api/v1/knowledge-bases/:id/documents`，multipart/form-data，上传进度回调
  - `getDocuments(kbId: string, params: DocListParams) → PaginatedResponse<KBDocument>`——GET `/api/v1/knowledge-bases/:id/documents`，参数含 `search`、`file_type`、`page`、`page_size`
  - `getDocument(kbId: string, docId: string) → KBDocumentDetail`——GET `/api/v1/knowledge-bases/:id/documents/:doc_id`
  - `deleteDocument(kbId: string, docId: string) → void`——DELETE `/api/v1/knowledge-bases/:id/documents/:doc_id`
  - `batchDeleteDocuments(kbId: string, docIds: string[]) → void`——POST `/api/v1/knowledge-bases/:id/documents/batch-delete`
  - `reparseDocument(kbId: string, docId: string) → KBDocument`——POST `/api/v1/knowledge-bases/:id/documents/:doc_id/reparse`
  - `updateDocumentAcl(kbId: string, docId: string, acl: DocAclUpdate) → KBDocument`——PUT `/api/v1/knowledge-bases/:id/documents/:doc_id/acl`
- [ ] **配置与重建**
  - `updateChunkStrategy(kbId: string, strategy: ChunkStrategyConfig) → KnowledgeBaseDetail`——PUT `/api/v1/knowledge-bases/:id/chunk-strategy`
  - `updateEmbeddingConfig(kbId: string, config: EmbeddingConfig) → KnowledgeBaseDetail`——PUT `/api/v1/knowledge-bases/:id/embedding-config`
  - `migrateBackend(kbId: string, target: 'elasticsearch' | 'milvus') → MigrationStatus`——POST `/api/v1/knowledge-bases/:id/migrate-backend`
  - `getRebuildStatus(kbId: string) → RebuildStatus`——GET `/api/v1/knowledge-bases/:id/rebuild/status`
  - `previewChunks(kbId: string, docId: string) → ChunkPreview[]`——GET `/api/v1/knowledge-bases/:id/chunk-preview?doc_id=xxx`
- [ ] **SSE 订阅**
  - `subscribeRebuildProgress(kbId: string, onEvent: (event: RebuildProgressEvent) => void) → () => void`——订阅 `/api/v1/knowledge-bases/:id/rebuild/status/stream`（SSE），返回取消订阅函数
  - `subscribeUploadProgress(kbId: string, onEvent: (event: UploadProgressEvent) => void) → () => void`——订阅文档上传/解析进度 SSE
- [ ] **类型定义**（放在 `api/knowledge/knowledge-base.ts` 或独立 `entities/knowledge/types.ts`）
  - `KnowledgeBaseListItem`：`{ id, name, description, vector_backend, visibility, status, document_count, chunk_count, storage_size_bytes, owner_id, created_at, updated_at }`
  - `KnowledgeBaseDetail`：`{ ...KnowledgeBaseListItem, chunk_strategy: ChunkStrategyConfig, embedding_config: EmbeddingConfig, visible_roles: string[], last_rebuild_task: RebuildTask | null }`
  - `ChunkStrategyConfig`：`{ method: 'fixed_size' | 'semantic' | 'paragraph' | 'heading' | 'recursive', chunk_size?: number, overlap?: number, separator?: string, similarity_threshold?: number, min_chunk_size?: number, max_chunk_size?: number, heading_levels?: number[], preserve_heading_path?: boolean, separator_priority_list?: string[], chunk_metadata?: boolean }`
  - `EmbeddingConfig`：`{ model: string, dimensions: number, batch_size: number, similarity_metric: 'cosine' | 'euclidean' | 'dot_product', multilingual_mode: 'auto' | string | null }`
  - `KBDocument`：`{ id, kb_id, filename, file_type, file_size, page_count, md5_hash, parse_status, access_level, owner_id, chunk_count, uploaded_at }`
  - `KBDocumentDetail`：`{ ...KBDocument, text_content?: string, metadata: Record<string, unknown>, doc_acl: string[] | null, chunks_preview?: ChunkPreview[] }`
  - `ChunkPreview`：`{ chunk_index, content_preview: string, token_count, metadata: Record<string, unknown> }`
  - `RebuildTask`：`{ id, kb_id, trigger, status, progress_pct, started_at, completed_at, error_message }`
  - `MigrationStatus`：`{ task_id, kb_id, source_backend, target_backend, status, progress_pct, estimated_remaining_seconds }`
  - `UploadProgressItem`：`{ filename, percentage, status, error_message? }`
  - `DocAclEntry`：`{ doc_id, filename, access_level, doc_acl: string[] | null }`
  - `DeleteCheckResult`：`{ can_delete: boolean, referenced_by: { pipeline_id: string, pipeline_name: string }[] }`

### 2.3 知识库列表页（6.3 知识库列表页）

#### `features/knowledge/pages/KnowledgeListPage.tsx`

- [ ] **页面布局**：顶部标题"知识库" + `[+ 创建知识库]` 按钮
- [ ] **搜索/筛选栏**
  - 搜索输入框（按名称模糊搜索，带 300ms 防抖）
  - 向量后端筛选下拉：全部 / Chroma / Elasticsearch / Milvus
  - 状态筛选下拉：全部 / 就绪 / 重建中 / 索引中 / 异常
  - 可见性筛选下拉：全部 / 公开 / 角色可见 / 私有
- [ ] **卡片网格**：响应式 grid（3 列 → 2 列 → 1 列），每张卡片为 `KnowledgeBaseCard`
- [ ] **新建知识库对话框**（Modal）
  - 名称输入（必填，max 64 字符）
  - 描述输入（多行文本，max 512 字符）
  - 向量后端选择（Radio.Button：Chroma / Elasticsearch / Milvus，默认 Chroma）
  - 可见性选择（Radio.Button：公开 / 角色可见 / 私有，默认公开）
  - 角色可见选择（当 visibility=role_scoped 时显示，Tag + Select 多选角色）
  - 分块策略快速选择（Select：固定大小 / 语义 / 按段落 / 按标题 / 递归，默认固定大小）
  - Embedding 模型快速选择（Select，从 `/api/v1/config/embedding-models` 加载）
  - 提交后 navigate 到 `/knowledge/:id`
- [ ] **空状态**：无知识库时显示引导文案 "暂无知᷈识库，点击创建第一个" + 新建按钮
- [ ] **加载态**：卡片区域骨架屏（Ant Design Skeleton card，显示 6 张占位卡）
- [ ] **错误态**：加载失败显示 `<Alert type="error" message="加载失败" action={<Button>重试</Button>} />`
- [ ] **路由**：`/knowledge`，点击卡片或"打开"按钮 navigate 到 `/knowledge/:id`

#### `features/knowledge/components/KnowledgeBaseCard.tsx`

- [ ] **卡片内容**
  - 知识库名称（粗体，可截断，hover 完整显示 Tooltip）
  - 向量后端标签（如 `Milvus`，使用不同颜色 Tag：Chroma=青色、ES=金色、Milvus=蓝色）
  - 文档数 × 分块数（如 `12,500 文档 · 156 万块`）
  - 权限标识（`🔒 公开` / `🔒 角色可见` / `🔒 私有`，带对应图标）
  - 状态标签（`✅ 就绪` / `🔄 重建中` / `⚠️ 异常`，不同颜色）
  - 存储大小（如 `2.3 GB`）
  - 底部操作按钮：`[打开]` 主按钮
- [ ] **交互**
  - hover 显示卡片阴影加深
  - 点击卡片标题或"[打开]"按钮 navigate 到 `/knowledge/:id`
  - 更多操作下拉菜单：`[重命名] [更改可见性] [删除]`
  - 删除前检查：先调 API 检查管道引用，有引用时弹窗列出引用管道名并阻止删除

### 2.4 知识库详情页（6.4 知识库详情页）

#### `features/knowledge/pages/KnowledgeDetailPage.tsx`

- [ ] **页面布局**
  - 顶部面包屑：`← 知识库` + 知识库名称 + 向量后端标记 + 文档数 + 状态标签
  - 4 选项卡 Tabs：`[文档] [分块&向量] [权限] [设置]`
- [ ] **URL 路由匹配**
  - `/knowledge/:id` → 默认激活 `documents` tab
  - `/knowledge/:id/documents` → `activeTab='documents'`
  - `/knowledge/:id/chunks` → `activeTab='chunks'`
  - `/knowledge/:id/permissions` → `activeTab='permissions'`
  - `/knowledge/:id/settings` → `activeTab='settings'`
- [ ] **数据加载**
  - `useEffect` 中调用 `loadKnowledgeBase(id)` 初始化详情
  - 加载失败显示错误提示 + 返回列表按钮
  - 切换选项卡时按需加载对应数据（文档列表、分块配置、ACL 列表等）

#### `features/knowledge/components/DocumentsTab.tsx`

- [ ] **拖拽上传区域**
  - 使用 Ant Design `Upload.Dragger` 组件，或手动实现拖拽区域
  - 支持格式提示："拖拽 PDF / TXT / Markdown / HTML / EPUB 到此处上传，或 [选择文件]"
  - 拖拽悬停时区域高亮蓝色边框
  - 点击 [选择文件] 触发原生文件选择器
  - `multiple` 属性允许一次选择多个文件（最多 50 个）
  - `accept` 属性限制文件类型：`.pdf,.txt,.md,.html,.htm,.epub`
- [ ] **上传进度**
  - 上传区域下方渲染进度列表
  - 每项显示：文件名 + 进度条 (`<Progress percent={pct} />`) + 状态文本（上传中... / 解析中... / √ 完成 / ✕ 失败）
  - 失败项显示错误信息（如 "文件损坏，无法解析"）+ [重试] 按钮
  - 全部完成后自动刷新文档列表
- [ ] **MD5 去重检测**
  - 上传完成后如果后端返回重复标记，进度项显示 "已存在，无需重复上传"（黄色信息提示）+ 自动关联已有文档
- [ ] **文档列表**
  - 搜索栏：输入框（文件名搜索）+ 文件类型下拉筛选（全部/PDF/TXT/Markdown/HTML/EPUB）+ `[批量删除]` 按钮
  - 表格列：☐ 复选框 / 文件名（可点击查看详情） / 文件类型 / 大小 / 分块数 / 解析状态（Tag：待解析/解析中/已解析/异常）/ 权限级别（继承/受限）/ 上传时间 / 操作（[重新解析] [删除]）
  - 分页：底部 Pagination，默认 20 条/页
  - 全选/批量删除：选中 ≥1 行时 `[批量删除]` 按钮可用，点击弹出确认弹窗
- [ ] **文档详情抽屉**（点击文件名打开）
  - 元数据信息：文件名、大小、页数、MD5、上传时间、上传者、解析状态
  - 分块预览：前 10 块的内容片段（截断 200 字符）
  - 操作按钮：`[重新解析]` `[删除文档]` `[查看全部分块 →]`（跳转到分块 Tab 并自动预览该文档）
- [ ] **空状态**：无文档时显示 "暂无文档，拖拽文件到上方区域上传"
- [ ] **加载态**：表格区域 Skeleton

#### `features/knowledge/components/ChunksTab.tsx`

- [ ] **分块策略配置区**
  - 分块方式 Select 下拉：固定大小 / 语义分块 / 按段落 / 按标题层级 / 递归分块
  - 根据选中方式动态渲染参数表单：
    - 固定大小：`chunk_size`（InputNumber, 128–4096）、`overlap`（Slider, 0–50%）、`separator`（Select: paragraph/sentence/custom）
    - 语义分块：`similarity_threshold`（Slider, 0.5–0.95）、`min_chunk_size`/`max_chunk_size`（InputNumber）、`embedding_model`（Select，从配置加载）
    - 按段落：`paragraph_separator_regex`（Input）、`max_chunk_size`（InputNumber）、`min_sentences_per_chunk`（InputNumber）
    - 按标题层级：`heading_levels`（Checkbox.Group: H1/H2/H3）、`preserve_heading_path`（Switch）
    - 递归分块：`separator_priority_list`（Tag + Input 可排序列表）、`chunk_size`（InputNumber）
  - 通用参数：`min_chunk_size`（InputNumber）、`max_chunk_size`（InputNumber）、`chunk_metadata`（Switch）
  - 参数旁 Tooltip 显示说明
  - 修改后显示 "分块策略已修改，保存后将触发全量索引重建" 警告提示
  - `[保存分块策略]` 按钮 → 调用 API → 触发重建 → 显示重建进度
- [ ] **Embedding 配置区**
  - Embedding 模型 Select：从 `/api/v1/config/embedding-models` 动态加载
  - 向量维度 Select（InputNumber，或根据模型自动填充）
  - 批量大小 Select：16 / 32 / 64 / 128
  - 相似度度量 Select：cosine / euclidean / dot_product
  - 多语言模式 Select：auto / 指定语言列表
  - 修改后显示 "Embedding 配置已修改，保存后将触发全量索引重建" 警告提示
  - `[保存 Embedding 配置]` 按钮 → 调用 API → 触发重建 → 显示重建进度
- [ ] **向量后端迁移 UI**
  - 当前后端展示（Tag 标签 + 知识库名称）
  - 迁移按钮：`[迁移到 Elasticsearch...]` `[迁移到 Milvus...]`（已使用的后端按钮置灰）
  - 点击迁移按钮 → 弹出确认 Modal：
    - 显示预计迁移时间（基于文档量估算："预计需要 5–10 分钟"）
    - 警告提示："迁移期间知识库可读不可写"
    - `[确认迁移]` / `[取消]`
  - 确认后调用 `migrateBackend` API → SSE 订阅进度 → 进度条实时更新
  - 迁移完成后自动刷新页面状态，显示新后端标签
  - 迁移失败 → 错误提示 + "已回滚到原后端" 信息
- [ ] **分块预览**
  - `[预览分块结果]` 按钮 → 弹出文档选择器（Select，搜索当前知识库已解析的文档）
  - 选择文档后 → 调用 `previewChunks` API → 右侧滑出 Preview Drawer
  - Drawer 内容：
    - 文档名称 + 总块数
    - 分块列表（滚动）：每块显示 `#{chunk_index}` + 字符数 + 内容预览（截断 300 字符，可展开）
    - 分块统计：平均块大小、总字符数、块大小分布 Mini 柱状图
  - Drawer 底部按钮：`[关闭]`
- [ ] **重建历史**
  - 最近 5 次重建记录（表格或 Timeline 组件）
  - 每项显示：触发原因（分块变更/Embedding变更/后端迁移）、状态（运行中/已完成/失败）、开始时间、耗时、进度百分比
  - 运行中的任务显示进度条（SSE 实时更新）
  - 失败的任务显示错误信息 Tooltip

#### `features/knowledge/components/PermissionsTab.tsx`

- [ ] **可见性设置区**
  - Radio.Button 组：公开 / 角色可见 / 私有
  - 每个选项旁显示说明文字
    - 公开：所有租户成员可见此知识库
    - 角色可见：仅指定角色的成员可见
    - 私有：仅创建者和知识库管理员可见
  - 修改后即时保存（`updateVisibility` API）
- [ ] **角色可见列表**（visibility=role_scoped 时显示）
  - 已选角色 Tag 列表（如 `[药师] [管理员] [+ 添加]`）
  - 点击 `[+ 添加]` → Select 下拉多选角色（从 `/api/v1/roles` 加载）
  - 确认后调用 `updateVisibleRoles` API
- [ ] **文档 ACL 总览**
  - 表格列：文档名称（可点击查看详情） / access_level（Select 下拉：inherit / restricted，inline 编辑） / doc_acl（当 access_level=restricted 时显示角色 Tag 列表，inline 编辑） / 操作（[编辑 ACL]）
  - inherit 行：doc_acl 列显示 "继承自知识库"（灰色文本），access_level 可改为 restricted
  - restricted 行：doc_acl 列显示角色 Tag，点击编辑 → Modal 多选角色（不超过知识库 visible_roles 范围）+ `[保存]`
  - 批量修改：选中多行 → `[批量设置 access_level]` 下拉 → inherit / restricted
  - `[保存全部变更]` 按钮（仅当有未保存的 ACL 修改时显示）
  - 搜索框：按文件名搜索文档
  - 分页

#### `features/knowledge/components/SettingsTab.tsx`

- [ ] **基本信息编辑区**
  - 名称输入框（必填，max 64 字符）
  - 描述输入框（多行，max 512 字符）
  - `[保存]` 按钮，保存成功后显示绿色提示
- [ ] **危险区域**
  - 分隔线 + 红色标题 "⚠️ 危险区域"
  - 删除知识库按钮：红色 `[⚠️ 删除此知识库]` Button（danger type）
  - 点击 → 调用 `deleteKnowledgeBase` API 做管道引用检查：
    - 无引用 → 弹出二次确认 Modal："确定删除知识库「XXX」及其全部文档、分块和向量索引？此操作不可撤销。"
    - 有引用 → 弹出警告 Modal：
      ```
      ⚠️  无法删除此知识库
      以下管道正在引用此知识库：
      · 综合问诊管道 v3
      · 心血管专科管道 v1
      请先从这些管道中移除引用后再试。
      [知道了]
      ```
    - 确认删除后调用删除 API → 成功后 navigate 回 `/knowledge`

### 2.5 测试数据页（6.5 测试数据页）

#### `features/knowledge/pages/TestDataPage.tsx`

- [ ] **页面布局**
  - 顶部标题"测试数据"
  - 3 选项卡 Tabs：`[测试用例] [测试集] [草稿]`
  - 每个选项卡内渲染对应的现有 rag-eval 页面组件，适配为内嵌模式
- [ ] **测试用例 Tab**
  - 复用 `features/rag-eval/pages/TestCasePage.tsx` 的核心逻辑
  - 改造点：
    - 移除独立页面布局（Title、面包屑），改为内嵌在 Tab 内容区
    - 搜索栏：输入框 + 来源筛选（手动/草稿导入/JSON导入）+ 难度筛选（简单/中等/困难）
    - 用例表格：☐ 复选框 / 查询（截断 + hover Tooltip）/ 期望知识库ID（Tag 列表）/ 期望关键词（Tag 列表）/ 来源 / 难度（Tag 颜色：简单=绿、中等=黄、困难=红）/ 创建时间 / 操作（[编辑] [删除]）
    - 操作按钮：`[+ 新建用例]` `[JSON 导入]` `[批量删除]`
    - JSON 导入：点击 `[JSON 导入]` → Modal 提供文本区域粘贴 JSON → 格式校验 → 预览解析结果（Table 预览即将导入的用例） → `[确认导入]`
    - 分页
- [ ] **测试集 Tab**
  - 复用 `features/rag-eval/pages/TestSetPage.tsx` 的核心逻辑
  - 改造点：
    - 移除独立页面布局
    - 测试集卡片/表格视图（使用 Card 列表或 Table）
    - 每项显示：名称 / 描述 / 用例数 / 创建时间 / 操作（[查看用例] [编辑] [删除]）
    - 点击 `[+ 新建测试集]` → Modal：名称 + 描述 + 选择用例（Transfer 或 Modal 内 Table 选用例，支持搜索/分页）
    - CaseTransferModal：用例选择器支持分页加载，超过 100 条用例时虚拟滚动或分页表格
    - 点击测试集名称 → 进入该测试集的用例列表视图
- [ ] **草稿 Tab**
  - 复用 `features/rag-eval/pages/DraftPage.tsx` 的核心逻辑
  - 改造点：
    - 移除独立页面布局
    - 搜索/筛选栏：状态筛选（全部/待审核/已导入/已忽略）+ 搜索输入框
    - 草稿表格：☐ 复选框 / 查询（截断 + hover）/ 描述 / 来源文档 / faithfulness 得分（数字 + 进度条颜色：>0.8=绿色、>0.6=黄色、<0.6=红色）/ 状态（Tag）/ 创建时间 / 操作（[审核通过 → 导入] [忽略]）
    - 操作按钮：`[生成草稿]` `[批量导入]` `[批量忽略]`
    - `[生成草稿]` 按钮点击 → Modal 或 Drawer：
      - 选择源知识库
      - 选择文档（多选，默认全选已解析文档）
      - 配置参数：max_qa_per_chunk（默认 3）、min_qa_per_chunk（默认 1）
      - `[开始生成]` → SSE 进度订阅 → 进度条显示 "生成中: X/Y 已完成"
      - 生成完成后列表自动刷新
    - 分页
- [ ] **路由**：`/knowledge/test-data`（或配置为 `/knowledge/test-data/:tab` 支持直接 URL 定位到某个 Tab）
- [ ] **URL 匹配**
  - `/knowledge/test-data/cases` → `activeTab='cases'`
  - `/knowledge/test-data/sets` → `activeTab='sets'`
  - `/knowledge/test-data/drafts` → `activeTab='drafts'`

---

## 3. 关键实现细节

### 3.1 文档上传：拖拽区域 + 进度条 + MD5 去重

- **拖拽区域实现**：
  - 使用 Ant Design `Upload.Dragger` 组件，`customRequest` 属性接管上传逻辑
  - 或手动实现：`<div>` 监听 `onDragOver`、`onDragLeave`、`onDrop` 事件，`useRef` 跟踪拖拽状态
  - `onDrop` 中获取 `e.dataTransfer.files`，限制 `files.length ≤ 50`（超限时弹出 warning）
  - 文件类型校验：`.pdf`、`.txt`、`.md`、`.html`、`.htm`、`.epub`，非法类型直接阻止并提示
  - 拖拽悬停时 `.dragover` 样式：蓝色虚线边框 + 浅蓝背景
- **上传进度跟踪**：
  - 使用 `axios` 或 `fetch` 的 `onUploadProgress` 回调跟踪上传百分比
  - 上传完成后后端异步解析，通过 SSE 推送解析进度
  - 进度列表数据结构：`Map<filename, UploadProgressItem>`，使用 `useState` + `useCallback` 管理
  - 进度条组件：`<Progress percent={item.percentage} status={item.status === 'error' ? 'exception' : 'active'} />`
- **MD5 去重**：
  - 后端在文档上传时计算文件 MD5，与 `kb_documents.md5_hash` 比对
  - 命中已存在文档时返回 `{ duplicate: true, existing_document: KBDocument }`
  - 前端进度项显示 "已存在"（黄色 `Tag`）+ 不重复创建
  - 批量上传中部分重复不影响其他文件
- **解析失败重试**：
  - 可重试的错误：文本提取失败、OCR 失败、解析超时 → 显示 `[重试]` 按钮，调用 `reparseDocument` API
  - 不可重试的错误：格式不支持、文件损坏 → 仅显示错误信息，不显示重试按钮

### 3.2 分块预览：选择文档 → 侧滑面板

- **文档选择器**：
  - `<Select showSearch>`，选项为当前知识库已解析的文档（`parse_status='parsed'`）
  - 支持按文件名搜索过滤
  - placeholder："选择要预览的文档..."
- **侧滑 Drawer**：
  - 使用 Ant Design `<Drawer>`，`placement="right"`，`width={560}`
  - 调用 `previewChunks(kbId, docId)` API 获取分块结果
  - 渲染分块列表：
    - 每块一个 `<Card size="small">`，标题显示 `#{chunk_index}` + 字符数 badge
    - 内容预览 300 字符，超出部分显示 "..." + `[展开]` 链接（点击展开完整内容）
    - 元数据显示：`token_count`
  - 顶部统计摘要：总块数、总字符数、平均块大小
  - 底部块大小分布 Mini 柱状图（使用简单的 CSS bar chart 或 Ant Design Charts）
- **从文档详情跳转**：文档详情 Drawer 中点击 "[查看分块 →]" → 关闭文档 Drawer → 切换 Tab 到分块&向量 → 自动选中该文档 → 打开分块预览 Drawer

### 3.3 后端迁移 UI

- **迁移触发**：
  - 当前后端显示 Tag（如 `Chroma` 蓝色标签）
  - 目标后端按钮：`[迁移到 Elasticsearch...]` 和 `[迁移到 Milvus...]`（当前后端对应按钮 `disabled`）
  - 点击按钮 → Modal 弹出
- **迁移确认 Modal**：
  - 标题："迁移向量后端：Chroma → Elasticsearch"
  - 内容：
    - 预计迁移时间："根据 12,500 份文档，预计需要 5–10 分钟"
    - 警告 Alert："迁移期间知识库可读不可写。迁移完成后自动切换到新后端。"
    - 进度条（初始 0%）
  - 底部按钮：`[确认迁移]` `[取消]`
  - 确认后 Modal 内嵌进度条（不关闭 Modal），SSE 实时更新进度
- **进度展示**：
  - 进度百分比 + 进度条 + 当前步骤描述（如 "重新分块 345/12,500" → "向量化 1,200/45,000" → "写入 Elasticsearch 45,000/45,000"）
  - 预计剩余时间动态更新
- **完成/失败处理**：
  - 成功：进度条 100% → 显示 "迁移完成" → 5 秒后 Modal 自动关闭 → 刷新页面显示新后端
  - 失败：进度条变红色 → 显示错误信息 + "已自动回滚到原后端 Chroma" → `[关闭]` 按钮

### 3.4 知识库删除：管道引用检查

- **删除流程**：
  1. 用户在 Settings Tab 点击 `[⚠️ 删除此知识库]`
  2. 调用 `deleteKnowledgeBase(id)` API，后端检查管道引用
  3. 两种情况：
     - **无引用**：后端返回 `{ can_delete: true }` → 前端弹出二次确认 Modal → 确认后真正执行删除
     - **有引用**：后端返回 `{ can_delete: false, referenced_by: [...] }` → 前端弹出阻止 Modal
- **阻止 Modal**（有引用时）：
  ```
  ⚠️  无法删除此知识库
  
  以下管道正在引用此知识库：
  ┌──────────────────────────────────────────────────┐
  │ 📋 综合问诊管道（v3）                [查看]       │
  │ 📋 心血管专科管道（v1）              [查看]       │
  └──────────────────────────────────────────────────┘
  
  请先从这些管道中移除对该知识库的引用后再尝试删除。
  [知道了]
  ```
  点击 `[查看]` → 新标签页打开管道编辑器（`/pipelines/:id/edit`）
- **二次确认 Modal**（无引用时）：
  ```
  确定删除知识库「心血管指南库」？
  
  将同时删除：
  · 12,500 份文档
  · 156 万条分块
  · 全部向量索引
  · 约 2.3 GB 存储空间
  
  此操作不可撤销。
  [取消]  [⚠️ 确认删除]
  ```

### 3.5 测试数据页：3 选项卡 + 组件适配

- **组件复用策略**：
  - 现有 `TestCasePage`、`TestSetPage`、`DraftPage` 均在 `features/rag-eval/pages/` 下
  - 不创建新文件，而是通过 `TestDataPage.tsx` 作为容器页，内嵌这些组件的核心渲染逻辑
  - 如果现有组件包含独立页面布局（Title、面包屑、独立路由），需提取纯内容组件或通过 props 控制渲染模式
  - 方案 A（推荐）：创建 `features/rag-eval/components/TestCaseTabContent.tsx`、`TestSetTabContent.tsx`、`DraftTabContent.tsx`，将页面组件中的 `<div>` 内容部分提取为独立组件，`TestCasePage.tsx` 和 `TestDataPage.tsx` 均使用这些内容组件
  - 方案 B：在 `TestDataPage` 中直接 import 现有页面组件，通过 `embedded={true}` prop 控制是否渲染页面 chrome
- **JSON 导入**：
  - 点击 `[JSON 导入]` → Modal
  - 文本区域粘贴 JSON（placeholder："粘贴 JSON 数组，每项为一个测试用例..."）
  - Validate 按钮：解析 JSON → 校验每个用例的必填字段（query, expected_knowledge_ids, expected_keywords）
  - 校验结果：显示 `解析成功: N 条用例` 或 `第 X 行格式错误: ...`
  - 预览 Table：显示即将导入的用例列表（query / expected_knowledge_ids / expected_keywords / description）
  - `[确认导入]` → 调用 `importTestCases` API
- **分页加载**：CaseTransferModal 中选用例的 Table 支持分页（`page_size=20`），搜索支持按 query 模糊匹配

### 3.6 配置变更触发重建

- **统一警告提示**：修改分块策略或 Embedding 配置后，在配置区下方显示 `<Alert type="warning">保存后将触发全量索引重建，预计需要 X 分钟。重建期间知识库可正常读取。</Alert>`
- **保存 + 触发重建流程**：
  1. 点击 `[保存分块策略]` 或 `[保存 Embedding 配置]`
  2. 调用对应 API（`updateChunkStrategy` / `updateEmbeddingConfig`）
  3. 后端 API 响应中返回 `rebuild_task_id`
  4. 前端立即开始 SSE 订阅重建进度
  5. 在重建历史区域顶部显示当前进行中的任务进度条
  6. 重建完成 → 刷新知识库状态
- **保存按钮状态**：
  - 未修改配置时按钮 `disabled`
  - 修改后按钮 `type="primary"`
  - 保存中按钮 `loading`

### 3.7 权限 Tab 内联编辑

- **access_level 修改**：表格列中使用 `<Select>` 组件，`onChange` 时直接更新 `docAcls` 状态，标记行 `dirty=true`
- **doc_acl 修改**：仅当 access_level=restricted 时显示角色 Tag。点击 Tag 区域或编辑按钮 → Modal 多选角色（角色列表不超过知识库 `visible_roles`）
- **批量保存**：`[保存全部变更]` 按钮仅当有 dirty 行时显示。保存时只提交有变更的文档 ACL，调用 `updateDocumentAcl` API（可并行调用多个）
- **即时保存模式（可选）**：`access_level` 修改时即时调用 API 保存（无批量保存按钮），`doc_acl` 仍在 Modal 确认时保存

### 3.8 SSE 进度订阅

- **订阅模式**：使用 EventSource 或 fetch streaming
  - 后端端点：`GET /api/v1/knowledge-bases/:id/rebuild/status/stream`
  - 事件类型：
    - `progress` → `{ progress_pct: 45, current_step: 'rechunking', completed: 5400, total: 12000 }`
    - `completed` → `{ progress_pct: 100 }`
    - `error` → `{ error_message: '...' }`
- **Zustand 管理**：在 `knowledgeBaseStore` 中用 `subscribeRebuildProgress` action 管理 EventSource 生命周期
- **组件卸载清理**：`useEffect` 返回清理函数，关闭 EventSource 连接
- **上传进度 SSE**：类似模式，订阅文档解析进度

---

## 4. 测试策略

### 4.1 组件测试（Vitest + React Testing Library）

#### KnowledgeBaseCard 渲染

- [ ] **TC-6.1.1**：卡片显示知识库名称、向量后端（带颜色 Tag）、文档数×分块数、权限标识、状态标签、存储大小
- [ ] **TC-6.1.2**：Chroma 后端的卡片显示青色标签 "Chroma"
- [ ] **TC-6.1.3**：ES 后端的卡片显示金色标签 "Elasticsearch"
- [ ] **TC-6.1.4**：Milvus 后端的卡片显示蓝色标签 "Milvus"
- [ ] **TC-6.1.5**：状态为 `rebuilding` 时显示橙色 "🔄 重建中" 标签
- [ ] **TC-6.1.6**：状态为 `error` 时显示红色 "⚠️ 异常" 标签
- [ ] **TC-6.1.7**：可见性为 `public` 时显示 "🔒 公开"
- [ ] **TC-6.1.8**：可见性为 `private` 时显示 "🔒 私有"
- [ ] **TC-6.1.9**：点击卡片 → navigate 到 `/knowledge/:id`
- [ ] **TC-6.1.10**：更多菜单中点击 `[删除]` → 调用删除检查 API → 被引用时弹出阻止 Modal 列出管道名

#### DocumentsTab 上传区域

- [ ] **TC-6.2.1**：拖拽区域渲染正确（提示文本 + 点击选择文件）
- [ ] **TC-6.2.2**：拖入 PDF 文件 → 拖拽区域高亮蓝色边框
- [ ] **TC-6.2.3**：拖入非支持格式文件 → 阻止并提示 "不支持的文件格式"
- [ ] **TC-6.2.4**：一次性拖入 51 个文件 → 阻止并提示 "单次最多上传 50 个文件"
- [ ] **TC-6.2.5**：上传 1 个文件 → 进度列表显示文件名 + 进度条 + 解析中状态
- [ ] **TC-6.2.6**：上传完成后 → 进度项变为 "完成" + 文档列表自动刷新
- [ ] **TC-6.2.7**：上传已存在的文档（MD5 重复）→ 进度项显示 "已存在，无需重复上传"
- [ ] **TC-6.2.8**：上传失败（文件损坏）→ 进度项显示红色 "失败" + 错误信息，不显示重试按钮
- [ ] **TC-6.2.9**：上传失败（解析超时）→ 进度项显示错误 + `[重试]` 按钮

#### ChunksTab 配置与预览

- [ ] **TC-6.3.1**：分块方式切换 → 参数表单动态渲染对应参数
- [ ] **TC-6.3.2**：修改分块策略参数 → 显示 "保存后将触发全量索引重建" 警告
- [ ] **TC-6.3.3**：修改 Embedding 配置 → 显示 "保存后将触发全量索引重建" 警告
- [ ] **TC-6.3.4**：点击 `[保存分块策略]` → 调用 API → 重建进度 SSE 实时更新进度条
- [ ] **TC-6.3.5**：未修改配置时 `[保存]` 按钮 disabled
- [ ] **TC-6.3.6**：`[预览分块结果]` → 选择文档 → Drawer 打开显示分块列表
- [ ] **TC-6.3.7**：分块预览 Drawer 显示块号、字符数、内容预览、总块数统计
- [ ] **TC-6.3.8**：点击迁移按钮 → Modal 弹出显示预计时间
- [ ] **TC-6.3.9**：确认迁移 → SSE 进度更新 → 完成后 Modal 显示 "迁移完成"

#### PermissionsTab 权限编辑

- [ ] **TC-6.4.1**：切换可见性 Radio.Button → 即时调用 updateVisibility API
- [ ] **TC-6.4.2**：visibility=role_scoped 时显示角色可见列表
- [ ] **TC-6.4.3**：`[+ 添加]` 角色 → Select 下拉多选 → 确认后调用 updateVisibleRoles API
- [ ] **TC-6.4.4**：文档 ACL 表格渲染所有文档及当前 access_level
- [ ] **TC-6.4.5**：inherit 行 access_level 改为 restricted → inlne 编辑 → 显示 `[保存全部变更]` 按钮
- [ ] **TC-6.4.6**：批量选中多行 → `[批量设置 access_level]` → 多行同时变更为 inherit/restricted

#### SettingsTab 删除检查

- [ ] **TC-6.5.1**：名称/描述修改后点击 `[保存]` → 调用 updateKnowledgeBase API
- [ ] **TC-6.5.2**：点击 `[⚠️ 删除此知识库]` → 调用管道引用检查 API
- [ ] **TC-6.5.3**：无引用时 → 弹出二次确认 Modal → 确认后调用删除 API → navigate 回列表
- [ ] **TC-6.5.4**：有引用时 → 弹出阻止 Modal，列出引用管道名 + `[查看]` 链接

### 4.2 集成测试

#### 完整知识库生命周期

- [ ] **TC-6.6.1**：从列表页创建知识库 → 命名 + 选择后端 + 保存 → 自动跳转到详情页
- [ ] **TC-6.6.2**：详情页上传 1 个 PDF 文档 → 进度完成 → 文档列表出现该文档
- [ ] **TC-6.6.3**：修改分块策略 chunk_size=256 → 保存 → 重建进度条推进 → 完成后状态变为 ready
- [ ] **TC-6.6.4**：修改 Embedding 模型 → 保存 → 重建进度条推进 → 完成
- [ ] **TC-6.6.5**：上传文档后 → 分块预览可看到正确的分块结果
- [ ] **TC-6.6.6**：修改可见性为 role_scoped → 添加角色 [药师] → 权限 Tab 文档 ACL 总览正确

#### 后端迁移

- [ ] **TC-6.7.1**：点击 [迁移到 Elasticsearch...] → Modal 显示预计时间 → 确认 → 进度条实时更新 → 完成后显示新后端标签
- [ ] **TC-6.7.2**：迁移失败 → Modal 显示错误 + "已回滚到原后端"

#### 测试数据页

- [ ] **TC-6.8.1**：3 选项卡切换 → 分别显示用例列表、测试集列表、草稿列表
- [ ] **TC-6.8.2**：JSON 导入：粘贴 JSON → 校验格式 → 预览 → 确认导入 → 列表更新
- [ ] **TC-6.8.3**：CaseTransferModal 分页加载 >100 条用例
- [ ] **TC-6.8.4**：草稿 Tab 点击 [生成草稿] → 选择知识库和文档 → 开始生成 → SSE 进度显示

#### 列表筛选

- [ ] **TC-6.9.1**：搜索输入 "心血管" → 防抖 300ms → 列表过滤仅显示名称包含 "心血管" 的知识库
- [ ] **TC-6.9.2**：后端筛选 "Chroma" → 列表仅显示 Chroma 后端知识库
- [ ] **TC-6.9.3**：状态筛选 "重建中" → 列表仅显示 rebuilding 状态的知识库
- [ ] **TC-6.9.4**：可见性筛选 "私有" → 列表仅显示 private 的知识库

### 4.3 关键测试场景（至少 8 个）

| # | 场景 | 步骤 | 验证点 |
|---|------|------|--------|
| 1 | **创建知识库 + 上传文档 + 预览分块** | 创建 KB → 上传 PDF → 等待解析 → 分块 Tab 预览结果 | 上传进度正确、分块预览内容正确、解析状态为 parsed |
| 2 | **修改分块策略触发重建** | chunk_size 512→256 → 保存 → 等待重建完成 | 保存按钮可用、重建进度条实时更新、完成后状态 ready |
| 3 | **Vector Backend 迁移** | Chroma → 点击迁移 ES → 确认 → 等待完成 | 进度条实时更新、完成后后端标签变为 ES、可正常检索 |
| 4 | **删除被引用的知识库** | 管道中引用 KB → 设置 Tab 点删除 → 弹窗阻止 | 显示引用管道名、删除被阻止、可点击 [查看] 跳转管道编辑器 |
| 5 | **批量上传 + MD5 去重** | 上传 3 个文件（其中 1 个重复）→ 等待完成 | 重复文件显示 "已存在"、其他 2 个正常上传、文档列表正确 |
| 6 | **文档权限内联编辑** | 权限 Tab → 改文档为 restricted → 设置角色 ACL → 保存 | 保存成功、doc_acl 正确更新、角色列表不超过知识库 visible_roles |
| 7 | **测试数据页 3 选项卡** | 切到测试数据页 → 切换用例/测试集/草稿 → 各执行 CRUD 操作 | 三选项卡功能完整、JSON 导入/预览正常、分页正常 |
| 8 | **草稿生成 SSE 进度** | 测试数据页 → 草稿 Tab → 生成草稿 → 等待 | SSE 进度实时更新、生成完成列表自动刷新 |
| 9 | **分块策略参数表单联动** | 切换分块方式 → 表单字段动态变化 → 各方式参数校验 | 固定大小显示 chunk_size/overlap、语义显示 similarity_threshold、非法值标红 |
| 10 | **知识库列表全筛选** | 先后切换搜索/后端/状态/可见性筛选 → 观察列表变化 | 每种筛选独立生效、组合筛选正确、空结果提示友好 |

---

## 5. 验收检查点

### 5.1 知识库列表页

- [ ] 卡片网格视图正确展示，卡片包含名称/后端/文档数/分块数/权限/状态/存储大小
- [ ] 新建知识库弹窗表单完整（名称/描述/后端/可见性/角色可见/分块策略快速选择/Embedding 模型）
- [ ] 后端选择三个选项均可选（Chroma/ES/Milvus），新建后跳转到详情页
- [ ] 搜索框防抖 300ms 后按名称过滤
- [ ] 后端筛选正确过滤（全部/Chroma/ES/Milvus）
- [ ] 状态筛选正确过滤（全部/就绪/重建中/索引中/异常）
- [ ] 可见性筛选正确过滤（全部/公开/角色可见/私有）
- [ ] 卡片更多菜单中 `[重命名]` / `[更改可见性]` / `[删除]` 功能正常
- [ ] 空状态引导文案和新建按钮正常显示
- [ ] 加载态骨架屏正常显示

### 5.2 知识库详情页——文档 Tab

- [ ] 拖拽上传区域正常渲染，支持点击选择和拖拽文件
- [ ] 文件类型限制正确（pdf/txt/md/html/htm/epub），非法类型阻止并提示
- [ ] 单次上传上限 50 个文件，超限阻止并提示
- [ ] 上传进度列表实时更新文件名/百分比/状态（上传中→解析中→完成/失败）
- [ ] MD5 重复检测：重复文件显示 "已存在，无需重复上传"
- [ ] 解析失败：不可重试错误（文件损坏/格式不支持）不显示重试按钮；可重试错误（解析超时/OCR失败）显示 `[重试]` 按钮
- [ ] 文档表格列正确（文件名/类型/大小/分块数/解析状态/权限级别/上传时间/操作）
- [ ] 文档表格支持搜索、类型筛选、分页
- [ ] 选中文档后 `[批量删除]` 按钮可用，确认弹窗后执行批量删除
- [ ] 点击文档名打开详情 Drawer（元数据 + 前 10 块预览）
- [ ] 文件名搜索结果正确过滤

### 5.3 知识库详情页——分块&向量 Tab

- [ ] 分块方式切换 → 参数表单动态渲染，参数齐全
- [ ] 每种分块方式的参数表单正确渲染对应控件
- [ ] 参数 Tooltip 显示说明
- [ ] 修改配置后显示 "保存后将触发全量索引重建" 警告
- [ ] `[保存分块策略]` 和 `[保存 Embedding 配置]` 正确调用 API 并触发重建
- [ ] 保存按钮状态：未修改 disabled、修改后可点击、保存中 loading
- [ ] 重建进度 SSE 实时更新，进度条和预计剩余时间正确显示
- [ ] 重建完成 → 知识库状态变为 ready
- [ ] Embedding 模型下拉从 `/api/v1/config/embedding-models` 加载
- [ ] `[预览分块结果]` → 选择文档 → 右侧 Drawer 正常打开
- [ ] Drawer 中分块列表内容正确、总块数/字符数统计正确
- [ ] 迁移按钮正确渲染（当前后端按钮 disabled）
- [ ] 迁移确认 Modal 显示预计时间 → 确认 → 进度实时更新 → 完成/失败处理正确
- [ ] 失败时回滚提示正确显示
- [ ] 重建历史列表正确显示最近 5 次记录（触发原因/状态/耗时/进度）

### 5.4 知识库详情页——权限 Tab

- [ ] 可见性 Radio.Button 修改即时保存
- [ ] visibility=role_scoped 时角色可见列表渲染 + `[+ 添加]` 正常
- [ ] 文档 ACL 总览表格完整显示所有文档
- [ ] 文档 access_level 内联编辑（inherit ↔ restricted）
- [ ] restricted 文档的 doc_acl 在 Modal 中编辑角色，不超过知识库 visible_roles
- [ ] 批量设置 access_level 功能正常
- [ ] `[保存全部变更]` 按钮仅在有 dirty 行时显示
- [ ] 保存成功后 dirty 标记清除、数据刷新

### 5.5 知识库详情页——设置 Tab

- [ ] 名称/描述编辑后 `[保存]` 按钮可点击，保存成功后显示成功提示
- [ ] 危险区域删除按钮正确显示（红色 danger type）
- [ ] 点击删除 → 管道引用检查 API 被调用
- [ ] 无引用 → 二次确认弹窗 → 确认删除 → navigate 回列表
- [ ] 有引用 → 阻止 Modal 显示引用管道名 + `[查看]` 链接
- [ ] 阻止 Modal 中 `[查看]` 可跳转到管道编辑器

### 5.6 测试数据页

- [ ] 3 选项卡（测试用例/测试集/草稿）正常切换，URL 同步
- [ ] 测试用例 Tab：列表、搜索、筛选、分页、新建/编辑/删除功能正常
- [ ] JSON 导入：粘贴 JSON → 校验 → 预览 Table → 确认导入，全流程正常
- [ ] 测试集 Tab：列表、新建测试集 Modal（名称/描述/选用例 Transfer）、查看/编辑/删除功能正常
- [ ] CaseTransferModal 分页加载正常（>100 条用例时）
- [ ] 草稿 Tab：列表、搜索、筛选、状态修改、批量导入/忽略功能正常
- [ ] 草稿生成：选择知识库/文档/参数 → `[开始生成]` → SSE 进度 → 完成列表刷新
- [ ] 草稿审核 → 导入为用例功能正常
- [ ] 各 Tab 的组件无独立页面 chrome（无多余面包屑/Title），作为内嵌模式正确渲染

### 5.7 SSE 进度订阅

- [ ] 重建进度 SSE 连接正确建立，事件类型（progress/completed/error）正确解析
- [ ] 进度百分比实时更新到 UI
- [ ] 组件卸载时 SSE 连接正确关闭（无内存泄漏）
- [ ] 上传进度 SSE 类似机制正确
- [ ] SSE 连接异常断线时自动重连（最多 3 次）

### 5.8 异常处理

- [ ] 知识库列表加载失败时显示错误提示 + `[重试]` 按钮
- [ ] 知识库详情加载失败时显示错误提示 + 返回列表按钮
- [ ] 文档上传失败时进度项显示错误信息
- [ ] API 超时时提示 "请求超时，请重试"
- [ ] 网络断开时操作按钮置灰 + 提示 "网络不可用"
- [ ] 后端返回管道引用冲突时前端正确展示阻止 Modal

### 5.9 前端代码规范

- [ ] 所有组件遵循前端目录结构约定（`features/knowledge/` 下按 pages/components/hooks/stores 组织）
- [ ] 无直接 `class Xxx(BaseModel)` 定义（前端实体类型在 `entities/` 目录下使用 TypeScript interface）
- [ ] 无 `any` 类型（TypeScript 严格模式）
- [ ] API 客户端在 `api/knowledge/` 下集中管理
- [ ] 状态管理使用 Zustand（`knowledgeBaseStore`）
- [ ] 所有注释全中文
- [ ] 拖拽上传区域组件可复用（提取为共享组件 `shared/components/FileDropZone.tsx`）

---

## 附录 A：文件清单

| # | 文件 | 类型 | 说明 |
|---|------|------|------|
| 1 | `features/knowledge/stores/knowledgeBaseStore.ts` | 新建 | 知识库状态管理 |
| 2 | `api/knowledge/knowledge-base.ts` | 新建 | 知识库管理 API 客户端 |
| 3 | `entities/knowledge/types.ts` | 新建 | 知识库实体类型定义 |
| 4 | `features/knowledge/pages/KnowledgeListPage.tsx` | 新建 | 知识库列表页 |
| 5 | `features/knowledge/components/KnowledgeBaseCard.tsx` | 新建 | 知识库卡片组件 |
| 6 | `features/knowledge/pages/KnowledgeDetailPage.tsx` | 新建 | 知识库详情页（4 选项卡容器） |
| 7 | `features/knowledge/components/DocumentsTab.tsx` | 新建 | 文档 Tab（拖拽上传 + 文档列表） |
| 8 | `features/knowledge/components/ChunksTab.tsx` | 新建 | 分块&向量 Tab（策略配置 + Embedding + 迁移 + 预览） |
| 9 | `features/knowledge/components/PermissionsTab.tsx` | 新建 | 权限 Tab（可见性 + 角色可见 + 文档 ACL 总览） |
| 10 | `features/knowledge/components/SettingsTab.tsx` | 新建 | 设置 Tab（名称/描述 + 删除） |
| 11 | `features/knowledge/components/ChunkPreviewDrawer.tsx` | 新建 | 分块预览侧滑面板 |
| 12 | `features/knowledge/components/BackendMigrationModal.tsx` | 新建 | 后端迁移确认/进度 Modal |
| 13 | `features/knowledge/pages/TestDataPage.tsx` | 新建 | 测试数据页（3 选项卡容器） |
| 14 | `features/knowledge/hooks/useUploadProgress.ts` | 新建 | 上传进度追踪 Hook |
| 15 | `features/knowledge/hooks/useRebuildProgress.ts` | 新建 | 重建进度 SSE 订阅 Hook |
| 16 | `features/rag-eval/components/TestCaseTabContent.tsx` | 新建/提取 | 测试用例 Tab 内容组件（从 TestCasePage 提取） |
| 17 | `features/rag-eval/components/TestSetTabContent.tsx` | 新建/提取 | 测试集 Tab 内容组件（从 TestSetPage 提取） |
| 18 | `features/rag-eval/components/DraftTabContent.tsx` | 新建/提取 | 草稿 Tab 内容组件（从 DraftPage 提取） |
| 19 | `router/` | 改造 | 新增 `/knowledge`、`/knowledge/:id`、`/knowledge/test-data` 路由 |
| 20 | `shared/components/FileDropZone.tsx` | 新建 | 可复用的拖拽上传区域组件 |

**合计**：约 17 个新建文件 + 3 个改造/提取文件

## 附录 B：关键技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| `react` | 19.x | UI 框架 |
| `antd` | 6.x | UI 组件库（Card、Tabs、Table、Upload、Progress、Drawer、Modal、Select、InputNumber、Slider、Tag、Button、Alert、Skeleton 等） |
| `@ant-design/icons` | — | 图标（FilePdfOutlined、DatabaseOutlined、LockOutlined 等） |
| `zustand` | 5.x | 状态管理（knowledgeBaseStore） |
| `react-router-dom` | 7.x | SPA 路由（/knowledge...） |
| `@tanstack/react-query` | 5.x | 服务端状态管理（可选，用于文档列表/详情缓存） |
| `axios` | — | HTTP 请求 + 上传进度回调 |
| `EventSource` | 原生 | SSE 进度订阅（重建进度、上传进度） |

## 附录 C：与后端 Phase 2/3 的接口契约

| 前端功能 | 后端端点 | Phase |
|---------|---------|-------|
| 知识库 CRUD | `GET/POST/PUT/DELETE /api/v1/knowledge-bases` | Phase 2 §2.11 |
| 文档上传 | `POST /api/v1/knowledge-bases/:id/documents` | Phase 2 §2.11 |
| 文档列表/详情/删除 | `GET/DELETE /api/v1/knowledge-bases/:id/documents` | Phase 2 §2.11 |
| 文档重新解析 | `POST /api/v1/knowledge-bases/:id/documents/:doc_id/reparse` | Phase 2 §2.11 |
| 文档 ACL 更新 | `PUT /api/v1/knowledge-bases/:id/documents/:doc_id/acl` | Phase 2 §2.11 |
| 分块策略更新 | `PUT /api/v1/knowledge-bases/:id/chunk-strategy` | Phase 2 §2.11 |
| Embedding 配置更新 | `PUT /api/v1/knowledge-bases/:id/embedding-config` | Phase 2 §2.11 |
| 向量后端迁移 | `POST /api/v1/knowledge-bases/:id/migrate-backend` | Phase 2 §2.11 |
| 重建状态 SSE | `GET /api/v1/knowledge-bases/:id/rebuild/status/stream` | Phase 2 §2.11 |
| 分块预览 | `GET /api/v1/knowledge-bases/:id/chunk-preview` | Phase 2 §2.11 |
| 角色列表 | `GET /api/v1/roles` | Phase 1 §1.7 |
| Embedding 模型列表 | `GET /api/v1/config/embedding-models` | Phase 0 基础设施 |
| 测试用例 CRUD | `GET/POST/PUT/DELETE /api/v1/test-cases` | Phase 7 |
| 测试集 CRUD | `GET/POST/PUT/DELETE /api/v1/test-sets` | Phase 7 |
| 草稿 CRUD | `GET/POST/PUT /api/v1/test-case-drafts` | Phase 7 |
