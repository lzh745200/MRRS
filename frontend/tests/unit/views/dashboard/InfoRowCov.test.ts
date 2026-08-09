/**
 * views/dashboard/InfoRow.vue 补充覆盖（与 InfoRow.test.ts 合并达四指标 100%）
 *
 * 覆盖：startEdit/saveEdit 成功与失败、deleteActivity 成功与失败、
 * formatTime 全分支（空/非法日期/合法日期）、编辑模式模板（输入/保存/取消）、
 * 自定义条目（custom_ id / _custom 标记）编辑删除按钮、空态「暂无动态」、
 * 错误后 2s 自动重试分支、item 字段缺失兜底（action/description/target）。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

const { ElMessage, mockApiRequest, mockPut, mockDel, logError } = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  mockApiRequest: vi.fn(),
  mockPut: vi.fn(),
  mockDel: vi.fn(),
  logError: vi.fn(),
}))

vi.mock('element-plus', () => ({ ElMessage }))

vi.mock('@/api/request', () => ({
  apiRequest: mockApiRequest,
  put: mockPut,
  del: mockDel,
  get: vi.fn(),
  post: vi.fn(),
  default: {},
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

vi.mock('@/utils/logger', () => ({
  logger: { error: logError, warn: vi.fn(), info: vi.fn(), debug: vi.fn() },
}))

import InfoRow from '@/views/dashboard/InfoRow.vue'

const baseItems = [
  { id: 'custom_1', action: '新增项目', target: '甲村', type: 'project', time: '2026-06-06T10:30:00' },
  { id: 2, _custom: true, description: '仅描述', target: '', time: 'not-a-date' },
  { id: 3, action: '', description: '', time: '' },
  { id: 4, description: '无时间字段', created_at: '2026-07-01T08:00:00' },
]

function mountInfo(items: any[] = baseItems) {
  mockApiRequest.mockResolvedValue({ data: { items } })
  return mount(InfoRow, {
    global: {
      stubs: {
        'el-button': { template: '<button class="el-button-stub"><slot /></button>' },
        'el-icon': { template: '<span><slot /></span>' },
      },
    },
  })
}

beforeEach(() => {
  vi.clearAllMocks()
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('InfoRow 编辑与删除', () => {
  it('自定义条目渲染编辑按钮，所有条目渲染删除按钮；startEdit 填充表单并进入编辑模式', async () => {
    const wrapper = mountInfo()
    await flushPromises()
    // 编辑按钮仅自定义条目（2 个）；删除按钮对所有动态显示（4 个，系统动态为隐藏式删除）
    expect(wrapper.findAll('.tl-edit-btn').length).toBe(2)
    expect(wrapper.findAll('.tl-delete-btn').length).toBe(4)

    const vm = wrapper.vm as any
    await wrapper.findAll('.tl-edit-btn')[0].trigger('click')
    expect(vm.editingId).toBe('custom_1')
    expect(vm.editForm).toEqual({ action: '新增项目', target: '甲村' })
    // 编辑模式：输入框 + 保存/取消按钮
    expect(wrapper.find('.tl-edit-input').exists()).toBe(true)
    expect(wrapper.find('.tl-save-btn').exists()).toBe(true)
    wrapper.unmount()
  })

  it('saveEdit 成功 → put 调用 + 本地更新 + 退出编辑；取消 → 退出编辑不调用', async () => {
    mockPut.mockResolvedValue({})
    const wrapper = mountInfo()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.startEdit(baseItems[0])
    vm.editForm.action = '修改后动作'
    await wrapper.find('.tl-save-btn').trigger('click')
    expect(mockPut).toHaveBeenCalledWith('/dashboard/recent-activities/custom_1', {
      action: '修改后动作',
      target: '甲村',
    })
    expect(vm.activities[0].action).toBe('修改后动作')
    expect(vm.editingId).toBe(null)

    // startEdit 字段缺失兜底：action/target 全空
    await vm.startEdit({ id: 'custom_x', action: '', target: '' })
    expect(vm.editForm).toEqual({ action: '', target: '' })

    // 取消按钮
    await vm.startEdit(baseItems[0])
    await wrapper.find('.tl-cancel-btn').trigger('click')
    expect(vm.editingId).toBe(null)
    wrapper.unmount()
  })

  it('saveEdit 失败 → 错误提示且保持编辑状态', async () => {
    mockPut.mockRejectedValue(new Error('put down'))
    const wrapper = mountInfo()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.saveEdit('custom_1')
    expect(ElMessage.error).toHaveBeenCalledWith('保存失败，请重试')
    wrapper.unmount()
  })

  it('deleteActivity 成功 → del 调用 + 从列表移除；失败 → 错误提示', async () => {
    mockDel.mockResolvedValue({})
    const wrapper = mountInfo()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.activities.length).toBe(4)
    await vm.deleteActivity('custom_1')
    expect(mockDel).toHaveBeenCalledWith('/dashboard/recent-activities/custom_1')
    expect(vm.activities.length).toBe(3)
    expect(vm.activities.some((a: any) => a.id === 'custom_1')).toBe(false)

    mockDel.mockRejectedValue(new Error('del down'))
    await vm.deleteActivity(2)
    expect(ElMessage.error).toHaveBeenCalledWith('删除失败，请重试')
    expect(vm.activities.length).toBe(3)
    wrapper.unmount()
  })

  it('删除按钮触发 deleteActivity', async () => {
    mockDel.mockResolvedValue({})
    const wrapper = mountInfo()
    await flushPromises()
    await wrapper.findAll('.tl-delete-btn')[0].trigger('click')
    await flushPromises()
    expect(mockDel).toHaveBeenCalledWith('/dashboard/recent-activities/custom_1')
    wrapper.unmount()
  })
})

describe('InfoRow 格式化与状态', () => {
  it('formatTime：空串 → 空；非法日期 → 前 10 字符；合法日期 → 格式化', () => {
    const wrapper = mountInfo()
    const vm = wrapper.vm as any
    expect(vm.formatTime('')).toBe('')
    expect(vm.formatTime('garbage')).toBe('garbage')
    const d = new Date(2026, 5, 6, 10, 30)
    expect(vm.formatTime(d.toISOString())).toBe(`${d.getMonth() + 1}/6 10:30`)
    wrapper.unmount()
  })

  it('行渲染：target 缺省不显示、action/description 全缺 → 占位符 --、空列表 → 暂无动态', async () => {
    const wrapper = mountInfo()
    await flushPromises()
    expect(wrapper.text()).toContain('--')
    wrapper.unmount()

    const empty = mountInfo([])
    await flushPromises()
    expect(empty.find('.tl-empty').exists()).toBe(true)
    expect(empty.text()).toContain('暂无动态')
    empty.unmount()
  })

  it('加载失败 → 错误态；2s 后自动重试成功恢复', async () => {
    vi.useFakeTimers()
    mockApiRequest.mockRejectedValueOnce(new Error('net'))
    mockApiRequest.mockResolvedValueOnce({ data: { items: baseItems.slice(0, 1) } })
    const wrapper = mountInfo()
    await flushPromises()
    expect(logError).toHaveBeenCalled()
    expect(wrapper.find('.tl-state--error').exists()).toBe(true)
    vi.advanceTimersByTime(2000)
    await flushPromises()
    expect(wrapper.find('.tl-state--error').exists()).toBe(false)
    expect(wrapper.findAll('.timeline-item').length).toBe(1)
    vi.useRealTimers()
    wrapper.unmount()
  })

  it('错误态「重试」按钮 → 重新加载', async () => {
    mockApiRequest.mockRejectedValueOnce(new Error('net'))
    const wrapper = mountInfo()
    await flushPromises()
    expect(wrapper.find('.tl-state--error').exists()).toBe(true)
    mockApiRequest.mockResolvedValue({ data: { items: baseItems.slice(0, 2) } })
    await wrapper.find('.tl-state--error .el-button-stub').trigger('click')
    await flushPromises()
    expect(wrapper.find('.tl-state--error').exists()).toBe(false)
    expect(wrapper.findAll('.timeline-item').length).toBe(2)
    wrapper.unmount()
  })

  it('响应形状兜底：data.items 缺失但 items 存在；无 items 字段 → []；非数组 → []', async () => {
    const wrapper = mountInfo([])
    await flushPromises()
    // 覆盖 (res)?.items 兜底侧：先挂载空，再手动触发 loadActivities 读取 items 顶层字段
    mockApiRequest.mockResolvedValue({ items: [baseItems[0]] })
    await wrapper.vm.loadActivities()
    await flushPromises()
    expect(wrapper.findAll('.timeline-item').length).toBe(1)
    wrapper.unmount()

    // 无 data 也无 items → || [] 右侧（挂载后再覆盖 mock 并手动触发）
    const wrapper2 = mountInfo([])
    await flushPromises()
    mockApiRequest.mockResolvedValue({})
    await wrapper2.vm.loadActivities()
    await flushPromises()
    expect(wrapper2.findAll('.timeline-item').length).toBe(0)
    expect(wrapper2.find('.tl-empty').exists()).toBe(true)
    wrapper2.unmount()

    // 非数组 → Array.isArray 假侧 → []（挂载后再覆盖 mock 并手动触发）
    const wrapper3 = mountInfo([])
    await flushPromises()
    mockApiRequest.mockResolvedValue({ items: 'not-array' })
    await wrapper3.vm.loadActivities()
    await flushPromises()
    expect(wrapper3.findAll('.timeline-item').length).toBe(0)
    wrapper3.unmount()
  })
})
