/** 租户 */
export interface Tenant {
  id: string
  name: string
  slug: string
  status: 'active' | 'disabled' | 'archived'
  resource_limits: Record<string, number> | null
  user_count: number
  storage_usage_gb: number
  created_at: string
  updated_at: string
}

/** 用户 */
export interface User {
  id: string
  tenant_id: string
  username: string
  email: string
  status: 'active' | 'disabled'
  roles: string[]
  created_at: string
}

/** 角色 */
export interface Role {
  id: string
  tenant_id: string
  name: string
  slug: string
  permissions: string[]
  is_builtin: boolean
  created_at: string
}

/** 登录请求 */
export interface LoginRequest {
  username: string
  password: string
}

/** 登录响应 */
export interface LoginResponse {
  access_token: string
  refresh_token: string
  token_type: string
  user: User
  tenant: Tenant | null
}

/** 令牌刷新 */
export interface TokenRefreshResponse {
  access_token: string
  refresh_token: string
  token_type: string
}

/** 创建租户 */
export interface CreateTenantReq {
  name: string
  slug: string
  admin_user: {
    username: string
    email: string
    password: string
  }
  quotas?: {
    max_knowledge_bases?: number
    max_documents?: number
    max_users?: number
    max_storage_gb?: number
    max_search_qps?: number
  }
}

/** 创建用户 */
export interface CreateUserReq {
  username: string
  email: string
  password: string
  roles?: string[]
}

/** 创建角色 */
export interface CreateRoleReq {
  name: string
  slug: string
  permissions: string[]
}

/** 可用权限列表 */
export const PERMISSION_OPTIONS = [
  { value: 'kb:read', label: '知识库: 读取' },
  { value: 'kb:write', label: '知识库: 写入' },
  { value: 'kb:delete', label: '知识库: 删除' },
  { value: 'pipeline:read', label: '管道: 读取' },
  { value: 'pipeline:write', label: '管道: 写入' },
  { value: 'pipeline:publish', label: '管道: 发布' },
  { value: 'eval:read', label: '评估: 读取' },
  { value: 'eval:run', label: '评估: 运行' },
  { value: 'search:use', label: '搜索: 使用' },
  { value: 'admin:users', label: '管理: 用户' },
  { value: 'admin:roles', label: '管理: 角色' },
  { value: 'admin:settings', label: '管理: 系统配置' },
]

/** 用户邀请 */
export interface UserInvitation {
  id: string
  tenant_id: string
  email: string
  roles: string[]
  token: string
  expires_at: string
  accepted_at: string | null
  created_by: string
  created_at: string
}
