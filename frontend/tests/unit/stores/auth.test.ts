import { describe, it, expect, beforeEach, vi } from 'vitest'

const mockApiRequest = vi.fn()
const mockSetCachedToken = vi.fn()
const mockPrefetchCsrf = vi.fn(() => Promise.resolve())
const mockGetCurrentUser = vi.fn()
const mockVerifyLoginTwoFactor = vi.fn()
const mockAuthStorageGetToken = vi.fn()
const mockAuthStorageGetUser = vi.fn()
const mockAuthStorageSetAuthData = vi.fn()
const mockAuthStorageSetUser = vi.fn()
const mockAuthStorageClear = vi.fn()
const mockFetchMenus = vi.fn()
const mockUseMenuStore = vi.fn()

vi.mock('@/api/request', () => ({
  apiRequest: (...args: any[]) => mockApiRequest(...args),
  _setCachedToken: (...args: any[]) => mockSetCachedToken(...args),
  prefetchCsrfToken: () => mockPrefetchCsrf(),
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

vi.mock('@/api/queries/user', () => ({
  getCurrentUser: (...args: any[]) => mockGetCurrentUser(...args),
}))

vi.mock('@/api/twoFactor', () => ({
  verifyLoginTwoFactor: (...args: any[]) => mockVerifyLoginTwoFactor(...args),
}))

vi.mock('@/utils/authStorage', () => ({
  AuthStorage: {
    getToken: () => mockAuthStorageGetToken(),
    getUser: () => mockAuthStorageGetUser(),
    setAuthData: (...args: any[]) => mockAuthStorageSetAuthData(...args),
    setUser: (...args: any[]) => mockAuthStorageSetUser(...args),
    clear: (...args: any[]) => mockAuthStorageClear(...args),
  },
}))

vi.mock('@/utils/roleAccess', () => ({
  ADMIN_ROLES: ['admin', 'superuser'],
}))

vi.mock('@/stores/menu', () => ({
  useMenuStore: () => mockUseMenuStore(),
}))

import { setActivePinia, createPinia } from 'pinia'
import { useAuthStore } from '@/stores/auth'

describe('useAuthStore', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockAuthStorageGetToken.mockReturnValue('')
    mockAuthStorageGetUser.mockReturnValue(null)
    mockPrefetchCsrf.mockResolvedValue(undefined)
    mockFetchMenus.mockResolvedValue(undefined)
    mockUseMenuStore.mockReturnValue({ fetchMenus: mockFetchMenus })
    setActivePinia(createPinia())
  })

  it('isAuthenticated=false 当 token 为空', () => {
    const store = useAuthStore()
    expect(store.isAuthenticated).toBe(false)
  })

  it('isAuthenticated=true 当 token 非空', () => {
    mockAuthStorageGetToken.mockReturnValue('abc123')
    setActivePinia(createPinia())
    const store = useAuthStore()
    expect(store.isAuthenticated).toBe(true)
  })

  it('isAdmin=true 当 user.is_superuser=true', () => {
    mockAuthStorageGetUser.mockReturnValue({ id: 1, is_superuser: true })
    setActivePinia(createPinia())
    const store = useAuthStore()
    expect(store.isAdmin).toBe(true)
  })

  it('isAdmin=true 当 user.role 在 ADMIN_ROLES', () => {
    mockAuthStorageGetUser.mockReturnValue({ id: 1, role: 'admin' })
    setActivePinia(createPinia())
    const store = useAuthStore()
    expect(store.isAdmin).toBe(true)
  })

  it('isAdmin=false 当 user.role 不在 ADMIN_ROLES 且非 superuser', () => {
    mockAuthStorageGetUser.mockReturnValue({ id: 1, role: 'user' })
    setActivePinia(createPinia())
    const store = useAuthStore()
    expect(store.isAdmin).toBe(false)
  })

  it('isAdmin=false 当 user 缺少 role 字段', () => {
    mockAuthStorageGetUser.mockReturnValue({ id: 1 })
    setActivePinia(createPinia())
    const store = useAuthStore()
    expect(store.isAdmin).toBe(false)
  })

  it('isAdmin=false 当无 user 信息', () => {
    const store = useAuthStore()
    expect(store.isAdmin).toBe(false)
    expect(store.canViewDeleted).toBe(false)
  })

  it('canViewDeleted=true 当 is_superuser', () => {
    mockAuthStorageGetUser.mockReturnValue({ id: 1, is_superuser: true })
    setActivePinia(createPinia())
    const store = useAuthStore()
    expect(store.canViewDeleted).toBe(true)
  })

  it('canViewDeleted=true 当 role 在 ADMIN_ROLES', () => {
    mockAuthStorageGetUser.mockReturnValue({ id: 1, role: 'admin' })
    setActivePinia(createPinia())
    const store = useAuthStore()
    expect(store.canViewDeleted).toBe(true)
  })

  it('canViewDeleted=false 其他角色', () => {
    mockAuthStorageGetUser.mockReturnValue({ id: 1, role: 'manager' })
    setActivePinia(createPinia())
    const store = useAuthStore()
    expect(store.canViewDeleted).toBe(false)
  })

  it('canViewDeleted=false 当 user 缺少 role 字段', () => {
    mockAuthStorageGetUser.mockReturnValue({ id: 1 })
    setActivePinia(createPinia())
    const store = useAuthStore()
    expect(store.canViewDeleted).toBe(false)
  })

  it('mustChangePassword 默认为 false', () => {
    const store = useAuthStore()
    expect(store.mustChangePassword).toBe(false)
  })

  it('mustChangePassword=true 当 user.must_change_password=true', () => {
    mockAuthStorageGetUser.mockReturnValue({ id: 1, must_change_password: true })
    setActivePinia(createPinia())
    const store = useAuthStore()
    expect(store.mustChangePassword).toBe(true)
  })

  describe('modulePermissions', () => {
    it('普通用户按权限字符串解析 view/edit 映射', () => {
      mockAuthStorageGetUser.mockReturnValue({
        id: 1,
        role: 'user',
        permissions: [
          'village:read',
          'village:write',
          'schools:delete',
          'projects:manage_roles',
          'bad',
        ],
      })
      setActivePinia(createPinia())
      const store = useAuthStore()
      expect(store.modulePermissions.village).toEqual({ view: true, edit: true })
      expect(store.modulePermissions.schools).toEqual({ view: false, edit: true })
      expect(store.modulePermissions.projects).toEqual({ view: false, edit: true })
      expect(store.modulePermissions.unknown).toBeUndefined()
    })

    it('无权限时返回空映射', () => {
      mockAuthStorageGetUser.mockReturnValue({ id: 1, role: 'user', permissions: [] })
      setActivePinia(createPinia())
      const store = useAuthStore()
      expect(store.modulePermissions.anything).toBeUndefined()
    })

    it('is_superuser 返回全权限 Proxy', () => {
      mockAuthStorageGetUser.mockReturnValue({ id: 1, is_superuser: true })
      setActivePinia(createPinia())
      const store = useAuthStore()
      const p = store.modulePermissions as any
      expect(p.anyModule.view).toBe(true)
      expect(p.anyModule.edit).toBe(true)
      expect(p.then).toBeUndefined()
      expect(p.toJSON).toBeUndefined()
      expect('foo' in p).toBe(true)
    })

    it('role=super_admin 返回全权限 Proxy', () => {
      mockAuthStorageGetUser.mockReturnValue({ id: 1, role: 'super_admin' })
      setActivePinia(createPinia())
      const store = useAuthStore()
      const p = store.modulePermissions as any
      expect(p.x.view).toBe(true)
      expect(p.x.edit).toBe(true)
    })
  })

  describe('login', () => {
    const successPayload = {
      code: 200,
      data: {
        access_token: 'tok123',
        refresh_token: 'ref456',
        token_type: 'bearer',
        user: { id: 1, username: 'alice' },
      },
    }

    it('登录成功时返回 success 并持久化 token', async () => {
      mockApiRequest.mockResolvedValueOnce(successPayload)
      const store = useAuthStore()
      const result = await store.login('alice', 'pwd')
      expect(result.status).toBe('success')
      expect(store.token).toBe('tok123')
      expect(store.user?.username).toBe('alice')
      expect(mockSetCachedToken).toHaveBeenCalledWith('tok123')
      expect(mockAuthStorageSetAuthData).toHaveBeenCalled()
      expect(mockUseMenuStore).toHaveBeenCalled()
    })

    it('登录需要 2FA 时返回 two_factor_required + tempToken', async () => {
      mockApiRequest.mockResolvedValueOnce({
        code: 200,
        two_factor_required: true,
        temp_token: 'tmp-1',
      })
      const store = useAuthStore()
      const result = await store.login('alice', 'pwd')
      expect(result).toEqual({ status: 'two_factor_required', tempToken: 'tmp-1' })
    })

    it('two_factor_required=true 但无 temp_token 时走正常登录', async () => {
      mockApiRequest.mockResolvedValueOnce({
        code: 200,
        two_factor_required: true,
        ...successPayload,
      })
      const store = useAuthStore()
      const result = await store.login('alice', 'pwd')
      expect(result.status).toBe('success')
    })

    it('code=200 但无 data 时返回 error', async () => {
      mockApiRequest.mockResolvedValueOnce({ code: 200 })
      const store = useAuthStore()
      const result = await store.login('alice', 'pwd')
      expect(result).toEqual({ status: 'error', message: '登录失败' })
      expect(store.error).toBe('登录失败')
    })

    it('登录失败（非 200 code）时返回 error 并设置 error', async () => {
      mockApiRequest.mockResolvedValueOnce({
        code: 401,
        message: 'invalid credentials',
      })
      const store = useAuthStore()
      const result = await store.login('alice', 'wrong')
      expect(result.status).toBe('error')
      expect(store.error).toBe('invalid credentials')
    })

    it('登录异常时捕获 err.message', async () => {
      mockApiRequest.mockRejectedValueOnce(new Error('timeout'))
      const store = useAuthStore()
      const result = await store.login('alice', 'pwd')
      expect(result.status).toBe('error')
      expect(store.error).toBe('timeout')
    })

    it('登录异常优先取 response.data.message', async () => {
      mockApiRequest.mockRejectedValueOnce({ response: { data: { message: 'bad creds' } } })
      const store = useAuthStore()
      const result = await store.login('alice', 'pwd')
      expect(result.status).toBe('error')
      expect(store.error).toBe('bad creds')
    })

    it('登录异常无任何信息时使用默认错误信息', async () => {
      mockApiRequest.mockRejectedValueOnce({})
      const store = useAuthStore()
      const result = await store.login('alice', 'pwd')
      expect(result.status).toBe('error')
      expect(store.error).toBe('登录失败')
    })

    it('CSRF 预取失败不阻断登录', async () => {
      mockPrefetchCsrf.mockRejectedValueOnce(new Error('csrf'))
      mockApiRequest.mockResolvedValueOnce(successPayload)
      const store = useAuthStore()
      const result = await store.login('alice', 'pwd')
      expect(result.status).toBe('success')
    })

    it('登录后菜单加载失败不阻断登录', async () => {
      mockFetchMenus.mockRejectedValueOnce(new Error('menu'))
      mockApiRequest.mockResolvedValueOnce(successPayload)
      const store = useAuthStore()
      const result = await store.login('alice', 'pwd')
      expect(result.status).toBe('success')
    })

    it('useMenuStore 抛出异常不阻断登录', async () => {
      mockUseMenuStore.mockImplementationOnce(() => {
        throw new Error('store boom')
      })
      mockApiRequest.mockResolvedValueOnce(successPayload)
      const store = useAuthStore()
      const result = await store.login('alice', 'pwd')
      expect(result.status).toBe('success')
    })
  })

  describe('verifyTwoFactorLogin', () => {
    it('验证成功时完成登录并返回 true', async () => {
      mockVerifyLoginTwoFactor.mockResolvedValueOnce({
        code: 200,
        data: { access_token: 't2', user: { id: 2, username: 'bob' } },
        refresh_token: 'r2',
      })
      const store = useAuthStore()
      expect(await store.verifyTwoFactorLogin('tmp', '123456')).toBe(true)
      expect(store.token).toBe('t2')
      expect(mockAuthStorageSetAuthData).toHaveBeenCalled()
      expect(mockUseMenuStore).toHaveBeenCalled()
    })

    it('验证失败（非 200 code）返回 false 并设置 error', async () => {
      mockVerifyLoginTwoFactor.mockResolvedValueOnce({ code: 400, message: '验证码错误' })
      const store = useAuthStore()
      expect(await store.verifyTwoFactorLogin('tmp', '000000')).toBe(false)
      expect(store.error).toBe('验证码错误')
    })

    it('code=200 但无 data 返回 false 且使用默认错误信息', async () => {
      mockVerifyLoginTwoFactor.mockResolvedValueOnce({ code: 200, data: null })
      const store = useAuthStore()
      expect(await store.verifyTwoFactorLogin('tmp', '000000')).toBe(false)
      expect(store.error).toBe('2FA验证失败')
    })

    it('异常时优先取 response.data.detail', async () => {
      mockVerifyLoginTwoFactor.mockRejectedValueOnce({ response: { data: { detail: 'expired' } } })
      const store = useAuthStore()
      expect(await store.verifyTwoFactorLogin('tmp', '000000')).toBe(false)
      expect(store.error).toBe('expired')
    })

    it('异常时取 response.data.message', async () => {
      mockVerifyLoginTwoFactor.mockRejectedValueOnce({ response: { data: { message: 'bad code' } } })
      const store = useAuthStore()
      expect(await store.verifyTwoFactorLogin('tmp', '000000')).toBe(false)
      expect(store.error).toBe('bad code')
    })

    it('异常时取 err.message', async () => {
      mockVerifyLoginTwoFactor.mockRejectedValueOnce(new Error('network'))
      const store = useAuthStore()
      expect(await store.verifyTwoFactorLogin('tmp', '000000')).toBe(false)
      expect(store.error).toBe('network')
    })

    it('异常无任何信息时使用默认错误信息', async () => {
      mockVerifyLoginTwoFactor.mockRejectedValueOnce({})
      const store = useAuthStore()
      expect(await store.verifyTwoFactorLogin('tmp', '000000')).toBe(false)
      expect(store.error).toBe('2FA验证失败')
    })
  })

  it('logout 清空 token, user, error', async () => {
    mockAuthStorageGetToken.mockReturnValue('tok')
    mockAuthStorageGetUser.mockReturnValue({ id: 1 })
    setActivePinia(createPinia())
    const store = useAuthStore()
    await store.logout()
    expect(store.token).toBe('')
    expect(store.user).toBeNull()
    expect(store.error).toBe('')
    expect(mockSetCachedToken).toHaveBeenCalledWith(null)
    expect(mockAuthStorageClear).toHaveBeenCalled()
  })

  it('fetchUser 无 token 时立即返回', async () => {
    const store = useAuthStore()
    await store.fetchUser()
    expect(mockGetCurrentUser).not.toHaveBeenCalled()
  })

  it('fetchUser 有 user 时立即返回 (无需重新拉取)', async () => {
    mockAuthStorageGetToken.mockReturnValue('tok')
    mockAuthStorageGetUser.mockReturnValue({ id: 1, username: 'a' })
    setActivePinia(createPinia())
    const store = useAuthStore()
    await store.fetchUser()
    expect(mockGetCurrentUser).not.toHaveBeenCalled()
  })

  it('fetchUser 成功时更新 user', async () => {
    mockAuthStorageGetToken.mockReturnValue('tok')
    setActivePinia(createPinia())
    mockGetCurrentUser.mockResolvedValueOnce({
      code: 200,
      data: { id: 1, username: 'fetched' },
    })
    const store = useAuthStore()
    await store.fetchUser()
    expect(store.user?.username).toBe('fetched')
    expect(mockAuthStorageSetUser).toHaveBeenCalled()
  })

  it('fetchUser 异常时静默吞掉 (由 401 拦截器处理)', async () => {
    mockAuthStorageGetToken.mockReturnValue('tok')
    setActivePinia(createPinia())
    mockGetCurrentUser.mockRejectedValueOnce(new Error('401'))
    const store = useAuthStore()
    await expect(store.fetchUser()).resolves.toBeUndefined()
  })

  it('getAuthData 返回当前 token + user', () => {
    mockAuthStorageGetToken.mockReturnValue('tok-gd')
    mockAuthStorageGetUser.mockReturnValue({ id: 1, username: 'gd' })
    setActivePinia(createPinia())
    const store = useAuthStore()
    expect(store.getAuthData()).toEqual({
      token: 'tok-gd',
      user: { id: 1, username: 'gd' },
      refreshToken: undefined,
    })
  })

  it('getAuthData 无认证数据时返回 token 空字符串 + user null', () => {
    const store = useAuthStore()
    expect(store.getAuthData()).toEqual({ token: '', user: null, refreshToken: undefined })
  })
})
