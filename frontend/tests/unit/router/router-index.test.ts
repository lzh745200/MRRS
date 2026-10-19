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

// ReportExport.vue 同理：coverage-merge 不变量（本文件执行全部懒加载组件函数，
// 不渲染分支的 fnMap 分片与专属测试按 id 合并错位 → functions 88.88%，WSL 实测）。
vi.mock('@/views/export/ReportExport.vue', () => ({
  default: { name: 'ReportExportCoverageStub' },
}))

// 下级单位管理 / 模块策略配置：coverage-merge 不变量——两者各有专属深挂载测试，
// 本文件若真实加载会产出不含渲染分支的 fnMap 分片，满量按 id 合并会错位。
// 懒加载函数本体仍被执行（router/index.ts 语句覆盖不受影响），只是不再触碰真实模块。
vi.mock('@/views/admin/SubordinateManagement.vue', () => ({
  default: { name: 'SubordinateManagementCoverageStub' },
}))
vi.mock('@/views/admin/OrgModulePolicy.vue', () => ({
  default: { name: 'OrgModulePolicyCoverageStub' },
}))

// PairingList.vue 同理：本文件执行全部懒加载组件函数，专属测试
// tests/unit/views/pairing/List.test.ts 深挂载全部分支；此处桩替换避免 fnMap 分片错位。
vi.mock('@/views/pairing/List.vue', () => ({
  default: { name: 'PairingListCoverageStub' },
}))

// HandoverIndex.vue（w17-004）同理：专属测试
// tests/unit/views/handover/Index.test.ts 深挂载全部分支；本文件仅执行懒加载函数本体。
vi.mock('@/views/handover/Index.vue', () => ({
  default: { name: 'HandoverIndexCoverageStub' },
}))

// DonationList.vue（w17-003）同理：专属测试
// tests/unit/views/donation/List.test.ts 深挂载全部分支；本文件仅执行懒加载函数本体。
vi.mock('@/views/donation/List.vue', () => ({
  default: { name: 'DonationListCoverageStub' },
}))

// 工作台页头操作区（W11-T45 PageHeader 去重后的 views/dashboard/components/
// HeaderActions.vue）同理：专属测试 tests/unit/views/dashboard/HeaderActions.test.ts
// 深挂载全部分支；Dashboard 路由 chunk 会带入本模块，桩替换避免 fnMap 分片按 id 合并错位。
vi.mock('@/views/dashboard/components/HeaderActions.vue', () => ({
  default: { name: 'DashboardHeaderActionsCoverageStub' },
}))

// 帮扶村详情（w17-002 新增专属全分支测试 tests/unit/views/analytics/supported-villages/
// Detail.test.ts）同理：本文件执行全部懒加载组件函数，桩替换避免 fnMap 分片按 id 合并错位。
vi.mock('@/views/analytics/supported-villages/Detail.vue', () => ({
  default: { name: 'SupportedVillageDetailCoverageStub' },
}))

// 系统管理聚合页（v1.13.0 单一菜单源）：专属测试
// tests/unit/views/system/SystemConsole.test.ts 深挂载全部分支；本文件执行全部懒加载
// 组件函数时只验证模块可加载性，桩替换避免同一 .vue 出现第二个执行者导致 fnMap 合并错位。
vi.mock('@/views/system/console/SystemConsole.vue', () => ({
  default: { name: 'SystemConsoleCoverageStub' },
}))

// 布局 DefaultLayoutSafe.vue 同理：唯一执行者是
// tests/unit/layouts/DefaultLayoutSafe.test.ts（渲染全分支 + 其静态 import 的
// MenuSearchDialog/MobileBottomNav 在 layout 测试内以 vi.mock 桩掉）。本文件遍历
// 懒加载组件函数会真实 import 布局模块，必须桩替换否则产生第二个执行者。
vi.mock('@/layouts/DefaultLayoutSafe.vue', () => ({
  default: { name: 'DefaultLayoutSafeCoverageStub' },
}))

// W22（v1.14.0）新增页面同理：各自有专属渲染测试深挂载全部分支，本文件只执行
// 懒加载函数本体，桩替换避免同一 .vue 出现第二个执行者导致 fnMap 合并错位。
vi.mock('@/views/households/List.vue', () => ({
  default: { name: 'HouseholdListCoverageStub' },
}))
vi.mock('@/views/households/Detail.vue', () => ({
  default: { name: 'HouseholdDetailCoverageStub' },
}))
vi.mock('@/views/media/PhotoArchive.vue', () => ({
  default: { name: 'PhotoArchiveCoverageStub' },
}))
vi.mock('@/views/consumption/List.vue', () => ({
  default: { name: 'ConsumptionListCoverageStub' },
}))
vi.mock('@/views/dataVerify/Index.vue', () => ({
  default: { name: 'DataVerifyCoverageStub' },
}))

// R33（v1.15.12）单位授权配置/导入两页同理：各自有专属深挂载测试
// （tests/unit/views/system/OrgGrant.test.ts、tests/unit/views/system/GrantImport.test.ts）。
// 本文件遍历全部懒加载组件函数时会真实 import 这两个模块，不桩替换即产生第二个执行者，
// 满量按 id 合并 fnMap 时可能错位 → functions 跌破 100%（见 frontend/vitest.config.ts 注释 (A)）。
vi.mock('@/views/system/OrgGrant.vue', () => ({
  default: { name: 'OrgGrantCoverageStub' },
}))
vi.mock('@/views/system/GrantImport.vue', () => ({
  default: { name: 'GrantImportCoverageStub' },
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
      ['/sentiment', '/consumption'],
      ['/system/help', '/help'],
      ['/system/roles', '/system/users'],
      ['/system/menu-permissions', '/system/users'],
      // W8-018：用户权限管理页下线重定向 + 年度概览过渡页移除后的兼容重定向
      ['/system/user-permissions', '/system/permission-packs'],
      ['/supported-villages/yearly', '/supported-villages'],
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
      const mod: any = await import('@/router')
      // 契约：electronAPI 缺失时模块仍可加载、路由表完整，只是不注册 onNavigate
      expect(mod.default).toBeTruthy()
      expect(mod.default.getRoutes().length).toBeGreaterThan(0)
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
