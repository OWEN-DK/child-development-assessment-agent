# 04 — 权限与多租户

> **定位**：定义平台超管、租户管理、双层权限控制（库级别 + 文档级别）的完整规则。权限是横切关注点——在所有检索流程中强制注入，不可绕过。
> **与核心目标的关系**：实现 [核心目标 §三](./core-objectives.md#三双层权限控制库级别--文档级别全局强制) + 多租户管理。

---

## 配置层级

| 层级 | 谁配置 | 存储位置 | 示例 |
|------|--------|---------|------|
| **平台级** | 超管 | MySQL `tenants` + `tenant_quotas` | 创建/停用租户、资源配额、系统内置角色定义（admin/editor/viewer 的默认权限集） |
| **租户级** | 租户 admin | MySQL `roles` + `users` + 全局配置 | 自定义角色、用户邀请/禁用、租户级权限策略 |
| **资源级** | 租户 editor / 资源所有者 | MySQL `knowledge_bases.visibility` + 向量 metadata `doc_acl` | 单个知识库 visibility、单个文档 access_level + doc_acl |
| **JWT 自动注入** | 系统自动 | JWT claims | `tenant_id`、`user_id`、`roles` —— 登录签名时写入，不可手动配置 |

---

## 1. 角色层级

```
平台超管（system-level，管理所有租户）
  │
  ├── 租户 A
  │     ├── admin: 管理知识库/管道/用户/配置/监控
  │     ├── editor: 创建编辑知识库/管道，运行评估，执行搜索
  │     ├── viewer: 只读访问已授权资源，执行搜索
  │     └── 自定义角色: 客户自定义权限组合
  │
  └── 租户 B
        └── ...
```

### 1.1 超管

超管不属于任何租户。JWT 中无 `tenant_id`。登录后进入 `/admin/tenants`。

**超管权限**：
- 创建/停用/删除租户
- 查看所有租户详情（用户、配额、统计、操作日志）
- **进入任意租户上下文**——以 God 视角访问该租户所有资源，无视 `visibility`/`doc_acl`/RBAC
- 进入租户后顶部栏显示"当前以超管身份访问仁和医院"，可随时返回平台管理

**超管不可**：
- 登录普通租户（无 JWT `tenant_id`，不可直接访问租户登录页）

**God Mode 安全约束**：

| 约束项 | 规则 |
|--------|------|
| **会话超时** | God Mode 默认 30 分钟自动退出租户上下文，可续期一次（+30 分钟） |
| **操作范围** | God Mode 默认**只读**。执行写操作（删除文档、修改管道配置、变更权限）需二次确认弹窗 |
| **操作审计** | God Mode 期间的所有操作写入 `god_mode_audit_log`（含操作类型、目标资源、操作详情），不只是进入/退出 |
| **不可撤销** | God Mode 操作不可回滚，UI 中需显式提示"当前以超管身份操作，此操作不可撤销" |
| **并发限制** | 同一时间只允许一个超管进入同一租户的 God Mode |

### 1.2 内置租户角色

| 角色 | 标识 | 权限范围 |
|------|------|---------|
| **管理员** | `admin` | 租户内全部：知识库+管道+评估+用户管理+配置+监控 |
| **编辑者** | `editor` | 知识库和管道的创建/编辑/删除、评估运行、搜索执行 |
| **查看者** | `viewer` | 只读访问已授权知识库和管道、执行搜索 |

---

## 2. 租户管理（超管页面）

### 2.1 租户列表 `/admin/tenants`

```
┌─ 租户管理 ────────────────────────────────────────────────────┐
│  [+ 创建租户]                                                    │
│                                                                │
│  ┌────────┬────────┬──────┬────────┬──────────┬────────────┐  │
│  │ 名称    │ 标识    │ 状态  │ 用户数   │ 存储用量   │ 操作        │  │
│  │ 仁和医院 │ renhe   │ ✅   │ 26     │ 2.3 GB   │ 查看 停用   │  │
│  │ 协和医院 │ xiehe   │ ✅   │ 52     │ 5.1 GB   │ 查看 停用   │  │
│  │ 中伦律所 │ zhonglun│ ✅   │ 8      │ 0.8 GB   │ 查看 停用   │  │
│  └────────┴────────┴──────┴────────┴──────────┴────────────┘  │
│  共 3 个租户                                                     │
└──────────────────────────────────────────────────────────────────┘
```

### 2.2 创建租户 `/admin/tenants` → 弹出创建表单

```
创建租户:

  租户名称: [仁和医院                ]  (显示名称)
  租户标识: [renhe                  ]  (唯一，用于存储路径和 API 上下文)
  初始管理员:
    用户名: [zhang                  ]
    邮箱:   [zhang@renhe.com        ]
    初始密码: [********              ]

  资源配额:
    知识库上限: [10    ]
    文档总量上限: [100万 ]
    用户数上限:  [100   ]
    存储上限:    [50 GB ]
    搜索 QPS 上限:[50   ]

  [创建] [取消]
```

**创建租户时后端自动执行**：
1. 数据库：初始化租户数据空间（`tenant_id` 行级过滤 + 租户记录插入）
2. 存储：创建 `storage/{tenant_id}/` 目录树
3. 角色：插入默认 admin/editor/viewer 角色记录
4. 用户：创建初始管理员用户（绑定 admin 角色）
5. 配额：记录配额限制到租户配置

### 2.3 租户详情 `/admin/tenants/:id`

```
┌─ ← 租户列表  │  仁和医院  │  ✅ 活跃  │  [停用] [删除]  ──────────────┐
│                                                                      │
│  [概览] [用户] [配额] [操作日志]                                         │
│                                                                      │
│  【概览】                                                              │
│  ┌────────┬────────┬────────┬────────┬────────┐                      │
│  │ 知识库   │ 文档    │ 管道    │ 用户    │ 存储    │                      │
│  │ 5      │ 12,500 │ 3      │ 26     │ 2.3 GB │                      │
│  └────────┴────────┴────────┴────────┴────────┘                      │
│  搜索统计(30天): 12,300 次 │ 平均延迟: 1.8s │ 错误率: 0.3%              │
│                                                                      │
│  [进入此租户] — 以超管身份访问仁和医院全部资源                              │
│                                                                      │
│  【用户】该租户所有用户列表，可查看、重置密码、禁用                           │
│  【配额】知识库 5/10 │ 文档 12,500/100万 │ 用户 26/100 │ 存储 2.3/50 GB    │
│          [调整配额...]                                                 │
│  【操作日志】租户创建时间、管理员变更、停用/启用历史                           │
└──────────────────────────────────────────────────────────────────────┘
```

**停用租户**：禁止该租户所有用户登录，搜索 API 返回 403。数据保留。
**归档租户**：租户状态 → `archived`。禁止登录和 API 访问，数据保留但不计入活跃配额。可随时恢复为 `active`。
**删除租户**：软删除（`deleted_at` 标记） → 30 天保留期 → 自动物理清理。保留期内可恢复。物理清理前自动生成数据导出快照（MySQL dump + 向量存储元数据 + 文件列表），快照保留 90 天。需二次确认输入租户标识。

---

## 3. 租户内部（权限控制）

### 3.1 上下文栏

所有租户内页面顶部：

```
┌──────────────────────────────────────────────────────────────┐
│  📚 知识    🔧 管道    ⚙️ 设置                                 │
│                                                              │
│  仁和医院 │ 管理员 │ [切换角色视角 ▾]          [← 返回平台管理]  │
└──────────────────────────────────────────────────────────────┘
```

- "切换角色视角"：管理员可模拟普通医生角色预览页面——知识库列表和管道列表按该角色权限过滤
- "← 返回平台管理"：仅超管可见，退出租户上下文返回 `/admin/tenants`

### 3.2 租户隔离

| 隔离对象 | 实现 |
|---------|------|
| 数据库 | `tenant_id` 行级过滤（Repository 基类自动注入） |
| 向量存储 | 命名约定 `{tenant_id}_{kb_id}` |
| 文件存储 | `storage/{tenant_id}/` |
| 缓存 | Redis Key 前缀含 `tenant_id` |
| API 上下文 | JWT 携带 `tenant_id`、`user_id`、`roles`。中间件提取后注入请求上下文 |

**行级过滤的结构约束**（防止开发者遗漏 `tenant_id` 过滤导致跨租户泄漏）：

| 约束层 | 措施 |
|--------|------|
| **ORM 层** | `BaseRepository` 所有查询方法自动注入 `WHERE tenant_id = :tenant_id`。子类禁止覆写此行为 |
| **SQL 审计** | 开发环境启用 SQL 日志审计，检测并告警不含 `tenant_id` 条件的 SELECT/UPDATE/DELETE 语句 |
| **CI 静态扫描** | CI 流水线中 grep 扫描所有 `.py` 文件，检测裸 SQL（`text()`/`execute()`）调用并阻断合并 |
| **后台任务** | 定时任务/异步任务必须显式传入 `tenant_id` 参数。无 `tenant_id` 上下文的任务禁止执行数据访问，抛出 `MissingTenantContextError` |
| **数据库兜底（二期）** | MySQL 8.0+ Row-Level Security 策略，或通过视图层强制过滤，作为最后防线 |

### 3.3 RBAC 页面 `/settings/users`

```
┌─ [用户] [角色] ──────────────────────────────────────────────┐
│                                                                │
│  【用户】                                                       │
│  [+ 邀请用户]                                                    │
│  ┌──────┬──────────┬────────────────────┬─────┬──────┐        │
│  │ 用户名 │ 邮箱      │ 角色                 │ 状态 │ 操作  │        │
│  │ 张主任 │ z@h.com  │ [管理员]              │ ✅  │ ...  │        │
│  │ 李医生 │ li@h.com │ [普通医生] [药师]      │ ✅  │ ...  │        │
│  └──────┴──────────┴────────────────────┴─────┴──────┘        │
│                                                                │
│  【角色】                                                       │
│  [+ 新建角色]                                                    │
│  ┌────────┬────────────────────────────────────┬─────┐        │
│  │ 角色名   │ 权限                                 │ 用户数│        │
│  │ 管理员   │ 全部                                 │ 2   │        │
│  │ 普通医生 │ kb:r(受限), search:ex               │ 15  │        │
│  └────────┴────────────────────────────────────┴─────┘        │
│                                                                │
│  编辑角色 → 抽屉勾选权限:                                          │
│    知识库: ☑ kb:read  ☐ kb:write  ☐ kb:delete  ☐ kb:manage_acl │
│    管道:   ☑ pipeline:read  ☐ pipeline:write  ☐ pipeline:publish│
│    搜索:   ☑ search:execute  ☐ search:stream                    │
│    评估:   ☐ eval:read  ☐ eval:write                           │
│    系统:   ☐ system:config  ☐ system:monitor                   │
└──────────────────────────────────────────────────────────────────┘
```

**用户邀请流程**：
1. 管理员输入邮箱 + 选择角色 → 点击"邀请"
2. 系统生成一次性邀请链接（含 token，24h 过期）
3. 发送邮件（或直接复制链接给用户）
4. 用户点击链接 → 设置密码 → 激活账号
5. 邀请链接过期可重新发送

### 3.4 双层 Pre-filter（检索时）

保留原有设计（详见旧版 §3），此处简述：

| 层级 | 时机 | 对象 | 方式 |
|------|------|------|------|
| 库级别 | 域分发前 | 知识库 → 域激活计划 | 裁剪无权限知识库对应的域 |
| 文档级别 | 检索执行时 | 域管道内候选文档 | 向量查询条件注入 `doc_acl` 过滤 |

超管进入租户后两层过滤均不生效（全量可见）。

**ACLFilterBuilder 统一接口**（文档级过滤的实现抽象）：

三种向量后端的 ACL 过滤语法不同，通过 `ACLFilterBuilder` 统一抽象：

```python
class ACLFilterBuilder(ABC):
    """根据用户角色构建向量存储的 ACL 过滤条件。"""

    @abstractmethod
    def build_filter(self, user_roles: list[str]) -> dict:
        """将用户角色列表转换为当前后端的过滤条件。
        - Chroma: 返回 where 条件 dict
        - Elasticsearch: 返回 filter clause list
        - Milvus: 返回 expr 字符串
        """
        ...

class ChromaACLFilterBuilder(ACLFilterBuilder): ...
class ESACLFilterBuilder(ACLFilterBuilder): ...
class MilvusACLFilterBuilder(ACLFilterBuilder): ...
```

**调用位置**：PipelineCompiler 执行检索节点时，通过知识库的向量后端类型获取对应的 `ACLFilterBuilder` 实例，将用户角色转换为过滤条件注入检索查询。

**不可妥协**：
- 所有检索节点必须通过 `ACLFilterBuilder` 注入 ACL 过滤，禁止跳过
- 三种后端的过滤行为必须一致（同一用户、同一知识库，三种后端返回相同的文档子集）
- 超管 God Mode 时 `build_filter` 返回空条件（不过滤）

### 3.5 角色视角切换

管理员在顶部栏切换角色后：
- 页面权限按所选角色重新计算（按钮灰掉/隐藏、列表过滤）
- 不会改变实际用户身份（JWT 不变）
- 搜索和评估以所选角色权限执行（验证权限是否生效）
- 选择"返回本角色"恢复原始权限

---

## 4. 知识库与文档权限

保留原有权限模型，详见 §4、§5（旧版），此处不重复。

| 属性 | 类型 | 说明 |
|------|------|------|
| `visibility` | enum | `public` / `role_scoped` / `private` |
| `visible_roles` | list[str] | role_scoped 时生效 |
| `doc_acl` | list[str] | 文档可访问角色列表 |
| `access_level` | enum | `inherit` / `restricted` |

权限继承规则、变更副作用保留不变。

---

## 5. 数据模型（新增表）

| 表名 | 关键字段 |
|------|---------|
| `tenants` | id, name, slug, status (active/disabled/archived/deleted), resource_limits (JSON), deleted_at, created_at, updated_at |
| `users` | id, tenant_id (NULL=超管), username, password_hash, email, status, deleted_at, created_at |
| `roles` | id, tenant_id, name, permissions (JSON), is_builtin, created_at |
| `user_roles` | user_id, role_id |
| `user_invitations` | id, tenant_id, email, roles (JSON), token, expires_at, accepted_at, created_by |
| `permission_audit_log` | id, tenant_id, actor_id, action, target_type, target_id, old_value, new_value, created_at |
| `tenant_audit_log` | id, tenant_id, actor_id (超管), action, details, created_at |
| `god_mode_audit_log` | id, tenant_id, actor_id (超管), action, target_type, target_id, details, session_started_at, created_at |
| `tenant_deletion_snapshots` | id, tenant_id, snapshot_path, status (pending/ready/expired), expires_at, created_at |

---

## 6. API 端点

### 6.1 超管 API（前缀 `/api/v1/admin`）

| 方法 | 路径 | 描述 |
|------|------|------|
| `POST` | `/tenants` | 创建租户（含初始管理员） |
| `GET` | `/tenants` | 租户列表（支持按状态筛选：active/disabled/archived/deleted） |
| `GET` | `/tenants/{id}` | 租户详情（含统计） |
| `PUT` | `/tenants/{id}` | 更新租户（启用/停用/调整配额） |
| `PUT` | `/tenants/{id}/archive` | 归档租户（禁止访问，数据保留，不计配额） |
| `PUT` | `/tenants/{id}/restore` | 恢复已归档或已软删除的租户 |
| `DELETE` | `/tenants/{id}` | 软删除租户（30 天保留期，自动生成数据导出快照） |
| `GET` | `/tenants/{id}/users` | 租户用户列表 |
| `POST` | `/tenants/{id}/impersonate` | 超管进入租户上下文（返回临时 JWT，30 分钟超时） |
| `GET` | `/tenants/{id}/god-mode-log` | God Mode 操作审计日志 |

### 6.2 租户内 API（前缀 `/api/v1`）

| 方法 | 路径 | 描述 |
|------|------|------|
| `POST` | `/auth/login` | 登录 |
| `GET` | `/users` | 用户列表 |
| `POST` | `/users/invite` | 邀请用户 |
| `POST` | `/users/accept-invitation` | 接受邀请（设置密码） |
| `PUT` | `/users/{id}` | 更新用户（角色分配、禁用） |
| `DELETE` | `/users/{id}` | 删除用户 |
| `GET` | `/roles` | 角色列表 |
| `POST` | `/roles` | 创建自定义角色 |
| `PUT` | `/roles/{id}` | 更新角色权限 |
| `DELETE` | `/roles/{id}` | 删除角色（检查引用） |
| `GET` | `/permissions` | 可用权限列表 |

---

## 7. 验收标准

### 超管与租户管理

- [ ] AC-4.1：超管登录后看到租户列表，可创建/停用/归档/删除租户
- [ ] AC-4.2：创建租户后自动初始化 DB 空间、存储目录、默认角色、初始管理员
- [ ] AC-4.3：超管进入租户后无视所有权限过滤，可操作该租户一切资源
- [ ] AC-4.4：超管进入租户后顶部显示"当前以超管身份访问 XXX"，可一键返回平台管理
- [ ] AC-4.5：停用租户后该租户所有用户无法登录，搜索 API 返回 403
- [ ] AC-4.6：删除租户为软删除（30 天保留期），保留期内可恢复；物理清理前自动生成数据导出快照
- [ ] AC-4.7：租户详情正确展示用户数、知识库数、存储用量、配额使用率
- [ ] AC-4.7a：归档租户后禁止登录和 API 访问，数据保留但不计入活跃配额，可随时恢复
- [ ] AC-4.7b：God Mode 会话 30 分钟超时，操作写入 `god_mode_audit_log`，写操作需二次确认

### 租户内权限

- [ ] AC-4.8：不同租户数据完全隔离，不可跨租户访问
- [ ] AC-4.8a：行级过滤有结构约束兜底——CI 静态扫描阻断裸 SQL 合并，后台任务无 `tenant_id` 时抛出 `MissingTenantContextError`
- [ ] AC-4.9：管理员邀请用户 → 发送邀请链接 → 用户接受邀请设置密码 → 激活成功
- [ ] AC-4.10：自定义角色权限不能超出创建者自身权限范围
- [ ] AC-4.11：管理员切换角色视角后页面内容按所选角色过滤
- [ ] AC-4.12：库级别权限：无权限知识库对应域在域分发时被裁剪
- [ ] AC-4.13：文档级别权限：同一知识库内不同角色检索到不同文档子集
- [ ] AC-4.13a：`ACLFilterBuilder` 三种后端实现一致——同一用户同一知识库，Chroma/ES/Milvus 返回相同文档子集
- [ ] AC-4.14：权限变更后 30 秒内相关缓存失效
- [ ] AC-4.15：所有搜索方式强制启用双层权限过滤

---

## 8. 与其他模块的接口

| 被依赖 | 接口 |
|--------|------|
| 所有模块 | JWT 认证中间件（tenant_id + user_id + roles 注入请求上下文） |
| [03-knowledge-base](./03-knowledge-base.md) | 知识库 visibility/visible_roles；文档 access_level/doc_acl |
| [01-pipeline-model](./01-pipeline-model-and-engine.md) | PipelineCompiler 调用权限模块注入域裁剪和文档过滤 |
| [06-rag-evaluation](./06-rag-evaluation.md) | 评估数据集权限隔离、运行角色模拟 |
