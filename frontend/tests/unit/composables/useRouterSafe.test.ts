import { describe, it, expect, beforeEach, vi } from 'vitest'

const mockPush = vi.fn()
const mockResolve = vi.fn(() => ({ name: 'TestRoute', matched: [{ path: '/test' }] }))
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mockPush, resolve: mockResolve }),
}))

import { useRouterSafe, safeRouteParam, isNavigationFailureLike } from '@/composables/useRouterSafe'

/** 构造与 vue-router createRouterError 同形的 NavigationFailure（Error + 数字 type + from/to） */
function makeNavigationFailure(type = 4) {
  return Object.assign(new Error('navigation aborted'), { type, from: {}, to: {} })
}

describe('isNavigationFailureLike', () => {
  it('非 Error（字符串/普通对象）→ false', () => {
    expect(isNavigationFailureLike('aborted')).toBe(false)
    expect(isNavigationFailureLike({ type: 4, from: {}, to: {} })).toBe(false)
    expect(isNavigationFailureLike(null)).toBe(false)
    expect(isNavigationFailureLike(undefined)).toBe(false)
  })

  it('Error 但 type 非数字 → false', () => {
    expect(isNavigationFailureLike(new Error('boom'))).toBe(false)
    expect(isNavigationFailureLike(Object.assign(new Error('x'), { type: '4' }))).toBe(false)
  })

  it('Error + 数字 type 但缺 from/to → false', () => {
    expect(isNavigationFailureLike(Object.assign(new Error('x'), { type: 4 }))).toBe(false)
    expect(isNavigationFailureLike(Object.assign(new Error('x'), { type: 4, from: {} }))).toBe(false)
  })

  it('Error + 数字 type + from/to → true（NavigationFailure 结构）', () => {
    expect(isNavigationFailureLike(makeNavigationFailure())).toBe(true)
  })
})

describe('safeRouteParam', () => {
  it('undefined → 默认回退值', () => {
    expect(safeRouteParam(undefined)).toBe(0)
    expect(safeRouteParam(undefined, 9)).toBe(9)
  })

  it('null → 默认回退值', () => {
    expect(safeRouteParam(null, 9)).toBe(9)
  })

  it('数字字符串 → 转数字', () => {
    expect(safeRouteParam('42')).toBe(42)
    expect(safeRouteParam('3.5', 9)).toBe(3.5)
  })

  it('无效字符串 → 回退值', () => {
    expect(safeRouteParam('abc', 9)).toBe(9)
  })

  it('数字值 → 直接返回', () => {
    expect(safeRouteParam(7)).toBe(7)
  })

  it('Infinity/NaN → 回退值', () => {
    expect(safeRouteParam(Infinity, 9)).toBe(9)
    expect(safeRouteParam(NaN, 9)).toBe(9)
  })

  it('数组取第一个有效值', () => {
    expect(safeRouteParam(['5'])).toBe(5)
    expect(safeRouteParam(['7', '8'])).toBe(7)
  })

  it('空数组 → 回退值', () => {
    expect(safeRouteParam([], 9)).toBe(9)
  })

  it('数组首元素为 null → 回退值', () => {
    expect(safeRouteParam([null], 9)).toBe(9)
  })

  it('数组内为无效值 → 回退值', () => {
    expect(safeRouteParam(['x'], 9)).toBe(9)
  })
})

describe('useRouterSafe', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('返回 pushSafe 函数', () => {
    const { pushSafe } = useRouterSafe()
    expect(typeof pushSafe).toBe('function')
  })

  it('pushSafe 调用 router.push with string path', () => {
    mockPush.mockReturnValueOnce(Promise.resolve())
    const { pushSafe } = useRouterSafe()
    pushSafe('/dashboard')
    expect(mockPush).toHaveBeenCalledWith('/dashboard')
  })

  it('pushSafe 调用 router.push with route object', () => {
    mockPush.mockReturnValueOnce(Promise.resolve())
    const { pushSafe } = useRouterSafe()
    const route = { path: '/users', query: { id: 5 } }
    pushSafe(route)
    expect(mockPush).toHaveBeenCalledWith(route)
  })

  it('pushSafe 接受 debugLabel 参数 (无副作用)', () => {
    mockPush.mockReturnValueOnce(Promise.resolve())
    const { pushSafe } = useRouterSafe()
    pushSafe('/test', '测试页面')
    expect(mockPush).toHaveBeenCalledWith('/test')
  })

  it('非 DEV 环境 debugLabel 不输出日志', () => {
    vi.stubEnv('DEV', false)
    const logSpy = vi.spyOn(console, 'log').mockImplementation(() => {})
    mockPush.mockReturnValueOnce(Promise.resolve())
    const { pushSafe } = useRouterSafe()
    pushSafe('/test', '测试页面')
    expect(logSpy).not.toHaveBeenCalled()
    expect(mockPush).toHaveBeenCalledWith('/test')
    logSpy.mockRestore()
    vi.unstubAllEnvs()
  })

  it('pushSafe 失败时调用 window.location.href fallback', async () => {
    mockPush.mockReturnValueOnce(Promise.reject(new Error('nav failed')))
    const originalLocation = window.location
    Object.defineProperty(window, 'location', {
      value: { ...originalLocation, href: '' },
      writable: true,
    })
    const consoleErr = vi.spyOn(console, 'error').mockImplementation(() => {})
    const { pushSafe } = useRouterSafe()
    pushSafe('/fallback')
    await new Promise((r) => setTimeout(r, 10))
    expect(consoleErr).toHaveBeenCalled()
    consoleErr.mockRestore()
  })

  it('pushSafe 同步异常时也 fallback 到 window.location.href', () => {
    mockPush.mockImplementationOnce(() => {
      throw new Error('sync')
    })
    const consoleErr = vi.spyOn(console, 'error').mockImplementation(() => {})
    const { pushSafe } = useRouterSafe()
    pushSafe('/safe')
    expect(consoleErr).toHaveBeenCalled()
    consoleErr.mockRestore()
  })

  // 2026-09-30 深审修复：未知内部路由原先 window.location.href 整页重载
  // （丢内存态、重启 SPA 后仍落到同一 404）。现改为 SPA 内 push NotFound，
  // 仅当 NotFound 也不可达时才回退原生跳转。断言随之改写。
  it('路由解析为 NotFound 时 console.error 并跳 SPA 内 NotFound（不整页重载）', () => {
    mockResolve.mockReturnValueOnce({ name: 'NotFound', matched: [{ path: '/x' }] })
    const originalLocation = window.location
    Object.defineProperty(window, 'location', {
      value: { ...originalLocation, href: '' },
      writable: true,
    })
    const consoleErr = vi.spyOn(console, 'error').mockImplementation(() => {})
    mockPush.mockReturnValueOnce(Promise.resolve())
    const { pushSafe } = useRouterSafe()
    pushSafe('/unknown', '未知路由')
    expect(consoleErr).toHaveBeenCalledWith(
      expect.stringContaining('/unknown (未知路由)')
    )
    expect(mockPush).toHaveBeenCalledWith({ name: 'NotFound' })
    expect(window.location.href).toBe('')
    consoleErr.mockRestore()
  })

  it('路由解析 matched 为空时同样跳 SPA 内 NotFound', () => {
    mockResolve.mockReturnValueOnce({ name: 'X', matched: [] })
    const consoleErr = vi.spyOn(console, 'error').mockImplementation(() => {})
    mockPush.mockReturnValueOnce(Promise.resolve())
    const { pushSafe } = useRouterSafe()
    pushSafe('/void')
    expect(consoleErr).toHaveBeenCalled()
    expect(mockPush).toHaveBeenCalledWith({ name: 'NotFound' })
    consoleErr.mockRestore()
  })

  it('NotFound 路由 push 异步失败 → 回退原生跳转（二次兜底）', async () => {
    mockResolve.mockReturnValueOnce({ name: 'NotFound', matched: [{ path: '/x' }] })
    const originalLocation = window.location
    Object.defineProperty(window, 'location', {
      value: { ...originalLocation, href: '' },
      writable: true,
    })
    const consoleErr = vi.spyOn(console, 'error').mockImplementation(() => {})
    mockPush.mockReturnValueOnce(Promise.reject(new Error('no 404 route')))
    const { pushSafe } = useRouterSafe()
    pushSafe('/unknown')
    await new Promise((r) => setTimeout(r, 10))
    expect(window.location.href).toBe('/unknown')
    consoleErr.mockRestore()
  })

  it('NotFound 路由 push 同步抛错 → 回退原生跳转（同步兜底）', () => {
    mockResolve.mockReturnValueOnce({ name: 'NotFound', matched: [{ path: '/x' }] })
    const originalLocation = window.location
    Object.defineProperty(window, 'location', {
      value: { ...originalLocation, href: '' },
      writable: true,
    })
    const consoleErr = vi.spyOn(console, 'error').mockImplementation(() => {})
    mockPush.mockImplementationOnce(() => {
      throw new Error('sync')
    })
    const { pushSafe } = useRouterSafe()
    pushSafe('/unknown')
    expect(window.location.href).toBe('/unknown')
    consoleErr.mockRestore()
  })

  it('守卫中止（NavigationFailure）→ 不整页重载、不打印错误', async () => {
    const hrefSpy = vi.spyOn(window.location, 'href' as any, 'set')
    const consoleErr = vi.spyOn(console, 'error').mockImplementation(() => {})
    mockPush.mockReturnValueOnce(Promise.reject(makeNavigationFailure()))
    const { pushSafe } = useRouterSafe()
    pushSafe('/dashboard')
    await new Promise((r) => setTimeout(r, 10))
    expect(hrefSpy).not.toHaveBeenCalled()
    expect(consoleErr).not.toHaveBeenCalled()
    consoleErr.mockRestore()
    hrefSpy.mockRestore()
  })

  it('非 NavigationFailure 的 Error → 仍回退原生跳转', async () => {
    const originalLocation = window.location
    Object.defineProperty(window, 'location', {
      value: { ...originalLocation, href: '' },
      writable: true,
    })
    const consoleErr = vi.spyOn(console, 'error').mockImplementation(() => {})
    mockPush.mockReturnValueOnce(Promise.reject(Object.assign(new Error('nf'), { type: 4 })))
    const { pushSafe } = useRouterSafe()
    pushSafe('/fallback2')
    await new Promise((r) => setTimeout(r, 10))
    expect(window.location.href).toBe('/fallback2')
    consoleErr.mockRestore()
  })

  it('路由对象无 path 时跳过解析检查并正常 push', () => {
    mockPush.mockReturnValueOnce(Promise.resolve())
    const { pushSafe } = useRouterSafe()
    const route = { name: 'SomeNamedRoute', params: { id: 1 } }
    pushSafe(route)
    expect(mockPush).toHaveBeenCalledWith(route)
  })

  it('push 返回非 Promise 时不抛错', () => {
    mockPush.mockReturnValueOnce(undefined as any)
    const { pushSafe } = useRouterSafe()
    expect(() => pushSafe('/no-promise')).not.toThrow()
  })

  it('路由对象无 path 且 push 同步抛错时不回退原生跳转', () => {
    mockPush.mockImplementationOnce(() => {
      throw new Error('sync')
    })
    const consoleErr = vi.spyOn(console, 'error').mockImplementation(() => {})
    const hrefSpy = vi.spyOn(window.location, 'href' as any, 'set')
    const { pushSafe } = useRouterSafe()
    pushSafe({ name: 'NamedRoute' })
    expect(consoleErr).toHaveBeenCalled()
    expect(hrefSpy).not.toHaveBeenCalled()
    consoleErr.mockRestore()
    hrefSpy.mockRestore()
  })

  it('路由对象无 path 且 push 异步失败时不回退原生跳转', async () => {
    mockPush.mockReturnValueOnce(Promise.reject(new Error('async')))
    const consoleErr = vi.spyOn(console, 'error').mockImplementation(() => {})
    const hrefSpy = vi.spyOn(window.location, 'href' as any, 'set')
    const { pushSafe } = useRouterSafe()
    pushSafe({ name: 'NamedRoute' })
    await new Promise((r) => setTimeout(r, 10))
    expect(consoleErr).toHaveBeenCalled()
    expect(hrefSpy).not.toHaveBeenCalled()
    consoleErr.mockRestore()
    hrefSpy.mockRestore()
  })
})
