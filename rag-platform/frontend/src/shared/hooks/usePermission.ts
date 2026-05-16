/** 权限检查 Hook

提供基于用户角色的权限判断能力。
支持单个权限检查、多个权限 AND/OR 逻辑、角色判断。
*/
import { useMemo, useCallback } from 'react'
import { useAuth } from './useAuth'

/** 检查用户是否拥有指定权限 */
export function usePermission() {
  const { user, tenant } = useAuth()

  /** 用户拥有的所有权限（从角色继承） */
  const permissions = useMemo(() => {
    if (!user?.roles) return []
    // 超管拥有所有权限
    if (user.roles.includes('superadmin')) return ['*']
    // 从存储的角色信息中提取权限
    return user.roles.flatMap((role) => {
      if (role === 'admin') return ['*']
      if (role === 'editor') return ['kb:read', 'kb:write', 'pipeline:read', 'pipeline:write', 'eval:read', 'eval:run', 'search:use']
      if (role === 'viewer') return ['kb:read', 'pipeline:read', 'eval:read', 'search:use']
      return [role] // 自定义角色直接用 role slug
    })
  }, [user?.roles])

  /** 是否拥有指定权限 */
  const has = useCallback(
    (permission: string) => {
      if (permissions.includes('*')) return true
      return permissions.includes(permission)
    },
    [permissions]
  )

  /** 是否拥有全部指定权限（AND） */
  const hasAll = useCallback(
    (...perms: string[]) => perms.every((p) => has(p)),
    [has]
  )

  /** 是否拥有任一指定权限（OR） */
  const hasAny = useCallback(
    (...perms: string[]) => perms.some((p) => has(p)),
    [has]
  )

  /** 是否为超管 */
  const isSuperadmin = useMemo(() => !tenant, [tenant])

  /** 是否为租户管理员 */
  const isTenantAdmin = useMemo(
    () => user?.roles?.includes('admin') ?? false,
    [user?.roles]
  )

  return {
    permissions,
    has,
    hasAll,
    hasAny,
    isSuperadmin,
    isTenantAdmin,
    canManageUsers: has('admin:users'),
    canManageRoles: has('admin:roles'),
    canManageSettings: has('admin:settings'),
    canWriteKB: has('kb:write'),
    canPublishPipeline: has('pipeline:publish'),
    canRunEval: has('eval:run'),
  }
}
