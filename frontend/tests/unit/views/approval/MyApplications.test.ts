/**
 * views/approval/MyApplications.vue 覆盖率攻坚（四指标 100%）
 * 覆盖：stats 四计数、statusLabel/statusTagType 映射与兜底、formatDate 两侧、
 * loadData（status 参数/失败）、resetFilters、handleWithdraw/handleResubmit（确认/取消/成功）、
 * 模板：查询/重置按钮、撤回与重新提交按钮 v-if、select v-model、date-picker v-model。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const { ElMessage, confirmMock, mockGetMyTasks, mockPost } = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  confirmMock: vi.fn(),
  mockGetMyTasks: vi.fn(),
  mockPost: vi.fn(),
}))

vi.mock('element-plus', () => ({
  ElMessage,
  ElMessageBox: { confirm: confirmMock },
}))

vi.mock('@/api/approval', () => ({
  getMyTasks: mockGetMyTasks,
  formatEntityType: (t: string) => ({ fund: '经费' }[t] || t),
}))

vi.mock('@/api/request', () => ({
  post: mockPost,
  get: vi.fn(),
  put: vi.fn(),
  del: vi.fn(),
  apiRequest: vi.fn(),
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

import MyApplications from '@/views/approval/MyApplications.vue'

const apps = [
  { id: 1, title: '申请A', type: 'data_change', status: 'pending', created_at: '2024-06-01 10:00:00', reviewer_name: '审1', opinion: '无' },
  { id: 2, title: '申请B', type: 'data_import', status: 'approved', created_at: '2024-06-02 11:00:00', reviewer_name: '审2', opinion: '同意' },
  { id: 3, title: '', type: '', status: 'rejected', created_at: '2024-06-03 12:00:00', reviewer_name: '', opinion: '驳回' },
  { id: 4, title: '申请D', type: 'export', status: 'withdrawn', created_at: '2024-06-04 13:00:00', reviewer_name: '审4', opinion: '' },
]

function mountComp() {
  return mount(MyApplications, {
    global: {
      renderStubDefaultSlot: true,
      stubs: {
        'el-card': {
          name: 'ElCard',
          template: '<div class="el-card-stub"><slot name="header" /><slot /></div>',
        },
        'el-table': { name: 'ElTable', template: '<div class="el-table-stub"><slot /></div>' },
        'el-table-column': {
          name: 'ElTableColumn',
          template:
            '<div class="el-table-column-stub"><slot :row="rowA" /><slot :row="rowB" /><slot :row="rowC" /><slot :row="rowD" /></div>',
          data() {
            return { rowA: apps[0], rowB: apps[1], rowC: apps[2], rowD: apps[3] }
          },
        },
        'el-select': {
          name: 'ElSelect',
          template: '<div class="el-select-stub"><slot /></div>',
          emits: ['update:modelValue'],
        },
        'el-date-picker': {
          name: 'ElDatePicker',
          template: '<div class="el-date-picker-stub" />',
          emits: ['update:modelValue'],
        },
        'el-tag': { name: 'ElTag', template: '<span class="el-tag-stub"><slot /></span>' },
      },
    },
  })
}

const findBtn = (wrapper: any, text: string) => {
  const btn = wrapper.findAll('el-button-stub').find((b: any) => b.text().includes(text))
  expect(btn, text).toBeTruthy()
  return btn!
}

beforeEach(() => {
  vi.resetAllMocks()
  mockGetMyTasks.mockResolvedValue({ items: apps, total: 4 })
  mockPost.mockResolvedValue({})
  confirmMock.mockResolvedValue('confirm')
})

describe('挂载与统计', () => {
  it('onMounted 加载；stats 四计数；模板渲染（撤回/重新提交 v-if）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(mockGetMyTasks).toHaveBeenCalledWith({ skip: 0, limit: 500 })
    expect(vm.applications).toHaveLength(4)
    expect(vm.stats.total).toBe(4)
    expect(vm.stats.pending).toBe(1)
    expect(vm.stats.approved).toBe(1)
    expect(vm.stats.rejected).toBe(1)
    expect(vm.loading).toBe(false)
    const text = wrapper.text()
    expect(text).toContain('data_change') // 类型列 slot
    expect(text).toContain('待审批')
    expect(text).toContain('已通过')
    expect(text).toContain('已驳回')
    expect(text).toContain('已撤回')
    expect(text).toContain('通用') // rowC type 缺失 → 通用
    expect(text).toContain('撤回')
    expect(text).toContain('重新提交')
    expect(text).toContain('2024/6/1 10:00:00')
  })

  it('loadData：status 参数；失败 → 空列表', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.filters.status = 'pending'
    await vm.loadData()
    expect(mockGetMyTasks).toHaveBeenCalledWith({ status: 'pending', skip: 0, limit: 500 })

    mockGetMyTasks.mockRejectedValue(new Error('net'))
    await vm.loadData()
    expect(vm.applications).toEqual([])
    expect(vm.loading).toBe(false)
  })

  it('loadData：dateRange 长度为 2 → 携带 date_from/date_to', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.filters.dateRange = ['2024-01-01', '2024-06-30']
    await vm.loadData()
    expect(mockGetMyTasks).toHaveBeenCalledWith({
      date_from: '2024-01-01',
      date_to: '2024-06-30',
      skip: 0,
      limit: 500,
    })

    // 长度非 2 → 不携带日期参数
    mockGetMyTasks.mockClear()
    vm.filters.dateRange = ['2024-01-01']
    await vm.loadData()
    expect(mockGetMyTasks).toHaveBeenCalledWith({ skip: 0, limit: 500 })
  })

  it('resetFilters 清空并重载；「查询」「重置」按钮', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.filters.status = 'approved'
    vm.filters.dateRange = ['2024-01-01', '2024-12-31']
    await findBtn(wrapper, '重置').trigger('click')
    await flushPromises()
    expect(vm.filters.status).toBe('')
    expect(vm.filters.dateRange).toBeNull()

    const base = mockGetMyTasks.mock.calls.length
    await findBtn(wrapper, '查询').trigger('click')
    await flushPromises()
    expect(mockGetMyTasks.mock.calls.length).toBe(base + 1)
  })
})

describe('标签与格式化', () => {
  it('statusLabel/statusTagType 映射与兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.statusLabel('pending')).toBe('待审批')
    expect(vm.statusLabel('approved')).toBe('已通过')
    expect(vm.statusLabel('rejected')).toBe('已驳回')
    expect(vm.statusLabel('withdrawn')).toBe('已撤回')
    expect(vm.statusLabel('weird')).toBe('weird')
    expect(vm.statusTagType('pending')).toBe('warning')
    expect(vm.statusTagType('approved')).toBe('success')
    expect(vm.statusTagType('rejected')).toBe('danger')
    expect(vm.statusTagType('withdrawn')).toBe('info')
    expect(vm.statusTagType('weird')).toBe('info')
  })

  it('formatDate：有值/空', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.formatDate('2024-06-01T10:00:00')).not.toBe('-')
    expect(vm.formatDate('')).toBe('-')
  })
})

describe('撤回与重新提交', () => {
  it('handleWithdraw：确认 → post + 提示 + 重载；取消静默；模板按钮', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await findBtn(wrapper, '撤回').trigger('click') // rowA pending
    await flushPromises()
    expect(confirmMock).toHaveBeenCalledWith(
      '确认撤回「申请A」？撤回后审批流程将终止。',
      '撤回申请',
      expect.objectContaining({ type: 'warning' })
    )
    expect(mockPost).toHaveBeenCalledWith('/approval/tasks/1/withdraw')
    expect(ElMessage.success).toHaveBeenCalledWith('已撤回')
    expect(mockGetMyTasks).toHaveBeenCalled()

    confirmMock.mockRejectedValueOnce(new Error('cancel'))
    await vm.handleWithdraw(apps[0])
    expect(mockPost.mock.calls.length).toBe(1)
  })

  it('handleWithdraw：无标题 → 兜底文案', async () => {
    const wrapper = mountComp()
    await flushPromises()
    await (wrapper.vm as any).handleWithdraw({ id: 3, title: '' })
    expect(confirmMock).toHaveBeenCalledWith(
      '确认撤回「该申请」？撤回后审批流程将终止。',
      '撤回申请',
      expect.anything()
    )
  })

  it('handleResubmit：确认 → post + 提示 + 重载；取消静默；模板按钮', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await findBtn(wrapper, '重新提交').trigger('click') // rowC rejected
    await flushPromises()
    expect(confirmMock).toHaveBeenCalledWith('确认重新提交「该申请」？', '重新提交')
    expect(mockPost).toHaveBeenCalledWith('/approval/tasks/3/resubmit')
    expect(ElMessage.success).toHaveBeenCalledWith('已重新提交')
    expect(mockGetMyTasks).toHaveBeenCalled()

    confirmMock.mockRejectedValueOnce(new Error('cancel'))
    await vm.handleResubmit(apps[2])
    expect(mockPost.mock.calls.length).toBe(1)
  })
})

describe('表单 v-model', () => {
  it('status/dateRange 同步', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    wrapper.findAllComponents({ name: 'ElSelect' })[0].vm.$emit('update:modelValue', 'rejected')
    expect(vm.filters.status).toBe('rejected')
    const range = ['2024-01-01', '2024-06-01']
    wrapper.findAllComponents({ name: 'ElDatePicker' })[0].vm.$emit('update:modelValue', range)
    expect(vm.filters.dateRange).toEqual(range)
  })
})
