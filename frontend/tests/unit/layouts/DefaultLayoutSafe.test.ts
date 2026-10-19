/**
 * DefaultLayoutSafe.vue 测试 —— 布局唯一执行者（渲染全分支）
 *
 * 单一执行者规程：`src/layouts/DefaultLayoutSafe.vue` 全仓只允许本文件真实执行。
 * 其它可能触碰它的测试均已桩替换：
 * - tests/unit/router/router-index.test.ts（懒加载遍历）
 * - tests/unit/promptContract.test.ts（import('@/main') 初始导航）
 * 本文件内对其静态 import 的 MenuSearchDialog.vue / MobileBottomNav.vue 使用
 * `vi.mock` 桩掉（**不是 global.stubs**：stubs 只阻止渲染，仍会真实加载 SFC 模块，
 * 会与这两个组件各自的专属测试形成第二执行者 → fnMap 合并损坏 functions）。
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { markRaw, nextTick } from 'vue'
import { mount, enableAutoUnmount, flushPromises, type VueWrapper } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import DefaultLayoutSafe from '@/layouts/DefaultLayoutSafe.vue'
import { useMenuStore } from '@/stores/menu'
import { useMenuFavorites, resetMenuFavorites } from '@/composables/useMenuFavorites'
import { useRecentMenus, resetRecentMenus } from '@/composables/useRecentMenus'

enableAutoUnmount(afterEach)

// ── hoisted：所有 mock 状态（vi.mock 工厂需在模块提升阶段可访问） ──
const mocks = vi.hoisted(() => ({
  pushSafe: vi.fn(),
  route: {
    path: '/dashboard',
    fullPath: '/dashboard',
    meta: { title: '工作台' } as Record<string, unknown>,
  },
  auth: {
    user: null as null | { username?: string; full_name?: string },
    isAuthenticated: true,
    lockSession: vi.fn(),
    logout: vi.fn(),
  },
  lockOptions: null as null | { onLock: () => void },
  notification: vi.fn(),
  consumeLockDigest: vi.fn(() => false),
  markLockNow: vi.fn(),
  getUnreadCount: vi.fn(),
  get: vi.fn(),
  freezeRequests: vi.fn(),
  cancelAllRequests: vi.fn(),
  config: { theme: 'default', setTheme: vi.fn() },
  themeOptions: [
    { label: '军绿（默认）', value: 'default' },
    { label: '深色大屏', value: 'dark-bigscreen' },
    { label: '户外高对比', value: 'outdoor' },
  ],
}))

vi.mock('vue-router', async () => {
  // 真实 vue-router 的 route 是响应式的：用 reactive 包装以驱动组件内 watch/面包屑
  const { reactive } = await import('vue')
  mocks.route = reactive({
    path: '/dashboard',
    fullPath: '/dashboard',
    meta: { title: '工作台' } as Record<string, unknown>,
  })
  return {
    useRoute: () => mocks.route,
  }
})

vi.mock('@/composables/useRouterSafe', () => ({
  useRouterSafe: () => ({ pushSafe: (...args: any[]) => mocks.pushSafe(...args) }),
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => mocks.auth,
}))

vi.mock('@/stores/config', () => ({
  useConfigStore: () => mocks.config,
  THEME_OPTIONS: mocks.themeOptions,
}))

vi.mock('@/composables/useAutoLock', () => ({
  useAutoLock: (options: { onLock: () => void }) => {
    mocks.lockOptions = options
  },
}))

vi.mock('@/utils/lockDigest', () => ({
  consumeLockDigest: (...args: any[]) => mocks.consumeLockDigest(...args),
  markLockNow: (...args: any[]) => mocks.markLockNow(...args),
}))

vi.mock('element-plus', () => ({
  ElNotification: (...args: any[]) => mocks.notification(...args),
}))

vi.mock('@/api/message', () => ({
  getUnreadCount: (...args: any[]) => mocks.getUnreadCount(...args),
}))

vi.mock('@/api/request', () => ({
  get: (...args: any[]) => mocks.get(...args),
  getCsrfToken: vi.fn(() => Promise.resolve('test-csrf')),
  freezeRequests: () => mocks.freezeRequests(),
  cancelAllRequests: () => mocks.cancelAllRequests(),
}))

vi.mock('@/utils/authStorage', () => ({
  AuthStorage: { getToken: () => 'token' },
}))

// 静态 import 的两个子 .vue 一律桩掉（各自有专属测试 = 各自唯一执行者）
vi.mock('@/components/layout/MobileBottomNav.vue', () => ({
  default: { name: 'MobileBottomNav', template: '<div class="mobile-nav-stub" />' },
}))
vi.mock('@/components/nav/MenuSearchDialog.vue', () => ({
  default: {
    name: 'MenuSearchDialog',
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template: '<div class="menu-search-dialog-stub" />',
  },
}))
// W1 外观面板由 AppearanceSettings.test.ts 唯一真实执行，本文件只桩掉
vi.mock('@/components/settings/AppearanceSettings.vue', () => ({
  default: { name: 'AppearanceSettingsStub', template: '<div class="appearance-settings-stub" />' },
}))

/** 契约 §2 的最小 v2 数据：page + group + console + 未知图标/无图标 */
const V2_PAYLOAD = {
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
          kind: 'page',
        },
        {
          key: 'funds',
          label: '经费管理',
          icon: 'Money',
          kind: 'group',
          children: [
            {
              key: 'funds-admin',
              label: '经费台账',
              path: '/funds',
              icon: 'Money',
              kind: 'page',
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
          kind: 'console',
          tabs: [{ key: 'users-orgs', label: '用户与组织', path: '/system/users' }],
        },
        { key: 'strange', label: '未知图标', path: '/strange', icon: 'NoSuchIcon', kind: 'page' },
        { key: 'no-icon', label: '无图标', path: '/no-icon', kind: 'page' },
      ],
    },
  ],
  flat_keys: [
    'dashboard',
    'villages',
    'funds',
    'funds-admin',
    'system-console-org',
    'strange',
    'no-icon',
  ],
}

// ── matchMedia 可编程桩（setup.ts 的全局桩恒 matches:false，此处覆盖以测窄屏分支） ──
type MediaListener = (event: { matches: boolean }) => void
let mediaListeners: MediaListener[] = []
const mediaRemoveEventListener = vi.fn()

function installMatchMedia(matches: boolean) {
  mediaListeners = []
  vi.stubGlobal('matchMedia', (query: string) => ({
    matches,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: (_type: string, listener: MediaListener) => {
      mediaListeners.push(listener)
    },
    removeEventListener: mediaRemoveEventListener,
    dispatchEvent: vi.fn(),
  }))
}

// ── 布局内所有 Element Plus 组件桩（渲染默认插槽，便于断言数据驱动结构） ──
/** el-dropdown 桩：保留 name/emits，测试可直接对组件实例 emit('command') */
const ElDropdownStub = {
  name: 'ElDropdown',
  props: ['trigger'],
  emits: ['command'],
  template: '<div class="dropdown-stub"><slot /><slot name="dropdown" /></div>',
}

const layoutStubs: Record<string, any> = {
  'el-aside': {
    props: ['width'],
    template: '<aside class="aside-stub" :data-width="width"><slot /></aside>',
  },
  'el-scrollbar': { template: '<div class="scrollbar-stub"><slot /></div>' },
  'el-menu': {
    props: ['defaultActive', 'collapse'],
    template: '<nav class="menu-stub" :data-active="defaultActive"><slot /></nav>',
  },
  'el-menu-item': {
    props: ['index'],
    template: '<div class="menu-item-stub" :data-index="index"><slot name="title" /><slot /></div>',
  },
  'el-sub-menu': {
    props: ['index', 'popperClass'],
    template:
      '<div class="sub-menu-stub" :data-index="index"><slot name="title" /><div class="sub-inline"><slot /></div></div>',
  },
  'el-container': { template: '<section class="container-stub"><slot /></section>' },
  'el-header': { template: '<header class="header-stub"><slot /></header>' },
  'el-main': { template: '<main class="main-stub"><slot /></main>' },
  'el-footer': { template: '<footer class="footer-stub"><slot /></footer>' },
  'el-button': {
    props: ['icon', 'text'],
    emits: ['click'],
    template: '<button class="button-stub" @click="$emit(\'click\')"><slot /></button>',
  },
  'el-breadcrumb': { template: '<div class="breadcrumb-stub"><slot /></div>' },
  'el-breadcrumb-item': {
    props: ['to'],
    template: '<span class="breadcrumb-item-stub"><slot /></span>',
  },
  'el-tooltip': { template: '<span class="tooltip-stub"><slot /></span>' },
  'el-badge': {
    props: ['value', 'hidden', 'max'],
    template:
      '<span class="badge-stub" :data-value="value" :data-hidden="String(hidden)"><slot /></span>',
  },
  'el-dropdown': ElDropdownStub,
  'el-dropdown-menu': { template: '<div class="dropdown-menu-stub"><slot /></div>' },
  'el-dropdown-item': {
    props: ['command', 'divided'],
    template: '<div class="dropdown-item-stub"><slot /></div>',
  },
  'el-avatar': { template: '<span class="avatar-stub"><slot /></span>' },
  'el-icon': { template: '<i class="icon-stub"><slot /></i>' },
  'el-dialog': {
    name: 'ElDialog',
    props: ['modelValue', 'title', 'width'],
    emits: ['update:modelValue'],
    template: '<div v-if="modelValue" class="dialog-stub"><h3>{{ title }}</h3><slot /></div>',
  },
  CommonErrorBoundary: { template: '<div class="boundary-stub"><slot /></div>' },
}

interface MountOptions {
  /** false = 不预置菜单（模拟“尚未加载”，由 onMounted 拉取） */
  presetMenus?: boolean
  /** true = router-view 提供真实组件，覆盖 `<component :is>` 真分支 */
  routedView?: boolean
  /** false = 保持板块默认折叠状态（默认 true 供既有渲染断言使用） */
  expandAll?: boolean
}

async function mountLayout(options: MountOptions = {}): Promise<VueWrapper> {
  setActivePinia(createPinia())
  if (options.presetMenus !== false) {
    useMenuStore().setMenus(V2_PAYLOAD)
  }
  const routerViewStub = options.routedView
    ? {
        template: '<div class="router-view-stub"><slot :Component="viewComponent" /></div>',
        data: () => ({
          viewComponent: markRaw({
            name: 'RoutedView',
            template: '<span class="routed-view" />',
          }),
        }),
      }
    : { template: '<div class="router-view-stub"><slot :Component="null" /></div>' }
  const wrapper = mount(DefaultLayoutSafe, {
    global: {
      stubs: { ...layoutStubs, 'router-view': routerViewStub },
    },
  })
  await nextTick()
  await flushPromises()
  await nextTick()
  if (options.expandAll !== false) {
    for (const toggle of wrapper.findAll('.menu-section-toggle')) {
      await toggle.trigger('click')
    }
    await nextTick()
  }
  return wrapper
}

/** 按板块标题文本定位折叠开关 */
function sectionToggle(wrapper: VueWrapper, label: string) {
  const toggle = wrapper.findAll('.menu-section-toggle').find((node) => node.text().includes(label))
  expect(toggle, `板块「${label}」折叠开关`).toBeTruthy()
  return toggle!
}

/** 板块入口是否可见（v-show） */
function isVisible(wrapper: VueWrapper, index: string): boolean {
  const node = wrapper.find(`.menu-item-stub[data-index="${index}"]`)
  const style = node.attributes('style') ?? ''
  return node.exists() && !style.includes('display: none')
}

function menuIndexes(wrapper: VueWrapper): string[] {
  return wrapper.findAll('.menu-item-stub').map((item) => item.attributes('data-index') as string)
}

function sectionLabels(wrapper: VueWrapper): string[] {
  return wrapper.findAll('.menu-section-label').map((label) => label.text())
}

function dispatchKey(
  key: string,
  options: { ctrl?: boolean; shift?: boolean } = {},
  target: EventTarget = window
) {
  target.dispatchEvent(
    new KeyboardEvent('keydown', {
      key,
      ctrlKey: options.ctrl ?? false,
      shiftKey: options.shift ?? false,
      bubbles: true,
    })
  )
}

describe('DefaultLayoutSafe.vue（数据驱动导航）', () => {
  const originalLocationDescriptor = Object.getOwnPropertyDescriptor(window, 'location')

  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    resetMenuFavorites()
    resetRecentMenus()
    mocks.route.path = '/dashboard'
    mocks.route.fullPath = '/dashboard'
    mocks.route.meta = { title: '工作台' }
    mocks.auth.user = null
    mocks.auth.isAuthenticated = true
    mocks.config.theme = 'default'
    mocks.consumeLockDigest.mockReturnValue(false)
    mocks.get.mockResolvedValue({ data: V2_PAYLOAD })
    mocks.getUnreadCount.mockResolvedValue({ data: { total: 0 } })
    installMatchMedia(false)
    // 锁屏/登出使用 window.location.href 硬跳转：替换为可写桩便于断言
    Object.defineProperty(window, 'location', {
      configurable: true,
      writable: true,
      value: { href: '' },
    })
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
    if (originalLocationDescriptor) {
      Object.defineProperty(window, 'location', originalLocationDescriptor)
    }
  })

  // ══════════════════ 侧栏数据驱动 ══════════════════

  it('侧栏完全数据驱动：工作台固定第一 → 收藏 → 最近访问 → 板块（page/group/console）', async () => {
    useMenuFavorites().toggleFavorite({
      key: 'villages',
      label: '帮扶村管理',
      path: '/supported-villages',
    })
    // 已不可访问的收藏/历史：key 不在 allKeys 内 → 不渲染
    useMenuFavorites().toggleFavorite({ key: 'gone', label: '已下线', path: '/gone' })
    useRecentMenus().recordMenu({
      key: 'villages',
      label: '帮扶村管理',
      path: '/supported-villages',
    })
    useRecentMenus().recordMenu({ key: 'funds-admin', label: '经费台账', path: '/funds' })
    useRecentMenus().recordMenu({ key: 'gone', label: '已下线', path: '/gone' })

    const wrapper = await mountLayout()

    // 收藏 + 最近访问 + 两个板块
    expect(sectionLabels(wrapper)).toEqual(['收藏', '最近访问', '帮扶业务', '系统管理'])

    // 工作台固定第一
    const indexes = menuIndexes(wrapper)
    expect(indexes[0]).toBe('/dashboard')
    // 收藏区渲染可访问项；最近访问剔除已收藏项与不可访问项
    expect(indexes.slice(0, 3)).toEqual(['/dashboard', '/supported-villages', '/funds'])
    // 板块内 page/group children/console 全部渲染
    expect(indexes).toContain('/funds')
    expect(indexes).toContain('/system/console/org')
    expect(wrapper.find('.menu-item-console').attributes('data-index')).toBe('/system/console/org')
    // group 以子菜单渲染，children 在 sub-inline 内
    const group = wrapper.find('.sub-menu-stub[data-index="group-funds"]')
    expect(group.exists()).toBe(true)
    expect(group.find('.sub-inline .menu-item-stub').attributes('data-index')).toBe('/funds')
    // 未知图标/无图标均回退，不白屏
    expect(indexes).toEqual(expect.arrayContaining(['/strange', '/no-icon']))
  })

  it('空菜单（loaded 但 sections 为空）：仅工作台、无分区标签', async () => {
    const wrapper = await mountLayout()
    useMenuStore().setMenus({ sections: [], flat_keys: [] })
    await nextTick()
    expect(sectionLabels(wrapper)).toEqual([])
    expect(menuIndexes(wrapper)).toEqual(['/dashboard'])
  })

  it('未加载时挂载自动 fetchMenus 并渲染下发的板块', async () => {
    const wrapper = await mountLayout({ presetMenus: false })
    expect(mocks.get).toHaveBeenCalledWith('/menus/accessible')
    expect(useMenuStore().loaded).toBe(true)
    expect(sectionLabels(wrapper)).toEqual(['帮扶业务', '系统管理'])
  })

  it('已加载时不重复请求菜单', async () => {
    await mountLayout()
    expect(mocks.get).not.toHaveBeenCalled()
  })

  it('折叠按钮切换侧栏宽度并隐藏板块标题', async () => {
    const wrapper = await mountLayout()
    const aside = wrapper.find('.aside-stub')
    expect(aside.attributes('data-width')).toBe('var(--layout-sidebar-width, 240px)')
    expect(wrapper.find('.section-head').attributes('style')).toBeUndefined()

    await wrapper.find('.button-stub').trigger('click')
    await nextTick()
    expect(aside.attributes('data-width')).toBe('var(--layout-sidebar-collapsed-width, 68px)')
    expect(wrapper.find('.section-head').attributes('style')).toContain('display: none')
  })

  it('窄屏自动收起：初始 matches=true 收起，change 事件进入/退出窄屏', async () => {
    installMatchMedia(true)
    const wrapper = await mountLayout()
    expect(wrapper.find('.aside-stub').attributes('data-width')).toBe(
      'var(--layout-sidebar-collapsed-width, 68px)'
    )
    // 宽屏事件（false 分支）不回滚折叠偏好
    mediaListeners[0]({ matches: false })
    await nextTick()
    expect(wrapper.find('.aside-stub').attributes('data-width')).toBe(
      'var(--layout-sidebar-collapsed-width, 68px)'
    )
    expect(mediaListeners).toHaveLength(1)
    wrapper.unmount()
    expect(mediaRemoveEventListener).toHaveBeenCalledWith('change', expect.any(Function))
  })

  it('useAutoLock 自定义 onLock：lockSession + markLockNow + 携带当前路由跳转', async () => {
    await mountLayout()
    expect(mocks.lockOptions).not.toBeNull()

    mocks.lockOptions?.onLock()
    expect(mocks.auth.lockSession).toHaveBeenCalledTimes(1)
    expect(mocks.markLockNow).toHaveBeenCalledTimes(1)
    expect(window.location.href).toBe('/login?redirect=%2Fdashboard')

    // 已在登录页：不带 redirect
    mocks.route.fullPath = '/login'
    mocks.lockOptions?.onLock()
    expect(window.location.href).toBe('/login')

    // 空 fullPath：同样不带 redirect（覆盖 && 假分支）
    mocks.route.fullPath = ''
    mocks.lockOptions?.onLock()
    expect(window.location.href).toBe('/login')
  })

  // ══════════════════ 顶栏能力 ══════════════════

  it('面包屑与用户名按路由/用户数据渲染（含回退分支）', async () => {
    mocks.auth.user = { username: '张三' }
    let wrapper = await mountLayout()
    expect(wrapper.find('.breadcrumb-current').text()).toBe('工作台')
    expect(wrapper.find('.username').text()).toBe('张三')

    mocks.auth.user = { full_name: '李四' }
    wrapper = await mountLayout()
    expect(wrapper.find('.username').text()).toBe('李四')

    mocks.auth.user = null
    wrapper = await mountLayout()
    expect(wrapper.find('.username').text()).toBe('管理员')
  })

  it('未匹配路由且无 meta.title 时不渲染面包屑层级', async () => {
    mocks.route.path = '/mystery-page'
    mocks.route.meta = {}
    const wrapper = await mountLayout()
    expect(wrapper.find('.breadcrumb-section').exists()).toBe(false)
    expect(wrapper.find('.breadcrumb-current').exists()).toBe(false)
  })

  it('router-view 有组件时渲染路由内容', async () => {
    const wrapper = await mountLayout({ routedView: true })
    expect(wrapper.find('.routed-view').exists()).toBe(true)
  })

  it('消息铃铛点击跳转消息中心', async () => {
    const wrapper = await mountLayout()
    await wrapper.find('.message-bell').trigger('click')
    expect(mocks.pushSafe).toHaveBeenCalledWith('/message')
  })

  it('主题切换器命令调用 configStore.setTheme；顶栏仅开放 default/outdoor', async () => {
    const wrapper = await mountLayout()
    const dropdowns = wrapper.findAllComponents(ElDropdownStub)
    dropdowns[0].vm.$emit('command', 'outdoor')
    expect(mocks.config.setTheme).toHaveBeenCalledWith('outdoor')
    const themeText = wrapper.find('.theme-switcher').text()
    expect(themeText).toContain('军绿')
    expect(themeText).toContain('户外高对比')
    // dark-bigscreen 仅大屏使用，不出现在顶栏主题切换器
    expect(themeText).not.toContain('深色大屏')
  })

  it('用户菜单命令：个人中心 / 修改密码 / 退出登录', async () => {
    const wrapper = await mountLayout()
    const dropdowns = wrapper.findAllComponents(ElDropdownStub)
    const userDropdown = dropdowns[1]

    userDropdown.vm.$emit('command', 'profile')
    expect(mocks.pushSafe).toHaveBeenCalledWith('/profile')

    userDropdown.vm.$emit('command', 'change-password')
    expect(mocks.pushSafe).toHaveBeenCalledWith('/change-password')

    userDropdown.vm.$emit('command', 'logout')
    expect(mocks.freezeRequests).toHaveBeenCalledTimes(1)
    expect(mocks.cancelAllRequests).toHaveBeenCalledTimes(1)
    expect(mocks.auth.logout).toHaveBeenCalledTimes(1)
    expect(window.location.href).toBe('/login')
  })

  it('搜索入口点击打开菜单搜索弹窗', async () => {
    const wrapper = await mountLayout()
    const dialog = wrapper.findComponent({ name: 'MenuSearchDialog' })
    expect(dialog.props('modelValue')).toBe(false)

    await wrapper.find('.menu-search-trigger').trigger('click')
    expect(dialog.props('modelValue')).toBe(true)

    dialog.vm.$emit('update:modelValue', false)
    await nextTick()
    expect(dialog.props('modelValue')).toBe(false)
  })

  // ══════════════════ 未读角标 / 轮询 / 锁屏摘要 ══════════════════

  it('未读角标：total 优先，electronAPI 同步托盘角标', async () => {
    mocks.getUnreadCount.mockResolvedValue({ data: { total: 5 } })
    const traySpy = vi.fn()
    ;(window as any).electronAPI = { updateTrayUnread: traySpy }
    try {
      const wrapper = await mountLayout()
      expect(mocks.getUnreadCount).toHaveBeenCalled()
      const badge = wrapper.find('.badge-stub')
      expect(badge.attributes('data-value')).toBe('5')
      expect(badge.attributes('data-hidden')).toBe('false')
      expect(traySpy).toHaveBeenCalledWith(5)
    } finally {
      delete (window as any).electronAPI
    }
  })

  it('未读角标：total 缺失时回退 count；无 electronAPI 时静默', async () => {
    mocks.getUnreadCount.mockResolvedValue({ data: { count: 3 } })
    const wrapper = await mountLayout()
    expect(wrapper.find('.badge-stub').attributes('data-value')).toBe('3')
    expect(wrapper.find('.badge-stub').attributes('data-hidden')).toBe('false')
  })

  it('未读角标：响应为 null 时归零并隐藏角标', async () => {
    mocks.getUnreadCount.mockResolvedValue(null)
    const wrapper = await mountLayout()
    expect(wrapper.find('.badge-stub').attributes('data-value')).toBe('0')
    expect(wrapper.find('.badge-stub').attributes('data-hidden')).toBe('true')
  })

  it('electronAPI 存在但无 updateTrayUnread 时静默跳过', async () => {
    ;(window as any).electronAPI = {}
    try {
      const wrapper = await mountLayout()
      expect(wrapper.find('.badge-stub').exists()).toBe(true)
    } finally {
      delete (window as any).electronAPI
    }
  })

  it('未读数请求失败静默，不抛出', async () => {
    mocks.getUnreadCount.mockRejectedValue(new Error('network'))
    const wrapper = await mountLayout()
    expect(wrapper.find('.badge-stub').attributes('data-value')).toBe('0')
  })

  it('锁屏归来摘要：已登录且有未读时弹通知，点击跳转消息中心', async () => {
    mocks.consumeLockDigest.mockReturnValue(true)
    mocks.getUnreadCount.mockResolvedValue({ data: { total: 2 } })
    await mountLayout()

    expect(mocks.notification).toHaveBeenCalledTimes(1)
    const options = mocks.notification.mock.calls[0][0]
    expect(options.title).toBe('欢迎回来')
    expect(options.message).toBe('您有 2 条未读消息')
    options.onClick()
    expect(mocks.pushSafe).toHaveBeenCalledWith('/message')
  })

  it('未登录或摘要条件不满足时不弹通知', async () => {
    mocks.auth.isAuthenticated = false
    mocks.consumeLockDigest.mockReturnValue(true)
    await mountLayout()
    expect(mocks.notification).not.toHaveBeenCalled()

    resetMenuFavorites()
    mocks.auth.isAuthenticated = true
    mocks.consumeLockDigest.mockReturnValue(false)
    await mountLayout()
    expect(mocks.notification).not.toHaveBeenCalled()
  })

  it('注册 60s 轮询，轮询刷新未读数并在卸载时清理定时器', async () => {
    const intervalSpy = vi.spyOn(window, 'setInterval')
    const clearSpy = vi.spyOn(window, 'clearInterval')
    mocks.getUnreadCount.mockResolvedValue({ data: { total: 1 } })
    const wrapper = await mountLayout()
    expect(wrapper.find('.badge-stub').attributes('data-value')).toBe('1')
    expect(intervalSpy).toHaveBeenCalledWith(expect.any(Function), 60000)

    // 手动触发一次轮询回调（避免 fake timers 与动态 import/flushPromises 冲突）
    const tick = intervalSpy.mock.calls[0][0] as () => Promise<void>
    mocks.getUnreadCount.mockResolvedValue({ data: { total: 7 } })
    await tick()
    await nextTick()
    expect(wrapper.find('.badge-stub').attributes('data-value')).toBe('7')

    wrapper.unmount()
    expect(clearSpy).toHaveBeenCalled()
    intervalSpy.mockRestore()
    clearSpy.mockRestore()
  })

  // ══════════════════ 快捷键 ══════════════════

  it('Ctrl+K 打开菜单搜索；其余导航快捷键调用 pushSafe', async () => {
    const wrapper = await mountLayout()
    const dialog = wrapper.findComponent({ name: 'MenuSearchDialog' })

    dispatchKey('k', { ctrl: true })
    await nextTick()
    expect(dialog.props('modelValue')).toBe(true)
    dialog.vm.$emit('update:modelValue', false)
    await nextTick()

    const expected: Array<[string, boolean, string]> = [
      ['h', false, '/'],
      ['d', false, '/data-analysis'],
      ['v', false, '/supported-villages'],
      ['f', false, '/funds'],
      ['p', false, '/projects'],
      ['s', false, '/schools'],
      ['m', false, '/data-analysis/map'],
      ['b', true, '/system/backup'],
      ['u', true, '/system/users'],
    ]
    for (const [key, shift, target] of expected) {
      dispatchKey(key, { ctrl: true, shift })
      expect(mocks.pushSafe).toHaveBeenCalledWith(target)
    }

    // Shift+? 切换快捷键帮助面板（无副作用，仅覆盖处理器）
    dispatchKey('?', { shift: true })
    expect(mocks.pushSafe).toHaveBeenCalledTimes(expected.length)
  })

  it('输入框内普通快捷键被禁用，Ctrl+K 仍可用', async () => {
    const wrapper = await mountLayout()
    const dialog = wrapper.findComponent({ name: 'MenuSearchDialog' })
    const input = document.createElement('input')
    document.body.appendChild(input)
    try {
      dispatchKey('h', { ctrl: true }, input)
      expect(mocks.pushSafe).not.toHaveBeenCalled()

      dispatchKey('k', { ctrl: true }, input)
      await nextTick()
      expect(dialog.props('modelValue')).toBe(true)
    } finally {
      input.remove()
    }
  })

  it('卸载后快捷键监听解绑', async () => {
    const wrapper = await mountLayout()
    wrapper.unmount()
    dispatchKey('h', { ctrl: true })
    expect(mocks.pushSafe).not.toHaveBeenCalled()
  })

  // ══════════════════ W22：板块折叠放大 ══════════════════

  it('板块默认折叠：标题放大加粗且入口隐藏，点击展开后持久化', async () => {
    const wrapper = await mountLayout({ expandAll: false })
    // 板块标题渲染（7 板块中的 2 个测试板块）
    expect(sectionLabels(wrapper)).toEqual(['帮扶业务', '系统管理'])
    const businessToggle = sectionToggle(wrapper, '帮扶业务')
    expect(businessToggle.attributes('aria-expanded')).toBe('false')
    expect(businessToggle.classes()).toContain('menu-section-toggle')
    // 默认折叠：板块入口全部 v-show=false
    expect(isVisible(wrapper, '/supported-villages')).toBe(false)
    expect(isVisible(wrapper, '/system/console/org')).toBe(false)
    // 工作台固定第一不受折叠影响
    expect(isVisible(wrapper, '/dashboard')).toBe(true)

    // 点击展开 → 入口可见、aria 切换、localStorage 记录展开集合
    await businessToggle.trigger('click')
    await nextTick()
    expect(sectionToggle(wrapper, '帮扶业务').attributes('aria-expanded')).toBe('true')
    expect(isVisible(wrapper, '/supported-villages')).toBe(true)
    expect(JSON.parse(localStorage.getItem('nav:expanded-sections') as string)).toEqual([
      'business',
    ])
    // 未点击的板块仍折叠（独立性）
    expect(isVisible(wrapper, '/system/console/org')).toBe(false)

    // 再次点击收起并写回空数组
    await sectionToggle(wrapper, '帮扶业务').trigger('click')
    await nextTick()
    expect(isVisible(wrapper, '/supported-villages')).toBe(false)
    expect(JSON.parse(localStorage.getItem('nav:expanded-sections') as string)).toEqual([])
  })

  it('展开状态从 localStorage 恢复（默认折叠）', async () => {
    localStorage.setItem('nav:expanded-sections', JSON.stringify(['system']))
    const wrapper = await mountLayout({ expandAll: false })
    expect(isVisible(wrapper, '/supported-villages')).toBe(false)
    expect(isVisible(wrapper, '/system/console/org')).toBe(true)
  })

  it('损坏 localStorage（非 JSON / 非数组）回退为全部折叠', async () => {
    localStorage.setItem('nav:expanded-sections', '{bad-json')
    let wrapper = await mountLayout({ expandAll: false })
    expect(isVisible(wrapper, '/supported-villages')).toBe(false)
    expect(sectionToggle(wrapper, '帮扶业务').attributes('aria-expanded')).toBe('false')

    localStorage.setItem('nav:expanded-sections', JSON.stringify({ business: true }))
    wrapper = await mountLayout({ expandAll: false })
    expect(isVisible(wrapper, '/supported-villages')).toBe(false)
  })

  it('localStorage 写入失败时折叠仍生效（静默降级）', async () => {
    const wrapper = await mountLayout({ expandAll: false })
    const spy = vi.spyOn(localStorage, 'setItem').mockImplementation(() => {
      throw new Error('QuotaExceededError')
    })
    try {
      await sectionToggle(wrapper, '帮扶业务').trigger('click')
      await nextTick()
      expect(isVisible(wrapper, '/supported-villages')).toBe(true)
      expect(sectionToggle(wrapper, '帮扶业务').attributes('aria-expanded')).toBe('true')
    } finally {
      spy.mockRestore()
    }
  })

  it('折叠状态下仍可打开菜单搜索（Ctrl+K 与收藏/最近不受影响）', async () => {
    useMenuFavorites().toggleFavorite({
      key: 'villages',
      label: '帮扶村管理',
      path: '/supported-villages',
    })
    const wrapper = await mountLayout({ expandAll: false })
    // 收藏区始终可见（不受板块折叠影响）
    expect(sectionLabels(wrapper)).toContain('收藏')
    expect(isVisible(wrapper, '/supported-villages')).toBe(true)
    dispatchKey('k', { ctrl: true })
    await nextTick()
    expect(wrapper.findComponent({ name: 'MenuSearchDialog' }).props('modelValue')).toBe(true)
  })

  // ══════════════════ W23：面包屑 / 当前板块 / 收起态浮层 / 外观入口 ══════════════════

  it('面包屑「板块 › 页面」：page / group 子项 / console / 详情前缀', async () => {
    mocks.route.path = '/supported-villages'
    mocks.route.meta = { title: '帮扶村' }
    let wrapper = await mountLayout({ expandAll: false })
    expect(wrapper.find('.breadcrumb-section').text()).toBe('帮扶业务')
    expect(wrapper.find('.breadcrumb-current').text()).toBe('帮扶村管理')

    mocks.route.path = '/funds' // group children
    wrapper = await mountLayout({ expandAll: false })
    expect(wrapper.find('.breadcrumb-section').text()).toBe('帮扶业务')
    expect(wrapper.find('.breadcrumb-current').text()).toBe('经费台账')

    mocks.route.path = '/system/console/org' // console 聚合页
    wrapper = await mountLayout({ expandAll: false })
    expect(wrapper.find('.breadcrumb-section').text()).toBe('系统管理')
    expect(wrapper.find('.breadcrumb-current').text()).toBe('组织与权限')

    mocks.route.path = '/supported-villages/42' // 详情页按入口前缀归入
    wrapper = await mountLayout({ expandAll: false })
    expect(wrapper.find('.breadcrumb-current').text()).toBe('帮扶村管理')
  })

  it('面包屑：工作台固定「工作台」；未匹配回退 meta.title', async () => {
    mocks.route.path = '/dashboard'
    let wrapper = await mountLayout()
    expect(wrapper.find('.breadcrumb-section').exists()).toBe(false)
    expect(wrapper.find('.breadcrumb-current').text()).toBe('工作台')

    mocks.route.path = '/mystery-page'
    mocks.route.meta = { title: '未知页' }
    wrapper = await mountLayout()
    expect(wrapper.find('.breadcrumb-section').exists()).toBe(false)
    expect(wrapper.find('.breadcrumb-current').text()).toBe('未知页')
  })

  it('当前板块自动展开并保持，切换路由后新板块自动展开', async () => {
    mocks.route.path = '/supported-villages'
    const wrapper = await mountLayout({ expandAll: false })
    // 当前板块（帮扶业务）自动展开，非当前板块保持折叠
    expect(isVisible(wrapper, '/supported-villages')).toBe(true)
    expect(isVisible(wrapper, '/system/console/org')).toBe(false)
    const stored = JSON.parse(localStorage.getItem('nav:expanded-sections') as string)
    expect(stored).toContain('business')

    // 当前板块标题金色竖条（is-current 只标记当前板块）
    expect(sectionToggle(wrapper, '帮扶业务').classes()).toContain('is-current')
    expect(sectionToggle(wrapper, '系统管理').classes()).not.toContain('is-current')

    // 路由切换 → 新板块自动展开，原板块保持展开
    mocks.route.path = '/system/console/org'
    await nextTick()
    expect(isVisible(wrapper, '/system/console/org')).toBe(true)
    expect(isVisible(wrapper, '/supported-villages')).toBe(true)
    const expanded = JSON.parse(localStorage.getItem('nav:expanded-sections') as string)
    expect(expanded).toEqual(expect.arrayContaining(['business', 'system']))
    expect(sectionToggle(wrapper, '系统管理').classes()).toContain('is-current')

    // 回到已展开板块：不重复追加（has 分支）
    mocks.route.path = '/supported-villages'
    await nextTick()
    const again = JSON.parse(localStorage.getItem('nav:expanded-sections') as string)
    expect(again.filter((key: string) => key === 'business')).toHaveLength(1)
  })

  it('板块收起态：hover 标题浮出子项浮层，点击子项跳转并关闭', async () => {
    const wrapper = await mountLayout({ expandAll: false })
    expect(wrapper.find('[data-test="section-flyout"]').exists()).toBe(false)

    const heads = wrapper.findAll('.section-head')
    // hover 帮扶业务标题 → 浮层展示 page 项与 group 子项
    await heads[0].trigger('mouseenter')
    await nextTick()
    let flyout = wrapper.find('[data-test="section-flyout"]')
    expect(flyout.exists()).toBe(true)
    expect(flyout.find('.section-flyout-title').text()).toBe('帮扶业务')
    const labels = flyout
      .findAll('.section-flyout-item')
      .map((item) => item.text().replace(/\s+/g, ''))
    expect(labels).toEqual(['帮扶村管理', '经费台账'])

    // 点击 page 子项 → 跳转并关闭浮层
    await flyout.findAll('.section-flyout-item')[0].trigger('click')
    expect(mocks.pushSafe).toHaveBeenCalledWith('/supported-villages')
    expect(wrapper.find('[data-test="section-flyout"]').exists()).toBe(false)

    // 键盘聚焦标题同样浮出；点击 group 子项跳转
    await sectionToggle(wrapper, '帮扶业务').trigger('focus')
    await nextTick()
    flyout = wrapper.find('[data-test="section-flyout"]')
    expect(flyout.exists()).toBe(true)
    await flyout.findAll('.section-flyout-item')[1].trigger('click')
    expect(mocks.pushSafe).toHaveBeenCalledWith('/funds')

    // 鼠标移出板块标题区域 → 浮层关闭
    await heads[0].trigger('mouseenter')
    await nextTick()
    expect(wrapper.find('[data-test="section-flyout"]').exists()).toBe(true)
    await heads[0].trigger('mouseleave')
    await nextTick()
    expect(wrapper.find('[data-test="section-flyout"]').exists()).toBe(false)
  })

  it('板块展开态 hover 不显示浮层；展开/收起时清理浮层', async () => {
    const wrapper = await mountLayout({ expandAll: false })
    const heads = wrapper.findAll('.section-head')
    await heads[1].trigger('mouseenter') // 系统管理（收起）
    await nextTick()
    expect(wrapper.find('[data-test="section-flyout"]').exists()).toBe(true)

    // 点击标题展开 → 浮层立即清理
    await sectionToggle(wrapper, '系统管理').trigger('click')
    await nextTick()
    expect(isVisible(wrapper, '/system/console/org')).toBe(true)
    expect(wrapper.find('[data-test="section-flyout"]').exists()).toBe(false)

    // 展开态 hover 不再显示浮层
    await heads[1].trigger('mouseenter')
    await nextTick()
    expect(wrapper.find('[data-test="section-flyout"]').exists()).toBe(false)
  })

  it('浮层 console 子项点击跳转', async () => {
    const wrapper = await mountLayout({ expandAll: false })
    const heads = wrapper.findAll('.section-head')
    await heads[1].trigger('mouseenter')
    await nextTick()
    const flyout = wrapper.find('[data-test="section-flyout"]')
    expect(flyout.findAll('.section-flyout-item').map((item) => item.text())).toContain(
      '组织与权限'
    )
    await flyout.findAll('.section-flyout-item')[0].trigger('click')
    expect(mocks.pushSafe).toHaveBeenCalledWith('/system/console/org')
  })

  it('头像菜单「外观设置」打开外观面板并能关闭', async () => {
    const wrapper = await mountLayout()
    const dropdowns = wrapper.findAllComponents(ElDropdownStub)
    dropdowns[1].vm.$emit('command', 'appearance')
    await nextTick()

    const dialog = wrapper.findComponent({ name: 'ElDialog' })
    expect(dialog.props('modelValue')).toBe(true)
    expect(dialog.props('title')).toBe('外观设置')
    // W1 外观面板（本文件桩掉，真实执行者是 AppearanceSettings.test.ts）
    expect(dialog.find('.appearance-settings-stub').exists()).toBe(true)

    dialog.vm.$emit('update:modelValue', false)
    await nextTick()
    expect(dialog.props('modelValue')).toBe(false)
  })
})

describe('面包屑最长路径优先（v1.15.0 收口）', () => {
  const RURAL_PAYLOAD = (listFirst: boolean) => ({
    sections: [
      {
        key: 'rural',
        label: '乡村振兴',
        order: 10,
        items: listFirst
          ? [
              { key: 'rural-list', label: '工作列表', path: '/rural-works/list', icon: 'List', kind: 'page' },
              { key: 'rural-home', label: '工作首页', path: '/rural-works', icon: 'Sunny', kind: 'page' },
            ]
          : [
              { key: 'rural-home', label: '工作首页', path: '/rural-works', icon: 'Sunny', kind: 'page' },
              { key: 'rural-list', label: '工作列表', path: '/rural-works/list', icon: 'List', kind: 'page' },
            ],
      },
    ],
    flat_keys: ['rural-list', 'rural-home'],
  })

  it('短前缀先出现、长路径后出现：替换为更长匹配（true 分支）', async () => {
    const wrapper = await mountLayout()
    useMenuStore().setMenus(RURAL_PAYLOAD(false) as never)
    mocks.route.path = '/rural-works/list'
    mocks.route.meta = { title: '路由标题' }
    await nextTick()
    expect(wrapper.find('.breadcrumb-section').text()).toBe('乡村振兴')
    expect(wrapper.find('.breadcrumb-current').text()).toBe('工作列表')
  })

  it('长路径先出现、短前缀后出现：不覆盖（false 分支）', async () => {
    const wrapper = await mountLayout()
    useMenuStore().setMenus(RURAL_PAYLOAD(true) as never)
    mocks.route.path = '/rural-works/list'
    mocks.route.meta = { title: '路由标题' }
    await nextTick()
    expect(wrapper.find('.breadcrumb-current').text()).toBe('工作列表')
  })
})
