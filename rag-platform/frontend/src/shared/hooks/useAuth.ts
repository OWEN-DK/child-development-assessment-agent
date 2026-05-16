/** 认证 Hook

提供用户登录状态、令牌管理、角色切换等能力。
从 localStorage 读取 JWT，解析 payload 获取用户信息。
*/
import { useState, useCallback, useMemo } from 'react'
import type { User, Tenant } from '@/entities/auth/types'
import { login as apiLogin, switchRole as apiSwitchRole } from '@/api/auth'

interface AuthState {
  user: User | null
  tenant: Tenant | null
  token: string | null
  refreshToken: string | null
  isAuthenticated: boolean
  isLoading: boolean
}

/** 从 JWT payload 中解码用户信息（不验证签名） */
function decodeJwtPayload(token: string): Record<string, unknown> | null {
  try {
    const base64Url = token.split('.')[1]
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/')
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    )
    return JSON.parse(jsonPayload)
  } catch {
    return null
  }
}

export function useAuth() {
  const [state, setState] = useState<AuthState>(() => {
    const token = localStorage.getItem('token')
    const refreshToken = localStorage.getItem('refresh_token')
    const cachedUser = localStorage.getItem('user')
    const cachedTenant = localStorage.getItem('tenant')

    return {
      user: cachedUser ? JSON.parse(cachedUser) : null,
      tenant: cachedTenant ? JSON.parse(cachedTenant) : null,
      token,
      refreshToken,
      isAuthenticated: !!token,
      isLoading: false,
    }
  })

  /** 登录 */
  const login = useCallback(async (username: string, password: string) => {
    setState((s) => ({ ...s, isLoading: true }))
    try {
      const result = await apiLogin({ username, password })
      localStorage.setItem('token', result.access_token)
      localStorage.setItem('refresh_token', result.refresh_token)
      localStorage.setItem('user', JSON.stringify(result.user))
      if (result.tenant) {
        localStorage.setItem('tenant', JSON.stringify(result.tenant))
      }
      setState({
        user: result.user,
        tenant: result.tenant,
        token: result.access_token,
        refreshToken: result.refresh_token,
        isAuthenticated: true,
        isLoading: false,
      })
    } catch {
      setState((s) => ({ ...s, isLoading: false }))
      throw new Error('登录失败')
    }
  }, [])

  /** 登出 */
  const logout = useCallback(() => {
    localStorage.removeItem('token')
    localStorage.removeItem('refresh_token')
    localStorage.removeItem('user')
    localStorage.removeItem('tenant')
    setState({
      user: null,
      tenant: null,
      token: null,
      refreshToken: null,
      isAuthenticated: false,
      isLoading: false,
    })
  }, [])

  /** 切换角色 */
  const switchRole = useCallback(async (role: string) => {
    const result = await apiSwitchRole(role)
    localStorage.setItem('token', result.access_token)
    localStorage.setItem('user', JSON.stringify(result.user))
    setState((s) => ({
      ...s,
      user: result.user,
      token: result.access_token,
    }))
  }, [])

  /** 检查令牌是否即将过期（5 分钟内） */
  const isTokenExpiring = useMemo(() => {
    if (!state.token) return false
    const payload = decodeJwtPayload(state.token)
    if (!payload?.exp) return false
    const expMs = (payload.exp as number) * 1000
    return Date.now() > expMs - 5 * 60 * 1000
  }, [state.token])

  return {
    ...state,
    login,
    logout,
    switchRole,
    isTokenExpiring,
  }
}
