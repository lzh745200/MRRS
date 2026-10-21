/**
 * MobileBottomNav.vue 测试（唯一执行者）
 *
 * 数据驱动：工作台固定第一 + menuStore.flatEntries 前 3 个入口 + 「更多」抽屉。
 * 覆盖：移动/桌面宽度渲染、active 状态（精确/前缀/更多不高亮）、点击导航、
 * 「更多」抽屉菜单 + 页内搜索、空态、最近访问记录、resize、监听解绑、数据不足降级。
 */
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { nextTick } from 'vue'
import { mount, enableAutoUnmount, type VueWrapper } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import MobileBottomNav from '@/components/layout/MobileBottomNav.vue'
import { useMenuStore } from '@/stores/menu'
import { useRecentMenus, resetRecentMenus } from '@/composables/useRecentMenus'

enableAutoUnmount(afterEach)

const mocks = vi.hoisted(() => ({
  route: { path: '/dashboard' },
  pushSafe: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRoute: () => mocks.route,
}))

vi.mock('@/composables/useRouterSafe', () => ({
  useRouterSafe: () => ({ pushSafe: (...args: any[]) => mocks.pushSafe(...args) }),
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({ user: null }),
}))

vi.mock('@/api/request', () => ({
  get: vi.fn(),
  getCsrfToken: vi.fn(() => Promise.resolve('test-csrf')),
}))

vi.mock('@/utils/authStorage', () => ({
  AuthStorage: { getToken: () => 'token' },
}))

/** 4 个可导航入口（工作台 + 3 个板块入口），用于验证「sections 前 3 个」 */
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
          tabs: [],
        },
      ],
    },
  ],
  flat_keys: ['dashboard', 'villages', 'funds-admin', 'system-console-org'],
}

const ElIconStub = {
  name: 'ElIcon',
  template: '<i class="icon-stub"><slot /></i>',
}

const ElDrawerStub = {
  name: 'ElDrawer',
  props: ['modelValue', 'title', 'direction', 'size'],
  emits: ['update:modelValue'],
  template: '<div v-if="modelValue" class="drawer-stub"><h3>{{ title }}</h3><slot /></div>',
}

const ElInputStub = {
  name: 'ElInput',
  props: ['modelValue', 'placeholder', 'clearable'],
  emits: ['update:modelValue'],
  template:
    '<div class="input-stub"><input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" /></div>',
}

const ElEmptyStub = {
  name: 'ElEmpty',
  props: ['description'],
  template: '<div class="empty-stub">{{ description }}</div>',
}

function setWidth(w: number) {
  Object.defineProperty(window, 'innerWidth', {
    value: w,
    configurable: true,
    writable: true,
  })
}

function mountNav() {
  return mount(MobileBottomNav, {
    global: {
      stubs: {
        'el-icon': ElIconStub,
        'el-drawer': ElDrawerStub,
        'el-input': ElInputStub,
        'el-empty': ElEmptyStub,
      },
    },
  })
}

function navLabels(wrapper: VueWrapper): string[] {
  return wrapper.findAll('button.nav-btn').map((btn) => btn.find('.nav-label').text())
}

describe('MobileBottomNav.vue（数据驱动）', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.route.path = '/dashboard'
    localStorage.clear()
    resetRecentMenus()
    setActivePinia(createPinia())
    useMenuStore().setMenus(V2_PAYLOAD)
  })

  afterEach(() => {
    resetRecentMenus()
  })

  it('桌面宽度（≥768）不渲染导航', () => {
    setWidth(1024)
    const wrapper = mountNav()
    expect(wrapper.find('nav.mobile-nav').exists()).toBe(false)
  })

  it('移动宽度渲染：工作台 + 前 3 个入口 + 更多（共 5 个按钮）', () => {
    setWidth(500)
    const wrapper = mountNav()
    expect(wrapper.find('nav.mobile-nav').exists()).toBe(true)
    expect(navLabels(wrapper)).toEqual(['工作台', '帮扶村管理', '经费台账', '组织与权限', '更多'])
  })

  it('入口不足 3 个时按实际数量渲染', () => {
    useMenuStore().setMenus({ sections: [], flat_keys: [] })
    setWidth(500)
    const wrapper = mountNav()
    expect(navLabels(wrapper)).toEqual(['工作台', '更多'])
  })

  it('当前路由高亮（精确匹配）', () => {
    setWidth(500)
    mocks.route.path = '/dashboard'
    const wrapper = mountNav()
    const buttons = wrapper.findAll('button.nav-btn')
    expect(buttons[0].classes()).toContain('active')
    expect(buttons[1].classes()).not.toContain('active')
    // 「更多」无 path，不被前缀匹配误判高亮
    expect(buttons[buttons.length - 1].classes()).not.toContain('active')
  })

  it('当前路由高亮（前缀匹配：子路由）', () => {
    setWidth(500)
    mocks.route.path = '/supported-villages/123'
    const wrapper = mountNav()
    expect(wrapper.findAll('button.nav-btn')[1].classes()).toContain('active')
  })

  it('点击普通入口调用 pushSafe', async () => {
    setWidth(500)
    const wrapper = mountNav()
    await wrapper.findAll('button.nav-btn')[2].trigger('click')
    expect(mocks.pushSafe).toHaveBeenCalledWith('/funds')
  })

  it('抽屉内点击 console 子项 → 跳转带 ?tab= 并记录最近访问（含 tabKey）', async () => {
    useMenuStore().setMenus({
      sections: [
        {
          key: 'system',
          label: '系统管理',
          order: 90,
          items: [
            {
              key: 'system-console-storage',
              label: '备份与存储',
              path: '/system/console/storage',
              kind: 'console',
              order: 10,
              tabs: [
                { key: 'backup', label: '数据备份', path: '/system/backup', order: 1 },
              ],
            },
          ],
        },
      ],
      flat_keys: [],
    })
    setWidth(500)
    const wrapper = mountNav()
    const moreBtn = wrapper
      .findAll('button.nav-btn')
      .find((btn) => btn.find('.nav-label').text() === '更多')
    expect(moreBtn).toBeDefined()
    await moreBtn?.trigger('click')

    const items = wrapper.findAll('button.mobile-menu-item')
    const backupItem = items.find((item) => item.text().includes('数据备份'))
    expect(backupItem).toBeDefined()
    await backupItem?.trigger('click')

    expect(mocks.pushSafe).toHaveBeenCalledWith({
      path: '/system/console/storage',
      query: { tab: 'backup' },
    })
    const { recentMenus } = useRecentMenus()
    expect(recentMenus.value[0].tabKey).toBe('backup')
  })

  it('点击「更多」打开抽屉并展示全量菜单', async () => {
    setWidth(500)
    const wrapper = mountNav()
    await wrapper.findAll('button.nav-btn')[4].trigger('click')
    expect(wrapper.find('.drawer-stub').exists()).toBe(true)
    expect(wrapper.find('.drawer-stub h3').text()).toBe('全部菜单')
    // 抽屉内包含工作台与全部入口
    expect(wrapper.findAll('button.mobile-menu-item')).toHaveLength(4)
  })

  it('抽屉页内搜索（label/path 子串），无匹配展示空态', async () => {
    setWidth(500)
    const wrapper = mountNav()
    await wrapper.findAll('button.nav-btn')[4].trigger('click')

    await wrapper.find('.input-stub input').setValue('经费')
    await nextTick()
    expect(wrapper.findAll('button.mobile-menu-item')).toHaveLength(1)
    expect(wrapper.find('.mobile-menu-item-label').text()).toBe('经费台账')

    await wrapper.find('.input-stub input').setValue('zzz')
    await nextTick()
    expect(wrapper.findAll('button.mobile-menu-item')).toHaveLength(0)
    expect(wrapper.find('.empty-stub').text()).toBe('未找到匹配的菜单')
  })

  it('关键词为空时展示全部入口', async () => {
    setWidth(500)
    const wrapper = mountNav()
    await wrapper.findAll('button.nav-btn')[4].trigger('click')
    await wrapper.find('.input-stub input').setValue('工作台')
    await nextTick()
    expect(wrapper.findAll('button.mobile-menu-item')).toHaveLength(1)
    await wrapper.find('.input-stub input').setValue('')
    await nextTick()
    expect(wrapper.findAll('button.mobile-menu-item')).toHaveLength(4)
  })

  it('点击抽屉入口：关闭抽屉、写最近访问、跳转', async () => {
    setWidth(500)
    const wrapper = mountNav()
    await wrapper.findAll('button.nav-btn')[4].trigger('click')
    await wrapper.findAll('button.mobile-menu-item')[0].trigger('click')
    expect(mocks.pushSafe).toHaveBeenCalledWith('/dashboard')
    expect(wrapper.find('.drawer-stub').exists()).toBe(false)
    expect(useRecentMenus().recentMenus.value[0].key).toBe('dashboard')
  })

  it('el-drawer 自身关闭（点遮罩/关闭按钮）同步 v-model', async () => {
    setWidth(500)
    const wrapper = mountNav()
    await wrapper.findAll('button.nav-btn')[4].trigger('click')
    expect(wrapper.find('.drawer-stub').exists()).toBe(true)
    wrapper.findComponent(ElDrawerStub).vm.$emit('update:modelValue', false)
    await nextTick()
    expect(wrapper.find('.drawer-stub').exists()).toBe(false)
  })

  it('窗口尺寸变化时响应（resize 进出移动端）', async () => {
    setWidth(500)
    const wrapper = mountNav()
    expect(wrapper.find('nav.mobile-nav').exists()).toBe(true)

    setWidth(800)
    window.dispatchEvent(new Event('resize'))
    await nextTick()
    expect(wrapper.find('nav.mobile-nav').exists()).toBe(false)

    setWidth(400)
    window.dispatchEvent(new Event('resize'))
    await nextTick()
    expect(wrapper.find('nav.mobile-nav').exists()).toBe(true)
  })

  it('卸载时移除 resize 监听', async () => {
    setWidth(500)
    const removeSpy = vi.spyOn(window, 'removeEventListener')
    const wrapper = mountNav()
    wrapper.unmount()
    expect(removeSpy).toHaveBeenCalledWith('resize', expect.any(Function))
    removeSpy.mockRestore()
  })
})
