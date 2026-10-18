/**
 * MenuSearchDialog.vue 测试（唯一执行者；layout 测试中以 vi.mock 桩掉，不真实执行）
 *
 * 覆盖：空搜索展示收藏/最近、label/key/path 搜索、空态、键盘上下+回车+Esc、
 * 点击跳转、行内收藏切换、打开时重置、监听器解绑、不可访问记录过滤、去重。
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, enableAutoUnmount, type VueWrapper } from '@vue/test-utils'
import { nextTick } from 'vue'
import { setActivePinia, createPinia } from 'pinia'
import MenuSearchDialog from '@/components/nav/MenuSearchDialog.vue'
import { useMenuStore } from '@/stores/menu'
import { useRecentMenus, resetRecentMenus } from '@/composables/useRecentMenus'
import { useMenuFavorites, resetMenuFavorites } from '@/composables/useMenuFavorites'

enableAutoUnmount(afterEach)

const mocks = vi.hoisted(() => ({
  pushSafe: vi.fn(),
}))

vi.mock('@/composables/useRouterSafe', () => ({
  useRouterSafe: () => ({ pushSafe: mocks.pushSafe }),
}))

// 本文件只关心搜索弹窗逻辑，auth store 保持未登录（canAccessMenu 走 allKeys 判定）
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

/** 契约 §2 的最小 v2 数据：page + group + console + dashboard */
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
  flat_keys: ['dashboard', 'villages', 'funds', 'funds-admin', 'system-console-org'],
}

const ElDialogStub = {
  name: 'ElDialog',
  props: ['modelValue', 'title', 'width'],
  emits: ['update:modelValue'],
  template: '<div v-if="modelValue" class="dialog-stub"><slot /></div>',
}

const ElInputStub = {
  name: 'ElInput',
  props: ['modelValue', 'placeholder', 'clearable'],
  emits: ['update:modelValue'],
  template:
    '<div class="input-stub"><input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" /><slot name="prefix" /></div>',
}

const ElIconStub = {
  name: 'ElIcon',
  template: '<i class="icon-stub"><slot /></i>',
}

const ElEmptyStub = {
  name: 'ElEmpty',
  props: ['description'],
  template: '<div class="empty-stub">{{ description }}</div>',
}

function mountDialog(modelValue = true) {
  return mount(MenuSearchDialog, {
    props: { modelValue },
    global: {
      stubs: {
        'el-dialog': ElDialogStub,
        'el-input': ElInputStub,
        'el-icon': ElIconStub,
        'el-empty': ElEmptyStub,
      },
    },
  })
}

function findLabels(wrapper: VueWrapper): string[] {
  return wrapper.findAll('.menu-search-item-label').map((node) => node.text())
}

function groupTitles(wrapper: VueWrapper): string[] {
  return wrapper.findAll('.menu-search-group-title').map((node) => node.text())
}

async function typeKeyword(wrapper: VueWrapper, keyword: string) {
  await wrapper.find('.input-stub input').setValue(keyword)
  await nextTick()
}

async function pressKey(key: string) {
  window.dispatchEvent(new KeyboardEvent('keydown', { key }))
  await nextTick()
}

describe('MenuSearchDialog.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    resetRecentMenus()
    resetMenuFavorites()
    setActivePinia(createPinia())
    useMenuStore().setMenus(V2_PAYLOAD)
  })

  afterEach(() => {
    resetRecentMenus()
    resetMenuFavorites()
  })

  it('弹窗关闭时不渲染内容', () => {
    const wrapper = mountDialog(false)
    expect(wrapper.find('.dialog-stub').exists()).toBe(false)
    expect(wrapper.find('.menu-search').exists()).toBe(false)
  })

  it('空搜索：无历史时展示空态提示', () => {
    const wrapper = mountDialog()
    expect(wrapper.findAll('.menu-search-item')).toHaveLength(0)
    expect(wrapper.find('.empty-stub').text()).toBe('暂无收藏与最近访问')
  })

  it('空搜索：展示收藏 + 最近访问（最近已收藏项去重）', () => {
    const { recordMenu } = useRecentMenus()
    const { toggleFavorite } = useMenuFavorites()
    toggleFavorite({ key: 'villages', label: '帮扶村管理', path: '/supported-villages' })
    recordMenu({ key: 'villages', label: '帮扶村管理', path: '/supported-villages' })
    recordMenu({ key: 'funds-admin', label: '经费台账', path: '/funds' })

    const wrapper = mountDialog()
    expect(groupTitles(wrapper)).toEqual(['收藏', '最近访问'])
    expect(findLabels(wrapper)).toEqual(['帮扶村管理', '经费台账'])
    // 收藏区条目不显示板块副标题，最近访问的也不显示（存储记录无 sectionLabel）
    expect(wrapper.findAll('.menu-search-item-section')).toHaveLength(0)
  })

  it('空搜索：不可访问（已删除/无权限）的记录被过滤', () => {
    const { recordMenu } = useRecentMenus()
    const { toggleFavorite } = useMenuFavorites()
    toggleFavorite({ key: 'gone', label: '已下线菜单', path: '/gone' })
    recordMenu({ key: 'gone', label: '已下线菜单', path: '/gone' })
    const wrapper = mountDialog()
    expect(findLabels(wrapper)).toEqual([])
    expect(wrapper.find('.empty-stub').text()).toBe('暂无收藏与最近访问')
  })

  it('label 子串搜索（大小写不敏感）', async () => {
    const wrapper = mountDialog()
    await typeKeyword(wrapper, '帮扶')
    expect(groupTitles(wrapper)).toEqual(['搜索结果'])
    expect(findLabels(wrapper)).toEqual(['帮扶村管理'])
    // 搜索结果条目带板块副标题
    expect(wrapper.find('.menu-search-item-section').text()).toBe('帮扶业务')
  })

  it('key 子串搜索', async () => {
    const wrapper = mountDialog()
    await typeKeyword(wrapper, 'FUNDS')
    expect(findLabels(wrapper)).toEqual(['经费台账'])
  })

  it('path 子串搜索', async () => {
    const wrapper = mountDialog()
    await typeKeyword(wrapper, 'console')
    expect(findLabels(wrapper)).toEqual(['组织与权限'])
  })

  it('无匹配时展示搜索空态并重置高亮', async () => {
    const wrapper = mountDialog()
    await typeKeyword(wrapper, 'zzz-not-exists')
    expect(findLabels(wrapper)).toEqual([])
    expect(wrapper.find('.empty-stub').text()).toBe('未找到匹配的菜单')
    await pressKey('ArrowDown')
    await pressKey('Enter')
    expect(mocks.pushSafe).not.toHaveBeenCalled()
  })

  it('上下键循环移动高亮，Enter 跳转并记录最近访问、关闭弹窗', async () => {
    const wrapper = mountDialog()
    await typeKeyword(wrapper, 'e') // 匹配帮扶村管理/经费台账/组织与权限 等
    const items = wrapper.findAll('.menu-search-item')
    expect(items.length).toBeGreaterThan(1)

    // 初始高亮第 0 项
    expect(wrapper.findAll('.menu-search-item.is-active')).toHaveLength(1)
    expect(wrapper.findAll('.menu-search-item')[0].classes()).toContain('is-active')

    // ↓ 到第 1 项
    await pressKey('ArrowDown')
    expect(wrapper.findAll('.menu-search-item')[1].classes()).toContain('is-active')

    // ↑ 回第 0 项
    await pressKey('ArrowUp')
    expect(wrapper.findAll('.menu-search-item')[0].classes()).toContain('is-active')

    // ↑ 从 0 循环到末项
    await pressKey('ArrowUp')
    const all = wrapper.findAll('.menu-search-item')
    expect(all[all.length - 1].classes()).toContain('is-active')

    // Enter 跳转当前高亮项（末项）
    await pressKey('Enter')
    const lastLabel = all[all.length - 1].find('.menu-search-item-label').text()
    expect(mocks.pushSafe).toHaveBeenCalledTimes(1)
    expect(wrapper.emitted('update:modelValue')?.at(-1)).toEqual([false])
    const { recentMenus } = useRecentMenus()
    expect(recentMenus.value[0].label).toBe(lastLabel)
  })

  it('Esc 关闭弹窗', async () => {
    const wrapper = mountDialog()
    await pressKey('Escape')
    expect(wrapper.emitted('update:modelValue')?.at(-1)).toEqual([false])
  })

  it('el-dialog 自身关闭（点遮罩/关闭按钮）同步 v-model', async () => {
    const wrapper = mountDialog()
    wrapper.findComponent(ElDialogStub).vm.$emit('update:modelValue', false)
    await nextTick()
    expect(wrapper.emitted('update:modelValue')?.at(-1)).toEqual([false])
  })

  it('弹窗关闭时键盘事件不响应', async () => {
    const wrapper = mountDialog(false)
    await pressKey('ArrowDown')
    await pressKey('ArrowUp')
    await pressKey('Enter')
    await pressKey('Escape')
    expect(mocks.pushSafe).not.toHaveBeenCalled()
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
  })

  it('点击条目跳转、记录最近访问并关闭', async () => {
    const wrapper = mountDialog()
    await typeKeyword(wrapper, '组织')
    await wrapper.find('.menu-search-item').trigger('click')
    expect(mocks.pushSafe).toHaveBeenCalledWith('/system/console/org')
    expect(wrapper.emitted('update:modelValue')?.at(-1)).toEqual([false])
    expect(useRecentMenus().recentMenus.value[0].key).toBe('system-console-org')
  })

  it('行内星标切换收藏且不触发跳转', async () => {
    const wrapper = mountDialog()
    await typeKeyword(wrapper, '帮扶村')
    await wrapper.find('.menu-search-item-star').trigger('click')
    expect(useMenuFavorites().isFavorite('villages')).toBe(true)
    expect(mocks.pushSafe).not.toHaveBeenCalled()
    // 再次点击取消收藏
    await wrapper.find('.menu-search-item-star').trigger('click')
    expect(useMenuFavorites().isFavorite('villages')).toBe(false)
  })

  it('鼠标移入条目更新高亮', async () => {
    const wrapper = mountDialog()
    await typeKeyword(wrapper, 'e')
    const items = wrapper.findAll('.menu-search-item')
    await items[1].trigger('mouseenter')
    expect(wrapper.findAll('.menu-search-item')[1].classes()).toContain('is-active')
  })

  it('重新打开时重置关键词与高亮', async () => {
    const wrapper = mountDialog()
    await typeKeyword(wrapper, '帮扶')
    expect(findLabels(wrapper)).toEqual(['帮扶村管理'])

    await wrapper.setProps({ modelValue: false })
    await wrapper.setProps({ modelValue: true })
    expect(findLabels(wrapper)).toEqual([])
    expect(wrapper.find('.empty-stub').text()).toBe('暂无收藏与最近访问')
  })

  it('卸载时移除全局键盘监听', async () => {
    const removeSpy = vi.spyOn(window, 'removeEventListener')
    const wrapper = mountDialog()
    wrapper.unmount()
    expect(removeSpy).toHaveBeenCalledWith('keydown', expect.any(Function))
    removeSpy.mockRestore()
  })
})
