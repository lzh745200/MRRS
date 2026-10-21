import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

const mockGet = vi.fn()
const mockGetToken = vi.fn()

vi.mock('@/api/request', () => ({
  get: (...args: any[]) => mockGet(...args),
  getCsrfToken: vi.fn(() => Promise.resolve('test-csrf')),
}))

vi.mock('@/utils/authStorage', () => ({
  AuthStorage: {
    getToken: () => mockGetToken(),
  },
}))

// canAccessMenu 现引入超管旁路判断（useAuthStore）。本文件只测 menu store 本身，
// 故 mock 掉 auth store（user=null → 旁路不触发，既有断言语义不变），
// 同时避免引入 auth.ts 的传递依赖（api/queries 等）。超管旁路语义见 menu-bypass.test.ts。
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({ user: null }),
}))

import {
  useMenuStore,
  DASHBOARD_FLAT_ENTRY,
  DASHBOARD_MENU_KEY,
  type MenuPayloadV2,
  type MenuSection,
} from '@/stores/menu'

/** 契约 §2 的 v2 响应样例（sections + flat_keys） */
const V2_PAYLOAD: MenuPayloadV2 = {
  version: 2,
  sections: [
    {
      key: 'business',
      label: '帮扶业务',
      order: 10,
      items: [
        {
          key: 'villages',
          label: '帮扶村管理',
          path: '/supported-villages',
          icon: 'Location',
          order: 10,
          kind: 'page',
          roles: null,
        },
        {
          key: 'funds',
          label: '经费管理',
          icon: 'Money',
          order: 40,
          kind: 'group',
          roles: ['admin', 'super_admin', 'user', 'viewer'],
          children: [
            {
              key: 'funds-admin',
              label: '经费台账',
              path: '/funds',
              icon: 'Money',
              order: 10,
              kind: 'page',
              roles: ['admin', 'super_admin', 'user', 'viewer'],
            },
          ],
        },
      ],
    },
    {
      key: 'system',
      label: '系统管理',
      order: 90,
      items: [
        {
          key: 'system-console-org',
          label: '组织与权限',
          path: '/system/console/org',
          icon: 'OfficeBuilding',
          order: 10,
          kind: 'console',
          roles: ['admin', 'super_admin'],
          tabs: [
            {
              key: 'users-orgs',
              label: '用户与组织',
              path: '/system/users',
              icon: 'User',
              order: 10,
              roles: ['admin', 'super_admin'],
            },
          ],
        },
      ],
    },
  ],
  flat_keys: ['dashboard', 'villages', 'funds', 'funds-admin', 'system-console-org', 'users-orgs'],
}

/** 脏数据样例：一次覆盖各解析分支的非法输入路径 */
const MALFORMED_PAYLOAD = {
  sections: [
    null,
    'not-a-section',
    { key: 42, items: [] },
    { key: 'no-items', label: 'NoItems' },
    { key: 'empty', label: 'Empty', items: [] },
    {
      key: 'dirty',
      items: [
        null,
        [],
        { label: '缺 key' },
        { key: 'grp-empty', kind: 'group' },
        {
          key: 'grp-dirty',
          kind: 'group',
          children: [null, { label: '缺 key 的子项' }, { key: 'ok-child', path: '/ok' }],
        },
        {
          key: 'console-dirty',
          kind: 'console',
          path: '/console',
          tabs: [null, { key: 'tab-no-path' }, { key: 'tab-ok', path: '/tab' }],
        },
        { key: 'no-label-page', path: '/no-label', icon: 42, order: 'bad' },
        { key: 'console-no-path', kind: 'console' },
        { key: 'page-no-path' },
      ],
    },
  ],
  flat_keys: ['dirty', 7],
}

describe('useMenuStore', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetToken.mockReturnValue('token123')
    setActivePinia(createPinia())
  })

  it('initial state: 空数组/未加载/工作台扁平条目固定第一', () => {
    const store = useMenuStore()
    expect(store.menus).toEqual([])
    expect(store.sections).toEqual([])
    expect(store.flatEntries).toEqual([DASHBOARD_FLAT_ENTRY])
    expect(store.allSections).toEqual([])
    expect(store.activeMenu).toBe('')
    expect(store.loaded).toBe(false)
    expect(store.allSectionsLoaded).toBe(false)
    expect(store.allMenusLoadFailed).toBe(false)
    expect(store.allKeys.size).toBe(0)
    expect(store.canAccessMenu(DASHBOARD_MENU_KEY)).toBe(false)
  })

  it('setActive 修改当前激活菜单', () => {
    const store = useMenuStore()
    store.setActive('villages')
    expect(store.activeMenu).toBe('villages')
    store.setActive('a')
    store.setActive('b')
    expect(store.activeMenu).toBe('b')
  })

  describe('setMenus（v2 解析）', () => {
    it('解析 sections / flatEntries / allKeys（含 children 与 tabs.key）', () => {
      const store = useMenuStore()
      store.setMenus(V2_PAYLOAD)

      expect(store.sections).toHaveLength(2)
      expect(store.sections[0].key).toBe('business')
      expect(store.sections[1].label).toBe('系统管理')
      expect(store.menus).toEqual([])
      expect(store.loaded).toBe(true)
      expect(store.loading).toBe(false)
      expect(store.loadFailed).toBe(false)

      // flatEntries：工作台固定第一 → page → group children → console 自身 → console tabs
      expect(store.flatEntries.map((entry) => entry.key)).toEqual([
        'dashboard',
        'villages',
        'funds-admin',
        'system-console-org',
        'users-orgs',
      ])
      expect(store.flatEntries[2].parentKey).toBe('funds')
      expect(store.flatEntries[2].parentLabel).toBe('经费管理')
      expect(store.flatEntries[1].sectionLabel).toBe('帮扶业务')
      expect(store.flatEntries[3].kind).toBe('console')
      // R35：console 子项（tab）也进入扁平列表，带 parent 与 tabKey 供 “?tab=” 跳转
      expect(store.flatEntries[4].tabKey).toBe('users-orgs')
      expect(store.flatEntries[4].parentKey).toBe('system-console-org')
      expect(store.flatEntries[4].parentLabel).toBe('组织与权限')
      expect(store.flatEntries[4].path).toBe('/system/console/org')

      // allKeys：后端 flat_keys ∪ 工作台 ∪ 结构 key ∪ tabs.key
      for (const key of [
        'dashboard',
        'villages',
        'funds',
        'funds-admin',
        'system-console-org',
        'users-orgs',
      ]) {
        expect(store.allKeys.has(key), `缺少 key: ${key}`).toBe(true)
      }
      expect(store.accessibleKeys.has('users-orgs')).toBe(true)
      expect(store.canAccessMenu('users-orgs')).toBe(true)
    })

    it('非 v2 对象（无 sections 字段）按空板块处理', () => {
      const store = useMenuStore()
      store.setMenus({ data: V2_PAYLOAD } as unknown as MenuPayloadV2)
      // 直接 setMenus 不做信封解包（信封解包在 fetchMenus），故无 sections → 空板块
      expect(store.sections).toEqual([])
      expect(store.loaded).toBe(true)
    })

    it('脏数据条目被过滤，且 label/icon/order 缺失时降级', () => {
      const store = useMenuStore()
      store.setMenus(MALFORMED_PAYLOAD)

      expect(store.sections).toHaveLength(1)
      const items = store.sections[0].items
      expect(items.map((item) => item.key)).toEqual([
        'grp-dirty',
        'console-dirty',
        'no-label-page',
        'console-no-path',
        'page-no-path',
      ])
      expect(items[0].kind).toBe('group')
      expect(items[0].children?.map((child) => child.key)).toEqual(['ok-child'])
      expect(items[1].kind).toBe('console')
      expect(items[1].tabs?.map((tab) => tab.key)).toEqual(['tab-ok'])
      // label 缺失回退 key；icon/order 非预期类型降级为 undefined
      expect(items[2].label).toBe('no-label-page')
      expect(items[2].icon).toBeUndefined()
      expect(items[2].order).toBeUndefined()
      // 无 path 的 page/console 不进入扁平可导航列表
      expect(store.flatEntries.map((entry) => entry.key)).toEqual([
        'dashboard',
        'ok-child',
        'console-dirty',
        'tab-ok',
        'no-label-page',
      ])
      // flat_keys 非字符串项被过滤，合法项并入 allKeys
      expect(store.allKeys.has('dirty')).toBe(true)
      expect(store.allKeys.has('7')).toBe(false)
    })

    it('console 有 path 但无 tabs → 只产出聚合页自身扁平项（不展开子项）', () => {
      const store = useMenuStore()
      store.setMenus({
        sections: [
          {
            key: 'system',
            label: '系统管理',
            order: 90,
            items: [
              {
                key: 'system-console-empty-tabs',
                label: '空聚合页',
                path: '/system/console/empty',
                kind: 'console',
                order: 10,
              },
            ],
          },
        ],
        flat_keys: [],
      })

      expect(store.flatEntries.map((entry) => entry.key)).toEqual([
        'dashboard',
        'system-console-empty-tabs',
      ])
      expect(store.flatEntries[1].tabKey).toBeUndefined()
    })

    it('sections/flat_keys 均非数组时按空处理', () => {
      const store = useMenuStore()
      store.setMenus({ sections: 'nope', flat_keys: {} } as unknown as MenuPayloadV2)
      expect(store.sections).toEqual([])
      expect(store.flatEntries).toEqual([DASHBOARD_FLAT_ENTRY])
      expect(store.loaded).toBe(true)
    })

    it('label 缺失的板块/入口/tab 回退 key', () => {
      const store = useMenuStore()
      store.setMenus({
        sections: [
          {
            key: 'sec',
            items: [
              { key: 'grp', kind: 'group', children: [{ key: 'child', path: '/c' }] },
              {
                key: 'con',
                kind: 'console',
                path: '/con',
                tabs: [{ key: 'tab', path: '/t' }],
              },
            ],
          },
        ],
      })
      expect(store.sections[0].label).toBe('sec')
      expect(store.sections[0].items[0].label).toBe('grp')
      const group = store.sections[0].items[0]
      expect(group.children?.[0].label).toBe('child')
      const consoleEntry = store.sections[0].items[1]
      expect(consoleEntry.tabs?.[0].label).toBe('tab')
    })

    it('null/undefined 入参按空菜单处理', () => {
      const store = useMenuStore()
      store.setMenus(null)
      expect(store.sections).toEqual([])
      expect(store.loaded).toBe(true)
      store.setMenus(undefined)
      expect(store.flatEntries).toEqual([DASHBOARD_FLAT_ENTRY])
      expect(store.loadFailed).toBe(false)
    })
  })

  describe('setMenus（旧数组结构降级）', () => {
    it('旧数组结构折叠为单板块（group/page，递归 children）', () => {
      const store = useMenuStore()
      store.setMenus([
        { key: 'dashboard', label: '工作台', path: '/dashboard' },
        {
          key: 'system',
          label: '系统管理',
          children: [{ key: 'users-orgs', label: '用户与组织', path: '/system/users' }],
        },
      ])
      expect(store.menus).toHaveLength(2)
      expect(store.sections).toHaveLength(1)
      expect(store.sections[0].key).toBe('legacy')
      expect(store.sections[0].label).toBe('全部菜单')
      expect(store.sections[0].items.map((item) => item.kind)).toEqual(['page', 'group'])
      // 旧树里「无 path 且无 children」的脏节点被丢弃
      const legacyKeys = [...store.allKeys]
      expect(legacyKeys).toContain('dashboard')
      expect(legacyKeys).toContain('system')
      expect(legacyKeys).toContain('users-orgs')
    })

    it('旧数组结构脏节点被过滤（缺 key），无 path/无 label 节点降级保留', () => {
      const store = useMenuStore()
      store.setMenus([
        null as any,
        [] as any,
        { label: '缺 key' } as any,
        { key: 'no-path', label: '空节点' },
        { key: 'ok', label: 'OK', path: '/ok', icon: 'Location', order: 3 },
        { key: 'no-label', path: '/no-label' },
      ])
      // 无 path 节点仍在 sections（保证 allKeys 兼容旧权限配置），但不进入 flatEntries
      expect(store.sections[0].items.map((item) => item.key)).toEqual(['no-path', 'ok', 'no-label'])
      expect(store.sections[0].items[0].path).toBeUndefined()
      // label 缺失回退 key
      expect(store.sections[0].items[2].label).toBe('no-label')
      expect(store.flatEntries.map((entry) => entry.key)).toEqual(['dashboard', 'ok', 'no-label'])
      expect(store.allKeys.has('no-path')).toBe(true)
      expect(store.sections[0].items[1].order).toBe(3)
    })

    it('空数组不产生板块', () => {
      const store = useMenuStore()
      store.setMenus([])
      expect(store.sections).toEqual([])
      expect(store.flatEntries).toEqual([DASHBOARD_FLAT_ENTRY])
      expect(store.loaded).toBe(true)
    })
  })

  describe('setOrgPolicies / 模块策略', () => {
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

    it('canEditModule：无策略 true / full_edit true / read_only false / disabled false', () => {
      const store = useMenuStore()
      expect(store.canEditModule('schools')).toBe(true)
      store.setOrgPolicies([
        { module_key: 'schools', visibility: 'visible', edit_mode: 'full_edit' },
        { module_key: 'funds', visibility: 'visible', edit_mode: 'read_only' },
        { module_key: 'projects', visibility: 'visible', edit_mode: 'disabled' },
      ])
      expect(store.canEditModule('schools')).toBe(true)
      expect(store.canEditModule('funds')).toBe(false)
      expect(store.canEditModule('projects')).toBe(false)
    })

    it('isModuleDisabled：disabled/hidden true，其余 false，无策略 false', () => {
      const store = useMenuStore()
      expect(store.isModuleDisabled('a')).toBe(false)
      store.setOrgPolicies([
        { module_key: 'a', visibility: 'visible', edit_mode: 'disabled' },
        { module_key: 'b', visibility: 'hidden', edit_mode: 'full_edit' },
        { module_key: 'c', visibility: 'visible', edit_mode: 'full_edit' },
      ])
      expect(store.isModuleDisabled('a')).toBe(true)
      expect(store.isModuleDisabled('b')).toBe(true)
      expect(store.isModuleDisabled('c')).toBe(false)
    })
  })

  describe('canAccessMenu', () => {
    it('菜单未加载时返回 false（loaded 优先）', () => {
      const store = useMenuStore()
      expect(store.canAccessMenu('dashboard')).toBe(false)
    })

    it('模块策略 hidden 时返回 false', () => {
      const store = useMenuStore()
      store.setMenus([{ key: 'dashboard', label: 'D' }])
      store.setOrgPolicies([
        { module_key: 'dashboard', visibility: 'hidden', edit_mode: 'full_edit' },
      ])
      expect(store.canAccessMenu('dashboard')).toBe(false)
    })

    it('未命中组织策略时按 allKeys 判定', () => {
      const store = useMenuStore()
      store.setMenus([{ key: 'dashboard', label: 'D' }])
      store.setOrgPolicies([{ module_key: 'other', visibility: 'hidden', edit_mode: 'full_edit' }])
      expect(store.canAccessMenu('dashboard')).toBe(true)
      expect(store.canAccessMenu('nope')).toBe(false)
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
      let resolveGet!: (v: unknown) => void
      mockGet.mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveGet = resolve
          })
      )
      const store = useMenuStore()
      const p1 = store.fetchMenus()
      const p2 = store.fetchMenus()
      expect(mockGet).toHaveBeenCalledTimes(1)
      resolveGet({ data: V2_PAYLOAD })
      await Promise.all([p1, p2])
      expect(store.loaded).toBe(true)
      expect(store.sections).toHaveLength(2)
    })

    it('成功（{ data: v2 } 信封）时写入 sections 并更新状态', async () => {
      mockGet.mockResolvedValueOnce({ data: V2_PAYLOAD })
      const store = useMenuStore()
      await store.fetchMenus()
      expect(mockGet).toHaveBeenCalledWith('/menus/accessible')
      expect(store.sections).toHaveLength(2)
      // 3 个普通条目 + console 自身 + 1 个 console tab
      expect(store.flatEntries.length).toBe(5)
      expect(store.loaded).toBe(true)
      expect(store.loading).toBe(false)
      expect(store.loadFailed).toBe(false)
    })

    it('成功（裸 v2 payload）时写入 sections', async () => {
      mockGet.mockResolvedValueOnce(V2_PAYLOAD)
      const store = useMenuStore()
      await store.fetchMenus()
      expect(store.sections).toHaveLength(2)
      expect(store.loaded).toBe(true)
    })

    it('成功（旧数组结构）时走降级分支', async () => {
      mockGet.mockResolvedValueOnce([{ key: 'dashboard', label: 'D', path: '/dashboard' }])
      const store = useMenuStore()
      await store.fetchMenus()
      expect(store.menus).toHaveLength(1)
      expect(store.sections).toHaveLength(1)
      expect(store.loaded).toBe(true)
    })

    it('成功但数据为空对象时置空菜单', async () => {
      mockGet.mockResolvedValueOnce({ data: { items: [] } })
      const store = useMenuStore()
      await store.fetchMenus()
      expect(store.sections).toEqual([])
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
      expect(store.sections).toEqual([])
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

  describe('fetchAllMenus（管理员全量菜单，权限面板数据源）', () => {
    it('无 token 时返回空数组且不发请求', async () => {
      mockGetToken.mockReturnValue(null)
      const store = useMenuStore()
      await expect(store.fetchAllMenus()).resolves.toEqual([])
      expect(mockGet).not.toHaveBeenCalled()
      expect(store.allSectionsLoaded).toBe(false)
    })

    it('成功（{ data: v2 }）时写入 allSections，不影响用户 sections', async () => {
      mockGet.mockResolvedValueOnce({ data: V2_PAYLOAD })
      const store = useMenuStore()
      store.setMenus(V2_PAYLOAD)
      const sections = await store.fetchAllMenus()

      expect(mockGet).toHaveBeenCalledWith('/menus/all')
      expect(sections).toHaveLength(2)
      expect(store.allSections).toHaveLength(2)
      expect(store.allSectionsLoaded).toBe(true)
      expect(store.allMenusLoadFailed).toBe(false)
      // 用户可见 sections 不被全量菜单覆盖
      expect(store.sections).toHaveLength(2)
    })

    it('成功（裸 v2 payload）时同样解析', async () => {
      mockGet.mockResolvedValueOnce(V2_PAYLOAD)
      const store = useMenuStore()
      const sections = await store.fetchAllMenus()
      expect(sections).toHaveLength(2)
      expect(store.allSectionsLoaded).toBe(true)
    })

    it('旧数组结构响应走降级分支', async () => {
      mockGet.mockResolvedValueOnce([{ key: 'dashboard', label: 'D', path: '/dashboard' }])
      const store = useMenuStore()
      const sections = await store.fetchAllMenus()
      expect(sections).toHaveLength(1)
      expect(sections[0].key).toBe('legacy')
    })

    it('并发调用共享同一请求', async () => {
      let resolveGet!: (v: unknown) => void
      mockGet.mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveGet = resolve
          })
      )
      const store = useMenuStore()
      const p1 = store.fetchAllMenus()
      const p2 = store.fetchAllMenus()
      expect(mockGet).toHaveBeenCalledTimes(1)
      resolveGet({ data: V2_PAYLOAD })
      const [a, b] = await Promise.all([p1, p2])
      expect(a).toHaveLength(2)
      expect(b).toHaveLength(2)
    })

    it('请求失败时返回空数组并标记 allMenusLoadFailed', async () => {
      mockGet.mockRejectedValueOnce(new Error('forbidden'))
      const store = useMenuStore()
      await expect(store.fetchAllMenus()).resolves.toEqual([])
      expect(store.allMenusLoadFailed).toBe(true)
      expect(store.allSectionsLoaded).toBe(false)
    })

    it('响应为 falsy 值（如 0）时按空板块处理', async () => {
      mockGet.mockResolvedValueOnce(0)
      const store = useMenuStore()
      await expect(store.fetchAllMenus()).resolves.toEqual([])
      expect(store.allSections).toEqual([])
      expect(store.allSectionsLoaded).toBe(true)
    })

    it('失败后重试成功会清除失败标记', async () => {
      mockGet.mockRejectedValueOnce(new Error('forbidden'))
      mockGet.mockResolvedValueOnce({ data: V2_PAYLOAD })
      const store = useMenuStore()
      await store.fetchAllMenus()
      expect(store.allMenusLoadFailed).toBe(true)
      await store.fetchAllMenus()
      expect(store.allMenusLoadFailed).toBe(false)
      expect(store.allSectionsLoaded).toBe(true)
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

  describe('DASHBOARD 常量与 sections 边界', () => {
    it('DASHBOARD_FLAT_ENTRY 描述工作台固定入口', () => {
      expect(DASHBOARD_FLAT_ENTRY).toMatchObject({
        key: 'dashboard',
        label: '工作台',
        path: '/dashboard',
        kind: 'page',
      })
      expect(DASHBOARD_MENU_KEY).toBe('dashboard')
    })

    it('空板块被过滤，dashboard 始终在 flatEntries/allKeys 中', () => {
      const store = useMenuStore()
      store.setMenus({ sections: [{ key: 'empty', items: [] }] })
      expect(store.sections).toEqual([])
      expect(store.flatEntries[0].key).toBe('dashboard')
      expect(store.allKeys.has('dashboard')).toBe(true)
    })

    it('setMenus 清理 loading / loadFailed', () => {
      const store = useMenuStore()
      store.loading = true
      store.loadFailed = true
      store.setMenus([] as MenuSection[])
      expect(store.loaded).toBe(true)
      expect(store.loading).toBe(false)
      expect(store.loadFailed).toBe(false)
    })
  })
})
