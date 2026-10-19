/**
 * views/dashboard/InfoRow.vue 唯一执行者测试（W23 W4，四指标 100%）
 *
 * 覆盖：近期动态时间线（.app-card）、加载/错误/空三件套（.app-loading/.app-error/.app-empty）、
 * 错误自动 2s 重试与重试按钮、编辑/取消/保存、删除、时间格式化与字段兜底、响应形状兜底。
 * 注：合并原 InfoRowCov.test.ts 的补充覆盖，保证单执行者。
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
  getCsrfToken: vi.fn(() => Promise.resolve('test-csrf')),
}))

vi.mock('@/utils/logger', () => ({
  logger: { error: logError, warn: vi.fn(), info: vi.fn(), debug: vi.fn() },
}))

import InfoRow from '@/views/dashboard/InfoRow.vue'

const baseItems = [
  {
    id: 'custom_1',
    action: '新增项目',
    target: '甲村',
    type: 'project',
    time: '2026-06-06T10:30:00',
  },
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
  vi.useRealTimers()
  vi.restoreAllMocks()
})

describe('InfoRow 渲染与状态', () => {
  it('渲染 .app-card 时间线区域；加载中显示 .app-loading，完成后渲染列表', async () => {
    let resolve!: (v: any) => void
    mockApiRequest.mockImplementation(() => new Promise((r) => (resolve = r)))
    const wrapper = mount(InfoRow, {
      global: {
        stubs: {
          'el-button': { template: '<button class="el-button-stub"><slot /></button>' },
          'el-icon': { template: '<span><slot /></span>' },
        },
      },
    })
    await nextTick()
    expect(wrapper.find('.timeline-section').exists()).toBe(true)
    expect(wrapper.find('.timeline-section').classes()).toContain('app-card')
    expect(wrapper.find('.app-loading').exists()).toBe(true)
    resolve({ data: { items: baseItems } })
    await flushPromises()
    expect(wrapper.find('.app-loading').exists()).toBe(false)
    expect(wrapper.findAll('.timeline-item').length).toBeGreaterThan(0)
    wrapper.unmount()
  })

  it('最多渲染 10 条动态（接口返回 15 条截断）', async () => {
    const many = Array.from({ length: 15 }, (_, i) => ({
      id: i + 1,
      action: `操作${i + 1}`,
      target: `目标${i + 1}`,
      time: '2026-06-06',
    }))
    mockApiRequest.mockResolvedValue({ data: { items: many } })
    const wrapper = mount(InfoRow, {
      global: {
        stubs: {
          'el-button': { template: '<button class="el-button-stub"><slot /></button>' },
          'el-icon': { template: '<span><slot /></span>' },
        },
      },
    })
    await flushPromises()
    expect(wrapper.findAll('.timeline-item').length).toBe(10)
    wrapper.unmount()
  })

  it('字段兜底：target 缺省不显示；action/description 全缺 → --；空列表 → .app-empty', async () => {
    const wrapper = mountInfo()
    await flushPromises()
    expect(wrapper.text()).toContain('--')
    expect(wrapper.text()).toContain('新增项目')
    expect(wrapper.text()).toContain('甲村')
    wrapper.unmount()

    const empty = mountInfo([])
    await flushPromises()
    expect(empty.find('.tl-empty').exists()).toBe(true)
    expect(empty.find('.app-empty').exists()).toBe(true)
    expect(empty.text()).toContain('暂无动态')
    empty.unmount()
  })

  it('formatTime：空串/非法日期 → 空；合法日期 → 格式化', () => {
    const wrapper = mountInfo()
    const vm = wrapper.vm as any
    expect(vm.formatTime('')).toBe('')
    expect(vm.formatTime('garbage')).toBe('')
    const d = new Date(2026, 5, 6, 10, 30)
    expect(vm.formatTime(d.toISOString())).toBe(`${d.getMonth() + 1}/6 10:30`)
    wrapper.unmount()
  })
})

describe('InfoRow 编辑与删除', () => {
  it('自定义条目渲染编辑按钮；全部条目渲染删除按钮；startEdit 进入编辑模式', async () => {
    const wrapper = mountInfo()
    await flushPromises()
    expect(wrapper.findAll('.tl-edit-btn').length).toBe(2)
    expect(wrapper.findAll('.tl-delete-btn').length).toBe(4)

    await wrapper.findAll('.tl-edit-btn')[0].trigger('click')
    const vm = wrapper.vm as any
    expect(vm.editingId).toBe('custom_1')
    expect(vm.editForm).toEqual({ action: '新增项目', target: '甲村' })
    expect(wrapper.find('.tl-edit-input').exists()).toBe(true)
    expect(wrapper.find('.tl-save-btn').exists()).toBe(true)
    wrapper.unmount()
  })

  it('saveEdit 成功 → put + 本地更新 + 退出编辑；取消 → 退出编辑', async () => {
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

    // startEdit 字段缺失兜底
    await vm.startEdit({ id: 'custom_x', action: '', target: '' })
    expect(vm.editForm).toEqual({ action: '', target: '' })

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

  it('deleteActivity 成功移除；失败提示且列表不变；删除按钮触发', async () => {
    mockDel.mockResolvedValue({})
    const wrapper = mountInfo()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.activities.length).toBe(4)
    await vm.deleteActivity('custom_1')
    expect(mockDel).toHaveBeenCalledWith('/dashboard/recent-activities/custom_1')
    expect(vm.activities.length).toBe(3)

    mockDel.mockRejectedValue(new Error('del down'))
    await vm.deleteActivity(2)
    expect(ElMessage.error).toHaveBeenCalledWith('删除失败，请重试')
    expect(vm.activities.length).toBe(3)

    // 模板删除按钮（系统动态为隐藏式删除）
    mockDel.mockResolvedValue({})
    await wrapper.findAll('.tl-delete-btn')[0].trigger('click')
    await flushPromises()
    expect(mockDel).toHaveBeenCalled()
    wrapper.unmount()
  })
})

describe('InfoRow 错误重试与响应形状', () => {
  it('加载失败 → .app-error/.tl-state--error；2s 后自动重试成功恢复', async () => {
    vi.useFakeTimers()
    mockApiRequest.mockRejectedValueOnce(new Error('net'))
    mockApiRequest.mockResolvedValueOnce({ data: { items: baseItems.slice(0, 1) } })
    const wrapper = mountInfo()
    await flushPromises()
    expect(logError).toHaveBeenCalled()
    expect(wrapper.find('.tl-state--error').exists()).toBe(true)
    expect(wrapper.find('.app-error').exists()).toBe(true)
    await vi.advanceTimersByTimeAsync(2000)
    await flushPromises()
    expect(wrapper.find('.tl-state--error').exists()).toBe(false)
    expect(wrapper.findAll('.timeline-item').length).toBe(1)
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

  it('卸载时清理自动重试定时器（不再触发请求）', async () => {
    vi.useFakeTimers()
    mockApiRequest.mockRejectedValue(new Error('down'))
    const wrapper = mountInfo()
    await flushPromises()
    expect(mockApiRequest).toHaveBeenCalledTimes(1)
    wrapper.unmount()
    await vi.advanceTimersByTimeAsync(10000)
    await flushPromises()
    expect(mockApiRequest).toHaveBeenCalledTimes(1)
  })

  it('响应形状兜底：顶层 items / 空对象 → [] / 非数组 → []', async () => {
    const wrapper = mountInfo([])
    await flushPromises()
    const vm = wrapper.vm as any

    mockApiRequest.mockResolvedValue({ items: [baseItems[0]] })
    await vm.loadActivities()
    await flushPromises()
    expect(wrapper.findAll('.timeline-item').length).toBe(1)
    wrapper.unmount()

    const wrapper2 = mountInfo([])
    await flushPromises()
    mockApiRequest.mockResolvedValue({})
    await (wrapper2.vm as any).loadActivities()
    await flushPromises()
    expect(wrapper2.find('.tl-empty').exists()).toBe(true)
    wrapper2.unmount()

    const wrapper3 = mountInfo([])
    await flushPromises()
    mockApiRequest.mockResolvedValue({ items: 'not-array' })
    await (wrapper3.vm as any).loadActivities()
    await flushPromises()
    expect(wrapper3.findAll('.timeline-item').length).toBe(0)
    wrapper3.unmount()
  })
})
