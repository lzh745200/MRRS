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
      // R16：凭据同源 —— 会话槽必须同时有 token 才被视为有效身份
      AuthStorage.setToken('t')
      AuthStorage.setUser(USER)
      expect(AuthStorage.getUser()).toEqual(USER)
    })

    it('仅有 user 而无 token → null（凭据不完整，fail-closed）', () => {
      AuthStorage.setUser(USER)
      expect(AuthStorage.getUser()).toBeNull()
    })

    it('无用户时返回 null', () => {
      expect(AuthStorage.getUser()).toBeNull()
    })

    it('非法 JSON 返回 null', () => {
      AuthStorage.setToken('t')
      sessionStorage.setItem('auth_user', 'not-json{')
      expect(AuthStorage.getUser()).toBeNull()
    })
  })

  describe('setRefreshToken / getRefreshToken', () => {
    it('写入并读取刷新令牌', () => {
      AuthStorage.setToken('t')
      AuthStorage.setUser(USER)
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
      AuthStorage.setToken('t')
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

    it('clearSession 仅清会话，保留记住登录持久凭据（锁屏场景）', () => {
      AuthStorage.persistForAutoLogin({
        token: 'persist-keep',
        user: USER,
        refreshToken: 'rt-keep',
      })
      AuthStorage.setToken('session-t')
      AuthStorage.setUser(USER)
      AuthStorage.setRefreshToken('session-rt')
      AuthStorage.clearSession()
      // 会话清空
      expect(AuthStorage.getToken()).toBe('persist-keep') // 回退到持久令牌
      expect(sessionStorage.getItem('auth_token')).toBeNull()
      expect(sessionStorage.getItem('auth_user')).toBeNull()
      expect(sessionStorage.getItem('refresh_token')).toBeNull()
      // 持久数据保留（记住登录不被锁屏破坏）
      expect(localStorage.getItem('auth_persist_token')).toBe('persist-keep')
      expect(localStorage.getItem('auth_persist_refresh')).toBe('rt-keep')
      expect(AuthStorage.hasPersistedAuth()).toBe(true)
      AuthStorage.clearPersisted()
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

  // 2026-09-30 深审：原先 getToken/getUser/getRefreshToken 是三条**彼此独立**的
  // 回退链，可以拼出"A 的 token + B 的档案/刷新令牌"这类串号组合。
  // 现改为整份凭据同源（_activeCredentials）。
  describe('凭据同源（拒绝跨来源拼接）', () => {
    it('会话 token 与持久 user 属不同凭据时 → 不返回该 user（isAuthenticated 为 false）', () => {
      AuthStorage.setToken('token-A')
      // 持久槽属于另一个用户/另一次登录（token 不同）
      AuthStorage.persistForAutoLogin({ token: 'token-B', user: USER, refreshToken: 'rt-B' })
      expect(AuthStorage.getToken()).toBe('token-A')
      expect(AuthStorage.getUser()).toBeNull()
      expect(AuthStorage.getRefreshToken()).toBeNull()
      expect(AuthStorage.isAuthenticated()).toBe(false)
    })

    it('会话 token 与持久 token 完全一致时 → 允许用持久档案补齐（续期只写 token 的正常路径）', () => {
      AuthStorage.persistForAutoLogin({ token: 'same-t', user: USER, refreshToken: 'rt-same' })
      AuthStorage.setToken('same-t')
      expect(AuthStorage.getUser()).toEqual(USER)
      expect(AuthStorage.getRefreshToken()).toBe('rt-same')
      expect(AuthStorage.isAuthenticated()).toBe(true)
    })

    it('会话自带完整档案 → 整份以会话为准，不借用持久槽任何字段', () => {
      AuthStorage.persistForAutoLogin({
        token: 'same-t2',
        user: { id: '2', username: 'other', role: 'user' },
        refreshToken: 'rt-2',
      })
      AuthStorage.setToken('same-t2')
      AuthStorage.setUser(USER)
      // 会话槽 token+user 齐备即为权威来源：档案与 refresh 都不跨界取用
      expect(AuthStorage.getUser()).toEqual(USER)
      expect(AuthStorage.getRefreshToken()).toBeNull()
    })

    it('会话 refresh 缺失且持久 token 不同 → 不借用别人的刷新令牌', () => {
      AuthStorage.setToken('token-x')
      AuthStorage.setUser(USER)
      AuthStorage.persistForAutoLogin({ token: 'token-y', user: USER, refreshToken: 'rt-y' })
      expect(AuthStorage.getRefreshToken()).toBeNull()
    })

    it('会话有 token+refresh 但档案缺失 → refresh 仍保留（同源，401 续期不可失效）', () => {
      // 回归：早期实现该分支把 refresh 一并置 null，导致"access 已轮换、档案未回填"
      // 的会话无法续期（登出吊销也拿不到 refresh_token）。
      AuthStorage.setToken('t-keep')
      AuthStorage.setRefreshToken('rt-keep')
      expect(AuthStorage.getUser()).toBeNull() // 无档案 → isAuthenticated 为 false
      expect(AuthStorage.isAuthenticated()).toBe(false)
      expect(AuthStorage.getRefreshToken()).toBe('rt-keep')
    })

    it('会话完全为空时整体回退持久凭据', () => {
      AuthStorage.persistForAutoLogin({ token: 'p-t', user: USER, refreshToken: 'p-rt' })
      expect(AuthStorage.getToken()).toBe('p-t')
      expect(AuthStorage.getUser()).toEqual(USER)
      expect(AuthStorage.getRefreshToken()).toBe('p-rt')
    })

    it('无会话/无持久时回退旧版 localStorage 键（含 user 与 refresh）', () => {
      localStorage.setItem('access_token', 'legacy-t')
      localStorage.setItem('user', JSON.stringify(USER))
      localStorage.setItem('refresh_token', 'legacy-rt')
      expect(AuthStorage.getToken()).toBe('legacy-t')
      expect(AuthStorage.getUser()).toEqual(USER)
      expect(AuthStorage.getRefreshToken()).toBe('legacy-rt')
    })

    it('setAuthData 无 refreshToken 时清除上一会话遗留的刷新令牌（防串号续期）', () => {
      AuthStorage.setRefreshToken('stale-rt')
      AuthStorage.setAuthData({ token: 'new-t', user: USER })
      expect(AuthStorage.getRefreshToken()).toBeNull()
    })

    it('持久 user 为非对象 JSON（如 "abc"）时视为无档案', () => {
      localStorage.setItem('auth_persist_token', 'p-t2')
      localStorage.setItem('auth_persist_user', JSON.stringify('abc'))
      expect(AuthStorage.getUser()).toBeNull()
    })
  })
})
