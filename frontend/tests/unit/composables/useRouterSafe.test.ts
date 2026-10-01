import { describe, it, expect, beforeEach, vi } from 'vitest'

const mockPush = vi.fn()
const mockResolve = vi.fn(() => ({ name: 'TestRoute', matched: [{ path: '/test' }] }))
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mockPush, resolve: mockResolve }),
}))

import {
  useRouterSafe,
  safeRouteParam,
  isNavigationFailureLike,
  toSafeLocationHref,
  SAFE_LOCATION_FALLBACK,
} from '@/composables/useRouterSafe'

/** 构造与 vue-router createRouterError 同形的 NavigationFailure（Error + 数字 type + from/to） */
function makeNavigationFailure(type = 4) {
  return Object.assign(new Error('navigation aborted'), { type, from: {}, to: {} })
}

describe('toSafeLocationHref（开放重定向 / 脚本协议守卫）', () => {
  it('同源相对路径原样放行', () => {
    expect(toSafeLocationHref('/dashboard')).toBe('/dashboard')
    expect(toSafeLocationHref('/policies/1?tab=detail')).toBe('/policies/1?tab=detail')
    expect(toSafeLocationHref('relative/path')).toBe('relative/path')
    expect(toSafeLocationHref('#hash')).toBe('#hash')
  })

  it('空串 / 纯空白 / 控制字符 → 回退默认首页', () => {
    // cleaned 为空 → 命中 `if (!cleaned) return fallback`
    expect(toSafeLocationHref('')).toBe(SAFE_LOCATION_FALLBACK)
    expect(toSafeLocationHref('   ')).toBe(SAFE_LOCATION_FALLBACK)
    expect(toSafeLocationHref('\t\n\r')).toBe(SAFE_LOCATION_FALLBACK)
    expect(toSafeLocationHref('\u0000\u001f')).toBe(SAFE_LOCATION_FALLBACK)
  })

  it('自定义 fallback 在非法目标时生效', () => {
    expect(toSafeLocationHref('', '/login')).toBe('/login')
    expect(toSafeLocationHref('https://evil.com', '/login')).toBe('/login')
  })

  it('协议相对地址（// 或 /\\ 开头）→ 回退（防外站跳转）', () => {
    expect(toSafeLocationHref('//evil.com/x')).toBe(SAFE_LOCATION_FALLBACK)
    expect(toSafeLocationHref('/\\evil.com/x')).toBe(SAFE_LOCATION_FALLBACK)
    expect(toSafeLocationHref('\\\\evil.com/x')).toBe(SAFE_LOCATION_FALLBACK)
    expect(toSafeLocationHref('\\evil.com')).toBe(SAFE_LOCATION_FALLBACK)
  })

  it('带协议前缀（http/https/javascript/data 等）→ 回退（防脚本执行）', () => {
    expect(toSafeLocationHref('https://evil.com')).toBe(SAFE_LOCATION_FALLBACK)
    expect(toSafeLocationHref('http://evil.com')).toBe(SAFE_LOCATION_FALLBACK)
    expect(toSafeLocationHref('javascript:alert(1)')).toBe(SAFE_LOCATION_FALLBACK)
    expect(toSafeLocationHref('data:text/html,<script>x</script>')).toBe(SAFE_LOCATION_FALLBACK)
    expect(toSafeLocationHref('vbscript:msgbox(1)')).toBe(SAFE_LOCATION_FALLBACK)
    // 大小写不敏感（正则 [a-zA-Z] 首字符）
    expect(toSafeLocationHref('JavaScript:alert(1)')).toBe(SAFE_LOCATION_FALLBACK)
  })

  it('控制字符剥离后仍能识别脚本协议（防 java\\tscript: 绕过）', () => {
    // 先剥离 \t \n \r 再判定，否则 "java\tscript:" 会通过协议正则漏网
    expect(toSafeLocationHref('java\tscript:alert(1)')).toBe(SAFE_LOCATION_FALLBACK)
    expect(toSafeLocationHref('java\nscript:alert(1)')).toBe(SAFE_LOCATION_FALLBACK)
    expect(toSafeLocationHref('\tjavascript:alert(1)')).toBe(SAFE_LOCATION_FALLBACK)
    // 带前导空白的正常路径剥离后放行
    expect(toSafeLocationHref('  /dashboard  ')).toBe('/dashboard')
  })

  it('协议判定不误伤含冒号但非协议前缀的相对路径', () => {
    // 首字符非字母（正则要求 [a-zA-Z] 开头）→ 不判为协议
    expect(toSafeLocationHref('/a:b')).toBe('/a:b')
    expect(toSafeLocationHref('1:2')).toBe('1:2')
  })

  it('运行时传入 null/undefined（绕过 TS 类型）→ 回退而非抛错', () => {
    // String(path ?? '') 的 ?? 右侧：JS 调用方（如 window.location.href 直接取值）
    // 可能传入 undefined，此处锁死"不抛 TypeError、静默回退"的防御语义
    expect(toSafeLocationHref(null as unknown as string)).toBe(SAFE_LOCATION_FALLBACK)
    expect(toSafeLocationHref(undefined as unknown as string)).toBe(SAFE_LOCATION_FALLBACK)
  })
})

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
    expect(isNavigationFailureLike(Object.assign(new Error('x'), { type: 4, from: {} }))).toBe(
      false
    )
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
    expect(consoleErr).toHaveBeenCalledWith(expect.stringContaining('/unknown (未知路由)'))
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
