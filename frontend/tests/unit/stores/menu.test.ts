import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

const mockGet = vi.fn()
const mockGetToken = vi.fn()

vi.mock('@/api/request', () => ({
  get: (...args: any[]) => mockGet(...args),
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

vi.mock('@/utils/authStorage', () => ({
  AuthStorage: {
    getToken: () => mockGetToken(),
  },
}))

import { useMenuStore } from '@/stores/menu'

describe('useMenuStore', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetToken.mockReturnValue('token123')
    setActivePinia(createPinia())
  })

  it('initial state: menus 是空数组, activeMenu 是空字符串', () => {
    const store = useMenuStore()
    expect(store.menus).toEqual([])
    expect(store.activeMenu).toBe('')
  })

  it('setMenus 写入菜单列表', () => {
    const store = useMenuStore()
    const items = [
      { key: 'dashboard', label: '仪表盘', path: '/dashboard' },
      { key: 'villages', label: '帮扶村', path: '/villages' },
    ]
    store.setMenus(items)
    expect(store.menus).toEqual(items)
  })

  it('setActive 修改当前激活菜单', () => {
    const store = useMenuStore()
    store.setActive('villages')
    expect(store.activeMenu).toBe('villages')
  })

  it('多次 setActive 后保持最后一个值', () => {
    const store = useMenuStore()
    store.setActive('a')
    store.setActive('b')
    store.setActive('c')
    expect(store.activeMenu).toBe('c')
  })

  it('setMenus 替换为新数组', () => {
    const store = useMenuStore()
    store.setMenus([{ key: 'a', label: 'A' }])
    store.setMenus([{ key: 'b', label: 'B' }])
    expect(store.menus).toHaveLength(1)
    expect(store.menus[0].key).toBe('b')
  })

  it('setMenus 提取所有 key（含子节点）到 accessibleKeys', () => {
    const store = useMenuStore()
    store.setMenus([
      {
        key: 'root',
        label: 'Root',
        children: [
          { key: 'child-a', label: 'A' },
          { key: 'child-b', label: 'B', children: [{ key: 'grand', label: 'G' }] },
        ],
      },
    ])
    expect(store.accessibleKeys.has('root')).toBe(true)
    expect(store.accessibleKeys.has('child-a')).toBe(true)
    expect(store.accessibleKeys.has('child-b')).toBe(true)
    expect(store.accessibleKeys.has('grand')).toBe(true)
  })

  it('setMenus 清空 loading / loadFailed 并置 loaded=true', () => {
    const store = useMenuStore()
    store.loading = true
    store.loadFailed = true
    store.setMenus([])
    expect(store.loaded).toBe(true)
    expect(store.loading).toBe(false)
    expect(store.loadFailed).toBe(false)
  })

  it('setOrgPolicies 构建 module_key → policy 映射', () => {
    const store = useMenuStore()
    store.setOrgPolicies([
      { module_key: 'funds', visibility: 'hidden', edit_mode: 'read_only' },
      { module_key: 'schools', visibility: 'visible', edit_mode: 'full_edit' },
    ])
    expect(store.orgPolicies['funds']).toEqual({
      module_key: 'funds',
      visibility: 'hidden',
      edit_mode: 'read_only',
    })
    expect(store.orgPolicies['schools'].edit_mode).toBe('full_edit')
  })

  describe('canAccessMenu', () => {
    it('菜单未加载时返回 false', () => {
      const store = useMenuStore()
      expect(store.canAccessMenu('dashboard')).toBe(false)
    })

    it('模块策略 hidden 时返回 false', () => {
      const store = useMenuStore()
      store.setMenus([{ key: 'dashboard', label: 'D' }])
      store.setOrgPolicies([{ module_key: 'dashboard', visibility: 'hidden', edit_mode: 'full_edit' }])
      expect(store.canAccessMenu('dashboard')).toBe(false)
    })

    it('key 在 allKeys 中返回 true', () => {
      const store = useMenuStore()
      store.setMenus([{ key: 'dashboard', label: 'D' }])
      expect(store.canAccessMenu('dashboard')).toBe(true)
    })

    it('key 不在 allKeys 中返回 false', () => {
      const store = useMenuStore()
      store.setMenus([{ key: 'dashboard', label: 'D' }])
      expect(store.canAccessMenu('nope')).toBe(false)
    })
  })

  describe('canEditModule', () => {
    it('无策略时返回 true', () => {
      const store = useMenuStore()
      expect(store.canEditModule('schools')).toBe(true)
    })

    it('full_edit 返回 true', () => {
      const store = useMenuStore()
      store.setOrgPolicies([{ module_key: 'schools', visibility: 'visible', edit_mode: 'full_edit' }])
      expect(store.canEditModule('schools')).toBe(true)
    })

    it('read_only 返回 false', () => {
      const store = useMenuStore()
      store.setOrgPolicies([{ module_key: 'schools', visibility: 'visible', edit_mode: 'read_only' }])
      expect(store.canEditModule('schools')).toBe(false)
    })

    it('disabled 返回 false', () => {
      const store = useMenuStore()
      store.setOrgPolicies([{ module_key: 'schools', visibility: 'visible', edit_mode: 'disabled' }])
      expect(store.canEditModule('schools')).toBe(false)
    })
  })

  describe('isModuleDisabled', () => {
    it('edit_mode=disabled 返回 true', () => {
      const store = useMenuStore()
      store.setOrgPolicies([{ module_key: 'a', visibility: 'visible', edit_mode: 'disabled' }])
      expect(store.isModuleDisabled('a')).toBe(true)
    })

    it('visibility=hidden 返回 true', () => {
      const store = useMenuStore()
      store.setOrgPolicies([{ module_key: 'a', visibility: 'hidden', edit_mode: 'full_edit' }])
      expect(store.isModuleDisabled('a')).toBe(true)
    })

    it('full_edit + visible 返回 false', () => {
      const store = useMenuStore()
      store.setOrgPolicies([{ module_key: 'a', visibility: 'visible', edit_mode: 'full_edit' }])
      expect(store.isModuleDisabled('a')).toBe(false)
    })

    it('无策略时返回 false', () => {
      const store = useMenuStore()
      expect(store.isModuleDisabled('a')).toBe(false)
    })
  })

  describe('fetchMenus', () => {
    it('无 token 时直接返回', async () => {
      mockGetToken.mockReturnValue(null)
      const store = useMenuStore()
      await store.fetchMenus()
      expect(mockGet).not.toHaveBeenCalled()
    })

    it('并发调用共享同一请求（只发一次 API，双方都等到加载完成）', async () => {
      // 回归锁定：登录后 fire-and-forget 预加载与路由守卫的 await 必须共享
      // 同一 in-flight Promise —— 旧实现"loading 中直接 return"导致守卫拿到
      // loaded=false 的假完成，登录后立即被弹到 /403。
      let resolveGet!: (v: { data: { key: string; label: string }[] }) => void
      mockGet.mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveGet = resolve
          })
      )
      const store = useMenuStore()
      const p1 = store.fetchMenus()
      const p2 = store.fetchMenus()
      expect(mockGet).toHaveBeenCalledTimes(1) // 去重：只发一次请求
      resolveGet({ data: [{ key: 'dashboard', label: '工作台' }] })
      await Promise.all([p1, p2])
      expect(store.loaded).toBe(true)
      expect(store.menus).toHaveLength(1)
    })

    it('成功（res.data 数组）时写入菜单并更新状态', async () => {
      mockGet.mockResolvedValueOnce({
        data: [{ key: 'dashboard', label: 'D' }, { key: 'funds', label: 'F' }],
      })
      const store = useMenuStore()
      await store.fetchMenus()
      expect(mockGet).toHaveBeenCalledWith('/menus/accessible')
      expect(store.menus).toHaveLength(2)
      expect(store.loaded).toBe(true)
      expect(store.loading).toBe(false)
      expect(store.loadFailed).toBe(false)
    })

    it('成功（裸数组响应）时写入菜单', async () => {
      mockGet.mockResolvedValueOnce([{ key: 'dashboard', label: 'D' }])
      const store = useMenuStore()
      await store.fetchMenus()
      expect(store.menus).toHaveLength(1)
      expect(store.loaded).toBe(true)
    })

    it('成功但数据非数组时置空菜单', async () => {
      mockGet.mockResolvedValueOnce({ data: { items: [] } })
      const store = useMenuStore()
      await store.fetchMenus()
      expect(store.menus).toEqual([])
      expect(store.loaded).toBe(true)
    })

    it('响应为 null 时进入失败分支', async () => {
      mockGet.mockResolvedValueOnce(null)
      const store = useMenuStore()
      await store.fetchMenus()
      expect(store.loadFailed).toBe(true)
      expect(store.menus).toEqual([])
    })

    it('响应为 falsy 值（如 0）时置空菜单', async () => {
      mockGet.mockResolvedValueOnce(0)
      const store = useMenuStore()
      await store.fetchMenus()
      expect(store.menus).toEqual([])
      expect(store.loaded).toBe(true)
    })

    it('请求失败时标记 loadFailed 并重置 loading', async () => {
      mockGet.mockRejectedValueOnce(new Error('network'))
      const store = useMenuStore()
      await store.fetchMenus()
      expect(store.loadFailed).toBe(true)
      expect(store.loading).toBe(false)
      expect(store.loaded).toBe(false)
    })
  })

  describe('fetchOrgPolicies', () => {
    it('成功时写入策略映射', async () => {
      mockGet.mockResolvedValueOnce({
        data: [{ module_key: 'funds', visibility: 'hidden', edit_mode: 'read_only' }],
      })
      const store = useMenuStore()
      await store.fetchOrgPolicies()
      expect(mockGet).toHaveBeenCalledWith('/org-policies/current')
      expect(store.orgPolicies['funds'].visibility).toBe('hidden')
    })

    it('数据非数组时不更新', async () => {
      mockGet.mockResolvedValueOnce({ data: { module_key: 'x' } })
      const store = useMenuStore()
      store.setOrgPolicies([{ module_key: 'keep', visibility: 'visible', edit_mode: 'full_edit' }])
      await store.fetchOrgPolicies()
      expect(store.orgPolicies['keep']).toBeDefined()
      expect(store.orgPolicies['x']).toBeUndefined()
    })

    it('响应为 falsy 值（如 0）时清空策略映射', async () => {
      mockGet.mockResolvedValueOnce(0)
      const store = useMenuStore()
      store.setOrgPolicies([{ module_key: 'keep', visibility: 'visible', edit_mode: 'full_edit' }])
      await store.fetchOrgPolicies()
      expect(store.orgPolicies['keep']).toBeUndefined()
    })

    it('失败时静默', async () => {
      mockGet.mockRejectedValueOnce(new Error('network'))
      const store = useMenuStore()
      await expect(store.fetchOrgPolicies()).resolves.toBeUndefined()
    })
  })
})
