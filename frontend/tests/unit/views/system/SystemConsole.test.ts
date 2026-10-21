/**
 * views/system/console/SystemConsole.vue 专属测试（契约 §5/§8，四指标 100%）
 *
 * 单执行者规程：SystemConsole.vue 全仓只能被本文件执行。
 * - 契约 §5 的全部 Tab 子组件（W22 删 i18n/email 后 28 个）都在本文件用 `vi.mock` 工厂替换为桩组件
 *   （工厂不加载真实 .vue），真实子页仍由各自专属测试唯一执行；
 * - 另用 defineAsyncComponent 懒加载的 loader 为模块级函数：本文件通过遍历
 *   6 个板块的全部 Tab 各渲染一次，确保每个 loader 都被执行（functions 100%）。
 *
 * 覆盖：group 解析、可见 Tab 过滤（无映射 key 剔除）、query.tab 初始化/数组形态/
 * 非法值回退、切换 Tab 的 router.replace query 同步与"仅渲染当前 Tab"、未知 group、
 * 无权限（sections 无 console 节点）、无可渲染 Tab、菜单未加载兜底 fetchMenus
 * （成功/在途/失败）、返回工作台按钮。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises, enableAutoUnmount, config } from '@vue/test-utils'
import { reactive } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'

enableAutoUnmount(afterEach)

// setup.ts 为全局注入了一个 stub router；本文件每个用例自行安装带
// 目标路由表的真实 router，两个 router 插件同时 use 会重复 defineProperty($route)，
// 故仅在本文件清空全局插件列表。
config.global.plugins = []

// ── 可提升状态：mock 工厂里只能用 hoisted 变量 ──
const hoisted = vi.hoisted(() => {
  const loadedModules: string[] = []
  const menuState: { store: any } = { store: null }
  const makeStub = (name: string) => ({ name: `${name}Stub`, render: () => null })
  return { loadedModules, menuState, makeStub }
})

// ── store mock：SystemConsole 只消费 loaded/loading/sections/fetchMenus ──
vi.mock('@/stores/menu', () => ({ useMenuStore: () => hoisted.menuState.store }))

// ── 契约 §5：全部 Tab 子组件桩（W22 删 i18n/email 后 28 个），工厂执行即记录"模块被加载" ──
vi.mock('@/views/system/UserManagement.vue', () => {
  hoisted.loadedModules.push('UserManagement')
  return { __esModule: true, default: hoisted.makeStub('UserManagement') }
})
vi.mock('@/views/system/Role.vue', () => {
  hoisted.loadedModules.push('Role')
  return { __esModule: true, default: hoisted.makeStub('Role') }
})
vi.mock('@/views/system/Menu.vue', () => {
  hoisted.loadedModules.push('Menu')
  return { __esModule: true, default: hoisted.makeStub('Menu') }
})
vi.mock('@/views/system/PermissionPacks.vue', () => {
  hoisted.loadedModules.push('PermissionPacks')
  return { __esModule: true, default: hoisted.makeStub('PermissionPacks') }
})
vi.mock('@/views/organization/List.vue', () => {
  hoisted.loadedModules.push('OrganizationList')
  return { __esModule: true, default: hoisted.makeStub('OrganizationList') }
})
vi.mock('@/views/system/OrgGrant.vue', () => {
  hoisted.loadedModules.push('OrgGrant')
  return { __esModule: true, default: hoisted.makeStub('OrgGrant') }
})
vi.mock('@/views/system/GrantImport.vue', () => {
  hoisted.loadedModules.push('GrantImport')
  return { __esModule: true, default: hoisted.makeStub('GrantImport') }
})
vi.mock('@/views/system/AuditManagement.vue', () => {
  hoisted.loadedModules.push('AuditManagement')
  return { __esModule: true, default: hoisted.makeStub('AuditManagement') }
})
vi.mock('@/views/system/ZeroTrust.vue', () => {
  hoisted.loadedModules.push('ZeroTrust')
  return { __esModule: true, default: hoisted.makeStub('ZeroTrust') }
})
vi.mock('@/views/system/SecretsManagement.vue', () => {
  hoisted.loadedModules.push('SecretsManagement')
  return { __esModule: true, default: hoisted.makeStub('SecretsManagement') }
})
vi.mock('@/views/system/DataTier.vue', () => {
  hoisted.loadedModules.push('DataTier')
  return { __esModule: true, default: hoisted.makeStub('DataTier') }
})
vi.mock('@/views/system/EncryptionSettings.vue', () => {
  hoisted.loadedModules.push('EncryptionSettings')
  return { __esModule: true, default: hoisted.makeStub('EncryptionSettings') }
})
vi.mock('@/views/admin/MachineCodeManagement.vue', () => {
  hoisted.loadedModules.push('MachineCodeManagement')
  return { __esModule: true, default: hoisted.makeStub('MachineCodeManagement') }
})
vi.mock('@/views/system/SettingsOverview.vue', () => {
  hoisted.loadedModules.push('SettingsOverview')
  return { __esModule: true, default: hoisted.makeStub('SettingsOverview') }
})
vi.mock('@/views/system/HealthCheck.vue', () => {
  hoisted.loadedModules.push('HealthCheck')
  return { __esModule: true, default: hoisted.makeStub('HealthCheck') }
})
vi.mock('@/views/system/MonitoringDashboard.vue', () => {
  hoisted.loadedModules.push('MonitoringDashboard')
  return { __esModule: true, default: hoisted.makeStub('MonitoringDashboard') }
})
vi.mock('@/views/system/CacheManagement.vue', () => {
  hoisted.loadedModules.push('CacheManagement')
  return { __esModule: true, default: hoisted.makeStub('CacheManagement') }
})
vi.mock('@/views/system/TaskManager.vue', () => {
  hoisted.loadedModules.push('TaskManager')
  return { __esModule: true, default: hoisted.makeStub('TaskManager') }
})
vi.mock('@/views/system/EnvCheck.vue', () => {
  hoisted.loadedModules.push('EnvCheck')
  return { __esModule: true, default: hoisted.makeStub('EnvCheck') }
})
vi.mock('@/views/system/ErrorReports.vue', () => {
  hoisted.loadedModules.push('ErrorReports')
  return { __esModule: true, default: hoisted.makeStub('ErrorReports') }
})
vi.mock('@/views/system/BackupManagement.vue', () => {
  hoisted.loadedModules.push('BackupManagement')
  return { __esModule: true, default: hoisted.makeStub('BackupManagement') }
})
vi.mock('@/views/system/ChunkedUploadManager.vue', () => {
  hoisted.loadedModules.push('ChunkedUploadManager')
  return { __esModule: true, default: hoisted.makeStub('ChunkedUploadManager') }
})
vi.mock('@/views/system/MapTileManager.vue', () => {
  hoisted.loadedModules.push('MapTileManager')
  return { __esModule: true, default: hoisted.makeStub('MapTileManager') }
})
vi.mock('@/views/system/ControlPackage.vue', () => {
  hoisted.loadedModules.push('ControlPackage')
  return { __esModule: true, default: hoisted.makeStub('ControlPackage') }
})
vi.mock('@/views/system/ConfigPackage.vue', () => {
  hoisted.loadedModules.push('ConfigPackage')
  return { __esModule: true, default: hoisted.makeStub('ConfigPackage') }
})
vi.mock('@/views/system/UpdateLogs.vue', () => {
  hoisted.loadedModules.push('UpdateLogs')
  return { __esModule: true, default: hoisted.makeStub('UpdateLogs') }
})
vi.mock('@/views/system/About.vue', () => {
  hoisted.loadedModules.push('About')
  return { __esModule: true, default: hoisted.makeStub('About') }
})
vi.mock('@/views/system/Feedback.vue', () => {
  hoisted.loadedModules.push('Feedback')
  return { __esModule: true, default: hoisted.makeStub('Feedback') }
})
vi.mock('@/views/help/HelpCenter.vue', () => {
  hoisted.loadedModules.push('HelpCenter')
  return { __esModule: true, default: hoisted.makeStub('HelpCenter') }
})
vi.mock('@/views/admin/AdminDashboard.vue', () => {
  hoisted.loadedModules.push('AdminDashboard')
  return { __esModule: true, default: hoisted.makeStub('AdminDashboard') }
})

import SystemConsole from '@/views/system/console/SystemConsole.vue'

// ── 契约 §4/§5 测试夹具：6 个板块的 console 节点与 tabs（key 与组件映射一一对应）──
const GROUP_TABS: Record<string, string[]> = {
  org: [
    'users-orgs',
    'roles',
    'menus',
    'system-permission-packs',
    'organizations',
    'system-org-grant',
    'system-grant-import',
  ],
  security: ['audit', 'zero-trust', 'secrets', 'data-tier', 'encryption', 'machine-code'],
  ops: [
    'system-overview',
    'health-check',
    'monitor',
    'cache',
    'tasks',
    'environment',
    'error-reports',
  ],
  storage: ['backup', 'chunked-upload', 'map-tiles', 'control-package', 'config-package'],
  settings: ['update-logs'],
  about: ['about', 'feedback', 'help', 'admin-dashboard'],
}

const GROUP_LABELS: Record<string, string> = {
  org: '组织与权限',
  security: '安全与审计',
  ops: '运维与监控',
  storage: '备份与存储',
  settings: '系统设置',
  about: '关于与反馈',
}

/** 无前端组件映射的 Tab key（后端下发未知 key 时的防御分支） */
const UNMAPPED_TAB = 'unknown-tab'

/** 全部 30 个真实 Tab key（UNMAPPED_TAB 除外；含 R33 单位授权 2 个） */
const ALL_TAB_KEYS = Object.values(GROUP_TABS).flat()

function buildSections() {
  return [
    {
      key: 'system',
      label: '系统管理',
      order: 90,
      items: [
        ...Object.keys(GROUP_TABS).map((group, index) => ({
          key: `system-console-${group}`,
          label: GROUP_LABELS[group],
          path: `/system/console/${group}`,
          kind: 'console',
          order: index,
          tabs: [
            ...GROUP_TABS[group].map((tabKey, tabIndex) => ({
              key: tabKey,
              label: `${tabKey}页签`,
              path: `/tab/${tabKey}`,
              order: tabIndex,
            })),
            // 只有 ops 板块额外带一个无映射 key，覆盖"过滤不可渲染 Tab"分支
            ...(group === 'ops'
              ? [{ key: UNMAPPED_TAB, label: '未映射页签', path: '/tab/unknown', order: 99 }]
              : []),
          ],
        })),
        // 同 section 下的普通 page 条目：覆盖 consoleNode 查找中 kind !== 'console' 分支
        { key: 'dashboard-entry', label: '工作台入口', path: '/dashboard', kind: 'page' },
      ],
    },
  ]
}

function makeStore(overrides: Record<string, any> = {}) {
  // 必须用 reactive：组件 computed 依赖 loaded/sections 的变更重新求值
  return reactive({
    loaded: true,
    loading: false,
    sections: buildSections(),
    fetchMenus: vi.fn().mockResolvedValue(undefined),
    canAccessMenu: vi.fn(() => true),
    ...overrides,
  })
}

// ── 最小 router：提供 useRoute/useRouter 与 pushSafe('/dashboard') 的目标路由 ──
const NoopPage = { name: 'NoopPage', render: () => null }

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/dashboard', name: 'Dashboard', component: NoopPage },
      { path: '/system/console/:group', name: 'SystemConsoleRoute', component: NoopPage },
      { path: '/:pathMatch(.*)*', name: 'NotFound', component: NoopPage },
    ],
  })
}

// ── Element Plus 桩（与仓内既有 .test.ts 相同的 template 桩写法）──
const ElButtonStub = {
  name: 'ElButtonStub',
  emits: ['click'],
  template: '<button class="stub-btn" @click="$emit(\'click\')"><slot /></button>',
}

const ElTabsStub = {
  name: 'ElTabsStub',
  props: ['modelValue'],
  emits: ['update:modelValue'],
  template: '<div class="tabs-stub"><slot /></div>',
}

const ElTabPaneStub = {
  name: 'ElTabPaneStub',
  props: ['label', 'name'],
  template:
    '<div class="tab-pane-stub" :data-name="name">' +
    '<span class="tab-label">{{ label }}</span><slot /></div>',
}

const ElSkeletonStub = {
  name: 'ElSkeletonStub',
  template: '<div class="skeleton-stub" />',
}

const ElEmptyStub = {
  name: 'ElEmptyStub',
  props: ['description'],
  template: '<div class="empty-stub">{{ description }}<slot /></div>',
}

const MOUNT_STUBS = {
  'el-tabs': ElTabsStub,
  'el-tab-pane': ElTabPaneStub,
  'el-skeleton': ElSkeletonStub,
  'el-empty': ElEmptyStub,
  'el-button': ElButtonStub,
}

/** 挂载并等待异步 Tab 组件解析完成 */
async function mountAt(path: string, store = makeStore()) {
  hoisted.menuState.store = store
  const router = makeRouter()
  await router.push(path)
  await router.isReady()
  const wrapper = mount(SystemConsole, {
    global: { plugins: [router], stubs: MOUNT_STUBS },
  })
  await flushPromises()
  await flushPromises()
  return { wrapper, router, store }
}

const pane = (wrapper: any, key: string) =>
  wrapper.find(`[data-testid="system-console-pane-${key}"]`)

beforeEach(() => {
  hoisted.menuState.store = makeStore()
})

afterEach(() => {
  vi.clearAllMocks()
})

describe('Tab 懒加载与切换（query.tab 同步）', () => {
  it('仅加载当前 Tab 组件；切换 Tab 用 router.replace 同步 query 且只渲染当前 Tab', async () => {
    const store = makeStore()
    hoisted.menuState.store = store
    const router = makeRouter()
    await router.push('/system/console/ops')
    await router.isReady()
    const wrapper = mount(SystemConsole, {
      global: { plugins: [router], stubs: MOUNT_STUBS },
    })
    await flushPromises()
    await flushPromises()

    // 默认第一个 Tab（system-overview），只加载其对应模块
    expect(pane(wrapper, 'system-overview').exists()).toBe(true)
    expect(hoisted.loadedModules).toEqual(['SettingsOverview'])
    // 其余 Tab 模块不得被提前加载（避免一次性加载全部系统页）
    expect(hoisted.loadedModules).not.toContain('MonitoringDashboard')
    expect(hoisted.loadedModules).not.toContain('BackupManagement')
    expect(hoisted.loadedModules).not.toContain('HelpCenter')
    expect(store.fetchMenus).not.toHaveBeenCalled() // loaded=true → 不主动请求

    const replaceSpy = vi.spyOn(router, 'replace')
    wrapper.findComponent({ name: 'ElTabsStub' }).vm.$emit('update:modelValue', 'monitor')
    await flushPromises()
    await flushPromises()

    expect(replaceSpy).toHaveBeenCalledTimes(1)
    expect(replaceSpy.mock.calls[0][0]).toMatchObject({
      path: '/system/console/ops',
      query: { tab: 'monitor' },
    })
    expect(router.currentRoute.value.query.tab).toBe('monitor')
    expect(pane(wrapper, 'monitor').exists()).toBe(true)
    expect(pane(wrapper, 'system-overview').exists()).toBe(false)
    // 切换后才加载新 Tab 的模块
    expect(hoisted.loadedModules).toContain('MonitoringDashboard')
    expect(hoisted.loadedModules).toHaveLength(2)
  })
})

describe('group 解析与可见 Tab', () => {
  it('按 group 定位 console 节点，标题取节点 label，默认选中第一个 Tab', async () => {
    const { wrapper } = await mountAt('/system/console/org')

    expect(wrapper.find('[data-testid="system-console-title"]').text()).toBe('组织与权限')
    expect(wrapper.find('[data-testid="system-console-description"]').text()).toContain(
      '用户、角色、菜单、权限包与组织架构'
    )
    // 可见 tabs = 后端下发的 5 个（全部有组件映射）
    expect(wrapper.findAll('.tab-label').map((n) => n.text())).toEqual(
      GROUP_TABS.org.map((key) => `${key}页签`)
    )
    expect((wrapper.vm as any).currentTab).toBe('users-orgs')
    expect(pane(wrapper, 'users-orgs').exists()).toBe(true)
    expect(pane(wrapper, 'roles').exists()).toBe(false)
  })

  it('query.tab 指定合法 Tab 时直接选中对应 Tab（不 replace）', async () => {
    const router = makeRouter()
    await router.push('/system/console/org?tab=menus')
    await router.isReady()
    hoisted.menuState.store = makeStore()
    const replaceSpy = vi.spyOn(router, 'replace')
    const wrapper = mount(SystemConsole, {
      global: { plugins: [router], stubs: MOUNT_STUBS },
    })
    await flushPromises()
    await flushPromises()

    expect(pane(wrapper, 'menus').exists()).toBe(true)
    expect(pane(wrapper, 'users-orgs').exists()).toBe(false)
    expect(replaceSpy).not.toHaveBeenCalled()
  })

  it('非法 query.tab / 无组件映射的 Tab 被过滤，并回退首个可见 Tab', async () => {
    // 非法 key
    const invalid = await mountAt('/system/console/org?tab=not-exist')
    expect((invalid.wrapper.vm as any).currentTab).toBe('users-orgs')

    // 后端下发了前端无映射的 key：不渲染该 tab，数量仍为 7（ops 真实 tab 数）
    const unmapped = await mountAt(`/system/console/ops?tab=${UNMAPPED_TAB}`)
    expect(unmapped.wrapper.findAll('.tab-label')).toHaveLength(GROUP_TABS.ops.length)
    expect(unmapped.wrapper.text()).not.toContain('未映射页签')
    expect((unmapped.wrapper.vm as any).currentTab).toBe('system-overview')
  })

  it('query.tab 为数组形态（?tab=a&tab=b）时视为非法并回退首个 Tab', async () => {
    const { wrapper } = await mountAt('/system/console/org?tab=users-orgs&tab=roles')
    expect((wrapper.vm as any).currentTab).toBe('users-orgs')
    expect(pane(wrapper, 'users-orgs').exists()).toBe(true)
  })

  it('canAccessMenu 兜底过滤无权限 Tab；全部无权限 → 空态', async () => {
    // 部分无权限：roles 被 canAccessMenu 拒绝，其余 org 板块 Tab 全部保留
    const partial = makeStore()
    partial.canAccessMenu.mockImplementation((key: string) => key !== 'roles')
    const hidden = await mountAt('/system/console/org', partial)
    expect(hidden.wrapper.findAll('.tab-label')).toHaveLength(GROUP_TABS.org.length - 1)
    expect(hidden.wrapper.text()).not.toContain('roles页签')

    // 全部无权限：console 节点存在但无可见 Tab → 空态（标题仍取节点 label）
    const denied = makeStore()
    denied.canAccessMenu.mockReturnValue(false)
    const none = await mountAt('/system/console/org', denied)
    expect(none.wrapper.find('[data-testid="system-console-empty"]').exists()).toBe(true)
    expect(none.wrapper.find('[data-testid="system-console-title"]').text()).toBe('组织与权限')
  })
})

describe('空态：未知 group / 无权限 / 无可渲染 Tab', () => {
  it('未知 group → 空态 + 顶部返回工作台按钮跳转', async () => {
    const { wrapper, router } = await mountAt('/system/console/nope')

    expect(wrapper.find('[data-testid="system-console-empty"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="system-console-title"]').text()).toBe('未知板块')
    expect(wrapper.find('[data-testid="system-console-description"]').text()).toContain(
      '该板块不存在或已下线'
    )
    expect(wrapper.find('.tabs-stub').exists()).toBe(false)

    await wrapper.find('[data-testid="system-console-back"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/dashboard')
  })

  it('有权限板块但 sections 中无对应 console 节点 → 空态（标题取板块元数据），空态按钮回工作台', async () => {
    // 仅保留 org 板块，security 节点缺失
    const store = makeStore({ sections: buildSections() })
    store.sections[0].items = store.sections[0].items.filter(
      (item: any) => item.path !== '/system/console/security'
    )
    const { wrapper, router } = await mountAt('/system/console/security', store)

    expect(wrapper.find('[data-testid="system-console-empty"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="system-console-title"]').text()).toBe('安全与审计')
    expect(wrapper.find('[data-testid="system-console-description"]').text()).toContain(
      '审计日志、零信任'
    )

    await wrapper.find('[data-testid="system-console-empty-back"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/dashboard')
  })

  it('console 节点无 tabs → 空态；currentTab 取空集合兜底', async () => {
    const store = makeStore({
      sections: [
        {
          key: 'system',
          label: '系统管理',
          items: [
            {
              key: 'system-console-org',
              label: '组织与权限',
              path: '/system/console/org',
              kind: 'console',
            },
          ],
        },
      ],
    })
    const { wrapper } = await mountAt('/system/console/org', store)

    expect(wrapper.find('[data-testid="system-console-empty"]').exists()).toBe(true)
    // 无 Tab 时 currentTab 不被模板访问，这里显式取值覆盖 getter 的空集合分支
    expect((wrapper.vm as any).currentTab).toBeUndefined()
  })
})

describe('菜单加载兜底（深链/刷新场景）', () => {
  it('未加载且不在途 → fetchMenus 兜底；加载中先显示骨架，完成后渲染 Tab', async () => {
    let release!: () => void
    const gate = new Promise<void>((resolve) => {
      release = resolve
    })
    const store = makeStore({ loaded: false, sections: [] })
    store.fetchMenus.mockImplementation(async () => {
      await gate
      store.sections = buildSections()
      store.loaded = true
    })
    hoisted.menuState.store = store
    const router = makeRouter()
    await router.push('/system/console/org')
    await router.isReady()
    const wrapper = mount(SystemConsole, {
      global: { plugins: [router], stubs: MOUNT_STUBS },
    })

    // onMounted 已进入等待，booting 仍为 true → 骨架（不能误判为无权限）
    await flushPromises()
    expect(wrapper.find('.skeleton-stub').exists()).toBe(true)
    expect(store.fetchMenus).toHaveBeenCalledTimes(1)

    release()
    await flushPromises()
    await flushPromises()
    expect(wrapper.find('.skeleton-stub').exists()).toBe(false)
    expect(pane(wrapper, 'users-orgs').exists()).toBe(true)
  })

  it('未加载但已有请求在途（loading=true）→ 不重复 fetch，直接空态等待', async () => {
    const store = makeStore({ loaded: false, loading: true, sections: [] })
    const { wrapper } = await mountAt('/system/console/org', store)

    expect(store.fetchMenus).not.toHaveBeenCalled()
    expect(wrapper.find('[data-testid="system-console-empty"]').exists()).toBe(true)
  })

  it('fetchMenus 失败 → 吞掉异常并显示空态，不阻断页面', async () => {
    const store = makeStore({ loaded: false, sections: [] })
    store.fetchMenus.mockRejectedValue(new Error('network down'))
    const { wrapper } = await mountAt('/system/console/org', store)

    expect(store.fetchMenus).toHaveBeenCalledTimes(1)
    expect(wrapper.find('[data-testid="system-console-empty"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="system-console-title"]').text()).toBe('组织与权限')
  })
})

describe('契约 §5 组件映射完整性', () => {
  it('30 个 Tab key 全部懒加载并渲染对应组件（每个异步 loader 均被执行）', async () => {
    for (const [group, tabs] of Object.entries(GROUP_TABS)) {
      for (const tabKey of tabs) {
        const { wrapper, router } = await mountAt(`/system/console/${group}?tab=${tabKey}`)
        expect(router.currentRoute.value.query.tab).toBe(tabKey)
        expect(pane(wrapper, tabKey).exists()).toBe(true)
        wrapper.unmount()
      }
    }
    // 30 个 mock 模块工厂各被执行且仅被执行一次（每个 defineAsyncComponent loader 都跑过）
    expect(ALL_TAB_KEYS).toHaveLength(30)
    expect(hoisted.loadedModules).toHaveLength(30)
    expect(new Set(hoisted.loadedModules).size).toBe(30)
  })
})
