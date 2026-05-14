# Phase 1：权限与多租户

> **定位**：实现 RAG 平台化的认证、授权、租户隔离、RBAC 权限体系。所有后续 Phase 的数据访问和 API 调用依赖本阶段的中间件和 Repository 基类。
> **依赖**：Phase 0（基础设施搭建）——需要项目骨架、数据库 Schema (`tenants`/`users`/`roles`/`user_roles`/`user_invitations`/`god_mode_audit_log`/`tenant_deletion_snapshots`/`permission_audit_log`/`tenant_audit_log`)、统一响应与异常基础设施就绪。
> **参考文档**：
> - [实施清单 Phase 1](../../implementation-checklist.md#phase-1权限与多租户)
> - [代码级实施方案 §3](../../implementation-plan-detail.md#3.1 Repository 基类改造（最关键）)
> - [实施计划 §四](../../implementation-plan.md#四后端改动权限与多租户需求文档-04)
> - [需求文档 04](../../requirements/04-permission-and-multi-tenancy.md)
> - [核心目标 §三](../../core-objectives.md#三双层权限控制库级别--文档级别全局强制)
> **代码规范**：全部遵循 CLAUDE.md 编码规范（实体类在 schemas/、类≤500行、全中文注释、零迁移）。

---

## 1. 阶段目标

建立平台级认证与权限基础设施：

1. **超管体系**：平台级超管 (superadmin)，不属于任何租户，JWT 中无 `tenant_id`。可创建/停用/归档/删除租户、进入任意租户 God Mode。
2. **租户隔离**：共享数据库实例，通过 `tenant_id` 行级过滤实现逻辑隔离。所有数据访问自动注入 `WHERE tenant_id = :current_tenant_id`。
3. **租户内 RBAC**：三个内置角色 (admin/editor/viewer) + 自定义角色 CRUD。角色→权限映射，JWT 携带 roles 数组。
4. **双层权限注入点**：库级别（域分发前裁剪不可见知识库对应域）和文档级别（检索时注入 doc_acl 向量过滤条件）的权限注入位置在本阶段建立，实际过滤逻辑在 Phase 2 (知识库管理) 和 Phase 3 (管道引擎) 中完成。
5. **God Mode**：超管可进入任意租户上下文操作，30min 会话超时，全量操作审计，写操作二次确认，并发限制（同一租户仅允许一个超管 God Mode）。

---

## 2. 任务清单

### 2.1 1.1 认证核心

| # | 文件 | 任务 | 关键逻辑 |
|---|------|------|---------|
| 1 | `core/auth/password.py` | 密码哈希/验证 | bcrypt 哈希，`hash_password(raw)` 返回 hash，`verify_password(raw, hashed)` 返回 bool |
| 2 | `core/auth/jwt_service.py` | JWT 签发/验证/刷新 | `issue(payload)` 签发，`decode(token)` 验证并返回 payload，`refresh(old_token)` 刷新。区分超管 (无 `tenant_id`) 和租户用户 (有 `tenant_id`) |
| 3 | `core/auth/defaults.py` | 内置角色定义 + 默认权限集 | `DEFAULT_ROLES`: admin (全部权限), editor (kb:rw + pipeline:rw + eval:rw + search:ex), viewer (kb:r + pipeline:r + search:ex)。`PERMISSION_SET`: 所有可用权限点的完整定义 |
| 4 | `core/auth/exceptions.py` | 认证授权异常类 | `AuthenticationError`, `AuthorizationError`, `TenantSuspendedError`，全部继承 `AppException` |
| 5 | `core/auth/invitation.py` | 邀请链接生成/验证/过期处理 | `generate_token(tenant_id, email, roles)` → 带 24h 过期的 token，`verify(token)` → 返回 payload 或抛出过期/无效 |

### 2.2 1.2 中间件

| # | 文件 | 任务 | 关键逻辑 |
|---|------|------|---------|
| 6 | `middleware/auth_middleware.py` | JWT 认证中间件 | 从 `Authorization: Bearer <token>` 提取 token → 验证 → 注入 `request.state.user_id`, `request.state.tenant_id`, `request.state.roles`, `request.state.is_superadmin`。豁免路径：`/health`, `/metrics`, `/api/v1/auth/login`, `/api/v1/users/accept-invitation` |
| 7 | `middleware/tenant_middleware.py` | 租户状态中间件 | 检查 `request.state.tenant_id` 对应的租户状态：active→放行，disabled→403 TenantSuspendedError，archived→403。检查配额是否耗尽（可选告警） |

### 2.3 1.3 Repository 基类改造

| # | 文件 | 任务 | 关键逻辑 |
|---|------|------|---------|
| 8 | `repository/base.py` | 基类改造 | 见 §3.1 详细描述。新增 `_get_session(tenant_id)`（必须传 tenant_id，None 抛 `MissingTenantContextError`）、`_get_admin_session()`（超管专用，不做 tenant_id 过滤）、`_add_tenant_filter(stmt, model, tenant_id)`（自动注入 WHERE 条件） |
| 9 | `repository/auth/tenant_repo.py` | 租户 CRUD | 继承 BaseRepository。create/update/delete/list/find_by_slug。删除/归档操作使用 `_get_admin_session()` |
| 10 | `repository/auth/user_repo.py` | 用户 CRUD + 角色关联 | findByEmail, findByUsername, listByTenant, assignRole, removeRole, disable |
| 11 | `repository/auth/role_repo.py` | 角色 CRUD | create/listByTenant/update/delete。删除时检查引用（`user_roles` 表中是否仍有关联） |
| 12 | `repository/auth/invitation_repo.py` | 邀请管理 | create (含 token, expires_at), findByToken, markAccepted, findPendingByTenant |
| 13 | `repository/auth/audit_repo.py` | 审计日志统一写入 | 统一接口：`log_god_mode_action()`, `log_permission_change()`, `log_tenant_action()`，分别写 `god_mode_audit_log`/`permission_audit_log`/`tenant_audit_log` |

### 2.4 1.4 数据模型

| # | 文件 | 任务 | 关键字段 |
|---|------|------|---------|
| 14 | `models/tenant.py` | Tenant, TenantQuota | Tenant: id, name, slug, status(active/disabled/archived/deleted), resource_limits(JSON), deleted_at, created_at, updated_at。TenantQuota: tenant_id, kb_limit, doc_limit, user_limit, storage_limit, search_qps_limit |
| 15 | `models/user.py` | User, UserRole | User: id, tenant_id(NULL=超管), username, password_hash, email, status(active/disabled), deleted_at, created_at。UserRole: user_id, role_id |
| 16 | `models/role.py` | Role | id, tenant_id, name, permissions(JSON), is_builtin(bool), created_at |
| 17 | `models/invitation.py` | UserInvitation | id, tenant_id, email, roles(JSON), token, expires_at, accepted_at, created_by |
| 18 | `models/audit.py` | GodModeAuditLog, PermissionAuditLog, TenantAuditLog, TenantDeletionSnapshot | GodModeAuditLog: tenant_id, actor_id, action, target_type, target_id, details(JSON), session_started_at。PermissionAuditLog: tenant_id, actor_id, action, target_type, target_id, old_value, new_value。TenantAuditLog: tenant_id, actor_id, action, details。TenantDeletionSnapshot: tenant_id, snapshot_path, status(pending/ready/expired), expires_at |

### 2.5 1.5 Schemas

| # | 文件 | 任务 | 实体类 |
|---|------|------|--------|
| 19 | `schemas/auth/tenant.py` | 租户相关实体 | `TenantCreate` (name, slug, admin_user: AdminUserCreate, quotas: QuotaConfig), `TenantRead` (id, name, slug, status, resource_limits, user_count, storage_usage, created_at), `TenantUpdate`, `TenantList`, `QuotaUsage`, `AdminUserCreate` (username, email, password) |
| 20 | `schemas/auth/user.py` | 用户相关实体 | `UserCreate`, `UserRead` (id, username, email, status, roles, created_at), `UserInvite` (email, roles: list[str]), `UserAcceptInvitation` (token, password), `UserUpdate` (roles, status) |
| 21 | `schemas/auth/role.py` | 角色相关实体 | `RoleCreate` (name, permissions: list[str]), `RoleRead` (id, name, permissions, is_builtin, user_count), `RoleUpdate`, `PermissionList` (permissions: list[PermissionItem])。`PermissionItem`: permission_code, category, description |
| 22 | `schemas/auth/auth.py` | 认证相关实体 | `LoginRequest` (username, password), `LoginResponse` (access_token, refresh_token, user: UserRead, tenant: TenantRead), `TokenRefresh` (refresh_token) |
| 23 | `schemas/auth/god_mode.py` | God Mode 实体 | `GodModeEnter` (tenant_id), `GodModeSession` (access_token, expires_at, tenant_id, actor_id), `GodModeAuditLog` (id, tenant_id, actor_id, action, target_type, target_id, details, created_at) |

### 2.6 1.6 服务层

| # | 文件 | 任务 | 关键逻辑 |
|---|------|------|---------|
| 24 | `service/auth/provisioning.py` | 租户初始化 (Provisioning) | 见 §3.4。事务性：DB 写入 tenants + 创建存储目录 + 插入默认 admin/editor/viewer 角色 + 创建初始管理员用户 + 绑定 admin 角色 + 记录配额。任一步骤失败则整体回滚 |
| 25 | `service/auth/tenant_service.py` | 租户 CRUD + 生命周期管理 | create/provision → get/list → update → archive/restore → soft_delete (30 天保留期) → force_delete (物理清理前生成快照)。状态机：active ⇄ disabled ⇄ archived ⇄ deleted |
| 26 | `service/auth/user_service.py` | 用户管理 | invite (生成 token + 24h 过期 + 发邮件/返回链接) → accept_invitation (验证 token → 创建 User + UserRole → 标记邀请已接受) → assign_role → remove_role → disable → delete |
| 27 | `service/auth/role_service.py` | 角色管理 | create (权限不能超出创建者自身权限) → update (检查引用和权限范围) → delete (检查 user_roles 引用) → get_permissions (返回可用权限列表)。内置角色不可删除、不可改名 |
| 28 | `service/auth/god_mode_service.py` | God Mode 服务 | 见 §3.5。enter (检查并发 → 创建 session → 签发临时 JWT → 记录 audit log) → exit (清除 session → 记录 audit log) → audit_operation (每次写操作写入 audit log) → check_timeout |

### 2.7 1.7 控制器

| # | 文件 | 路由前缀 | 端点 | 权限要求 |
|---|------|---------|------|---------|
| 29 | `controller/auth/auth_controller.py` | `/api/v1/auth` | `POST /login`, `POST /refresh`, `POST /switch-role` | 无认证（login/refresh 在中间件豁免列表中）；switch-role 需认证 |
| 30 | `controller/auth/tenant_controller.py` | `/api/v1/admin/tenants` | `POST /` (create), `GET /` (list), `GET /{id}` (get), `PUT /{id}` (update), `PUT /{id}/archive`, `PUT /{id}/restore`, `DELETE /{id}` (soft delete), `GET /{id}/users`, `POST /{id}/impersonate` (God Mode 进入), `POST /{id}/impersonate/extend` (God Mode 延长), `DELETE /{id}/impersonate` (God Mode 退出), `GET /{id}/god-mode-log` | 超管 (is_superadmin=True) |
| 31 | `controller/auth/user_controller.py` | `/api/v1/users` | `GET /`, `POST /invite`, `POST /accept-invitation`, `PUT /{id}`, `DELETE /{id}` | 租户用户 (admin 角色可管理用户；accept-invitation 豁免认证) |
| 32 | `controller/auth/role_controller.py` | `/api/v1/roles` | `GET /`, `POST /`, `PUT /{id}`, `DELETE /{id}`, `GET /permissions` | 租户用户 (admin 角色可管理角色) |

### 2.8 1.8 RBAC

| # | 文件 | 任务 | 关键逻辑 |
|---|------|------|---------|
| 33 | `core/auth/rbac.py` | 权限检查引擎 | `check_permission(user_roles, required_permission)` → bool。角色→权限映射从 `roles.permissions` JSON 读取，支持通配符 (`*` = 全部权限)。`get_visible_resources(user_roles, resources, visibility_field)` → 过滤资源列表。超管 (is_superadmin) 直接返回 True |
| 34 | `core/auth/tenant_context.py` | 租户上下文注入 | 从 `request.state` 提取 tenant_id/user_id/roles/is_superadmin，构造 `TenantContext` 对象。提供 `get_current_context()` 获取当前请求上下文（基于 contextvars，支持异步传播）。God Mode 下 context 标记 `is_god_mode=True` |

---

## 3. 关键实现细节

### 3.1 Repository 基类：tenant_id 自动注入机制

**设计原则**：所有数据访问必须带租户上下文。禁止裸 SQL 和缺少 `tenant_id` 的查询。通过 Python 层强制约束（一期），二期可叠加 MySQL Row-Level Security。

**核心接口**：

```python
class BaseRepository:
    """所有 Repository 的基类。自动注入 tenant_id 过滤。"""

    def __init__(self, session_factory: async_session_factory):
        self._session_factory = session_factory

    @asynccontextmanager
    async def _get_session(self, tenant_id: str):
        """获取数据库 session。
        
        tenant_id 必须显式传入。无 tenant_id 时抛出 MissingTenantContextError。
        这是防止跨租户泄漏的第一道防线——在 Python 层直接阻断。
        """
        if tenant_id is None:
            raise MissingTenantContextError(
                "数据访问必须提供 tenant_id。超管操作请使用 _get_admin_session()"
            )
        async with self._session_factory() as session:
            yield session

    @asynccontextmanager
    async def _get_admin_session(self):
        """超管专用 session。不做 tenant_id 过滤。
        
        使用限制：
        - 仅超管 API (/api/v1/admin/*) 的 Repository 调用可使用
        - 调用方必须在代码注释中说明为何需要跨租户访问
        - 审计日志自动记录使用此方法的调用栈
        """
        async with self._session_factory() as session:
            yield session

    async def _add_tenant_filter(self, stmt, model, tenant_id: str):
        """为查询语句自动添加 tenant_id 过滤条件。
        
        如果 model 没有 tenant_id 属性（如 roles 的某些查询），跳过过滤。
        """
        if hasattr(model, 'tenant_id'):
            stmt = stmt.where(model.tenant_id == tenant_id)
        return stmt
```

**_get_admin_session 逃逸舱口使用规则**：
- 仅以下模块允许使用：`service/auth/tenant_service.py`（租户 CRUD）、`service/auth/god_mode_service.py`（审计日志写入）
- 每次使用必须在 commit message 中说明原因
- CI 静态扫描 `_get_admin_session` 的调用位置，若发现未授权模块调用则阻断

**子类使用模式**：

```python
class UserRepository(BaseRepository):
    async def list_by_tenant(self, tenant_id: str) -> list[User]:
        async with self._get_session(tenant_id) as session:
            stmt = select(User).where(User.deleted_at.is_(None))
            stmt = await self._add_tenant_filter(stmt, User, tenant_id)
            result = await session.execute(stmt)
            return result.scalars().all()
```

### 3.2 JWT Payload 结构

**超管 JWT（无 tenant_id）**：
```json
{
  "sub": "superadmin_user_id",
  "user_id": "sa_abc123",
  "tenant_id": null,
  "roles": [],
  "is_superadmin": true,
  "exp": 1715000000,
  "iat": 1714900000
}
```

**租户用户 JWT（有 tenant_id）**：
```json
{
  "sub": "user_id",
  "user_id": "usr_xyz789",
  "tenant_id": "t_renhe",
  "roles": ["admin"],
  "is_superadmin": false,
  "exp": 1715000000,
  "iat": 1714900000
}
```

**God Mode 临时 JWT**：
```json
{
  "sub": "superadmin_user_id",
  "user_id": "sa_abc123",
  "tenant_id": "t_renhe",
  "roles": [],
  "is_superadmin": true,
  "is_god_mode": true,
  "god_mode_entered_at": "2026-05-14T10:00:00Z",
  "exp": 1715001800,
  "iat": 1715000000
}
```

**关键区分点**：
- 超管登录 JWT：`tenant_id=null, is_superadmin=true` → 只能访问 `/api/v1/admin/*` 路由
- God Mode JWT：`tenant_id=有值, is_superadmin=true, is_god_mode=true` → 访问租户资源但无视权限过滤
- 租户用户 JWT：`tenant_id=有值, is_superadmin=false` → 正常权限过滤

### 3.3 内置角色与权限定义

**三个内置角色**（创建租户时自动插入，不可删除、不可改名）：

| 角色 | permissions |
|------|-------------|
| `admin` | `["kb:read", "kb:write", "kb:delete", "kb:manage_acl", "pipeline:read", "pipeline:write", "pipeline:delete", "pipeline:publish", "eval:read", "eval:write", "eval:delete", "search:execute", "search:stream", "system:config", "system:monitor", "user:manage", "role:manage"]` |
| `editor` | `["kb:read", "kb:write", "pipeline:read", "pipeline:write", "eval:read", "eval:write", "search:execute", "search:stream"]` |
| `viewer` | `["kb:read", "pipeline:read", "search:execute", "search:stream"]` |

**完整权限代码表**：

| 权限代码 | 类别 | 描述 |
|---------|------|------|
| `kb:read` | 知识库 | 查看知识库及其文档 |
| `kb:write` | 知识库 | 创建/编辑知识库、上传文档 |
| `kb:delete` | 知识库 | 删除知识库及文档 |
| `kb:manage_acl` | 知识库 | 管理知识库和文档的 ACL 权限 |
| `pipeline:read` | 管道 | 查看管道配置和历史版本 |
| `pipeline:write` | 管道 | 创建/编辑管道 |
| `pipeline:delete` | 管道 | 删除管道 |
| `pipeline:publish` | 管道 | 发布/停用管道 URL |
| `eval:read` | 评估 | 查看评估结果 |
| `eval:write` | 评估 | 运行评估、上传测试数据 |
| `eval:delete` | 评估 | 删除评估历史 |
| `search:execute` | 搜索 | 执行搜索 |
| `search:stream` | 搜索 | 执行 SSE 流式搜索 |
| `system:config` | 系统 | 修改租户级系统配置 |
| `system:monitor` | 系统 | 查看监控指标 |
| `user:manage` | 用户 | 邀请/禁用/删除用户 |
| `role:manage` | 角色 | 创建/编辑/删除角色的权限范围 |

### 3.4 租户 Provisioning：事务性初始化流程

```python
class TenantProvisioningService:
    """租户初始化服务。创建租户时自动执行全部初始化步骤。"""

    async def provision(self, data: TenantCreate) -> TenantProvisionResult:
        """创建租户的完整流程（同步事务）。
        
        步骤顺序不可变更——每步依赖前一步的产物。
        任一步骤失败整体回滚（DB 事务 + 文件系统清理）。
        """
        async with self._session_factory() as session:
            async with session.begin():
                # 1. 插入 tenants 记录
                tenant = Tenant(
                    id=generate_id(),
                    name=data.name,
                    slug=data.slug,
                    status="active",
                    resource_limits=data.quotas.model_dump(),
                )
                session.add(tenant)
                await session.flush()  # 立即写入获取 tenant.id

                # 2. 创建存储目录（DB 事务外，失败需手动清理）
                try:
                    self._create_storage_dirs(tenant.id)
                except Exception as e:
                    raise TenantProvisioningError(f"存储目录创建失败: {e}")

                # 3. 插入默认角色
                for role_def in DEFAULT_ROLES:
                    session.add(Role(
                        id=generate_id(),
                        tenant_id=tenant.id,
                        name=role_def["name"],
                        permissions=role_def["permissions"],
                        is_builtin=True,
                    ))
                await session.flush()

                # 4. 创建初始管理员用户
                admin_user = User(
                    id=generate_id(),
                    tenant_id=tenant.id,
                    username=data.admin_user.username,
                    email=data.admin_user.email,
                    password_hash=hash_password(data.admin_user.password),
                    status="active",
                )
                session.add(admin_user)
                await session.flush()

                # 5. 关联管理员 → admin 角色
                admin_role = await self._get_role_by_name(
                    session, tenant.id, "admin"
                )
                session.add(UserRole(
                    user_id=admin_user.id,
                    role_id=admin_role.id,
                ))

                # 6. 记录配额（冗余存储，方便查询，与 tenants.resource_limits 保持同步）
                session.add(TenantQuota(
                    tenant_id=tenant.id,
                    kb_limit=data.quotas.kb_limit,
                    doc_limit=data.quotas.doc_limit,
                    user_limit=data.quotas.user_limit,
                    storage_limit=data.quotas.storage_limit,
                    search_qps_limit=data.quotas.search_qps_limit,
                ))

            # 事务成功提交
            # 7. 写入租户操作审计日志
            await self._log_tenant_created(tenant.id)

            return TenantProvisionResult(
                tenant_id=tenant.id,
                tenant_slug=tenant.slug,
                admin_user_id=admin_user.id,
            )
```

**存储目录结构**：
```
storage/{tenant_id}/
├── vectors/          # 向量存储数据
├── documents/        # 上传的原始文档
├── snapshots/        # 数据导出快照
└── exports/          # 临时导出文件
```

### 3.5 God Mode：进入/退出/审计/超时

**完整生命周期**：

```
超管在租户详情页
  │
  ├─ 点击 [进入此租户]
  │     │
  │     ├─ 检查是否已有其他超管在此租户 God Mode → 有则提示并阻止
  │     ├─ 签发 30min 过期临时 JWT（is_god_mode=true, tenant_id=目标租户）
  │     ├─ 写入 god_mode_audit_log: action="god_mode_enter"
  │     └─ 前端跳转到租户首页 + 顶部显示 God Mode 横幅
  │
  ├─ God Mode 期间操作
  │     │
  │     ├─ 每次写操作 → 弹窗二次确认 "当前以超管身份操作，此操作不可撤销"
  │     ├─ 确认后 → 执行操作 → 写入 god_mode_audit_log
  │     └─ 每 5 分钟检查 session 是否即将过期 (剩余 < 5min)
  │           │
  │           └─ 弹窗提示 "God Mode 即将过期，是否续期？"
  │                 ├─ 是 → 续期 30min（仅一次）
  │                 └─ 否/超时 → 自动退出
  │
  └─ 退出 (主动点击或超时)
        │
        ├─ 写入 god_mode_audit_log: action="god_mode_exit"
        ├─ 清除 Redis 中的 session
        └─ 前端跳转回超管租户列表
```

**并发限制实现**：
- Redis key: `god_mode:{tenant_id}` → value: `superadmin_user_id` + 过期时间 = session 过期时间
- enter 时 SET NX（仅当 key 不存在时设置），失败则返回 "已有其他超管在此租户的 God Mode 中"
- exit 或超时时 DEL key

**审计日志格式**：
```json
{
  "id": "gmal_xxx",
  "tenant_id": "t_renhe",
  "actor_id": "sa_abc123",
  "action": "kb_delete",
  "target_type": "knowledge_base",
  "target_id": "kb_001",
  "details": {
    "kb_name": "心血管指南库",
    "document_count": 1450,
    "reason": "超管清理过期知识库"
  },
  "session_started_at": "2026-05-14T10:00:00Z",
  "created_at": "2026-05-14T10:15:32Z"
}
```

### 3.6 租户状态机

```
  [创建] → active
              │
              ├─→ disabled  (停用：禁止登录 + API 403，数据保留)
              │     │
              │     └─→ active  (重新启用)
              │
              ├─→ archived  (归档：禁止一切访问，数据保留，不计配额)
              │     │
              │     └─→ active  (恢复)
              │
              └─→ deleted   (软删除：deleted_at 标记，30 天保留期)
                    │
                    ├─→ active  (恢复，需在保留期内)
                    │
                    └─→ [物理清理]  (30 天后自动：清理 DB 行 + 向量存储 + 文件)
                           │
                           └─→ 清理前自动生成 TenantDeletionSnapshot
```

**状态检查时机**：
- `AuthMiddleware`: 检查 JWT 是否有效
- `TenantMiddleware`: 检查 `tenant.state` → disabled/archived → 返回 403
- API 层面：`tenant_service.soft_delete` → 写 `deleted_at` + 创建 `TenantDeletionSnapshot`
- 定时任务：每日扫描 `deleted_at < now() - 30 days` 的租户 → 执行物理清理

### 3.7 RBAC 权限检查流程

```
API 请求进入
  │
  ├── AuthMiddleware: 解析 JWT → request.state (user_id, tenant_id, roles, is_superadmin)
  │
  ├── TenantMiddleware: 检查租户状态
  │
  └── 控制器方法
        │
        ├─ 声明所需权限 (装饰器或显式调用)
        │     @require_permission("kb:read")
        │     async def get_knowledge_base(self, ...):
        │
        └─ rbac.check_permission(request.state.roles, "kb:read")
              │
              ├─ is_superadmin? → 直接返回 True
              │
              ├─ 加载用户所有角色 → 合并 permissions 列表 → 去重
              │
              ├─ 检查是否包含通配符 "*" → True
              │
              └─ 检查是否包含精确匹配的 permission → True/False
                    │
                    └─ False → raise AuthorizationError("无此操作权限: kb:read")
```

**权限校验层级**：
1. **路由级**：中间件检查认证状态（已登录/未登录）
2. **端点级**：控制器方法声明所需权限，RBAC 引擎校验
3. **数据级**：Repository 基类自动注入 `tenant_id` 过滤，防止跨租户访问
4. **资源级**：知识库 visibility + 文档 doc_acl 在管道执行时注入（Phase 2/3 实现）

---

## 4. 测试策略

### 4.1 单元测试

| 测试模块 | 测试内容 | 预期结果 |
|---------|---------|---------|
| `test_jwt_service.py` | 签发超管 JWT → 验证 payload → 确认 `tenant_id=null, is_superadmin=true` | payload 正确 |
| `test_jwt_service.py` | 签发租户用户 JWT → 验证 payload → 确认 `tenant_id=有值, roles` 正确 | payload 正确 |
| `test_jwt_service.py` | 签发过期 JWT → 验证 → 抛出 `TokenExpiredError` | 异常正确抛出 |
| `test_jwt_service.py` | 签发 God Mode JWT → 验证 payload → 确认 `is_god_mode=true, exp=30min` | payload 正确，过期时间正确 |
| `test_password.py` | `hash_password("test123")` → `verify_password("test123", hash)` → True | 验证通过 |
| `test_password.py` | `verify_password("wrong", hash)` → False | 验证失败 |
| `test_rbac.py` | admin 角色检查 `kb:read` → True | 全部权限通过 |
| `test_rbac.py` | viewer 角色检查 `kb:write` → False | 越权被拒绝 |
| `test_rbac.py` | 多角色用户 (viewer+自定义) 检查 `kb:write` → 取决于自定义角色 | 权限合并正确 |
| `test_rbac.py` | 超管 `is_superadmin=True` 检查任意权限 → True | 超管免检查 |
| `test_tenant_context.py` | 从 mock Request 提取 context → 验证 `tenant_id, user_id, roles` 正确 | 上下文提取正确 |
| `test_invitation.py` | 生成邀请 token → 验证 → 确认 email, roles, tenant_id 正确 | token payload 正确 |
| `test_invitation.py` | 过期 token 验证 → 抛出 `InvitationExpiredError` | 异常正确抛出 |

### 4.2 集成测试

| 测试场景 | 步骤 | 验收标准 |
|---------|------|---------|
| **租户 Provisioning 完整流程** | 调用 `POST /api/v1/admin/tenants` 创建租户 → 验证 DB 中有 tenants/roles(3)/users(1)/user_roles(1)/tenant_quota(1) 记录 → 验证存储目录创建 → 验证初始管理员可登录 | 7 条记录存在，目录存在，管理员登录成功 |
| **租户 Provisioning 失败回滚** | Mock 存储目录创建失败 → 验证 DB 中无残留记录 | 事务回滚，DB 干净 |
| **租户软删除 + 恢复流程** | soft_delete → 验证 deleted_at 非空 + 快照生成 → 用户登录返回 403 → restore → 验证 deleted_at=NULL → 用户可登录 | 删除/恢复状态正确，快照存在 |
| **用户邀请 → 激活完整流程** | admin 邀请 email → 生成 token → 用户携带 token 设置密码 → 验证 User 创建 + UserRole 绑定 + 邀请标记 accepted → 新用户可登录 | 用户创建完成，角色正确，可登录 |
| **God Mode 进入 → 操作 → 退出** | 超管 POST `/tenants/{id}/impersonate` → 获取临时 JWT → 用临时 JWT 访问租户资源（无视 visibility/doc_acl）→ 执行写操作（需二次确认） → POST exit → 验证 session 清除 | 全流程无权限拦截，审计日志完整 |
| **God Mode 并发限制** | 超管 A 进入租户 God Mode → 超管 B 尝试进入同一租户 → 返回 409 Conflict | 并发限制生效 |
| **God Mode 超时** | 超管进入 God Mode → 等待 30min → 再次请求 → 返回 401 Token 过期 | 超时自动退出 |
| **God Mode 写操作审计** | 超管在 God Mode 中删除知识库 → 验证 `god_mode_audit_log` 表中有 `action=kb_delete, target_type=knowledge_base, target_id=kb_id, details` 记录 | 审计日志完整 |
| **RBAC 权限拒绝** | viewer 角色尝试 POST `/api/v1/knowledge-bases` → 返回 403 AuthorizationError (error_code=`FORBIDDEN`) | 权限检查生效 |
| **跨租户隔离** | 租户 A 的用户尝试访问租户 B 的知识库（通过修改请求中的 kb_id） → Repository 自动过滤 → 返回 404（不是 403，防止信息泄漏） | 跨租户数据隔离 |
| **租户禁用** | admin 停用租户 → 该租户用户尝试登录 → 返回 403 TenantSuspendedError → 超管仍可查看该租户信息 | 禁用状态正确阻止访问 |
| **角色删除引用检查** | admin 审批角色有 5 个用户 → 尝试删除角色 → 返回 409 Conflict (提示仍有用户引用) | 引用检查生效 |
| **自定义角色权限不可越权** | editor 角色尝试创建"超管"角色（权限范围超过 editor） → 返回 403 AuthorizationError | 权限范围约束生效 |
| **内置角色不可删除** | admin 尝试 DELETE `/roles/{admin_role_id}` → 返回 403 (is_builtin=true) | 内置角色保护 |

### 4.3 关键测试场景（≥ 8）

1. **超管创建租户全流程**：创建租户 → 验证 5 类记录 + 目录 + 登录
2. **租户用户正常登录 + 权限校验**：登录 → 获取 JWT → 访问资源 → 权限检查
3. **不同角色权限边界**：admin/editor/viewer 分别测试各权限点的通过/拒绝
4. **跨租户数据不可见**：租户 A 用户访问租户 B 资源 → 404（不暴露存在性）
5. **God Mode 全生命周期**：进入 → 操作 → 审计 → 超时 → 退出
6. **God Mode 写操作二次确认**：弹窗交互 + 审计日志记录
7. **租户状态机流转**：active → disabled → active → archived → active → deleted (soft) → restore → deleted (soft) → 物理清理
8. **邀请-激活用户闭环**：邀请 → token 过期重发 → 接受邀请设置密码 → 登录
9. **Repository 基类 MissingTenantContextError**：后台任务未传 tenant_id → 抛出异常
10. **权限变更后缓存失效**：修改角色权限 → 验证相关语义缓存 key 在 30s 内被删除

---

## 5. 验收检查点

### 5.1 认证与中间件

- [ ] V-1.1：`AuthMiddleware` 正确解析 `Authorization: Bearer <token>`，注入 `request.state` 的 4 个字段 (user_id, tenant_id, roles, is_superadmin)
- [ ] V-1.2：豁免路径 (`/health`, `/metrics`, `/api/v1/auth/login`, `/api/v1/users/accept-invitation`) 不要求认证
- [ ] V-1.3：无效 Token 返回 401 `InvalidTokenError`，过期 Token 返回 401 `TokenExpiredError`
- [ ] V-1.4：`TenantMiddleware` 正确检查租户状态：disabled → 403 `TenantSuspendedError`，archived → 403
- [ ] V-1.5：超管 JWT (无 tenant_id) 通过认证，`is_superadmin=True`
- [ ] V-1.6：God Mode 临时 JWT 正确注入 `is_god_mode=True` 标记

### 5.2 JWT 服务

- [ ] V-2.1：`issue(payload)` 签发 JWT，包含 exp/iat，超管 JWT 无 tenant_id 字段
- [ ] V-2.2：`decode(token)` 正确解析并验证签名，过期/无效 Token 抛出对应异常
- [ ] V-2.3：`refresh(old_token)` 返回新 Token，过期时间重置
- [ ] V-2.4：密码哈希使用 bcrypt，明文永不存储

### 5.3 Repository 基类

- [ ] V-3.1：`_get_session(tenant_id)` 正常返回 session，tenant_id=None 抛出 `MissingTenantContextError`
- [ ] V-3.2：`_get_admin_session()` 正常返回 session，不带 tenant_id 过滤
- [ ] V-3.3：`_add_tenant_filter(stmt, model, tenant_id)` 正确注入 `WHERE model.tenant_id = :tenant_id`
- [ ] V-3.4：所有 Repository 子类的查询方法通过 `_get_session(tenant_id)` 获取 session
- [ ] V-3.5：CI 静态扫描检测到未授权模块调用 `_get_admin_session()` 时阻断合并

### 5.4 租户 Provisioning

- [ ] V-4.1：创建租户成功写入 tenants(1) + roles(3) + users(1) + user_roles(1) + tenant_quota(1) = 7 条记录
- [ ] V-4.2：存储目录 `storage/{slug}/` (vectors/, documents/, snapshots/, exports/) 创建成功
- [ ] V-4.3：初始管理员可用创建时的密码成功登录
- [ ] V-4.4：任一步骤失败 → 整体回滚（DB 事务 + 文件系统无残留）
- [ ] V-4.5：租户 slug 唯一性校验（创建时检查）

### 5.5 God Mode

- [ ] V-5.1：enter 成功签发 30min 临时 JWT，`is_god_mode=true`
- [ ] V-5.2：enter/exit/写操作均写入 `god_mode_audit_log`
- [ ] V-5.3：同一租户仅允许一个超管 God Mode（并发限制 SET NX）
- [ ] V-5.4：God Mode 写操作需二次确认（前端弹窗，后端不强制但强烈建议）
- [ ] V-5.5：session 超时后自动退出，Token 验证失败
- [ ] V-5.6：续期仅允许一次（+30min）
- [ ] V-5.7：God Mode 下访问租户资源不触发权限过滤（全量可见）

### 5.6 RBAC 权限

- [ ] V-6.1：admin 角色拥有全部 18 种权限
- [ ] V-6.2：editor 角色拥有 8 种权限（kb:rw, pipeline:rw, eval:rw, search:ex+stream）
- [ ] V-6.3：viewer 角色拥有 4 种权限（kb:r, pipeline:r, search:ex+stream）
- [ ] V-6.4：`check_permission(roles, perm)` 正确判断，超管直接返回 True
- [ ] V-6.5：多角色用户权限为其所有角色权限的并集
- [ ] V-6.6：自定义角色权限不能超出创建者自身权限范围
- [ ] V-6.7：内置角色不可删除、不可改名
- [ ] V-6.8：删除角色时检查 `user_roles` 引用，有引用则返回 409

### 5.7 租户隔离

- [ ] V-7.1：租户 A 用户访问租户 B 资源返回 404（不返回 403，防止信息泄漏）
- [ ] V-7.2：Repository 所有查询自动注入 `tenant_id` 条件
- [ ] V-7.3：后台任务必须显式传入 `tenant_id`，否则抛出 `MissingTenantContextError`

### 5.8 邀请与用户管理

- [ ] V-8.1：邀请 token 24h 过期，过期可重发
- [ ] V-8.2：接受邀请（token + password）→ User + UserRole 创建，邀请标记 accepted
- [ ] V-8.3：禁用用户 → 无法登录（401）
- [ ] V-8.4：删除用户 → UserRole 关联一并清除（同步删除 user_roles 记录）

### 5.9 租户状态机

- [ ] V-9.1：active → disabled → 用户无法登录，API 返回 403
- [ ] V-9.2：disabled → active → 用户恢复登录
- [ ] V-9.3：active → archived → 禁止登录和 API，数据保留
- [ ] V-9.4：archived → active → 恢复访问
- [ ] V-9.5：active/disabled/archived → deleted (soft) → deleted_at 标记 + 快照生成
- [ ] V-9.6：deleted (soft) → active (restore, 30 天内) → deleted_at 清空
- [ ] V-9.7：deleted (soft, >30天) → 自动物理清理（DB 行 + 向量 + 文件）

### 5.10 数据模型完整性

- [ ] V-10.1：9 张表全部有对应的 SQLAlchemy 模型，字段与需求一致
- [ ] V-10.2：User.tenant_id=NULL 表示超管
- [ ] V-10.3：Role.permissions 为 JSON 存储，is_builtin 标注内置角色
- [ ] V-10.4：UserInvitation.token 唯一，expires_at 自动计算
- [ ] V-10.5：GodModeAuditLog, PermissionAuditLog, TenantAuditLog 字段完整
- [ ] V-10.6：TenantDeletionSnapshot 状态机完整 (pending→ready→expired)
- [ ] V-10.7：Tenant.status 使用 SQLAlchemy Enum，`values_callable` 正确配置

### 5.11 Schemas 完整性

- [ ] V-11.1：所有 Pydantic 实体类位于 `schemas/auth/` 目录，`__init__.py` 统一导出
- [ ] V-11.2：输入类 (Create/Update) 有正确的 `field_validator` 校验
- [ ] V-11.3：输出类 (Read) 使用 `from_attributes=True`
- [ ] V-11.4：无业务逻辑混入 Schema 类（仅数据校验和序列化）

### 5.12 API 端点

- [ ] V-12.1：所有端点返回统一格式 `{code: 0, message: "success", data: {...}}`
- [ ] V-12.2：错误返回包含 `code`, `message`, `error_code`, `details`
- [ ] V-12.3：超管 API (`/api/v1/admin/*`) 仅超管可访问
- [ ] V-12.4：租户内 API (`/api/v1/*`) require tenant_id 上下文
- [ ] V-12.5：`/api/v1/auth/login` 返回 JWT + 用户信息 + 租户信息

---

> **Phase 1 完成标志**：所有验收检查点通过 + 全部测试通过 + `repository/base.py` 改造完成（所有现有 Repository 子类已适配 `_get_session(tenant_id)` 调用模式）。
