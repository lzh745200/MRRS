import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { apiRequest, _setCachedToken, prefetchCsrfToken } from '@/api/request'
import { useMenuStore } from '@/stores/menu'
import { getCurrentUser } from '@/api/queries/user'
import { AuthStorage } from '@/utils/authStorage'
import { ADMIN_ROLES } from '@/utils/roleAccess'
import { verifyLoginTwoFactor } from '@/api/twoFactor'
import type { AuthData } from '@/utils/authStorage'
import type { ApiResponse } from '@/types/api'

export type UserInfo = AuthData['user']

/** login() 返回结果 */
export type LoginResult =
  | { status: 'success' }
  | { status: 'two_factor_required'; tempToken: string }
  | { status: 'error'; message: string }

/** Wire-format login response (snake_case, matches backend JSON) */
interface LoginPayload {
  access_token: string
  refresh_token?: string
  token_type: string
  user: UserInfo
  must_change_password?: boolean
  two_factor_required?: boolean
  temp_token?: string
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref(AuthStorage.getToken() || '')
  const user = ref<UserInfo | null>(AuthStorage.getUser())
  const error = ref('')

  const isAuthenticated = computed(() => !!token.value)
  const isAdmin = computed(
    () => user.value?.is_superuser === true || ADMIN_ROLES.includes(user.value?.role ?? '')
  )
  /**
   * 回收站入口可见性：仅 super_admin/admin 可见软删记录。
   *
   * 采用严格路线（参考 AGENTS.md "软删除模式" 章节）：
   *   - True → UI 显示"回收站"入口，请求列表时附加 `include_deleted=true`
   *   - False → 入口隐藏；后端 `enforce_admin_include_deleted` 依赖会兜底降级
   *
   * 注意：manager/approval_leader 不在允许列表内（数据范围 OWN_DEPT
   * 不等于"可查看软删记录"）。
   */
  const canViewDeleted = computed(
    () => user.value?.is_superuser === true || ADMIN_ROLES.includes(user.value?.role ?? '')
  )
  const mustChangePassword = computed(() => user.value?.must_change_password ?? false)

  /**
   * 模块级权限映射：将用户权限列表（如 ["village:read", "village:write"]）
   * 转换为结构化查找表 { village: { view: true, edit: true }, ... }
   * 用于 v-permission 指令的 view/edit 粒度控制
   */
  const modulePermissions = computed(() => {
    const perms: string[] = user.value?.permissions || []
    // super_admin 拥有所有模块的全部权限 — 不使用硬编码列表，任何模块皆可
    if (user.value?.is_superuser || user.value?.role === 'super_admin') {
      return new Proxy<Record<string, { view: boolean; edit: boolean }>>(Object.create(null), {
        get(_target, prop: string) {
          if (prop === 'then' || prop === 'toJSON') return undefined
          return { view: true, edit: true }
        },
        has(_target, _prop: string) {
          return true
        },
      })
    }
    const result: Record<string, { view: boolean; edit: boolean }> = {}
    for (const p of perms) {
      const parts = p.split(':')
      if (parts.length >= 2) {
        const module = parts[0]
        const action = parts.slice(1).join(':')
        if (!result[module]) {
          result[module] = { view: false, edit: false }
        }
        if (action === 'read') result[module].view = true
        if (action === 'write' || action === 'delete' || action === 'manage_roles') {
          result[module].edit = true
        }
      }
    }
    return result
  })

  function persistAuth(t: string, u: UserInfo, refreshToken?: string) {
    token.value = t
    user.value = u
    _setCachedToken(t)
    AuthStorage.setAuthData({ token: t, user: u, refreshToken })
    // 预取 CSRF token：避免首次 POST/PUT/DELETE 请求因懒加载失败而返回 403
    prefetchCsrfToken().catch(() => {
      // 预取失败不阻断登录流程，后续请求会自动重试获取
    })
  }

  function logout() {
    token.value = ''
    user.value = null
    error.value = ''
    _setCachedToken(null)
    AuthStorage.clear()
  }

  /** 当前认证数据（供"记住登录"持久化） */
  function getAuthData(): AuthData | null {
    return { token: token.value, user: user.value as AuthData['user'], refreshToken: undefined }
  }

  /**
   * 登录；返回 LoginResult 表示登录结果。
   * - success: 登录成功
   * - two_factor_required: 需要 2FA 验证（附带 tempToken）
   * - error: 登录失败
   */
  async function login(username: string, password: string): Promise<LoginResult> {
    error.value = ''

    try {
      const res = await apiRequest<ApiResponse<LoginPayload>>({
        method: 'POST',
        url: '/auth/login',
        data: { username, password },
        timeout: 60000, // 登录超时 60s，bcrypt 纯 Python 回退时仍需安全兜底
      })

      if (res.code === 200) {
        // 2FA 挑战：后端要求双因素认证
        if (res.two_factor_required && res.temp_token) {
          return { status: 'two_factor_required', tempToken: res.temp_token as string }
        }

        // 正常登录成功
        if (res.data) {
          persistAuth(res.data.access_token, res.data.user, res.data.refresh_token)
          // 登录后立即预加载菜单 — 避免侧边栏渲染时 loaded=false 导致闪烁或泄露
          // 使用 try-catch 防止菜单加载失败影响登录流程
          try {
            useMenuStore()
              .fetchMenus()
              .catch(() => {})
          } catch {
            /* ignore */
          }
          return { status: 'success' }
        }
      }

      error.value = res.message || '登录失败'
      return { status: 'error', message: error.value }
    } catch (err: any) {
      const msg = err?.response?.data?.message || err?.message || '登录失败'
      error.value = msg
      return { status: 'error', message: msg }
    }
  }

  /**
   * 2FA 登录验证：使用 temp_token + TOTP 验证码完成登录。
   * 返回 true 表示验证成功并完成登录，false 表示失败。
   */
  async function verifyTwoFactorLogin(tempToken: string, code: string): Promise<boolean> {
    error.value = ''

    try {
      const res = await verifyLoginTwoFactor(tempToken, code)

      if (res.code === 200 && res.data) {
        persistAuth(res.data.access_token, res.data.user, res.refresh_token)
        useMenuStore().fetchMenus()
        return true
      }

      error.value = res.message || '2FA验证失败'
      return false
    } catch (err: any) {
      const msg =
        err?.response?.data?.detail || err?.response?.data?.message || err?.message || '2FA验证失败'
      error.value = msg
      return false
    }
  }

  /**
   * 页面刷新时恢复用户信息（token 已存在但 user 对象可能丢失）。
   * 仅在有 token 但无 user 时调用。
   */
  async function fetchUser() {
    if (!token.value || user.value) return
    try {
      const res = await getCurrentUser()
      if (res.code === 200 && res.data) {
        user.value = res.data as UserInfo
        AuthStorage.setUser(res.data as UserInfo)
      }
    } catch {
      // 401 已由 api/request.ts 拦截器 + 路由守卫处理跳转
    }
  }

  return {
    token,
    user,
    error,
    mustChangePassword,
    isAuthenticated,
    isAdmin,
    canViewDeleted,
    modulePermissions,
    logout,
    login,
    verifyTwoFactorLogin,
    fetchUser,
    getAuthData,
  }
})
