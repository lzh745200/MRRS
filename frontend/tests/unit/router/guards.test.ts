/**
 * W3-T2：菜单权限守卫单测
 * user 角色访问无权限 menuKey 路由 → 重定向 /403；
 * 有权限 menuKey → 放行；admin 角色全部放行；未登录 → 跳登录。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'

const { mockCanAccess, mockFetchMenus, mockGetUser, mockGetToken, menuState } = vi.hoisted(() => ({
  mockCanAccess: vi.fn(),
  mockFetchMenus: vi.fn(),
  mockGetUser: vi.fn(),
  mockGetToken: vi.fn(),
  menuState: { loaded: true, loadFailed: false, loading: false },
}))

vi.mock('@/stores/menu', () => ({
  useMenuStore: () => ({
    get loaded() {
      return menuState.loaded
    },
    loadFailed: menuState.loadFailed,
    loading: menuState.loading,
    fetchMenus: mockFetchMenus,
    canAccessMenu: mockCanAccess,
  }),
}))

vi.mock('@/utils/authStorage', () => ({
  AuthStorage: { getUser: mockGetUser, getToken: mockGetToken },
}))

import { routeGuard } from '@/router/guards'

describe('W3-T2 菜单权限守卫', () => {
  beforeEach(() => {
    mockCanAccess.mockReset()
    mockFetchMenus.mockReset()
    mockGetToken.mockReturnValue('tok')
    mockGetUser.mockReturnValue({ role: 'user' })
  })

  it('user 角色访问无权限 menuKey 路由 → 重定向 /403', async () => {
    mockCanAccess.mockReturnValue(false)
    const next = vi.fn()
    await routeGuard({ meta: { menuKey: 'audit' }, path: '/system/audit' } as any, {} as any, next)
    expect(next).toHaveBeenCalledWith('/403')
  })

  it('user 角色访问有权限 menuKey 路由 → 放行', async () => {
    mockCanAccess.mockImplementation((k: string) => k === 'audit')
    const next = vi.fn()
    await routeGuard({ meta: { menuKey: 'audit' }, path: '/system/audit' } as any, {} as any, next)
    expect(next).toHaveBeenCalledWith()
  })

  it('admin 角色访问任何 menuKey 路由 → 放行', async () => {
    mockGetUser.mockReturnValue({ role: 'admin' })
    mockCanAccess.mockReturnValue(true)
    const next = vi.fn()
    await routeGuard({ meta: { menuKey: 'audit' }, path: '/system/audit' } as any, {} as any, next)
    expect(next).toHaveBeenCalledWith()
  })

  it('未登录 → 跳登录页', async () => {
    mockGetToken.mockReturnValue(null)
    const next = vi.fn()
    await routeGuard({ meta: {}, path: '/system/audit' } as any, {} as any, next)
    expect(next).toHaveBeenCalledWith(expect.stringContaining('/login'))
  })
})

describe('403 修复：菜单加载失败不阻断导航 + 旧角色归一化', () => {
  beforeEach(() => {
    mockCanAccess.mockReset()
    mockFetchMenus.mockReset()
    mockGetToken.mockReturnValue('tok')
  })

  it('菜单未加载（后端冷启动/接口失败）→ 放行，由后端接口兜底', async () => {
    menuState.loaded = false // fetchMenus 失败后保持未加载
    // 真实 store 的 fetchMenus 内部捕获异常后 resolve（loaded 保持 false）
    mockFetchMenus.mockResolvedValue(undefined)
    mockCanAccess.mockReturnValue(false)
    mockGetUser.mockReturnValue({ role: 'admin' })
    const next = vi.fn()
    await routeGuard({ meta: { menuKey: 'audit' }, path: '/system/audit' } as any, {} as any, next)
    expect(next).toHaveBeenCalledWith()
    expect(next).not.toHaveBeenCalledWith('/403')
    menuState.loaded = true
  })

  it('存量旧角色 manager 访问 admin 页 → 归一化后放行', async () => {
    mockGetUser.mockReturnValue({ role: 'manager' })
    const next = vi.fn()
    await routeGuard(
      {
        meta: { title: '用户管理', roles: ['admin', 'super_admin'] },
        path: '/system/users',
      } as any,
      {} as any,
      next
    )
    expect(next).toHaveBeenCalledWith()
  })

  it('user 角色访问 admin 页 → 仍拒绝', async () => {
    mockGetUser.mockReturnValue({ role: 'user' })
    const next = vi.fn()
    await routeGuard(
      {
        meta: { title: '用户管理', roles: ['admin', 'super_admin'] },
        path: '/system/users',
      } as any,
      {} as any,
      next
    )
    expect(next).toHaveBeenCalledWith('/403')
  })
})
