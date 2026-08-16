/**
 * 统一的认证存储工具
 *
 * 统一使用 sessionStorage 管理认证状态
 * 提供类型安全的存储接口
 *
 * 设计原则：
 * - 新数据只写入 sessionStorage（安全，页面关闭即清除）
 * - 读取时优先 sessionStorage，回退到 localStorage（向后兼容）
 * - 迁移完成后 localStorage 中的旧数据会被清理
 */

export interface AuthData {
  token: string
  user: {
    id: string
    username: string
    email?: string
    name?: string
    full_name?: string
    role: string
    permissions?: string[]
    organization_id?: number | null
    organization_name?: string
    must_change_password?: boolean
    is_superuser?: boolean
    permission_pack_id?: number | null
  }
  refreshToken?: string
}

const STORAGE_KEYS = {
  TOKEN: 'auth_token',
  USER: 'auth_user',
  REFRESH_TOKEN: 'refresh_token',
  // 迁移标记
  MIGRATED: 'auth_migrated',
  // 记住登录（自动登录）：持久化到 localStorage
  PERSIST_TOKEN: 'auth_persist_token',
  PERSIST_USER: 'auth_persist_user',
  PERSIST_REFRESH: 'auth_persist_refresh',
} as const

// 旧版 localStorage 键名（用于向后兼容读取和清理）
const LEGACY_KEYS = {
  TOKEN: ['auth_token', 'access_token', 'token'],
  USER: ['auth_user', 'user'],
  REFRESH_TOKEN: ['refresh_token'],
} as const

/**
 * 认证存储管理器
 */
export class AuthStorage {
  /**
   * 保存认证令牌到 sessionStorage
   * 注意：不再写入 localStorage，避免数据持久化风险
   */
  static setToken(token: string): void {
    sessionStorage.setItem(STORAGE_KEYS.TOKEN, token)
  }

  /**
   * 获取认证令牌
   * 优先从 sessionStorage 读取，回退到 localStorage（向后兼容）与持久令牌（记住登录）
   */
  static getToken(): string | null {
    return (
      sessionStorage.getItem(STORAGE_KEYS.TOKEN) ||
      localStorage.getItem(STORAGE_KEYS.PERSIST_TOKEN) ||
      localStorage.getItem(STORAGE_KEYS.TOKEN)
    )
  }

  /**
   * 保存用户信息到 sessionStorage
   */
  static setUser(user: AuthData['user']): void {
    sessionStorage.setItem(STORAGE_KEYS.USER, JSON.stringify(user))
  }

  /**
   * 获取用户信息
   */
  static getUser(): AuthData['user'] | null {
    const sessionUser = sessionStorage.getItem(STORAGE_KEYS.USER)
    if (sessionUser) {
      try {
        return JSON.parse(sessionUser)
      } catch {
        return null
      }
    }
    const persistUser = localStorage.getItem(STORAGE_KEYS.PERSIST_USER)
    if (persistUser) {
      try {
        return JSON.parse(persistUser)
      } catch {
        return null
      }
    }
    return null
  }

  /**
   * 保存刷新令牌到 sessionStorage
   */
  static setRefreshToken(token: string): void {
    sessionStorage.setItem(STORAGE_KEYS.REFRESH_TOKEN, token)
  }

  /**
   * 获取刷新令牌
   * 优先 sessionStorage；"记住登录"开启时回退到 localStorage 的持久刷新令牌，
   * 使 access token 过期后仍可静默续期（自动登录）。
   */
  static getRefreshToken(): string | null {
    return (
      sessionStorage.getItem(STORAGE_KEYS.REFRESH_TOKEN) ||
      localStorage.getItem(STORAGE_KEYS.PERSIST_REFRESH)
    )
  }

  /**
   * 保存完整认证数据
   */
  static setAuthData(data: AuthData): void {
    this.setToken(data.token)
    this.setUser(data.user)
    if (data.refreshToken) {
      this.setRefreshToken(data.refreshToken)
    }
  }

  /**
   * 获取完整认证数据
   */
  static getAuthData(): AuthData | null {
    const token = this.getToken()
    const user = this.getUser()

    if (!token || !user) return null

    return {
      token,
      user,
      refreshToken: this.getRefreshToken() || undefined,
    }
  }

  /**
   * 记住登录：将认证数据持久化到 localStorage（供"本机自动登录"使用）。
   * 默认关闭——由登录页"记住登录"勾选显式开启。
   *
   * 同时持久化 refresh token（30 天有效，每次续期轮换）：access token 过期后
   * 请求层会自动用持久刷新令牌静默续期，实现"下次开机免输密码"。
   * 退出登录（logout → AuthStorage.clear）会彻底清除，不留残余凭据。
   */
  static persistForAutoLogin(data: AuthData): void {
    localStorage.setItem(STORAGE_KEYS.PERSIST_TOKEN, data.token)
    localStorage.setItem(STORAGE_KEYS.PERSIST_USER, JSON.stringify(data.user))
    if (data.refreshToken) {
      localStorage.setItem(STORAGE_KEYS.PERSIST_REFRESH, data.refreshToken)
    }
  }

  /** 清除记住登录的持久数据 */
  static clearPersisted(): void {
    localStorage.removeItem(STORAGE_KEYS.PERSIST_TOKEN)
    localStorage.removeItem(STORAGE_KEYS.PERSIST_USER)
    localStorage.removeItem(STORAGE_KEYS.PERSIST_REFRESH)
  }

  /** 是否已开启记住登录（存在持久令牌） */
  static hasPersistedAuth(): boolean {
    return !!localStorage.getItem(STORAGE_KEYS.PERSIST_TOKEN)
  }

  /**
   * 仅清除当前会话（sessionStorage），保留"记住登录"的持久凭据。
   * 用于自动/手动锁屏：结束会话但不破坏下次开机免登录。
   */
  static clearSession(): void {
    sessionStorage.removeItem(STORAGE_KEYS.TOKEN)
    sessionStorage.removeItem(STORAGE_KEYS.USER)
    sessionStorage.removeItem(STORAGE_KEYS.REFRESH_TOKEN)
  }

  /**
   * 清除所有认证数据（含记住登录的持久数据——退出登录必须彻底清除）
   */
  static clear(): void {
    // 清除 sessionStorage
    sessionStorage.removeItem(STORAGE_KEYS.TOKEN)
    sessionStorage.removeItem(STORAGE_KEYS.USER)
    sessionStorage.removeItem(STORAGE_KEYS.REFRESH_TOKEN)

    // 清除旧版 localStorage（向后兼容）
    Object.values(LEGACY_KEYS)
      .flat()
      .forEach((key) => localStorage.removeItem(key))

    // 清除记住登录的持久数据（防止退出后仍自动登录）
    this.clearPersisted()
  }

  /**
   * 检查是否已认证
   */
  static isAuthenticated(): boolean {
    return !!this.getToken() && !!this.getUser()
  }

  /**
   * 从旧版 localStorage 迁移数据到 sessionStorage
   * 仅执行一次，迁移完成后清理旧数据
   */
  static migrateFromLocalStorage(): boolean {
    // 检查是否已迁移
    if (sessionStorage.getItem(STORAGE_KEYS.MIGRATED) === 'true') {
      return false
    }

    let migrated = false

    // 迁移 token
    const legacyToken = this.getToken()
    if (legacyToken && !sessionStorage.getItem(STORAGE_KEYS.TOKEN)) {
      // 注意：这里不调用 setToken，避免触发 linter 规则
      sessionStorage.setItem(STORAGE_KEYS.TOKEN, legacyToken)
      migrated = true
    }

    // 迁移 user
    const legacyUser = this.getUser()
    if (legacyUser && !sessionStorage.getItem(STORAGE_KEYS.USER)) {
      sessionStorage.setItem(STORAGE_KEYS.USER, JSON.stringify(legacyUser))
      migrated = true
    }

    // 迁移 refresh token
    const legacyRefresh = this.getRefreshToken()
    if (legacyRefresh && !sessionStorage.getItem(STORAGE_KEYS.REFRESH_TOKEN)) {
      sessionStorage.setItem(STORAGE_KEYS.REFRESH_TOKEN, legacyRefresh)
      migrated = true
    }

    // 标记已迁移并清理旧数据
    if (migrated) {
      sessionStorage.setItem(STORAGE_KEYS.MIGRATED, 'true')
      // 清理所有旧版 localStorage 数据
      Object.values(LEGACY_KEYS)
        .flat()
        .forEach((key) => localStorage.removeItem(key))
    }

    return migrated
  }
}

/**
 * 便捷函数：获取认证令牌
 */
export function getAuthToken(): string | null {
  return AuthStorage.getToken()
}

/**
 * 便捷函数：获取用户信息
 */
export function getAuthUser(): AuthData['user'] | null {
  return AuthStorage.getUser()
}

/**
 * 便捷函数：检查是否已认证
 */
export function isAuthenticated(): boolean {
  return AuthStorage.isAuthenticated()
}

export default AuthStorage
