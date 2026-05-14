# Phase 9：超管前端——实施文档

> **依赖**：Phase 1（权限与多租户）完成后启动。后端认证、租户/用户/角色 CRUD、God Mode、RBAC API 已就绪，前端构建超管管理全流程。
> **产出**：超管登录页、租户列表/详情页、用户管理页、角色管理页、全局布局（TenantLayout + AdminLayout）、路由守卫、God Mode 横幅。
> **参考规范**：[04-permission-and-multi-tenancy.md](../../requirements/04-permission-and-multi-tenancy.md) §2 租户管理（超管页面）、§3 租户内部（权限控制）
> **最后更新**：2026-05-14

---

## 1. 阶段目标

构建超管前端的完整交互链路，实现多租户平台管理、租户内用户与角色管理、God Mode 模式、全局布局与路由守卫：

- **登录页**：租户用户登录（用户名 + 密码 → JWT），超管登录（跳转 `/admin/tenants`）
- **超管布局（AdminLayout）**：左侧简洁导航栏（租户管理），右侧内容区
- **租户列表页**：表格展示所有租户，支持搜索/状态筛选，创建租户对话框（含配额设置）
- **租户详情页**：4 选项卡（概览/用户/配额/操作日志），God Mode 入口，停用/归档/删除操作
- **租户内布局（TenantLayout）**：上下文栏（租户名 + 角色切换 + "返回平台管理"），主内容区
- **用户管理页**：用户列表 + 邀请对话框（邮箱 + 角色选择），角色分配/禁用/删除
- **角色管理页**：角色列表 + 创建/编辑抽屉（权限勾选矩阵），内置角色保护
- **God Mode 横幅**：持久化顶部横幅，30 分钟倒计时，续期按钮，二次确认写操作
- **路由守卫**：JWT 有效性检查 + 租户状态检查 + 角色权限检查 + 超管路由隔离

---

## 2. 任务清单

### 2.1 状态管理（9.1 状态管理）

#### `features/auth/stores/authStore.ts`

- [ ] **认证状态接口定义**：`AuthState` 接口
  - `accessToken: string | null`——JWT access token
  - `refreshToken: string | null`——刷新 token
  - `user: UserInfo | null`——当前用户信息 `{ id, username, email, status }`
  - `tenant: TenantInfo | null`——当前租户信息 `{ id, name, slug }`
  - `roles: string[]`——用户角色列表（如 `["admin"]`）
  - `isSuperadmin: boolean`——是否为平台超管
  - `isAuthenticated: boolean`——是否已登录
  - `selectedRole: string | null`——角色视角切换选中的角色（null 表示本角色视角）
- [ ] **操作方法**
  - `login(username, password): Promise<void>`——调用 `POST /api/v1/auth/login`，成功后解析 JWT 并存储状态
  - `logout(): void`——清除 token，重置状态，跳转登录页
  - `refreshToken(): Promise<void>`——调用 `POST /api/v1/auth/refresh`，更新 accessToken
  - `selectRole(roleName: string | null): void`——切换角色视角（前端过滤，不改 JWT）
  - `parseJWT(token: string): void`——解析 JWT payload 提取 user_id、tenant_id、roles、is_superadmin
  - `loadFromStorage(): void`——从 localStorage 恢复 token 和状态
- [ ] **持久化**：
  - `accessToken` 和 `refreshToken` 存 localStorage
  - 页面刷新后 `loadFromStorage()` 恢复状态，token 过期则自动登出
  - `selectedRole` 存 sessionStorage（标签页级别，不跨标签页共享）
- [ ] **Token 自动刷新**：
  - 拦截 401 响应 → 自动调用 `refreshToken()` → 重试原请求
  - 刷新失败 → 自动 `logout()`
  - 刷新间隔：access token 过期前 5 分钟自动刷新
- [ ] **角色权限衍生**：
  - `hasPermission(permission: string): boolean`——根据 `selectedRole`（优先）或用户全部角色判断
  - `effectiveRoles: string[]`——当 `selectedRole` 非空时返回 `[selectedRole]`，否则返回全部 `roles`

#### `features/auth/stores/godModeStore.ts`

- [ ] **God Mode 状态接口**：`GodModeState`
  - `isActive: boolean`——God Mode 是否激活
  - `tenantId: string | null`——目标租户 ID
  - `tenantName: string | null`——目标租户名称
  - `expiresAt: number | null`——过期时间戳（ms）
  - `sessionToken: string | null`——临时 JWT（用于 API 调用）
  - `countdown: number`——剩余秒数（每秒更新）
  - `canExtend: boolean`——是否可续期（仅一次）
- [ ] **操作方法**
  - `enterGodMode(tenantId: string): Promise<void>`——调用 `POST /api/v1/admin/tenants/{id}/impersonate` → 获取临时 JWT → 设置状态 + 启动倒计时
  - `exitGodMode(): void`——调用退出 API → 清除状态 → 跳转回超管租户列表
  - `extendGodMode(): Promise<void>`——调用续期 API → 更新 expiresAt + 重置倒计时 → `canExtend = false`
  - `startCountdown(): void`——每秒递减 countdown，到期自动 exitGodMode
  - `stopCountdown(): void`——清除倒计时 interval
- [ ] **倒计时逻辑**：
  - 进入 God Mode 时启动 `setInterval(1000)` 倒计时
  - 显示格式 `mm:ss`
  - 剩余 5 分钟时弹窗提示"God Mode 即将过期，是否续期？"
  - 剩余 0 时自动退出
- [ ] **持久化**：
  - God Mode 状态仅存内存，不持久化到 localStorage（安全考虑）
  - 页面刷新后 God Mode 状态丢失 → 超管需重新进入

### 2.2 API 客户端（9.2 API 客户端）

#### `api/auth/auth.ts`

- [ ] **认证 API**
  - `login(data: LoginRequest) → LoginResponse`——POST `/api/v1/auth/login`
  - `refreshToken(refreshToken: string) → TokenRefreshResponse`——POST `/api/v1/auth/refresh`
- [ ] **类型定义**
  - `LoginRequest: { username: string; password: string }`
  - `LoginResponse: { access_token: string; refresh_token: string; user: UserRead; tenant: TenantRead | null }`
  - `TokenRefreshResponse: { access_token: string; refresh_token: string }`

#### `api/auth/tenant.ts`

- [ ] **租户管理 API（超管）**
  - `getTenants(params: TenantListParams) → TenantListResponse`——GET `/api/v1/admin/tenants`
    - 支持参数：`status`（状态筛选）、`search`（按名称搜索）、`page`、`page_size`
  - `getTenant(id: string) → TenantDetail`——GET `/api/v1/admin/tenants/:id`
  - `createTenant(data: TenantCreate) → TenantDetail`——POST `/api/v1/admin/tenants`
  - `updateTenant(id: string, data: TenantUpdate) → TenantDetail`——PUT `/api/v1/admin/tenants/:id`
  - `archiveTenant(id: string) → void`——PUT `/api/v1/admin/tenants/:id/archive`
  - `restoreTenant(id: string) → void`——PUT `/api/v1/admin/tenants/:id/restore`
  - `deleteTenant(id: string) → void`——DELETE `/api/v1/admin/tenants/:id`（软删除）
  - `getTenantUsers(id: string) → UserRead[]`——GET `/api/v1/admin/tenants/:id/users`
  - `enterGodMode(tenantId: string) → GodModeSession`——POST `/api/v1/admin/tenants/:id/impersonate`
  - `getGodModeLog(tenantId: string) → GodModeAuditLog[]`——GET `/api/v1/admin/tenants/:id/god-mode-log`
- [ ] **类型定义**
  - `TenantCreate: { name: string; slug: string; admin_user: { username: string; email: string; password: string }; quotas: QuotaConfig }`
  - `QuotaConfig: { kb_limit: number; doc_limit: number; user_limit: number; storage_limit: number; search_qps_limit: number }`
  - `TenantListItem: { id: string; name: string; slug: string; status: 'active' | 'disabled' | 'archived' | 'deleted'; user_count: number; storage_usage: string; created_at: string }`
  - `TenantDetail: { id: string; name: string; slug: string; status: string; resource_limits: object; user_count: number; kb_count: number; doc_count: number; pipeline_count: number; storage_usage: string; quotas: QuotaUsage; created_at: string; updated_at: string }`
  - `GodModeSession: { access_token: string; expires_at: string; tenant_id: string; actor_id: string }`

#### `api/auth/user.ts`

- [ ] **用户管理 API（租户内）**
  - `getUsers(params?: UserListParams) → UserListResponse`——GET `/api/v1/users`（含租户上下文字段）
  - `inviteUser(data: UserInvite) → InviteResponse`——POST `/api/v1/users/invite`
  - `acceptInvitation(data: AcceptInvitation) → void`——POST `/api/v1/users/accept-invitation`
  - `updateUser(id: string, data: UserUpdate) → UserRead`——PUT `/api/v1/users/:id`
  - `deleteUser(id: string) → void`——DELETE `/api/v1/users/:id`
- [ ] **类型定义**
  - `UserListItem: { id: string; username: string; email: string; roles: string[]; status: 'active' | 'disabled'; created_at: string }`
  - `UserInvite: { email: string; roles: string[] }`
  - `InviteResponse: { invitation_id: string; invitation_link: string; expires_at: string }`
  - `AcceptInvitation: { token: string; password: string }`
  - `UserUpdate: { roles?: string[]; status?: 'active' | 'disabled' }`

#### `api/auth/role.ts`

- [ ] **角色管理 API（租户内）**
  - `getRoles() → RoleListItem[]`——GET `/api/v1/roles`
  - `createRole(data: RoleCreate) → RoleRead`——POST `/api/v1/roles`
  - `updateRole(id: string, data: RoleUpdate) → RoleRead`——PUT `/api/v1/roles/:id`
  - `deleteRole(id: string) → void`——DELETE `/api/v1/roles/:id`
  - `getPermissions() → PermissionList`——GET `/api/v1/permissions`
- [ ] **类型定义**
  - `RoleCreate: { name: string; permissions: string[] }`
  - `RoleListItem: { id: string; name: string; permissions: string[]; is_builtin: boolean; user_count: number; created_at: string }`
  - `RoleUpdate: { name?: string; permissions?: string[] }`
  - `PermissionItem: { permission_code: string; category: string; description: string }`
  - `PermissionList: { permissions: PermissionItem[] }`

### 2.3 全局布局（9.3 全局布局）

#### `app/layouts/AdminLayout.tsx`

- [ ] **超管布局**
  - 左侧固定宽度侧边栏（220px），深色主题背景
  - 侧边栏内容：
    - 顶部平台 Logo + 名称（如 "RAG 平台管理系统"）
    - 导航菜单项：`[🏠 租户管理]`（链接到 `/admin/tenants`）
    - 底部：当前超管用户名 + `[退出登录]` 按钮
  - 右侧内容区：`<Outlet />` 渲染子路由
  - 响应式：小屏幕侧边栏折叠为汉堡菜单
  - URL 路由前缀：`/admin/*`
  - 进入路由时检查 `authStore.isSuperadmin === true`，否则重定向到 `/login`

#### `app/layouts/TenantLayout.tsx`

- [ ] **租户内布局（含上下文栏）**
  - **上下文栏**（顶部固定，高度 56px）：
    - 左侧区域：`[📚 知识库] [🔧 管道] [📊 评估] [⚙️ 设置]` 导航 Tab（链接到对应路由）
    - 右侧区域：
      - 租户名称标签（如 "仁和医院"）
      - 当前角色标签（如 "管理员"）
      - 角色切换下拉按钮（仅多角色用户可见，或管理员可切换视角）
      - "返回平台管理" 按钮（仅 `authStore.isSuperadmin && godModeStore.isActive` 时可见）
      - 用户头像/名称下拉菜单：`[个人设置] [退出登录]`
  - **主内容区**：`<Outlet />` 渲染子路由，上方 `padding-top: 56px` 防止被上下文栏遮挡
  - URL 路由前缀：`/app/*`
  - 进入路由时检查 `authStore.isAuthenticated === true`，否则重定向到 `/login`

#### `features/auth/components/RoleSwitcher.tsx`

- [ ] **角色切换下拉组件**
  - 渲染条件：`authStore.roles.length > 1`（多角色用户）或 `authStore.roles.includes('admin')`
  - 下拉选项：
    - 当前有效角色列表（从 `authStore.roles` 读取）
    - 每个角色显示角色名 + 图标
    - 顶部选项：`"本角色 (原始权限)"`——取消角色视角切换
  - 选中角色后调用 `authStore.selectRole(roleName)`
  - 选中态：下拉按钮显示 `"视角: {角色名}"`（选中非本角色时），或 `"切换角色视角"`（本角色时）
  - Tooltip："管理员可切换视角预览该角色的页面权限和资源可见性，不影响实际身份"

#### `features/auth/components/GodModeBanner.tsx`

- [ ] **God Mode 持久化横幅**
  - 渲染条件：`godModeStore.isActive === true`
  - 样式：页面顶部固定横幅（`position: fixed; top: 0; z-index: 1000`），高度 40px
  - 背景色：醒目的橙色/金色（`#fa8c16` 或 `#faad14`），左侧有警告图标
  - 横幅内容：
    - 左侧：`⚠️ 当前以超管身份访问「{tenantName}」| 剩余时间: {countdown}`（格式 `mm:ss`）
    - 中间：`[续期]` 按钮（仅 `godModeStore.canExtend === true` 时可见，点击调用 `extendGodMode()`）
    - 右侧：`[退出 God Mode]` 按钮（调用 `exitGodMode()`）
  - 倒计时颜色变化：>5min 正常色，<5min 红色闪烁
  - 横幅出现时，页面内容 `margin-top: 40px` 避免遮挡
  - 与 TenantLayout 上下文栏并排显示（GodModeBanner 在最顶部，上下文栏在其下方）

### 2.4 登录页（9.4 登录页）

#### `features/auth/pages/LoginPage.tsx`

- [ ] **页面布局**
  - 居中布局，背景使用品牌色渐变或浅灰
  - 左侧/上方：平台 Logo + 名称
  - 中央：登录卡片（白色背景，圆角，阴影）
- [ ] **登录表单**
  - 用户名输入框（`<Input>`，前缀图标为用户图标）
  - 密码输入框（`<Input.Password>`，前缀图标为锁图标）
  - 登录按钮（全宽 `<Button type="primary">`）
  - 表单校验：用户名必填（min=3, max=64），密码必填（min=6, max=128）
- [ ] **登录流程**
  1. 用户填写表单 → 点击"登录"
  2. 调用 `authStore.login(username, password)`
  3. 成功：
     - 超管（`isSuperadmin=true`）→ 跳转 `/admin/tenants`
     - 租户用户（`tenant !== null`）→ 跳转 `/app/knowledge-bases`（或租户首页）
     - 禁用用户 → 提示 "账号已被禁用，请联系管理员"
  4. 失败：显示错误提示（用户名/密码错误、账号已禁用、租户已停用）
- [ ] **加载态**：登录按钮 loading + 禁用
- [ ] **错误态**：表单下方显示错误信息（红色文本）
- [ ] **其他**
  - 路由：`/login`
  - 已登录用户访问 `/login` → 自动跳转到对应首页
  - 未登录用户访问任意页面 → 重定向到 `/login?redirect={original_url}`

### 2.5 租户管理页（9.5 租户管理页）

#### `features/auth/pages/TenantListPage.tsx`

- [ ] **页面标题栏**
  - 左侧："租户管理" 标题
  - 右侧：`[+ 创建租户]` 按钮（打开创建租户对话框）
- [ ] **筛选栏**
  - 搜索框：按租户名称模糊搜索（300ms 防抖）
  - 状态筛选：Select 下拉，选项 `全部 / 活跃 / 已停用 / 已归档 / 已删除`
  - 筛选条件变更时自动重新加载列表
- [ ] **租户表格**（Ant Design Table）
  - 列定义：
    - `名称`（可点击跳转到租户详情，加粗显示）
    - `标识`（slug，灰色小字）
    - `状态`（Tag 组件：active=绿色, disabled=橙色, archived=灰色, deleted=红色）
    - `用户数`（数字 + 用户图标）
    - `存储用量`（格式如 "2.3 GB / 50 GB"，进度条）
    - `创建时间`（格式 YYYY-MM-DD）
    - `操作`（按钮组）：
      - `[查看]` → 跳转 `/admin/tenants/:id`
      - `[停用]` / `[启用]`（根据当前状态动态显示）→ 确认弹窗后调用 API
      - `[归档]` → 确认弹窗后调用 API
      - `[删除]` → 二次确认（输入租户标识确认）→ 调用 API
      - 更多下拉：`[恢复]`（仅 deleted 状态可见）
  - 分页：每页 20 条，支持跳转
  - 排序：支持按创建时间、用户数、存储用量排序
- [ ] **空状态**：无租户时显示 "暂无租户，点击「创建租户」开始" + `[+ 创建租户]` 按钮
- [ ] **加载态**：Table Skeleton
- [ ] **错误态**：加载失败显示重试按钮
- [ ] **路由**：`/admin/tenants`

#### 创建租户对话框（`TenantListPage.tsx` 内嵌 Modal）

- [ ] **表单字段**
  - `租户名称`（Input，必填，max=64，placeholder="如：仁和医院"）
  - `租户标识`（Input，必填，max=32，正则 `[a-z0-9-]+`，placeholder="如：renhe-hospital"）
    - 失去焦点时异步校验 slug 唯一性（调用后端校验或 debounce 查询）
  - 分割线 + `初始管理员`
  - `管理员用户名`（Input，必填，max=64）
  - `管理员邮箱`（Input，必填，email 格式）
  - `管理员初始密码`（Input.Password，必填，min=8）
  - 分割线 + `资源配额`
  - `知识库上限`（InputNumber，min=1, max=1000, default=10）
  - `文档总量上限`（InputNumber，min=1, max=10000000, default=1000000，单位：条）
  - `用户数上限`（InputNumber，min=1, max=10000, default=100）
  - `存储上限`（InputNumber，min=1, max=10000, default=50，单位：GB）
  - `搜索 QPS 上限`（InputNumber，min=1, max=10000, default=50）
- [ ] **表单校验**
  - slug 唯一性异步校验（显示 loading 状态）
  - 所有必填字段有值
  - 邮箱格式正则为标准 email
- [ ] **提交流程**
  1. 点击 `[创建]` → 表单校验 → 调用 `createTenant(data)`
  2. 成功后 → Modal 关闭 → 列表刷新 → 成功提示 "租户「XXX」创建成功，管理员可使用初始密码登录"
  3. 失败 → 保留 Modal 打开 → 显示错误详情
- [ ] **取消**：点击 `[取消]` 或关闭按钮，如已填写内容 → 确认弹窗 "已填写的内容将丢失，确定取消？"

#### `features/auth/pages/TenantDetailPage.tsx`

- [ ] **页面头部**
  - 左上角 `← 租户列表` 返回按钮
  - 租户名称 + `[状态标签]` + `[停用/启用] [归档] [删除]` 操作按钮组
- [ ] **选项卡布局**（Ant Design Tabs）：`概览 | 用户 | 配额 | 操作日志`

- [ ] **概览 Tab**
  - 统计卡片（Ant Design Statistic / Card grid）：
    - `知识库数`、`文档数`、`管道数`、`用户数`、`存储用量`
  - 搜索统计（30 天）：搜索次数、平均延迟、错误率（从后端 `/tenants/{id}` 接口获取）
  - `[进入此租户]` 按钮（醒目样式，橙色/金色），点击调用 `godModeStore.enterGodMode(tenantId)`：
    1. 调用 API 获取临时 JWT
    2. 成功后 navigates 到 `/app/knowledge-bases`（该租户首页）
    3. 失败（并发限制）→ 提示 "已有其他超管在此租户的 God Mode 中"
  - 租户基本信息：名称、标识、创建时间、最后更新时间

- [ ] **用户 Tab**
  - 该租户所有用户列表（复用 UserManagementPage 的用户表格，但 `tenantId` 从 `TenantDetailPage` props 传入）
  - 支持查看、重置密码、禁用操作（超管权限）

- [ ] **配额 Tab**
  - 配额使用情况进度条：
    - 知识库：`kb_count / kb_limit`
    - 文档：`doc_count / doc_limit`
    - 用户：`user_count / user_limit`
    - 存储：`storage_usage / storage_limit`
    - 搜索 QPS：`current_qps / search_qps_limit`
  - 每项显示百分比进度条 + 数值，接近上限时（>80%）黄色警告，达上限时红色
  - `[调整配额]` 按钮 → 弹出 Modal 修改配额值
    - 表单：每个配额项 InputNumber + 当前值展示
    - 调整后调用 `updateTenant(id, { quotas: newQuotas })`

- [ ] **操作日志 Tab**
  - 表格展示 `tenant_audit_log` 和 `god_mode_audit_log` 数据
  - 列：操作时间、操作人、操作类型、目标资源、详情
  - 支持筛选：按操作类型（租户创建/停用/归档/删除、God Mode 进入/退出/写操作）

- [ ] **停用/启用交互**
  - 停用确认弹窗："确定停用租户「XXX」？停用后该租户所有用户将无法登录，搜索 API 返回 403。数据保留。"
  - 启用直接操作（确认即可）
  - 归档确认弹窗："确定归档租户「XXX」？归档后禁止登录和 API 访问，数据保留但不计入活跃配额。可随时恢复。"

- [ ] **删除交互**
  - 二次确认弹窗：
    1. 提示："删除为软删除，30 天保留期内可恢复。到期后自动物理清理（数据不可恢复）。"
    2. 输入框要求输入租户标识以确认：`请输入 "xxx" 确认删除`
    3. 输入匹配后 `[确认删除]` 按钮启用
    4. 确认后调用 `deleteTenant(id)`

- [ ] **路由**：`/admin/tenants/:id`

### 2.6 用户管理页（9.6 用户管理页）

#### `features/auth/pages/UserManagementPage.tsx`

- [ ] **页面标题栏**
  - 左侧：Tab 切换 `[用户] [角色]`（或作为顶级页面内的两个 Section）
  - 右侧：`[+ 邀请用户]` 按钮
- [ ] **用户表格**
  - 列定义：
    - `用户名`（加粗）
    - `邮箱`
    - `角色`（Tag 列表，每个角色一个 Tag，不同颜色区分）
    - `状态`（Tag：active=绿色, disabled=灰色）
    - `创建时间`
    - `操作`：`[编辑角色] [禁用/启用] [删除]`
      - 编辑角色：弹出 Modal，Checkbox.Group 选择角色
      - 删除：确认弹窗 "确定删除用户「XXX」？其角色关联将同步清除。"
  - 支持搜索：按用户名或邮箱搜索
  - 分页：每页 20 条
- [ ] **邀请用户对话框**（Modal）
  - 标题："邀请用户加入 {租户名}"
  - 表单字段：
    - `邮箱`（Input，必填，email 格式）
    - `选择角色`（Checkbox.Group，选项从 `getRoles()` API 加载，包含内置角色和自定义角色）
    - 提示文本："邀请链接 24 小时内有效，过期后需重新发送"
  - 提交按钮：`[发送邀请]`
  - 成功后：
    - 显示邀请链接（可复制）：
      ```
      ✅ 邀请已生成
      邀请链接：https://xxx.com/invite/{token}
      [复制链接] [发送邮件]
      ```
    - "发送邮件" 按钮触发后端邮件发送（或前端 mock，提示 "邮件已发送"）
    - "复制链接" 使用 `navigator.clipboard.writeText()` + message.success("链接已复制")
  - 失败：
    - 邮箱已存在 → "该邮箱已被邀请或已注册"
    - 角色选择为空 → 表单校验提示
- [ ] **空状态**：无用户时显示 "暂无用户，点击「邀请用户」开始"
- [ ] **路由**：`/app/settings/users`（TenantLayout 上下文中）

#### `features/auth/pages/RoleManagementPage.tsx`

- [ ] **角色表格**
  - 列定义：
    - `角色名`（加粗）
    - `权限摘要`（简略显示权限数量和关键权限，悬停显示完整列表）
    - `内置/自定义`（Tag：内置=蓝色, 自定义=绿色）
    - `用户数`（点击可跳转到用户列表筛选该角色）
    - `操作`：`[编辑] [删除]`
      - 编辑：打开权限编辑抽屉
      - 删除：确认弹窗 "确定删除角色「XXX」？"
        - 有用户引用时 → 提示 "该角色下有 N 个用户，请先移除用户或替换角色"
        - 内置角色 → 隐藏删除按钮
- [ ] **[+ 新建角色] 按钮** → 打开权限编辑抽屉（同编辑抽屉，但所有权限初始未勾选）
- [ ] **权限编辑抽屉**（Drawer，右侧滑入）
  - 标题："编辑角色 — {角色名}" 或 "新建角色"
  - 表单字段：
    - `角色名称`（Input，必填，max=64，内置角色不可改名——显示文本）
  - 权限勾选矩阵（按分类分组）：
    - **知识库**：`☑ kb:read` `☑ kb:write` `☐ kb:delete` `☐ kb:manage_acl`
    - **管道**：`☑ pipeline:read` `☐ pipeline:write` `☐ pipeline:delete` `☐ pipeline:publish`
    - **评估**：`☐ eval:read` `☐ eval:write` `☐ eval:delete`
    - **搜索**：`☑ search:execute` `☑ search:stream`
    - **系统**：`☐ system:config` `☐ system:monitor`
    - **用户**：`☐ user:manage` `☐ role:manage`
    - 每项权限旁显示 Tooltip（中文说明）
    - 权限代码只读（灰色文本），不可编辑
  - 权限约束检查：
    - 新建角色时，权限不能超出当前用户自身权限范围
    - 编辑角色时，同样不能授予自己未拥有的权限
    - 超出范围时权限项禁用 + Tooltip "您没有此权限，无法授予"
  - 底部按钮：`[保存] [取消]`
  - 保存成功 → 抽屉关闭 + 列表刷新 + 成功提示
  - 保存失败 → 保留抽屉 + 错误提示
- [ ] **路由**：`/app/settings/roles`（TenantLayout 上下文中）

### 2.7 路由（9.7 路由）

#### `router/routes.tsx`（新增路由定义）

- [ ] **全局路由表**

  ```typescript
  // 路由结构
  const routes = [
    {
      path: '/login',
      element: <LoginPage />,
    },
    {
      path: '/invite/:token',
      element: <AcceptInvitationPage />,  // 接受邀请设置密码页（简化实现）
    },
    {
      path: '/admin',
      element: <AuthGuard requireSuperadmin><AdminLayout /></AuthGuard>,
      children: [
        { index: true, redirect: '/admin/tenants' },
        { path: 'tenants', element: <TenantListPage /> },
        { path: 'tenants/:id', element: <TenantDetailPage /> },
      ],
    },
    {
      path: '/app',
      element: <AuthGuard><TenantLayout /></AuthGuard>,
      children: [
        { index: true, redirect: '/app/knowledge-bases' },
        { path: 'knowledge-bases/*', element: <KnowledgeBaseRoutes /> },  // Phase 6
        { path: 'pipelines/*', element: <PipelineRoutes /> },              // Phase 5
        { path: 'evaluations/*', element: <EvalRoutes /> },                // Phase 7
        {
          path: 'settings',
          element: <RoleGuard requiredPermissions={['user:manage']}><SettingsLayout /></RoleGuard>,
          children: [
            { path: 'users', element: <UserManagementPage /> },
            { path: 'roles', element: <RoleManagementPage /> },
          ],
        },
      ],
    },
    {
      path: '*',
      element: <Navigate to="/login" replace />,
    },
  ];
  ```

#### 路由守卫

- [ ] **AuthGuard 组件**

  ```typescript
  /**
   * 认证守卫。检查是否已登录。
   * 
   * 流程：
   * 1. 检查 authStore.isAuthenticated
   * 2. 未认证 → 重定向到 /login?redirect={current_path}
   * 3. 已认证 + requireSuperadmin=true → 检查 authStore.isSuperadmin
   *    → 不是超管 → 重定向到 /app/knowledge-bases（无权限访问超管页面）
   * 4. 通过 → 渲染 children
   */
  function AuthGuard({ children, requireSuperadmin = false }: AuthGuardProps) {
    const { isAuthenticated, isSuperadmin } = useAuthStore();
    const location = useLocation();

    if (!isAuthenticated) {
      return <Navigate to={`/login?redirect=${encodeURIComponent(location.pathname)}`} replace />;
    }

    if (requireSuperadmin && !isSuperadmin) {
      return <Navigate to="/app/knowledge-bases" replace />;
    }

    return <>{children}</>;
  }
  ```

- [ ] **RoleGuard 组件**

  ```typescript
  /**
   * 角色权限守卫。检查用户是否拥有指定权限。
   * 
   * 流程：
   * 1. 检查 authStore.effectiveRoles（已考虑角色视角切换）
   * 2. 加载当前用户角色和对应权限映射
   * 3. 检查是否拥有 requiredPermissions 中任一权限（OR 逻辑）
   * 4. 不满足 → 返回 403 页面（非重定向，直接渲染无权限提示）
   * 5. God Mode 中（is_god_mode=true）→ 直接通过
   * 
   * 权限映射：/api/v1/permissions 返回的权限列表，缓存在前端
   */
  function RoleGuard({ children, requiredPermissions = [] }: RoleGuardProps) {
    const { effectiveRoles, isSuperadmin } = useAuthStore();
    const { isActive: isGodMode } = useGodModeStore();
    const { permissions: permissionMap } = usePermissionCache();

    // God Mode 或超管豁免权限检查
    if (isGodMode || isSuperadmin) {
      return <>{children}</>;
    }

    const hasPermission = requiredPermissions.some(perm =>
      effectiveRoles.some(role => permissionMap[role]?.includes(perm))
    );

    if (!hasPermission) {
      return <ForbiddenPage />;  // 渲染 403 页面
    }

    return <>{children}</>;
  }
  ```

- [ ] **Token 有效性拦截器**（在 `shared/api/http-client.ts` 中实现）
  - Axios/fetch 响应拦截器
  - 401 响应 → 自动调用 `authStore.refreshToken()` → 重试原请求
  - 刷新失败 → `authStore.logout()` → 跳转 `/login`
  - 403 响应（`error_code: "TENANT_SUSPENDED"`）→ 提示 "租户已被停用，请联系管理员" → 登出

---

## 3. 关键实现细节

### 3.1 上下文栏（TenantLayout Context Bar）

- **实现方式**：TenantLayout 顶部固定 `<header>` 元素，`position: fixed; top: 0; z-index: 900`
- **God Mode 横幅叠加**：GodModeBanner 使用 `z-index: 1000`，上下文栏 `top: 40px`（当 GodModeBanner 激活时动态调整）
- **导航 Tab 高亮**：使用 Ant Design `Menu` 组件 `mode="horizontal"`，`selectedKeys` 与当前路由匹配
- **角色切换下拉**：`<RoleSwitcher />` 嵌入上下文栏右侧
- **"返回平台管理" 按钮**：
  - 渲染条件：`godModeStore.isActive && authStore.isSuperadmin`
  - 点击行为：`godModeStore.exitGodMode()` → 等待退出完成 → `navigate('/admin/tenants')`
  - 样式：文字链接 + 左箭头图标，与右侧其他元素有间距分隔

### 3.2 角色视角切换机制

- **设计原则**：JWT 中的 `roles` 数组不变，API 调用使用原始 JWT。前端筛选——页面中按 `selectedRole` 过滤可见资源和操作按钮
- **影响范围**：
  - 知识库列表：只显示 `selectedRole` 可读取的知识库（visibility 过滤）
  - 管道列表：只显示 `selectedRole` 可读取的管道
  - 操作按钮：`[新建知识库]` 等写操作按钮在 `selectedRole` 无相应权限时 disabled/hidden
  - 搜索：使用原始权限（不可切换视角降低搜索权限，保证安全）
- **权限缓存**：
  - 前端维护一份 `permissionMap: Record<string, string[]>`（角色名 → 权限列表）
  - 进入应用时从 `GET /api/v1/permissions` 加载可用权限列表
  - 从 `GET /api/v1/roles` 加载所有角色的权限映射
  - 缓存 30 分钟，角色增删改时失效

### 3.3 God Mode 横幅与倒计时

- **倒计时实现**：`godModeStore.startCountdown()` 使用 `setInterval(1000)`
  ```typescript
  startCountdown: () => {
    const timer = setInterval(() => {
      const remaining = (get().expiresAt! - Date.now()) / 1000;
      if (remaining <= 0) {
        clearInterval(timer);
        get().exitGodMode();
      } else {
        set({ countdown: Math.ceil(remaining) });
        if (remaining <= 300 && !get()._fiveMinWarned) {  // 剩余 5 分钟
          set({ _fiveMinWarned: true });
          // 触发弹窗提示
          Modal.warning({
            title: 'God Mode 即将过期',
            content: `God Mode 将在 5 分钟后自动退出。是否续期？`,
            okText: '续期 30 分钟',
            cancelText: '稍后退出',
            onOk: () => get().extendGodMode(),
          });
        }
      }
    }, 1000);
    set({ _countdownTimer: timer });
  },
  ```
- **退出清理**：`exitGodMode()` 中调用 `stopCountdown()` 清除 interval
- **页面刷新后 God Mode 丢失**：组件初始化时检查 `godModeStore.isActive`，若为 false 但 URL 为 `/app/*` 且用户无租户上下文 → 重定向到 `/admin/tenants`

### 3.4 登录页与递归重定向

- **登录后重定向**：
  1. 读取 URL 参数 `?redirect={original_url}`
  2. 若有 `redirect` 参数 → 登录成功后跳转到 `redirect` 路径
  3. 若无 `redirect` 参数 → 按角色默认跳转：超管 → `/admin/tenants`，租户用户 → `/app/knowledge-bases`
- **防止无限重定向**：
  - `AuthGuard` 重定向到 `/login` 时携带 `redirect` 参数
  - 登录页本身不在 `AuthGuard` 包裹内
  - `/login` 路由设置 `meta: { public: true }`

### 3.5 邀请流程实现

- **完整流程**：
  1. 管理员在 UserManagementPage 点击 `[+ 邀请用户]` → 弹出 Modal
  2. 填写邮箱 + 选择角色 → 提交
  3. 调用 `POST /api/v1/users/invite` → 后端生成 token + 存储 UserInvitation → 返回邀请链接
  4. 前端展示邀请链接，提供 `[复制链接]` 和 `[发送邮件]` 两个按钮
  5. `[复制链接]`：`navigator.clipboard.writeText(invitationLink)` + `message.success()`
  6. `[发送邮件]`：调用后端邮件发送 API（如未实现，前端可做 mock 提示）
  7. 被邀请用户访问邀请链接 → 渲染 `AcceptInvitationPage`
     - 页面解析 URL 中的 `token` 参数
     - 显示 `设置密码` 表单（密码 + 确认密码）
     - 提交 `POST /api/v1/users/accept-invitation` + `{ token, password }`
     - 成功后跳转登录页
  8. 邀请过期：24 小时后 token 失效，邀请记录状态变为过期
     - 管理员可在用户列表中看到待激活用户 + `[重新发送邀请]` 按钮

### 3.6 租户列表页状态筛选

- **状态枚举与颜色映射**：
  ```typescript
  const TENANT_STATUS_MAP = {
    active:    { label: '活跃', color: 'green' },
    disabled:  { label: '已停用', color: 'orange' },
    archived:  { label: '已归档', color: 'default' },
    deleted:   { label: '已删除', color: 'red' },
  };
  ```
- **筛选下拉**：`<Select>` 组件，选项为上述 4 种状态 + "全部"（默认）
- **操作按钮动态显示**：
  - `active` → 显示 `[停用] [归档] [删除]`
  - `disabled` → 显示 `[启用] [归档] [删除]`
  - `archived` → 显示 `[恢复] [删除]`
  - `deleted` → 显示 `[恢复]`（仅保留期内）

### 3.7 权限编辑抽屉

- **权限分类映射**：
  ```typescript
  const PERMISSION_CATEGORIES = [
    {
      key: 'kb',
      label: '知识库',
      permissions: [
        { code: 'kb:read', description: '查看知识库及其文档' },
        { code: 'kb:write', description: '创建/编辑知识库、上传文档' },
        { code: 'kb:delete', description: '删除知识库及文档' },
        { code: 'kb:manage_acl', description: '管理知识库和文档的 ACL 权限' },
      ],
    },
    // ... 管道、评估、搜索、系统、用户 分类同理
  ];
  ```
- **权限约束**：
  - 获取当前用户的 `effectivePermissions`（当前角色拥有的权限集合）
  - 渲染时，`currentUserPermissions` 中不存在的权限项 → `<Checkbox disabled>` + Tooltip "您没有此权限"
  - 创建者自身的权限范围是 `roles.includes('admin') ? allPermissions : effectivePermissions`
- **内置角色保护**：`is_builtin=true` 的角色 → 隐藏删除按钮，名称字段变为只读文本

---

## 4. 测试策略

### 4.1 组件测试（Vitest + React Testing Library）

#### LoginPage 表单校验

- [ ] **TC-9.1.1**：用户名和密码为空时点击登录 → 表单校验提示 "请输入用户名" 和 "请输入密码"
- [ ] **TC-9.1.2**：用户名少于 3 字符 → 提示 "用户名至少 3 个字符"
- [ ] **TC-9.1.3**：密码少于 6 字符 → 提示 "密码至少 6 个字符"
- [ ] **TC-9.1.4**：输入正确格式 → 调用 login API → 成功后跳转
- [ ] **TC-9.1.5**：登录 API 返回错误 → 显示错误提示信息

#### TenantListPage 筛选

- [ ] **TC-9.2.1**：页面加载时调用 `getTenants()` 并渲染表格
- [ ] **TC-9.2.2**：搜索框输入 "仁和" → 调用 API 带 `search=仁和` 参数 → 列表过滤
- [ ] **TC-9.2.3**：状态下拉选择 "已停用" → 调用 API 带 `status=disabled` → 表格仅显示已停用租户
- [ ] **TC-9.2.4**：点击 `[+ 创建租户]` → Modal 打开 → 填写表单 → 提交 → Modal 关闭 → 列表刷新
- [ ] **TC-9.2.5**：点击租户名称 → 跳转到 `/admin/tenants/:id`
- [ ] **TC-9.2.6**：删除租户 → 确认弹窗 → 需输入租户标识才可确认
- [ ] **TC-9.2.7**：空列表状态显示引导文案和创建按钮

#### RoleManagementPage 权限编辑

- [ ] **TC-9.3.1**：角色列表渲染正确，内置角色标记 `[内置]`，自定义角色标记 `[自定义]`
- [ ] **TC-9.3.2**：点击 `[+ 新建角色]` → 抽屉打开 → 所有权限初始未勾选
- [ ] **TC-9.3.3**：编辑自定义角色 → 抽屉打开 → 已有权限已勾选
- [ ] **TC-9.3.4**：普通 editor 用户创建角色 → 超出 editor 权限范围的选项被 disabled
- [ ] **TC-9.3.5**：保存角色 → 调用 API → 成功后列表刷新
- [ ] **TC-9.3.6**：删除有用户引用的角色 → 提示 "该角色下有 N 个用户，无法删除"
- [ ] **TC-9.3.7**：内置角色不显示删除按钮

#### GodModeBanner

- [ ] **TC-9.4.1**：`godModeStore.isActive=true` 时横幅渲染
- [ ] **TC-9.4.2**：横幅显示租户名称、倒计时剩余时间
- [ ] **TC-9.4.3**：`canExtend=true` 时 `[续期]` 按钮可见
- [ ] **TC-9.4.4**：点击 `[退出 God Mode]` → 调用 exit API → 跳转到 `/admin/tenants`
- [ ] **TC-9.4.5**：剩余时间 < 5min → 弹窗提示续期
- [ ] **TC-9.4.6**：倒计时归零 → 自动退出

#### AuthGuard / RoleGuard

- [ ] **TC-9.5.1**：未登录用户访问 `/app/knowledge-bases` → 重定向到 `/login?redirect=...`
- [ ] **TC-9.5.2**：已登录用户访问 `/login` → 重定向到对应首页
- [ ] **TC-9.5.3**：租户用户访问 `/admin/tenants` → 重定向到 `/app/knowledge-bases`
- [ ] **TC-9.5.4**：超管访问 `/app/settings/users` → 正常通过（无租户上下文但 God Mode 激活时通过）
- [ ] **TC-9.5.5**：viewer 角色访问 `/app/settings/users` → 渲染 403 页面
- [ ] **TC-9.5.6**：viewer 角色访问 `/app/knowledge-bases` → 正常通过

### 4.2 集成测试

#### 超管完整流程

- [ ] **TC-9.6.1**：超管登录 → 跳转 `/admin/tenants` → 看到租户列表
- [ ] **TC-9.6.2**：超管创建租户 → 填写完整表单 → 创建成功 → 列表出现新租户
- [ ] **TC-9.6.3**：超管点击租户 → 进入详情页 → 概览 Tab 显示统计 → 配额 Tab 显示使用率
- [ ] **TC-9.6.4**：超管停用租户 → 确认 → 状态变为 disabled → 用户无法登录
- [ ] **TC-9.6.5**：超管进入租户 God Mode → 获取临时 JWT → 跳转租户首页 → 顶部显示横幅

#### God Mode 完整流程

- [ ] **TC-9.7.1**：超管在租户详情页点击 `[进入此租户]` → God Mode 激活 → 跳转 `/app/knowledge-bases` → 横幅显示
- [ ] **TC-9.7.2**：God Mode 中访问任意页面和资源 → 无权限拦截，全量可见
- [ ] **TC-9.7.3**：God Mode 中执行写操作 → 二次确认弹窗 → 确认后执行
- [ ] **TC-9.7.4**：点击横幅 `[退出 God Mode]` → 清除 session → 跳转回 `/admin/tenants`
- [ ] **TC-9.7.5**：超管 A 已进入租户 God Mode → 超管 B 尝试进入同一租户 → 返回错误提示
- [ ] **TC-9.7.6**：God Mode 超时 → 自动退出 → 跳转回 `/admin/tenants`

#### 用户管理流程

- [ ] **TC-9.8.1**：管理员进入 `/app/settings/users` → 看到用户列表
- [ ] **TC-9.8.2**：管理员邀请新用户 → 填写邮箱 + 角色 → 获得邀请链接
- [ ] **TC-9.8.3**：被邀请用户访问邀请链接 → 设置密码 → 激活成功 → 可登录
- [ ] **TC-9.8.4**：管理员编辑用户角色 → 分配新角色 → 用户刷新后权限更新
- [ ] **TC-9.8.5**：管理员禁用用户 → 用户尝试登录 → 返回 "账号已被禁用"

### 4.3 关键测试场景（≥ 8）

| # | 场景 | 步骤 | 验证点 |
|---|------|------|--------|
| 1 | **超管创建租户全流程** | 登录→创建租户→查看租户详情→验证统计→进入 God Mode | 租户创建成功、统计正确、God Mode 激活、横幅显示 |
| 2 | **租户用户登录 → 权限校验** | admin 登录→访问知识库→访问用户管理→viewer 登录→访问用户管理 | admin 可访问全部，viewer 看到 403 |
| 3 | **多角色权限边界** | 创建自定义角色 "编辑+查看者" → 分配用户 → 验证 kb:write 可写、user:manage 不可见 | 权限粒度正确生效 |
| 4 | **God Mode 全生命周期** | 进入→操作写资源（二次确认）→续期→主动退出 | 审计日志完整、倒计时正确、续期生效 |
| 5 | **God Mode 超时** | 进入后等待 30 分钟（或模拟过期）→ 操作资源 → 自动退出 | Token 过期、自动退出、跳转正确 |
| 6 | **租户状态流转** | active→停用→用户登录被拒→启用→用户登录成功→归档→访问被拒→恢复 | 状态转换正确、API 响应正确 |
| 7 | **邀请-激活用户闭环** | 邀请用户→复制链接→被邀请者访问链接设置密码→激活→登录→权限正确 | 全链路成功、Token 解析正确 |
| 8 | **角色视角切换** | admin 切换到 editor 视角→页面按钮变化→搜索以原始权限执行→切回本角色 | 前端过滤正确、不影响后端权限 |
| 9 | **角色权限约束** | editor 创建自定义角色 → 尝试添加 `kb:manage_acl` → 权限项 disabled | 不能越权授予 |
| 10 | **Token 自动刷新** | 登录 → 等待接近过期 → 触发下一个 API 调用 → 401 → 自动 refresh → 重试成功 | 刷新流程无感知、用户体验不受影响 |
| 11 | **路由守卫** | 未登录访问 `/app/knowledge-bases` → 跳转登录页 → viewer 访问 `/app/settings/users` → 403 | 守卫逻辑正确 |
| 12 | **租户删除二次确认** | 点击删除→弹窗显示警告→输入框空白→确认按钮 disabled→输入正确标识→确认按钮 enabled | 二次确认保护机制 |

---

## 5. 验收检查点

### 5.1 登录页

- [ ] 用户名/密码表单校验正常（必填、长度限制）
- [ ] 超管登录后跳转到 `/admin/tenants`
- [ ] 租户用户登录后跳转到 `/app/knowledge-bases`
- [ ] 禁用用户登录返回错误提示
- [ ] 登录失败显示错误信息
- [ ] 已登录用户访问 `/login` 自动跳转到对应首页
- [ ] 未登录用户访问任意页面重定向到 `/login?redirect=`，登录后跳回原页面

### 5.2 超管布局（AdminLayout）

- [ ] 左侧侧边栏展示正常，导航到 `/admin/tenants`
- [ ] 超管用户名显示在侧边栏底部
- [ ] `[退出登录]` 清除状态并跳转登录页
- [ ] 租户用户无法访问 `/admin/*` 路由（重定向）

### 5.3 租户列表页

- [ ] 租户表格正确展示名称、标识、状态（颜色正确）、用户数、存储用量、创建时间
- [ ] 搜索框按名称筛选正常工作（300ms 防抖）
- [ ] 状态筛选下拉（全部/活跃/已停用/已归档/已删除）正常工作
- [ ] 创建租户对话框表单校验正常（必填、slug 唯一性校验、邮箱格式）
- [ ] 创建租户成功后列表刷新，成功提示正确
- [ ] 停用/启用/归档/删除操作均有确认弹窗
- [ ] 删除操作二次确认需输入租户标识
- [ ] 空列表状态显示引导文案
- [ ] 分页正常工作

### 5.4 租户详情页

- [ ] 4 个选项卡（概览/用户/配额/操作日志）切换正常
- [ ] 概览 Tab：统计卡片（知识库数、文档数、管道数、用户数、存储用量）正确展示
- [ ] `[进入此租户]` 按钮 → God Mode 激活 → 跳转租户首页
- [ ] `[停用]` / `[启用]` / `[归档]` / `[删除]` 按钮根据状态正确显示/隐藏
- [ ] 配额 Tab：使用率进度条显示正确，接近上限时颜色变化
- [ ] `[调整配额]` 功能正常（修改后保存）
- [ ] 操作日志 Tab：正确展示审计日志，支持按类型筛选

### 5.5 God Mode

- [ ] God Mode 横幅持久显示在页面顶部，显示租户名称和倒计时
- [ ] 倒计时实时更新，格式 `mm:ss`
- [ ] 剩余 5 分钟时弹窗提示续期
- [ ] `[续期]` 按钮可用时点击生效（仅一次）
- [ ] `[退出 God Mode]` 清除状态 + 跳转回 `/admin/tenants`
- [ ] 倒计时归零自动退出
- [ ] God Mode 中写操作需二次确认（弹窗）
- [ ] God Mode 中所有资源全量可见，无权限拦截
- [ ] 并发限制：同一租户仅一个超管可进入 God Mode

### 5.6 租户内布局（TenantLayout）

- [ ] 上下文栏显示租户名称和角色标签
- [ ] 导航 Tab（知识库/管道/评估/设置）链接正确，高亮匹配当前路由
- [ ] 角色切换下拉在拥有多角色时可见
- [ ] "返回平台管理" 仅在 God Mode 激活时可见
- [ ] 退出登录功能正常

### 5.7 角色视角切换

- [ ] 切换到 editor 视角 → 写操作按钮 disabled/hidden
- [ ] 搜索功能以原始权限执行（不受视角切换影响）
- [ ] 切换回 "本角色" → 恢复正常权限
- [ ] 页面刷新后视角状态保持

### 5.8 用户管理

- [ ] 用户列表表格正确展示（用户名、邮箱、角色 Tag、状态、操作）
- [ ] 邀请用户对话框表单校验正常
- [ ] 邀请成功显示邀请链接 + `[复制链接]` 和 `[发送邮件]` 按钮
- [ ] 复制链接功能正常（clipboard API）
- [ ] 编辑用户角色功能正常
- [ ] 禁用用户后该用户无法登录
- [ ] 删除用户后用户列表刷新

### 5.9 角色管理

- [ ] 角色列表表格正确展示（角色名、权限摘要、内置标记、用户数）
- [ ] 新建/编辑角色抽屉正常打开，权限勾选矩阵按分类分组
- [ ] 编辑自定义角色时已有权限已勾选
- [ ] 权限约束：不能超越创建者自身权限范围
- [ ] 内置角色不显示删除按钮
- [ ] 删除有用户引用的角色时提示

### 5.10 路由守卫

- [ ] `AuthGuard`：未登录重定向到登录页
- [ ] `AuthGuard requireSuperadmin`：非超管无法访问 `/admin/*`
- [ ] `RoleGuard`：无权限角色访问受保护页面 → 显示 403 页面
- [ ] God Mode 中 `RoleGuard` 豁免所有权限检查
- [ ] 401 响应自动触发 token 刷新
- [ ] Token 刷新失败自动登出

### 5.11 前端代码规范

- [ ] 所有组件遵循前端目录结构约定（`features/auth/` 下按 pages/components/stores 组织）
- [ ] 无直接 Pydantic/BaseModel 定义（前端实体类型在 `entities/` 目录下使用 TypeScript interface）
- [ ] 无 `any` 类型（TypeScript 严格模式）
- [ ] API 客户端在 `api/auth/` 下集中管理
- [ ] 状态管理使用 Zustand（`authStore` + `godModeStore`）
- [ ] 所有注释全中文

---

## 附录 A：文件清单

| # | 文件 | 类型 |
|---|------|------|
| 1 | `features/auth/stores/authStore.ts` | 新建 |
| 2 | `features/auth/stores/godModeStore.ts` | 新建 |
| 3 | `api/auth/auth.ts` | 新建 |
| 4 | `api/auth/tenant.ts` | 新建 |
| 5 | `api/auth/user.ts` | 新建 |
| 6 | `api/auth/role.ts` | 新建 |
| 7 | `app/layouts/AdminLayout.tsx` | 新建 |
| 8 | `app/layouts/TenantLayout.tsx` | 新建 |
| 9 | `features/auth/components/RoleSwitcher.tsx` | 新建 |
| 10 | `features/auth/components/GodModeBanner.tsx` | 新建 |
| 11 | `features/auth/pages/LoginPage.tsx` | 新建 |
| 12 | `features/auth/pages/TenantListPage.tsx` | 新建 |
| 13 | `features/auth/pages/TenantDetailPage.tsx` | 新建 |
| 14 | `features/auth/pages/UserManagementPage.tsx` | 新建 |
| 15 | `features/auth/pages/RoleManagementPage.tsx` | 新建 |
| 16 | `features/auth/pages/AcceptInvitationPage.tsx` | 新建 |
| 17 | `features/auth/pages/ForbiddenPage.tsx` | 新建（403 页面） |
| 18 | `features/auth/components/AuthGuard.tsx` | 新建 |
| 19 | `features/auth/components/RoleGuard.tsx` | 新建 |
| 20 | `entities/auth/types.ts` | 新建（TypeScript 类型定义） |
| 21 | `shared/api/http-client.ts` | 改造（新增 401 拦截器 + token 刷新逻辑） |
| 22 | `router/routes.tsx` | 改造（新增全部路由 + 守卫包装） |

**合计**：约 20 个新建文件 + 2 个改造文件

## 附录 B：关键技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| `zustand` | 5.x | 状态管理（authStore, godModeStore） |
| `antd` | 6.x | UI 组件库（Table, Form, Modal, Drawer, Tabs, Tag, Menu, InputNumber, Select, Checkbox, Button, Tooltip, Skeleton, message） |
| `@ant-design/icons` | — | 图标（UserOutlined, LockOutlined, WarningOutlined 等） |
| `react-router-dom` | 7.x | SPA 路由（/login, /admin/*, /app/*） |
| `@tanstack/react-query` | 5.x | 服务端状态管理（租户列表/详情的缓存和重新获取） |
| `dayjs` | — | 时间格式化（创建时间、过期时间、倒计时） |

## 附录 C：与后端 Phase 1 的接口契约

| 前端功能 | 后端端点 | Phase |
|---------|---------|-------|
| 登录 | `POST /api/v1/auth/login` | Phase 1 §1.7 |
| Token 刷新 | `POST /api/v1/auth/refresh` | Phase 1 §1.7 |
| 租户列表 | `GET /api/v1/admin/tenants` | Phase 1 §1.7 |
| 租户详情 | `GET /api/v1/admin/tenants/:id` | Phase 1 §1.7 |
| 创建租户 | `POST /api/v1/admin/tenants` | Phase 1 §1.7 |
| 更新租户 | `PUT /api/v1/admin/tenants/:id` | Phase 1 §1.7 |
| 归档租户 | `PUT /api/v1/admin/tenants/:id/archive` | Phase 1 §1.7 |
| 恢复租户 | `PUT /api/v1/admin/tenants/:id/restore` | Phase 1 §1.7 |
| 删除租户 | `DELETE /api/v1/admin/tenants/:id` | Phase 1 §1.7 |
| 租户用户列表 | `GET /api/v1/admin/tenants/:id/users` | Phase 1 §1.7 |
| 进入 God Mode | `POST /api/v1/admin/tenants/:id/impersonate` | Phase 1 §1.7 |
| God Mode 日志 | `GET /api/v1/admin/tenants/:id/god-mode-log` | Phase 1 §1.7 |
| 用户列表 | `GET /api/v1/users` | Phase 1 §1.7 |
| 邀请用户 | `POST /api/v1/users/invite` | Phase 1 §1.7 |
| 接受邀请 | `POST /api/v1/users/accept-invitation` | Phase 1 §1.7 |
| 更新用户 | `PUT /api/v1/users/:id` | Phase 1 §1.7 |
| 删除用户 | `DELETE /api/v1/users/:id` | Phase 1 §1.7 |
| 角色列表 | `GET /api/v1/roles` | Phase 1 §1.7 |
| 创建角色 | `POST /api/v1/roles` | Phase 1 §1.7 |
| 更新角色 | `PUT /api/v1/roles/:id` | Phase 1 §1.7 |
| 删除角色 | `DELETE /api/v1/roles/:id` | Phase 1 §1.7 |
| 权限列表 | `GET /api/v1/permissions` | Phase 1 §1.7 |
