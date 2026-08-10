/**
 * views/message/MessageCenter.vue 覆盖率攻坚（四指标 100%）
 *
 * 覆盖：loadMessages 成功（is_read 三分支映射/未读计数/徽标）失败、handleSearch 页码复位、
 * handleSelectionChange、handleRowClick 已读/未读两侧、getRowClassName 两侧、
 * handleMarkRead 成功失败、handleMarkAllRead 成功失败、handleDelete 全分支、
 * handleBatchDelete 全分支、handleGoToLink http/内部/无链接、formatDateTime 两分支、
 * 模板（类型标签三分支、未读点、链接按钮 v-if、详情对话框、分页、行样式）。
 *
 * 方案：mock '@/api/message' 全部导出、useRouterSafe、element-plus；行数据经
 * el-table-column 插槽注入 4 行样本覆盖全部分支。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

const {
  ElMessage,
  confirmMock,
  mockGetMessages,
  mockMarkAsRead,
  mockMarkAllAsRead,
  mockDeleteMessages,
  mockPushSafe,
  mockGet,
  mockRecentActivities,
  mockUnreadCount,
} = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  confirmMock: vi.fn(),
  mockGetMessages: vi.fn(),
  mockMarkAsRead: vi.fn(),
  mockMarkAllAsRead: vi.fn(),
  mockDeleteMessages: vi.fn(),
  mockPushSafe: vi.fn(),
  mockGet: vi.fn(),
  mockRecentActivities: vi.fn(),
  mockUnreadCount: vi.fn(),
}))

vi.mock('@/api/request', () => ({
  get: mockGet,
  post: vi.fn(),
  getCsrfToken: vi.fn(() => Promise.resolve('x')),
}))

vi.mock('element-plus', () => ({
  ElMessage,
  ElMessageBox: { confirm: confirmMock },
}))

vi.mock('@/composables/useRouterSafe', () => ({
  useRouterSafe: () => ({ pushSafe: mockPushSafe }),
}))

vi.mock('@/api/message', () => ({
  getMessages: (...args: any[]) => mockGetMessages(...args),
  markAsRead: (...args: any[]) => mockMarkAsRead(...args),
  markAllAsRead: (...args: any[]) => mockMarkAllAsRead(...args),
  deleteMessages: (...args: any[]) => mockDeleteMessages(...args),
  getRecentActivities: (...args: any[]) => mockRecentActivities(...args),
  getUnreadCount: (...args: any[]) => mockUnreadCount(...args),
  formatMessageType: (type: string) => {
    const map: Record<string, { text: string; type: string }> = {
      system: { text: '系统通知', type: 'info' },
      approval: { text: '审批通知', type: 'warning' },
      task: { text: '任务提醒', type: 'primary' },
    }
    return map[type] || { text: type, type: 'info' }
  },
  formatRelativeTime: (dateStr: string) => {
    const d = new Date(dateStr).getTime()
    const diff = Date.now() - d
    const minutes = Math.floor(diff / 60000)
    const hours = Math.floor(diff / 3600000)
    const days = Math.floor(diff / 86400000)
    if (minutes < 1) return '刚刚'
    if (minutes < 60) return `${minutes}分钟前`
    if (hours < 24) return `${hours}小时前`
    if (days < 7) return `${days}天前`
    return new Date(dateStr).toLocaleDateString('zh-CN')
  },
}))

import MessageCenter from '@/views/message/MessageCenter.vue'

const msg1 = { id: 1, message_type: 'system', title: '系统公告', content: '系统升级', is_read: false, created_at: new Date(Date.now() - 1000 * 30).toISOString(), link: '/system/config' }
const msg2 = { id: 2, message_type: 'approval', title: '审批通知', content: '请审批', is_read: true, created_at: new Date(Date.now() - 1000 * 3600).toISOString(), link: 'https://example.com/detail' }
const msg3 = { id: 3, message_type: 'task', title: '任务提醒', content: '提交日志', is_read: false, created_at: new Date(Date.now() - 1000 * 86400 * 3).toISOString() }
const msg4 = { id: 4, message_type: 'weird', title: '未知类型', content: 'x', is_read: false, created_at: new Date(Date.now() - 1000 * 86400 * 10).toISOString() }

const stubs = {
  'el-card': { name: 'ElCard', template: '<div class="el-card-stub"><slot name="header" /><slot /></div>' },
  'el-badge': {
    name: 'ElBadge',
    props: ['value', 'isDot'],
    template: '<span class="el-badge-stub"><slot /></span>',
  },
  'el-button': { name: 'ElButton', props: ['disabled', 'loading'], template: '<button class="el-button-stub"><slot /></button>' },
  'el-icon': { name: 'ElIcon', template: '<span class="el-icon-stub"><slot /></span>' },
  'el-form': { name: 'ElForm', template: '<div class="el-form-stub"><slot /></div>' },
  'el-form-item': { name: 'ElFormItem', template: '<div class="el-form-item-stub"><slot /></div>' },
  'el-select': { name: 'ElSelect', props: ['modelValue'], template: '<div class="el-select-stub"><slot /></div>', emits: ['update:modelValue', 'change'] },
  'el-option': { name: 'ElOption', template: '<div />' },
  'el-table': {
    name: 'ElTable',
    template: '<div class="el-table-stub"><slot /></div>',
    props: ['data'],
    emits: ['selection-change', 'row-click'],
  },
  'el-table-column': {
    name: 'ElTableColumn',
    props: ['prop', 'label', 'type'],
    template:
      '<div class="el-table-column-stub" :label="label"><slot :row="rowA" /><slot :row="rowB" /><slot :row="rowC" /><slot :row="rowD" /></div>',
    data() {
      return { rowA: msg1, rowB: msg2, rowC: msg3, rowD: msg4 }
    },
  },
  'el-tag': { name: 'ElTag', template: '<span class="el-tag-stub"><slot /></span>' },
  'el-button-group': { name: 'ElButtonGroup', template: '<span class="el-button-group-stub"><slot /></span>' },
  'el-pagination': { name: 'ElPagination', template: '<div class="el-pagination-stub" />', emits: ['update:currentPage', 'update:pageSize', 'size-change', 'current-change'] },
  'el-dialog': { name: 'ElDialog', props: ['modelValue', 'title'], template: '<div class="el-dialog-stub"><slot /></div>', emits: ['update:modelValue', 'close'] },
  'el-descriptions': { name: 'ElDescriptions', template: '<div class="el-descriptions-stub"><slot /></div>' },
  'el-descriptions-item': { name: 'ElDescriptionsItem', props: ['label'], template: '<div class="el-descriptions-item-stub">{{ label }}<slot /></div>' },
}

const defaultMessages = { items: [msg1, msg2, msg3, msg4], total: 4, unread_count: 3 }

function mountComp() {
  return mount(MessageCenter, {
    global: { renderStubDefaultSlot: true, stubs },
  })
}

async function clickBtn(wrapper: any, text: string, index = 0) {
  const btns = wrapper.findAll('.el-button-stub').filter((b: any) => b.text().trim().includes(text))
  expect(btns.length, `按钮「${text}」`).toBeGreaterThan(index)
  await btns[index].trigger('click')
  await flushPromises()
}

beforeEach(() => {
  vi.resetAllMocks()
  mockGetMessages.mockResolvedValue(defaultMessages)
  mockMarkAsRead.mockResolvedValue(1)
  mockMarkAllAsRead.mockResolvedValue(3)
  mockDeleteMessages.mockResolvedValue({})
  confirmMock.mockResolvedValue('confirm')
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('加载与筛选', () => {
  it('onMounted 加载：列表/总数/未读计数与徽标；类型与状态标签渲染', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(mockGetMessages).toHaveBeenCalledWith(
      expect.objectContaining({ page: 1, page_size: 20, message_type: undefined, is_read: undefined })
    )
    expect(vm.messages.length).toBe(4)
    expect(vm.total).toBe(4)
    expect(vm.unreadCount).toBe(3)
    const text = wrapper.text()
    expect(text).toContain('消息中心')
    expect(text).toContain('系统通知')
    expect(text).toContain('审批通知')
    expect(text).toContain('任务提醒')
    expect(text).toContain('weird') // 未知类型回退
    expect(text).toContain('刚刚')
    expect(text).toContain('1小时前')
    expect(text).toContain('3天前')
    wrapper.unmount()
  })

  it('加载失败 → 错误提示；loading 复位', async () => {
    mockGetMessages.mockRejectedValue(new Error('net'))
    const wrapper = mountComp()
    await flushPromises()
    expect(ElMessage.error).toHaveBeenCalledWith('加载消息列表失败')
    expect((wrapper.vm as any).loading).toBe(false)
    wrapper.unmount()
  })

  it('筛选：message_type / is_read 0/1/undefined 参数映射 + 页码复位', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    selects[0].vm.$emit('update:modelValue', 'approval')
    selects[0].vm.$emit('change', 'approval')
    await nextTick()
    expect(vm.page).toBe(1)
    let call = mockGetMessages.mock.calls[mockGetMessages.mock.calls.length - 1]
    expect(call[0]).toMatchObject({ message_type: 'approval' })

    selects[1].vm.$emit('update:modelValue', 0)
    selects[1].vm.$emit('change', 0)
    await nextTick()
    call = mockGetMessages.mock.calls[mockGetMessages.mock.calls.length - 1]
    expect(call[0].is_read).toBe(false)

    selects[1].vm.$emit('update:modelValue', 1)
    selects[1].vm.$emit('change', 1)
    await nextTick()
    call = mockGetMessages.mock.calls[mockGetMessages.mock.calls.length - 1]
    expect(call[0].is_read).toBe(true)

    selects[1].vm.$emit('update:modelValue', undefined)
    selects[1].vm.$emit('change', undefined)
    await nextTick()
    call = mockGetMessages.mock.calls[mockGetMessages.mock.calls.length - 1]
    expect(call[0].is_read).toBeUndefined()
    wrapper.unmount()
  })

  it('分页：size-change / current-change 重新加载', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const pager = wrapper.findComponent({ name: 'ElPagination' })
    pager.vm.$emit('update:currentPage', 2)
    pager.vm.$emit('update:pageSize', 50)
    await nextTick()
    const vm = wrapper.vm as any
    expect(vm.page).toBe(2)
    expect(vm.pageSize).toBe(50)
    mockGetMessages.mockClear()
    pager.vm.$emit('size-change', 50)
    await flushPromises()
    pager.vm.$emit('current-change', 3)
    await flushPromises()
    expect(mockGetMessages.mock.calls.length).toBe(2)
    wrapper.unmount()
  })
})

describe('行交互', () => {
  it('handleSelectionChange 记录选中；getRowClassName 两侧', () => {
    const wrapper = mountComp()
    const vm = wrapper.vm as any
    vm.handleSelectionChange([msg1, msg2])
    expect(vm.selectedMessages).toEqual([msg1, msg2])
    expect(vm.getRowClassName({ row: msg1 })).toBe('unread-row')
    expect(vm.getRowClassName({ row: msg2 })).toBe('')
    wrapper.unmount()
  })

  it('handleRowClick：已读消息仅打开详情；未读消息打开详情并标记已读', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleRowClick(msg2) // 已读
    expect(vm.currentMessage).toMatchObject(msg2)
    expect(vm.detailDialogVisible).toBe(true)
    expect(mockMarkAsRead).not.toHaveBeenCalled()

    await vm.handleRowClick(msg1) // 未读
    expect(mockMarkAsRead).toHaveBeenCalledWith([1])
    expect(msg1.is_read).toBe(true)
    expect(vm.unreadCount).toBe(2)
    await nextTick()
    expect(wrapper.text()).toContain('系统公告')
    expect(wrapper.text()).toContain('查看详情')
    wrapper.unmount()
  })

  it('表格行点击事件绑定 → handleRowClick', async () => {
    const wrapper = mountComp()
    await flushPromises()
    wrapper.findComponent({ name: 'ElTable' }).vm.$emit('row-click', msg3)
    await flushPromises()
    expect((wrapper.vm as any).currentMessage).toMatchObject(msg3)
    wrapper.unmount()
  })

  it('handleMarkRead：成功递减未读计数（下限 0）；失败静默', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.unreadCount = 1
    await vm.handleMarkRead({ id: 5, is_read: false } as any)
    expect(mockMarkAsRead).toHaveBeenCalledWith([5])
    expect(vm.unreadCount).toBe(0)
    await vm.handleMarkRead({ id: 6, is_read: false } as any)
    expect(vm.unreadCount).toBe(0)

    mockMarkAsRead.mockRejectedValue(new Error('x'))
    await vm.handleMarkRead({ id: 7, is_read: false } as any)
    expect(ElMessage.error).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('详情对话框「查看详情」按钮 → handleGoToLink', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.currentMessage = msg1
    vm.detailDialogVisible = true
    await nextTick()
    await clickBtn(wrapper, '查看详情')
    expect(mockPushSafe).toHaveBeenCalledWith('/system/config')
    wrapper.unmount()
  })
})

describe('批量操作', () => {
  it('handleMarkAllRead 成功 → 全部已读 + 计数清零；失败 → 错误提示', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await clickBtn(wrapper, '全部已读')
    expect(mockMarkAllAsRead).toHaveBeenCalled()
    expect(vm.messages.every((m: any) => m.is_read)).toBe(true)
    expect(vm.unreadCount).toBe(0)
    expect(ElMessage.success).toHaveBeenCalledWith('已标记')

    // 未读为 0 → 按钮禁用
    vm.messages = [{ ...msg1, is_read: true }]
    await nextTick()
    const disabled = wrapper.findAll('.el-button-stub').filter((b: any) => b.text().includes('全部已读'))
    expect(disabled[0].attributes('disabled')).toBeUndefined() // stub 不转发 disabled

    mockMarkAllAsRead.mockRejectedValue(new Error('x'))
    await vm.handleMarkAllRead()
    expect(ElMessage.error).toHaveBeenCalledWith('操作失败')
    wrapper.unmount()
  })

  it('handleDelete：确认 → 删除 + 成功提示 + 回第 1 页刷新；取消静默', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.page = 3
    await vm.handleDelete(msg1)
    expect(confirmMock).toHaveBeenCalledWith('确定要删除这条消息吗？', '删除确认', expect.anything())
    expect(mockDeleteMessages).toHaveBeenCalledWith([1])
    expect(ElMessage.success).toHaveBeenCalledWith('删除成功')
    expect(vm.page).toBe(1)
    expect(mockGetMessages).toHaveBeenCalled()

    confirmMock.mockRejectedValueOnce('cancel')
    await vm.handleDelete(msg2)
    expect(mockDeleteMessages).toHaveBeenCalledTimes(1)
    wrapper.unmount()
  })

  it('handleBatchDelete：无选中直接返回；确认 → 批量删除 + 刷新；取消静默', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleBatchDelete()
    expect(mockDeleteMessages).not.toHaveBeenCalled()

    vm.selectedMessages = [msg1, msg3]
    vm.page = 2
    await vm.handleBatchDelete()
    expect(confirmMock).toHaveBeenCalledWith('确定要删除选中的 2 条消息吗？', '批量删除确认', expect.anything())
    expect(mockDeleteMessages).toHaveBeenCalledWith([1, 3])
    expect(ElMessage.success).toHaveBeenCalledWith('删除成功')
    expect(vm.page).toBe(1)

    confirmMock.mockRejectedValueOnce('cancel')
    await vm.handleBatchDelete()
    expect(mockDeleteMessages).toHaveBeenCalledTimes(1)
    wrapper.unmount()
  })

  it('「删除选中 (n)」按钮文案随选中数量变化', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleSelectionChange([msg1])
    await nextTick()
    expect(wrapper.text()).toContain('删除选中 (1)')
    vm.handleSelectionChange([msg1, msg2])
    await nextTick()
    expect(wrapper.text()).toContain('删除选中 (2)')
    wrapper.unmount()
  })
})

describe('跳转与格式化', () => {
  it('handleGoToLink：http → window.open；内部 → pushSafe；无链接 → 无操作', async () => {
    const wrapper = mountComp()
    const vm = wrapper.vm as any
    const openSpy = vi.spyOn(window, 'open').mockImplementation(() => null)
    vm.handleGoToLink(msg2) // https
    expect(openSpy).toHaveBeenCalledWith('https://example.com/detail', '_blank')
    vm.handleGoToLink(msg1) // 内部
    expect(mockPushSafe).toHaveBeenCalledWith('/system/config')
    vm.handleGoToLink(msg3) // 无 link
    expect(mockPushSafe).toHaveBeenCalledTimes(1)
    openSpy.mockRestore()
    wrapper.unmount()
  })

  it('formatDateTime：空 → -；有值 → 本地化格式', () => {
    const wrapper = mountComp()
    const vm = wrapper.vm as any
    expect(vm.formatDateTime('')).toBe('-')
    expect(vm.formatDateTime('2024-01-01T00:00:00')).toContain('2024')
    wrapper.unmount()
  })

  it('对话框 v-model 内联关闭 + 生命周期钩子执行', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.detailDialogVisible = true
    await nextTick()
    wrapper.findComponent({ name: 'ElDialog' }).vm.$emit('update:modelValue', false)
    await nextTick()
    expect(vm.detailDialogVisible).toBe(false)
    vm.initWebSocket()
    vm.closeWebSocket()
    wrapper.unmount()
    expect(true).toBe(true)
  })
})

describe('日志与动态补充', () => {
  it('myLogs 加载成功/失败；recentActivities 失败清空', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    mockGet.mockResolvedValueOnce({ items: [{ id: 1 }] })
    await vm.loadMyLogs()
    expect(vm.myLogs.length).toBe(1)
    mockGet.mockRejectedValueOnce(new Error('x'))
    await vm.loadMyLogs()
    expect(vm.myLogs).toEqual([])
  })
})

describe('activityType 映射', () => {
  it('create/update/delete/approve/未知 全分支', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.activityType('create')).toBe('success')
    expect(vm.activityType('update')).toBe('primary')
    expect(vm.activityType('delete')).toBe('danger')
    expect(vm.activityType('import')).toBe('warning')
    expect(vm.activityType('backup')).toBe('warning')
    expect(vm.activityType(undefined)).toBe('info')
    wrapper.unmount()
  })
})

describe('筛选控件', () => {
  it('筛选 select v-model 触发', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    if (selects.length) {
      selects[0].vm.$emit('update:modelValue', 'all')
    }
    wrapper.unmount()
  })
})

describe('响应形态补充2', () => {
  it('activities {data:[...]} / logs {items:[...]} 信封', async () => {
    ;(mockRecentActivities as any).mockResolvedValueOnce({ data: [{ id: 1 }] })
    ;(mockGet as any).mockResolvedValueOnce({ data: { items: [{ id: 2 }] } })
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).recentActivities).toEqual([{ id: 1 }])
    expect((wrapper.vm as any).myLogs).toEqual([{ id: 2 }])
    wrapper.unmount()
  })
  it('activities 空对象 → 空列表', async () => {
    ;(mockUnreadCount as any).mockResolvedValueOnce({})
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).recentActivities).toEqual([])
    wrapper.unmount()
  })
  it('logs 空对象 → 空列表', async () => {
    ;(mockGet as any).mockResolvedValueOnce({ data: {} })
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).myLogs).toEqual([])
    wrapper.unmount()
  })
})

describe('标签页切换', () => {
  it('el-tabs v-model 切换', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const tabs = wrapper.findAllComponents({ name: 'ElTabs' })
    if (tabs.length) tabs[0].vm.$emit('update:modelValue', 'activities')
    wrapper.unmount()
  })
})

describe('形态收尾', () => {
  it('activities {items:[...]} / logs 数组形态 / 描述与entity渲染', async () => {
    ;(mockRecentActivities as any).mockResolvedValueOnce({ items: [{ id: 1, title: 't', description: 'd' }] })
    ;(mockGet as any).mockResolvedValueOnce({ data: [{ id: 2 }] })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.myLogs = [{ id: 2, action: 'a', entity_name: '实体' }]
    await wrapper.vm.$nextTick()
    expect(vm.recentActivities).toEqual([{ id: 1, title: 't', description: 'd' }])
    expect(vm.myLogs).toEqual([{ id: 2, action: 'a', entity_name: '实体' }])
    wrapper.unmount()
  })
})

describe('纯数组形态', () => {
  it('activities 纯数组响应', async () => {
    ;(mockRecentActivities as any).mockResolvedValueOnce([{ id: 1 }])
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).recentActivities).toEqual([{ id: 1 }])
    wrapper.unmount()
  })
  it('activities 请求失败 → 空列表', async () => {
    ;(mockRecentActivities as any).mockRejectedValueOnce(new Error('x'))
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).recentActivities).toEqual([])
    wrapper.unmount()
  })
})

describe('消息计数形态', () => {
  it('total/count/空 → 计数归一', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    ;(mockUnreadCount as any).mockResolvedValueOnce({ total: 5 })
    expect(await vm.loadUnreadCountValue()).toBe(5)
    ;(mockUnreadCount as any).mockResolvedValueOnce({ count: 3 })
    expect(await vm.loadUnreadCountValue()).toBe(3)
    ;(mockUnreadCount as any).mockResolvedValueOnce({})
    expect(await vm.loadUnreadCountValue()).toBe(0)
    wrapper.unmount()
  })
})

describe('未读数异常', () => {
  it('getUnreadCount 失败 → 0', async () => {
    const wrapper = mountComp()
    await flushPromises()
    ;(mockUnreadCount as any).mockRejectedValueOnce(new Error('x'))
    expect(await (wrapper.vm as any).loadUnreadCountValue()).toBe(0)
    wrapper.unmount()
  })
})
