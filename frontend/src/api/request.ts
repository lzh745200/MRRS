/**
 * Axios HTTP 请求封装
 */
import axios, { type AxiosRequestConfig, type Canceler } from 'axios'
import { ElMessage } from 'element-plus'
import { logger } from '@/utils/logger'
import { AuthStorage } from '@/utils/authStorage'
import { safeArray } from '@/composables/useSafeData'
import { isOfflineMode, getMockResponse } from '@/utils/offlineMock'

const request = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
  // 携带凭证（Cookie）：CSRF Double Submit Cookie 模式需要跨域/同源均能携带
  // csrftoken Cookie，服务端 CORS 已开启 allow_credentials。
  withCredentials: true,
})

export type RequestConfig = AxiosRequestConfig

// 跟踪待处理请求
const pendingRequests = new Map<string, Canceler>()

/** 内存缓存 token，避免每条请求都读 sessionStorage */
let _cachedToken: string | null = null

// ── 请求冻结机制 ──
// 改密/登出后立即冻结，防止 setTimeout 跳转期间 Vue 组件发请求触发 401 竞态。
// 冻结期间所有请求被直接取消（不触发 401 拦截器），页面跳转后自动解冻。
let _requestFrozen = false
export function freezeRequests(): void {
  _requestFrozen = true
}
export function unfreezeRequests(): void {
  _requestFrozen = false
}

// ── Refresh Token 续期机制 ──
// 401 时尝试用 refresh_token 换取新 access_token，成功后重试原请求。
// 使用标志位防止并发 401 触发多次 refresh，其余请求排队等待。
let _isRefreshing = false
let _refreshSubscribers: Array<{ resolve: (token: string) => void; reject: (err: any) => void }> =
  []

/** 将等待中的请求加入队列，refresh 成功后用新 token 重发 */
function _subscribeTokenRefresh(
  resolve: (token: string) => void,
  reject: (err: any) => void
): void {
  _refreshSubscribers.push({ resolve, reject })
}

/** refresh 成功后通知所有排队请求 */
function _onTokenRefreshed(newToken: string): void {
  _refreshSubscribers.forEach(({ resolve }) => resolve(newToken))
  _refreshSubscribers = []
}

/** refresh 失败后拒绝所有排队请求 */
function _onRefreshFailed(err: any): void {
  _refreshSubscribers.forEach(({ reject }) => reject(err))
  _refreshSubscribers = []
}

/** 判断请求 URL 是否为不应触发 refresh 的端点 */
function _isAuthEndpoint(url: string | undefined): boolean {
  if (!url) return false
  return (
    url.includes('/auth/login') ||
    url.includes('/auth/refresh') ||
    url.includes('/auth/two-factor/verify-login')
  )
}

/**
 * 会话过期统一出口：提示 + 清理 + 跳转登录。
 *
 * 体验约定（修复"提示闪一下看不清"）：
 * - ElMessage grouping 去重（并发多请求同时 401 只弹一条角标计数）；
 * - 先 closeAll() 清掉过时提示，再延迟 600ms 整页跳转，保证用户读完整文案。
 * 四个 401 分支（_retry 再 401 / auth 端点 401 / 无 refresh_token / refresh 失败）
 * 一律走此函数，行为完全一致。
 */
function _handleSessionExpired(error: any): Promise<never> {
  error.userMessage = '登录已过期，请重新登录'
  if (!_requestFrozen) {
    ElMessage.error({ message: '登录已过期，请重新登录', grouping: true })
  }
  if (
    typeof window !== 'undefined' &&
    !_isTestEnv &&
    !_requestFrozen &&
    !window.location.pathname.startsWith('/login')
  ) {
    window.setTimeout(() => {
      window.location.href = '/login'
    }, 600)
  }
  return Promise.reject(error)
}

// ── CSRF Token 管理（Double Submit Cookie 模式）──
// 后端开启 CSRF 保护后，POST/PUT/DELETE/PATCH 需在 X-CSRF-Token 头回填 token。
// token 来源：优先从 csrftoken Cookie 读取；若无则懒加载 GET /auth/csrf-token 获取
// （响应会同时 Set-Cookie）。测试环境（MODE=test）不发起自动获取，避免影响单测。
const _CSRF_COOKIE_NAME = 'csrftoken'
const _CSRF_HEADER_NAME = 'X-CSRF-Token'
const _CSRF_TOKEN_ENDPOINT = '/auth/csrf-token'
const _UNSAFE_METHODS = new Set(['post', 'put', 'delete', 'patch'])
const _isTestEnv = import.meta.env.MODE === 'test'
let _csrfToken: string | null = null
let _csrfFetchInFlight: Promise<string | null> | null = null

/** 从 document.cookie 读取指定 cookie 值 */
function _readCookie(name: string): string | null {
  if (typeof document === 'undefined' || !document.cookie) return null
  const match = document.cookie.match(
    new RegExp('(?:^|; )' + name.replace(/([.$?*|{}()[\]\\/+^])/g, '\\$1') + '=([^;]*)')
  )
  return match ? decodeURIComponent(match[1]) : null
}

/**
 * 确保已获取 CSRF token（cookie 优先，缺失时懒加载一次）。
 * 测试环境直接返回 null，不发起网络请求。
 */
async function _ensureCsrfToken(): Promise<string | null> {
  if (_csrfToken) return _csrfToken
  // 1. 优先从 cookie 读取（Double Submit Cookie）
  const fromCookie = _readCookie(_CSRF_COOKIE_NAME)
  if (fromCookie) {
    _csrfToken = fromCookie
    return _csrfToken
  }
  // 2. 测试环境不自动获取，避免单测触发真实网络请求
  if (_isTestEnv || typeof document === 'undefined') return null
  // 3. 懒加载获取（去重并发请求）
  if (!_csrfFetchInFlight) {
    _csrfFetchInFlight = (async () => {
      try {
        // 用裸 axios.get 绕过自身拦截器，避免递归（GET 为安全方法本就不会触发 CSRF 分支）
        const res = await axios.get(
          (import.meta.env.VITE_API_BASE_URL || '/api/v1') + _CSRF_TOKEN_ENDPOINT,
          { withCredentials: true }
        )
        const token =
          (res.data && (res.data as any)?.data?.csrf_token) ||
          (res.data && (res.data as any)?.csrf_token) ||
          _readCookie(_CSRF_COOKIE_NAME)
        if (token) _csrfToken = token as string
        return _csrfToken
      } catch {
        // 获取失败不阻断请求；服务端会返回 403 由响应拦截器处理
        return null
        /* c8 ignore next -- finally 分支为 v8 计数伪影（try 必定走到 finally） */
      } finally {
        _csrfFetchInFlight = null
      }
    })()
  }
  await _csrfFetchInFlight
  return _csrfToken
}

/** 生成稳定排序的请求标识 key */
function _makeRequestKey(method: string | undefined, url: string | undefined, params: any): string {
  const serialized = JSON.stringify(params || {}, Object.keys(params || {}).sort())
  return `${method}:${url}:${serialized}`
}

request.interceptors.request.use(async (config) => {
  // 请求被冻结时直接取消（改密/登出后跳转期间，防止组件发请求触发 401 竞态）
  if (_requestFrozen) {
    return Promise.reject(new axios.Cancel('Requests frozen after logout/password-change'))
  }
  if (_cachedToken === null) {
    _cachedToken = AuthStorage.getToken()
  }
  if (_cachedToken) {
    config.headers.Authorization = `Bearer ${_cachedToken}`
  }
  // ── CSRF：不安全方法自动回填 X-CSRF-Token ──
  const method = (config.method || 'get').toLowerCase()
  if (_UNSAFE_METHODS.has(method)) {
    const token = await _ensureCsrfToken()
    if (token) {
      config.headers[_CSRF_HEADER_NAME] = token
    }
  }
  // ── W3-T4：仅幂等的 GET 参与去重取消 ──
  // POST/PUT/DELETE 绝不互相取消：此前全方法共用 key 池，同端点两个并发 POST
  // （body 不同）会被静默 cancel 导致批量操作丢写入。
  if ((config.method || 'get').toLowerCase() === 'get') {
    const requestKey = _makeRequestKey(config.method, config.url, config.params)
    if (pendingRequests.has(requestKey)) {
      pendingRequests.get(requestKey)!()
    }
    config.cancelToken = new axios.CancelToken((cancel) => {
      pendingRequests.set(requestKey, cancel)
    })
  }
  return config
})

/**
 * RESPONSE UNWRAP INTERCEPTOR
 *
 * Backend wraps most responses as: { code: 200, data: <payload>, message: "success" }
 * This interceptor expands <payload> keys into the top-level response.data object
 * so callers can access fields directly without `.data.data.xxx`.
 *
 * Behavior:
 * - Object payload → keys copied to response.data (existing keys like code/message/data preserved)
 * - Array payload  → set as response.data.items (if items not already present)
 *
 * IMPORTANT: This mutates response.data IN PLACE. Both raw axios callers (Pattern A:
 * `import { get, post, put, patch, apiRequest } from '@/api/request'` → use `.data`) and auto-unwrapped callers (Pattern B:
 * `import { get, post } from "./request"` → `.data` NOT needed) see the same expanded shape.
 *
 * @see apiRequest — auto-unwrapped access (returns res.data directly)
 */
// ── 错误提示策略（2026-08-14 重构）──
// 拦截器不再对业务错误直接弹全局提示（避免与页面 catch 双重弹窗、并发请求刷屏）：
// 1. 401 保持系统级处理（登录过期提示 + refresh 续期 / 跳转登录）
// 2. 其余错误统一挂载 error.userMessage（含 Blob 响应体中的 JSON 错误解析），
//    由页面自行决定提示方式；未被任何页面捕获的失败由全局
//    unhandledrejection 兜底提示（utils/errorHandler.ts），保证每个失败最多一条提示。
// 3. 请求配置支持 silent: true —— 页面明确不需要任何错误提示（连兜底也跳过）。

/** 从错误响应中提取服务端返回的可读信息（支持 Blob 响应体中的 JSON 错误） */
async function _extractServerMessage(error: any): Promise<string> {
  const data = error?.response?.data
  if (data instanceof Blob) {
    try {
      const text = await data.text()
      const parsed = JSON.parse(text)
      if (parsed?.detail) return typeof parsed.detail === 'string' ? parsed.detail : ''
      if (parsed?.message) return typeof parsed.message === 'string' ? parsed.message : ''
      return ''
    } catch {
      return ''
    }
  }
  const detail = data?.detail
  if (typeof detail === 'string' && detail) return detail
  const message = data?.message
  if (typeof message === 'string' && message) return message
  return ''
}

/** 构建用户可读的错误消息（挂载到 error.userMessage） */
async function _buildUserMessage(error: any): Promise<string> {
  const serverMsg = await _extractServerMessage(error)
  const status = error?.response?.status

  if (status === 422) {
    const detail: any = error?.response?.data?.detail
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0]
      return `${first.loc?.join('.') || ''}: ${first.msg || first.message || ''}`.trim()
    }
    return serverMsg || '输入数据校验失败'
  }
  // 注：401/403 由响应拦截器先行处理（登录过期/CSRF 重试），不会到达本函数
  if (status === 404) return serverMsg || '请求的资源不存在'
  if (status >= 500) return serverMsg || '服务器错误，请稍后重试'
  if (status) return serverMsg || `请求失败 (${status})`
  if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
    return '请求超时，请重试'
  }
  if (error.code === 'ERR_NETWORK' || error.message?.includes('NetworkError')) {
    return '网络连接失败，请检查服务是否启动'
  }
  if (typeof error?.message === 'string' && error.message && error.message !== 'Network Error') {
    return error.message
  }
  return '操作失败'
}

request.interceptors.response.use(
  (response) => {
    const requestKey = _makeRequestKey(
      response.config.method,
      response.config.url,
      response.config.params
    )
    pendingRequests.delete(requestKey)

    // ── 统一响应格式：自动展开 {data: payload} → 顶层字段 ──
    // 保持 data 键不变以兼容旧代码（res.data / res.data.data），同时将内部字段提升到顶层
    // 注意：不覆盖 code/message/data 顶层键（若 payload 内同名字段需通过 .data.xxx 访问）
    const data = response.data
    if (data && typeof data === 'object') {
      if ('data' in data) {
        const inner = data.data
        if (inner !== null && inner !== undefined) {
          if (typeof inner === 'object' && !Array.isArray(inner)) {
            // 对象 → 展开到顶层，但跳过已有键（保护 code/message/data 元数据）
            for (const key of Object.keys(inner)) {
              if (!(key in data)) {
                data[key] = inner[key]
              }
            }
          } else if (Array.isArray(inner)) {
            // 数组 → 设为 items（不覆盖已有 items）
            if (!('items' in data)) {
              data.items = inner
            }
          }
        }
      }
      // 安全化 items 字段（非数组 → []）
      if ('items' in data) {
        const safe = safeArray(data.items)
        if (safe !== data.items) {
          logger.warn("[API] 'items' field sanitized (was not an array)", data)
          data.items = safe
        }
      }
      // 安全化 total 字段（非数字 → items.length）
      if ('total' in data && typeof data.total !== 'number') {
        data.total = safeArray(data.items).length
      }
    }
    return response
  },
  async (error) => {
    // ── 已取消的请求不提示 ──
    if (error.__CANCEL__ || error.code === 'ERR_CANCELED') {
      return Promise.reject(error)
    }

    // ── 清理 pending 请求追踪（失败请求也需要清理，防止 stale entry 阻塞后续请求）──
    if (error.config) {
      const requestKey = _makeRequestKey(error.config.method, error.config.url, error.config.params)
      pendingRequests.delete(requestKey)
    }

    const originalRequest = error.config

    // ── HTTP 状态码分类处理 ──
    if (error.response) {
      const { status } = error.response
      if (status === 401) {
        // W3-T5：已带 _retry 标记的请求再次 401 → refresh 已试过仍失败，
        // 直接登出，严禁再进入刷新流程（防止无限刷新循环）
        if (originalRequest && (originalRequest as any)._retry) {
          _cachedToken = null
          _isRefreshing = false
          _onRefreshFailed(new Error('refresh 已重试仍 401'))
          AuthStorage.clear()
          return _handleSessionExpired(error)
        }
        // 系统级处理：登录过期提示 + refresh 续期 / 跳转登录（保留全局提示）
        if (!originalRequest || _isAuthEndpoint(originalRequest.url)) {
          _cachedToken = null
          AuthStorage.clear()
          return _handleSessionExpired(error)
        }

        // 检查是否有 refresh_token 可用
        const refreshToken = AuthStorage.getRefreshToken()
        if (!refreshToken) {
          // 无 refresh_token，直接登出
          _cachedToken = null
          AuthStorage.clear()
          return _handleSessionExpired(error)
        }

        // 如果已经在刷新中，将当前请求加入队列等待
        if (_isRefreshing) {
          return new Promise((resolve, reject) => {
            _subscribeTokenRefresh(
              (newToken: string) => {
                originalRequest.headers.Authorization = `Bearer ${newToken}`
                resolve(request.request(originalRequest))
              },
              (err: any) => {
                reject(err)
              }
            )
          })
        }

        // 标记正在刷新，防止并发 401 重复触发
        _isRefreshing = true
        originalRequest._retry = true

        try {
          // 调用 refresh 端点（用裸 axios 避免触发自身拦截器）。
          // 注意：/auth/refresh 不在后端 CSRF 豁免列表，必须手动携带
          // X-CSRF-Token 头，否则会 403 导致续期失败（修复 2026-08-14）。
          const csrf = await _ensureCsrfToken()
          const refreshHeaders: Record<string, string> = { 'Content-Type': 'application/json' }
          if (csrf) {
            refreshHeaders[_CSRF_HEADER_NAME] = csrf
          }
          const refreshRes = await axios.post(
            (import.meta.env.VITE_API_BASE_URL || '/api/v1') + '/auth/refresh',
            { token: refreshToken },
            { headers: refreshHeaders, withCredentials: true }
          )

          const refreshData = refreshRes.data
          const newAccessToken = refreshData?.data?.access_token
          // 后端信封 {code, data:{access_token, refresh_token}}；兼容裸返回
          const newRefreshToken = refreshData?.data?.refresh_token || refreshData?.refresh_token

          if (!newAccessToken) {
            throw new Error('Refresh response missing access_token')
          }

          // 更新存储的 token
          _cachedToken = newAccessToken
          AuthStorage.setToken(newAccessToken)
          if (newRefreshToken) {
            AuthStorage.setRefreshToken(newRefreshToken)
          }
          // 记住登录（自动登录）开启时：同步更新持久令牌，保持免登录长期有效
          if (AuthStorage.hasPersistedAuth()) {
            const persistedUser = AuthStorage.getUser()
            if (persistedUser) {
              AuthStorage.persistForAutoLogin({
                token: newAccessToken,
                user: persistedUser,
                refreshToken: newRefreshToken,
              })
            }
          }

          // 通知所有排队请求使用新 token 重试
          _onTokenRefreshed(newAccessToken)

          // 重试原始请求
          originalRequest.headers.Authorization = `Bearer ${newAccessToken}`
          return request.request(originalRequest)
        } catch (refreshError) {
          // Refresh 失败：清除认证状态，拒绝所有排队请求
          _onRefreshFailed(refreshError)
          _cachedToken = null
          AuthStorage.clear()
          // 保留原始 refreshError 作为 rejection 原因（调用方依赖其错误消息）
          return _handleSessionExpired(refreshError)
          /* c8 ignore next -- finally 分支为 v8 计数伪影（try/catch 必定走到 finally） */
        } finally {
          _isRefreshing = false
        }
      }

      if (status === 403) {
        // CSRF 校验失败时重置 token 缓存，自动获取新 token 并重试一次
        const serverMsg = await _extractServerMessage(error)
        if (serverMsg.includes('CSRF') || serverMsg.includes('csrf')) {
          _csrfToken = null
          // 自动重试：获取新 CSRF token 后重发原请求（仅重试一次，防无限循环）
          if (originalRequest && !originalRequest._csrfRetried) {
            originalRequest._csrfRetried = true
            return _ensureCsrfToken().then((newToken) => {
              if (newToken) {
                originalRequest.headers[_CSRF_HEADER_NAME] = newToken
              }
              return request.request(originalRequest)
            })
          }
          error.userMessage = '安全校验已过期，请重试（CSRF）'
        } else {
          error.userMessage = serverMsg || '权限不足，无法执行此操作'
        }
      } else {
        // 400/404/422/5xx：不再全局弹窗，挂载 userMessage 由页面/兜底处理
        error.userMessage = await _buildUserMessage(error)
      }
    } else if (error.code === 'ERR_NETWORK' || error.message?.includes('NetworkError')) {
      // 离线回退：检查是否处于离线模式，尝试从离线 Mock 提供数据
      if (isOfflineMode() && error.config) {
        const { method, url } = error.config
        const mockData = getMockResponse(method || 'GET', url || '')
        if (mockData) {
          // 清理 pending 请求追踪（模拟成功拦截器的清理逻辑）
          const requestKey = `${method}:${url}`
          pendingRequests.delete(requestKey)
          console.info('[API] Offline fallback:', method, url)
          return Promise.resolve(mockData)
        }
      }
      // 自动重试：后端可能正在短暂重启（Electron 自动重启机制），延迟 2 秒后重试一次
      if (error.config && !error.config._networkRetried && !_isTestEnv) {
        error.config._networkRetried = true
        return new Promise((resolve) => setTimeout(resolve, 2000)).then(() => {
          return request.request(error.config)
        })
      }
      error.userMessage = '网络连接失败，请检查服务是否启动'
    } else if (error.code === 'ECONNABORTED') {
      error.userMessage = '请求超时，请重试'
    } else {
      console.error('[API] Unexpected error:', error.message || error)
      error.userMessage =
        typeof error?.message === 'string' && error.message ? error.message : '操作失败'
    }

    // silent 配置：页面明确不需要任何错误提示（连全局兜底也跳过）
    if ((originalRequest as any)?.silent) {
      error.__silent = true
    }

    return Promise.reject(error)
  }
)

/** 更新 token 缓存（登录/登出时由 auth store 调用） */
export function _setCachedToken(t: string | null) {
  _cachedToken = t
}

/** 主动获取并缓存 CSRF token（应用初始化/登录后可调用以预热） */
export async function prefetchCsrfToken(): Promise<string | null> {
  return _ensureCsrfToken()
}

/**
 * 获取 CSRF token（供 el-upload 等原生 XHR/FormData 上传使用——
 * 这些请求不走 axios 拦截器，必须手动携带 X-CSRF-Token 头）
 */
export async function getCsrfToken(): Promise<string | null> {
  return _ensureCsrfToken()
}

// ── 泛型核心请求函数 ──

/**
 * Generic request function with automatic response unwrapping.
 *
 * Unlike raw `get()` which returns `AxiosResponse<T>`,
 * this function returns `T` directly (`res.data`), unwrapping one level.
 *
 * Combined with the response interceptor's in-place expansion,
 * callers receive the backend's `data` payload directly.
 *
 * USAGE: Prefer `get<T>(url)` / `post<T>(url, data)` convenience wrappers.
 *        DO NOT access `.data` on their return values — they are already unwrapped.
 *
 * @example
 *   // Pattern B — auto-unwrapped via apiRequest()
 *   const items = await get<Item[]>("/items");  // Item[], not AxiosResponse
 *   items[0].name   // correct
 *   items.data      // WRONG (double-unwrap)
 *
 *   // Pattern A — raw axios instance
 *   const res = await request.get<Item[]>("/items");
 *   res.data[0].name  // correct (.data needed on AxiosResponse)
 */
export async function apiRequest<T = any>(config: AxiosRequestConfig): Promise<T> {
  const res = await request.request<T>(config)
  return res.data
}

// ── 便捷方法别名 ──

export async function get<T = any>(url: string, params?: any): Promise<T> {
  return apiRequest<T>({ method: 'GET', url, params })
}

export async function post<T = any>(
  url: string,
  data?: any,
  extra?: AxiosRequestConfig
): Promise<T> {
  const config: AxiosRequestConfig = {
    method: 'POST',
    url,
    data,
    ...(extra || {}),
  }
  if (data instanceof FormData) {
    // 移除 Content-Type 让浏览器自动设置 multipart boundary
    // （无论调用方是否传 headers——否则 axios 会按默认 JSON 序列化 FormData，
    //   导致后端 UploadFile 参数 422）
    const h = { ...(config.headers || {}) } as Record<string, any>
    delete h['Content-Type']
    delete h['content-type']
    config.headers = h
    // 覆盖默认 transformRequest：实例级默认 headers 的 application/json 会在
    // mergeConfig 时合并回来（hasJSONContentType=true → JSON.stringify(FormData)=="{}"，
    // 后端 multipart 解析失败返回 422 file missing）。此处原样透传 FormData，
    // 并在转换阶段彻底清除 Content-Type，让浏览器自动生成 multipart boundary。
    config.transformRequest = [
      (d: any, hdrs: any) => {
        if (d instanceof FormData) {
          hdrs?.setContentType?.(undefined)
          return d
        }
        return d
      },
    ]
  }
  return apiRequest<T>(config)
}

export async function put<T = any>(url: string, data?: any): Promise<T> {
  return apiRequest<T>({ method: 'PUT', url, data })
}

export async function del<T = any>(url: string): Promise<T> {
  return apiRequest<T>({ method: 'DELETE', url })
}

export async function patch<T = any>(url: string, data?: any): Promise<T> {
  return apiRequest<T>({ method: 'PATCH', url, data })
}

// ── 取消管理 ──

/** 取消指定 URL 的挂起请求（精确匹配 URL 段，避免子串误伤） */
export function cancelRequest(url: string): void {
  const urlSegment = `:${url}:`
  for (const [key, cancel] of pendingRequests.entries()) {
    if (key.includes(urlSegment)) {
      cancel()
      pendingRequests.delete(key)
    }
  }
}

/** 取消所有挂起请求 */
export function cancelAllRequests(): void {
  for (const cancel of pendingRequests.values()) {
    cancel()
  }
  pendingRequests.clear()
}

/** 检查错误是否为请求取消 */
export function isRequestCancelled(error: any): boolean {
  return axios.isCancel(error)
}

/** 获取挂起请求数量 */
export function getPendingRequestCount(): number {
  return pendingRequests.size
}

/** 创建可取消请求 */
export function createCancelableRequest<T = any>(
  config: AxiosRequestConfig
): { promise: Promise<T>; cancel: Canceler } {
  const source = axios.CancelToken.source()
  const promise = apiRequest({
    ...config,
    cancelToken: source.token,
  }) as Promise<T>
  return { promise, cancel: source.cancel }
}

/** 带超时的请求 */
export function requestWithTimeout<T = any>(
  config: AxiosRequestConfig,
  timeoutMs: number
): Promise<T> {
  return new Promise((resolve, reject) => {
    const { promise, cancel } = createCancelableRequest<T>(config)
    const timer = setTimeout(() => {
      cancel()
      reject(new Error(`Request timeout after ${timeoutMs}ms`))
    }, timeoutMs)
    promise.then(resolve, reject).finally(() => clearTimeout(timer))
  })
}

/** 检查响应是否成功 */
export function isSuccess(status: number): boolean {
  return status >= 200 && status < 300
}

/**
 * 从响应头 Content-Disposition 解析文件名。
 *
 * 后端使用 RFC 5987 格式：`attachment; filename*=UTF-8''%E5%B8%AE%E6%89%B6%E6%9D%91.xlsx`
 * 浏览器/某些场景会把 `UTF-8` 当作文件名（用户反馈"所有模板下载文件名都是 UTF-8"），
 * 因此前端必须显式解析并 decodeURIComponent。
 *
 * 支持两种格式：
 *   1. filename*=UTF-8''<percent-encoded>   （优先，RFC 5987）
 *   2. filename="<quoted>"                  （回退，ASCII）
 *
 * @param headers axios 响应头对象
 * @param fallback 解析失败时的兜底文件名
 */
export function parseContentDisposition(
  headers: Record<string, string> | undefined,
  fallback = 'download.xlsx'
): string {
  if (!headers) return fallback
  // axios 响应头大小写不固定，统一小写查找
  const cd =
    headers['content-disposition'] ||
    headers['Content-Disposition'] ||
    headers['CONTENT-DISPOSITION']
  if (!cd) return fallback

  // 1. 优先 filename*=UTF-8''xxx
  const starMatch = cd.match(/filename\*=([^;]+)/i)
  if (starMatch) {
    // 形如 UTF-8''%E5%B8%AE...  → 取 '' 之后的 percent-encoded 段
    const raw = starMatch[1].trim()
    const idx = raw.indexOf("''")
    if (idx >= 0) {
      const encoded = raw.slice(idx + 2)
      try {
        const decoded = decodeURIComponent(encoded)
        if (decoded) return decoded
      } catch {
        // 解码失败时 fallthrough 到下一策略
      }
    }
  }

  // 2. 回退 filename="xxx"
  const quotedMatch = cd.match(/filename="?([^";]+)"?/i)
  if (quotedMatch) {
    const name = quotedMatch[1].trim()
    if (name) return name
  }

  return fallback
}

/** 触发浏览器下载 Blob（封装 saveAs 逻辑，避免重复依赖 file-saver） */
export function downloadBlob(blob: Blob, filename: string): void {
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.style.display = 'none'
  document.body.appendChild(link)
  link.click()
  // 释放对象 URL，避免内存泄漏
  setTimeout(() => {
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
  }, 100)
}

export default request
