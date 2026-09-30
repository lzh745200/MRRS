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

/** 单一来源的整份凭据（token / user / refresh 必须同源，绝不跨来源拼接） */
interface CredentialSlot {
  token: string | null
  user: AuthData['user'] | null
  refresh: string | null
}

/** 凭据来源：当前会话 / 记住登录持久化 / 旧版 localStorage 键 */
type CredentialSource = 'session' | 'persist' | 'legacy'

/**
 * 认证存储管理器
 */
export class AuthStorage {
  /** 解析用户 JSON（损坏/非对象一律 null，避免把字符串当用户档案用） */
  private static _parseUser(raw: string | null): AuthData['user'] | null {
    if (!raw) return null
    try {
      const parsed = JSON.parse(raw)
      return parsed && typeof parsed === 'object' ? (parsed as AuthData['user']) : null
    } catch {
      return null
    }
  }

  /** 读取旧版 localStorage 键（按顺序取第一个非空值） */
  private static _readLegacy(keys: readonly string[]): string | null {
    for (const key of keys) {
      const value = localStorage.getItem(key)
      if (value) return value
    }
    return null
  }

  /** 读取某个来源上的整份凭据 */
  private static _readSlot(source: CredentialSource): CredentialSlot {
    if (source === 'session') {
      return {
        token: sessionStorage.getItem(STORAGE_KEYS.TOKEN),
        user: AuthStorage._parseUser(sessionStorage.getItem(STORAGE_KEYS.USER)),
        refresh: sessionStorage.getItem(STORAGE_KEYS.REFRESH_TOKEN),
      }
    }
    if (source === 'persist') {
      return {
        token: localStorage.getItem(STORAGE_KEYS.PERSIST_TOKEN),
        user: AuthStorage._parseUser(localStorage.getItem(STORAGE_KEYS.PERSIST_USER)),
        refresh: localStorage.getItem(STORAGE_KEYS.PERSIST_REFRESH),
      }
    }
    return {
      token: AuthStorage._readLegacy(LEGACY_KEYS.TOKEN),
      user: AuthStorage._parseUser(AuthStorage._readLegacy(LEGACY_KEYS.USER)),
      refresh: AuthStorage._readLegacy(LEGACY_KEYS.REFRESH_TOKEN),
    }
  }

  /**
   * 判定当前生效的**整份凭据**（token/user/refresh 同源）。
   *
   * 历史实现是三条彼此独立的回退链（getToken: session→persist→legacy；
   * getUser: session→persist；getRefreshToken: session→persist），可以拼出
   * "A 的 token + B 的档案/刷新令牌"这种串号组合。这里改为整体取值：
   *
   * 1) 会话槽有 token → 会话槽为权威来源；若会话槽缺 user（例如 401 续期只写了
   *    新 access token），仅当持久槽持有**完全相同的 token** 时才用持久 user 补齐
   *    （同一份凭据的正常刷新路径），否则视为不一致 → 不提供身份（fail-closed，
   *    宁愿要求重新登录，也不能把两个人的凭据拼在一起）。
   * 2) 会话槽无 token → 持久槽（记住登录）→ 旧版键。
   */
  private static _activeCredentials(): CredentialSlot {
    const session = AuthStorage._readSlot('session')
    if (session.token) {
      if (session.user) return session
      const persist = AuthStorage._readSlot('persist')
      if (persist.user && persist.token === session.token) {
        return {
          token: session.token,
          user: persist.user,
          refresh: session.refresh || persist.refresh,
        }
      }
      // 会话有 token 但拿不到同源档案 → 不提供身份（isAuthenticated() 因此为 false）。
      // refresh 仍取自**同一会话槽**：它与 token 同源（同一次登录写入），
      // 若一并丢弃会让"刷新后 access 已轮换、档案尚未回填"的 401 续期路径失效。
      return { token: session.token, user: null, refresh: session.refresh }
    }
    const persist = AuthStorage._readSlot('persist')
    if (persist.token) return persist
    return AuthStorage._readSlot('legacy')
  }
  /**
   * 保存认证令牌到 sessionStorage
   * 注意：不再写入 localStorage，避免数据持久化风险
   */
  static setToken(token: string): void {
    sessionStorage.setItem(STORAGE_KEYS.TOKEN, token)
  }

  /**
   * 获取认证令牌。
   *
   * 优先级与历史行为一致（session → 持久令牌 → 旧版键），但改为从
   * _activeCredentials() 这一**唯一天然来源**取值，保证 token/user/refresh
   * 三者同源（详见 _activeCredentials 注释）。
   */
  static getToken(): string | null {
    return AuthStorage._activeCredentials().token
  }

  /**
   * 保存用户信息到 sessionStorage
   */
  static setUser(user: AuthData['user']): void {
    sessionStorage.setItem(STORAGE_KEYS.USER, JSON.stringify(user))
  }

  /**
   * 获取用户信息（与 getToken 同源，绝不返回另一个来源的档案）
   */
  static getUser(): AuthData['user'] | null {
    return AuthStorage._activeCredentials().user
  }

  /**
   * 保存刷新令牌到 sessionStorage
   */
  static setRefreshToken(token: string): void {
    sessionStorage.setItem(STORAGE_KEYS.REFRESH_TOKEN, token)
  }

  /**
   * 获取刷新令牌。
   *
   * 与 getToken/getUser 同源：只在"凭据完全一致"时才回退到持久刷新令牌，
   * 避免用**上一个用户**的刷新令牌续期出别人的 access token。
   */
  static getRefreshToken(): string | null {
    return AuthStorage._activeCredentials().refresh
  }

  /**
   * 保存完整认证数据
   */
  static setAuthData(data: AuthData): void {
    this.setToken(data.token)
    this.setUser(data.user)
    if (data.refreshToken) {
      this.setRefreshToken(data.refreshToken)
    } else {
      // 本次登录没有 refresh_token：必须清掉上一会话遗留的会话级刷新令牌，
      // 否则 401 续期会用它换出**上一个用户**的 access token（身份串号）。
      sessionStorage.removeItem(STORAGE_KEYS.REFRESH_TOKEN)
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
   * 从旧版 localStorage 迁移数据到 sessionStorage。
   * 仅执行一次，迁移完成后清理旧数据。
   *
   * 注：这里沿用 getToken/getUser/getRefreshToken 读取"当前生效凭据"——
   * 迁移时机在应用启动早期（session 通常为空），_activeCredentials() 会回退到
   * 旧版键，因此旧数据仍能被完整搬走（保持既有可测语义）。
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
