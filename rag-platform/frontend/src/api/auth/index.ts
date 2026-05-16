/** 认证与用户管理 API 客户端 */
import apiClient from '@/shared/api/client'
import type {
  LoginRequest, LoginResponse, TokenRefreshResponse,
  Tenant, CreateTenantReq,
  User, CreateUserReq,
  Role, CreateRoleReq,
  UserInvitation,
} from '@/entities/auth/types'

const BASE = '/api/v1'

// ── 认证 ──

export async function login(data: LoginRequest): Promise<LoginResponse> {
  const res = await apiClient.post(`${BASE}/auth/login`, data)
  return (res as unknown as { data: LoginResponse }).data
}

export async function refreshToken(refreshToken: string): Promise<TokenRefreshResponse> {
  const res = await apiClient.post(`${BASE}/auth/refresh`, { refresh_token: refreshToken })
  return (res as unknown as { data: TokenRefreshResponse }).data
}

export async function switchRole(role: string): Promise<LoginResponse> {
  const res = await apiClient.post(`${BASE}/auth/switch-role`, { role })
  return (res as unknown as { data: LoginResponse }).data
}

// ── 租户管理 (超管) ──

export async function getTenants(params?: {
  page?: number; page_size?: number; search?: string
}): Promise<{ items: Tenant[]; total: number }> {
  const res = await apiClient.get(`${BASE}/admin/tenants`, { params })
  return (res as unknown as { data: { items: Tenant[]; total: number } }).data
}

export async function getTenant(id: string): Promise<Tenant> {
  const res = await apiClient.get(`${BASE}/admin/tenants/${id}`)
  return (res as unknown as { data: Tenant }).data
}

export async function createTenant(data: CreateTenantReq): Promise<Tenant> {
  const res = await apiClient.post(`${BASE}/admin/tenants`, data)
  return (res as unknown as { data: Tenant }).data
}

export async function updateTenant(id: string, data: Partial<CreateTenantReq>): Promise<Tenant> {
  const res = await apiClient.put(`${BASE}/admin/tenants/${id}`, data)
  return (res as unknown as { data: Tenant }).data
}

// ── 用户管理 ──

export async function getUsers(params?: {
  page?: number; page_size?: number; search?: string
}): Promise<{ items: User[]; total: number }> {
  const res = await apiClient.get(`${BASE}/users`, { params })
  return (res as unknown as { data: { items: User[]; total: number } }).data
}

export async function createUser(data: CreateUserReq): Promise<User> {
  const res = await apiClient.post(`${BASE}/users`, data)
  return (res as unknown as { data: User }).data
}

export async function updateUser(id: string, data: Partial<CreateUserReq>): Promise<User> {
  const res = await apiClient.put(`${BASE}/users/${id}`, data)
  return (res as unknown as { data: User }).data
}

export async function deleteUser(id: string): Promise<void> {
  await apiClient.delete(`${BASE}/users/${id}`)
}

// ── 角色管理 ──

export async function getRoles(): Promise<Role[]> {
  const res = await apiClient.get(`${BASE}/roles`)
  return (res as unknown as { data: Role[] }).data
}

export async function createRole(data: CreateRoleReq): Promise<Role> {
  const res = await apiClient.post(`${BASE}/roles`, data)
  return (res as unknown as { data: Role }).data
}

export async function updateRole(id: string, data: Partial<CreateRoleReq>): Promise<Role> {
  const res = await apiClient.put(`${BASE}/roles/${id}`, data)
  return (res as unknown as { data: Role }).data
}

export async function deleteRole(id: string): Promise<void> {
  await apiClient.delete(`${BASE}/roles/${id}`)
}

// ── 用户邀请 ──

export async function inviteUser(data: { email: string; roles: string[] }): Promise<UserInvitation> {
  const res = await apiClient.post(`${BASE}/users/invite`, data)
  return (res as unknown as { data: UserInvitation }).data
}

export async function getInvitations(): Promise<UserInvitation[]> {
  const res = await apiClient.get(`${BASE}/users/invitations`)
  return (res as unknown as { data: UserInvitation[] }).data
}
