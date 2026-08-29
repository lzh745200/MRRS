import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// request.ts 的 `_isTestEnv`（import.meta.env.MODE === 'test'）在模块加载时求值，
// 决定 CSRF 懒加载、登录跳转、网络重试等分支是否可达。
// 本文件用 vi.stubEnv + vi.resetModules + 动态 import 按需加载不同环境下的模块实例。
const {
  handlers,
  mockInst,
  mockAxiosGet,
  mockAxiosPost,
  authState,
  mockAuthStorage,
  mockElMessage,
} = vi.hoisted(() => {
  const handlers: { request: any; response: any; responseR: any } = {
    request: null,
    response: null,
    responseR: null,
  }
  const authState = { token: 'test-jwt-token', refreshToken: 'refresh-1' }
  const mockElMessage = { error: vi.fn(), warning: vi.fn(), success: vi.fn(), info: vi.fn() }
  const mockAuthStorage = {
    getToken: vi.fn(() => authState.token),
    getRefreshToken: vi.fn(() => authState.refreshToken),
    setToken: vi.fn(),
    setRefreshToken: vi.fn(),
    clear: vi.fn(() => {
      authState.token = ''
    }),
  }
  const mockInst = {
    request: vi.fn(),
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
    patch: vi.fn(),
    interceptors: {
      request: { use: vi.fn((f: any) => { handlers.request = f }) },
      response: {
        use: vi.fn((f: any, r: any) => {
          handlers.response = f
          handlers.responseR = r
        }),
      },
    },
    defaults: {},
  }
  return {
    handlers,
    mockInst,
    mockAxiosGet: vi.fn(),
    mockAxiosPost: vi.fn(),
    authState,
    mockAuthStorage,
    mockElMessage,
  }
})

vi.mock('axios', () => ({
  default: {
    create: vi.fn(() => mockInst),
    get: mockAxiosGet,
    post: mockAxiosPost,
    CancelToken: vi.fn(() => 'cancel-token'),
    Cancel: class Cancel {},
    isCancel: (e: any) => e?.__CANCEL__ === true,
  },
}))

vi.mock('@/utils/authStorage', () => ({ AuthStorage: mockAuthStorage }))

vi.mock('element-plus', () => ({ ElMessage: mockElMessage }))

vi.mock('@/utils/offlineMock', () => ({
  isOfflineMode: vi.fn(() => false),
  getMockResponse: vi.fn(),
}))

vi.mock('@/composables/useSafeData', () => ({
  safeArray: (arr: any) => (Array.isArray(arr) ? arr : []),
}))

let requestModule: typeof import('@/api/request')

async function load(mode: 'development' | 'test') {
  vi.stubEnv('MODE', mode)
  vi.resetModules()
  requestModule = await import('@/api/request')
}

function clearCookies() {
  document.cookie.split(';').forEach((c) => {
    const name = c.split('=')[0].trim()
    if (name) {
      document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/`
    }
  })
}

beforeEach(() => {
  vi.clearAllMocks()
  authState.token = 'test-jwt-token'
  authState.refreshToken = 'refresh-1'
  clearCookies()
})

afterEach(() => {
  vi.restoreAllMocks()
  vi.useRealTimers()
})

const makeConfig = (over: any = {}) => ({
  method: 'GET',
  url: '/x',
  params: {},
  headers: {},
  ...over,
})

describe('api/request — 非测试环境 CSRF 懒加载', () => {
  beforeEach(async () => {
    await load('development')
  })

  it('prefetchCsrfToken 无 cookie 时懒加载获取 token（data.data.csrf_token）', async () => {
    mockAxiosGet.mockResolvedValueOnce({ data: { data: { csrf_token: 'lazy-t1' } } })
    const token = await requestModule.prefetchCsrfToken()
    expect(token).toBe('lazy-t1')
    expect(mockAxiosGet).toHaveBeenCalledWith(
      '/api/v1/auth/csrf-token',
      expect.objectContaining({ withCredentials: true })
    )
  })

  it('懒加载响应走 data.csrf_token 兜底形状', async () => {
    mockAxiosGet.mockResolvedValueOnce({ data: { csrf_token: 'lazy-t2' } })
    expect(await requestModule.prefetchCsrfToken()).toBe('lazy-t2')
  })

  it('懒加载响应 data 为 null → 兜底到 cookie 读取并返回 null', async () => {
    mockAxiosGet.mockResolvedValueOnce({ data: null })
    expect(await requestModule.prefetchCsrfToken()).toBeNull()
  })

  it('懒加载响应 data 为空对象 → 兜底到 cookie 读取并返回 null', async () => {
    mockAxiosGet.mockResolvedValueOnce({ data: {} })
    expect(await requestModule.prefetchCsrfToken()).toBeNull()
  })

  it('懒加载响应无 token 时回退读取 cookie', async () => {
    document.cookie = 'csrftoken=cookie-t; path=/'
    mockAxiosGet.mockResolvedValueOnce({ data: {} })
    expect(await requestModule.prefetchCsrfToken()).toBe('cookie-t')
  })

  it('懒加载获取失败返回 null 且不阻断后续请求', async () => {
    mockAxiosGet.mockRejectedValueOnce(new Error('network down'))
    expect(await requestModule.prefetchCsrfToken()).toBeNull()
  })

  it('并发调用懒加载仅发起一次请求（去重）', async () => {
    let resolveGet: any
    mockAxiosGet.mockReturnValueOnce(
      new Promise((res) => {
        resolveGet = res
      })
    )
    const p1 = requestModule.prefetchCsrfToken()
    const p2 = requestModule.prefetchCsrfToken()
    expect(mockAxiosGet).toHaveBeenCalledTimes(1)
    resolveGet({ data: { data: { csrf_token: 'dedup-t' } } })
    await expect(p1).resolves.toBe('dedup-t')
    await expect(p2).resolves.toBe('dedup-t')
  })

  it('懒加载成功后 POST 请求自动回填 X-CSRF-Token 头', async () => {
    mockAxiosGet.mockResolvedValueOnce({ data: { data: { csrf_token: 'header-t' } } })
    const config = makeConfig({ method: 'POST', url: '/secure' })
    await handlers.request(config)
    expect(config.headers['X-CSRF-Token']).toBe('header-t')
  })
})

describe('api/request — 测试环境 CSRF 分支', () => {
  beforeEach(async () => {
    await load('test')
  })

  it('POST 请求 cookie 无 csrftoken 键时返回 null 不设置头', async () => {
    document.cookie = 'other=1; path=/'
    const config = makeConfig({ method: 'POST', url: '/no-key' })
    await handlers.request(config)
    expect(config.headers['X-CSRF-Token']).toBeUndefined()
    expect(mockAxiosGet).not.toHaveBeenCalled()
  })

  it('CSRF token 缓存后后续不安全请求直接复用缓存', async () => {
    document.cookie = 'csrftoken=csrf-cached; path=/'
    const cfg1 = makeConfig({ method: 'PUT', url: '/cache-1' })
    await handlers.request(cfg1)
    expect(cfg1.headers['X-CSRF-Token']).toBe('csrf-cached')
    const cfg2 = makeConfig({ method: 'DELETE', url: '/cache-2' })
    await handlers.request(cfg2)
    expect(cfg2.headers['X-CSRF-Token']).toBe('csrf-cached')
    expect(mockAxiosGet).not.toHaveBeenCalled()
  })
})

describe('api/request — 非测试环境登录跳转', () => {
  beforeEach(async () => {
    await load('development')
  })

  it('401 登录端点 → 清除认证并跳转 /login', async () => {
    const error = { response: { status: 401, data: {} }, config: makeConfig({ url: '/auth/login' }) }
    await expect(handlers.responseR(error)).rejects.toBe(error)
    expect(mockAuthStorage.clear).toHaveBeenCalled()
    expect(mockElMessage.error).toHaveBeenCalledWith(expect.objectContaining({ message: '登录已过期，请重新登录', grouping: true }))
  })

  it('401 无 refresh_token → 清除认证并跳转 /login', async () => {
    authState.refreshToken = ''
    const error = { response: { status: 401, data: {} }, config: makeConfig({ url: '/data' }) }
    await expect(handlers.responseR(error)).rejects.toBe(error)
    expect(mockAuthStorage.clear).toHaveBeenCalled()
    expect(mockAxiosPost).not.toHaveBeenCalled()
  })

  it('401 refresh 失败 → 拒绝排队请求、清除认证并跳转 /login', async () => {
    mockAxiosPost.mockRejectedValueOnce(new Error('refresh failed'))
    const error = { response: { status: 401, data: {} }, config: makeConfig({ url: '/data' }) }
    await expect(handlers.responseR(error)).rejects.toThrow('refresh failed')
    expect(mockAuthStorage.clear).toHaveBeenCalled()
    expect(mockElMessage.error).toHaveBeenCalledWith(expect.objectContaining({ message: '登录已过期，请重新登录', grouping: true }))
  })
})

describe('api/request — 非测试环境网络自动重试', () => {
  beforeEach(async () => {
    await load('development')
  })

  it('ERR_NETWORK 且未重试过 → 延迟 2s 后自动重发原请求', async () => {
    vi.useFakeTimers()
    mockInst.request.mockResolvedValueOnce('retried')
    const config = makeConfig({ method: 'GET', url: '/flaky' })
    const error = { code: 'ERR_NETWORK', message: 'NetworkError', config }
    const promise = handlers.responseR(error)
    const assertion = expect(promise).resolves.toBe('retried')
    await vi.advanceTimersByTimeAsync(2000)
    await assertion
    expect(config._networkRetried).toBe(true)
    expect(mockInst.request).toHaveBeenCalledWith(config)
  })

  it('ERR_NETWORK 已重试过 → 不再重试并挂载网络失败消息', async () => {
    const config = makeConfig({ _networkRetried: true })
    const error = { code: 'ERR_NETWORK', message: 'NetworkError', config }
    await expect(handlers.responseR(error)).rejects.toBe(error)
    expect(error.userMessage).toBe('网络连接失败，请检查服务是否启动')
    expect(mockElMessage.error).not.toHaveBeenCalled()
  })
})
