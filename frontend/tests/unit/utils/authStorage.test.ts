import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import AuthStorage, {
  AuthStorage as AuthStorageClass,
  getAuthToken,
  getAuthUser,
  isAuthenticated,
} from '@/utils/authStorage'

const USER = {
  id: '1',
  username: 'admin',
  role: 'admin',
}

describe('utils/authStorage', () => {
  beforeEach(() => {
    sessionStorage.clear()
    localStorage.clear()
    vi.restoreAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('setToken / getToken', () => {
    it('写入并读取 sessionStorage', () => {
      AuthStorage.setToken('token-1')
      expect(AuthStorage.getToken()).toBe('token-1')
      expect(sessionStorage.getItem('auth_token')).toBe('token-1')
    })

    it('无 token 时返回 null', () => {
      expect(AuthStorage.getToken()).toBeNull()
    })
  })

  describe('setUser / getUser', () => {
    it('写入并读取用户 JSON', () => {
      AuthStorage.setUser(USER)
      expect(AuthStorage.getUser()).toEqual(USER)
    })

    it('无用户时返回 null', () => {
      expect(AuthStorage.getUser()).toBeNull()
    })

    it('非法 JSON 返回 null', () => {
      sessionStorage.setItem('auth_user', 'not-json{')
      expect(AuthStorage.getUser()).toBeNull()
    })
  })

  describe('setRefreshToken / getRefreshToken', () => {
    it('写入并读取刷新令牌', () => {
      AuthStorage.setRefreshToken('rt-1')
      expect(AuthStorage.getRefreshToken()).toBe('rt-1')
    })

    it('无刷新令牌时返回 null', () => {
      expect(AuthStorage.getRefreshToken()).toBeNull()
    })
  })

  describe('setAuthData / getAuthData', () => {
    it('含 refreshToken 时完整保存', () => {
      AuthStorage.setAuthData({ token: 't', user: USER, refreshToken: 'rt' })
      expect(AuthStorage.getAuthData()).toEqual({ token: 't', user: USER, refreshToken: 'rt' })
    })

    it('无 refreshToken 时不写入刷新令牌', () => {
      AuthStorage.setAuthData({ token: 't', user: USER })
      expect(AuthStorage.getRefreshToken()).toBeNull()
      expect(AuthStorage.getAuthData()).toEqual({ token: 't', user: USER, refreshToken: undefined })
    })

    it('token 缺失时返回 null', () => {
      AuthStorage.setUser(USER)
      expect(AuthStorage.getAuthData()).toBeNull()
    })

    it('user 缺失时返回 null', () => {
      AuthStorage.setToken('t')
      expect(AuthStorage.getAuthData()).toBeNull()
    })
  })

  describe('clear', () => {
    it('清空 session 与旧版 localStorage 数据', () => {
      AuthStorage.setToken('t')
      AuthStorage.setUser(USER)
      AuthStorage.setRefreshToken('rt')
      localStorage.setItem('access_token', 'old')
      localStorage.setItem('user', JSON.stringify(USER))
      localStorage.setItem('token', 'old2')

      AuthStorage.clear()

      expect(AuthStorage.getToken()).toBeNull()
      expect(AuthStorage.getUser()).toBeNull()
      expect(AuthStorage.getRefreshToken()).toBeNull()
      expect(localStorage.getItem('access_token')).toBeNull()
      expect(localStorage.getItem('token')).toBeNull()
      expect(localStorage.getItem('user')).toBeNull()
      expect(localStorage.getItem('auth_token')).toBeNull()
      expect(localStorage.getItem('refresh_token')).toBeNull()
    })
  })

  describe('isAuthenticated', () => {
    it('token 与 user 齐全时为 true', () => {
      AuthStorage.setToken('t')
      AuthStorage.setUser(USER)
      expect(AuthStorage.isAuthenticated()).toBe(true)
    })

    it('仅 token 时为 false', () => {
      AuthStorage.setToken('t')
      expect(AuthStorage.isAuthenticated()).toBe(false)
    })

    it('仅 user 时为 false', () => {
      AuthStorage.setUser(USER)
      expect(AuthStorage.isAuthenticated()).toBe(false)
    })
  })

  describe('migrateFromLocalStorage', () => {
    it('已迁移时返回 false', () => {
      sessionStorage.setItem('auth_migrated', 'true')
      expect(AuthStorage.migrateFromLocalStorage()).toBe(false)
    })

    it('无数据时不迁移,返回 false', () => {
      expect(AuthStorage.migrateFromLocalStorage()).toBe(false)
    })

    it('token 已在 session 中时不再重复写入', () => {
      sessionStorage.setItem('auth_token', 'existing')
      const spy = vi.spyOn(AuthStorageClass, 'getToken').mockReturnValue('existing')
      expect(AuthStorage.migrateFromLocalStorage()).toBe(false)
      expect(sessionStorage.getItem('auth_token')).toBe('existing')
      spy.mockRestore()
    })

    it('完整迁移 token/user/refreshToken 并清理旧数据', () => {
      const tokenSpy = vi.spyOn(AuthStorageClass, 'getToken').mockReturnValue('legacy-token')
      const userSpy = vi.spyOn(AuthStorageClass, 'getUser').mockReturnValue(USER)
      const refreshSpy = vi.spyOn(AuthStorageClass, 'getRefreshToken').mockReturnValue('legacy-rt')

      localStorage.setItem('access_token', 'old')
      localStorage.setItem('user', JSON.stringify(USER))

      const migrated = AuthStorage.migrateFromLocalStorage()

      expect(migrated).toBe(true)
      expect(sessionStorage.getItem('auth_token')).toBe('legacy-token')
      expect(sessionStorage.getItem('auth_user')).toBe(JSON.stringify(USER))
      expect(sessionStorage.getItem('refresh_token')).toBe('legacy-rt')
      expect(sessionStorage.getItem('auth_migrated')).toBe('true')
      expect(localStorage.getItem('access_token')).toBeNull()
      expect(localStorage.getItem('user')).toBeNull()

      tokenSpy.mockRestore()
      userSpy.mockRestore()
      refreshSpy.mockRestore()
    })

    it('仅 token 可迁移时部分迁移', () => {
      const tokenSpy = vi.spyOn(AuthStorageClass, 'getToken').mockReturnValue('only-token')
      const userSpy = vi.spyOn(AuthStorageClass, 'getUser').mockReturnValue(null)
      const refreshSpy = vi.spyOn(AuthStorageClass, 'getRefreshToken').mockReturnValue(null)

      expect(AuthStorage.migrateFromLocalStorage()).toBe(true)
      expect(sessionStorage.getItem('auth_token')).toBe('only-token')

      tokenSpy.mockRestore()
      userSpy.mockRestore()
      refreshSpy.mockRestore()
    })
  })

  describe('便捷函数', () => {
    it('getAuthToken 委托 AuthStorage.getToken', () => {
      AuthStorage.setToken('t')
      expect(getAuthToken()).toBe('t')
    })

    it('getAuthUser 委托 AuthStorage.getUser', () => {
      AuthStorage.setUser(USER)
      expect(getAuthUser()).toEqual(USER)
    })

    it('isAuthenticated 委托 AuthStorage.isAuthenticated', () => {
      AuthStorage.setToken('t')
      AuthStorage.setUser(USER)
      expect(isAuthenticated()).toBe(true)
    })

    it('默认导出为 AuthStorage 类', () => {
      expect(AuthStorage).toBe(AuthStorageClass)
      expect(typeof AuthStorage.setToken).toBe('function')
    })
  })

  describe('记住登录（自动登录持久化）', () => {
    it('persistForAutoLogin 写入 localStorage（token+user+refresh token，供免登录静默续期）', () => {
      AuthStorage.persistForAutoLogin({ token: 'persist-t', user: USER, refreshToken: 'persist-r' })
      expect(localStorage.getItem('auth_persist_token')).toBe('persist-t')
      expect(localStorage.getItem('auth_persist_user')).toContain('admin')
      // 2026-08-14：持久化 refresh token（30 天轮换续期），修复"记住登录"隔天失效问题
      expect(localStorage.getItem('auth_persist_refresh')).toBe('persist-r')
    })

    it('persistForAutoLogin 无 refreshToken 时不写入', () => {
      AuthStorage.persistForAutoLogin({ token: 't2', user: USER })
      expect(localStorage.getItem('auth_persist_refresh')).toBeNull()
    })

    it('getRefreshToken 回退持久刷新令牌', () => {
      AuthStorage.persistForAutoLogin({ token: 't3', user: USER, refreshToken: 'persist-rt' })
      expect(AuthStorage.getRefreshToken()).toBe('persist-rt')
    })

    it('hasPersistedAuth 判断', () => {
      expect(AuthStorage.hasPersistedAuth()).toBe(false)
      AuthStorage.persistForAutoLogin({ token: 't4', user: USER })
      expect(AuthStorage.hasPersistedAuth()).toBe(true)
    })

    it('getToken 回退持久令牌', () => {
      AuthStorage.persistForAutoLogin({ token: 'persist-fallback', user: USER })
      expect(AuthStorage.getToken()).toBe('persist-fallback')
    })

    it('getUser 回退持久用户（含损坏 JSON 兜底）', () => {
      localStorage.setItem('auth_persist_user', '{bad json')
      expect(AuthStorage.getUser()).toBeNull()
      AuthStorage.persistForAutoLogin({ token: 't5', user: USER })
      expect(AuthStorage.getUser()).toMatchObject({ username: 'admin' })
    })

    it('clearPersisted 清除持久数据', () => {
      AuthStorage.persistForAutoLogin({ token: 't6', user: USER, refreshToken: 'rt' })
      AuthStorage.clearPersisted()
      expect(AuthStorage.hasPersistedAuth()).toBe(false)
      expect(localStorage.getItem('auth_persist_refresh')).toBeNull()
    })

    it('clear 同时清除记住登录持久数据（退出登录彻底失效）', () => {
      AuthStorage.persistForAutoLogin({ token: 't7', user: USER, refreshToken: 'rt' })
      AuthStorage.setToken('session-t')
      AuthStorage.clear()
      expect(AuthStorage.hasPersistedAuth()).toBe(false)
      expect(AuthStorage.getToken()).toBeNull()
      expect(localStorage.getItem('auth_persist_token')).toBeNull()
    })
  })
})
