/**
 * W3-T2：菜单权限守卫单测
 * user 角色访问无权限 menuKey 路由 → 重定向 /403；
 * 有权限 menuKey → 放行；admin 角色全部放行；未登录 → 跳登录。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'

const { mockCanAccess, mockFetchMenus, mockGetUser, mockGetToken } = vi.hoisted(() => ({
  mockCanAccess: vi.fn(),
  mockFetchMenus: vi.fn(),
  mockGetUser: vi.fn(),
  mockGetToken: vi.fn(),
}))

vi.mock('@/stores/menu', () => ({
  useMenuStore: () => ({
    loaded: true,
    loadFailed: false,
    loading: false,
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
