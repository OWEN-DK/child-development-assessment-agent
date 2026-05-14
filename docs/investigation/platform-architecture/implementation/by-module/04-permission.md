# 04 — 权限与多租户：实现规格

> **定位**：平台超管、租户管理、双层权限控制（库级别 + 文档级别）的完整实现规格。
> **上游需求**：[04-permission-and-multi-tenancy.md](../../requirements/04-permission-and-multi-tenancy.md)
> **横切约束**：权限在所有检索流程中强制注入，不可绕过。

---

## 1. API 契约

所有接口返回统一格式：

```json
// 成功
{ "code": 0, "message": "success", "data": {...} }

// 错误
{ "code": <number>, "message": "<msg>", "error_code": "<STR>", "details": {...} }
```

---

### 1.1 超管 API（前缀 `/api/v1/admin`）

所有端点要求 JWT 中无 `tenant_id`（即超管身份），由 `AuthMiddleware` 校验。

#### `POST /tenants` — 创建租户（含初始管理员）

**Request Body:**

```json
{
  "name": "仁和医院",
  "slug": "renhe",
  "initial_admin": {
    "username": "zhang",
    "email": "zhang@renhe.com",
    "password": "securePassword123"
  },
  "resource_limits": {
    "kb_max": 10,
    "doc_max": 1000000,
    "user_max": 100,
    "storage_gb_max": 50,
    "search_qps_max": 50
  }
}
```

**Response (201):**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "tenant": {
      "id": "uuid-t-001",
      "name": "仁和医院",
      "slug": "renhe",
      "status": "active",
      "resource_limits": {
        "kb_max": 10,
        "doc_max": 1000000,
        "user_max": 100,
        "storage_gb_max": 50,
        "search_qps_max": 50
      },
      "created_at": "2026-05-14T10:00:00Z",
      "updated_at": "2026-05-14T10:00:00Z"
    },
    "admin_user": {
      "id": "uuid-u-001",
      "username": "zhang",
      "email": "zhang@renhe.com",
      "tenant_id": "uuid-t-001",
      "status": "active"
    }
  }
}
```

**Errors:**
- `409 TENANT_SLUG_EXISTS` — slug 已存在

---

#### `GET /tenants` — 租户列表

**Query Parameters:**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `status` | string | 否 | 筛选：`active` \| `disabled` \| `archived` \| `deleted`。不传返回全部 |
| `page` | int | 否 | 页码，默认 1 |
| `page_size` | int | 否 | 每页条数，默认 20，最大 100 |

**Response (200):**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "id": "uuid-t-001",
        "name": "仁和医院",
        "slug": "renhe",
        "status": "active",
        "user_count": 26,
        "storage_used_gb": 2.3,
        "resource_limits": {
          "storage_gb_max": 50
        },
        "created_at": "2026-05-14T10:00:00Z"
      }
    ],
    "total": 3,
    "page": 1,
    "page_size": 20
  }
}
```

---

#### `GET /tenants/{id}` — 租户详情（含统计）

**Response (200):**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "uuid-t-001",
    "name": "仁和医院",
    "slug": "renhe",
    "status": "active",
    "resource_limits": {
      "kb_max": 10,
      "doc_max": 1000000,
      "user_max": 100,
      "storage_gb_max": 50,
      "search_qps_max": 50
    },
    "stats": {
      "kb_count": 5,
      "doc_count": 12500,
      "pipeline_count": 3,
      "user_count": 26,
      "storage_used_gb": 2.3,
      "search_30d_count": 12300,
      "avg_latency_ms": 1800,
      "error_rate": 0.003
    },
    "created_at": "2026-05-14T10:00:00Z",
    "updated_at": "2026-05-14T10:00:00Z"
  }
}
```

**Errors:**
- `404 TENANT_NOT_FOUND`

---

#### `PUT /tenants/{id}` — 更新租户（启用/停用/调整配额）

**Request Body（部分更新，只传变更字段）:**

```json
{
  "name": "仁和医院（第一分院）",
  "status": "disabled",
  "resource_limits": {
    "kb_max": 20,
    "user_max": 200
  }
}
```

**Response (200):** 返回更新后的租户完整对象

**Errors:**
- `404 TENANT_NOT_FOUND`
- `400 CANNOT_ACTIVATE_DELETED` — 已删除租户不可直接启用，需先 restore

---

#### `PUT /tenants/{id}/archive` — 归档租户

无请求体。租户状态 `active` → `archived`。

**Response (200):**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "uuid-t-001",
    "status": "archived",
    "changed_at": "2026-05-14T10:00:00Z"
  }
}
```

**Errors:**
- `404 TENANT_NOT_FOUND`
- `400 TENANT_NOT_ACTIVE` — 只能归档 active 状态的租户

---

#### `PUT /tenants/{id}/restore` — 恢复已归档或已软删除的租户

无请求体。`archived`/`deleted` → `active`。

**Response (200):** 同 archive 格式

**Errors:**
- `404 TENANT_NOT_FOUND`
- `400 TENANT_CANNOT_RESTORE` — 状态不是 archived 或 deleted

---

#### `DELETE /tenants/{id}` — 软删除租户

**软删除流程**：`deleted_at` 标记 → 30 天保留期 → 自动物理清理。物理清理前生成数据导出快照（`tenant_deletion_snapshots` 表），快照保留 90 天。

**Request Body:**

```json
{
  "confirm_slug": "renhe"
}
```

**Response (200):**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "uuid-t-001",
    "status": "deleted",
    "deleted_at": "2026-05-14T10:00:00Z",
    "retention_expires_at": "2026-06-13T10:00:00Z",
    "snapshot_id": "uuid-snap-001"
  }
}
```

**Errors:**
- `404 TENANT_NOT_FOUND`
- `400 TENANT_SLUG_MISMATCH` — confirm_slug 不匹配
- `400 TENANT_ALREADY_DELETED`

---

#### `GET /tenants/{id}/users` — 租户用户列表

**Query Parameters:**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `page` | int | 否 | 默认 1 |
| `page_size` | int | 否 | 默认 20 |
| `status` | string | 否 | `active` \| `disabled` |
| `role_id` | string | 否 | 按角色筛选 |

**Response (200):**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "id": "uuid-u-001",
        "username": "zhang",
        "email": "zhang@renhe.com",
        "status": "active",
        "roles": [
          { "id": "uuid-r-001", "name": "管理员", "slug": "admin" }
        ],
        "created_at": "2026-05-14T10:00:00Z"
      }
    ],
    "total": 26,
    "page": 1,
    "page_size": 20
  }
}
```

---

#### `POST /tenants/{id}/impersonate` — 超管进入租户上下文（God Mode）

**Request Body:**

```json
{}
```

**Response (200):**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "impersonate_token": "eyJ...god_mode_jwt...",
    "tenant_id": "uuid-t-001",
    "tenant_name": "仁和医院",
    "session_expires_at": "2026-05-14T10:30:00Z",
    "god_mode_session_id": "uuid-god-001"
  }
}
```

**行为说明：**
- 返回一个临时 JWT，`claims` 中携带 `tenant_id`、`god_mode: true`、`god_mode_session_id`、`roles: ["_god_mode"]`
- Token 有效期 30 分钟
- 后端写入 `god_mode_audit_log` 记录 `action=enter`
- 若已有超管在该租户 God Mode 中，返回 `409 GOD_MODE_CONCURRENT`（同一时间只允许一个超管进入同一租户）

**Errors:**
- `404 TENANT_NOT_FOUND`
- `400 TENANT_NOT_ACTIVE` — 停用/归档/已删除的租户不可进入
- `409 GOD_MODE_CONCURRENT` — 已有其他超管在此租户 God Mode 中

---

#### `POST /tenants/{id}/impersonate/extend` — 续期 God Mode

**Request Body:**

```json
{
  "god_mode_session_id": "uuid-god-001"
}
```

**Response (200):**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "impersonate_token": "eyJ...new_god_mode_jwt...",
    "session_expires_at": "2026-05-14T11:00:00Z"
  }
}
```

**约束：** 仅允许续期一次（+30 分钟），二次续期返回 `400 GOD_MODE_EXTEND_LIMIT`

---

#### `DELETE /tenants/{id}/impersonate` — 退出 God Mode

**Request Body:**

```json
{
  "god_mode_session_id": "uuid-god-001"
}
```

**Response (200):**

```json
{
  "code": 0,
  "message": "success",
  "data": null
}
```

后端写入 `god_mode_audit_log` 记录 `action=exit`。

---

#### `GET /tenants/{id}/god-mode-log` — God Mode 操作审计日志

**Query Parameters:**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `page` | int | 否 | 默认 1 |
| `page_size` | int | 否 | 默认 50 |
| `session_id` | string | 否 | 按会话筛选 |
| `action` | string | 否 | `enter` \| `exit` \| `write` \| `read` |

**Response (200):**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "id": "uuid-god-log-001",
        "tenant_id": "uuid-t-001",
        "actor_id": "uuid-super-001",
        "action": "write",
        "target_type": "document",
        "target_id": "uuid-doc-001",
        "details": "删除文档「康复训练方案 v2」",
        "session_started_at": "2026-05-14T10:00:00Z",
        "created_at": "2026-05-14T10:12:00Z"
      }
    ],
    "total": 5,
    "page": 1,
    "page_size": 50
  }
}
```

---

### 1.2 租户内 API（前缀 `/api/v1`）

所有端点要求 JWT 中携带合法 `tenant_id`。由 `AuthMiddleware` 校验。

---

#### `POST /auth/login` — 登录

**Request Body:**

```json
{
  "slug": "renhe",
  "username": "zhang",
  "password": "securePassword123"
}
```

**Response (200):**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "access_token": "eyJ...jwt...",
    "token_type": "bearer",
    "expires_at": "2026-05-15T10:00:00Z",
    "user": {
      "id": "uuid-u-001",
      "username": "zhang",
      "email": "zhang@renhe.com",
      "tenant_id": "uuid-t-001",
      "tenant_name": "仁和医院",
      "roles": [
        { "id": "uuid-r-001", "name": "管理员", "slug": "admin" }
      ]
    }
  }
}
```

**JWT Claims 内容:**

```json
{
  "sub": "uuid-u-001",
  "tenant_id": "uuid-t-001",
  "tenant_slug": "renhe",
  "roles": ["admin"],
  "permissions": ["kb:read", "kb:write", "kb:delete", "kb:manage_acl", "pipeline:read", "pipeline:write", "pipeline:publish", "search:execute", "search:stream", "eval:read", "eval:write", "system:config", "system:monitor"],
  "username": "zhang",
  "god_mode": false,
  "god_mode_session_id": null,
  "iat": 1715688000,
  "exp": 1715774400
}
```

**Errors:**
- `401 INVALID_CREDENTIALS`
- `403 TENANT_DISABLED` — 租户已停用
- `403 TENANT_ARCHIVED` — 租户已归档
- `403 USER_DISABLED` — 用户已被禁用
- `404 TENANT_NOT_FOUND`

---

#### `GET /auth/refresh` — 刷新 Token

**Request:** Bearer Token（可接受已过期但未超过刷新窗口的 Token）

**Response (200):**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "access_token": "eyJ...new_jwt...",
    "expires_at": "2026-05-15T11:00:00Z"
  }
}
```

---

#### `POST /auth/switch-role` — 角色视角切换

**Request Body:**

```json
{
  "role_slug": "viewer"
}
```

**Response (200):**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "access_token": "eyJ...switched_jwt...",
    "simulated_role": {
      "slug": "viewer",
      "permissions": ["kb:read", "search:execute"]
    }
  }
}
```

**说明：**
- 不改变实际用户身份，新的 JWT 中保留原始 `user_id`/`username`，但 `roles`/`permissions` 替换为所选角色的权限集
- JWT claims 中 `simulated_role` 标记为 `viewer`
- 选择 `__original__` 恢复原始权限

**校验规则：**
- 所选角色必须属于同一租户
- 所选角色权限集必须是当前用户权限集的子集（不能越级模拟）
- 超管 God Mode 中不可切换角色

---

#### `GET /users` — 用户列表

**Query Parameters:**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `page` | int | 否 | 默认 1 |
| `page_size` | int | 否 | 默认 20 |
| `status` | string | 否 | `active` \| `disabled` |
| `role_id` | string | 否 | 按角色筛选 |

**Response (200):**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "id": "uuid-u-001",
        "username": "zhang",
        "email": "zhang@renhe.com",
        "status": "active",
        "roles": [
          { "id": "uuid-r-001", "name": "管理员", "slug": "admin" }
        ],
        "created_at": "2026-05-14T10:00:00Z"
      }
    ],
    "total": 26,
    "page": 1,
    "page_size": 20
  }
}
```

**权限要求：** `system:config` 或 `admin` 角色

---

#### `POST /users/invite` — 邀请用户

**Request Body:**

```json
{
  "email": "li@renhe.com",
  "role_ids": ["uuid-r-003", "uuid-r-004"]
}
```

**Response (201):**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "invitation": {
      "id": "uuid-inv-001",
      "email": "li@renhe.com",
      "roles": ["普通医生", "药师"],
      "token": "inv-token-abc123",
      "invite_url": "https://app.example.com/invite?token=inv-token-abc123",
      "expires_at": "2026-05-15T10:00:00Z",
      "created_by": "uuid-u-001"
    }
  }
}
```

**权限要求：** `system:config` 或 `admin` 角色
**校验：** 分配的角色权限不能超出邀请者自身权限

**Errors:**
- `400 EMAIL_ALREADY_INVITED` — 该邮箱已有未过期的邀请
- `400 EMAIL_ALREADY_MEMBER` — 该邮箱已是租户成员
- `400 ROLE_PERMISSION_EXCEEDS` — 所选角色权限超出邀请者权限
- `400 TENANT_USER_LIMIT_REACHED` — 已达用户数上限

---

#### `POST /users/accept-invitation` — 接受邀请（设置密码）

**Request Body:**

```json
{
  "token": "inv-token-abc123",
  "username": "li",
  "password": "liPassword456"
}
```

**Response (200):**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "user": {
      "id": "uuid-u-002",
      "username": "li",
      "email": "li@renhe.com",
      "tenant_id": "uuid-t-001",
      "status": "active"
    },
    "access_token": "eyJ...jwt..."
  }
}
```

**Errors:**
- `400 INVITATION_EXPIRED`
- `400 INVITATION_ALREADY_ACCEPTED`
- `404 INVITATION_NOT_FOUND`

---

#### `PUT /users/{id}` — 更新用户（角色分配、禁用）

**Request Body（部分更新）:**

```json
{
  "status": "disabled",
  "role_ids": ["uuid-r-003"]
}
```

**Response (200):** 返回更新后的用户对象

**权限要求：** `system:config` 或 `admin` 角色
**校验：** 不能禁用自己；分配的角色权限不能超出操作者自身权限

**Errors:**
- `404 USER_NOT_FOUND`
- `400 CANNOT_DISABLE_SELF`
- `400 ROLE_PERMISSION_EXCEEDS`

---

#### `DELETE /users/{id}` — 删除用户

**Response (200):**

```json
{
  "code": 0,
  "message": "success",
  "data": null
}
```

**权限要求：** `system:config` 或 `admin` 角色
**校验：** 不能删除自己；不能删除租户最后一个 admin

**Errors:**
- `404 USER_NOT_FOUND`
- `400 CANNOT_DELETE_SELF`
- `400 CANNOT_DELETE_LAST_ADMIN`

---

#### `GET /roles` — 角色列表

**Response (200):**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "id": "uuid-r-001",
        "name": "管理员",
        "slug": "admin",
        "is_builtin": true,
        "permissions": ["kb:read", "kb:write", "kb:delete", "kb:manage_acl", "pipeline:read", "pipeline:write", "pipeline:publish", "search:execute", "search:stream", "eval:read", "eval:write", "system:config", "system:monitor"],
        "user_count": 2,
        "created_at": "2026-05-14T10:00:00Z"
      },
      {
        "id": "uuid-r-002",
        "name": "编辑者",
        "slug": "editor",
        "is_builtin": true,
        "permissions": ["kb:read", "kb:write", "kb:delete", "pipeline:read", "pipeline:write", "search:execute", "eval:read", "eval:write"],
        "user_count": 5,
        "created_at": "2026-05-14T10:00:00Z"
      },
      {
        "id": "uuid-r-003",
        "name": "查看者",
        "slug": "viewer",
        "is_builtin": true,
        "permissions": ["kb:read", "search:execute"],
        "user_count": 19,
        "created_at": "2026-05-14T10:00:00Z"
      },
      {
        "id": "uuid-r-004",
        "name": "普通医生",
        "slug": "doctor",
        "is_builtin": false,
        "permissions": ["kb:read", "search:execute", "eval:read"],
        "user_count": 15,
        "created_at": "2026-05-14T10:00:00Z"
      }
    ],
    "total": 4
  }
}
```

---

#### `POST /roles` — 创建自定义角色

**Request Body:**

```json
{
  "name": "药师",
  "slug": "pharmacist",
  "permissions": ["kb:read", "search:execute"]
}
```

**Response (201):** 返回创建的角色对象

**权限要求：** `system:config` 或 `admin` 角色
**校验规则：**
- `slug` 不允许与内置角色重名
- `permissions` 必须是创建者自身权限集的子集
- `permissions` 中每个值必须在预定义的权限列表中

**Errors:**
- `400 ROLE_SLUG_EXISTS`
- `400 ROLE_PERMISSION_EXCEEDS`
- `400 INVALID_PERMISSION` — permissions 中包含未知权限

---

#### `PUT /roles/{id}` — 更新角色权限

**Request Body（部分更新）:**

```json
{
  "name": "高级药师",
  "permissions": ["kb:read", "search:execute", "eval:read"]
}
```

**Response (200):** 返回更新后的角色对象

**权限要求：** `system:config` 或 `admin` 角色
**校验规则：**
- 不能修改内置角色（`is_builtin=true`）的 `permissions`
- 新权限集不能超出操作者自身权限

**Errors:**
- `404 ROLE_NOT_FOUND`
- `400 CANNOT_MODIFY_BUILTIN_ROLE`
- `400 ROLE_PERMISSION_EXCEEDS`

---

#### `DELETE /roles/{id}` — 删除角色

**Response (200):**

```json
{
  "code": 0,
  "message": "success",
  "data": null
}
```

**权限要求：** `system:config` 或 `admin` 角色
**校验规则：**
- 不能删除内置角色
- 不能删除仍有用户引用的角色（需先解除所有用户-角色关联）

**Errors:**
- `404 ROLE_NOT_FOUND`
- `400 CANNOT_DELETE_BUILTIN_ROLE`
- `400 ROLE_HAS_USERS` — 仍有用户引用此角色

---

#### `GET /permissions` — 可用权限列表

**Response (200):**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "permissions": [
      { "slug": "kb:read", "description": "查看知识库和文档", "group": "知识库" },
      { "slug": "kb:write", "description": "创建和编辑知识库、上传文档", "group": "知识库" },
      { "slug": "kb:delete", "description": "删除知识库和文档", "group": "知识库" },
      { "slug": "kb:manage_acl", "description": "管理知识库和文档的访问权限", "group": "知识库" },
      { "slug": "pipeline:read", "description": "查看管道配置", "group": "管道" },
      { "slug": "pipeline:write", "description": "创建和编辑管道", "group": "管道" },
      { "slug": "pipeline:publish", "description": "发布管道到生产环境", "group": "管道" },
      { "slug": "search:execute", "description": "执行搜索", "group": "搜索" },
      { "slug": "search:stream", "description": "使用流式搜索", "group": "搜索" },
      { "slug": "eval:read", "description": "查看评估结果和报告", "group": "评估" },
      { "slug": "eval:write", "description": "创建和运行评估", "group": "评估" },
      { "slug": "system:config", "description": "管理系统配置", "group": "系统" },
      { "slug": "system:monitor", "description": "查看监控数据", "group": "系统" }
    ]
  }
}
```

**权限列表定义在 `backend/src/config/modules/permissions.py` 中，作为集中配置，禁止硬编码到控制器或前端组件。**

---

### 1.3 God Mode 内部 API（前缀 `/api/v1`，要求 JWT 携带 `god_mode: true`）

God Mode 下，所有业务接口正常访问，但额外适用以下规则：
- **写操作需要二次确认**：前端在 PUT/POST/DELETE 请求的 Header 中附加 `X-God-Mode-Confirm: true`。后端在 God Mode 写操作时检查此 Header，缺少则返回 `412 GOD_MODE_WRITE_CONFIRM_REQUIRED`。
- **所有操作写入审计**：后端中间件自动记录到 `god_mode_audit_log`。

**二次确认弹窗（前端规格）：**

```
┌───────────────────────────────────────────────────┐
│  ⚠️ God Mode 操作确认                              │
│                                                   │
│  当前以超管身份操作仁和医院。此操作不可撤销。           │
│                                                   │
│  操作类型: 删除文档                                │
│  目标资源: 「康复训练方案 v2」                        │
│                                                   │
│  [取消]  [确认操作]                                 │
└───────────────────────────────────────────────────┘
```

---

## 2. 数据库 DDL

以下为 MySQL 5.7 完整建表语句，遵循项目现有规范：
- 引擎 InnoDB，字符集 utf8mb4，校对规则 utf8mb4_unicode_ci
- 无外键约束，应用层保证一致性
- JSON 字段使用 `json` 类型
- 主键统一 `varchar(36)`（UUID）

```sql
-- =============================================
-- 权限与多租户模块 DDL
-- 追加到 .ai/full_init_script_mysql57.sql
-- =============================================

-- ----------------------------
-- 租户表
-- ----------------------------
DROP TABLE IF EXISTS `tenants`;

CREATE TABLE `tenants` (
    `id` varchar(36) NOT NULL COMMENT '租户ID (UUID)',
    `name` varchar(255) NOT NULL COMMENT '租户显示名称',
    `slug` varchar(100) NOT NULL COMMENT '租户唯一标识，用于存储路径和 API 上下文',
    `status` enum('active','disabled','archived','deleted') NOT NULL DEFAULT 'active' COMMENT '租户状态',
    `resource_limits` json NOT NULL COMMENT '资源配额限制 JSON',
    `deleted_at` datetime DEFAULT NULL COMMENT '软删除时间',
    `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_tenants_slug` (`slug`),
    KEY `idx_tenants_status` (`status`),
    KEY `idx_tenants_deleted_at` (`deleted_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='租户表';

-- ----------------------------
-- 用户表
-- ----------------------------
DROP TABLE IF EXISTS `users`;

CREATE TABLE `users` (
    `id` varchar(36) NOT NULL COMMENT '用户ID (UUID)',
    `tenant_id` varchar(36) DEFAULT NULL COMMENT '租户ID，NULL=超管',
    `username` varchar(100) NOT NULL COMMENT '用户名',
    `password_hash` varchar(255) NOT NULL COMMENT '密码哈希 (bcrypt)',
    `email` varchar(255) NOT NULL COMMENT '邮箱',
    `status` enum('active','disabled') NOT NULL DEFAULT 'active' COMMENT '用户状态',
    `deleted_at` datetime DEFAULT NULL COMMENT '软删除时间',
    `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_users_tenant_email` (`tenant_id`, `email`),
    UNIQUE KEY `uk_users_tenant_username` (`tenant_id`, `username`),
    KEY `idx_users_tenant_id` (`tenant_id`),
    KEY `idx_users_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户表';

-- ----------------------------
-- 角色表
-- ----------------------------
DROP TABLE IF EXISTS `roles`;

CREATE TABLE `roles` (
    `id` varchar(36) NOT NULL COMMENT '角色ID (UUID)',
    `tenant_id` varchar(36) NOT NULL COMMENT '所属租户ID',
    `name` varchar(100) NOT NULL COMMENT '角色显示名称',
    `slug` varchar(100) NOT NULL COMMENT '角色唯一标识 (admin/editor/viewer 或自定义)',
    `permissions` json NOT NULL COMMENT '权限列表 JSON 数组',
    `is_builtin` tinyint(1) NOT NULL DEFAULT 0 COMMENT '是否为系统内置角色 (不可修改权限集)',
    `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_roles_tenant_slug` (`tenant_id`, `slug`),
    KEY `idx_roles_tenant_id` (`tenant_id`),
    KEY `idx_roles_is_builtin` (`is_builtin`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='角色表';

-- ----------------------------
-- 用户角色关联表
-- ----------------------------
DROP TABLE IF EXISTS `user_roles`;

CREATE TABLE `user_roles` (
    `user_id` varchar(36) NOT NULL COMMENT '用户ID',
    `role_id` varchar(36) NOT NULL COMMENT '角色ID',
    PRIMARY KEY (`user_id`, `role_id`),
    KEY `idx_user_roles_user_id` (`user_id`),
    KEY `idx_user_roles_role_id` (`role_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户角色关联表';

-- ----------------------------
-- 用户邀请表
-- ----------------------------
DROP TABLE IF EXISTS `user_invitations`;

CREATE TABLE `user_invitations` (
    `id` varchar(36) NOT NULL COMMENT '邀请ID (UUID)',
    `tenant_id` varchar(36) NOT NULL COMMENT '所属租户ID',
    `email` varchar(255) NOT NULL COMMENT '被邀请人邮箱',
    `roles` json NOT NULL COMMENT '分配的角色ID列表 JSON 数组',
    `token` varchar(128) NOT NULL COMMENT '一次性邀请 Token',
    `expires_at` datetime NOT NULL COMMENT '过期时间 (默认 24h)',
    `accepted_at` datetime DEFAULT NULL COMMENT '接受时间',
    `created_by` varchar(36) NOT NULL COMMENT '邀请人用户ID',
    `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_invitations_token` (`token`),
    KEY `idx_invitations_tenant_id` (`tenant_id`),
    KEY `idx_invitations_email` (`email`),
    KEY `idx_invitations_expires_at` (`expires_at`),
    KEY `idx_invitations_created_by` (`created_by`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户邀请表';

-- ----------------------------
-- God Mode 操作审计日志表
-- ----------------------------
DROP TABLE IF EXISTS `god_mode_audit_log`;

CREATE TABLE `god_mode_audit_log` (
    `id` varchar(36) NOT NULL COMMENT '审计日志ID (UUID)',
    `tenant_id` varchar(36) NOT NULL COMMENT '被访问的租户ID',
    `actor_id` varchar(36) NOT NULL COMMENT '超管用户ID',
    `action` enum('enter','exit','read','write','extend') NOT NULL COMMENT '操作类型',
    `target_type` varchar(100) DEFAULT NULL COMMENT '目标资源类型 (kb/document/pipeline/user/role/config)',
    `target_id` varchar(36) DEFAULT NULL COMMENT '目标资源ID',
    `details` text DEFAULT NULL COMMENT '操作详情文本',
    `session_started_at` datetime NOT NULL COMMENT '本次 God Mode 会话开始时间',
    `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '操作时间',
    PRIMARY KEY (`id`),
    KEY `idx_god_mode_tenant_id` (`tenant_id`),
    KEY `idx_god_mode_actor_id` (`actor_id`),
    KEY `idx_god_mode_action` (`action`),
    KEY `idx_god_mode_session` (`session_started_at`),
    KEY `idx_god_mode_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='God Mode操作审计日志表';

-- ----------------------------
-- 权限操作审计日志表
-- ----------------------------
DROP TABLE IF EXISTS `permission_audit_log`;

CREATE TABLE `permission_audit_log` (
    `id` varchar(36) NOT NULL COMMENT '审计日志ID (UUID)',
    `tenant_id` varchar(36) NOT NULL COMMENT '所属租户ID',
    `actor_id` varchar(36) NOT NULL COMMENT '操作者用户ID',
    `action` varchar(100) NOT NULL COMMENT '操作类型 (create_role/update_role/delete_role/assign_role/revoke_role/invite_user/disable_user/enable_user)',
    `target_type` varchar(100) NOT NULL COMMENT '目标类型 (role/user/user_role/invitation)',
    `target_id` varchar(36) NOT NULL COMMENT '目标ID',
    `old_value` json DEFAULT NULL COMMENT '变更前值',
    `new_value` json DEFAULT NULL COMMENT '变更后值',
    `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '操作时间',
    PRIMARY KEY (`id`),
    KEY `idx_perm_audit_tenant_id` (`tenant_id`),
    KEY `idx_perm_audit_actor_id` (`actor_id`),
    KEY `idx_perm_audit_action` (`action`),
    KEY `idx_perm_audit_target` (`target_type`, `target_id`),
    KEY `idx_perm_audit_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='权限操作审计日志表';

-- ----------------------------
-- 租户管理审计日志表
-- ----------------------------
DROP TABLE IF EXISTS `tenant_audit_log`;

CREATE TABLE `tenant_audit_log` (
    `id` varchar(36) NOT NULL COMMENT '审计日志ID (UUID)',
    `tenant_id` varchar(36) NOT NULL COMMENT '目标租户ID',
    `actor_id` varchar(36) NOT NULL COMMENT '超管用户ID',
    `action` varchar(100) NOT NULL COMMENT '操作类型 (create/update/disable/enable/archive/restore/delete/update_quota)',
    `details` text DEFAULT NULL COMMENT '操作详情文本',
    `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '操作时间',
    PRIMARY KEY (`id`),
    KEY `idx_tenant_audit_tenant_id` (`tenant_id`),
    KEY `idx_tenant_audit_actor_id` (`actor_id`),
    KEY `idx_tenant_audit_action` (`action`),
    KEY `idx_tenant_audit_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='租户管理审计日志表';

-- ----------------------------
-- 租户删除快照表
-- ----------------------------
DROP TABLE IF EXISTS `tenant_deletion_snapshots`;

CREATE TABLE `tenant_deletion_snapshots` (
    `id` varchar(36) NOT NULL COMMENT '快照ID (UUID)',
    `tenant_id` varchar(36) NOT NULL COMMENT '租户ID',
    `snapshot_path` varchar(1000) NOT NULL COMMENT '快照文件路径 (storage/snapshots/{tenant_id}_{timestamp}/)',
    `status` enum('pending','ready','expired') NOT NULL DEFAULT 'pending' COMMENT '快照状态',
    `expires_at` datetime NOT NULL COMMENT '快照过期时间 (默认生成后 90 天)',
    `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    KEY `idx_snapshots_tenant_id` (`tenant_id`),
    KEY `idx_snapshots_status` (`status`),
    KEY `idx_snapshots_expires_at` (`expires_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='租户删除快照表';
```

---

## 3. 服务层接口

所有类定义在 `backend/src/service/permission/` 目录下（新建模块）。遵循现有规范：使用 Injector DI、`async_session_factory` 注入 Repository、门面模式管理复杂服务。

---

### 3.1 TenantService

```python
# backend/src/service/permission/tenant_service.py

class TenantService:
    """租户管理服务（超管专用）

    负责租户全生命周期：创建（含自动 Provisioning）、停用、归档、软删除、恢复。
    """

    def __init__(
        self,
        tenant_repository: "TenantRepository",
        user_repository: "UserRepository",
        role_repository: "RoleRepository",
        provisioning_service: "ProvisioningService",
        tenant_audit_log_repository: "TenantAuditLogRepository",
        tenant_deletion_snapshot_repository: "TenantDeletionSnapshotRepository",
    ): ...

    async def create_tenant(
        self,
        name: str,
        slug: str,
        initial_admin: "CreateAdminInput",
        resource_limits: "ResourceLimitsInput",
        actor_id: str | None = None,
    ) -> "CreateTenantResult": ...

    async def get_tenant_list(
        self,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> "PaginatedResult[TenantSummary]": ...

    async def get_tenant_detail(self, tenant_id: str) -> "TenantDetail": ...

    async def update_tenant(
        self,
        tenant_id: str,
        updates: "UpdateTenantInput",
        actor_id: str | None = None,
    ) -> "TenantDetail": ...

    async def archive_tenant(
        self,
        tenant_id: str,
        actor_id: str | None = None,
    ) -> "TenantStatusResult": ...
    """将 active 状态租户置为 archived。数据保留但不计入活跃配额。"""

    async def restore_tenant(
        self,
        tenant_id: str,
        actor_id: str | None = None,
    ) -> "TenantStatusResult": ...
    """将 archived 或 deleted 状态租户恢复为 active。"""

    async def soft_delete_tenant(
        self,
        tenant_id: str,
        confirm_slug: str,
        actor_id: str | None = None,
    ) -> "DeleteTenantResult": ...
    """软删除：标记 deleted_at，生成数据导出快照。"""

    async def get_tenant_users(
        self,
        tenant_id: str,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
        role_id: str | None = None,
    ) -> "PaginatedResult[TenantUserSummary]": ...

    async def _perform_physical_cleanup(self, tenant_id: str) -> None: ...
    """由定时任务调用：检查 deleted_at 超过 30 天的租户，执行物理清理（删除 DB 记录和存储文件）。"""

    async def _generate_deletion_snapshot(self, tenant_id: str) -> str: ...
    """生成租户数据导出快照（MySQL dump + 向量存储元数据 + 文件列表），返回快照路径。"""
```

---

### 3.2 UserService

```python
# backend/src/service/permission/user_service.py

class UserService:
    """租户用户管理服务

    负责用户邀请、接受邀请、角色分配、禁用、删除。
    """

    def __init__(
        self,
        user_repository: "UserRepository",
        role_repository: "RoleRepository",
        user_invitation_repository: "UserInvitationRepository",
        permission_audit_log_repository: "PermissionAuditLogRepository",
        rbac_service: "RBACService",
        jwt_service: "JWTService",
        email_service: "EmailService | None" = None,
    ): ...

    async def invite_user(
        self,
        tenant_id: str,
        email: str,
        role_ids: list[str],
        invited_by: str,
    ) -> "UserInvitationResult": ...
    """生成一次性邀请链接（token 24h 过期）。
    校验：角色权限不能超出邀请者权限；邮箱不能已有未过期邀请；不能已是成员。
    """

    async def accept_invitation(
        self,
        token: str,
        username: str,
        password: str,
    ) -> "AcceptInvitationResult": ...
    """接受邀请：验证 token → 创建用户 → 绑定角色 → 返回 JWT。"""

    async def assign_roles(
        self,
        tenant_id: str,
        user_id: str,
        role_ids: list[str],
        actor_id: str,
    ) -> "UserDetail": ...
    """为用户分配角色（替换现有角色集）。
    校验：角色权限不能超出操作者权限。
    """

    async def disable_user(
        self,
        tenant_id: str,
        user_id: str,
        actor_id: str,
    ) -> "UserDetail": ...
    """禁用用户。不能禁用自己。"""

    async def enable_user(
        self,
        tenant_id: str,
        user_id: str,
        actor_id: str,
    ) -> "UserDetail": ...

    async def delete_user(
        self,
        tenant_id: str,
        user_id: str,
        actor_id: str,
    ) -> None: ...
    """删除用户。不能删除自己；不能删除租户最后一个 admin。"""

    async def get_user_list(
        self,
        tenant_id: str,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
        role_id: str | None = None,
    ) -> "PaginatedResult[UserSummary]": ...

    async def get_user_detail(
        self,
        tenant_id: str,
        user_id: str,
    ) -> "UserDetail": ...
```

---

### 3.3 RoleService

```python
# backend/src/service/permission/role_service.py

class RoleService:
    """角色管理服务

    负责角色 CRUD、权限校验。关键约束：自定义角色权限不能超出创建者权限。
    """

    def __init__(
        self,
        role_repository: "RoleRepository",
        user_roles_repository: "UserRolesRepository",
        permission_audit_log_repository: "PermissionAuditLogRepository",
        rbac_service: "RBACService",
    ): ...

    async def get_role_list(self, tenant_id: str) -> list["RoleDetail"]: ...

    async def get_role_detail(self, tenant_id: str, role_id: str) -> "RoleDetail": ...

    async def create_role(
        self,
        tenant_id: str,
        name: str,
        slug: str,
        permissions: list[str],
        actor_id: str,
        actor_permissions: list[str],
    ) -> "RoleDetail": ...
    """创建自定义角色。
    校验：slug 不与内置角色冲突；permissions 必须是 actor_permissions 的子集。
    """

    async def update_role(
        self,
        tenant_id: str,
        role_id: str,
        updates: "UpdateRoleInput",
        actor_id: str,
        actor_permissions: list[str],
    ) -> "RoleDetail": ...
    """更新角色。不能修改内置角色权限。新权限集不能超出 actor_permissions。"""

    async def delete_role(
        self,
        tenant_id: str,
        role_id: str,
        actor_id: str,
    ) -> None: ...
    """删除角色。不能删除内置角色；不能删除仍有用户引用的角色。"""

    async def get_available_permissions(self) -> "AvailablePermissionsResult": ...
    """返回系统中所有可用的权限列表（集中定义在 config 中）。"""

    async def _validate_permissions_are_known(self, permissions: list[str]) -> None: ...
    """校验 permissions 中的每个值都在已知权限列表中。"""

    async def _validate_permissions_subset(
        self, requested: list[str], granted: list[str]
    ) -> None: ...
    """校验 requested 权限集是 granted 权限集的子集。不满足则抛出 ROLE_PERMISSION_EXCEEDS。"""

    async def _validate_has_users(self, role_id: str) -> bool: ...
    """检查角色是否有用户引用。"""
```

---

### 3.4 GodModeService

```python
# backend/src/service/permission/god_mode_service.py

class GodModeService:
    """God Mode 服务（超管进入租户上下文）

    管理 God Mode 会话生命周期：进入、退出、审计、超时管理。
    """

    GOD_MODE_SESSION_TTL = 30 * 60  # 30 分钟
    GOD_MODE_EXTEND_LIMIT = 1  # 只允许续期一次
    GOD_MODE_ROLE_SLUG = "_god_mode"

    def __init__(
        self,
        god_mode_audit_log_repository: "GodModeAuditLogRepository",
        jwt_service: "JWTService",
        redis_client: "RedisClient | None" = None,  # 用于并发控制
    ): ...

    async def enter(
        self,
        tenant_id: str,
        actor_id: str,
    ) -> "GodModeEnterResult": ...
    """进入 God Mode：
    1. 检查租户状态（必须 active）
    2. 检查并发（Redis 锁：同一租户同一时间只允许一个超管 God Mode）
    3. 生成 god_mode_session_id
    4. 签发临时 JWT（含 god_mode=true, session_id）
    5. 写入 god_mode_audit_log（action=enter）
    6. 设置 Redis TTL（30 分钟）
    """

    async def extend(
        self,
        tenant_id: str,
        god_mode_session_id: str,
        actor_id: str,
    ) -> "GodModeEnterResult": ...
    """续期 God Mode（仅一次）：
    1. 验证 session 存在且未过期
    2. 检查 extend_count < 1
    3. 签发新 JWT（有效期 +30 分钟）
    4. 写入 god_mode_audit_log（action=extend）
    """

    async def exit(
        self,
        tenant_id: str,
        god_mode_session_id: str,
        actor_id: str,
    ) -> None: ...
    """退出 God Mode：
    1. 清除 Redis 锁
    2. 写入 god_mode_audit_log（action=exit）
    """

    async def audit_write(
        self,
        tenant_id: str,
        god_mode_session_id: str,
        actor_id: str,
        action: str,  # 'write'
        target_type: str,
        target_id: str,
        details: str,
    ) -> None: ...
    """记录 God Mode 写操作审计日志。"""

    async def check_god_mode_active(
        self, tenant_id: str, god_mode_session_id: str
    ) -> bool: ...
    """检查 God Mode 会话是否仍然有效。由中间件在每次请求时调用。"""

    async def _acquire_god_mode_lock(self, tenant_id: str) -> bool: ...
    """获取 God Mode 并发锁（Redis SETNX），返回是否获取成功。"""

    async def _release_god_mode_lock(self, tenant_id: str) -> None: ...

    async def _get_extend_count(self, session_id: str) -> int: ...
```

---

### 3.5 ProvisioningService

```python
# backend/src/service/permission/provisioning_service.py

class ProvisioningService:
    """租户 Provisioning 服务

    创建租户时自动执行：初始化 DB 空间、存储目录、默认角色、初始管理员。
    任一子步骤失败则整体回滚。
    """

    BUILTIN_ROLES = [
        {
            "name": "管理员", "slug": "admin", "is_builtin": True,
            "permissions": [
                "kb:read", "kb:write", "kb:delete", "kb:manage_acl",
                "pipeline:read", "pipeline:write", "pipeline:publish",
                "search:execute", "search:stream",
                "eval:read", "eval:write",
                "system:config", "system:monitor",
            ],
        },
        {
            "name": "编辑者", "slug": "editor", "is_builtin": True,
            "permissions": [
                "kb:read", "kb:write", "kb:delete",
                "pipeline:read", "pipeline:write",
                "search:execute",
                "eval:read", "eval:write",
            ],
        },
        {
            "name": "查看者", "slug": "viewer", "is_builtin": True,
            "permissions": [
                "kb:read", "search:execute",
            ],
        },
    ]

    def __init__(
        self,
        tenant_repository: "TenantRepository",
        user_repository: "UserRepository",
        role_repository: "RoleRepository",
        user_roles_repository: "UserRolesRepository",
        storage_config: "StorageConfig",  # 用于获取存储根路径
    ): ...

    async def provision(
        self,
        tenant_id: str,
        slug: str,
        initial_admin_username: str,
        initial_admin_email: str,
        initial_admin_password: str,
        resource_limits: dict,
    ) -> "ProvisioningResult": ...
    """执行完整的租户 Provisioning 流程：
    1. 创建存储目录 storage/{slug}/
    2. 创建存储子目录：storage/{slug}/documents, storage/{slug}/index, storage/{slug}/reports, storage/{slug}/snapshots
    3. 插入默认角色记录
    4. 创建初始管理员用户（绑定 admin 角色）
    5. 若任一步骤失败，回滚已完成的操作
    """

    async def rollback(self, tenant_id: str, slug: str, completed_steps: list[str]) -> None: ...
    """回滚 Provisioning：根据已完成步骤反向清理。"""

    async def _create_storage_dirs(self, slug: str) -> None: ...
    """创建存储目录树。"""

    async def _remove_storage_dirs(self, slug: str) -> None: ...
    """删除存储目录树（回滚用）。"""

    async def _insert_default_roles(self, tenant_id: str) -> dict[str, str]: ...
    """插入默认角色，返回 {slug: role_id} 映射。"""

    async def _create_admin_user(
        self, tenant_id: str, username: str, email: str, password: str, admin_role_id: str
    ) -> str: ...
    """创建初始管理员用户并绑定 admin 角色，返回 user_id。"""
```

---

### 3.6 JWTService

```python
# backend/src/service/permission/jwt_service.py

class JWTService:
    """JWT 令牌服务

    负责 JWT 签发、验证、刷新。区分超管与租户用户。
    """

    ACCESS_TOKEN_TTL = 24 * 60 * 60       # 24 小时
    REFRESH_WINDOW = 7 * 24 * 60 * 60     # 7 天刷新窗口

    def __init__(
        self,
        secret_key: str,
        algorithm: str = "HS256",
    ): ...

    def issue(
        self,
        user_id: str,
        username: str,
        tenant_id: str | None,      # None = 超管
        tenant_slug: str | None,
        roles: list[str],
        permissions: list[str],
        god_mode: bool = False,
        god_mode_session_id: str | None = None,
        simulated_role: str | None = None,
        ttl: int | None = None,
    ) -> str: ...
    """签发 JWT。
    - tenant_id=None 时为超管令牌，不携带租户上下文
    - god_mode=True 时携带 God Mode 标记
    - simulated_role 非空时表示角色视角切换
    """

    def verify(self, token: str) -> "JWTClaims": ...
    """验证 JWT 并返回解析后的 claims。"""
    """抛出：
    - ExpiredJWTError（exp 过期但在 refresh window 内）
    - InvalidJWTError（签名无效、格式错误）
    """

    def refresh(self, token: str) -> str: ...
    """刷新 JWT：验证旧 token 在 refresh window 内 → 签发新 token。"""

    def is_super_admin(self, claims: "JWTClaims") -> bool: ...
    """判断是否为超管（tenant_id 为 None）。"""

    def is_god_mode(self, claims: "JWTClaims") -> bool: ...
    """判断是否为 God Mode。"""

    def get_permissions(self, claims: "JWTClaims") -> list[str]: ...
    """从 claims 中提取权限列表。如果是 God Mode，返回全部权限。"""
```

---

### 3.7 RBACService

```python
# backend/src/service/permission/rbac_service.py

class RBACService:
    """RBAC 权限服务

    负责权限检查、可见资源计算。权限判断基于用户角色的 permissions 集合求并集。
    """

    def __init__(
        self,
        role_repository: "RoleRepository",
        user_roles_repository: "UserRolesRepository",
    ): ...

    async def check_permission(
        self,
        tenant_id: str,
        user_id: str,
        required_permission: str,
        god_mode: bool = False,
    ) -> bool: ...
    """检查用户是否拥有某个权限。
    - god_mode=True 时始终返回 True
    """

    async def check_permissions(
        self,
        tenant_id: str,
        user_id: str,
        required_permissions: list[str],
        god_mode: bool = False,
    ) -> bool: ...
    """检查用户是否拥有全部指定权限（AND 逻辑）。"""

    async def has_any_permission(
        self,
        tenant_id: str,
        user_id: str,
        required_permissions: list[str],
        god_mode: bool = False,
    ) -> bool: ...
    """检查用户是否拥有任一指定权限（OR 逻辑）。"""

    async def get_user_permissions(
        self,
        tenant_id: str,
        user_id: str,
    ) -> list[str]: ...
    """获取用户所有权限（所有角色权限的并集）。"""

    async def get_visible_resource_ids(
        self,
        tenant_id: str,
        user_id: str,
        resource_type: str,  # 'kb' | 'document' | 'pipeline'
        god_mode: bool = False,
    ) -> list[str] | None: ...
    """获取用户可见的资源 ID 列表。
    - resource_type='kb'：返回可见知识库 ID 列表（基于 visibility 和角色）
    - resource_type='document'：返回可见文档 ID 列表（基于 doc_acl 和角色）
    - 返回 None 表示不过滤（God Mode）
    """

    async def get_role_permissions(
        self,
        tenant_id: str,
        role_slug: str,
    ) -> list[str]: ...
    """获取某个角色的权限列表（用于角色视角切换）。"""

    def merge_permissions(self, role_slugs: list[str], roles_map: dict[str, list[str]]) -> list[str]: ...
    """权限并集计算：多个角色 permissions 求并集。"""
```

---

### 3.8 ACLFilterBuilder（三层向量后端抽象）

```python
# backend/src/service/permission/acl_filter_builder.py

from abc import ABC, abstractmethod

class ACLFilterBuilder(ABC):
    """ACL 过滤条件构建器（抽象基类）

    根据用户角色构建向量存储的 ACL 过滤条件。
    不同向量后端的过滤语法不同，通过子类实现统一接口。
    """

    @abstractmethod
    def build_filter(
        self, user_roles: list[str], god_mode: bool = False
    ) -> dict | list | str: ...
    """将用户角色列表转换为当前后端的过滤条件。
    - Chroma: 返回 where 条件 dict
    - Elasticsearch: 返回 filter clause list
    - Milvus: 返回 expr 字符串
    - god_mode=True 时返回空/全量条件（不过滤）
    """


class ChromaACLFilterBuilder(ACLFilterBuilder):
    """ChromaDB ACL 过滤条件构建器

    输出格式：ChromaDB where clause dict
    示例：{"$or": [{"doc_acl": {"$contains": "admin"}}, {"doc_acl": {"$contains": "doctor"}}]}
    """

    def build_filter(self, user_roles: list[str], god_mode: bool = False) -> dict: ...


class ESACLFilterBuilder(ACLFilterBuilder):
    """Elasticsearch ACL 过滤条件构建器

    输出格式：ES bool filter clause list
    示例：[{"terms": {"doc_acl": ["admin", "doctor"]}}, {"term": {"access_level": "public"}}]
    """

    def build_filter(self, user_roles: list[str], god_mode: bool = False) -> list: ...


class MilvusACLFilterBuilder(ACLFilterBuilder):
    """Milvus ACL 过滤条件构建器

    输出格式：Milvus expr 字符串
    示例：'doc_acl in ["admin", "doctor"]'
    """

    def build_filter(self, user_roles: list[str], god_mode: bool = False) -> str: ...
```

---

### 3.9 门面服务：PermissionFacade

```python
# backend/src/service/permission/facade.py

class PermissionFacade:
    """权限模块门面服务

    对外提供统一的权限管理接口，内部协调 TenantService / UserService / RoleService / GodModeService。
    """

    def __init__(
        self,
        tenant_service: "TenantService",
        user_service: "UserService",
        role_service: "RoleService",
        god_mode_service: "GodModeService",
        provisioning_service: "ProvisioningService",
        jwt_service: "JWTService",
        rbac_service: "RBACService",
    ): ...

    # Tenant 管理（委托 TenantService）
    async def create_tenant(...) -> "CreateTenantResult": ...
    async def get_tenant_list(...) -> "PaginatedResult[TenantSummary]": ...
    async def get_tenant_detail(...) -> "TenantDetail": ...
    async def update_tenant(...) -> "TenantDetail": ...
    async def archive_tenant(...) -> "TenantStatusResult": ...
    async def restore_tenant(...) -> "TenantStatusResult": ...
    async def soft_delete_tenant(...) -> "DeleteTenantResult": ...
    async def get_tenant_users(...) -> "PaginatedResult[TenantUserSummary]": ...

    # User 管理（委托 UserService）
    async def login(...) -> "LoginResult": ...
    async def refresh_token(...) -> "RefreshTokenResult": ...
    async def switch_role(...) -> "SwitchRoleResult": ...
    async def invite_user(...) -> "UserInvitationResult": ...
    async def accept_invitation(...) -> "AcceptInvitationResult": ...
    async def update_user(...) -> "UserDetail": ...
    async def delete_user(...) -> None: ...
    async def get_user_list(...) -> "PaginatedResult[UserSummary]": ...
    async def get_user_detail(...) -> "UserDetail": ...

    # Role 管理（委托 RoleService）
    async def get_role_list(...) -> list["RoleDetail"]: ...
    async def create_role(...) -> "RoleDetail": ...
    async def update_role(...) -> "RoleDetail": ...
    async def delete_role(...) -> None: ...
    async def get_available_permissions(...) -> "AvailablePermissionsResult": ...

    # God Mode（委托 GodModeService）
    async def enter_god_mode(...) -> "GodModeEnterResult": ...
    async def extend_god_mode(...) -> "GodModeEnterResult": ...
    async def exit_god_mode(...) -> None: ...
    async def get_god_mode_log(...) -> "PaginatedResult[GodModeAuditLogEntry]": ...
```

---

### 3.10 Repository 接口

```python
# backend/src/repository/permission/
# 所有新 Repository 继承 BaseRepository[ModelType]，
# 遵循现有模式：接收 async_session_factory，每个方法内独立管理 session
# 所有查询自动注入 WHERE tenant_id = :tenant_id（行级过滤）

class TenantRepository(BaseRepository[Tenant]):
    """租户 Repository"""
    async def get_by_slug(self, slug: str) -> Tenant | None: ...
    async def get_active_tenants(self) -> list[Tenant]: ...
    async def get_pending_cleanup(self) -> list[Tenant]: ...
    """查询 deleted_at 超过 30 天、待物理清理的租户。"""

class UserRepository(BaseRepository[User]):
    """用户 Repository（自动注入 tenant_id 行级过滤）"""
    async def get_by_username(self, tenant_id: str, username: str) -> User | None: ...
    async def get_by_email(self, tenant_id: str, email: str) -> User | None: ...
    async def get_super_admin_by_username(self, username: str) -> User | None: ...
    """查询超管用户（tenant_id IS NULL）。"""
    async def get_admin_count(self, tenant_id: str) -> int: ...
    """统计租户内 admin 角色用户数。"""

class RoleRepository(BaseRepository[Role]):
    """角色 Repository（自动注入 tenant_id 行级过滤）"""
    async def get_by_slug(self, tenant_id: str, slug: str) -> Role | None: ...
    async def get_builtin_roles(self, tenant_id: str) -> list[Role]: ...

class UserRolesRepository(BaseRepository[UserRole]):
    """用户角色关联 Repository"""
    async def get_roles_for_user(self, user_id: str) -> list[str]: ...
    """返回用户的角色 ID 列表。"""
    async def get_users_for_role(self, role_id: str) -> list[str]: ...
    """返回拥有该角色的用户 ID 列表。"""
    async def set_user_roles(self, user_id: str, role_ids: list[str]) -> None: ...
    """原子替换用户角色（删除旧关联 + 插入新关联）。"""
    async def has_admin_role(self, user_id: str) -> bool: ...

class UserInvitationRepository(BaseRepository[UserInvitation]):
    """用户邀请 Repository（自动注入 tenant_id 行级过滤）"""
    async def get_by_token(self, token: str) -> UserInvitation | None: ...
    async def get_pending_by_email(self, tenant_id: str, email: str) -> UserInvitation | None: ...
    """查询该邮箱是否有未过期、未接受的邀请。"""

class GodModeAuditLogRepository(BaseRepository[GodModeAuditLog]):
    """God Mode 审计日志 Repository"""
    async def get_by_session(self, session_id: str, **pagination) -> list[GodModeAuditLog]: ...
    async def check_concurrent(self, tenant_id: str) -> bool: ...
    """检查该租户是否有活跃的 God Mode 会话（最近 30 分钟内的 enter 无对应 exit）。"""

class PermissionAuditLogRepository(BaseRepository[PermissionAuditLog]):
    """权限操作审计日志 Repository（自动注入 tenant_id 行级过滤）"""

class TenantAuditLogRepository(BaseRepository[TenantAuditLog]):
    """租户管理审计日志 Repository"""

class TenantDeletionSnapshotRepository(BaseRepository[TenantDeletionSnapshot]):
    """租户删除快照 Repository"""
    async def get_expired_snapshots(self) -> list[TenantDeletionSnapshot]: ...
    """查询过期快照（expires_at < NOW()）。"""
```

---

## 4. 认证流程（时序描述）

### 4.1 登录流程 (username/password → JWT)

```
1. 用户 POST /api/v1/auth/login { slug, username, password }
2. 后端 PermissionFacade.login():
   a. TenantRepository.get_by_slug(slug) → 获取 tenant
   b. 校验租户状态：disabled/archived → 403
   c. UserRepository.get_by_username(tenant.id, username) → 获取 user
   d. 校验用户状态：disabled → 403
   e. 验证密码（bcrypt）：不匹配 → 401 INVALID_CREDENTIALS
   f. UserRolesRepository.get_roles_for_user(user.id) → 获取角色 ID 列表
   g. RoleRepository 批量查询角色 → 获取 permissions 列表
   h. RBACService.merge_permissions(roles) → 权限并集
   i. JWTService.issue(
        user_id=user.id, username=user.username,
        tenant_id=tenant.id, tenant_slug=slug,
        roles=[role.slug for role in roles],
        permissions=merged_permissions,
        ttl=24h
      )
   j. 返回 { access_token, token_type, expires_at, user }
```

### 4.2 God Mode 进入流程

```
1. 超管已登录（无 tenant_id 的 JWT），浏览租户列表
2. 超管点击"进入此租户"按钮（前端 POST /api/v1/admin/tenants/{id}/impersonate）
3. 后端 GodModeService.enter():
   a. TenantRepository.get_by_id(id) → 校验租户存在且状态为 active
   b. _acquire_god_mode_lock(tenant_id) → Redis SETNX
      - 失败 → 409 GOD_MODE_CONCURRENT（已有其他超管在此租户 God Mode 中）
   c. 生成 god_mode_session_id = uuid4()
   d. JWTService.issue(
        user_id=super_admin.id, username=super_admin.username,
        tenant_id=tenant.id, tenant_slug=tenant.slug,
        roles=["_god_mode"],
        permissions=[ALL_PERMISSIONS],  # 全部权限
        god_mode=True,
        god_mode_session_id=session_id,
        ttl=30min
      )
   e. GodModeAuditLogRepository 写入 action=enter
   f. 设置 Redis TTL = 30min（用于超时自动退出）
4. 前端收到 impersonate_token，替换本地 JWT
5. 前端路由切换到租户上下文（/kb, /pipeline, /settings 等租户内页面）
6. 顶部栏显示"当前以超管身份访问仁和医院" + [← 返回平台管理] 按钮
7. 所有后续请求携带 God Mode JWT，后端中间件识别 god_mode=true：
   - 跳过所有 RBAC 校验
   - 跳过所有 ACL 过滤
   - 写操作检测 X-God-Mode-Confirm Header
```

### 4.3 双层 Pre-filter 注入流程（检索时）

```
1. 用户发起搜索请求 → 触发 RAG 检索流水线
2. PipelineCompiler 构建检索计划时：
   a. 从请求上下文获取 tenant_id, user_id, roles, god_mode
   b. RBACService.get_visible_resource_ids(resource_type='kb') → 可见知识库 ID 列表
3. 库级别裁剪（Domain Dispatch 阶段）：
   a. 从域激活计划中剔除无权限知识库对应的域
   b. 确保被裁剪的域不会进入后续检索节点
4. 文档级别过滤（检索执行阶段）：
   a. PipelineCompiler 确定知识库使用的向量后端类型
   b. 通过后端类型获取对应的 ACLFilterBuilder 实例
   c. ACLFilterBuilder.build_filter(user_roles=roles, god_mode=god_mode)
      - Chroma → where clause dict 注入 query
      - ES → filter clause list 注入 query
      - Milvus → expr string 注入 query
   d. 若 god_mode=True，build_filter 返回空条件（全量可见）
5. 检索执行后返回的文档自然满足 ACL 约束
6. 【约束】所有检索节点必须调用 ACLFilterBuilder.build_filter，禁止跳过
```

### 4.4 角色视角切换流程

```
1. 管理员在顶部栏点击"切换角色视角"下拉 → 选择 viewer 角色
2. 前端 POST /api/v1/auth/switch-role { role_slug: "viewer" }
3. 后端 PermissionFacade.switch_role():
   a. 从当前 JWT claims 获取 user_id, tenant_id, 当前 permissions
   b. RoleRepository.get_by_slug(tenant_id, "viewer") → 获取 viewer 角色权限集
   c. _validate_permissions_subset(viewer_perms, current_perms)
      - viewer_perms 必须是 current_perms 的子集，否则 400 ROLE_PERMISSION_EXCEEDS
   d. JWTService.issue(
        user_id=current_user.id,
        username=current_user.username,
        tenant_id=current_tenant.id,
        tenant_slug=current_tenant.slug,
        roles=["viewer"],
        permissions=viewer_perms,
        simulated_role="viewer",  # 标记
        ttl=24h
      )
4. 前端更新本地 JWT，重新渲染页面
5. 页面行为：
   - 按钮灰掉/隐藏（无权限的操作不可见）
   - 知识库列表按 viewer 权限过滤（仅可见 public 知识库和被授权的 role_scoped 知识库）
   - 搜索和评估以 viewer 权限执行（只读）
6. 管理员选择"+ 返回本角色" → 重新签发原始权限的 JWT → 恢复
```

---

## 5. 中间件规格

### 5.1 AuthMiddleware

**位置**：`backend/src/middleware/auth_middleware.py`

**职责**：提取 JWT、验证、注入请求上下文。

```python
class AuthMiddleware:
    """认证中间件

    注册为 FastAPI 中间件，在每个请求到达控制器前执行。
    遵循现有中间件模式（参考 TraceMiddleware）。
    """

    def __init__(
        self,
        jwt_service: "JWTService",
        tenant_service: "TenantService | None" = None,
        god_mode_service: "GodModeService | None" = None,
    ): ...

    async def __call__(self, request: Request, call_next):
        """中间件入口：
        1. 检查请求路径是否在白名单中（登录/接受邀请/健康检查 等无需认证的端点）
        2. 从 Authorization Header 提取 Bearer Token
        3. JWTService.verify(token) → JWTClaims
           - 过期但未超刷新窗口 → 401 TOKEN_EXPIRED（前端应触发 refresh）
           - 签名无效/格式错误 → 401 INVALID_TOKEN
        4. 若 claims.tenant_id 为 None：
           - 标记为超管请求
           - 注入 request.state.super_admin = True
           - 注入 request.state.tenant_id = None
        5. 若 claims.tenant_id 不为 None：
           - 注入 request.state.tenant_id, user_id, username, roles, permissions
           - 若 claims.god_mode = True：
             a. GodModeService.check_god_mode_active(tenant_id, session_id)
                - 已过期 → 401 GOD_MODE_EXPIRED
             b. 注入 request.state.god_mode = True
           - 若 claims.god_mode = False：
             a. TenantService 检查租户状态（active/disabled/archived）
                - disabled → 403 TENANT_DISABLED
                - archived → 403 TENANT_ARCHIVED
        6. call_next(request)
        """
```

**请求上下文结构**（存储于 `request.state`）：

```python
class RequestContext:
    tenant_id: str | None       # None = 超管
    user_id: str
    username: str
    roles: list[str]            # 角色 slug 列表
    permissions: list[str]      # 权限列表
    god_mode: bool              # 是否为 God Mode
    god_mode_session_id: str | None
    simulated_role: str | None  # 角色视角切换标记
    super_admin: bool           # 是否为超管（无 tenant_id）
```

**跳过认证的路径白名单**：

```python
AUTH_WHITELIST = [
    ("POST", "/api/v1/auth/login"),
    ("POST", "/api/v1/users/accept-invitation"),
    ("GET", "/health"),
    ("GET", "/metrics"),
    # God Mode 进入/退出也跳过（使用超管 Token）：
    # 超管 Token 无 tenant_id，不会被 tenant 校验拦截
    # 实际上这些是 admin 路由，由 admin 前缀的中间件处理
]
```

### 5.2 TenantMiddleware

**位置**：`backend/src/middleware/tenant_middleware.py`

**职责**：校验租户状态、检查配额。

```python
class TenantMiddleware:
    """租户中间件

    在 AuthMiddleware 之后执行。
    仅对有 tenant_id 的请求生效。
    """

    def __init__(
        self,
        tenant_service: "TenantService",
        cache_service: "ICacheService | None" = None,
    ): ...

    async def __call__(self, request: Request, call_next):
        """中间件入口：
        1. 若 request.state.tenant_id 为 None（超管请求），跳过
        2. 若 request.state.god_mode = True，跳过（God Mode 不受租户状态限制）
        3. 检查缓存中的租户状态（TTL 60s），定期刷新
        4. 若租户状态 != active → 403（TENANT_DISABLED / TENANT_ARCHIVED）
        5. 若请求为写操作（POST/PUT/DELETE）且非 God Mode：
           a. 检查资源配额（用户数/知识库数/存储量/搜索 QPS）
           b. 超过配额 → 403 TENANT_QUOTA_EXCEEDED
        6. call_next(request)
        """
```

### 5.3 错误响应格式

**401 响应（认证失败）：**

```json
{
  "code": 11001,
  "message": "Token 无效或已过期",
  "error_code": "INVALID_TOKEN",
  "details": null
}
```

**401 响应（Token 过期但可刷新）：**

```json
{
  "code": 11002,
  "message": "Token 已过期，请刷新",
  "error_code": "TOKEN_EXPIRED",
  "details": null
}
```

**401 响应（God Mode 超时）：**

```json
{
  "code": 11003,
  "message": "God Mode 会话已超时",
  "error_code": "GOD_MODE_EXPIRED",
  "details": { "session_started_at": "2026-05-14T10:00:00Z" }
}
```

**403 响应（租户已停用）：**

```json
{
  "code": 12001,
  "message": "租户已停用，请联系管理员",
  "error_code": "TENANT_DISABLED",
  "details": { "tenant_id": "uuid-t-001", "tenant_name": "仁和医院" }
}
```

**403 响应（权限不足）：**

```json
{
  "code": 12002,
  "message": "权限不足",
  "error_code": "INSUFFICIENT_PERMISSIONS",
  "details": { "required": ["kb:write"], "granted": ["kb:read", "search:execute"] }
}
```

**412 响应（God Mode 写操作需确认）：**

```json
{
  "code": 12003,
  "message": "God Mode 下写操作需要二次确认",
  "error_code": "GOD_MODE_WRITE_CONFIRM_REQUIRED",
  "details": { "require_header": "X-God-Mode-Confirm: true" }
}
```

### 5.4 中间件注册顺序

```python
# backend/src/server.py 中的注册顺序（优先级从高到低）
app.add_middleware(TraceMiddleware)         # 1. 追踪（最先，捕获所有请求）
app.add_middleware(AuthMiddleware)          # 2. 认证（提取 JWT，注入上下文）
app.add_middleware(TenantMiddleware)        # 3. 租户校验（状态 + 配额）
app.add_middleware(ResponseWrapperMiddleware) # 4. 响应包装
```

---

## 6. 测试策略

### 6.1 测试文件组织

```
backend/tests/
├── unit/
│   └── service/
│       └── permission/
│           ├── test_jwt_service.py            # JWT 签发/验证/刷新
│           ├── test_rbac_service.py            # RBAC 权限检查
│           ├── test_acl_filter_builder.py      # ACLFilterBuilder 正确性
│           ├── test_tenant_service.py          # TenantService 单元测试
│           ├── test_user_service.py            # UserService 单元测试
│           ├── test_role_service.py            # RoleService 单元测试
│           ├── test_god_mode_service.py        # GodModeService 单元测试
│           └── test_provisioning_service.py    # ProvisioningService 单元测试
├── integration/
│   └── permission/
│       ├── test_tenant_provisioning.py         # 租户 Provisioning 全流程
│       ├── test_tenant_lifecycle.py            # 租户全生命周期（归档/删除/恢复）
│       ├── test_user_invite_flow.py            # 用户邀请全流程
│       ├── test_god_mode.py                    # God Mode 进入/退出/超时
│       ├── test_rbac_enforcement.py            # RBAC 权限强制执行
│       ├── test_dual_layer_filter.py           # 双层 Pre-filter 验证
│       ├── test_middleware_auth.py             # AuthMiddleware 集成测试
│       ├── test_middleware_tenant.py           # TenantMiddleware 集成测试
│       └── test_acl_filter_consistency.py      # 三种后端 ACL 过滤一致性
└── fixtures/
    └── permission_fixtures.py                  # 权限模块共享 fixtures
```

### 6.2 单元测试规格

#### `test_jwt_service.py` — JWT 签发/验证/刷新

| 测试场景 | 输入 | 预期 |
|---------|------|------|
| `test_issue_tenant_token` | user_id, tenant_id, roles=["admin"], permissions=[...] | Token 字符串，claims 包含所有字段 |
| `test_issue_super_admin_token` | user_id, tenant_id=None | Token 中 tenant_id 为 None |
| `test_issue_god_mode_token` | user_id, tenant_id, god_mode=True | Token 中 god_mode=true, session_id 非空, ttl=30min |
| `test_verify_valid_token` | 有效 Token | 返回 JWTClaims，所有字段正确 |
| `test_verify_expired_token` | 已过期但未超刷新窗口的 Token | 抛出 ExpiredJWTError |
| `test_verify_invalid_signature` | 使用错误密钥的 Token | 抛出 InvalidJWTError |
| `test_verify_malformed_token` | 格式错误的字符串 | 抛出 InvalidJWTError |
| `test_refresh_valid_expired_token` | 已过期但在刷新窗口内的 Token | 新 Token，claims 一致，exp 更新 |
| `test_refresh_fully_expired_token` | 超过刷新窗口的 Token | 抛出 InvalidJWTError |
| `test_is_super_admin` | tenant_id=None 的 claims | True |
| `test_is_tenant_user` | tenant_id 非空的 claims | False（is_super_admin） |

#### `test_rbac_service.py` — RBAC 权限检查

| 测试场景 | 输入 | 预期 |
|---------|------|------|
| `test_check_permission_granted` | user 有 kb:read 权限，检查 kb:read | True |
| `test_check_permission_denied` | user 无 kb:write 权限，检查 kb:write | False |
| `test_check_permission_god_mode` | god_mode=True，检查任意权限 | True（无视 RBAC） |
| `test_check_multiple_permissions_all` | user 有全部所需权限 | True |
| `test_check_multiple_permissions_partial` | user 只有部分所需权限 | False |
| `test_check_any_permission` | user 有其中之一 | True |
| `test_check_any_permission_fail` | user 一个都没有 | False |
| `test_get_user_permissions_merge` | user 有两个角色，权限不同 | 返回并集 |
| `test_merge_permissions_no_duplicates` | 两个角色有重叠权限 | 去重后的并集 |
| `test_visible_kbs_public_only` | viewer 角色 | 只返回 public 和授权 role_scoped 知识库 |
| `test_visible_kbs_admin` | admin 角色 | 返回所有知识库 |
| `test_visible_docs_by_acl` | viewer 角色 | 只返回 doc_acl 包含 viewer 的文档 |

#### `test_acl_filter_builder.py` — ACLFilterBuilder 正确性

| 测试场景 | 输入 | 预期 |
|---------|------|------|
| `test_chroma_filter_single_role` | user_roles=["admin"] | `{"$or": [{"doc_acl": {"$contains": "admin"}}]}` |
| `test_chroma_filter_multi_role` | user_roles=["admin", "doctor"] | `$or` 包含两个 `$contains` |
| `test_chroma_filter_god_mode` | god_mode=True | 空 dict `{}`（不过滤） |
| `test_es_filter_multi_role` | user_roles=["admin", "doctor"] | `[{"terms": {"doc_acl": ["admin", "doctor"]}}]` |
| `test_es_filter_god_mode` | god_mode=True | `[]`（空 filter clause） |
| `test_milvus_filter_multi_role` | user_roles=["admin", "doctor"] | `'doc_acl in ["admin", "doctor"]'` |
| `test_milvus_filter_god_mode` | god_mode=True | `""`（空字符串，不过滤） |
| `test_three_backends_same_filter_logic` | user_roles=["admin"] | 三个 Builder 都返回 admin-accessible 条件，不包含 doctor-accessible |

#### `test_provisioning_service.py` — Provisioning 单元测试

| 测试场景 | 输入 | 预期 |
|---------|------|------|
| `test_provision_creates_dirs` | slug="test-tenant" | `storage/test-tenant/` 及其子目录创建 |
| `test_provision_inserts_default_roles` | tenant_id | roles 表有 3 条内置角色记录 |
| `test_provision_creates_admin_user` | tenant_id, username, email, password | users 表有 1 条用户，绑定 admin 角色 |
| `test_provision_rollback_on_failure` | 模拟某步失败 | 已创建的目录/记录被回滚清理 |

### 6.3 集成测试规格

#### `test_tenant_provisioning.py` — 租户 Provisioning 全流程

| 测试场景 | 步骤 | 预期 |
|---------|------|------|
| `test_create_tenant_full_provisioning` | 调用 TenantService.create_tenant → 检查 DB → 检查文件系统 | DB 有 tenant/user/role/user_role 记录；存储目录存在 |
| `test_create_tenant_slug_conflict` | 创建相同 slug 的租户 | 409 TENANT_SLUG_EXISTS |
| `test_provisioning_atomic_rollback` | Mock ProvisioningService 在步骤 3 失败 | 租户未创建；角色/用户记录未残留；目录已清理 |

#### `test_tenant_lifecycle.py` — 租户全生命周期

| 测试场景 | 步骤 | 预期 |
|---------|------|------|
| `test_disable_tenant_blocks_login` | 停用租户 → 尝试登录 | 403 TENANT_DISABLED |
| `test_disable_tenant_blocks_api` | 停用租户 → 调用业务 API | 403 TENANT_DISABLED |
| `test_archive_tenant_preserves_data` | 归档租户 → 检查 DB | 租户数据完整保留，status=archived |
| `test_archive_tenant_blocks_access` | 归档租户 → 尝试登录/API | 403 TENANT_ARCHIVED |
| `test_restore_archived_tenant` | 归档 → 恢复 → 登录 | 登录成功，数据完整 |
| `test_soft_delete_generates_snapshot` | 软删除租户 | tenant_deletion_snapshots 有 pending 记录 |
| `test_restore_deleted_tenant_within_window` | 软删除 → 30 天内恢复 | 恢复成功，status=active |
| `test_physical_cleanup_after_window` | Mock 超过 30 天 → 调用清理 | 租户及相关数据物理删除 |

#### `test_user_invite_flow.py` — 用户邀请全流程

| 测试场景 | 步骤 | 预期 |
|---------|------|------|
| `test_invite_user_sends_invitation` | admin 邀请用户 | DB 有 user_invitations 记录，token 非空 |
| `test_invite_user_email_already_member` | 邀请已是成员的邮箱 | 400 EMAIL_ALREADY_MEMBER |
| `test_invite_user_exceeds_creator_permissions` | admin 选择超出自己权限的角色 | 400 ROLE_PERMISSION_EXCEEDS |
| `test_accept_invitation_creates_user` | 被邀请人接受邀请 | DB 有 users 记录，status=active，绑定指定角色 |
| `test_accept_invitation_expired` | 24h 后接受邀请 | 400 INVITATION_EXPIRED |
| `test_accept_invitation_already_accepted` | 重复接受同一邀请 | 400 INVITATION_ALREADY_ACCEPTED |
| `test_invite_exceeds_user_limit` | 用户数已达上限时邀请 | 400 TENANT_USER_LIMIT_REACHED |

#### `test_god_mode.py` — God Mode 进入/退出/超时

| 测试场景 | 步骤 | 预期 |
|---------|------|------|
| `test_enter_god_mode_returns_token` | 超管进入租户 | 返回临时 JWT，god_mode=true |
| `test_god_mode_bypasses_rbac` | God Mode 用户访问受限资源 | 200（无视 ACL） |
| `test_god_mode_cannot_enter_disabled_tenant` | 进入已停用租户 | 400 TENANT_NOT_ACTIVE |
| `test_god_mode_concurrent_prevented` | 超管 A 进入 → 超管 B 进入同一租户 | 409 GOD_MODE_CONCURRENT |
| `test_god_mode_exit_releases_lock` | 超管 A 退出 → 超管 B 进入 | 成功 |
| `test_god_mode_timeout` | 30 分钟后自动退出 → 访问资源 | 401 GOD_MODE_EXPIRED |
| `test_god_mode_extend_once` | 进入 → 续期一次 → 续期第二次 | 第一次成功，第二次 400 GOD_MODE_EXTEND_LIMIT |
| `test_god_mode_write_requires_confirmation` | God Mode 下 PUT 不含确认 Header | 412 GOD_MODE_WRITE_CONFIRM_REQUIRED |
| `test_god_mode_write_with_confirmation` | God Mode 下 PUT 含确认 Header | 200，写入 god_mode_audit_log |
| `test_god_mode_audit_log` | 进入 → 写操作 → 退出 | god_mode_audit_log 有 enter/write/exit 三条记录 |

#### `test_rbac_enforcement.py` — RBAC 权限强制执行

| 测试场景 | 步骤 | 预期 |
|---------|------|------|
| `test_viewer_cannot_create_kb` | viewer 用户 POST /api/v1/kb | 403 INSUFFICIENT_PERMISSIONS |
| `test_editor_cannot_manage_users` | editor 用户 PUT /api/v1/users/{id} | 403 INSUFFICIENT_PERMISSIONS |
| `test_admin_can_all_operations` | admin 用户执行所有操作 | 全部 200 |
| `test_role_switch_to_viewer` | admin 切换到 viewer → 访问写操作 | 前端按钮灰掉，API 403 |
| `test_role_switch_cannot_exceed` | viewer 尝试切换到 admin | 400 ROLE_PERMISSION_EXCEEDS |
| `test_custom_role_permissions_respected` | 自定义角色仅 kb:read → 执行 kb:write | 403 |

#### `test_dual_layer_filter.py` — 双层 Pre-filter 验证

| 测试场景 | 步骤 | 预期 |
|---------|------|------|
| `test_domain_crop_excludes_unauthorized_kb` | viewer 搜索 → 检查域激活计划 | 无权限知识库域不在激活计划中 |
| `test_doc_acl_filter_returns_subset` | viewer 搜索含不同 doc_acl 的文档 | 只返回 doc_acl 包含 viewer 的文档 |
| `test_god_mode_no_filter` | God Mode 搜索 | 返回所有文档（库级别 + 文档级别均不过滤） |
| `test_public_kb_visible_to_viewer` | viewer 搜索 public 知识库 | 返回该知识库文档 |
| `test_private_kb_invisible_to_viewer` | viewer 搜索 private 知识库 | 不返回该知识库文档 |

#### `test_acl_filter_consistency.py` — 三种后端 ACL 过滤一致性

| 测试场景 | 步骤 | 预期 |
|---------|------|------|
| `test_chroma_es_milvus_same_result` | 同一用户、同一知识库，分别查询 Chroma/ES/Milvus | 返回相同的文档 ID 集合 |

#### `test_middleware_auth.py` — AuthMiddleware 集成测试

| 测试场景 | 步骤 | 预期 |
|---------|------|------|
| `test_missing_token_returns_401` | 无 Authorization Header 访问受保护端点 | 401 |
| `test_invalid_token_returns_401` | 使用伪造 Token | 401 INVALID_TOKEN |
| `test_expired_token_returns_401` | 使用已过期 Token | 401 TOKEN_EXPIRED |
| `test_whitelisted_path_skips_auth` | 访问 /health | 200（不校验 Token） |
| `test_context_injected_correctly` | 有效 Token 访问端点 | request.state 包含正确的 tenant_id/user_id/roles |

#### `test_middleware_tenant.py` — TenantMiddleware 集成测试

| 测试场景 | 步骤 | 预期 |
|---------|------|------|
| `test_disabled_tenant_returns_403` | 停用租户 → 有效 Token 访问 | 403 TENANT_DISABLED |
| `test_active_tenant_passes` | 活跃租户 → 有效 Token 访问 | 通过 |
| `test_super_admin_skips_tenant_check` | 超管 Token 访问 | 通过（不检查租户状态） |
| `test_god_mode_skips_tenant_check` | God Mode Token 访问已停用租户 | 通过 |
| `test_quota_exceeded_returns_403` | 超配额后执行写操作 | 403 TENANT_QUOTA_EXCEEDED |

---

## 7. 验收标准映射

以下将需求文档 §7 的 15 条验收标准（AC-4.1 到 AC-4.15）映射到具体测试场景。

| 验收标准 | 对应测试（测试文件 → 测试场景） |
|---------|-------------------------------|
| **AC-4.1**：超管登录后看到租户列表，可创建/停用/归档/删除租户 | `test_tenant_provisioning.py::test_create_tenant_full_provisioning`<br>`test_tenant_lifecycle.py::test_disable_tenant_blocks_login`<br>`test_tenant_lifecycle.py::test_archive_tenant_preserves_data`<br>`test_tenant_lifecycle.py::test_soft_delete_generates_snapshot` |
| **AC-4.2**：创建租户后自动初始化 DB 空间、存储目录、默认角色、初始管理员 | `test_tenant_provisioning.py::test_create_tenant_full_provisioning`<br>`test_provisioning_service.py::test_provision_creates_dirs`<br>`test_provisioning_service.py::test_provision_inserts_default_roles`<br>`test_provisioning_service.py::test_provision_creates_admin_user` |
| **AC-4.3**：超管进入租户后无视所有权限过滤，可操作该租户一切资源 | `test_god_mode.py::test_god_mode_bypasses_rbac`<br>`test_dual_layer_filter.py::test_god_mode_no_filter` |
| **AC-4.4**：超管进入租户后顶部显示"当前以超管身份访问 XXX"，可一键返回平台管理 | 前端验收（不在后端测试范围），但后端需确保 `POST /tenants/{id}/impersonate` 返回 `tenant_name` 和 `impersonate_token` |
| **AC-4.5**：停用租户后该租户所有用户无法登录，搜索 API 返回 403 | `test_tenant_lifecycle.py::test_disable_tenant_blocks_login`<br>`test_tenant_lifecycle.py::test_disable_tenant_blocks_api`<br>`test_middleware_tenant.py::test_disabled_tenant_returns_403` |
| **AC-4.6**：删除租户为软删除（30 天保留期），保留期内可恢复；物理清理前自动生成数据导出快照 | `test_tenant_lifecycle.py::test_soft_delete_generates_snapshot`<br>`test_tenant_lifecycle.py::test_restore_deleted_tenant_within_window`<br>`test_tenant_lifecycle.py::test_physical_cleanup_after_window` |
| **AC-4.7**：租户详情正确展示用户数、知识库数、存储用量、配额使用率 | `GET /tenants/{id}` 返回 stats 对象包含所有字段；单元测试验证 `TenantService.get_tenant_detail()` 输出 |
| **AC-4.7a**：归档租户后禁止登录和 API 访问，数据保留但不计入活跃配额，可随时恢复 | `test_tenant_lifecycle.py::test_archive_tenant_preserves_data`<br>`test_tenant_lifecycle.py::test_archive_tenant_blocks_access`<br>`test_tenant_lifecycle.py::test_restore_archived_tenant`<br>`test_middleware_tenant.py::test_disabled_tenant_returns_403`（覆盖 archived 状态） |
| **AC-4.7b**：God Mode 会话 30 分钟超时，操作写入 `god_mode_audit_log`，写操作需二次确认 | `test_god_mode.py::test_god_mode_timeout`<br>`test_god_mode.py::test_god_mode_audit_log`<br>`test_god_mode.py::test_god_mode_write_requires_confirmation`<br>`test_god_mode.py::test_god_mode_write_with_confirmation`<br>`test_god_mode.py::test_god_mode_extend_once` |
| **AC-4.8**：不同租户数据完全隔离，不可跨租户访问 | `test_middleware_auth.py::test_context_injected_correctly`（验证 tenant_id 正确注入）<br>集成测试：租户 A 用户无法访问租户 B 的资源（Repository 自动注入 tenant_id 过滤） |
| **AC-4.8a**：行级过滤有结构约束兜底——CI 静态扫描阻断裸 SQL 合并，后台任务无 `tenant_id` 时抛出 `MissingTenantContextError` | CI 配置（非运行时测试）：grep 扫描 `text()`/`execute()` 裸 SQL；后台任务单元测试验证传入无 tenant_id 上下文时抛出异常 |
| **AC-4.9**：管理员邀请用户 → 发送邀请链接 → 用户接受邀请设置密码 → 激活成功 | `test_user_invite_flow.py::test_invite_user_sends_invitation`<br>`test_user_invite_flow.py::test_accept_invitation_creates_user` |
| **AC-4.10**：自定义角色权限不能超出创建者自身权限范围 | `test_user_invite_flow.py::test_invite_user_exceeds_creator_permissions`<br>`test_rbac_enforcement.py::test_role_switch_cannot_exceed`<br>`test_role_service.py` 中验证 `_validate_permissions_subset` |
| **AC-4.11**：管理员切换角色视角后页面内容按所选角色过滤 | `test_rbac_enforcement.py::test_role_switch_to_viewer`（后端 API + 前端集成测试） |
| **AC-4.12**：库级别权限：无权限知识库对应域在域分发时被裁剪 | `test_dual_layer_filter.py::test_domain_crop_excludes_unauthorized_kb` |
| **AC-4.13**：文档级别权限：同一知识库内不同角色检索到不同文档子集 | `test_dual_layer_filter.py::test_doc_acl_filter_returns_subset`<br>`test_dual_layer_filter.py::test_public_kb_visible_to_viewer`<br>`test_dual_layer_filter.py::test_private_kb_invisible_to_viewer` |
| **AC-4.13a**：`ACLFilterBuilder` 三种后端实现一致——同一用户同一知识库，Chroma/ES/Milvus 返回相同文档子集 | `test_acl_filter_consistency.py::test_chroma_es_milvus_same_result`<br>`test_acl_filter_builder.py::test_three_backends_same_filter_logic` |
| **AC-4.14**：权限变更后 30 秒内相关缓存失效 | 单元测试：模拟角色权限更新，验证 Redis 缓存 key 在 30s 内被失效；验证 ConfigCache/EventBus 发布缓存失效事件 |
| **AC-4.15**：所有搜索方式强制启用双层权限过滤 | `test_dual_layer_filter.py` 全部场景；代码级验证（所有检索节点必须调用 `ACLFilterBuilder.build_filter`，通过 AST 扫描或 mock 验证） |

---

### 附录 A：SQLAlchemy 模型文件清单

新模型文件位于 `backend/src/models/permission/`：

```
backend/src/models/permission/
├── __init__.py
├── tenant.py           # Tenant ORM 模型
├── user.py             # User ORM 模型
├── role.py             # Role ORM 模型
├── user_role.py        # UserRole 关联模型
├── user_invitation.py  # UserInvitation ORM 模型
├── god_mode_audit_log.py     # GodModeAuditLog ORM 模型
├── permission_audit_log.py   # PermissionAuditLog ORM 模型
├── tenant_audit_log.py       # TenantAuditLog ORM 模型
├── tenant_deletion_snapshot.py # TenantDeletionSnapshot ORM 模型
└── enums.py            # TenantStatus, UserStatus, GodModeAction 等枚举
```

**模型必须遵循的约束（参考 `backend/src/models/monitor.py` 模式）：**
- 所有 Enum 字段必须使用 `values_callable=lambda obj: [e.value for e in obj]`
- `deleted_at` 使用 `DateTime, nullable=True`
- `created_at` 使用 `DateTime, server_default=func.now()`
- `updated_at` 使用 `DateTime, server_default=func.now(), onupdate=func.now()`
- JSON 字段使用 `mapped_column(JSON, nullable=False)`
- 所有 `__tablename__` 使用蛇形命名（如 `god_mode_audit_log`）
- 主键 `id` 使用 `mapped_column(String(36), primary_key=True, default=uuid4_str)`

### 附录 B：Pydantic Schema 文件清单

新 Schema 文件位于 `backend/src/schemas/permission/`：

```
backend/src/schemas/permission/
├── __init__.py
├── tenant.py           # CreateTenantInput, UpdateTenantInput, TenantSummary, TenantDetail...
├── user.py             # LoginInput, LoginResult, InviteUserInput, AcceptInvitationInput...
├── role.py             # CreateRoleInput, UpdateRoleInput, RoleDetail...
├── god_mode.py         # ImpersonateRequest, GodModeEnterResult...
├── jwt.py              # JWTClaims, TokenResponse...
└── common.py           # PaginatedResult, ResourceLimits, ...
```

**Schema 必须遵循的约束：**
- 继承 `BaseModel`，禁止继承 ORM 模型
- 使用 `class Config: from_attributes = True` 支持 ORM 对象转换
- 所有字段使用中文 `Field(description=...)` 注解

### 附录 C：DI 注册

在 `backend/src/core/di_container.py` 中新增 `PermissionModule` 类：

```python
class PermissionModule(Module):
    """权限与多租户依赖注入模块"""

    @singleton
    @provider
    def provide_tenant_repository(self) -> TenantRepository:
        return TenantRepository(async_session_factory)

    @singleton
    @provider
    def provide_user_repository(self) -> UserRepository:
        return UserRepository(async_session_factory)

    # ... 其余 10 个 Repository 类推

    @singleton
    @provider
    def provide_jwt_service(self) -> JWTService:
        return JWTService(
            secret_key=settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
        )

    @singleton
    @provider
    def provide_rbac_service(self, role_repository, user_roles_repository) -> RBACService:
        return RBACService(role_repository, user_roles_repository)

    # ... 其余 Service 类推

    @singleton
    @provider
    def provide_permission_facade(self, ...) -> PermissionFacade:
        return PermissionFacade(...)
```

注册到全局 Injector：`injector = Injector([..., PermissionModule()])`

### 附录 D：定时任务补充

在 `backend/src/core/scheduler.py` 中补充：

| 任务 | Cron | 说明 |
|------|------|------|
| `cleanup_expired_tenants` | `0 3 * * *`（每天 03:00） | 扫描 `deleted_at` 超过 30 天的租户，执行物理清理 |
| `cleanup_expired_snapshots` | `0 4 * * *`（每天 04:00） | 扫描 `expires_at` 超过当前时间的快照记录，清理文件 |
| `cleanup_expired_invitations` | `0 3 * * *`（每天 03:00） | 清理 `expires_at` 超过 7 天且未接受的邀请 |

---

### 附录 E：权限列表集中配置

```python
# backend/src/config/modules/permissions.py

AVAILABLE_PERMISSIONS = [
    {"slug": "kb:read",          "description": "查看知识库和文档",                         "group": "知识库"},
    {"slug": "kb:write",         "description": "创建和编辑知识库、上传文档",                "group": "知识库"},
    {"slug": "kb:delete",        "description": "删除知识库和文档",                          "group": "知识库"},
    {"slug": "kb:manage_acl",    "description": "管理知识库和文档的访问权限",                "group": "知识库"},
    {"slug": "pipeline:read",    "description": "查看管道配置",                              "group": "管道"},
    {"slug": "pipeline:write",   "description": "创建和编辑管道",                            "group": "管道"},
    {"slug": "pipeline:publish", "description": "发布管道到生产环境",                       "group": "管道"},
    {"slug": "search:execute",   "description": "执行搜索",                                 "group": "搜索"},
    {"slug": "search:stream",    "description": "使用流式搜索",                             "group": "搜索"},
    {"slug": "eval:read",        "description": "查看评估结果和报告",                       "group": "评估"},
    {"slug": "eval:write",       "description": "创建和运行评估",                           "group": "评估"},
    {"slug": "system:config",    "description": "管理系统配置",                             "group": "系统"},
    {"slug": "system:monitor",   "description": "查看监控数据",                             "group": "系统"},
]

ALL_PERMISSION_SLUGS = [p["slug"] for p in AVAILABLE_PERMISSIONS]
```

### 附录 F：错误码汇总

| 错误码 | HTTP 状态 | error_code | 说明 |
|--------|----------|------------|------|
| 11001 | 401 | `INVALID_TOKEN` | Token 无效或格式错误 |
| 11002 | 401 | `TOKEN_EXPIRED` | Token 已过期（但在可刷新窗口内） |
| 11003 | 401 | `GOD_MODE_EXPIRED` | God Mode 会话超时 |
| 12001 | 403 | `TENANT_DISABLED` | 租户已停用 |
| 12002 | 403 | `INSUFFICIENT_PERMISSIONS` | 权限不足 |
| 12003 | 412 | `GOD_MODE_WRITE_CONFIRM_REQUIRED` | God Mode 写操作需二次确认 |
| 12004 | 403 | `TENANT_ARCHIVED` | 租户已归档 |
| 12005 | 403 | `TENANT_QUOTA_EXCEEDED` | 租户配额超限 |
| 13001 | 400 | `ROLE_PERMISSION_EXCEEDS` | 角色权限超出操作者权限 |
| 13002 | 400 | `CANNOT_MODIFY_BUILTIN_ROLE` | 不可修改内置角色 |
| 13003 | 400 | `CANNOT_DELETE_BUILTIN_ROLE` | 不可删除内置角色 |
| 13004 | 400 | `ROLE_SLUG_EXISTS` | 角色标识已存在 |
| 13005 | 400 | `ROLE_HAS_USERS` | 角色仍有用户引用 |
| 13006 | 400 | `INVALID_PERMISSION` | 权限列表中包含未知权限 |
| 14001 | 401 | `INVALID_CREDENTIALS` | 用户名或密码错误 |
| 14002 | 403 | `USER_DISABLED` | 用户已被禁用 |
| 14003 | 400 | `CANNOT_DISABLE_SELF` | 不能禁用自己 |
| 14004 | 400 | `CANNOT_DELETE_SELF` | 不能删除自己 |
| 14005 | 400 | `CANNOT_DELETE_LAST_ADMIN` | 不能删除租户最后一个管理员 |
| 15001 | 400 | `EMAIL_ALREADY_INVITED` | 该邮箱已有未过期的邀请 |
| 15002 | 400 | `EMAIL_ALREADY_MEMBER` | 该邮箱已是租户成员 |
| 15003 | 400 | `INVITATION_EXPIRED` | 邀请已过期 |
| 15004 | 400 | `INVITATION_ALREADY_ACCEPTED` | 邀请已被接受 |
| 15005 | 404 | `INVITATION_NOT_FOUND` | 邀请不存在 |
| 16001 | 409 | `TENANT_SLUG_EXISTS` | 租户标识已存在 |
| 16002 | 404 | `TENANT_NOT_FOUND` | 租户不存在 |
| 16003 | 400 | `TENANT_NOT_ACTIVE` | 操作需要租户为 active 状态 |
| 16004 | 400 | `TENANT_SLUG_MISMATCH` | 确认标识不匹配 |
| 16005 | 400 | `TENANT_ALREADY_DELETED` | 租户已被删除 |
| 16006 | 400 | `TENANT_CANNOT_RESTORE` | 租户无法恢复 |
| 16007 | 400 | `CANNOT_ACTIVATE_DELETED` | 已删除租户不可直接启用 |
| 16008 | 400 | `TENANT_USER_LIMIT_REACHED` | 租户用户数已达上限 |
| 17001 | 409 | `GOD_MODE_CONCURRENT` | 已有超管在此租户 God Mode 中 |
| 17002 | 400 | `GOD_MODE_EXTEND_LIMIT` | God Mode 续期次数已达上限 |
| 17003 | 404 | `USER_NOT_FOUND` | 用户不存在 |
| 17004 | 404 | `ROLE_NOT_FOUND` | 角色不存在 |
