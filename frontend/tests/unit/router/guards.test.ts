/**
 * src/router/guards.ts 覆盖率测试
 *
 * 策略：
 *  - mock '@/router/index' 捕获 beforeEach 注册的守卫函数，
 *    直接以 (to, from, next) 三元组调用验证各分支。
 *  - mock '@/utils/authStorage'（token / user 可控）
 *  - mock '@/stores/menu'（loaded / fetchMenus / canAccessMenu 可控）
 *  - '@/utils/roleAccess' 使用真实 ADMIN_ROLES（admin, super_admin）
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'

const {
  mockBeforeEach,
  mockGetToken,
  mockGetUser,
  mockFetchMenus,
  mockCanAccessMenu,
  mockUseMenuStore,
} = vi.hoisted(() => ({
  mockBeforeEach: vi.fn(),
  mockGetToken: vi.fn(),
  mockGetUser: vi.fn(),
  mockFetchMenus: vi.fn(),
  mockCanAccessMenu: vi.fn(),
  mockUseMenuStore: vi.fn(),
}))

vi.mock('@/router/index', () => ({
  default: {
    beforeEach: (guard: any) => mockBeforeEach(guard),
  },
}))

vi.mock('@/utils/authStorage', () => ({
  AuthStorage: {
    getToken: () => mockGetToken(),
    getUser: () => mockGetUser(),
  },
}))

vi.mock('@/stores/menu', () => ({
  useMenuStore: () => mockUseMenuStore(),
}))

import '@/router/guards'

// guards.ts 在模块加载时即通过 router.beforeEach 注册守卫，
// 此处捕获该函数实例（必须在 beforeEach 的 clearAllMocks 之前读取）。
const guard: any = mockBeforeEach.mock.calls[0][0]

const defaultMenuStore = () => ({
  loaded: true,
  fetchMenus: mockFetchMenus,
  canAccessMenu: mockCanAccessMenu,
})

describe('router guards', () => {
  let next: ReturnType<typeof vi.fn>

  beforeEach(() => {
    vi.clearAllMocks()
    mockGetToken.mockReturnValue('')
    mockGetUser.mockReturnValue(null)
    mockFetchMenus.mockResolvedValue(undefined)
    mockCanAccessMenu.mockReturnValue(true)
    mockUseMenuStore.mockReturnValue(defaultMenuStore())
    next = vi.fn()
  })

  async function run(to: any, from: any = { path: '/from' }) {
    await guard(to, from, next)
  }

  it('守卫已注册到路由实例', () => {
    expect(typeof guard).toBe('function')
  })

  it('noAuth 路由直接放行并设置页面标题', async () => {
    await run({ path: '/login', meta: { noAuth: true, title: '登录' } })
    expect(next).toHaveBeenCalledWith()
    expect(document.title).toBe('登录')
  })

  it('白名单路径直接放行（无 meta 时使用默认标题）', async () => {
    await run({ path: '/register', meta: undefined })
    expect(next).toHaveBeenCalledWith()
    expect(document.title).toBe('帮扶管理信息系统')
  })

  it('未登录时跳转登录页并携带 redirect', async () => {
    mockGetToken.mockReturnValue(null)
    await run({ path: '/dashboard', meta: { title: '工作台' } })
    expect(next).toHaveBeenCalledWith('/login?redirect=/dashboard')
    expect(document.title).toBe('工作台')
  })

  it('强制改密用户访问普通页面时重定向到改密页', async () => {
    mockGetToken.mockReturnValue('tok')
    mockGetUser.mockReturnValue({ id: '1', must_change_password: true })
    await run({ path: '/dashboard', meta: {} })
    expect(next).toHaveBeenCalledWith('/change-password')
  })

  it('强制改密用户访问改密页时放行', async () => {
    mockGetToken.mockReturnValue('tok')
    mockGetUser.mockReturnValue({ id: '1', must_change_password: true })
    await run({ path: '/change-password', meta: {} })
    expect(next).toHaveBeenCalledWith()
  })

  it('不满足角色要求时跳转 403', async () => {
    mockGetToken.mockReturnValue('tok')
    mockGetUser.mockReturnValue({ id: '1', role: 'user' })
    await run({ path: '/system/users', meta: { roles: ['admin', 'super_admin'] } })
    expect(next).toHaveBeenCalledWith('/403')
  })

  it('管理员角色通过角色校验', async () => {
    mockGetToken.mockReturnValue('tok')
    mockGetUser.mockReturnValue({ id: '1', role: 'admin' })
    await run({ path: '/system/users', meta: { roles: ['admin', 'super_admin'] } })
    expect(next).toHaveBeenCalledWith()
  })

  it('目标角色在 requiredRoles 中时通过校验', async () => {
    mockGetToken.mockReturnValue('tok')
    mockGetUser.mockReturnValue({ id: '1', role: 'viewer' })
    await run({ path: '/x', meta: { roles: ['viewer'] } })
    expect(next).toHaveBeenCalledWith()
  })

  it('空角色列表不拦截', async () => {
    mockGetToken.mockReturnValue('tok')
    await run({ path: '/x', meta: { roles: [] } })
    expect(next).toHaveBeenCalledWith()
  })

  it('有 token 但无用户信息且需角色时跳转 403', async () => {
    mockGetToken.mockReturnValue('tok')
    await run({ path: '/x', meta: { roles: ['admin'] } })
    expect(next).toHaveBeenCalledWith('/403')
  })

  it('菜单未加载时先拉取菜单，无权访问跳转 403', async () => {
    mockGetToken.mockReturnValue('tok')
    mockUseMenuStore.mockReturnValue({
      loaded: false,
      fetchMenus: mockFetchMenus,
      canAccessMenu: mockCanAccessMenu,
    })
    mockCanAccessMenu.mockReturnValue(false)
    await run({ path: '/funds', meta: { menuKey: 'funds' } })
    expect(mockFetchMenus).toHaveBeenCalledTimes(1)
    expect(next).toHaveBeenCalledWith('/403')
  })

  it('菜单未加载时先拉取菜单，有权访问放行', async () => {
    mockGetToken.mockReturnValue('tok')
    mockUseMenuStore.mockReturnValue({
      loaded: false,
      fetchMenus: mockFetchMenus,
      canAccessMenu: mockCanAccessMenu,
    })
    mockCanAccessMenu.mockReturnValue(true)
    await run({ path: '/funds', meta: { menuKey: 'funds' } })
    expect(mockFetchMenus).toHaveBeenCalledTimes(1)
    expect(next).toHaveBeenCalledWith()
  })

  it('菜单已加载时不重复拉取并放行', async () => {
    mockGetToken.mockReturnValue('tok')
    await run({ path: '/funds', meta: { menuKey: 'funds' } })
    expect(mockFetchMenus).not.toHaveBeenCalled()
    expect(next).toHaveBeenCalledWith()
  })

  it('无 menuKey 时跳过菜单权限检查', async () => {
    mockGetToken.mockReturnValue('tok')
    await run({ path: '/profile', meta: { title: '个人中心' } })
    expect(mockUseMenuStore).not.toHaveBeenCalled()
    expect(next).toHaveBeenCalledWith()
  })
})


describe('router guards — 免登录直达', () => {
  it('已登录（持久令牌）访问白名单路径 → 重定向工作台', async () => {
    mockGetToken.mockReturnValue('persisted-tok')
    const next = vi.fn()
    await guard({ path: '/login', meta: {} }, { path: '/from' }, next)
    expect(next).toHaveBeenCalledWith('/dashboard')
  })
})
