/**
 * views/dashboard/index.vue 覆盖率攻坚（四指标 100%）
 *
 * 覆盖：loadLayout 四种形态（有效存储/无效 JSON/形状非法/缺省）、saveLayout 持久化、
 * resetLayout、visible 计算、refreshKpiData（document.hidden 两侧）、60s 定时器生命周期、
 * 拖拽排序全分支（onDragStart/Over/Leave/End/Drop：同 key、空 dragKey、目标未命中）、
 * onToggle、applyPreset 六个预设 + layoutSaved 2s 复位、handleBackup 成功/失败、
 * handleRestore、isAdmin 三种角色形态与快捷按钮 pushSafe、布局编辑器开关与弹窗内交互。
 *
 * 方案：子组件全部 stub（PageHeader/HeaderActions/QuickActions/KpiCards/ChartRow/InfoRow），
 * 只测 index.vue 自身逻辑；mock '@/api/backup' createBackup 与 '@/stores/user'。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'

const { ElMessage, mockCreateBackup, mockPushSafe, userBox, logError } = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  mockCreateBackup: vi.fn(),
  mockPushSafe: vi.fn(),
  userBox: { currentUser: { role: 'admin', is_superuser: false } },
  logError: vi.fn(),
}))

vi.mock('element-plus', () => ({ ElMessage }))

vi.mock('@/api/backup', () => ({ createBackup: mockCreateBackup }))

vi.mock('@/api/request', () => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  del: vi.fn(),
  apiRequest: vi.fn(),
  getCsrfToken: vi.fn(() => Promise.resolve('test-csrf')),
}))

vi.mock('@/api/search', () => ({
  globalSearch: vi.fn(),
  SEARCH_TYPE_LABELS: {},
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({ user: userBox.currentUser }),
}))

vi.mock('@/stores/user', () => ({
  useUserStore: () => userBox,
}))

vi.mock('@/stores/menu', () => ({
  useMenuStore: () => ({ loaded: true, fetchMenus: vi.fn() }),
}))

vi.mock('@/composables/useRouterSafe', () => ({
  useRouterSafe: () => ({ pushSafe: mockPushSafe }),
}))

vi.mock('@/utils/logger', () => ({
  logger: { error: logError, warn: vi.fn(), info: vi.fn(), debug: vi.fn() },
}))

vi.mock('@/utils/echarts', () => ({
  default: {
    init: () => ({ setOption: vi.fn(), dispose: vi.fn(), resize: vi.fn() }),
    graphic: { LinearGradient: vi.fn(() => ({})) },
  },
}))

import Dashboard from '@/views/dashboard/index.vue'

const childStubs = {
  // 共享 PageHeader 标准件（W11-T45 去重后由 index.vue 引用）：渲染 title/extra 插槽，
  // 使工作台的操作区 stub 与欢迎语插槽内容被真实渲染（覆盖 index.vue 的插槽函数）。
  PageHeader: {
    name: 'PageHeader',
    props: ['title', 'subtitle', 'showBack', 'backTo', 'level'],
    template: '<div class="ph-stub"><slot name="title" /><slot name="extra" /></div>',
  },
  HeaderActions: {
    name: 'HeaderActions',
    props: ['isAdmin', 'backingUp'],
    template: '<div class="ha-stub" />',
    emits: ['toggle-layout', 'backup'],
  },
  QuickActions: {
    name: 'QuickActions',
    props: ['isManager', 'isAdmin', 'backingUp'],
    template: '<div class="qa-stub" />',
    emits: ['backup', 'restore'],
  },
  KpiCards: { name: 'KpiCards', template: '<div class="kpi-stub" />' },
  TodoListPanel: { name: 'TodoListPanel', template: '<div class="todo-stub" />' },
  ChartRow: { name: 'ChartRow', template: '<div class="chart-stub" />' },
  InfoRow: { name: 'InfoRow', template: '<div class="info-stub" />' },
}

const elStubs = {
  'el-select': {
    name: 'ElSelect',
    props: ['modelValue'],
    template: '<div class="el-select-stub"><slot /></div>',
    emits: ['update:modelValue', 'change'],
  },
  'el-option': { name: 'ElOption', template: '<div />' },
  'el-switch': {
    name: 'ElSwitch',
    props: ['modelValue'],
    template: '<div class="el-switch-stub" />',
    emits: ['update:modelValue', 'change'],
  },
  'el-button': { name: 'ElButton', template: '<button class="el-button-stub"><slot /></button>' },
  'el-icon': { name: 'ElIcon', template: '<span class="el-icon-stub"><slot /></span>' },
  'el-tooltip': { name: 'ElTooltip', template: '<div><slot /></div>' },
}

function mountComp() {
  const pinia = createPinia()
  setActivePinia(pinia)
  return mount(Dashboard, {
    global: { plugins: [pinia], renderStubDefaultSlot: true, stubs: { ...elStubs, ...childStubs } },
  })
}

async function clickByText(wrapper: any, text: string) {
  const btn = wrapper.findAll('button').find((b: any) => b.text().includes(text))
  expect(btn, `按钮「${text}」`).toBeTruthy()
  await btn!.trigger('click')
}

beforeEach(() => {
  vi.resetAllMocks()
  localStorage.clear()
  userBox.currentUser = { role: 'admin', is_superuser: false }
  mockCreateBackup.mockResolvedValue({ success: true })
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('布局加载与持久化', () => {
  it('无存储记录 → 默认四区块全部可见；切换开关触发 saveLayout 持久化', async () => {
    const wrapper = mountComp()
    const vm = wrapper.vm as any
    await nextTick()
    expect(vm.layoutSections.map((s: any) => s.key)).toEqual([
      'kpi',
      'todos',
      'charts',
      'quickActions',
      'info',
    ])
    expect(vm.visible.kpi).toBe(true)
    expect(wrapper.find('.kpi-stub').exists()).toBe(true)
    expect(wrapper.find('.todo-stub').exists()).toBe(true)
    expect(wrapper.find('.chart-stub').exists()).toBe(true)
    expect(wrapper.find('.info-stub').exists()).toBe(true)
    expect(wrapper.text()).toContain('常用操作')
    // 关闭「待办清单」→ 区块隐藏
    vm.layoutSections[1].visible = false
    await nextTick()
    expect(wrapper.find('.todo-stub').exists()).toBe(false)

    vm.layoutSections[0].visible = false // watch deep → saveLayout
    await nextTick()
    const saved = JSON.parse(localStorage.getItem('dashboard_layout_v2') || '[]')
    expect(saved[0].visible).toBe(false)
    // 关掉 kpi → kpi-strip 隐藏
    await nextTick()
    expect(wrapper.find('.kpi-stub').exists()).toBe(false)
    wrapper.unmount()
  })

  it('localStorage 有有效记录 → 直接加载；形状非法/损坏 JSON → 回退默认', async () => {
    localStorage.setItem(
      'dashboard_layout_v2',
      JSON.stringify([
        { key: 'kpi', label: '数据概览', visible: true },
        { key: 'charts', label: '数据趋势', visible: false },
        { key: 'quickActions', label: '快捷入口', visible: true },
        { key: 'info', label: '最新动态', visible: false },
      ])
    )
    const wrapper = mountComp()
    const vm = wrapper.vm as any
    expect(vm.visible.charts).toBe(false)
    expect(vm.visible.info).toBe(false)
    expect(vm.visible.kpi).toBe(true)
    wrapper.unmount()

    // 形状非法：包含未知 key / 非布尔 visible → 回退默认
    localStorage.setItem(
      'dashboard_layout_v2',
      JSON.stringify([{ key: 'nope', label: 'x', visible: true }])
    )
    const wrapper2 = mountComp()
    expect((wrapper2.vm as any).visible.kpi).toBe(true)
    wrapper2.unmount()

    // 损坏 JSON → catch → 回退默认
    localStorage.setItem('dashboard_layout_v2', '{oops')
    const wrapper3 = mountComp()
    expect((wrapper3.vm as any).layoutSections.length).toBe(5)
    wrapper3.unmount()
  })

  it('resetLayout：写入存储失败（配额满/被禁用）→ 降级文案，不谎报已落盘', async () => {
    const wrapper = mountComp()
    const vm = wrapper.vm as any
    await nextTick()

    // 只让本实例写失败：spy 在 localStorage 实例上（jsdom 的方法继承自 Storage.prototype）
    const spy = vi.spyOn(window.localStorage, 'setItem').mockImplementation(() => {
      throw new DOMException('QuotaExceededError', 'QuotaExceededError')
    })
    // saveLayout 直接返回 false（写路径的 catch）
    expect(vm.saveLayout()).toBe(false)
    // resetLayout 据此走降级提示
    vm.resetLayout()
    expect(ElMessage.success).toHaveBeenCalledWith(
      '已恢复默认布局（当前存储不可用，仅本次会话生效）'
    )
    expect(vm.layoutSections.every((s: any) => s.visible)).toBe(true)

    spy.mockRestore()
    wrapper.unmount()
  })

  it('resetLayout → 恢复默认 + 持久化 + 成功提示', async () => {
    const wrapper = mountComp()
    const vm = wrapper.vm as any
    await nextTick()
    wrapper.findComponent({ name: 'HeaderActions' }).vm.$emit('toggle-layout')
    await nextTick()
    vm.layoutSections[2].visible = false
    await clickByText(wrapper, '恢复默认')
    expect(vm.layoutSections.every((s: any) => s.visible)).toBe(true)
    expect(ElMessage.success).toHaveBeenCalledWith('已恢复默认布局')
    const saved = JSON.parse(localStorage.getItem('dashboard_layout_v2') || '[]')
    expect(saved.every((s: any) => s.visible)).toBe(true)
    wrapper.unmount()
  })
})

describe('布局编辑器', () => {
  it('PageHeader emit toggle-layout → 编辑器显示；「完成」关闭；el-select change → applyPreset', async () => {
    const wrapper = mountComp()
    const vm = wrapper.vm as any
    expect(vm.showLayoutEditor).toBe(false)
    wrapper.findComponent({ name: 'HeaderActions' }).vm.$emit('toggle-layout')
    await nextTick()
    expect(vm.showLayoutEditor).toBe(true)
    expect(wrapper.find('.layout-editor').exists()).toBe(true)

    // el-select 选择「紧凑模式」
    const select = wrapper.findComponent({ name: 'ElSelect' })
    select.vm.$emit('update:modelValue', 'compact')
    select.vm.$emit('change', 'compact')
    await nextTick()
    expect(vm.layoutSections.filter((s: any) => s.visible).map((s: any) => s.key)).toEqual([
      'kpi',
      'quickActions',
    ])
    // layoutSaved 2s 后复位
    expect(vm.layoutSaved).toBe(true)
    await new Promise((r) => setTimeout(r, 2100))
    expect(vm.layoutSaved).toBe(false)

    await clickByText(wrapper, '完成')
    expect(vm.showLayoutEditor).toBe(false)
    wrapper.unmount()
  })

  it('applyPreset 全部六个预设分支', async () => {
    const wrapper = mountComp()
    const vm = wrapper.vm as any
    const allKeys = ['kpi', 'todos', 'charts', 'quickActions', 'info']
    const visibleKeys = () => vm.layoutSections.filter((s: any) => s.visible).map((s: any) => s.key)

    vm.applyPreset('default')
    expect(visibleKeys()).toEqual(allKeys)
    vm.applyPreset('compact')
    expect(visibleKeys()).toEqual(['kpi', 'quickActions'])
    vm.applyPreset('expand')
    expect(visibleKeys()).toEqual(allKeys)
    vm.applyPreset('role_admin')
    expect(visibleKeys()).toEqual(allKeys)
    vm.applyPreset('role_officer')
    expect(visibleKeys()).toEqual(['kpi', 'todos', 'charts', 'quickActions'])
    vm.applyPreset('role_viewer')
    expect(visibleKeys()).toEqual(['kpi', 'info'])
    wrapper.unmount()
  })

  it('onToggle 保存布局并显示「已保存」（无 2s 复位，仅 applyPreset 复位）', async () => {
    const wrapper = mountComp()
    const vm = wrapper.vm as any
    vm.onToggle()
    expect(vm.layoutSaved).toBe(true)
    expect(JSON.parse(localStorage.getItem('dashboard_layout_v2') || '[]').length).toBe(5)
    wrapper.unmount()
  })
})

describe('拖拽排序', () => {
  it('onDrop 不同 key 重排并持久化；同 key / 空 dragKey / 未命中跳过', async () => {
    const wrapper = mountComp()
    const vm = wrapper.vm as any
    await nextTick()
    const order = () => vm.layoutSections.map((s: any) => s.key)

    // 同 key → 不动
    vm.onDragStart({} as any, 'kpi')
    vm.onDrop({} as any, 'kpi')
    expect(order()).toEqual(['kpi', 'todos', 'charts', 'quickActions', 'info'])

    // 把 kpi 拖到 charts 位置
    vm.onDrop({} as any, 'charts')
    expect(order()).toEqual(['todos', 'charts', 'kpi', 'quickActions', 'info'])

    // 空 dragKey → 直接 return
    vm.onDragStart({} as any, '')
    vm.onDrop({} as any, 'kpi')
    expect(order()).toEqual(['todos', 'charts', 'kpi', 'quickActions', 'info'])

    // from/to 未命中 → 跳过
    vm.onDragStart({} as any, 'nonexistent')
    vm.onDrop({} as any, 'kpi')
    expect(order()).toEqual(['todos', 'charts', 'kpi', 'quickActions', 'info'])

    // dragOverKey 状态流转
    vm.onDragOver('info')
    expect(vm.dragOverKey).toBe('info')
    vm.onDragLeave()
    expect(vm.dragOverKey).toBe('')
    vm.onDragStart({} as any, 'charts')
    vm.onDrop({} as any, 'quickActions')
    vm.onDragEnd()
    expect(vm.dragOverKey).toBe('')
    expect(vm.layoutSaved).toBe(true)
    wrapper.unmount()
  })

  it('模板内联事件：打开编辑器 → 真实 DOM 拖拽事件触发 onDragStart/onDrop/onDragEnd', async () => {
    const wrapper = mountComp()
    await nextTick()
    wrapper.findComponent({ name: 'HeaderActions' }).vm.$emit('toggle-layout')
    await nextTick()
    const items = wrapper.findAll('.layout-item')
    expect(items.length).toBe(5)
    await items[0].trigger('dragstart', { dataTransfer: {} })
    await items[2].trigger('dragover')
    await items[2].trigger('drop')
    await items[2].trigger('dragend')
    await nextTick()
    const vm = wrapper.vm as any
    expect(vm.dragOverKey).toBe('')
    // kpi 被移到 charts（items[2]）之后的位置
    expect(vm.layoutSections.map((s: any) => s.key)[2]).toBe('kpi')
    await items[0].trigger('dragleave')
    await nextTick()
    expect(vm.dragOverKey).toBe('')
    wrapper.unmount()
  })

  it('模板内联事件：el-switch v-model 更新 visible；快捷入口设置按钮打开编辑器', async () => {
    const wrapper = mountComp()
    await nextTick()
    // 快捷入口面板的设置按钮（仅图标无文字）→ showLayoutEditor 翻转
    const quickPanelBtn = wrapper.find('.quick-panel .el-button-stub')
    expect(quickPanelBtn.exists()).toBe(true)
    await quickPanelBtn.trigger('click')
    await nextTick()
    const vm = wrapper.vm as any
    expect(vm.showLayoutEditor).toBe(true)
    // el-switch v-model 更新 → section.visible 写入
    const switchStub = wrapper.findComponent({ name: 'ElSwitch' })
    switchStub.vm.$emit('update:modelValue', false)
    switchStub.vm.$emit('change', false)
    await nextTick()
    expect(vm.layoutSections[0].visible).toBe(false)
    wrapper.unmount()
  })
})

describe('KPI 自动刷新', () => {
  it('refreshKpiData：页面可见 → key 自增；document.hidden → 跳过', () => {
    const wrapper = mountComp()
    const vm = wrapper.vm as any
    const before = vm.kpiRefreshKey
    vm.refreshKpiData()
    expect(vm.kpiRefreshKey).toBe(before + 1)

    Object.defineProperty(document, 'hidden', { value: true, configurable: true })
    vm.refreshKpiData()
    expect(vm.kpiRefreshKey).toBe(before + 1)
    Object.defineProperty(document, 'hidden', { value: false, configurable: true })
    wrapper.unmount()
  })

  it('60s 定时器触发刷新；unmount 清理', async () => {
    vi.useFakeTimers()
    const wrapper = mountComp()
    const vm = wrapper.vm as any
    const before = vm.kpiRefreshKey
    vi.advanceTimersByTime(60 * 1000)
    expect(vm.kpiRefreshKey).toBe(before + 1)
    vi.advanceTimersByTime(60 * 1000)
    expect(vm.kpiRefreshKey).toBe(before + 2)
    wrapper.unmount()
    vi.advanceTimersByTime(60 * 1000)
    expect(vm.kpiRefreshKey).toBe(before + 2)
    vi.useRealTimers()
  })
})

describe('备份与恢复', () => {
  it('handleBackup 成功 → createBackup 调用 + 成功提示；失败 → 错误提示', async () => {
    const wrapper = mountComp()
    const vm = wrapper.vm as any
    mockCreateBackup.mockResolvedValue({ success: true })
    await vm.handleBackup()
    expect(mockCreateBackup).toHaveBeenCalledWith({ description: '手动备份' })
    expect(ElMessage.success).toHaveBeenCalledWith('备份创建成功')
    expect(vm.backingUp).toBe(false)

    mockCreateBackup.mockRejectedValue(new Error('磁盘满'))
    await vm.handleBackup()
    expect(ElMessage.error).toHaveBeenCalledWith('磁盘满')
    expect(vm.backingUp).toBe(false)

    mockCreateBackup.mockRejectedValue({})
    await vm.handleBackup()
    expect(ElMessage.error).toHaveBeenCalledWith('备份失败，请前往系统管理→备份管理重试')
    wrapper.unmount()
  })

  it('QuickActions emit restore → pushSafe(/system/backup)；backup → handleBackup', async () => {
    const wrapper = mountComp()
    await nextTick()
    const qa = wrapper.findComponent({ name: 'QuickActions' })
    expect(qa.exists()).toBe(true)
    qa.vm.$emit('restore')
    await nextTick()
    expect(mockPushSafe).toHaveBeenCalledWith('/system/backup')

    qa.vm.$emit('backup')
    await flushPromises()
    expect(mockCreateBackup).toHaveBeenCalled()
    wrapper.unmount()
  })
})

describe('角色与快捷按钮', () => {
  it('admin → 显示新建项目/新增帮扶村；点击各按钮 pushSafe', async () => {
    const wrapper = mountComp()
    await nextTick()
    expect(wrapper.text()).toContain('新建项目')
    expect(wrapper.text()).toContain('新增帮扶村')
    await clickByText(wrapper, '新建项目')
    expect(mockPushSafe).toHaveBeenCalledWith('/projects/create')
    await clickByText(wrapper, '新增帮扶村')
    expect(mockPushSafe).toHaveBeenCalledWith('/supported-villages')
    await clickByText(wrapper, '资金申请')
    expect(mockPushSafe).toHaveBeenCalledWith('/funds/user')
    await clickByText(wrapper, '数据上报')
    expect(mockPushSafe).toHaveBeenCalledWith('/data-package/report')
    wrapper.unmount()
  })

  it('super_admin / is_superuser → isAdmin 为真', async () => {
    userBox.currentUser = { role: 'super_admin', is_superuser: false }
    const wrapper = mountComp()
    expect((wrapper.vm as any).isAdmin).toBe(true)
    expect((wrapper.vm as any).isManager).toBe(true)
    wrapper.unmount()

    userBox.currentUser = { role: 'user', is_superuser: true }
    const wrapper2 = mountComp()
    expect((wrapper2.vm as any).isAdmin).toBe(true)
    wrapper2.unmount()
  })

  it('普通用户 → isAdmin 为假，隐藏管理按钮', () => {
    userBox.currentUser = { role: 'user', is_superuser: false }
    const wrapper = mountComp()
    expect((wrapper.vm as any).isAdmin).toBe(false)
    expect(wrapper.text()).not.toContain('新建项目')
    expect(wrapper.text()).not.toContain('新增帮扶村')
    wrapper.unmount()
  })

  it('currentUser 无 role / 为 null → role || 空串兜底，isAdmin 为假', async () => {
    userBox.currentUser = { is_superuser: false } as any
    const wrapper = mountComp()
    await nextTick()
    expect((wrapper.vm as any).isAdmin).toBe(false)
    wrapper.unmount()

    userBox.currentUser = null as any
    const wrapper2 = mountComp()
    await nextTick()
    expect((wrapper2.vm as any).isAdmin).toBe(false)
    wrapper2.unmount()
  })
})

describe('页头：共享 PageHeader 骨架 + HeaderActions 操作区（W11-T45 去重）', () => {
  it('标题/日期/层级与操作区 props 注入', async () => {
    userBox.currentUser = {
      full_name: '张科长',
      username: 'zhang',
      role: 'admin',
      is_superuser: false,
    }
    const wrapper = mountComp()
    await nextTick()

    const header = wrapper.findComponent({ name: 'PageHeader' })
    expect(header.props('title')).toBe('欢迎回来，张科长')
    expect(header.props('subtitle')).toBe((wrapper.vm as any).formattedDate)
    expect(header.props('level')).toBe(1)
    expect(wrapper.find('.welcome-name').text()).toBe('张科长')
    expect((wrapper.vm as any).formattedDate).toMatch(
      /\d{4}年\d{1,2}月\d{1,2}日 周[日一二三四五六]/
    )

    const actions = wrapper.findComponent({ name: 'HeaderActions' })
    expect(actions.props('isAdmin')).toBe(true)
    expect(actions.props('backingUp')).toBe(false)
    wrapper.unmount()
  })

  it('displayName 兜底：无 full_name → username；两者皆无 → 管理员', async () => {
    userBox.currentUser = { username: 'zhangsan', role: 'user', is_superuser: false }
    const wrapper = mountComp()
    expect((wrapper.vm as any).displayName).toBe('zhangsan')
    wrapper.unmount()

    userBox.currentUser = { role: 'user', is_superuser: false }
    const wrapper2 = mountComp()
    expect((wrapper2.vm as any).displayName).toBe('管理员')
    wrapper2.unmount()
  })

  it('HeaderActions emit backup → 复用页面 handleBackup 创建备份', async () => {
    userBox.currentUser = { role: 'admin', is_superuser: false }
    const wrapper = mountComp()
    await nextTick()
    wrapper.findComponent({ name: 'HeaderActions' }).vm.$emit('backup')
    await flushPromises()
    expect(mockCreateBackup).toHaveBeenCalledWith({ description: '手动备份' })
    wrapper.unmount()
  })
})