import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// ── Mock 基建：捕获 axios 实例与拦截器 handler，直接驱动 ──
const {
  handlers,
  mockInst,
  mockAxiosPost,
  mockAxiosGet,
  capturedCancels,
  authState,
  mockAuthStorage,
  mockElMessage,
  offlineState,
  mockGetMockResponse,
  mockCancelSource,
  mockCancel,
} = vi.hoisted(() => {
  const handlers: { request: any; response: any; responseR: any } = {
    request: null,
    response: null,
    responseR: null,
  }
  const capturedCancels: any[] = []
  const authState = { token: 'test-jwt-token', refreshToken: '' }
  const offlineState = { offline: false }
  const mockElMessage = { error: vi.fn(), warning: vi.fn(), success: vi.fn(), info: vi.fn() }
  const mockGetMockResponse = vi.fn()
  const mockCancel = vi.fn()
  const mockAuthStorage = {
    getToken: vi.fn(() => authState.token),
    getRefreshToken: vi.fn(() => authState.refreshToken),
    setToken: vi.fn(),
    setRefreshToken: vi.fn(),
    setAuthData: vi.fn(),
    getUser: vi.fn(() => null),
    hasPersistedAuth: vi.fn(() => false),
    persistForAutoLogin: vi.fn(),
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
      request: {
        use: vi.fn((f: any) => {
          handlers.request = f
        }),
      },
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
    mockAxiosPost: vi.fn(),
    mockAxiosGet: vi.fn(),
    capturedCancels,
    authState,
    mockAuthStorage,
    mockElMessage,
    offlineState,
    mockGetMockResponse,
    mockCancelSource: vi.fn(() => ({ token: 'mock-cancel-token', cancel: mockCancel })),
    mockCancel,
  }
})

vi.mock('axios', () => {
  const MockCancelToken: any = vi.fn((executor: any) => {
    const cancel = vi.fn()
    capturedCancels.push(cancel)
    executor(cancel)
    return 'cancel-token'
  })
  MockCancelToken.source = mockCancelSource
  return {
    default: {
      create: vi.fn(() => mockInst),
      post: mockAxiosPost,
      get: mockAxiosGet,
      CancelToken: MockCancelToken,
      Cancel: class Cancel {},
      isCancel: (e: any) => e?.__CANCEL__ === true,
    },
  }
})

vi.mock('@/utils/authStorage', () => ({ AuthStorage: mockAuthStorage }))

vi.mock('element-plus', () => ({ ElMessage: mockElMessage }))

vi.mock('@/utils/offlineMock', () => ({
  isOfflineMode: () => offlineState.offline,
  getMockResponse: mockGetMockResponse,
}))

vi.mock('@/composables/useSafeData', () => ({
  safeArray: (arr: any) => (Array.isArray(arr) ? arr : []),
}))

import {
  isSuccess,
  freezeRequests,
  unfreezeRequests,
  isRequestCancelled,
  getPendingRequestCount,
  cancelRequest,
  cancelAllRequests,
  _setCachedToken,
  prefetchCsrfToken,
  getCsrfToken,
  apiRequest,
  get,
  post,
  put,
  del,
  patch,
  createCancelableRequest,
  requestWithTimeout,
  parseContentDisposition,
  downloadBlob,
} from '@/api/request'

const makeConfig = (over: any = {}) => ({
  method: 'GET',
  url: '/x',
  params: {},
  headers: {},
  ...over,
})

describe('api/request — utility', () => {
  it('isSuccess 返回 true 对 2xx', () => {
    expect(isSuccess(200)).toBe(true)
    expect(isSuccess(201)).toBe(true)
    expect(isSuccess(299)).toBe(true)
  })

  it('isSuccess 返回 false 对 非 2xx', () => {
    expect(isSuccess(400)).toBe(false)
    expect(isSuccess(401)).toBe(false)
    expect(isSuccess(500)).toBe(false)
  })

  it('freezeRequests / unfreezeRequests', () => {
    freezeRequests()
    freezeRequests()
    unfreezeRequests()
  })

  it('isRequestCancelled', () => {
    expect(isRequestCancelled({ __CANCEL__: true })).toBe(true)
    expect(isRequestCancelled({})).toBe(false)
    expect(isRequestCancelled(null)).toBe(false)
  })

  it('getPendingRequestCount', () => {
    expect(getPendingRequestCount()).toBe(0)
  })

  it('cancelRequest / cancelAllRequests', () => {
    cancelRequest('/test')
    cancelAllRequests()
  })

  it('_setCachedToken', () => {
    _setCachedToken('new-token')
    _setCachedToken(null)
  })

  it('prefetchCsrfToken 在测试环境返回 null（不发起网络请求）', async () => {
    const result = await prefetchCsrfToken()
    expect(result).toBeNull()
    expect(mockAxiosGet).not.toHaveBeenCalled()
  })

  it('getCsrfToken 与 prefetchCsrfToken 行为一致（测试环境 null）', async () => {
    const result = await getCsrfToken()
    expect(result).toBeNull()
  })
})

describe('api/request — request 拦截器', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    authState.token = 'test-jwt-token'
    authState.refreshToken = ''
    offlineState.offline = false
    capturedCancels.length = 0
    _setCachedToken(null)
    unfreezeRequests()
    cancelAllRequests()
  })

  it('冻结状态下拒绝请求', async () => {
    freezeRequests()
    const config = makeConfig({ method: 'GET', url: '/test' })
    await expect(handlers.request(config)).rejects.toBeDefined()
    unfreezeRequests()
  })

  it('挂载 Authorization header', async () => {
    const config = makeConfig()
    await handlers.request(config)
    expect(config.headers.Authorization).toBe('Bearer test-jwt-token')
  })

  it('无 token 时不挂载 Authorization', async () => {
    authState.token = ''
    const config = makeConfig()
    await handlers.request(config)
    expect(config.headers.Authorization).toBeUndefined()
  })

  it('不安全方法无 csrftoken cookie 时不设置 CSRF 头', async () => {
    // document.cookie 非空但不存在 csrftoken → _readCookie 正则不匹配 → null
    document.cookie = 'other=1; path=/'
    const config = makeConfig({ method: 'DELETE', url: '/unsafe2' })
    await handlers.request(config)
    expect(config.headers['X-CSRF-Token']).toBeUndefined()
  })

  it('POST 请求回填 cookie 中的 CSRF token', async () => {
    document.cookie = 'csrftoken=csrf-abc; path=/'
    const config = makeConfig({ method: 'POST', url: '/unsafe' })
    await handlers.request(config)
    expect(config.headers['X-CSRF-Token']).toBe('csrf-abc')
  })

  it('GET 请求不设置 CSRF 头', async () => {
    document.cookie = 'csrftoken=csrf-abc; path=/'
    const config = makeConfig({ method: 'GET', url: '/safe' })
    await handlers.request(config)
    expect(config.headers['X-CSRF-Token']).toBeUndefined()
  })

  it('相同 key 的重复请求取消前一个挂起请求', async () => {
    await handlers.request(makeConfig({ method: 'GET', url: '/dup', params: { a: 1 } }))
    expect(capturedCancels).toHaveLength(1)
    await handlers.request(makeConfig({ method: 'GET', url: '/dup', params: { a: 1 } }))
    expect(capturedCancels).toHaveLength(2)
    expect(capturedCancels[0]).toHaveBeenCalled()
    expect(capturedCancels[1]).not.toHaveBeenCalled()
  })

  it('config 无 method 时回退为 get（不触发 CSRF）', async () => {
    const config = makeConfig({ method: undefined })
    await handlers.request(config)
    expect(config.headers['X-CSRF-Token']).toBeUndefined()
  })
})

describe('api/request — response 成功拦截器', () => {
  it('非对象 data 原样返回', () => {
    const response = { config: makeConfig(), data: 'plain-text' }
    const result = handlers.response(response)
    expect(result.data).toBe('plain-text')
  })

  it('data 为 null 时不展开', () => {
    const response = { config: makeConfig(), data: { code: 200, data: null } }
    const result = handlers.response(response)
    expect(result).toBe(response)
    expect(response.data).toEqual({ code: 200, data: null })
  })

  it('展开对象 payload 到顶层', () => {
    const response = { config: makeConfig(), data: { code: 200, data: { name: 'test', value: 42 } } }
    handlers.response(response)
    expect(response.data.name).toBe('test')
    expect(response.data.value).toBe(42)
  })

  it('展开时不覆盖已有顶层键（code/message/data 元数据保护）', () => {
    const response = {
      config: makeConfig(),
      data: { code: 200, message: 'ok', data: { code: 999, extra: 1 } },
    }
    handlers.response(response)
    expect(response.data.code).toBe(200)
    expect(response.data.message).toBe('ok')
    expect((response.data as any).extra).toBe(1)
  })

  it('数组 payload 设为 items', () => {
    const response = { config: makeConfig(), data: { code: 200, data: [{ id: 1 }, { id: 2 }] } }
    handlers.response(response)
    expect(response.data.items).toEqual([{ id: 1 }, { id: 2 }])
  })

  it('数组 payload 不覆盖已有 items', () => {
    const response = { config: makeConfig(), data: { code: 200, data: [1, 2], items: [9] } }
    handlers.response(response)
    expect(response.data.items).toEqual([9])
  })

  it('items 非数组时安全化为 [] 并告警', () => {
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const response = { config: makeConfig(), data: { code: 200, items: 'oops' } }
    handlers.response(response)
    expect(response.data.items).toEqual([])
    expect(warnSpy).toHaveBeenCalled()
    warnSpy.mockRestore()
  })

  it('items 已是数组时不告警不改动', () => {
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const response = { config: makeConfig(), data: { code: 200, items: [1, 2] } }
    handlers.response(response)
    expect(response.data.items).toEqual([1, 2])
    expect(warnSpy).not.toHaveBeenCalled()
    warnSpy.mockRestore()
  })

  it('total 非数字时回退为 items.length', () => {
    const response = { config: makeConfig(), data: { code: 200, items: [1, 2, 3], total: 'many' } }
    handlers.response(response)
    expect(response.data.total).toBe(3)
  })

  it('total 为数字时保持不变', () => {
    const response = { config: makeConfig(), data: { code: 200, items: [1], total: 7 } }
    handlers.response(response)
    expect(response.data.total).toBe(7)
  })
})

describe('api/request — response 错误拦截器', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    authState.token = 'test-jwt-token'
    authState.refreshToken = ''
    offlineState.offline = false
    capturedCancels.length = 0
    _setCachedToken(null)
    unfreezeRequests()
    cancelAllRequests()
  })

  it('已取消请求直接拒绝不处理', async () => {
    const error = { __CANCEL__: true }
    await expect(handlers.responseR(error)).rejects.toBe(error)
  })

  it('ERR_CANCELED 直接拒绝不处理', async () => {
    const error = { code: 'ERR_CANCELED' }
    await expect(handlers.responseR(error)).rejects.toBe(error)
  })

  it('失败请求清理 pending 追踪', async () => {
    const config = makeConfig({ method: 'GET', url: '/pending' })
    await handlers.request(config)
    expect(getPendingRequestCount()).toBe(1)
    const error = { response: { status: 400, data: {} }, config }
    await expect(handlers.responseR(error)).rejects.toBe(error)
    expect(getPendingRequestCount()).toBe(0)
  })

  it('400 带 detail → 挂载 detail', async () => {
    const error = { response: { status: 400, data: { detail: '参数错误' } }, config: makeConfig() }
    await expect(handlers.responseR(error)).rejects.toBe(error)
    expect(error.userMessage).toBe('参数错误')
    expect(mockElMessage.warning).not.toHaveBeenCalled()
  })

  it('400 无 detail 但带 message → 挂载 message', async () => {
    const error = { response: { status: 400, data: { message: '请求被拒绝' } }, config: makeConfig() }
    await expect(handlers.responseR(error)).rejects.toBe(error)
    expect(error.userMessage).toBe('请求被拒绝')
    expect(mockElMessage.warning).not.toHaveBeenCalled()
  })

  it('400 detail 为对象 → 挂载通用请求失败消息', async () => {
    const error = { response: { status: 400, data: { detail: { field: 'x' } } }, config: makeConfig() }
    await expect(handlers.responseR(error)).rejects.toBe(error)
    expect(error.userMessage).toBe('请求失败 (400)')
    expect(mockElMessage.warning).not.toHaveBeenCalled()
  })

  it('400 无任何信息 → 挂载通用请求失败消息', async () => {
    const error = { response: { status: 400, data: {} }, config: makeConfig() }
    await expect(handlers.responseR(error)).rejects.toBe(error)
    expect(error.userMessage).toBe('请求失败 (400)')
    expect(mockElMessage.warning).not.toHaveBeenCalled()
  })

  it('403 + CSRF 信息 → 自动重试一次并重发原请求', async () => {
    mockInst.request.mockResolvedValueOnce('retried')
    const config = makeConfig({ method: 'POST', url: '/secure' })
    const error = { response: { status: 403, data: { detail: 'CSRF token missing' } }, config }
    const result = await handlers.responseR(error)
    expect(result).toBe('retried')
    expect((config as any)._csrfRetried).toBe(true)
    expect(mockInst.request).toHaveBeenCalledWith(config)
  })

  it('403 + CSRF 重试时回填新 token（cookie 可用）', async () => {
    document.cookie = 'csrftoken=csrf-retry; path=/'
    mockInst.request.mockResolvedValueOnce('retried-2')
    const config = makeConfig({ method: 'POST', url: '/secure2' })
    const error = { response: { status: 403, data: { detail: 'csrf failed' } }, config }
    const result = await handlers.responseR(error)
    expect(result).toBe('retried-2')
    expect(config.headers['X-CSRF-Token']).toBe('csrf-retry')
  })

  it('403 + CSRF 已重试过 → 挂载安全校验过期消息', async () => {
    const config = makeConfig({ method: 'POST', url: '/secure3', _csrfRetried: true })
    const error = { response: { status: 403, data: { detail: 'csrf invalid' } }, config }
    await expect(handlers.responseR(error)).rejects.toBe(error)
    expect(error.userMessage).toBe('安全校验已过期，请重试（CSRF）')
    expect(mockElMessage.error).not.toHaveBeenCalled()
  })

  it('403 非 CSRF → 显示服务端 detail', async () => {
    const error = { response: { status: 403, data: { detail: '无操作权限' } }, config: makeConfig() }
    await expect(handlers.responseR(error)).rejects.toBe(error)
    expect(error.userMessage).toBe('无操作权限')
    expect(mockElMessage.error).not.toHaveBeenCalled()
  })

  it('403 非 CSRF 且无 detail → 默认权限提示', async () => {
    const error = { response: { status: 403, data: {} }, config: makeConfig() }
    await expect(handlers.responseR(error)).rejects.toBe(error)
    expect(error.userMessage).toBe('权限不足，无法执行此操作')
    expect(mockElMessage.error).not.toHaveBeenCalled()
  })

  it('404 → 挂载资源不存在消息（无 URL 拼接）', async () => {
    const error = { response: { status: 404, data: {} }, config: makeConfig({ url: '/missing' }) }
    await expect(handlers.responseR(error)).rejects.toBe(error)
    expect(error.userMessage).toBe('请求的资源不存在')
    expect(mockElMessage.warning).not.toHaveBeenCalled()
  })

  it('404 无 config → 挂载资源不存在消息', async () => {
    const error = { response: { status: 404, data: {} } }
    await expect(handlers.responseR(error)).rejects.toBe(error)
    expect(error.userMessage).toBe('请求的资源不存在')
    expect(mockElMessage.warning).not.toHaveBeenCalled()
  })

  it('404 带 detail → 挂载 detail', async () => {
    const error = { response: { status: 404, data: { detail: '记录已删除' } }, config: makeConfig() }
    await expect(handlers.responseR(error)).rejects.toBe(error)
    expect(error.userMessage).toBe('记录已删除')
    expect(mockElMessage.warning).not.toHaveBeenCalled()
  })

  it('404 带 message → 挂载 message', async () => {
    const error = { response: { status: 404, data: { message: '资源被移除' } }, config: makeConfig() }
    await expect(handlers.responseR(error)).rejects.toBe(error)
    expect(error.userMessage).toBe('资源被移除')
    expect(mockElMessage.warning).not.toHaveBeenCalled()
  })

  it('500 → 挂载服务器错误消息', async () => {
    const error = { response: { status: 500, data: {} }, config: makeConfig() }
    await expect(handlers.responseR(error)).rejects.toBe(error)
    expect(error.userMessage).toBe('服务器错误，请稍后重试')
    expect(mockElMessage.error).not.toHaveBeenCalled()
  })

  it('503 → 挂载服务器错误消息', async () => {
    const error = { response: { status: 503, data: {} }, config: makeConfig() }
    await expect(handlers.responseR(error)).rejects.toBe(error)
    expect(error.userMessage).toBe('服务器错误，请稍后重试')
    expect(mockElMessage.error).not.toHaveBeenCalled()
  })

  it('422 数组 detail → 提取首条字段错误', async () => {
    const error = {
      response: { status: 422, data: { detail: [{ loc: ['body', 'name'], msg: '必填' }] } },
      config: makeConfig(),
    }
    await expect(handlers.responseR(error)).rejects.toBe(error)
    expect(error.userMessage).toBe('body.name: 必填')
    expect(mockElMessage.warning).not.toHaveBeenCalled()
  })

  it('422 字符串 detail → 挂载 detail', async () => {
    const error = {
      response: { status: 422, data: { detail: '数据格式错误' } },
      config: makeConfig(),
    }
    await expect(handlers.responseR(error)).rejects.toBe(error)
    expect(error.userMessage).toBe('数据格式错误')
    expect(mockElMessage.warning).not.toHaveBeenCalled()
  })

  it('422 无 detail → 默认校验失败提示', async () => {
    const error = { response: { status: 422, data: {} }, config: makeConfig() }
    await expect(handlers.responseR(error)).rejects.toBe(error)
    expect(error.userMessage).toBe('输入数据校验失败')
    expect(mockElMessage.warning).not.toHaveBeenCalled()
  })

  it('422 detail 为空数组 → 默认校验失败提示', async () => {
    const error = { response: { status: 422, data: { detail: [] } }, config: makeConfig() }
    await expect(handlers.responseR(error)).rejects.toBe(error)
    expect(error.userMessage).toBe('输入数据校验失败')
    expect(mockElMessage.warning).not.toHaveBeenCalled()
  })

  it('422 detail 首条无 loc → 仅展示 msg', async () => {
    const error = {
      response: { status: 422, data: { detail: [{ msg: '必填' }] } },
      config: makeConfig(),
    }
    await expect(handlers.responseR(error)).rejects.toBe(error)
    expect(error.userMessage).toBe(': 必填')
    expect(mockElMessage.warning).not.toHaveBeenCalled()
  })

  it('422 detail 首条无 msg 但含 message → 展示 message', async () => {
    const error = {
      response: { status: 422, data: { detail: [{ loc: ['name'], message: '非法值' }] } },
      config: makeConfig(),
    }
    await expect(handlers.responseR(error)).rejects.toBe(error)
    expect(error.userMessage).toBe('name: 非法值')
    expect(mockElMessage.warning).not.toHaveBeenCalled()
  })

  it('网络错误且无离线 mock → 挂载网络失败消息', async () => {
    const error = { code: 'ERR_NETWORK', message: 'NetworkError', config: makeConfig() }
    await expect(handlers.responseR(error)).rejects.toBe(error)
    expect(error.userMessage).toBe('网络连接失败，请检查服务是否启动')
    expect(mockElMessage.error).not.toHaveBeenCalled()
  })

  it('离线模式命中 mock → 返回 mock 数据', async () => {
    offlineState.offline = true
    const mockData = { data: { offline: true } }
    mockGetMockResponse.mockReturnValueOnce(mockData)
    const error = {
      code: 'ERR_NETWORK',
      message: 'NetworkError',
      config: makeConfig({ method: 'GET', url: '/offline-data' }),
    }
    const result = await handlers.responseR(error)
    expect(result).toBe(mockData)
  })

  it('离线模式命中 mock 且 config 无 method/url → 使用 GET 兜底', async () => {
    offlineState.offline = true
    const mockData = { data: { offline: true } }
    mockGetMockResponse.mockReturnValueOnce(mockData)
    const error = { code: 'ERR_NETWORK', message: 'NetworkError', config: {} }
    const result = await handlers.responseR(error)
    expect(result).toBe(mockData)
    expect(mockGetMockResponse).toHaveBeenCalledWith('GET', '')
  })

  it('离线模式未命中 mock → 挂载网络失败消息', async () => {
    offlineState.offline = true
    mockGetMockResponse.mockReturnValueOnce(null)
    const error = { code: 'ERR_NETWORK', message: 'NetworkError', config: makeConfig() }
    await expect(handlers.responseR(error)).rejects.toBe(error)
    expect(error.userMessage).toBe('网络连接失败，请检查服务是否启动')
    expect(mockElMessage.error).not.toHaveBeenCalled()
  })

  it('超时错误 → 挂载超时消息', async () => {
    const error = { code: 'ECONNABORTED', message: 'timeout', config: makeConfig() }
    await expect(handlers.responseR(error)).rejects.toBe(error)
    expect(error.userMessage).toBe('请求超时，请重试')
    expect(mockElMessage.warning).not.toHaveBeenCalled()
  })

  it('未知错误 → console.error 记录', async () => {
    const errSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    const error = { message: 'something weird' }
    await expect(handlers.responseR(error)).rejects.toBe(error)
    expect(errSpy).toHaveBeenCalled()
    errSpy.mockRestore()
  })

  it('未知错误无 message → 记录 error 对象', async () => {
    const errSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    const error = { code: 'WHATEVER' }
    await expect(handlers.responseR(error)).rejects.toBe(error)
    expect(errSpy).toHaveBeenCalled()
    errSpy.mockRestore()
  })
})

describe('api/request — 401 与 refresh 续期', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    authState.token = 'test-jwt-token'
    authState.refreshToken = ''
    offlineState.offline = false
    capturedCancels.length = 0
    _setCachedToken(null)
    unfreezeRequests()
    cancelAllRequests()
  })

  it('401 无 config → 清除认证并提示重新登录', async () => {
    const error = { response: { status: 401, data: {} } }
    await expect(handlers.responseR(error)).rejects.toBe(error)
    expect(mockAuthStorage.clear).toHaveBeenCalled()
    expect(mockElMessage.error).toHaveBeenCalledWith('登录已过期，请重新登录')
    expect(mockAxiosPost).not.toHaveBeenCalled()
  })

  it('401 config.url 为 undefined → _isAuthEndpoint 短路分支 + 登出', async () => {
    const error = {
      response: { status: 401, data: {} },
      config: makeConfig({ url: undefined }),
    }
    await expect(handlers.responseR(error)).rejects.toBe(error)
    expect(mockAuthStorage.clear).toHaveBeenCalled()
    expect(mockElMessage.error).toHaveBeenCalledWith('登录已过期，请重新登录')
  })

  it('401 登录端点 → 不触发 refresh（防无限循环）', async () => {
    authState.refreshToken = 'refresh-1'
    const error = { response: { status: 401, data: {} }, config: makeConfig({ url: '/auth/login' }) }
    await expect(handlers.responseR(error)).rejects.toBe(error)
    expect(mockAuthStorage.clear).toHaveBeenCalled()
    expect(mockAxiosPost).not.toHaveBeenCalled()
  })

  it('401 refresh 端点 → 不触发 refresh', async () => {
    authState.refreshToken = 'refresh-1'
    const error = { response: { status: 401, data: {} }, config: makeConfig({ url: '/auth/refresh' }) }
    await expect(handlers.responseR(error)).rejects.toBe(error)
    expect(mockAxiosPost).not.toHaveBeenCalled()
  })

  it('401 2FA 验证端点 → 不触发 refresh', async () => {
    authState.refreshToken = 'refresh-1'
    const error = {
      response: { status: 401, data: {} },
      config: makeConfig({ url: '/auth/two-factor/verify-login' }),
    }
    await expect(handlers.responseR(error)).rejects.toBe(error)
    expect(mockAxiosPost).not.toHaveBeenCalled()
  })

  it('401 非登录端点 → 走 refresh 流程', async () => {
    authState.refreshToken = 'refresh-1'
    mockAxiosPost.mockResolvedValueOnce({
      data: { data: { access_token: 'new-access' }, refresh_token: 'new-refresh' },
    })
    mockInst.request.mockResolvedValueOnce('retry-ok')
    const originalRequest = makeConfig({ url: '/data' })
    const error = { response: { status: 401, data: {} }, config: originalRequest }
    const result = await handlers.responseR(error)
    expect(result).toBe('retry-ok')
    expect(mockAxiosPost).toHaveBeenCalledWith(
      '/api/v1/auth/refresh',
      { token: 'refresh-1' },
      expect.objectContaining({ withCredentials: true })
    )
    expect(mockAuthStorage.setToken).toHaveBeenCalledWith('new-access')
    expect(mockAuthStorage.setRefreshToken).toHaveBeenCalledWith('new-refresh')
    expect(originalRequest.headers.Authorization).toBe('Bearer new-access')
    expect(mockInst.request).toHaveBeenCalledWith(originalRequest)
  })

  it('401 refresh 响应无 refresh_token → 仅更新 access_token', async () => {
    authState.refreshToken = 'refresh-1'
    mockAxiosPost.mockResolvedValueOnce({ data: { data: { access_token: 'tok-only' } } })
    mockInst.request.mockResolvedValueOnce('ok')
    const error = { response: { status: 401, data: {} }, config: makeConfig({ url: '/data2' }) }
    await expect(handlers.responseR(error)).resolves.toBe('ok')
    expect(mockAuthStorage.setRefreshToken).not.toHaveBeenCalled()
  })

  it('401 无 refresh_token → 清除认证并提示重新登录', async () => {
    const error = { response: { status: 401, data: {} }, config: makeConfig({ url: '/data3' }) }
    await expect(handlers.responseR(error)).rejects.toBe(error)
    expect(mockAuthStorage.clear).toHaveBeenCalled()
    expect(mockElMessage.error).toHaveBeenCalledWith('登录已过期，请重新登录')
    expect(mockAxiosPost).not.toHaveBeenCalled()
  })

  it('401 refresh 响应缺 access_token → 失败路径清除认证', async () => {
    authState.refreshToken = 'refresh-1'
    mockAxiosPost.mockResolvedValueOnce({ data: {} })
    const error = { response: { status: 401, data: {} }, config: makeConfig({ url: '/data4' }) }
    await expect(handlers.responseR(error)).rejects.toThrow('Refresh response missing access_token')
    expect(mockAuthStorage.clear).toHaveBeenCalled()
    expect(mockElMessage.error).toHaveBeenCalledWith('登录已过期，请重新登录')
  })

  it('401 refresh 期间后续 401 排队，成功后统一用新 token 重发', async () => {
    authState.refreshToken = 'refresh-1'
    let resolveRefresh: any
    mockAxiosPost.mockReturnValueOnce(
      new Promise((res) => {
        resolveRefresh = res
      })
    )
    mockInst.request.mockResolvedValue('ok')
    const errorA = { response: { status: 401, data: {} }, config: makeConfig({ url: '/a' }) }
    const p1 = handlers.responseR(errorA)
    const errorB = { response: { status: 401, data: {} }, config: makeConfig({ url: '/b' }) }
    const p2 = handlers.responseR(errorB)
    // 拦截器在发起 refresh 前会先 await _ensureCsrfToken()，需冲刷微任务后断言
    await new Promise((r) => setTimeout(r, 0))
    expect(mockAxiosPost).toHaveBeenCalledTimes(1)
    resolveRefresh({ data: { data: { access_token: 'T2' } } })
    await expect(p1).resolves.toBe('ok')
    await expect(p2).resolves.toBe('ok')
    expect(errorA.config.headers.Authorization).toBe('Bearer T2')
    expect(errorB.config.headers.Authorization).toBe('Bearer T2')
    expect(mockInst.request).toHaveBeenCalledTimes(2)
  })

  it('401 refresh 失败 → 当前请求与排队请求一并拒绝', async () => {
    authState.refreshToken = 'refresh-1'
    let rejectRefresh: any
    mockAxiosPost.mockReturnValueOnce(
      new Promise((_, rej) => {
        rejectRefresh = rej
      })
    )
    const errorA = { response: { status: 401, data: {} }, config: makeConfig({ url: '/c' }) }
    const p1 = handlers.responseR(errorA)
    const errorB = { response: { status: 401, data: {} }, config: makeConfig({ url: '/d' }) }
    const p2 = handlers.responseR(errorB)
    // 拦截器在发起 refresh 前会先 await _ensureCsrfToken()，需冲刷微任务后断言
    await new Promise((r) => setTimeout(r, 0))
    expect(mockAxiosPost).toHaveBeenCalledTimes(1)
    rejectRefresh(new Error('refresh boom'))
    await expect(p1).rejects.toThrow('refresh boom')
    await expect(p2).rejects.toThrow('refresh boom')
    expect(mockAuthStorage.clear).toHaveBeenCalled()
    expect(mockElMessage.error).toHaveBeenCalledWith('登录已过期，请重新登录')
  })
})

describe('api/request — 封装方法参数透传', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    _setCachedToken(null)
    unfreezeRequests()
    cancelAllRequests()
  })

  it('apiRequest 透传 config 并返回 res.data', async () => {
    const body = { items: [1, 2] }
    mockInst.request.mockResolvedValueOnce({ data: body })
    const config = { method: 'GET', url: '/anything' }
    const result = await apiRequest(config)
    expect(mockInst.request).toHaveBeenCalledWith(config)
    expect(result).toBe(body)
  })

  it('get(url, params) → GET + params，返回已解包 body', async () => {
    mockInst.request.mockResolvedValueOnce({ data: ['a'] })
    const result = await get('/list', { page: 1 })
    expect(mockInst.request).toHaveBeenCalledWith({ method: 'GET', url: '/list', params: { page: 1 } })
    expect(result).toEqual(['a'])
  })

  it('get(url) 无参数时 params 为 undefined', async () => {
    mockInst.request.mockResolvedValueOnce({ data: {} })
    await get('/list')
    expect(mockInst.request).toHaveBeenCalledWith({ method: 'GET', url: '/list', params: undefined })
  })

  it('post(url, data) → POST + data', async () => {
    mockInst.request.mockResolvedValueOnce({ data: { id: 1 } })
    const result = await post('/items', { name: 'n' })
    expect(mockInst.request).toHaveBeenCalledWith({ method: 'POST', url: '/items', data: { name: 'n' } })
    expect(result).toEqual({ id: 1 })
  })

  it('post(url, data, extra) 合并 extra 配置', async () => {
    mockInst.request.mockResolvedValueOnce({ data: {} })
    await post('/items', { a: 1 }, { timeout: 5000, headers: { 'X-Custom': 'v' } })
    expect(mockInst.request).toHaveBeenCalledWith({
      method: 'POST',
      url: '/items',
      data: { a: 1 },
      timeout: 5000,
      headers: { 'X-Custom': 'v' },
    })
  })

  it('post FormData 时移除 Content-Type（保留其他 headers）', async () => {
    mockInst.request.mockResolvedValueOnce({ data: {} })
    const fd = new FormData()
    fd.append('file', new File(['x'], 'a.xlsx'))
    await post('/upload', fd, {
      headers: { 'Content-Type': 'multipart/form-data', 'X-Keep': 'yes' },
    })
    const config = mockInst.request.mock.calls[0][0]
    expect(config.data).toBe(fd)
    expect(config.headers['Content-Type']).toBeUndefined()
    expect(config.headers['content-type']).toBeUndefined()
    expect(config.headers['X-Keep']).toBe('yes')
  })

  it('post FormData 时设置 transformRequest：透传 FormData 并清除 Content-Type（防 JSON 序列化 422）', async () => {
    mockInst.request.mockResolvedValueOnce({ data: {} })
    const fd = new FormData()
    fd.append('file', new File(['x'], 'a.xlsx'))
    await post('/upload', fd)
    const config = mockInst.request.mock.calls[0][0]
    expect(Array.isArray(config.transformRequest)).toBe(true)
    // FormData 分支：清除 Content-Type（让浏览器自动 multipart boundary）并原样返回
    const headers = { setContentType: vi.fn() }
    const out = config.transformRequest[0](fd, headers)
    expect(out).toBe(fd)
    expect(headers.setContentType).toHaveBeenCalledWith(undefined)
    // 非 FormData 分支：原样返回
    const plain = { a: 1 }
    expect(config.transformRequest[0](plain, headers)).toBe(plain)
    expect(headers.setContentType).toHaveBeenCalledTimes(1)
  })

  it('post FormData 无 extra headers 时跳过 Content-Type 清理', async () => {
    mockInst.request.mockResolvedValueOnce({ data: {} })
    const fd = new FormData()
    await post('/upload2', fd)
    const config = mockInst.request.mock.calls[0][0]
    expect(config.data).toBe(fd)
    // 新行为：FormData 时始终构造 headers 对象并移除 Content-Type（防止 axios JSON 序列化 multipart）
    expect(config.headers).toEqual({})
  })

  it('post 非 FormData 数据时保留 headers', async () => {
    mockInst.request.mockResolvedValueOnce({ data: {} })
    await post('/items2', { json: true }, { headers: { 'Content-Type': 'application/json' } })
    const config = mockInst.request.mock.calls[0][0]
    expect(config.headers['Content-Type']).toBe('application/json')
  })

  it('put(url, data) → PUT + data', async () => {
    mockInst.request.mockResolvedValueOnce({ data: { ok: true } })
    const result = await put('/items/1', { name: 'n2' })
    expect(mockInst.request).toHaveBeenCalledWith({ method: 'PUT', url: '/items/1', data: { name: 'n2' } })
    expect(result).toEqual({ ok: true })
  })

  it('del(url) → DELETE', async () => {
    mockInst.request.mockResolvedValueOnce({ data: { deleted: true } })
    const result = await del('/items/1')
    expect(mockInst.request).toHaveBeenCalledWith({ method: 'DELETE', url: '/items/1' })
    expect(result).toEqual({ deleted: true })
  })

  it('patch(url, data) → PATCH + data', async () => {
    mockInst.request.mockResolvedValueOnce({ data: { patched: true } })
    const result = await patch('/items/1', { flag: 1 })
    expect(mockInst.request).toHaveBeenCalledWith({ method: 'PATCH', url: '/items/1', data: { flag: 1 } })
    expect(result).toEqual({ patched: true })
  })

  it('createCancelableRequest 返回 promise 与 cancel，并带上 cancelToken', async () => {
    mockInst.request.mockResolvedValueOnce({ data: 'done' })
    const { promise, cancel } = createCancelableRequest({ method: 'GET', url: '/c' })
    expect(mockCancelSource).toHaveBeenCalled()
    expect(mockInst.request).toHaveBeenCalledWith({
      method: 'GET',
      url: '/c',
      cancelToken: 'mock-cancel-token',
    })
    expect(cancel).toBe(mockCancel)
    await expect(promise).resolves.toBe('done')
  })

  it('requestWithTimeout 在超时内完成则正常返回', async () => {
    mockInst.request.mockResolvedValueOnce({ data: 'fast' })
    const result = await requestWithTimeout({ method: 'GET', url: '/t' }, 5000)
    expect(result).toBe('fast')
  })

  it('requestWithTimeout 超时后取消请求并拒绝', async () => {
    vi.useFakeTimers()
    try {
      mockInst.request.mockReturnValueOnce(new Promise(() => {}))
      const promise = requestWithTimeout({ method: 'GET', url: '/slow' }, 1000)
      const assertion = expect(promise).rejects.toThrow('Request timeout after 1000ms')
      await vi.advanceTimersByTimeAsync(1000)
      await assertion
      expect(mockCancel).toHaveBeenCalled()
    } finally {
      vi.useRealTimers()
    }
  })
})

describe('api/request — parseContentDisposition', () => {
  it('无 headers 返回 fallback', () => {
    expect(parseContentDisposition(undefined)).toBe('download.xlsx')
    expect(parseContentDisposition(undefined, 'a.csv')).toBe('a.csv')
  })

  it('无 content-disposition 返回 fallback', () => {
    expect(parseContentDisposition({ 'content-type': 'text/plain' })).toBe('download.xlsx')
  })

  it('解析 RFC 5987 filename*（小写头）', () => {
    const encoded = encodeURIComponent('帮扶村.xlsx')
    const headers = { 'content-disposition': `attachment; filename*=UTF-8''${encoded}` }
    expect(parseContentDisposition(headers)).toBe('帮扶村.xlsx')
  })

  it('解析 RFC 5987 filename*（大写头键）', () => {
    const encoded = encodeURIComponent('学校名单.xlsx')
    const headers = { 'Content-Disposition': `attachment; filename*=UTF-8''${encoded}` }
    expect(parseContentDisposition(headers)).toBe('学校名单.xlsx')
  })

  it('回退解析 filename="quoted"', () => {
    const headers = { 'content-disposition': 'attachment; filename="report.xlsx"' }
    expect(parseContentDisposition(headers)).toBe('report.xlsx')
  })

  it('回退解析 filename=plain（无引号）', () => {
    const headers = { 'content-disposition': 'attachment; filename=data.csv' }
    expect(parseContentDisposition(headers)).toBe('data.csv')
  })

  it('filename* 解码失败时回退 filename= 或 fallback', () => {
    const headers = {
      'content-disposition': 'attachment; filename*=UTF-8\'\'%E4%B8%AD%ZZ; filename="safe.xlsx"',
    }
    expect(parseContentDisposition(headers)).toBe('safe.xlsx')
  })

  it('filename* 解码结果为空时回退', () => {
    const headers = { 'content-disposition': 'attachment; filename*=UTF-8\'\'' }
    const result = parseContentDisposition(headers, 'fb.bin')
    expect(typeof result).toBe('string')
    expect(result.length).toBeGreaterThan(0)
  })

  it('全部解析失败返回 fallback', () => {
    const headers = { 'content-disposition': 'attachment' }
    expect(parseContentDisposition(headers, 'fb.bin')).toBe('fb.bin')
  })
})

describe('api/request — downloadBlob', () => {
  afterEach(() => {
    vi.restoreAllMocks()
    vi.useRealTimers()
  })

  it('创建 a 标签触发点击下载并释放 objectURL', () => {
    vi.useFakeTimers()
    const createObjectURL = vi.fn(() => 'blob:mock-url')
    const revokeObjectURL = vi.fn()
    ;(window.URL as any).createObjectURL = createObjectURL
    ;(window.URL as any).revokeObjectURL = revokeObjectURL

    const link = document.createElement('a')
    link.click = vi.fn()
    const realCreate = document.createElement.bind(document)
    vi.spyOn(document, 'createElement').mockImplementation((tag: any) =>
      tag === 'a' ? link : realCreate(tag)
    )

    const blob = new Blob(['x'])
    downloadBlob(blob, '导出.xlsx')

    expect(createObjectURL).toHaveBeenCalledWith(blob)
    expect(link.href).toBe('blob:mock-url')
    expect(link.download).toBe('导出.xlsx')
    expect(link.style.display).toBe('none')
    expect(link.click).toHaveBeenCalled()

    vi.advanceTimersByTime(150)
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:mock-url')
    expect(document.body.contains(link)).toBe(false)
  })
})

describe('api/request — cancelRequest 精确匹配', () => {
  it('取消匹配 URL 段的挂起请求', async () => {
    await handlers.request(makeConfig({ method: 'GET', url: '/dupx' }))
    expect(getPendingRequestCount()).toBe(1)
    cancelRequest('/dupx')
    expect(getPendingRequestCount()).toBe(0)
    expect(capturedCancels[0]).toHaveBeenCalled()
  })

  it('cancelRequest 不匹配无关 URL', async () => {
    await handlers.request(makeConfig({ method: 'GET', url: '/other' }))
    cancelRequest('/dupx')
    expect(getPendingRequestCount()).toBe(1)
    cancelAllRequests()
    expect(getPendingRequestCount()).toBe(0)
  })

  it('cancelAllRequests 清空全部挂起请求（W3-T4：仅 GET 入池）', async () => {
    await handlers.request(makeConfig({ method: 'GET', url: '/x1' }))
    await handlers.request(makeConfig({ method: 'GET', url: '/x2' }))
    // POST 不再参与去重池（防并发写操作被静默取消）
    await handlers.request(makeConfig({ method: 'POST', url: '/x3' }))
    expect(getPendingRequestCount()).toBe(2)
    cancelAllRequests()
    expect(getPendingRequestCount()).toBe(0)
    expect(capturedCancels[0]).toHaveBeenCalled()
    expect(capturedCancels[1]).toHaveBeenCalled()
  })
})

// ── MODE=development：测试环境守卫分支（CSRF 懒加载、网络重试、401 跳转）──
// 测试环境（MODE=test）中 _isTestEnv 恒为 true，以下分支结构上不可达；
// 通过 vi.stubEnv + resetModules + 动态导入得到 _isTestEnv=false 的新模块实例来覆盖。
describe('api/request — MODE=development 分支', () => {
  beforeEach(() => {
    vi.resetModules()
    vi.stubEnv('MODE', 'development')
    // 上一测试的 mock 调用与 once 实现会跨测试累积，这里整体清空
    vi.clearAllMocks()
    mockAxiosGet.mockReset()
    mockInst.request.mockReset()
    authState.token = ''
    authState.refreshToken = ''
    offlineState.offline = false
    capturedCancels.length = 0
    document.cookie = 'csrftoken='
  })

  afterEach(() => {
    vi.unstubAllEnvs()
    vi.unstubAllGlobals()
    vi.useRealTimers()
  })

  it('prefetchCsrfToken 懒加载：data.data.csrf_token 优先', async () => {
    mockAxiosGet.mockResolvedValueOnce({ data: { data: { csrf_token: 'tok1' } } })
    const m = await import('@/api/request')
    const r = await m.prefetchCsrfToken()
    expect(r).toBe('tok1')
    expect(mockAxiosGet).toHaveBeenCalledWith('/api/v1/auth/csrf-token', { withCredentials: true })
  })

  it('prefetchCsrfToken 懒加载：data.csrf_token 兜底', async () => {
    mockAxiosGet.mockResolvedValueOnce({ data: { data: {}, csrf_token: 'flat-tok' } })
    const m = await import('@/api/request')
    expect(await m.prefetchCsrfToken()).toBe('flat-tok')
  })

  it('prefetchCsrfToken 懒加载：cookie 兜底', async () => {
    document.cookie = 'csrftoken=cookie-tok; path=/'
    mockAxiosGet.mockResolvedValueOnce({ data: {} })
    const m = await import('@/api/request')
    expect(await m.prefetchCsrfToken()).toBe('cookie-tok')
  })

  it('prefetchCsrfToken 懒加载失败返回 null（不阻断）', async () => {
    mockAxiosGet.mockRejectedValueOnce(new Error('csrf fetch fail'))
    const m = await import('@/api/request')
    expect(await m.prefetchCsrfToken()).toBeNull()
  })

  it('prefetchCsrfToken 懒加载响应无任何 token → 兜底读 cookie 后返回 null', async () => {
    mockAxiosGet.mockResolvedValueOnce({ data: {} })
    const m = await import('@/api/request')
    expect(await m.prefetchCsrfToken()).toBeNull()
  })

  it('缓存的 CSRF token 直接复用，不再发起网络请求', async () => {
    mockAxiosGet.mockResolvedValueOnce({ data: { data: { csrf_token: 'cached-tok' } } })
    await import('@/api/request')
    await handlers.request(makeConfig({ method: 'POST', url: '/first' }))
    const config2 = makeConfig({ method: 'POST', url: '/second' })
    await handlers.request(config2)
    expect(config2.headers['X-CSRF-Token']).toBe('cached-tok')
    expect(mockAxiosGet).toHaveBeenCalledTimes(1)
  })

  it('prefetchCsrfToken 并发去重：仅发起一次网络请求', async () => {
    let resolveFetch: any
    mockAxiosGet.mockReturnValueOnce(
      new Promise((res) => {
        resolveFetch = res
      })
    )
    const m = await import('@/api/request')
    const p1 = m.prefetchCsrfToken()
    const p2 = m.prefetchCsrfToken()
    expect(mockAxiosGet).toHaveBeenCalledTimes(1)
    resolveFetch({ data: { data: { csrf_token: 'dedup-tok' } } })
    await expect(p1).resolves.toBe('dedup-tok')
    await expect(p2).resolves.toBe('dedup-tok')
  })

  it('prefetchCsrfToken 使用 VITE_API_BASE_URL 拼接端点', async () => {
    vi.stubEnv('VITE_API_BASE_URL', 'http://backend:8000/api')
    mockAxiosGet.mockResolvedValueOnce({ data: { data: { csrf_token: 't' } } })
    const m = await import('@/api/request')
    await m.prefetchCsrfToken()
    expect(mockAxiosGet).toHaveBeenCalledWith('http://backend:8000/api/auth/csrf-token', {
      withCredentials: true,
    })
  })

  it('request 拦截器：POST 不安全方法自动回填懒加载的 CSRF token', async () => {
    mockAxiosGet.mockResolvedValueOnce({ data: { data: { csrf_token: 'hdr-tok' } } })
    await import('@/api/request')
    const config = { method: 'POST', url: '/unsafe-dev', headers: {} }
    await handlers.request(config)
    expect(config.headers['X-CSRF-Token']).toBe('hdr-tok')
  })

  it('401 非登录页 → 跳转 /login', async () => {
    const location: any = { pathname: '/workbench', href: '' }
    vi.stubGlobal('location', location)
    await import('@/api/request')
    const error = { response: { status: 401, data: {} }, config: makeConfig({ url: '/data' }) }
    await expect(handlers.responseR(error)).rejects.toBe(error)
    expect(location.href).toBe('/login')
  })

  it('401 已在登录页 → 不跳转', async () => {
    const location: any = { pathname: '/login', href: '' }
    vi.stubGlobal('location', location)
    await import('@/api/request')
    const error = { response: { status: 401, data: {} }, config: makeConfig({ url: '/data' }) }
    await expect(handlers.responseR(error)).rejects.toBe(error)
    expect(location.href).toBe('')
  })

  it('401 config.url 为 undefined → _isAuthEndpoint 短路 + 跳转登录页', async () => {
    const location: any = { pathname: '/workbench', href: '' }
    vi.stubGlobal('location', location)
    await import('@/api/request')
    const error = {
      response: { status: 401, data: {} },
      config: makeConfig({ url: undefined }),
    }
    await expect(handlers.responseR(error)).rejects.toBe(error)
    expect(location.href).toBe('/login')
  })

  it('401 登录端点（有 refresh_token）→ 不 refresh 直接登出并跳转', async () => {
    const location: any = { pathname: '/workbench', href: '' }
    vi.stubGlobal('location', location)
    authState.refreshToken = 'refresh-1'
    await import('@/api/request')
    const error = { response: { status: 401, data: {} }, config: makeConfig({ url: '/auth/login' }) }
    await expect(handlers.responseR(error)).rejects.toBe(error)
    expect(mockAxiosPost).not.toHaveBeenCalled()
    expect(mockAuthStorage.clear).toHaveBeenCalled()
    expect(location.href).toBe('/login')
  })

  it('401 refresh 失败 → 清除认证并跳转登录页', async () => {
    const location: any = { pathname: '/workbench', href: '' }
    vi.stubGlobal('location', location)
    authState.refreshToken = 'refresh-1'
    mockAxiosPost.mockRejectedValueOnce(new Error('refresh down'))
    await import('@/api/request')
    const error = { response: { status: 401, data: {} }, config: makeConfig({ url: '/data' }) }
    await expect(handlers.responseR(error)).rejects.toThrow('refresh down')
    expect(mockAuthStorage.clear).toHaveBeenCalled()
    expect(mockElMessage.error).toHaveBeenCalledWith('登录已过期，请重新登录')
    expect(location.href).toBe('/login')
  })

  it('401 请求冻结中 → 不跳转不提示', async () => {
    const location: any = { pathname: '/workbench', href: '' }
    vi.stubGlobal('location', location)
    const m = await import('@/api/request')
    m.freezeRequests()
    try {
      const error = { response: { status: 401, data: {} }, config: makeConfig({ url: '/data' }) }
      await expect(handlers.responseR(error)).rejects.toBe(error)
      expect(location.href).toBe('')
      expect(mockElMessage.error).not.toHaveBeenCalled()
    } finally {
      m.unfreezeRequests()
    }
  })

  it('网络错误未重试过 → 延迟 2 秒后重试一次', async () => {
    vi.useFakeTimers()
    mockInst.request.mockResolvedValueOnce('network-retried')
    await import('@/api/request')
    const error = { code: 'ERR_NETWORK', message: 'NetworkError', config: makeConfig() }
    const p = handlers.responseR(error)
    expect((error.config as any)._networkRetried).toBe(true)
    await vi.advanceTimersByTimeAsync(2000)
    await expect(p).resolves.toBe('network-retried')
    expect(mockInst.request).toHaveBeenCalledWith(error.config)
  })

  it('网络错误已重试过 → 挂载网络失败消息不再重试', async () => {
    const config = makeConfig({ _networkRetried: true })
    await import('@/api/request')
    const error = { code: 'ERR_NETWORK', message: 'NetworkError', config }
    await expect(handlers.responseR(error)).rejects.toBe(error)
    expect(error.userMessage).toBe('网络连接失败，请检查服务是否启动')
    expect(mockElMessage.error).not.toHaveBeenCalled()
    expect(mockInst.request).not.toHaveBeenCalled()
  })
})
