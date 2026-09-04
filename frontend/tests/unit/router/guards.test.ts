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

describe('白名单路由（登录/注册/找回密码）免登录跳转 + 锁屏拦截', () => {
  beforeEach(() => {
    mockCanAccess.mockReset()
    mockFetchMenus.mockReset()
    mockGetToken.mockReturnValue('tok')
    mockGetUser.mockReturnValue({ role: 'user' })
    sessionStorage.clear()
  })

  it('已登录且未锁屏访问 /login → 直接进 /dashboard（免登录）', async () => {
    const next = vi.fn()
    await routeGuard({ meta: {}, path: '/login' } as any, {} as any, next)
    expect(next).toHaveBeenCalledWith('/dashboard')
  })

  it('/register 与 /forgot-password 同属白名单，同样免登录进工作台', async () => {
    for (const p of ['/register', '/forgot-password']) {
      const next = vi.fn()
      await routeGuard({ meta: {}, path: p } as any, {} as any, next)
      expect(next).toHaveBeenCalledWith('/dashboard')
    }
  })

  it('锁屏标记 auto_lock_active="1" 时，有令牌也不自动跳回（必须重输密码）', async () => {
    sessionStorage.setItem('auto_lock_active', '1')
    const next = vi.fn()
    await routeGuard({ meta: {}, path: '/login' } as any, {} as any, next)
    expect(next).toHaveBeenCalledWith()
    expect(next).not.toHaveBeenCalledWith('/dashboard')
  })

  it('锁屏标记为非 "1" 值时不算锁定（严格等值判定）', async () => {
    sessionStorage.setItem('auto_lock_active', '0')
    const next = vi.fn()
    await routeGuard({ meta: {}, path: '/login' } as any, {} as any, next)
    expect(next).toHaveBeenCalledWith('/dashboard')
  })

  it('未登录访问白名单页 → 原样放行（不产生 redirect 环）', async () => {
    mockGetToken.mockReturnValue(null)
    const next = vi.fn()
    await routeGuard({ meta: {}, path: '/login' } as any, {} as any, next)
    expect(next).toHaveBeenCalledWith()
    expect(next).not.toHaveBeenCalledWith('/dashboard')
  })

  it('sessionStorage 抛错（隐私模式/配额）时按未锁屏处理，不崩溃', async () => {
    // src/test/setup.ts 把 globalThis.sessionStorage 装成了一个普通对象（非 Storage 实例），
    // 因此必须直接 spy 该对象；spy Storage.prototype 不会被命中，catch 分支永远进不去。
    const spy = vi.spyOn(sessionStorage, 'getItem').mockImplementation(() => {
      throw new Error('SecurityError')
    })
    try {
      const next = vi.fn()
      await routeGuard({ meta: {}, path: '/login' } as any, {} as any, next)
      // 读锁屏标记失败 → locked 维持 false → 有令牌仍免登录进工作台
      expect(spy).toHaveBeenCalledWith('auto_lock_active')
      expect(next).toHaveBeenCalledWith('/dashboard')
    } finally {
      spy.mockRestore()
    }
  })
})

describe('强制改密（must_change_password）路由收口', () => {
  beforeEach(() => {
    mockCanAccess.mockReset()
    mockFetchMenus.mockReset()
    mockGetToken.mockReturnValue('tok')
    sessionStorage.clear()
  })

  it('must_change_password===true 访问业务页 → 重定向 /change-password', async () => {
    mockGetUser.mockReturnValue({ role: 'admin', must_change_password: true })
    const next = vi.fn()
    await routeGuard({ meta: {}, path: '/dashboard' } as any, {} as any, next)
    expect(next).toHaveBeenCalledWith('/change-password')
  })

  it('must_change_password===true 访问 /change-password 本身 → 放行（否则死循环）', async () => {
    mockGetUser.mockReturnValue({ role: 'admin', must_change_password: true })
    const next = vi.fn()
    await routeGuard({ meta: {}, path: '/change-password' } as any, {} as any, next)
    expect(next).toHaveBeenCalledWith()
    expect(next).not.toHaveBeenCalledWith('/change-password')
  })

  it('must_change_password===true 仍可访问 /logout（允许放弃改密退出）', async () => {
    mockGetUser.mockReturnValue({ role: 'admin', must_change_password: true })
    const next = vi.fn()
    await routeGuard({ meta: {}, path: '/logout' } as any, {} as any, next)
    expect(next).toHaveBeenCalledWith()
  })

  it('must_change_password 为字符串 "true" 时不触发（严格 === true）', async () => {
    mockGetUser.mockReturnValue({ role: 'admin', must_change_password: 'true' })
    const next = vi.fn()
    await routeGuard({ meta: {}, path: '/dashboard' } as any, {} as any, next)
    expect(next).toHaveBeenCalledWith()
  })

  it('must_change_password 为 false 时不受影响', async () => {
    mockGetUser.mockReturnValue({ role: 'admin', must_change_password: false })
    const next = vi.fn()
    await routeGuard({ meta: {}, path: '/dashboard' } as any, {} as any, next)
    expect(next).toHaveBeenCalledWith()
  })

  it('user 为 null 时不触发强制改密分支（可选链短路）', async () => {
    mockGetUser.mockReturnValue(null)
    const next = vi.fn()
    await routeGuard({ meta: {}, path: '/dashboard' } as any, {} as any, next)
    expect(next).toHaveBeenCalledWith()
  })

  it('强制改密优先于 meta.roles 校验（先收口到改密页，不再判 403）', async () => {
    mockGetUser.mockReturnValue({ role: 'user', must_change_password: true })
    const next = vi.fn()
    await routeGuard(
      { meta: { roles: ['admin', 'super_admin'] }, path: '/system/users' } as any,
      {} as any,
      next
    )
    expect(next).toHaveBeenCalledWith('/change-password')
    expect(next).not.toHaveBeenCalledWith('/403')
  })
})
