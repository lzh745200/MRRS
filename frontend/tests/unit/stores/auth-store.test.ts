import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

vi.mock('@/api/request', () => ({
  default: vi.fn(),
  apiRequest: vi.fn(),
  _setCachedToken: vi.fn(),
  prefetchCsrfToken: vi.fn().mockResolvedValue(undefined),
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

vi.mock('@/api/queries/user', () => ({
  getCurrentUser: vi.fn(),
}))

vi.mock('@/utils/authStorage', () => {
  const storage: any = {
    getToken: vi.fn(),
    getUser: vi.fn(),
    getRefreshToken: vi.fn(),
    setToken: vi.fn(),
    setUser: vi.fn(),
    setRefreshToken: vi.fn(),
    setAuthData: vi.fn(),
    clear: vi.fn(),
  }
  // Default returns
  storage.getToken.mockReturnValue('')
  storage.getUser.mockReturnValue(null)
  storage.getRefreshToken.mockReturnValue('')
  return { AuthStorage: storage }
})

vi.mock('@/utils/roleAccess', () => ({
  ADMIN_ROLES: ['admin', 'superadmin'],
}))

vi.mock('@/stores/menu', () => ({
  useMenuStore: () => ({ fetchMenus: vi.fn().mockResolvedValue(undefined) }),
}))

import { apiRequest, _setCachedToken } from '@/api/request'
import { getCurrentUser } from '@/api/queries/user'
import { AuthStorage } from '@/utils/authStorage'
import { useAuthStore } from '@/stores/auth'

describe('stores/auth', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    // Reset mock impls to defaults
    ;(AuthStorage.getToken as any).mockReturnValue('')
    ;(AuthStorage.getUser as any).mockReturnValue(null)
  })

  describe('initial state', () => {
    it('token/user/error 初始值', () => {
      ;(AuthStorage.getToken as any).mockReturnValue('stored-token')
      ;(AuthStorage.getUser as any).mockReturnValue({ id: 1, username: 'u' })
      const s = useAuthStore()
      expect(s.token).toBe('stored-token')
      expect(s.user).toEqual({ id: 1, username: 'u' })
      expect(s.error).toBe('')
    })

    it('isAuthenticated: !!token', () => {
      const s = useAuthStore()
      expect(s.isAuthenticated).toBe(false)
      s.token = 'abc'
      expect(s.isAuthenticated).toBe(true)
    })

    it('isAdmin: is_superuser=true', () => {
      const s = useAuthStore()
      s.user = { is_superuser: true } as any
      expect(s.isAdmin).toBe(true)
    })

    it('isAdmin: role in ADMIN_ROLES', () => {
      const s = useAuthStore()
      s.user = { role: 'admin' } as any
      expect(s.isAdmin).toBe(true)
    })

    it('isAdmin: 普通 user', () => {
      const s = useAuthStore()
      s.user = { role: 'viewer' } as any
      expect(s.isAdmin).toBe(false)
    })

    it('isAdmin: user null', () => {
      const s = useAuthStore()
      expect(s.isAdmin).toBe(false)
    })

    it('mustChangePassword: false when not set', () => {
      const s = useAuthStore()
      s.user = { id: 1 } as any
      expect(s.mustChangePassword).toBe(false)
    })

    it('mustChangePassword: true', () => {
      const s = useAuthStore()
      s.user = { must_change_password: true } as any
      expect(s.mustChangePassword).toBe(true)
    })
  })

  describe('login', () => {
    it('成功: persistAuth + return success', async () => {
      // 真实后端信封：refresh_token 位于顶层（data 内只有 access_token/user）
      ;(apiRequest as any).mockResolvedValue({
        code: 200,
        data: { access_token: 'A', user: { id: 1, username: 'u' } },
        refresh_token: 'R',
      })
      const s = useAuthStore()
      const r = await s.login('u', 'p')
      expect(r.status).toBe('success')
      expect(s.token).toBe('A')
      expect(s.user).toEqual({ id: 1, username: 'u' })
      expect(_setCachedToken).toHaveBeenCalledWith('A')
      expect(AuthStorage.setAuthData).toHaveBeenCalledWith({ token: 'A', user: { id: 1, username: 'u' }, refreshToken: 'R' })
    })

    it('code !== 200: error + return error status', async () => {
      ;(apiRequest as any).mockResolvedValue({ code: 401, message: 'bad creds' })
      const s = useAuthStore()
      const r = await s.login('u', 'p')
      expect(r.status).toBe('error')
      expect(s.error).toBe('bad creds')
    })

    it('no data: error + return error status', async () => {
      ;(apiRequest as any).mockResolvedValue({ code: 200, data: null })
      const s = useAuthStore()
      const r = await s.login('u', 'p')
      expect(r.status).toBe('error')
      expect(s.error).toBe('登录失败')
    })

    it('throw 401: err.message -> error', async () => {
      ;(apiRequest as any).mockRejectedValue({ response: { data: { message: 'Invalid creds' } } })
      const s = useAuthStore()
      const r = await s.login('u', 'p')
      expect(r.status).toBe('error')
      expect(s.error).toBe('Invalid creds')
    })

    it('throw 通用 Error: err.message', async () => {
      ;(apiRequest as any).mockRejectedValue(new Error('net down'))
      const s = useAuthStore()
      const r = await s.login('u', 'p')
      expect(r.status).toBe('error')
      expect(s.error).toBe('net down')
    })

    it('throw 其他: 默认 "登录失败"', async () => {
      ;(apiRequest as any).mockRejectedValue({})
      const s = useAuthStore()
      const r = await s.login('u', 'p')
      expect(r.status).toBe('error')
      expect(s.error).toBe('登录失败')
    })
  })

  describe('logout', () => {
    it('清空 token/user/error + clear storage', () => {
      const s = useAuthStore()
      s.token = 'X'
      s.user = { id: 1 } as any
      s.error = 'e'
      s.logout()
      expect(s.token).toBe('')
      expect(s.user).toBeNull()
      expect(s.error).toBe('')
      expect(_setCachedToken).toHaveBeenCalledWith(null)
      expect(AuthStorage.clear).toHaveBeenCalled()
    })
  })

  describe('fetchUser', () => {
    it('无 token: 跳过', async () => {
      const s = useAuthStore()
      await s.fetchUser()
      expect(getCurrentUser).not.toHaveBeenCalled()
    })

    it('已有 user: 跳过', async () => {
      const s = useAuthStore()
      s.token = 'T'
      s.user = { id: 1, username: 'u' } as any
      await s.fetchUser()
      expect(getCurrentUser).not.toHaveBeenCalled()
    })

    it('成功: 设置 user + AuthStorage.setUser', async () => {
      ;(getCurrentUser as any).mockResolvedValue({ code: 200, data: { id: 5, username: 'x' } })
      const s = useAuthStore()
      s.token = 'T'
      await s.fetchUser()
      expect(s.user).toEqual({ id: 5, username: 'x' })
      expect(AuthStorage.setUser).toHaveBeenCalledWith({ id: 5, username: 'x' })
    })

    it('code !== 200: 不修改 user', async () => {
      ;(getCurrentUser as any).mockResolvedValue({ code: 500 })
      const s = useAuthStore()
      s.token = 'T'
      await s.fetchUser()
      expect(s.user).toBeNull()
    })

    it('throw: 静默失败 (不抛错)', async () => {
      ;(getCurrentUser as any).mockRejectedValue(new Error('401'))
      const s = useAuthStore()
      s.token = 'T'
      await expect(s.fetchUser()).resolves.toBeUndefined()
    })
  })
})
