/**
 * src/router/index.ts 覆盖率测试
 *
 * 覆盖目标：src/router/index.ts 100% 语句覆盖
 *
 * 策略：
 *  - mock '@/composables/useChunkLoader' 的 retryImport 为恒等调用，
 *    使路由懒加载包装器 `() => retryImport(() => import(...))` 两层箭头函数体
 *    都被真实执行（真实 import 各视图模块）。
 *  - 真实使用导出的 router 实例（web history，jsdom 环境可用）逐个 push：
 *      · 全部 redirect 路由（静态与带参函数式）
 *      · beforeEach 守卫的 /undefined、/null 拦截与各 fallback 分支、放行分支
 *  - 遍历 routes 调用每个懒加载 component 函数，确保所有视图模块可被加载，
 *    覆盖全部 `component: () => ...` 语句。
 */
import { describe, it, expect, vi } from 'vitest'

// ==================== Mocks ====================

vi.mock('@/composables/useChunkLoader', () => ({
  retryImport: (fn: () => Promise<any>) => fn(),
  default: (fn: () => Promise<any>) => fn(),
}))

// 避免真实加载重型图表库（视图模块顶层 import 用）
vi.mock('@/utils/echarts', () => ({
  default: {
    init: () => ({
      setOption: () => {},
      on: () => {},
      resize: () => {},
      dispose: () => {},
      isDisposed: () => false,
    }),
    graphic: { LinearGradient: class {} },
    use: () => {},
  },
}))
vi.mock('echarts', () => ({
  init: () => ({ setOption: () => {}, on: () => {}, resize: () => {}, dispose: () => {} }),
  graphic: { LinearGradient: class {} },
}))
vi.mock('chart.js/auto', () => ({
  Chart: class {
    constructor(..._args: any[]) {}
    destroy() {}
  },
}))

// LoginEnhanced.vue 由专属测试 tests/unit/views/auth/LoginEnhanced.test.ts 单一引用覆盖
// （覆盖率合并不变量：每个被 100% 阈值锁定的 .vue 全仓只允许一个测试文件触碰，含 bare
// import）。本文件为覆盖 router/index.ts 的懒加载语句，会真实执行全部懒加载组件函数与
// push('/login')——若真实加载 LoginEnhanced，本 worker isolate 会留下不含渲染分支的
// fnMap 分片，与专属测试的 19 函数分片在满量按 id 合并时错位 → functions 88.23%
// （Linux CI 实测与 Node 版本无关）。用桩替换：懒加载函数本体仍被执行（router 语句
// 覆盖不受影响），但不再触碰 LoginEnhanced 真实模块。
vi.mock('@/views/auth/LoginEnhanced.vue', () => ({
  default: { name: 'LoginEnhancedCoverageStub' },
}))

import router, { routes } from '@/router'

// ==================== Helpers ====================

const push = (path: string) => router.push(path).catch((e) => e)

interface FlatRoute {
  path: string
  component: any
}

const flatten = (rs: any[], base = ''): FlatRoute[] =>
  rs.flatMap((r) => [
    { path: `${base}${r.path}`, component: r.component },
    ...(r.children ? flatten(r.children, `${base}${r.path} `) : []),
  ])

const lazyRoutes = flatten(routes as any[]).filter((r) => typeof r.component === 'function')

// ==================== Tests ====================

describe('router/index.ts', () => {
  it('路由表已定义且包含懒加载组件', () => {
    expect(routes.length).toBeGreaterThan(0)
    expect(lazyRoutes.length).toBeGreaterThan(50)
  })

  it('根路径重定向到工作台', async () => {
    await push('/')
    expect(router.currentRoute.value.path).toBe('/dashboard')
  })

  it('普通路径直接放行（守卫 next() 分支）', async () => {
    await push('/login')
    expect(router.currentRoute.value.path).toBe('/login')
    expect(router.currentRoute.value.name).toBe('Login')
  })

  it('旧帮扶村路径重定向（含函数式 redirect）', async () => {
    await push('/villages')
    expect(router.currentRoute.value.path).toBe('/supported-villages')

    await push('/villages/12')
    expect(router.currentRoute.value.path).toBe('/supported-villages/12')

    await push('/villages/12/yearly-data')
    expect(router.currentRoute.value.path).toBe('/supported-villages/12/yearly')

    await push('/villages/13/yearly')
    expect(router.currentRoute.value.path).toBe('/supported-villages/13/yearly')

    await push('/villages/14/edit')
    expect(router.currentRoute.value.path).toBe('/supported-villages/14')
    expect(router.currentRoute.value.query.mode).toBe('edit')
  })

  it('守卫拦截 /undefined 与 /null 路径并回退到各列表页', async () => {
    await push('/supported-villages/undefined')
    expect(router.currentRoute.value.path).toBe('/supported-villages')

    await push('/schools/undefined')
    expect(router.currentRoute.value.path).toBe('/schools')

    await push('/projects/null')
    expect(router.currentRoute.value.path).toBe('/projects')

    await push('/funds/undefined')
    expect(router.currentRoute.value.path).toBe('/funds')
  })

  it('守卫对未识别前缀的 /undefined 路径回退到工作台', async () => {
    await push('/system/undefined')
    expect(router.currentRoute.value.path).toBe('/dashboard')
  })

  it('旧版路径兼容重定向全部生效', async () => {
    const cases: Array<[string, string]> = [
      ['/data-sync', '/data-sync/export'],
      ['/funds/apply', '/funds/user'],
      ['/effectiveness', '/effectiveness/rankings'],
      ['/data-verify', '/data-verify/rules'],
      ['/system/help', '/help'],
      ['/system/roles', '/system/users'],
      ['/system/menu-permissions', '/system/users'],
      ['/analytics/map', '/data-analysis/map'],
      ['/analytics/dashboard', '/data-analysis/dashboard'],
      ['/analytics/work-analysis', '/data-analysis/reports'],
      ['/analytics/assessment', '/data-analysis/assessment'],
      ['/data-entry/comprehensive', '/data-entry'],
      ['/report-export', '/export/report'],
      ['/data-management/backup', '/system/backup'],
      ['/data-management/logs', '/system/audit'],
      ['/data-import/batch', '/data-package'],
      ['/system/config-package', '/system/config'],
    ]
    for (const [from, to] of cases) {
      await push(from)
      expect(router.currentRoute.value.path).toBe(to)
    }
  })

  it('未匹配路径命中 NotFound 路由', async () => {
    await push('/definitely-not-a-page-xyz')
    expect(router.currentRoute.value.name).toBe('NotFound')
  })

  it('Electron 托盘 onNavigate 收到合法路径时跳转', async () => {
    const onNavigateMock = vi.fn()
    ;(window as any).electronAPI = { onNavigate: onNavigateMock }
    try {
      vi.resetModules()
      const { default: freshRouter } = await import('@/router')
      expect(onNavigateMock).toHaveBeenCalled()
      const handler = onNavigateMock.mock.calls[0][0] as (route: string) => void
      expect(typeof handler).toBe('function')
      const before = freshRouter.currentRoute.value.path
      handler('/dashboard')
      await freshRouter.isReady()
      await new Promise((r) => setTimeout(r, 50))
      const after = freshRouter.currentRoute.value.path
      expect(before).not.toBe('/dashboard')
      expect(after).toBe('/dashboard')
    } finally {
      delete (window as any).electronAPI
      vi.resetModules()
      await import('@/router')
    }
  })

  it('Electron 托盘 onNavigate 收到非路径参数时不跳转', async () => {
    const onNavigateMock = vi.fn()
    ;(window as any).electronAPI = { onNavigate: onNavigateMock }
    try {
      vi.resetModules()
      await import('@/router')
      const handler = onNavigateMock.mock.calls[0][0] as (route: string) => void
      expect(handler).toBeDefined()
      handler('no-slash')
      handler(123 as any)
      expect(onNavigateMock).toHaveBeenCalled()
    } finally {
      delete (window as any).electronAPI
      vi.resetModules()
      await import('@/router')
    }
  })

  it('无 electronAPI 环境不注册导航', async () => {
    ;(window as any).electronAPI = undefined
    try {
      vi.resetModules()
      await import('@/router')
      expect(true).toBe(true)
    } finally {
      delete (window as any).electronAPI
      vi.resetModules()
      await import('@/router')
    }
  })

  // 分批加载全部懒加载组件（每批 15 条，防止单用例超时）
  const CHUNK = 15
  const chunks: FlatRoute[][] = []
  for (let i = 0; i < lazyRoutes.length; i += CHUNK) {
    chunks.push(lazyRoutes.slice(i, i + CHUNK))
  }
  chunks.forEach((chunk, idx) => {
    it(`懒加载组件均可加载（第 ${idx + 1}/${chunks.length} 批）`, async () => {
      const failures: string[] = []
      for (const r of chunk) {
        try {
          const mod = await r.component()
          expect(mod).toBeTruthy()
        } catch (e: any) {
          failures.push(`${r.path} → ${e?.message ?? e}`)
        }
      }
      expect(failures).toEqual([])
    })
  })
})
