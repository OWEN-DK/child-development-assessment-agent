# 03 — 知识库管理：完整实现规范

> **对应需求**：[03-knowledge-base](../requirements/03-knowledge-base.md)
> **核心目标**：实现多知识库独立管理——创建、文档上传、分块、向量化、索引维护。
> **依赖模块**：[04-permission](./04-permission.md)（JWT 中间件注入 tenant_id/user_id/roles，双层 Pre-filter）
> **被依赖模块**：[01-pipeline-engine](./01-pipeline-engine.md)（管道通过 kb_id 引用知识库），[05-search-api](./05-search-api.md)（搜索端点），[06-rag-evaluation](./06-rag-evaluation.md)（知识库快照）

---

## 1. API 契约

所有端点前缀：`/api/v1`。统一响应格式 `{code, message, data}`。
认证头：`Authorization: Bearer <JWT>`（中间件提取 tenant_id、user_id、roles 注入请求上下文）。

### 1.1 POST `/knowledge-bases` — 创建知识库

**Request Body:**
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | string | 是 | 知识库名称，1-200 字符 |
| `description` | string | 否 | 知识库描述 |
| `vector_backend` | enum | 是 | `chroma` / `elasticsearch` / `milvus` |
| `chunk_strategy` | object | 否 | 分块策略配置（不传则使用 L1/L0 默认值） |
| `chunk_strategy.type` | enum | 否 | `fixed_size` / `semantic` / `paragraph` / `heading` / `recursive` |
| `chunk_strategy.chunk_size` | int | 否 | 128-4096，默认 512 |
| `chunk_strategy.overlap` | int | 否 | 0-50（百分比），默认 10 |
| `chunk_strategy.separator` | enum | 否 | `paragraph` / `sentence` / `custom` |
| `chunk_strategy.min_chunk_size` | int | 否 | 最小块大小，默认 64 |
| `chunk_strategy.max_chunk_size` | int | 否 | 最大块大小，默认 2048 |
| `embedding_config` | object | 否 | Embedding 配置（不传则使用 L1/L0 默认值） |
| `embedding_config.model` | string | 否 | 模型标识，默认 `dashscope-text-embedding-v3` |
| `embedding_config.dimension` | int | 否 | 256/512/768/1024，默认模型原生维度 |
| `embedding_config.batch_size` | int | 否 | 16/32/64/128，默认 32 |
| `embedding_config.similarity_metric` | enum | 否 | `cosine` / `euclidean` / `dot_product`，默认 `cosine` |
| `embedding_config.multilingual_mode` | enum | 否 | `auto` / `zh` / `en` / `off`，默认 `auto` |
| `visibility` | enum | 是 | `public` / `role_scoped` / `private` |
| `visible_roles` | list[string] | 否 | role_scoped 时必填，角色名列表 |

**Response (201 Created):**
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "kb_a1b2c3d4e5f6",
    "tenant_id": "t_renhe",
    "name": "心血管指南库",
    "description": "覆盖高血压、冠心病等心血管内科常见疾病的诊疗指南",
    "vector_backend": "chroma",
    "chunk_strategy": { "type": "fixed_size", "chunk_size": 512, "overlap": 10, "separator": "paragraph", "min_chunk_size": 64, "max_chunk_size": 2048 },
    "embedding_config": { "model": "dashscope-text-embedding-v3", "dimension": 1024, "batch_size": 32, "similarity_metric": "cosine", "multilingual_mode": "auto" },
    "visibility": "public",
    "visible_roles": [],
    "owner_id": "u_zhang",
    "status": "ready",
    "document_count": 0,
    "chunk_count": 0,
    "storage_size_bytes": 0,
    "created_at": "2026-05-14T10:30:00Z",
    "updated_at": "2026-05-14T10:30:00Z"
  }
}
```

**错误：**
| 错误码 | error_code | 说明 |
|--------|-----------|------|
| 400 | `KB_LIMIT_EXCEEDED` | 知识库数量达到租户配额上限 |
| 400 | `INVALID_VECTOR_BACKEND` | 向量后端不在租户允许列表中 |
| 400 | `INVALID_VISIBLE_ROLES` | `role_scoped` 时 visible_roles 为空或含无效角色名 |
| 403 | `FORBIDDEN` | 用户无创建权限 |

---

### 1.2 GET `/knowledge-bases` — 知识库列表

**Query Parameters:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `search` | string | 否 | 名称模糊搜索 |
| `vector_backend` | enum | 否 | 按后端筛选 |
| `status` | enum | 否 | 按状态筛选 `ready` / `rebuilding` / `indexing` / `error` |
| `visibility` | enum | 否 | 按可见性筛选 |
| `page` | int | 否 | 页码，默认 1 |
| `page_size` | int | 否 | 每页数量，默认 20，最大 100 |

**Response:**
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [ { /* 知识库摘要，不含 chunk_strategy 和 embedding_config 详情 */ } ],
    "total": 5,
    "page": 1,
    "page_size": 20
  }
}
```

知识库摘要字段：id, tenant_id, name, description（截断前 200 字符）, vector_backend, visibility, status, document_count, chunk_count, storage_size_bytes, owner_id, created_at, updated_at。

---

### 1.3 GET `/knowledge-bases/{id}` — 知识库详情

**Path Parameters:** `id` — 知识库 ID

**Response:** 返回知识库完整信息（包含 chunk_strategy、embedding_config 全部字段）。若无权限访问则返回 403。

---

### 1.4 PUT `/knowledge-bases/{id}` — 更新知识库配置

仅更新名称/描述/权限（不触发重建）。

**Request Body:**
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | string | 否 | 知识库名称 |
| `description` | string | 否 | 知识库描述 |
| `visibility` | enum | 否 | `public` / `role_scoped` / `private` |
| `visible_roles` | list[string] | 否 | role_scoped 时生效 |

**Response:** 更新后的完整知识库对象。

**错误：**
| 错误码 | error_code | 说明 |
|--------|-----------|------|
| 403 | `FORBIDDEN` | 非 owner 且非 admin |
| 409 | `KB_IS_REBUILDING` | 知识库正在重建，禁止修改 |
| 422 | `INVALID_VISIBLE_ROLES` | role_scoped 时 visible_roles 为空 |

---

### 1.5 PUT `/knowledge-bases/{id}/chunk-strategy` — 更新分块策略（触发重建）

**Request Body:**
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `type` | enum | 是 | `fixed_size` / `semantic` / `paragraph` / `heading` / `recursive` |
| `chunk_size` | int | 否 | 128-4096 |
| `overlap` | int | 否 | 0-50 |
| `separator` | enum | 否 | `paragraph` / `sentence` / `custom` |
| `similarity_threshold` | float | 否 | 0.5-0.95（语义分块时必填） |
| `paragraph_separator_regex` | string | 否 | 按段落分块时必填 |
| `heading_levels` | list[string] | 否 | 按标题层级时必填，如 `["H1","H2","H3"]` |
| `preserve_heading_path` | bool | 否 | 按标题层级时选填 |
| `separator_priority_list` | list[string] | 否 | 递归分块时必填 |
| `min_chunk_size` | int | 否 | 默认 64 |
| `max_chunk_size` | int | 否 | 默认 2048 |
| `chunk_metadata` | bool | 否 | 是否保留源文档元数据，默认 true |

**Response:** 返回更新后的 chunk_strategy + `rebuild_task_id` 用于 SSE 进度追踪。

```json
{
  "code": 0,
  "message": "分块策略已更新，全量索引重建已触发",
  "data": {
    "chunk_strategy": { /* 新策略全字段 */ },
    "rebuild_task_id": "rt_abc123"
  }
}
```

---

### 1.6 PUT `/knowledge-bases/{id}/embedding-config` — 更新 Embedding 配置（触发重建）

**Request Body:**
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `model` | string | 是 | 模型标识 |
| `dimension` | int | 否 | 256/512/768/1024，默认模型原生 |
| `batch_size` | int | 否 | 16/32/64/128 |
| `similarity_metric` | enum | 否 | `cosine` / `euclidean` / `dot_product` |
| `multilingual_mode` | enum | 否 | `auto` / `zh` / `en` / `off` |

**Response:** 同 1.5，返回 embedding_config + rebuild_task_id。

**错误：**
| 错误码 | error_code | 说明 |
|--------|-----------|------|
| 400 | `EMBEDDING_MODEL_NOT_AVAILABLE` | 模型不在租户允许列表 |

---

### 1.7 POST `/knowledge-bases/{id}/migrate-backend` — 迁移向量后端（触发重建）

**Request Body:**
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `target_backend` | enum | 是 | `elasticsearch` / `milvus` / `chroma` |

**Response:**
```json
{
  "code": 0,
  "message": "向量后端迁移已提交",
  "data": {
    "source_backend": "chroma",
    "target_backend": "elasticsearch",
    "estimated_minutes": 12,
    "rebuild_task_id": "rt_def456"
  }
}
```

**错误：**
| 错误码 | error_code | 说明 |
|--------|-----------|------|
| 400 | `ALREADY_SAME_BACKEND` | 目标后端与当前相同 |
| 400 | `BACKEND_NOT_AVAILABLE` | 目标后端未在租户配置中启用 |
| 409 | `KB_ALREADY_MIGRATING` | 已有迁移/重建任务进行中 |

---

### 1.8 DELETE `/knowledge-bases/{id}` — 删除知识库

**Query Parameters:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `force` | bool | 否 | 跳过管道引用检查（仅 super_admin），默认 false |

**Response (无引用):**
```json
{
  "code": 0,
  "message": "知识库已删除",
  "data": null
}
```

**Response (有引用且未传 force):**
```json
{
  "code": 409,
  "message": "知识库被 2 个管道引用，无法删除",
  "error_code": "KB_HAS_REFERENCES",
  "details": {
    "pipelines": [
      {"id": "pl_001", "name": "心血管检索流水线"},
      {"id": "pl_002", "name": "药物查询流水线"}
    ]
  }
}
```

删除操作级联：删除知识库记录 → 删除所有 kb_documents → 删除所有 kb_chunks → 删除向量存储 Collection/Index → 删除 BM25 索引目录 → 删除重建任务记录。

---

### 1.9 POST `/knowledge-bases/{id}/documents` — 上传文档（批量）

**Content-Type:** `multipart/form-data`

**Form Fields:**
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `files` | file[] | 是 | 最多 50 个文件，支持 PDF/TXT/Markdown/HTML/EPUB |
| `access_level` | enum | 否 | `inherit` / `restricted`，默认 `inherit` |
| `doc_acl` | string | 否 | JSON 数组字符串，如 `["admin","editor"]` |

**Response:**
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "created": [
      { "id": "doc_001", "filename": "高血压指南2024.pdf", "status": "pending" }
    ],
    "duplicates": [
      { "id": "doc_002", "filename": "药物相互作用表.pdf", "message": "文档已存在，返回已有引用" }
    ],
    "errors": [
      { "filename": "broken.pdf", "message": "文件损坏，无法解析" }
    ]
  }
}
```

---

### 1.10 GET `/knowledge-bases/{id}/documents` — 文档列表

**Query Parameters:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `search` | string | 否 | 文件名模糊搜索 |
| `file_type` | enum | 否 | 按类型筛选 `pdf` / `txt` / `markdown` / `html` / `epub` |
| `parse_status` | enum | 否 | `pending` / `parsing` / `parsed` / `error` |
| `page` | int | 否 | 默认 1 |
| `page_size` | int | 否 | 默认 20，最大 100 |

**Response:** 标准分页响应，items 为文档摘要（不含 text_content）。

---

### 1.11 GET `/knowledge-bases/{id}/documents/{doc_id}` — 文档详情 + 分块预览

**Response:**
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "doc_001",
    "kb_id": "kb_a1b2",
    "filename": "高血压指南2024.pdf",
    "file_type": "pdf",
    "file_size": 2411724,
    "page_count": 156,
    "md5_hash": "a1b2c3d4e5f6...",
    "parse_status": "parsed",
    "metadata": { "author": "卫健委", "publish_year": 2024 },
    "access_level": "inherit",
    "doc_acl": [],
    "owner_id": "u_zhang",
    "chunk_count": 256,
    "uploaded_at": "2026-05-14T09:00:00Z",
    "chunk_preview": [
      { "chunk_index": 0, "content": "第一章 总则\n1.1 本指南适用于...", "token_count": 128, "vector_id": "vec_001" },
      { "chunk_index": 1, "content": "1.2 高血压诊断标准...", "token_count": 135, "vector_id": "vec_002" }
    ]
  }
}
```

`chunk_preview` 最多返回前 10 个分块。`text_content` 不在此接口返回（调用单独的内部方法获取全文）。

---

### 1.12 DELETE `/knowledge-bases/{id}/documents/{doc_id}` — 删除文档

**Response:**
```json
{
  "code": 0,
  "message": "文档已删除（含 256 个分块及向量）",
  "data": null
}
```

级联删除：文档记录 → 所有关联 kb_chunks → 向量存储中对应向量。

---

### 1.13 POST `/knowledge-bases/{id}/documents/{doc_id}/reparse` — 重新解析文档

**Response:**
```json
{
  "code": 0,
  "message": "文档重新解析已提交",
  "data": { "doc_id": "doc_001", "parse_status": "parsing" }
}
```

重新解析流程：重置 parse_status → `parsing`，重新提取文本 → 按当前分块策略重新分块 → 重新向量化 → 更新索引。

**错误：**
| 错误码 | error_code | 说明 |
|--------|-----------|------|
| 400 | `DOC_NOT_PARSABLE` | 文档格式不支持（如原始上传时的 parse_status 为 error 且原因为"不支持的文件格式"或"文件损坏"） |
| 409 | `KB_IS_REBUILDING` | 知识库正在重建中 |

---

### 1.14 PUT `/knowledge-bases/{id}/documents/{doc_id}/acl` — 更新文档 ACL

**Request Body:**
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `access_level` | enum | 是 | `inherit` / `restricted` |
| `doc_acl` | list[string] | 否 | restricted 时必填，角色列表 |

**验证规则：**
- `doc_acl` 中的角色不能超出知识库 `visible_roles` 范围
- `access_level=inherit` 时忽略 `doc_acl`（清空）
- 修改后 30 秒内相关缓存失效

**Response:** 更新后的文档权限对象。

---

### 1.15 GET `/knowledge-bases/{id}/rebuild/status` — 重建任务状态（SSE）

**Event Stream (SSE):**

```
event: progress
data: {"task_id":"rt_abc123","trigger":"chunk_change","progress_pct":45,"message":"重新分块中... 已完成 560/1248 块"}

event: progress
data: {"task_id":"rt_abc123","trigger":"chunk_change","progress_pct":78,"message":"向量化中... 已完成 973/1248 块"}

event: complete
data: {"task_id":"rt_abc123","trigger":"chunk_change","progress_pct":100,"message":"索引重建完成","completed_at":"2026-05-14T11:05:00Z"}

event: error
data: {"task_id":"rt_abc123","trigger":"embedding_change","progress_pct":32,"message":"向量化失败：API 超时","error":"Embedding API timeout after 30s"}
```

---

### 1.16 GET `/knowledge-bases/{id}/chunk-preview` — 分块预览

**Query Parameters:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `doc_id` | string | 是 | 要预览的文档 ID |

**Response:**
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "doc_id": "doc_001",
    "chunk_strategy": { "type": "fixed_size", "chunk_size": 512, "overlap": 10 },
    "total_chunks": 48,
    "preview": [
      { "index": 0, "content": "第一章 总则\n1.1 适用范围...", "char_count": 498, "token_estimate": 135 },
      { "index": 1, "content": "1.2 高血压诊断标准\n收缩压 ≥ 140mmHg...", "char_count": 512, "token_estimate": 142 }
    ]
  }
}
```

`preview` 返回前 10 个分块。

---

## 2. 数据库 DDL

MySQL 5.7 完整建表语句。所有 ID 使用 24 位雪花字符串（不使用自增整数）。租户隔离通过 Repository 基类自动注入 `WHERE tenant_id = :tenant_id`。

```sql
-- ============================================================
-- 知识库主表
-- ============================================================
CREATE TABLE IF NOT EXISTS `knowledge_bases` (
    `id` VARCHAR(24) NOT NULL COMMENT '知识库唯一标识，雪花ID',
    `tenant_id` VARCHAR(24) NOT NULL COMMENT '所属租户ID',
    `name` VARCHAR(200) NOT NULL COMMENT '知识库名称',
    `description` TEXT COMMENT '知识库描述',
    `vector_backend` ENUM('chroma', 'elasticsearch', 'milvus') NOT NULL DEFAULT 'chroma' COMMENT '向量存储后端',
    `chunk_strategy` JSON NOT NULL COMMENT '分块策略配置JSON',
    `embedding_config` JSON NOT NULL COMMENT 'Embedding配置JSON',
    `visibility` ENUM('public', 'role_scoped', 'private') NOT NULL DEFAULT 'private' COMMENT '可见性',
    `visible_roles` JSON COMMENT 'role_scoped时生效，角色名列表',
    `owner_id` VARCHAR(24) NOT NULL COMMENT '创建者用户ID',
    `status` ENUM('ready', 'rebuilding', 'indexing', 'error') NOT NULL DEFAULT 'ready' COMMENT '知识库状态',
    `document_count` INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '文档总数',
    `chunk_count` INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '分块总数',
    `storage_size_bytes` BIGINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '向量存储占用字节数',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    KEY `idx_tenant_id` (`tenant_id`),
    KEY `idx_owner_id` (`owner_id`),
    KEY `idx_status` (`status`),
    KEY `idx_vector_backend` (`vector_backend`),
    KEY `idx_tenant_status` (`tenant_id`, `status`),
    KEY `idx_tenant_backend` (`tenant_id`, `vector_backend`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='知识库主表';

-- ============================================================
-- 知识库文档表
-- ============================================================
CREATE TABLE IF NOT EXISTS `kb_documents` (
    `id` VARCHAR(24) NOT NULL COMMENT '文档唯一标识，雪花ID',
    `kb_id` VARCHAR(24) NOT NULL COMMENT '所属知识库ID',
    `tenant_id` VARCHAR(24) NOT NULL COMMENT '所属租户ID（冗余加速查询）',
    `filename` VARCHAR(500) NOT NULL COMMENT '原始文件名',
    `file_type` ENUM('pdf', 'txt', 'markdown', 'html', 'epub') NOT NULL COMMENT '文件类型',
    `file_size` INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '文件大小（字节）',
    `page_count` INT UNSIGNED DEFAULT 0 COMMENT '页数（PDF/EPUB）',
    `md5_hash` VARCHAR(64) NOT NULL COMMENT '文件内容MD5，用于去重',
    `parse_status` ENUM('pending', 'parsing', 'parsed', 'error') NOT NULL DEFAULT 'pending' COMMENT '解析状态',
    `error_message` VARCHAR(500) DEFAULT NULL COMMENT '解析失败时的错误信息',
    `text_content` MEDIUMTEXT COMMENT '解析后的纯文本内容',
    `metadata` JSON COMMENT '文档元数据（作者、出版年份、标题层级结构等）',
    `access_level` ENUM('inherit', 'restricted') NOT NULL DEFAULT 'inherit' COMMENT '文档访问级别',
    `doc_acl` JSON COMMENT 'restricted时的可访问角色列表',
    `owner_id` VARCHAR(24) NOT NULL COMMENT '上传者用户ID',
    `chunk_count` INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '当前分块数',
    `uploaded_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '上传时间',
    PRIMARY KEY (`id`),
    KEY `idx_kb_id` (`kb_id`),
    KEY `idx_tenant_id` (`tenant_id`),
    KEY `idx_md5_hash` (`md5_hash`),
    KEY `idx_parse_status` (`parse_status`),
    KEY `idx_kb_status` (`kb_id`, `parse_status`),
    KEY `idx_tenant_md5` (`tenant_id`, `md5_hash`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='知识库文档表';

-- ============================================================
-- 知识库分块表
-- ============================================================
CREATE TABLE IF NOT EXISTS `kb_chunks` (
    `id` VARCHAR(24) NOT NULL COMMENT '分块唯一标识，雪花ID',
    `kb_id` VARCHAR(24) NOT NULL COMMENT '所属知识库ID',
    `doc_id` VARCHAR(24) NOT NULL COMMENT '所属文档ID',
    `tenant_id` VARCHAR(24) NOT NULL COMMENT '所属租户ID（冗余加速查询）',
    `chunk_index` INT UNSIGNED NOT NULL COMMENT '分块在文档中的序号（从0开始）',
    `content` MEDIUMTEXT NOT NULL COMMENT '分块文本内容',
    `token_count` INT UNSIGNED NOT NULL DEFAULT 0 COMMENT 'Token估算数量',
    `metadata` JSON COMMENT '分块元数据（来源文档、页码、章节路径、角色ACL等）',
    `vector_id` VARCHAR(255) COMMENT '向量存储中的向量ID（Chroma的document_id, ES的_doc id, Milvus的entity id）',
    PRIMARY KEY (`id`),
    KEY `idx_kb_id` (`kb_id`),
    KEY `idx_doc_id` (`doc_id`),
    KEY `idx_tenant_id` (`tenant_id`),
    KEY `idx_vector_id` (`vector_id`),
    KEY `idx_kb_doc` (`kb_id`, `doc_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='知识库分块表';

-- ============================================================
-- 知识库重建任务表
-- ============================================================
CREATE TABLE IF NOT EXISTS `kb_rebuild_tasks` (
    `id` VARCHAR(24) NOT NULL COMMENT '任务唯一标识，雪花ID',
    `kb_id` VARCHAR(24) NOT NULL COMMENT '目标知识库ID',
    `tenant_id` VARCHAR(24) NOT NULL COMMENT '所属租户ID',
    `trigger` ENUM('chunk_change', 'embedding_change', 'backend_migration') NOT NULL COMMENT '触发原因',
    `status` ENUM('running', 'completed', 'failed') NOT NULL DEFAULT 'running' COMMENT '任务状态',
    `progress_pct` TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '进度百分比 0-100',
    `progress_message` VARCHAR(500) COMMENT '当前步骤描述',
    `started_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '开始时间',
    `completed_at` DATETIME COMMENT '完成时间',
    `error_message` TEXT COMMENT '失败时的错误详情',
    PRIMARY KEY (`id`),
    KEY `idx_kb_id` (`kb_id`),
    KEY `idx_tenant_id` (`tenant_id`),
    KEY `idx_status` (`status`),
    KEY `idx_kb_status` (`kb_id`, `status`),
    KEY `idx_tenant_kb` (`tenant_id`, `kb_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='知识库重建任务表';
```

**DDL 设计说明：**

- **`tenant_id` 冗余**：`kb_documents` 和 `kb_chunks` 中的 `tenant_id` 是冗余字段。复制该冗余使 `BaseRepository` 的 `tenant_id` 自动注入 WHERE 子句能一视同仁地作用于所有表，无需跨表 JOIN。这一致性对 CI 静态扫描检测裸 SQL 至关重要——所有表都有 `tenant_id` 列意味着所有查询都能被同一个 WHERE 条件覆盖。
- **`vector_id` 可为 NULL**：分块创建时（parse_status=`pending`）尚未向量化，`vector_id` 为空。向量化完成后回填。
- **`kb_chunks.content` 使用 MEDIUMTEXT**：支持最大 16MB 的单块内容（极端情况：长文档的 heading 级别分块可能一次切出较大的逻辑块）。
- **零外键约束**：遵循项目统一规范——采用弱关联（应用层保证引用完整性），MySQL 5.7 不建外键。`kb_id`、`doc_id` 的引用完整性由 Service 层的事务边界保证。

---

## 3. 服务层接口

### 3.1 字节级常量（`backend/src/service/knowledge/constants.py`）

```python
# 文件大小上限
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024        # 50MB 单文件
MAX_BATCH_FILES = 50                           # 批量上传上限
MAX_BATCH_SIZE_BYTES = 200 * 1024 * 1024       # 批量上传总大小 200MB

# 解析
PARSE_TIMEOUT_SECONDS = 300                    # 单文档解析超时 5 分钟
PARSE_RETRY_MAX = 1                            # 自动重试次数
PARSE_RETRY_DELAY_SECONDS = 5                  # 重试间隔

# 分块
CHUNK_SIZE_MIN = 128
CHUNK_SIZE_MAX = 4096
CHUNK_OVERLAP_MAX_PCT = 50

# 重建
REBUILD_SSE_HEARTBEAT_SECONDS = 15             # SSE 心跳间隔
REBUILD_STALE_TIMEOUT_SECONDS = 3600           # 重建任务超时 1 小时
```

### 3.2 知识库 Schema（`backend/src/schemas/knowledge.py`）

```python
from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field

# ── 枚举 ──

class VectorBackend(str, Enum):
    CHROMA = "chroma"
    ELASTICSEARCH = "elasticsearch"
    MILVUS = "milvus"

class KnowledgeBaseStatus(str, Enum):
    READY = "ready"
    REBUILDING = "rebuilding"
    INDEXING = "indexing"
    ERROR = "error"

class KnowledgeBaseVisibility(str, Enum):
    PUBLIC = "public"
    ROLE_SCOPED = "role_scoped"
    PRIVATE = "private"

class ParseStatus(str, Enum):
    PENDING = "pending"
    PARSING = "parsing"
    PARSED = "parsed"
    ERROR = "error"

class DocAccessLevel(str, Enum):
    INHERIT = "inherit"
    RESTRICTED = "restricted"

class RebuildTrigger(str, Enum):
    CHUNK_CHANGE = "chunk_change"
    EMBEDDING_CHANGE = "embedding_change"
    BACKEND_MIGRATION = "backend_migration"

class RebuildStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class ChunkType(str, Enum):
    FIXED_SIZE = "fixed_size"
    SEMANTIC = "semantic"
    PARAGRAPH = "paragraph"
    HEADING = "heading"
    RECURSIVE = "recursive"

class ChunkSeparator(str, Enum):
    PARAGRAPH = "paragraph"
    SENTENCE = "sentence"
    CUSTOM = "custom"

class SimilarityMetric(str, Enum):
    COSINE = "cosine"
    EUCLIDEAN = "euclidean"
    DOT_PRODUCT = "dot_product"

class MultilingualMode(str, Enum):
    AUTO = "auto"
    ZH = "zh"
    EN = "en"
    OFF = "off"

# ── 请求 Schema ──

class ChunkStrategyReq(BaseModel):
    type: ChunkType = ChunkType.FIXED_SIZE
    chunk_size: int = Field(default=512, ge=128, le=4096)
    overlap: int = Field(default=10, ge=0, le=50)
    separator: ChunkSeparator = ChunkSeparator.PARAGRAPH

    # 语义分块参数
    similarity_threshold: float | None = Field(default=None, ge=0.5, le=0.95)
    embedding_model: str | None = None

    # 段落分块参数
    paragraph_separator_regex: str | None = None

    # 标题层级参数
    heading_levels: list[str] | None = None
    preserve_heading_path: bool = False

    # 递归分块参数
    separator_priority_list: list[str] | None = None

    # 通用参数
    min_chunk_size: int = Field(default=64, ge=1)
    max_chunk_size: int = Field(default=2048, ge=128)
    chunk_metadata: bool = True


class EmbeddingConfigReq(BaseModel):
    model: str = "dashscope-text-embedding-v3"
    dimension: int | None = None
    batch_size: int = Field(default=32, ge=16, le=128)
    similarity_metric: SimilarityMetric = SimilarityMetric.COSINE
    multilingual_mode: MultilingualMode = MultilingualMode.AUTO


class CreateKnowledgeBaseReq(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    vector_backend: VectorBackend
    chunk_strategy: ChunkStrategyReq | None = None
    embedding_config: EmbeddingConfigReq | None = None
    visibility: KnowledgeBaseVisibility
    visible_roles: list[str] = Field(default_factory=list)


class UpdateKnowledgeBaseReq(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    visibility: KnowledgeBaseVisibility | None = None
    visible_roles: list[str] | None = None


class UpdateChunkStrategyReq(ChunkStrategyReq):
    pass


class UpdateEmbeddingConfigReq(EmbeddingConfigReq):
    pass


class MigrateBackendReq(BaseModel):
    target_backend: VectorBackend


class UpdateDocAclReq(BaseModel):
    access_level: DocAccessLevel
    doc_acl: list[str] = Field(default_factory=list)

# ── 响应 Schema ──

class KnowledgeBaseSummary(BaseModel):
    id: str
    tenant_id: str
    name: str
    description: str | None = None
    vector_backend: VectorBackend
    visibility: KnowledgeBaseVisibility
    status: KnowledgeBaseStatus
    document_count: int
    chunk_count: int
    storage_size_bytes: int
    owner_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class KnowledgeBaseDetail(KnowledgeBaseSummary):
    chunk_strategy: dict[str, Any]
    embedding_config: dict[str, Any]
    visible_roles: list[str]
    description: str | None = None  # 不截断


class DocumentSummary(BaseModel):
    id: str
    kb_id: str
    filename: str
    file_type: str
    file_size: int
    page_count: int
    md5_hash: str
    parse_status: ParseStatus
    error_message: str | None = None
    access_level: DocAccessLevel
    doc_acl: list[str]
    owner_id: str
    chunk_count: int
    uploaded_at: datetime

    class Config:
        from_attributes = True


class ChunkPreviewItem(BaseModel):
    chunk_index: int
    content: str
    token_count: int
    vector_id: str | None = None


class DocumentDetail(DocumentSummary):
    metadata: dict[str, Any] | None = None
    chunk_preview: list[ChunkPreviewItem]


class RebuildTaskSummary(BaseModel):
    id: str
    kb_id: str
    trigger: RebuildTrigger
    status: RebuildStatus
    progress_pct: int
    progress_message: str | None = None
    started_at: datetime
    completed_at: datetime | None = None
    error_message: str | None = None

    class Config:
        from_attributes = True


class RebuildTriggeredResponse(BaseModel):
    chunk_strategy: dict[str, Any] | None = None
    embedding_config: dict[str, Any] | None = None
    source_backend: str | None = None
    target_backend: str | None = None
    rebuild_task_id: str


class BatchUploadResult(BaseModel):
    created: list[DocumentSummary]
    duplicates: list[dict[str, str]]
    errors: list[dict[str, str]]


class ChunkPreviewResult(BaseModel):
    doc_id: str
    chunk_strategy: dict[str, Any]
    total_chunks: int
    preview: list[dict[str, Any]]


class PipelineReference(BaseModel):
    id: str
    name: str


class KbDeletionConflict(BaseModel):
    pipelines: list[PipelineReference]
```

### 3.3 SQLAlchemy Model（`backend/src/models/knowledge.py`）

```python
from datetime import datetime
from enum import Enum as PyEnum
from typing import Any

from sqlalchemy import (BigInteger, DateTime, Enum, Index, Integer, JSON,
                        String, Text, func)
from sqlalchemy.dialects.mysql import MEDIUMTEXT, TINYINT
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base


class VectorBackendEnum(PyEnum):
    CHROMA = "chroma"
    ELASTICSEARCH = "elasticsearch"
    MILVUS = "milvus"


class KnowledgeBaseStatusEnum(PyEnum):
    READY = "ready"
    REBUILDING = "rebuilding"
    INDEXING = "indexing"
    ERROR = "error"


class KnowledgeBaseVisibilityEnum(PyEnum):
    PUBLIC = "public"
    ROLE_SCOPED = "role_scoped"
    PRIVATE = "private"


class ParseStatusEnum(PyEnum):
    PENDING = "pending"
    PARSING = "parsing"
    PARSED = "parsed"
    ERROR = "error"


class DocAccessLevelEnum(PyEnum):
    INHERIT = "inherit"
    RESTRICTED = "restricted"


class RebuildTriggerEnum(PyEnum):
    CHUNK_CHANGE = "chunk_change"
    EMBEDDING_CHANGE = "embedding_change"
    BACKEND_MIGRATION = "backend_migration"


class RebuildStatusEnum(PyEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# 通用 Enum 配置工厂函数
def _enum_values(obj):
    return [e.value for e in obj]


class KnowledgeBase(Base):
    __tablename__ = "knowledge_bases"

    id: Mapped[str] = mapped_column(String(24), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(24), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    vector_backend: Mapped[VectorBackendEnum] = mapped_column(
        Enum(VectorBackendEnum, values_callable=_enum_values),
        nullable=False, default=VectorBackendEnum.CHROMA
    )
    chunk_strategy: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    embedding_config: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    visibility: Mapped[KnowledgeBaseVisibilityEnum] = mapped_column(
        Enum(KnowledgeBaseVisibilityEnum, values_callable=_enum_values),
        nullable=False, default=KnowledgeBaseVisibilityEnum.PRIVATE
    )
    visible_roles: Mapped[list[str] | None] = mapped_column(JSON)
    owner_id: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[KnowledgeBaseStatusEnum] = mapped_column(
        Enum(KnowledgeBaseStatusEnum, values_callable=_enum_values),
        nullable=False, default=KnowledgeBaseStatusEnum.READY
    )
    document_count: Mapped[int] = mapped_column(Integer, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    storage_size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = ({"extend_existing": True},)


class KbDocument(Base):
    __tablename__ = "kb_documents"

    id: Mapped[str] = mapped_column(String(24), primary_key=True)
    kb_id: Mapped[str] = mapped_column(String(24), nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(24), nullable=False)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str] = mapped_column(
        Enum("pdf", "txt", "markdown", "html", "epub"), nullable=False
    )
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    page_count: Mapped[int | None] = mapped_column(Integer, default=0)
    md5_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    parse_status: Mapped[ParseStatusEnum] = mapped_column(
        Enum(ParseStatusEnum, values_callable=_enum_values),
        nullable=False, default=ParseStatusEnum.PENDING
    )
    error_message: Mapped[str | None] = mapped_column(String(500))
    text_content: Mapped[str | None] = mapped_column(MEDIUMTEXT)
    metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    access_level: Mapped[DocAccessLevelEnum] = mapped_column(
        Enum(DocAccessLevelEnum, values_callable=_enum_values),
        nullable=False, default=DocAccessLevelEnum.INHERIT
    )
    doc_acl: Mapped[list[str] | None] = mapped_column(JSON)
    owner_id: Mapped[str] = mapped_column(String(24), nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = ({"extend_existing": True},)


class KbChunk(Base):
    __tablename__ = "kb_chunks"

    id: Mapped[str] = mapped_column(String(24), primary_key=True)
    kb_id: Mapped[str] = mapped_column(String(24), nullable=False)
    doc_id: Mapped[str] = mapped_column(String(24), nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(24), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(MEDIUMTEXT, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    vector_id: Mapped[str | None] = mapped_column(String(255))

    __table_args__ = ({"extend_existing": True},)


class KbRebuildTask(Base):
    __tablename__ = "kb_rebuild_tasks"

    id: Mapped[str] = mapped_column(String(24), primary_key=True)
    kb_id: Mapped[str] = mapped_column(String(24), nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(24), nullable=False)
    trigger: Mapped[RebuildTriggerEnum] = mapped_column(
        Enum(RebuildTriggerEnum, values_callable=_enum_values), nullable=False
    )
    status: Mapped[RebuildStatusEnum] = mapped_column(
        Enum(RebuildStatusEnum, values_callable=_enum_values),
        nullable=False, default=RebuildStatusEnum.RUNNING
    )
    progress_pct: Mapped[int] = mapped_column(TINYINT(unsigned=True), default=0)
    progress_message: Mapped[str | None] = mapped_column(String(500))
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    error_message: Mapped[str | None] = mapped_column(Text)

    __table_args__ = ({"extend_existing": True},)
```

### 3.4 Repository（`backend/src/repository/knowledge/`）

```python
# knowledge_base_repository.py
from sqlalchemy.ext.asyncio import async_sessionmaker
from src.models.knowledge import KnowledgeBase
from src.repository.base import BaseRepository

class KnowledgeBaseRepository(BaseRepository[KnowledgeBase]):
    """知识库 Repository，自动注入 tenant_id 行级过滤"""

    def __init__(self, db_session_factory: async_sessionmaker):
        super().__init__(KnowledgeBase, db_session_factory)

    async def count_by_tenant(self, tenant_id: str) -> int:
        return await self.count_by_filter(tenant_id=tenant_id)

    async def search(self, tenant_id: str, *, search: str = None,
                     vector_backend: str = None, status: str = None,
                     visibility: str = None, skip: int = 0, limit: int = 20):
        """多条件筛选 + 名称搜索（SQL LIKE）"""
        # 实现细节：动态构建 WHERE 条件
        ...


# document_repository.py
from src.models.knowledge import KbDocument
from src.repository.base import BaseRepository

class DocumentRepository(BaseRepository[KbDocument]):
    """文档 Repository"""

    def __init__(self, db_session_factory: async_sessionmaker):
        super().__init__(KbDocument, db_session_factory)

    async def get_by_md5(self, kb_id: str, tenant_id: str, md5: str) -> KbDocument | None:
        """MD5 去重查询：同一个 KB 下 MD5 相同视为重复"""
        ...


# chunk_repository.py
from src.models.knowledge import KbChunk
from src.repository.base import BaseRepository

class ChunkRepository(BaseRepository[KbChunk]):
    """分块 Repository"""

    def __init__(self, db_session_factory: async_sessionmaker):
        super().__init__(KbChunk, db_session_factory)

    async def batch_insert(self, chunks: list[dict]) -> list[KbChunk]:
        """批量插入分块"""
        ...

    async def get_by_doc_id(self, kb_id: str, doc_id: str, limit: int = 10) -> list[KbChunk]:
        """获取文档的前 N 个分块（预览用）"""
        ...

    async def delete_by_doc_id(self, kb_id: str, doc_id: str) -> int:
        """删除文档所有分块，返回删除数量"""
        ...


# rebuild_task_repository.py
from src.models.knowledge import KbRebuildTask
from src.repository.base import BaseRepository

class RebuildTaskRepository(BaseRepository[KbRebuildTask]):
    """重建任务 Repository"""

    def __init__(self, db_session_factory: async_sessionmaker):
        super().__init__(KbRebuildTask, db_session_factory)

    async def get_latest_running(self, kb_id: str, tenant_id: str) -> KbRebuildTask | None:
        """获取知识库当前运行中的任务"""
        ...

    async def get_recent(self, kb_id: str, tenant_id: str, limit: int = 5) -> list[KbRebuildTask]:
        """获取最近 N 次重建记录"""
        ...
```

### 3.5 `KnowledgeBaseService`（`backend/src/service/knowledge/knowledge_base_service.py`）

```python
from dataclasses import dataclass
from injector import inject
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.models.knowledge import KnowledgeBase, VectorBackendEnum
from src.schemas.knowledge import (
    CreateKnowledgeBaseReq, UpdateKnowledgeBaseReq,
    UpdateChunkStrategyReq, UpdateEmbeddingConfigReq,
    KnowledgeBaseDetail, KnowledgeBaseSummary, RebuildTriggeredResponse,
)
from src.repository.knowledge.knowledge_base_repository import KnowledgeBaseRepository
from src.repository.knowledge.rebuild_task_repository import RebuildTaskRepository
from src.service.knowledge.rebuild_service import RebuildService
from src.service.knowledge.migration_service import MigrationService
from src.service.knowledge.vector_store_factory import VectorStoreFactory


class KnowledgeBaseService:
    """知识库管理门面服务

    协调 CRUD、策略更新、后端迁移。内部委托子服务执行重建和迁移。
    """

    @inject
    def __init__(
        self,
        db_session_factory: async_sessionmaker,
        kb_repo: KnowledgeBaseRepository,
        task_repo: RebuildTaskRepository,
        rebuild_service: RebuildService,
        migration_service: MigrationService,
        vector_store_factory: VectorStoreFactory,
    ):
        self.db = db_session_factory
        self.kb_repo = kb_repo
        self.task_repo = task_repo
        self.rebuild_service = rebuild_service
        self.migration_service = migration_service
        self.vector_store_factory = vector_store_factory

    # ── CRUD ──

    async def create(self, tenant_id: str, user_id: str, req: CreateKnowledgeBaseReq) -> KnowledgeBaseDetail:
        """创建知识库：写入 MySQL + 创建向量存储 Collection/Index + 初始化 BM25 索引"""
        ...

    async def list(
        self, tenant_id: str, *, search: str = None, vector_backend: str = None,
        status: str = None, visibility: str = None, page: int = 1, page_size: int = 20
    ) -> tuple[list[KnowledgeBaseSummary], int]:
        """知识库列表（自动角色过滤）"""
        ...

    async def get_detail(self, kb_id: str, tenant_id: str) -> KnowledgeBaseDetail:
        """知识库详情（含完整配置）"""
        ...

    async def update(self, kb_id: str, tenant_id: str, user_id: str,
                     req: UpdateKnowledgeBaseReq) -> KnowledgeBaseDetail:
        """更新名称/描述/权限（不触发重建）"""
        ...

    async def delete(self, kb_id: str, tenant_id: str,
                     user_id: str, force: bool = False) -> None | dict:
        """删除知识库：检查管道引用 → 级联删除文档/分块/向量/BM25"""
        ...

    # ── 策略变更（触发重建）──

    async def update_chunk_strategy(
        self, kb_id: str, tenant_id: str, req: UpdateChunkStrategyReq
    ) -> RebuildTriggeredResponse:
        """更新分块策略 → 触发全量重建"""
        ...

    async def update_embedding_config(
        self, kb_id: str, tenant_id: str, req: UpdateEmbeddingConfigReq
    ) -> RebuildTriggeredResponse:
        """更新 Embedding 配置 → 触发全量重建"""
        ...

    async def migrate_backend(
        self, kb_id: str, tenant_id: str, target_backend: str
    ) -> RebuildTriggeredResponse:
        """迁移向量后端 → 委托 MigrationService"""
        ...

    # ── 辅助方法 ──

    async def _check_pipeline_references(self, kb_id: str, tenant_id: str) -> list[dict]:
        """查询引用此知识库的管道列表（跨模块调用管道模块 API）"""
        ...

    async def _validate_kb_access(self, kb_id: str, tenant_id: str, user_roles: list[str]) -> KnowledgeBase:
        """校验用户是否有权访问此知识库（visibility + roles 匹配）"""
        ...
```

### 3.6 `DocumentService`（`backend/src/service/knowledge/document_service.py`）

```python
from dataclasses import dataclass
from pathlib import Path
from injector import inject
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.schemas.knowledge import (
    BatchUploadResult, DocumentDetail, DocumentSummary, UpdateDocAclReq,
)
from src.repository.knowledge.document_repository import DocumentRepository
from src.repository.knowledge.chunk_repository import ChunkRepository
from src.service.knowledge.chunking_engine import ChunkingEngine
from src.service.knowledge.embedding_engine import EmbeddingEngine
from src.service.knowledge.vector_store_factory import VectorStoreFactory
from src.service.knowledge.parser_service import DocumentParserService


class DocumentService:
    """文档管理服务：上传、解析、分块、向量化、ACL"""

    @inject
    def __init__(
        self,
        db_session_factory: async_sessionmaker,
        doc_repo: DocumentRepository,
        chunk_repo: ChunkRepository,
        parser: DocumentParserService,
        chunking_engine: ChunkingEngine,
        embedding_engine: EmbeddingEngine,
        vector_store_factory: VectorStoreFactory,
    ):
        ...

    async def upload(
        self, kb_id: str, tenant_id: str, user_id: str,
        files: list[tuple[str, bytes, str]],  # (filename, content, content_type)
        access_level: str = "inherit", doc_acl: list[str] = None
    ) -> BatchUploadResult:
        """批量上传文档：MD5 去重 → 保存文件 → 插入 DB → 触发异步解析"""
        ...

    async def _parse_async(self, doc_id: str, kb_id: str, tenant_id: str):
        """异步解析文档：提取文本 → 更新 parse_status → 触发分块+向量化"""
        ...

    async def list_documents(
        self, kb_id: str, tenant_id: str, *, search: str = None,
        file_type: str = None, parse_status: str = None,
        page: int = 1, page_size: int = 20
    ) -> tuple[list[DocumentSummary], int]:
        """文档列表"""
        ...

    async def get_detail(self, kb_id: str, doc_id: str, tenant_id: str) -> DocumentDetail:
        """文档详情 + 分块预览（前 10 块）"""
        ...

    async def delete(self, kb_id: str, doc_id: str, tenant_id: str) -> None:
        """删除文档：级联删除分块记录 + 向量存储向量"""
        ...

    async def reparse(self, kb_id: str, doc_id: str, tenant_id: str) -> dict:
        """重新解析文档：校验可否重解析 → 重置 parse_status → 触发解析"""
        ...

    async def update_acl(self, kb_id: str, doc_id: str, tenant_id: str,
                         req: UpdateDocAclReq) -> DocumentSummary:
        """更新文档 ACL：校验角色范围 → 更新 doc_acl → 失效缓存"""
        ...

    async def chunk_preview(self, kb_id: str, doc_id: str, tenant_id: str) -> dict:
        """分块预览：获取文档文本 → 应用当前分块策略 → 返回前 10 块"""
        ...
```

### 3.7 `RebuildService`（`backend/src/service/knowledge/rebuild_service.py`）

```python
import asyncio
from dataclasses import dataclass
from injector import inject
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.schemas.knowledge import RebuildTaskSummary
from src.repository.knowledge.rebuild_task_repository import RebuildTaskRepository
from src.repository.knowledge.knowledge_base_repository import KnowledgeBaseRepository
from src.repository.knowledge.chunk_repository import ChunkRepository
from src.service.knowledge.chunking_engine import ChunkingEngine
from src.service.knowledge.embedding_engine import EmbeddingEngine
from src.service.knowledge.vector_store_factory import VectorStoreFactory
from src.service.knowledge.sse_publisher import SSEPublisher


class RebuildService:
    """索引重建服务：后台异步重建 + SSE 进度推送"""

    @inject
    def __init__(
        self,
        db_session_factory: async_sessionmaker,
        kb_repo: KnowledgeBaseRepository,
        task_repo: RebuildTaskRepository,
        chunk_repo: ChunkRepository,
        doc_repo,  # DocumentRepository
        chunking_engine: ChunkingEngine,
        embedding_engine: EmbeddingEngine,
        vector_store_factory: VectorStoreFactory,
        sse_publisher: SSEPublisher,
    ):
        ...

    async def trigger_rebuild(
        self, kb_id: str, tenant_id: str, trigger: str
    ) -> str:
        """触发重建：创建任务 → 更新 KB 状态 → 启动异步重建任务 → 返回 task_id"""
        ...

    async def _execute_rebuild(self, kb_id: str, tenant_id: str, task_id: str, trigger: str):
        """后台执行全量重建流水线"""
        # 1. 获取知识库所有文档
        # 2. 按当前分块策略重新分块
        # 3. 按 Embedding 配置重新向量化
        # 4. 写入向量存储
        # 5. 进度上报（SSE）
        ...

    async def watch_progress(self, kb_id: str, tenant_id: str):
        """SSE 生成器：轮询重建任务进度 → 推送 SSE 事件"""
        ...

    async def get_latest_task(self, kb_id: str, tenant_id: str) -> RebuildTaskSummary | None:
        """获取最近一次重建任务"""
        ...

    async def get_recent_tasks(self, kb_id: str, tenant_id: str, limit: int = 5) -> list[RebuildTaskSummary]:
        """获取最近 N 次重建任务列表"""
        ...
```

### 3.8 `MigrationService`（`backend/src/service/knowledge/migration_service.py`）

```python
import asyncio
from dataclasses import dataclass
from injector import inject
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.repository.knowledge.knowledge_base_repository import KnowledgeBaseRepository
from src.repository.knowledge.chunk_repository import ChunkRepository
from src.service.knowledge.embedding_engine import EmbeddingEngine
from src.service.knowledge.vector_store_factory import VectorStoreFactory
from src.service.knowledge.sse_publisher import SSEPublisher


class MigrationService:
    """向量后端迁移服务

    迁移流程：
    1. 创建新后端 Collection/Index
    2. 从旧后端读取所有向量
    3. 写入新后端（如果 embedding config 变了则重新向量化）
    4. 验证新后端数据完整性
    5. 切换 knowledge_base.vector_backend → 新后端
    6. 清理旧后端数据
    7. 失败时回滚（不清理旧数据，状态恢复 ready）
    """

    @inject
    def __init__(
        self,
        db_session_factory: async_sessionmaker,
        kb_repo: KnowledgeBaseRepository,
        chunk_repo: ChunkRepository,
        embedding_engine: EmbeddingEngine,
        vector_store_factory: VectorStoreFactory,
        sse_publisher: SSEPublisher,
    ):
        ...

    async def estimate_time(self, kb_id: str, tenant_id: str, target_backend: str) -> int:
        """估算迁移耗时（分钟），基于文档量和后端性能特征"""
        ...

    async def migrate(
        self, kb_id: str, tenant_id: str, target_backend: str, task_id: str
    ) -> None:
        """执行迁移。由 RebuildService.trigger_rebuild 调用，作为后台任务运行"""
        ...

    async def _rollback(self, kb_id: str, tenant_id: str, task_id: str):
        """迁移失败时回滚：清理新后端 → 恢复 KB 状态 ready → 记录错误"""
        ...
```

### 3.9 `SSEPublisher`（`backend/src/service/knowledge/sse_publisher.py`）

```python
import asyncio
from dataclasses import dataclass, field
from asyncio import Queue

class SSEPublisher:
    """SSE 事件发布器

    每个知识库维护一个 SSE 事件队列。多个连接共享同一个队列。
    发布者写入队列 → 所有监听者收到相同事件。
    """

    def __init__(self):
        self._channels: dict[str, set[Queue]] = {}  # kb_id → 订阅者队列集合

    async def subscribe(self, kb_id: str) -> Queue:
        """订阅知识库的 SSE 事件流，返回队列"""
        ...

    async def unsubscribe(self, kb_id: str, queue: Queue):
        """取消订阅"""
        ...

    async def publish(self, kb_id: str, event: dict):
        """向知识库所有订阅者广播事件"""
        ...
```

### 3.10 `DocumentParserService`（`backend/src/service/knowledge/parser_service.py`）

```python
import asyncio
from pathlib import Path

class DocumentParserService:
    """文档解析服务：PDF/TXT/Markdown/HTML/EPUB → 纯文本"""

    async def parse(self, file_path: Path, file_type: str) -> str:
        """解析文档，返回纯文本内容

        根据 file_type 选择解析器：
        - PDF: PyMuPDF (fitz) + 可选 OCR (pytesseract)
        - TXT: 直接读取 + 编码检测
        - Markdown: markdown-it-py → 提取纯文本（保留标题层级）
        - HTML: BeautifulSoup → 提取纯文本（保留标题标签）
        - EPUB: EbookLib → 提取文本内容

        解析超时：5 分钟（asyncio.wait_for）
        失败重试：1 次（间隔 5 秒）
        文件损坏/格式不匹配：直接返回 None，不重试
        """
        ...

    async def extract_metadata(self, file_path: Path, file_type: str) -> dict:
        """提取文档元数据（作者、标题、出版日期、页数等）"""
        ...
```

### 3.11 `VectorStoreFactory`（`backend/src/service/knowledge/vector_store_factory.py`）

```python
from src.service.knowledge.vector_store_adapter import VectorStoreAdapter

class VectorStoreFactory:
    """向量后端工厂，根据类型返回对应的适配器实例"""

    def __init__(self, chroma_adapter, es_adapter, milvus_adapter):
        self._adapters = {
            "chroma": chroma_adapter,
            "elasticsearch": es_adapter,
            "milvus": milvus_adapter,
        }

    def get(self, backend: str) -> VectorStoreAdapter:
        if backend not in self._adapters:
            raise ValueError(f"不支持的向量后端: {backend}")
        return self._adapters[backend]
```

---

## 4. 向量后端适配器接口

### 4.1 `VectorStoreAdapter` 抽象基类

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class CollectionInfo:
    name: str
    document_count: int
    dimension: int
    storage_bytes: int


class VectorStoreAdapter(ABC):
    """向量存储适配器抽象接口

    三个具体实现：ChromaAdapter, ElasticsearchAdapter, MilvusAdapter。
    每个方法的第一参数 metadata 用于传递后端特定配置（如 Chroma 的 hnsw:space）。
    """

    @abstractmethod
    async def create_collection(
        self, kb_id: str, tenant_id: str, dimension: int, metadata: dict[str, Any]
    ) -> None:
        """创建知识库对应的 Collection/Index

        Args:
            kb_id: 知识库 ID
            tenant_id: 租户 ID（用于命名约定）
            dimension: 向量维度
            metadata: 后端特定配置。Chroma 传入 {'hnsw:space': 'cosine'};
                      ES 传入 shards/replicas 配置; Milvus 传入 index_type 等。
        """
        ...

    @abstractmethod
    async def delete_collection(self, kb_id: str, tenant_id: str) -> None:
        """删除知识库对应的 Collection/Index"""
        ...

    @abstractmethod
    async def add_embeddings(
        self, kb_id: str, tenant_id: str,
        chunk_ids: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]],
        texts: list[str],
    ) -> list[str]:
        """批量添加向量

        Args:
            chunk_ids: 分块 ID 列表（用作主键/文档 ID）
            embeddings: 向量列表
            metadatas: 元数据列表（含 doc_id, chunk_index, doc_acl, page, heading_path 等）
            texts: 原始文本列表（ES 需存储用于全文搜索）

        Returns:
            vector_ids: 后端分配的向量 ID 列表（Chroma 返回 uuid, ES 返回 _id, Milvus 返回 entity id）
        """
        ...

    @abstractmethod
    async def search(
        self, kb_id: str, tenant_id: str,
        query_embedding: list[float],
        top_k: int = 10,
        filter_condition: dict[str, Any] = None,
    ) -> list[dict[str, Any]]:
        """向量检索

        Args:
            query_embedding: 查询向量
            top_k: 返回数量
            filter_condition: ACL 过滤条件（由 ACLFilterBuilder 构建）

        Returns:
            [{chunk_id, doc_id, content, score, metadata}, ...]
        """
        ...

    @abstractmethod
    async def delete_by_filter(
        self, kb_id: str, tenant_id: str, filter_condition: dict[str, Any]
    ) -> int:
        """按过滤条件删除向量

        Args:
            filter_condition: 过滤条件。如 {'doc_id': 'doc_001'} 删除某文档所有向量

        Returns:
            删除的向量数量
        """
        ...

    @abstractmethod
    async def get_collection_info(self, kb_id: str, tenant_id: str) -> CollectionInfo:
        """获取 Collection/Index 信息（文档数、维度、存储大小）"""
        ...

    # ── 命名约定 ──

    def _collection_name(self, kb_id: str, tenant_id: str) -> str:
        """Collection 命名规则：{tenant_id}_{kb_id}

        对于 ES（索引名必须全小写）：rag_{tenant_id}_{kb_id}
        对于 Milvus（collection 名必须全小写）：rag_{tenant_id}_{kb_id}
        Chroma 直接使用 {tenant_id}_{kb_id}
        """
        ...
```

### 4.2 `ChromaAdapter`

```python
import os
import chromadb
from chromadb.config import Settings

class ChromaAdapter(VectorStoreAdapter):
    """Chroma 向量后端适配器

    存储位置: storage/chroma/{tenant_id}/
    1 KB = 1 Collection，命名: {tenant_id}_{kb_id}
    必须使用 cosine 空间（DashScope 输出 cosine similarity）
    """

    def __init__(self, persist_dir: str = "storage/chroma"):
        self._base_dir = persist_dir

    def _get_client(self, tenant_id: str) -> chromadb.PersistentClient:
        tenant_dir = os.path.join(self._base_dir, tenant_id)
        return chromadb.PersistentClient(path=tenant_dir)

    async def create_collection(self, kb_id, tenant_id, dimension, metadata):
        client = self._get_client(tenant_id)
        name = self._collection_name(kb_id, tenant_id)
        # 强制注入 hnsw:space=cosine
        meta = {**metadata, "hnsw:space": "cosine"}
        client.create_collection(name=name, metadata=meta)

    async def search(self, kb_id, tenant_id, query_embedding, top_k=10, filter_condition=None):
        client = self._get_client(tenant_id)
        collection = client.get_collection(self._collection_name(kb_id, tenant_id))
        where = filter_condition.get("where") if filter_condition else None
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        return self._format_results(results, "cosine")

    # ... 其余方法类似
```

### 4.3 `ElasticsearchAdapter`

```python
from elasticsearch import AsyncElasticsearch

class ElasticsearchAdapter(VectorStoreAdapter):
    """Elasticsearch 向量后端适配器

    1 KB = 1 Index，命名: rag_{tenant_id}_{kb_id}（全小写）
    映射字段: chunk_id (keyword), doc_id (keyword), content (text),
              embedding (dense_vector), metadata (object),
              doc_acl (keyword 数组，用于 terms 过滤)
    支持 ES 内置 BM25 全文搜索（无需独立 BM25 索引）
    """

    def __init__(self, hosts: list[str], username: str = None, password: str = None):
        self._client = AsyncElasticsearch(hosts=hosts, basic_auth=(username, password) if username else None)

    async def create_collection(self, kb_id, tenant_id, dimension, metadata):
        index_name = self._collection_name(kb_id, tenant_id).lower()
        shards = metadata.get("shards", 1)
        replicas = metadata.get("replicas", 0)
        mapping = {
            "settings": {"number_of_shards": shards, "number_of_replicas": replicas},
            "mappings": {
                "properties": {
                    "chunk_id": {"type": "keyword"},
                    "doc_id": {"type": "keyword"},
                    "content": {"type": "text", "analyzer": "standard"},
                    "embedding": {"type": "dense_vector", "dims": dimension, "index": True, "similarity": "cosine"},
                    "doc_acl": {"type": "keyword"},
                    "page": {"type": "integer"},
                    "heading_path": {"type": "keyword"},
                    "uploaded_at": {"type": "date"},
                }
            }
        }
        await self._client.indices.create(index=index_name, body=mapping)

    async def search(self, kb_id, tenant_id, query_embedding, top_k=10, filter_condition=None):
        index_name = self._collection_name(kb_id, tenant_id).lower()
        query = {
            "knn": {
                "field": "embedding",
                "query_vector": query_embedding,
                "k": top_k,
                "num_candidates": top_k * 10,
            }
        }
        if filter_condition:
            query["knn"]["filter"] = filter_condition.get("filter", [])
        results = await self._client.search(index=index_name, body=query, size=top_k)
        return self._format_results(results)

    # collection_name 重写：ES index 名必须全小写
    def _collection_name(self, kb_id: str, tenant_id: str) -> str:
        return f"rag_{tenant_id}_{kb_id}".lower()

    # ... 其余方法
```

### 4.4 `MilvusAdapter`

```python
from pymilvus import connections, Collection, FieldSchema, CollectionSchema, DataType

class MilvusAdapter(VectorStoreAdapter):
    """Milvus 向量后端适配器

    1 KB = 1 Collection，命名: rag_{tenant_id}_{kb_id}（全小写）
    Schema: chunk_id (VARCHAR, primary), doc_id (VARCHAR), content (VARCHAR),
            embedding (FLOAT_VECTOR), doc_acl (VARCHAR 数组),
            page (INT64), heading_path (VARCHAR)
    索引类型: IVF_FLAT（默认）/ HNSW
    """

    def __init__(self, host: str = "localhost", port: int = 19530):
        connections.connect(host=host, port=port)

    async def create_collection(self, kb_id, tenant_id, dimension, metadata):
        from pymilvus import utility
        name = self._collection_name(kb_id, tenant_id).lower()
        fields = [
            FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=24, is_primary=True),
            FieldSchema(name="doc_id", dtype=DataType.VARCHAR, max_length=24),
            FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dimension),
            FieldSchema(name="doc_acl", dtype=DataType.ARRAY, element_type=DataType.VARCHAR, max_capacity=50, max_length=50),
            FieldSchema(name="page", dtype=DataType.INT64),
            FieldSchema(name="heading_path", dtype=DataType.VARCHAR, max_length=500),
        ]
        schema = CollectionSchema(fields, description=f"KB {kb_id} for tenant {tenant_id}")
        collection = Collection(name=name, schema=schema)
        # 创建索引
        index_type = metadata.get("index_type", "IVF_FLAT")
        index_params = {"metric_type": metadata.get("metric_type", "COSINE"), "index_type": index_type, "params": {"nlist": 128}}
        collection.create_index(field_name="embedding", index_params=index_params)

    async def search(self, kb_id, tenant_id, query_embedding, top_k=10, filter_condition=None):
        name = self._collection_name(kb_id, tenant_id).lower()
        collection = Collection(name=name)
        collection.load()
        expr = filter_condition.get("expr") if filter_condition else None
        search_params = {"metric_type": "COSINE", "params": {"nprobe": 10}}
        results = collection.search(
            data=[query_embedding], anns_field="embedding",
            param=search_params, limit=top_k, expr=expr,
            output_fields=["chunk_id", "doc_id", "content", "doc_acl", "page", "heading_path"],
        )
        return self._format_results(results)

    def _collection_name(self, kb_id: str, tenant_id: str) -> str:
        return f"rag_{tenant_id}_{kb_id}".lower()

    # ... 其余方法
```

### 4.5 `ACLFilterBuilder`（检索时注入文档级 ACL 过滤）

> **权威定义**：`ACLFilterBuilder` 接口和三个后端子类的权威定义在 [04-permission.md §3.8](04-permission.md)。此处仅列出知识库检索场景的使用方式和具体实现。

```python
# 权威定义：backend/src/service/permission/acl_filter_builder.py
# 以下为知识库检索场景的具体实现，由 Phase 1 权限模块提供接口

from service.permission.acl_filter_builder import (
    ACLFilterBuilder,
    ChromaACLFilterBuilder,
    ESACLFilterBuilder,
    MilvusACLFilterBuilder,
)

# 使用方式：在检索节点中根据知识库的 vector_backend 获取对应 Builder
# god_mode 参数由 TenantContext.is_god_mode 传入
# builder.build_filter(user_roles=roles, god_mode=is_god_mode)

class ChromaACLFilterBuilder(ACLFilterBuilder):
    """Chroma 后端具体实现（覆盖 04-permission 的桩实现）"""
    def build_filter(self, user_roles: list[str], god_mode: bool = False) -> dict:
        if god_mode or not user_roles:
            return {}
        return {
            "where": {
                "$or": [
                    {"doc_acl": {"$contains": role}} for role in user_roles
                ] + [
                    {"doc_acl": {"$size": 0}}
                ]
            }
        }


class ESACLFilterBuilder(ACLFilterBuilder):
    """ES 后端具体实现（覆盖 04-permission 的桩实现）"""
    def build_filter(self, user_roles: list[str], god_mode: bool = False) -> dict:
        if god_mode or not user_roles:
            return {}
        return {
            "filter": [
                {
                    "bool": {
                        "should": [
                            {"terms": {"doc_acl": user_roles}},
                            {"bool": {"must_not": {"exists": {"field": "doc_acl"}}}},
                        ],
                        "minimum_should_match": 1,
                    }
                }
            ]
        }


class MilvusACLFilterBuilder(ACLFilterBuilder):
    """Milvus 后端具体实现（覆盖 04-permission 的桩实现）"""
    def build_filter(self, user_roles: list[str], god_mode: bool = False) -> dict:
        if god_mode or not user_roles:
            return {}
        role_conditions = ' or '.join(
            f'"{role}" in doc_acl' for role in user_roles
        )
        inherit_condition = 'doc_acl is null or len(doc_acl) == 0'
        return {"expr": f"({role_conditions}) or ({inherit_condition})"}
```

---

## 5. 数据流

### 5.1 文档上传 → 解析 → 分块 → 向量化 → 索引 全流程

```
用户拖拽文件
    │
    ▼
POST /api/v1/knowledge-bases/{id}/documents
    │
    ├─[1] 文件校验：文件类型白名单、单文件 ≤ 50MB、批量 ≤ 50 个、总量 ≤ 200MB
    │
    ├─[2] MD5 去重：逐文件计算 MD5 → 查询 kb_documents.md5_hash
    │   ├─ 已存在 → 加入 duplicates 列表
    │   └─ 不存在 → 加入待处理列表
    │
    ├─[3] 保存文件：写入 storage/{tenant_id}/documents/{kb_id}/{doc_id}.{ext}
    │
    ├─[4] 插入 DB：写入 kb_documents 记录（parse_status=pending）
    │
    └─[5] 提交异步任务：BackgroundTasks 调用 _parse_async(doc_id, kb_id, tenant_id)
        │
        ▼
    _parse_async (后台执行)
        │
        ├─[6] 更新 parse_status → parsing
        │
        ├─[7] 调用 DocumentParserService.parse()
        │   ├─ 成功 → 返回 text_content + metadata
        │   ├─ 文件损坏/格式不匹配 → parse_status=error, error_message="文件损坏，无法解析"（不重试）
        │   └─ 文本提取失败/OCR失败/超时 → 重试 1 次（间隔 5s）→ 仍失败 → parse_status=error
        │
        ├─[8] 解析成功 → 更新 parse_status=parsed, text_content, metadata
        │
        ├─[9] 调用 ChunkingEngine.chunk(text_content, chunk_strategy)
        │   └─ 返回 list[Chunk] (content, token_count, metadata)
        │
        ├─[10] 批量插入 kb_chunks（chunk_index, content, token_count, metadata）
        │
        ├─[11] 调用 EmbeddingEngine.embed_batch(texts)
        │   └─ 返回 list[list[float]]（向量列表）
        │
        ├─[12] 调用 VectorStoreAdapter.add_embeddings(chunk_ids, embeddings, metadatas, texts)
        │   └─ 返回 vector_ids → 回填 kb_chunks.vector_id
        │
        ├─[13] 增量更新 BM25 索引（仅 Chroma/Milvus 后端需要）
        │
        └─[14] 更新 knowledge_bases.document_count++, chunk_count+=N, storage_size_bytes+=X
```

### 5.2 向量后端迁移流（Chroma → ES 为例）

```
POST /api/v1/knowledge-bases/{id}/migrate-backend (target_backend="elasticsearch")
    │
    ├─[1] 校验：target_backend ≠ current_backend；无进行中任务
    │
    ├─[2] 更新 KB status → rebuilding
    │
    ├─[3] 创建 kb_rebuild_tasks 记录（trigger=backend_migration, status=running）
    │
    └─[4] 提交异步任务 migrate(kb_id, tenant_id, "elasticsearch", task_id)
        │
        ▼
    后台迁移执行
        │
        ├─[5] SSE 推送: progress 0%,"正在初始化 ES 连接..."
        │
        ├─[6] 调用 ElasticsearchAdapter.create_collection()
        │   └─ 创建 ES index: rag_{tenant_id}_{kb_id}
        │
        ├─[7] SSE 推送: progress 5%,"ES 索引创建完成"
        │
        ├─[8] 从 kb_chunks 分页读取所有分块（每页 500 条）
        │   │
        │   ├─ 如果 embedding_config 未变 → 从旧后端读取现有向量（无需重新向量化）
        │   ├─ 如果 embedding_config 变了 → 从 kb_chunks.content 重新调用 EmbeddingEngine
        │   │
        │   ├─ SSE 推送: progress 5%→90%（按页码计算）
        │   │
        │   └─ 批量写入新后端（每批 32/64/128 条）
        │
        ├─[9] SSE 推送: progress 95%,"正在验证新索引完整性..."
        │
        ├─[10] 验证：新后端文档数 == kb_chunks 总数
        │   ├─ 验证通过 → 继续
        │   └─ 验证失败 → 跳转到 [13] 回滚
        │
        ├─[11] 更新 knowledge_bases.vector_backend = "elasticsearch"
        │
        ├─[12] 清理旧后端 Collection（Chroma: 删除 collection）
        │
        ├─[13 回滚分支] 清理新后端 Index → 恢复 KB status=ready → task status=failed
        │
        ├─[14] 更新 KB status → ready, task status → completed
        │
        └─[15] SSE 推送: event=complete, progress=100%
```

### 5.3 索引重建流（分块策略变更触发）

```
PUT /api/v1/knowledge-bases/{id}/chunk-strategy
    │
    ├─[1] 校验：KB 状态为 ready（非 rebuilding/indexing）
    │
    ├─[2] 更新 KB.chunk_strategy → 新策略
    │
    ├─[3] 更新 KB.status → rebuilding
    │
    ├─[4] 创建 kb_rebuild_tasks 记录（trigger=chunk_change, status=running）
    │
    └─[5] 提交异步任务 _execute_rebuild(kb_id, tenant_id, task_id)
        │
        ▼
    后台重建执行（与 Embedding 配置变更、后端迁移共用 _execute_rebuild 核心逻辑）
        │
        ├─[6] 创建临时向量存储空间（同后端的新 Collection/Index）
        │   └─ 此时旧索引仍可读，保证重建期间搜索不中断
        │
        ├─[7] 从 kb_documents 分页读取所有文档
        │   ├─ 只处理 parse_status=parsed 的文档
        │   └─ parse_status=error 的文档跳过
        │
        ├─[8] 对每篇文档调用 ChunkingEngine.chunk(text, new_strategy)
        │
        ├─[9] SSE 推送: progress（按文档进度计算）
        │
        ├─[10] 调用 EmbeddingEngine.embed_batch(texts) → 向量化
        │
        ├─[11] 写入临时向量存储
        │
        ├─[12] 更新 kb_chunks（删除旧分块 → 插入新分块）
        │
        ├─[13] 验证：新索引文档数 == 应有文档数
        │   ├─ 通过 → 切换到新索引（替换临时 Collection 为主 Collection）
        │   └─ 失败 → 删除临时 Collection → task status=failed → KB status=error
        │
        ├─[14] 重建 BM25 索引（仅 Chroma/Milvus 后端）
        │
        ├─[15] 更新 KB：chunk_count, storage_size_bytes, status=ready
        │
        └─[16] SSE 推送: event=complete
```

### 5.4 ACL 过滤注入流（检索时）

```
检索请求到达 PipelineCompiler
    │
    ├─[1] 从请求上下文获取 user_roles（JWT 中间件注入）
    │
    ├─[2] 判断是否为 God Mode：user_roles 为空 → 返回空过滤条件
    │
    ├─[3] 根据知识库 vector_backend 获取对应的 ACLFilterBuilder 实现
    │   ├─ Chroma → ChromaACLFilterBuilder
    │   ├─ ES → ESACLFilterBuilder
    │   └─ Milvus → MilvusACLFilterBuilder
    │
    ├─[4] 调用 acl_filter_builder.build_filter(user_roles)
    │   └─ 返回后端特定的过滤条件 dict
    │
    ├─[5] 将 filter_condition 注入到 VectorStoreAdapter.search() 调用中
    │
    └─[6] 后端执行搜索时自动应用 ACL 过滤，返回用户有权限的文档子集
```

---

## 6. 测试策略

### 6.1 单元测试

| # | 测试对象 | 测试内容 |
|---|---------|---------|
| UT-3.1 | `FixedSizeChunking` | 输入固定文本，验证 chunk_size=512 时分块长度、overlap 重叠区域正确 |
| UT-3.2 | `SemanticChunking` | 输入有语义边界的文本，验证分块边界在语义断裂处而非强制截断 |
| UT-3.3 | `ParagraphChunking` | 输入多段落文本，验证按段落分隔符切分，短段落合并 |
| UT-3.4 | `HeadingChunking` | 输入 Markdown 标题文本，验证 heading_path 保留（如"§1.2.3 诊断标准"） |
| UT-3.5 | `RecursiveChunking` | 输入混合格式文本，验证按优先级列表逐级尝试分割 |
| UT-3.6 | `EmbeddingEngine` | Mock Embedding API → 验证批量 32/64/128 时请求正确拆分、返回向量维度正确 |
| UT-3.7 | `ChromaACLFilterBuilder` | 传入 ["admin","editor"] → 输出 Chroma where 条件语法正确 |
| UT-3.8 | `ESACLFilterBuilder` | 传入 ["admin","editor"] → 输出 ES filter clause 语法正确 |
| UT-3.9 | `MilvusACLFilterBuilder` | 传入 ["admin","editor"] → 输出 Milvus expr 字符串语法正确 |
| UT-3.10 | `ACLFilterBuilder` God Mode | 传入 [] 空列表 → 三个 Builder 均返回空条件（不过滤） |

### 6.2 集成测试

| # | 测试对象 | 测试内容 |
|---|---------|---------|
| IT-3.1 | 创建知识库 | POST → 验证 MySQL 记录 + 向量存储 Collection/Index 创建成功 |
| IT-3.2 | 上传 PDF 并解析 | POST → 等待异步解析完成 → GET 验证 parse_status=parsed + text_content 非空 |
| IT-3.3 | MD5 去重 | 上传同一文件两次 → 第二次返回 duplicates 引用，不创建新记录 |
| IT-3.4 | 批量上传 50 文件 | POST → 验证 50 条记录全部成功、进度正确 |
| IT-3.5 | 分块+向量化 | 上传文档 → 等待解析完成 → 验证 kb_chunks 记录数与向量存储中条目数一致 |
| IT-3.6 | 分块策略变更重建 | PUT → 等待重建完成 → 验证新分块策略生效（分块数变化） |
| IT-3.7 | Embedding 配置变更重建 | PUT → 验证向量维度变化后索引重建成功 |
| IT-3.8 | Chroma 后端搜索 | 上传文档 → 搜索 → 验证返回相关分块，score 合理 |
| IT-3.9 | ES 后端搜索 | 同 IT-3.8，ES 后端 |
| IT-3.10 | Milvus 后端搜索 | 同 IT-3.8，Milvus 后端 |
| IT-3.11 | Chroma → ES 迁移 | POST migrate → 等待完成 → 验证 ES 索引中有同等数量文档、搜索正常 |
| IT-3.12 | 迁移失败回滚 | Mock ES 写入失败 → 验证 KB status 恢复 ready、旧后端数据完好 |
| IT-3.13 | 重建期间只读 | 触发重建 → 同时发起搜索请求 → 验证旧索引仍可返回结果 |
| IT-3.14 | 重建期间禁止修改文档 | 重建中 → POST 上传文档 → 409 Conflict |
| IT-3.15 | 文档 ACL 过滤（Chroma） | 上传 2 个文档（一个 inherit，一个 restricted to admin） → 以 editor 角色搜索 → 仅返回 inherit 文档 |
| IT-3.16 | 文档 ACL 过滤（三种后端一致） | 同一知识库、同一用户 → Chroma/ES/Milvus 三种后端返回相同文档子集 |
| IT-3.17 | 删除被引用知识库 | DELETE → 409 + 列出引用管道名 |
| IT-3.18 | 删除知识库（force） | DELETE?force=true → 级联删除所有文档/分块/向量/BM25 |
| IT-3.19 | 解析失败重试 | Mock 解析器抛异常 → 验证自动重试 1 次 → parse_status=error |
| IT-3.20 | 重新解析 | POST reparse → 验证重解析+重新分块+重新向量化 |
| IT-3.21 | SSE 进度推送 | 触发重建 → 建立 SSE 连接 → 验证收到 progress/complete 事件 |
| IT-3.22 | 分块预览 | GET chunk-preview?doc_id=xxx → 验证返回正确分块数+内容片段 |
| IT-3.23 | 租户隔离 | 租户 A 上传文档 → 租户 B 搜索同名 KB → 返回空结果 |

### 6.3 关键测试场景（≥ 10）

1. **TS-3.1 — 端到端完整链路**：创建知识库（Chroma）→ 上传 PDF → 等待解析完成 → 搜索验证 → 修改分块策略 → 重建完成 → 搜索验证新策略生效
2. **TS-3.2 — 多后端平等能力**：同一文档集分别导入 Chroma/ES/Milvus 三个知识库 → 同一查询 → 验证三后端返回结果语义一致（top-10 重叠率 ≥ 80%）
3. **TS-3.3 — 批量上传极限**：50 个文件（5 种格式各 10 个）同时上传 → 验证全部解析成功、无丢块、无重复
4. **TS-3.4 — 大文档极限**：上传 50MB PDF（约 2000 页）→ 解析时长 ≤ 5 分钟 → 分块数 ≥ 10000 → 全部向量化成功
5. **TS-3.5 — 损坏文件容错**：批量上传含 2 个损坏 PDF + 1 个格式不匹配文件 → 验证坏文件标记 error、好文件正常解析
6. **TS-3.6 — 迁移幂等性**：Chroma → ES 迁移 → 完成后再次请求迁移到 ES → 400 "已使用此后端"
7. **TS-3.7 — 迁移回滚原子性**：Chroma → ES 迁移 → Mock ES 写入中途失败 → 旧 Chroma 数据完好、KB status=error、task status=failed
8. **TS-3.8 — 并发重建互斥**：同时发起分块策略变更 + Embedding 配置变更 → 第一个成功创建重建任务，第二个 409 Conflict
9. **TS-3.9 — 重建期间搜索可用**：1200 文档知识库重建中 → 连续 50 次搜索请求 → 全部成功返回，响应耗时 ≤ 重建前的 2x
10. **TS-3.10 — 权限一致性**：同一知识库（2 个文档：inherit + restricted to admin）→ admin 搜索返回 2 个，editor 搜索返回 1 个（仅 inherit）
11. **TS-3.11 — 大型迁移不丢数据**：10000 文档 Chroma → ES 迁移 → 迁移后 ES 索引文档数 == kb_chunks 记录数 → 随机抽样 100 篇搜索验证
12. **TS-3.12 — 分块预览即时性**：上传 2000 页文档 → 请求分块预览 → 3 秒内返回前 10 块（不需要全量分块，流式处理）
13. **TS-3.13 — SSE 断线重连**：SSE 连接 → 断开 5 秒 → 重连 → 推送当前进度（而非从 0% 开始）
14. **TS-3.14 — 知识库删除级联清理**：知识库含 500 文档+50000 分块 → 删除 → Chroma Collection 不存在、BM25 目录不存在、MySQL 中 kb_* 三表无残留

---

## 7. 验收标准映射

| 验收标准 | 描述 | 映射测试 |
|---------|------|---------|
| **AC-3.1** | 创建知识库时三种后端均可选，创建后对应 Collection/Index 成功生成 | IT-3.1（覆盖 Chroma），IT-3.8/3.9/3.10（覆盖 ES/Milvus 搜索验证） |
| **AC-3.2** | 上传 PDF/TXT/Markdown/HTML/EPUB 文档均正确解析为文本 | IT-3.2（PDF），TS-3.3（5 格式全覆盖） |
| **AC-3.3** | 批量拖拽上传 50 个文件全部成功，进度实时更新 | IT-3.4，TS-3.3 |
| **AC-3.4** | 上传已存在的文档（MD5 相同）→ 返回已存在引用，不创建重复 | IT-3.3 |
| **AC-3.5** | 修改分块策略后自动触发全量索引重建，重建完成后新分块策略生效 | IT-3.6，TS-3.1 |
| **AC-3.6** | 修改 Embedding 配置后自动触发全量索引重建 | IT-3.7 |
| **AC-3.7** | 向量后端迁移（Chroma → ES）→ 迁移完成后可正常检索 | IT-3.11，TS-3.6 |
| **AC-3.8** | 迁移失败 → 回滚到旧后端，知识库状态恢复 ready | IT-3.12，TS-3.7 |
| **AC-3.9** | 重建期间知识库可正常读取（用旧索引），不可修改文档 | IT-3.13，IT-3.14，TS-3.9 |
| **AC-3.10** | ES 后端的知识库，BM25 检索节点自动使用 ES 内置 BM25 | IT-3.9（验证 ES 全文搜索结果包含非向量匹配的文档） |
| **AC-3.11** | Chroma/Milvus 后端的知识库，BM25 检索使用独立索引 | IT-3.8（Chroma）+ BM25 独立索引文件存在验证 |
| **AC-3.12** | 删除被管道引用的知识库 → 警告并阻止，列出引用管道名称 | IT-3.17 |
| **AC-3.13** | 分块预览正确展示某文档在当前策略下的分块结果 | IT-3.22，TS-3.12 |
| **AC-3.14** | 文档权限设置为 restricted 时，doc_acl 不能超出知识库 visible_roles 范围 | IT-3.15（验证 editor 角色受限），UT-3.7/3.8/3.9（Builder 逻辑正确） |
| **AC-3.15** | 重建进度 SSE 实时推送，前端显示百分比和预计剩余时间 | IT-3.21，TS-3.13 |

---

## 附录 A：BM25 独立索引规范

### A.1 触发条件

向量后端为 `chroma` 或 `milvus` 时必须维护独立 BM25 索引。后端为 `elasticsearch` 时不维护（使用 ES 内置 BM25）。

### A.2 索引结构

```
storage/bm25/{tenant_id}/{kb_id}/
├── index.json       # BM25Okapi 序列化索引
├── id_map.json      # 内部 ID → chunk_id 映射
└── metadata.json    # 创建时间、文档数、参数配置
```

### A.3 索引字段

| 字段 | 类型 | 来源 | 说明 |
|------|------|------|------|
| `chunk_id` | str | kb_chunks.id | 主键 |
| `doc_id` | str | kb_chunks.doc_id | 所属文档 |
| `content` | str | kb_chunks.content | 分词后的文本（jieba 中文分词） |
| `kb_id` | str | kb_chunks.kb_id | 所属知识库 |

### A.4 更新策略

- **增量更新**：文档上传/删除时，通过 `BM25IndexManager.add_chunks()` / `.remove_chunks()` 增量修改
- **全量重建**：索引重建时，通过 `BM25IndexManager.rebuild_from_chunks(chunks: list[KbChunk])` 全量重建
- **锁控制**：单知识库单写锁，避免并发修改导致索引损坏

### A.5 参数

- `k1`: 1.5（词频饱和度控制）
- `b`: 0.75（文档长度归一化）
- 以上参数为系统固定默认值，不接受用户配置

### A.6 接口

```python
class BM25IndexManager:
    """BM25 独立索引管理器"""

    def __init__(self, storage_root: str = "storage/bm25"):
        ...

    async def add_chunks(self, kb_id: str, tenant_id: str, chunks: list[dict]) -> None:
        """向索引添加分块"""
        ...

    async def remove_chunks(self, kb_id: str, tenant_id: str, chunk_ids: list[str]) -> None:
        """从索引移除分块"""
        ...

    async def search(self, kb_id: str, tenant_id: str, query: str, top_k: int = 10) -> list[dict]:
        """BM25 关键词检索"""
        ...

    async def rebuild(self, kb_id: str, tenant_id: str, chunks: list[dict]) -> None:
        """全量重建索引"""
        ...

    async def delete_index(self, kb_id: str, tenant_id: str) -> None:
        """删除索引目录"""
        ...

    async def get_info(self, kb_id: str, tenant_id: str) -> dict:
        """获取索引信息（文档数、创建时间）"""
        ...
```

---

## 附录 B：ChunkingEngine 完整接口

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Chunk:
    """分块结果数据结构"""
    content: str                              # 分块文本
    token_count: int                          # Token 估算数量
    metadata: dict[str, Any] = field(default_factory=dict)  # 源文档元数据 + 分块位置信息


class BaseChunkingStrategy(ABC):
    """分块策略抽象基类"""

    @abstractmethod
    async def chunk(self, text: str, config: dict) -> list[Chunk]:
        """对文本执行分块"""
        ...

    def _estimate_tokens(self, text: str) -> int:
        """Token 数量估算（中文：字符数 × 1.5，英文：单词数 × 1.3）"""
        ...


class FixedSizeChunking(BaseChunkingStrategy):
    """固定大小分块

    参数：chunk_size, overlap, separator, min_chunk_size, max_chunk_size, chunk_metadata
    """
    async def chunk(self, text: str, config: dict) -> list[Chunk]:
        ...


class SemanticChunking(BaseChunkingStrategy):
    """语义分块

    参数：similarity_threshold, min_chunk_size, max_chunk_size, embedding_model, chunk_metadata
    原理：计算相邻句子的 embedding 余弦相似度，在相似度低于阈值处切分。
    """
    async def chunk(self, text: str, config: dict) -> list[Chunk]:
        ...


class ParagraphChunking(BaseChunkingStrategy):
    """按段落分块

    参数：paragraph_separator_regex, max_chunk_size, min_sentences_per_chunk, chunk_metadata
    原理：按正则分割段落，短段落合并到相邻块直到满足最小句子数。
    """
    async def chunk(self, text: str, config: dict) -> list[Chunk]:
        ...


class HeadingChunking(BaseChunkingStrategy):
    """按标题层级分块

    参数：heading_levels, preserve_heading_path, max_chunk_size, chunk_metadata
    原理：识别 Markdown/HTML 标题层级（H1/H2/H3），以标题为分块边界。保留标题路径。
    """
    async def chunk(self, text: str, config: dict) -> list[Chunk]:
        ...


class RecursiveChunking(BaseChunkingStrategy):
    """递归分块

    参数：separator_priority_list, min_chunk_size, max_chunk_size, chunk_metadata
    原理：按优先级列表递归尝试分割：先双换行 → 单换行 → 句号 → 空格 → 字符。
          对无法满足 max_chunk_size 的块递归调用下一个分隔符。
    """
    async def chunk(self, text: str, config: dict) -> list[Chunk]:
        ...


class ChunkingEngine:
    """分块引擎门面

    根据策略类型选择对应的 ChunkingStrategy 实现。
    """

    def __init__(self):
        self._strategies: dict[str, BaseChunkingStrategy] = {
            "fixed_size": FixedSizeChunking(),
            "semantic": SemanticChunking(),
            "paragraph": ParagraphChunking(),
            "heading": HeadingChunking(),
            "recursive": RecursiveChunking(),
        }

    async def chunk(self, text: str, strategy_config: dict) -> list[Chunk]:
        strategy_type = strategy_config.get("type", "fixed_size")
        strategy = self._strategies.get(strategy_type)
        if strategy is None:
            raise ValueError(f"不支持的分块策略: {strategy_type}")
        return await strategy.chunk(text, strategy_config)

    async def preview(self, text: str, strategy_config: dict, limit: int = 10) -> tuple[int, list[Chunk]]:
        """预览分块结果：返回总分块数 + 前 N 块"""
        chunks = await self.chunk(text, strategy_config)
        return len(chunks), chunks[:limit]
```

---

## 附录 C：前端状态管理要点（仅供参考）

### C.1 知识库列表页状态

- 使用 React Query 管理 `GET /knowledge-bases` 缓存（staleTime: 30s）
- 筛选条件变化时自动重取（搜索 debounce 300ms）
- 后端/状态/可见性筛选器作为 query params，支持 URL 分享

### C.2 文档上传状态

- 使用 Zustand store 管理上传进度：`{ total: 50, completed: 23, inProgress: 5, failed: 2 }`
- XMLHttpRequest 或 fetch ReadableStream 读取上传进度
- 上传完成后 invalidate `GET /knowledge-bases/{id}` 和 `GET /knowledge-bases/{id}/documents` 缓存

### C.3 重建进度 SSE

- 使用 EventSource API 连接 `/api/v1/knowledge-bases/{id}/rebuild/status`
- 解析事件 `progress`（更新进度条百分比+文本）和 `complete`（刷新 KB 详情）
- 心跳检测：15 秒无事件 → 重连
