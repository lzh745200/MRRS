/**
 * views/dashboard/components/TodoListPanel.vue 专属测试（W23 W4，四指标 100%）
 *
 * 覆盖：待办加载（listTodos 参数/条数截断）、加载/错误/空三件套
 * （.app-loading/.app-error 重试/.app-empty）、优先级标签与类型、截止时间格式化、
 * 「查看全部待办」导航、响应形状兜底。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

const { mockListTodos, mockPushSafe, logError } = vi.hoisted(() => ({
  mockListTodos: vi.fn(),
  mockPushSafe: vi.fn(),
  logError: vi.fn(),
}))

vi.mock('@/api/todos', () => ({
  listTodos: (...a: any[]) => mockListTodos(...a),
}))

vi.mock('@/composables/useRouterSafe', () => ({
  useRouterSafe: () => ({ pushSafe: mockPushSafe }),
}))

vi.mock('@/utils/logger', () => ({
  logger: { error: logError, warn: vi.fn(), info: vi.fn(), debug: vi.fn() },
}))

import TodoListPanel from '@/views/dashboard/components/TodoListPanel.vue'

const rows = [
  { id: 1, title: '完善帮扶村台账', priority: 'high', deadline: '2026-10-20T18:00:00' },
  { id: 2, title: '审核项目申报', priority: 'medium', deadline: null },
  { id: 3, title: '', priority: 'low' },
  { id: 4, title: '其他事项', priority: 'unknown' },
  { id: 5, title: '第五条' },
  { id: 6, title: '第六条（超出 5 条应截断）' },
]

function mountPanel() {
  return mount(TodoListPanel, {
    global: {
      stubs: {
        'el-button': { template: '<button class="el-button-stub"><slot /></button>' },
        'el-tag': { template: '<span class="el-tag-stub"><slot /></span>' },
        'el-skeleton': { template: '<div class="skeleton-stub" />' },
      },
    },
  })
}

beforeEach(() => {
  vi.clearAllMocks()
  mockListTodos.mockResolvedValue({ items: rows, total: rows.length })
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('TodoListPanel', () => {
  it('加载未完成待办：参数 completed=false/page=1/page_size=5，最多渲染 5 条并显示计数', async () => {
    const wrapper = mountPanel()
    await flushPromises()
    await nextTick()

    expect(mockListTodos).toHaveBeenCalledWith({ completed: false, page: 1, page_size: 5 })
    expect(wrapper.find('.todo-list-card').classes()).toContain('app-card')
    expect(wrapper.findAll('.todo-item').length).toBe(5)
    expect(wrapper.find('[data-testid="todo-count"]').text()).toBe('5 项')
    expect(wrapper.text()).toContain('完善帮扶村台账')
    expect(wrapper.text()).toContain('未命名待办') // 标题空值兜底
    expect(wrapper.text()).toContain('紧急')
    expect(wrapper.text()).toContain('普通')
    expect(wrapper.text()).toContain('较低')
    expect(wrapper.text()).toContain('10-20 18:00') // 截止时间存在（格式化后）
    wrapper.unmount()
  })

  it('加载中显示 .app-loading 骨架，完成后隐藏', async () => {
    let resolve!: (v: any) => void
    mockListTodos.mockImplementation(() => new Promise((r) => (resolve = r)))
    const wrapper = mountPanel()
    await nextTick()
    expect(wrapper.find('.app-loading').exists()).toBe(true)
    expect(wrapper.find('[data-testid="todo-loading"]').exists()).toBe(true)
    resolve({ items: rows.slice(0, 2), total: 2 })
    await flushPromises()
    expect(wrapper.find('.app-loading').exists()).toBe(false)
    expect(wrapper.findAll('.todo-item').length).toBe(2)
    wrapper.unmount()
  })

  it('加载失败 → .app-error；重试按钮重新加载成功', async () => {
    mockListTodos.mockRejectedValueOnce(new Error('net'))
    const wrapper = mountPanel()
    await flushPromises()
    expect(logError).toHaveBeenCalled()
    expect(wrapper.find('.app-error').exists()).toBe(true)
    expect(wrapper.find('[data-testid="todo-error"]').exists()).toBe(true)
    expect(wrapper.findAll('.todo-item').length).toBe(0)

    mockListTodos.mockResolvedValue({ items: rows.slice(0, 1), total: 1 })
    await wrapper.find('[data-testid="todo-error"] .el-button-stub').trigger('click')
    await flushPromises()
    expect(wrapper.find('.app-error').exists()).toBe(false)
    expect(wrapper.findAll('.todo-item').length).toBe(1)
    wrapper.unmount()
  })

  it('空列表 → .app-empty 暂无待办；「查看全部待办」导航 /todos', async () => {
    mockListTodos.mockResolvedValue({ items: [], total: 0 })
    const wrapper = mountPanel()
    await flushPromises()
    expect(wrapper.find('.app-empty').exists()).toBe(true)
    expect(wrapper.text()).toContain('暂无待办事项')
    expect(wrapper.find('[data-testid="todo-count"]').text()).toBe('0 项')

    await wrapper.find('[data-testid="todo-view-all"]').trigger('click')
    expect(mockPushSafe).toHaveBeenCalledWith('/todos')
    wrapper.unmount()
  })

  it('响应形状兜底：裸数组 / {data:{items}} / 非数组 → []', async () => {
    mockListTodos.mockResolvedValue([rows[0]])
    const wrapper = mountPanel()
    await flushPromises()
    expect((wrapper.vm as any).todos.length).toBe(1)
    wrapper.unmount()

    mockListTodos.mockResolvedValue({ data: { items: rows.slice(0, 2) } })
    const wrapper2 = mountPanel()
    await flushPromises()
    expect((wrapper2.vm as any).todos.length).toBe(2)
    wrapper2.unmount()

    mockListTodos.mockResolvedValue({ items: 'bad' })
    const wrapper3 = mountPanel()
    await flushPromises()
    expect((wrapper3.vm as any).todos).toEqual([])
    wrapper3.unmount()
  })

  it('优先级/截止时间辅助函数全分支', async () => {
    const wrapper = mountPanel()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.priorityLabel('high')).toBe('紧急')
    expect(vm.priorityLabel('medium')).toBe('普通')
    expect(vm.priorityLabel('low')).toBe('较低')
    expect(vm.priorityLabel(undefined)).toBe('普通')
    expect(vm.priorityType('high')).toBe('danger')
    expect(vm.priorityType('medium')).toBe('warning')
    expect(vm.priorityType('low')).toBe('info')
    expect(vm.priorityType(undefined)).toBe('info')
    expect(vm.formatDeadline(null)).toBe('')
    expect(vm.formatDeadline('2026-10-20T18:00:00')).toContain('10-20')
    wrapper.unmount()
  })
})
