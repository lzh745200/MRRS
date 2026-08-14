import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// request.ts 本体测试：不 mock '@/api/request' 自身，捕获拦截器 handler 直接驱动。
// 覆盖 request-interceptors.test.ts 未触及的分支：403/404/500/422/400、
// 离线回退、refresh token 续期流程、items/total 安全化、重复请求取消。
const {
  handlers,
  mockInst,
  mockAxiosPost,
  capturedCancels,
  authState,
  mockAuthStorage,
  mockElMessage,
  offlineState,
  mockGetMockResponse,
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
    capturedCancels,
    authState,
    mockAuthStorage,
    mockElMessage,
    offlineState,
    mockGetMockResponse,
  }
})

vi.mock('axios', () => {
  const MockCancelToken: any = vi.fn((executor: any) => {
    const cancel = vi.fn()
    capturedCancels.push(cancel)
    executor(cancel)
    return 'cancel-token'
  })
  MockCancelToken.source = vi.fn(() => ({ token: 'mock-token', cancel: vi.fn() }))
  return {
    default: {
      create: vi.fn(() => mockInst),
      post: mockAxiosPost,
      get: vi.fn(),
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
  _setCachedToken,
  unfreezeRequests,
  cancelAllRequests,
  getPendingRequestCount,
  cancelRequest,
} from '@/api/request'

const makeConfig = (over: any = {}) => ({
  method: 'GET',
  url: '/x',
  params: {},
  headers: {},
  ...over,
})

describe('api/request — 拦截器未覆盖分支', () => {
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
  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('request interceptor', () => {
    it('POST 请求回填 cookie 中的 CSRF token', async () => {
      document.cookie = 'csrftoken=csrf-abc; path=/'
      const config = makeConfig({ method: 'POST', url: '/unsafe' })
      await handlers.request(config)
      expect(config.headers['X-CSRF-Token']).toBe('csrf-abc')
    })

    it('GET 请求不设置 CSRF 头', async () => {
      const config = makeConfig({ method: 'GET', url: '/safe' })
      await handlers.request(config)
      expect(config.headers['X-CSRF-Token']).toBeUndefined()
    })

    it('相同 key 的重复请求会取消前一个挂起请求', async () => {
      await handlers.request(makeConfig({ method: 'GET', url: '/dup', params: { a: 1 } }))
      expect(capturedCancels).toHaveLength(1)
      await handlers.request(makeConfig({ method: 'GET', url: '/dup', params: { a: 1 } }))
      expect(capturedCancels).toHaveLength(2)
      expect(capturedCancels[0]).toHaveBeenCalled()
      expect(capturedCancels[1]).not.toHaveBeenCalled()
    })
  })

  describe('response interceptor — success 边界', () => {
    it('data 为 null 时不展开', () => {
      const response = { config: makeConfig(), data: { code: 200, data: null } }
      const result = handlers.response(response)
      expect(result).toBe(response)
      expect(response.data).toEqual({ code: 200, data: null })
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

    it('数组 payload 不覆盖已有 items', () => {
      const response = {
        config: makeConfig(),
        data: { code: 200, data: [1, 2], items: [9] },
      }
      handlers.response(response)
      expect(response.data.items).toEqual([9])
    })

    it('items 非数组时安全化为 [] 并告警', () => {
      const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
      const response = { config: makeConfig(), data: { code: 200, items: 'oops' } }
      handlers.response(response)
      expect(response.data.items).toEqual([])
      expect(warnSpy).toHaveBeenCalled()
    })

    it('total 非数字时回退为 items.length', () => {
      const response = {
        config: makeConfig(),
        data: { code: 200, items: [1, 2, 3], total: 'many' },
      }
      handlers.response(response)
      expect(response.data.total).toBe(3)
    })

    it('非对象 data 原样返回', () => {
      const response = { config: makeConfig(), data: 'plain-text' }
      const result = handlers.response(response)
      expect(result.data).toBe('plain-text')
    })
  })

  describe('response interceptor — HTTP 状态分类', () => {
    it('失败请求清理 pending 追踪', async () => {
      const config = makeConfig({ method: 'GET', url: '/pending', params: {} })
      await handlers.request(config)
      expect(getPendingRequestCount()).toBe(1)
      const error = { response: { status: 400, data: {} }, config }
      await expect(handlers.responseR(error)).rejects.toBe(error)
      expect(getPendingRequestCount()).toBe(0)
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

    it('403 + CSRF 已重试过 → 挂载安全校验过期消息', async () => {
      const config = makeConfig({ method: 'POST', url: '/secure', _csrfRetried: true })
      const error = { response: { status: 403, data: { detail: 'csrf invalid' } }, config }
      await expect(handlers.responseR(error)).rejects.toBe(error)
      expect(error.userMessage).toBe('安全校验已过期，请重试（CSRF）')
      expect(mockElMessage.error).not.toHaveBeenCalled()
    })

    it('403 非 CSRF → 挂载服务端 detail', async () => {
      const error = {
        response: { status: 403, data: { detail: '无操作权限' } },
        config: makeConfig(),
      }
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

    it('404 → 挂载资源不存在消息', async () => {
      const error = { response: { status: 404, data: {} }, config: makeConfig({ url: '/missing' }) }
      await expect(handlers.responseR(error)).rejects.toBe(error)
      expect(error.userMessage).toBe('请求的资源不存在')
      expect(mockElMessage.warning).not.toHaveBeenCalled()
    })

    it('500 → 挂载服务器错误消息', async () => {
      const error = { response: { status: 500, data: {} }, config: makeConfig() }
      await expect(handlers.responseR(error)).rejects.toBe(error)
      expect(error.userMessage).toBe('服务器错误，请稍后重试')
      expect(mockElMessage.error).not.toHaveBeenCalled()
    })

    it('422 数组 detail → 提取首条字段错误', async () => {
      const error = {
        response: {
          status: 422,
          data: { detail: [{ loc: ['body', 'name'], msg: '必填' }] },
        },
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

    it('400 带 detail → 挂载 detail', async () => {
      const error = {
        response: { status: 400, data: { detail: '参数错误' } },
        config: makeConfig(),
      }
      await expect(handlers.responseR(error)).rejects.toBe(error)
      expect(error.userMessage).toBe('参数错误')
      expect(mockElMessage.warning).not.toHaveBeenCalled()
    })
  })

  describe('response interceptor — 网络/离线/未知错误', () => {
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

    it('网络错误且无离线 mock → 挂载网络失败消息', async () => {
      const error = {
        code: 'ERR_NETWORK',
        message: 'NetworkError',
        config: makeConfig(),
      }
      await expect(handlers.responseR(error)).rejects.toBe(error)
      expect(error.userMessage).toBe('网络连接失败，请检查服务是否启动')
      expect(mockElMessage.error).not.toHaveBeenCalled()
    })

    it('未知错误 → console.error 记录', async () => {
      const errSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
      const error = { message: 'something weird' }
      await expect(handlers.responseR(error)).rejects.toBe(error)
      expect(errSpy).toHaveBeenCalled()
    })
  })

  describe('response interceptor — 401 refresh 续期', () => {
    it('无 refresh_token → 清除认证并提示重新登录', async () => {
      const error = {
        response: { status: 401, data: {} },
        config: makeConfig({ url: '/data' }),
      }
      await expect(handlers.responseR(error)).rejects.toBe(error)
      expect(mockAuthStorage.clear).toHaveBeenCalled()
      expect(mockElMessage.error).toHaveBeenCalledWith('登录已过期，请重新登录')
      expect(mockAxiosPost).not.toHaveBeenCalled()
    })

    it('登录端点 401 不触发 refresh（防无限循环）', async () => {
      authState.refreshToken = 'refresh-1'
      const error = {
        response: { status: 401, data: {} },
        config: makeConfig({ url: '/auth/login' }),
      }
      await expect(handlers.responseR(error)).rejects.toBe(error)
      expect(mockAuthStorage.clear).toHaveBeenCalled()
      expect(mockAxiosPost).not.toHaveBeenCalled()
    })

    it('refresh 成功 → 更新 token 并用新 token 重发原请求', async () => {
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

    it('refresh 响应缺 access_token → 走失败路径清除认证', async () => {
      authState.refreshToken = 'refresh-1'
      mockAxiosPost.mockResolvedValueOnce({ data: {} })
      const error = {
        response: { status: 401, data: {} },
        config: makeConfig({ url: '/data' }),
      }
      await expect(handlers.responseR(error)).rejects.toThrow(
        'Refresh response missing access_token'
      )
      expect(mockAuthStorage.clear).toHaveBeenCalled()
      expect(mockElMessage.error).toHaveBeenCalledWith('登录已过期，请重新登录')
    })

    it('refresh 失败 → 当前请求与排队请求一并拒绝', async () => {
      authState.refreshToken = 'refresh-1'
      let rejectRefresh: any
      mockAxiosPost.mockReturnValueOnce(
        new Promise((_, rej) => {
          rejectRefresh = rej
        })
      )
      const errorA = { response: { status: 401, data: {} }, config: makeConfig({ url: '/a' }) }
      const p1 = handlers.responseR(errorA)
      // _isRefreshing 已为 true，第二个 401 进入队列
      const errorB = { response: { status: 401, data: {} }, config: makeConfig({ url: '/b' }) }
      const p2 = handlers.responseR(errorB)
      expect(mockAxiosPost).toHaveBeenCalledTimes(1)

      rejectRefresh(new Error('refresh boom'))
      await expect(p1).rejects.toThrow('refresh boom')
      await expect(p2).rejects.toThrow('refresh boom')
      expect(mockAuthStorage.clear).toHaveBeenCalled()
    })

    it('refresh 期间后续 401 排队，成功后统一用新 token 重发', async () => {
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
      // 排队期间只触发一次 refresh
      expect(mockAxiosPost).toHaveBeenCalledTimes(1)

      resolveRefresh({ data: { data: { access_token: 'T2' } } })
      await expect(p1).resolves.toBe('ok')
      await expect(p2).resolves.toBe('ok')
      expect(errorA.config.headers.Authorization).toBe('Bearer T2')
      expect(errorB.config.headers.Authorization).toBe('Bearer T2')
      expect(mockInst.request).toHaveBeenCalledTimes(2)
    })
  })

  describe('request interceptor — 剩余边界分支', () => {
    it('config 无 method 时回退为 get（不触发 CSRF）', async () => {
      const config = makeConfig({ method: undefined })
      await handlers.request(config)
      expect(config.headers['X-CSRF-Token']).toBeUndefined()
    })
  })

  describe('response interceptor — 401 无 url / 404 兜底 / 422 / 400 / 未知错误', () => {
    it('401 且 config.url 为 undefined → 走非登录端点分支并登出', async () => {
      const error = { response: { status: 401, data: {} }, config: makeConfig({ url: undefined }) }
      await expect(handlers.responseR(error)).rejects.toBe(error)
      expect(mockAuthStorage.clear).toHaveBeenCalled()
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

    it('422 detail 为空数组 → 默认校验失败提示', async () => {
      const error = {
        response: { status: 422, data: { detail: [] } },
        config: makeConfig(),
      }
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

    it('400 detail 为对象 → 挂载通用请求失败消息', async () => {
      const error = {
        response: { status: 400, data: { detail: { field: 'x' } } },
        config: makeConfig(),
      }
      await expect(handlers.responseR(error)).rejects.toBe(error)
      expect(error.userMessage).toBe('请求失败 (400)')
      expect(mockElMessage.warning).not.toHaveBeenCalled()
    })

    it('400 无 detail 但带 message → 挂载 message', async () => {
      const error = {
        response: { status: 400, data: { message: '请求被拒绝' } },
        config: makeConfig(),
      }
      await expect(handlers.responseR(error)).rejects.toBe(error)
      expect(error.userMessage).toBe('请求被拒绝')
      expect(mockElMessage.warning).not.toHaveBeenCalled()
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

    it('未知错误无 message → 记录 error 对象', async () => {
      const errSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
      const error = { code: 'WHATEVER' }
      await expect(handlers.responseR(error)).rejects.toBe(error)
      expect(errSpy).toHaveBeenCalled()
    })
  })

  describe('cancelRequest 精确匹配', () => {
    it('取消匹配 URL 段的挂起请求', async () => {
      await handlers.request(makeConfig({ method: 'GET', url: '/dupx' }))
      expect(getPendingRequestCount()).toBe(1)
      cancelRequest('/dupx')
      expect(getPendingRequestCount()).toBe(0)
      expect(capturedCancels[0]).toHaveBeenCalled()
    })
  })
})
