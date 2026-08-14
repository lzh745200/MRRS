/**
 * views/approval/History.vue 覆盖率攻坚（四指标 100%）
 * 覆盖：diffTableData（null/字段并集/缺省）、loadHistory（满页/短页 total 两侧/失败）、
 * handleSearch/handleReset、handleViewDetail（成功/失败静默）、handleViewEntity（rural_work/其他）、
 * formatDateTime 两侧、模板：刷新/搜索/重置按钮、分页 v-model 与事件、详情对话框与 diff 表。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

const {
  ElMessage,
  mockGetTasksHistory,
  mockGetTaskDiff,
  formatApprovalStatus,
  formatEntityType,
  pushSafeMock,
} = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  mockGetTasksHistory: vi.fn(),
  mockGetTaskDiff: vi.fn(),
  formatApprovalStatus: vi.fn((s: string) => ({ text: `状态${s}`, type: 'info' })),
  formatEntityType: vi.fn((t: string) => `类型${t}`),
  pushSafeMock: vi.fn(),
}))

vi.mock('element-plus', () => ({ ElMessage }))

vi.mock('@/composables/useRouterSafe', () => ({
  useRouterSafe: () => ({ pushSafe: pushSafeMock }),
}))

vi.mock('@/api/approval', () => ({
  getTasksHistory: mockGetTasksHistory,
  getTaskDiff: mockGetTaskDiff,
  formatApprovalStatus,
  formatEntityType,
}))

import History from '@/views/approval/History.vue'

const taskA = {
  id: 1,
  title: '任务A',
  entity_type: 'rural_work',
  entity_id: 5,
  status: 'pending',
  current_level: 2,
  created_at: '2024-06-01 10:00:00',
  completed_at: '2024-06-02 10:00:00',
}
const taskB = {
  id: 2,
  title: '',
  entity_type: 'project',
  entity_id: 8,
  status: 'approved',
  current_level: 1,
  created_at: '2024-06-03 10:00:00',
  completed_at: '',
}
const taskC = {
  id: 3,
  title: '任务C',
  entity_type: 'school',
  entity_id: 9,
  status: 'rejected',
  current_level: 3,
  created_at: '2024-06-04 10:00:00',
  completed_at: null,
}

function mountComp() {
  return mount(History, {
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
            '<div class="el-table-column-stub"><slot :row="rowA" /><slot :row="rowB" /><slot :row="rowC" /></div>',
          data() {
            return { rowA: taskA, rowB: taskB, rowC: taskC }
          },
        },
        'el-dialog': {
          name: 'ElDialog',
          template: '<div class="el-dialog-stub"><slot /><slot name="footer" /></div>',
          emits: ['update:modelValue'],
        },
        'el-pagination': {
          name: 'ElPagination',
          template: '<div class="el-pagination-stub" />',
          emits: ['update:currentPage', 'update:pageSize', 'size-change', 'current-change'],
        },
        'el-select': {
          name: 'ElSelect',
          template: '<div class="el-select-stub"><slot /></div>',
          emits: ['update:modelValue'],
        },
        'el-descriptions': {
          name: 'ElDescriptions',
          template: '<div class="el-descriptions-stub"><slot /></div>',
        },
        'el-descriptions-item': {
          name: 'ElDescriptionsItem',
          template: '<div class="el-descriptions-item-stub"><slot /></div>',
        },
        'el-divider': { name: 'ElDivider', template: '<div class="el-divider-stub"><slot /></div>' },
        'el-tag': { name: 'ElTag', template: '<span class="el-tag-stub"><slot /></span>' },
        'el-empty': { name: 'ElEmpty', template: '<div class="el-empty-stub"><slot /></div>' },
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
  formatApprovalStatus.mockImplementation((s: string) => ({ text: `状态${s}`, type: 'info' }))
  formatEntityType.mockImplementation((t: string) => `类型${t}`)
  mockGetTasksHistory.mockResolvedValue({ items: [taskA, taskB, taskC], total: 3 })
  mockGetTaskDiff.mockResolvedValue({
    original_data: { name: '旧' },
    change_data: { name: '新' },
    diff_fields: ['name'],
  })
})

describe('挂载与加载', () => {
  it('onMounted：加载历史（total 来自后端）；模板渲染', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(mockGetTasksHistory).toHaveBeenCalledWith({
      entity_type: undefined,
      status: undefined,
      skip: 0,
      limit: 20,
    })
    expect(vm.historyList).toHaveLength(3)
    expect(vm.total).toBe(3)
    expect(vm.loading).toBe(false)
    const text = wrapper.text()
    expect(text).toContain('任务A')
    expect(text).toContain('类型project #8') // title 缺失回退
    expect(text).toContain('状态pending')
    expect(text).toContain('第 2 级')
    expect(text).toContain('-') // completed_at 空
    expect(text).toContain('详情')
  })

  it('total 由后端返回；失败 → 错误提示', async () => {
    const list = Array.from({ length: 20 }, (_, i) => ({ ...taskA, id: i + 1 }))
    mockGetTasksHistory.mockResolvedValue({ items: list, total: 55 })
    let wrapper = mountComp()
    await flushPromises()
    let vm = wrapper.vm as any
    expect(vm.total).toBe(55)

    mockGetTasksHistory.mockRejectedValue(new Error('net'))
    wrapper = mountComp()
    await flushPromises()
    vm = wrapper.vm as any
    expect(ElMessage.error).toHaveBeenCalledWith('加载审批历史失败')
    expect(vm.loading).toBe(false)
  })

  it('handleSearch 重置页码并加载；「搜索」「重置」按钮', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.page = 3
    await findBtn(wrapper, '搜索').trigger('click')
    await flushPromises()
    expect(vm.page).toBe(1)
    expect(mockGetTasksHistory).toHaveBeenCalledWith(
      expect.objectContaining({ skip: 0 })
    )

    vm.filterForm.entity_type = 'project'
    vm.filterForm.status = 'pending'
    await findBtn(wrapper, '重置').trigger('click')
    await flushPromises()
    expect(vm.filterForm.entity_type).toBeUndefined()
    expect(vm.filterForm.status).toBeUndefined()
    expect(vm.page).toBe(1)
  })

  it('刷新按钮（header）触发 loadHistory', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const base = mockGetTasksHistory.mock.calls.length
    await findBtn(wrapper, '刷新').trigger('click')
    await flushPromises()
    expect(mockGetTasksHistory.mock.calls.length).toBe(base + 1)
  })
})

describe('分页', () => {
  it('v-model 与 size-change/current-change 事件', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const pg = wrapper.findAllComponents({ name: 'ElPagination' })
    expect(pg.length).toBe(1)
    pg[0].vm.$emit('update:currentPage', 2)
    expect(vm.page).toBe(2)
    pg[0].vm.$emit('update:pageSize', 50)
    expect(vm.pageSize).toBe(50)
    pg[0].vm.$emit('size-change', 50)
    await flushPromises()
    expect(mockGetTasksHistory).toHaveBeenCalledWith(expect.objectContaining({ skip: 50 }))
    pg[0].vm.$emit('update:currentPage', 3)
    pg[0].vm.$emit('current-change', 3)
    await flushPromises()
    expect(mockGetTasksHistory).toHaveBeenCalledWith(expect.objectContaining({ skip: 100 }))
  })
})

describe('详情与 diff', () => {
  it('diffTableData：null / 字段并集 / 缺省', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.diffTableData).toEqual([])

    vm.taskDiff = {
      original_data: { name: 'A', keep: 'x' },
      change_data: { name: 'B' },
      diff_fields: ['name'],
    }
    expect(vm.diffTableData).toEqual([
      { field: 'name', original: 'A', new: 'B', changed: true },
      { field: 'keep', original: 'x', new: undefined, changed: false },
    ])

    vm.taskDiff = { original_data: null, change_data: undefined, diff_fields: undefined }
    expect(vm.diffTableData).toEqual([])
  })

  it('handleViewDetail：成功加载 diff；失败静默；详情按钮点击', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await findBtn(wrapper, '详情').trigger('click') // rowA
    await flushPromises()
    expect(vm.currentTask).toEqual(taskA)
    expect(vm.detailDialogVisible).toBe(true)
    expect(vm.taskDiff).not.toBeNull()

    mockGetTaskDiff.mockRejectedValue(new Error('net'))
    await vm.handleViewDetail(taskB)
    expect(vm.taskDiff).toBeNull()
    expect(vm.detailDialogVisible).toBe(true)
  })

  it('对话框：diff 表 ?? "-" 渲染 / el-empty 两侧；关闭按钮；v-model', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.currentTask = taskA
    vm.taskDiff = {
      original_data: { name: 'A' },
      change_data: { name: 'B' },
      diff_fields: ['name'],
    }
    vm.detailDialogVisible = true
    await nextTick()
    expect(wrapper.find('.diff-view').exists()).toBe(true)
    expect(wrapper.find('.el-empty-stub').exists()).toBe(false)
    // 注入行（task 行）无 original/new → ?? "-" 兜底
    expect(wrapper.text()).toContain('-')

    vm.taskDiff = null
    await nextTick()
    expect(wrapper.find('.el-empty-stub').exists()).toBe(true)

    await findBtn(wrapper, '关闭').trigger('click')
    expect(vm.detailDialogVisible).toBe(false)
    vm.detailDialogVisible = true
    await nextTick()
    wrapper.findAllComponents({ name: 'ElDialog' })[0].vm.$emit('update:modelValue', false)
    expect(vm.detailDialogVisible).toBe(false)
  })

  it('handleViewEntity：rural_work 跳转并关闭；fund 等类型也跳转；其他类型无操作', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.currentTask = taskA
    vm.detailDialogVisible = true
    await nextTick()
    await findBtn(wrapper, '查看类型rural_work详情').trigger('click')
    expect(pushSafeMock).toHaveBeenCalledWith({
      path: '/rural-works',
      query: { id: 5, action: 'view' },
    })
    expect(vm.detailDialogVisible).toBe(false)

    // project 类型现在也可跳转实体详情页
    vm.handleViewEntity(taskB)
    expect(pushSafeMock).toHaveBeenCalledWith('/projects/8')

    // 非业务实体类型 → 无操作
    const calls = pushSafeMock.mock.calls.length
    vm.handleViewEntity({ entity_type: 'data_change', entity_id: 99 })
    expect(pushSafeMock.mock.calls.length).toBe(calls)
  })

  it('formatDateTime 两侧', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.formatDateTime('')).toBe('-')
    expect(vm.formatDateTime('2024-06-01T10:00:00')).not.toBe('-')
  })

  it('diffTableData：旧键名 original/changed 回退；original/changed 为假值时 ||{} 兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // 旧接口键名 original/changed（无 original_data/change_data）→ ?? 中段回退
    vm.taskDiff = {
      original: { name: '旧', keep: 'x' },
      changed: { name: '新' },
      diff_fields: ['name'],
    }
    expect(vm.diffTableData).toEqual([
      { field: 'name', original: '旧', new: '新', changed: true },
      { field: 'keep', original: 'x', new: undefined, changed: false },
    ])
    // original/changed 为假值（非 nullish，如 0/''）→ Object.keys(original || {}) 的 ||{} 兜底
    vm.taskDiff = { original_data: 0, change_data: '', diff_fields: undefined }
    expect(vm.diffTableData).toEqual([])
  })
})

describe('表单 v-model', () => {
  it('entity_type/status 同步', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const byName = (n: string) => wrapper.findAllComponents({ name: n })
    byName('ElSelect')[0].vm.$emit('update:modelValue', 'supported_village')
    byName('ElSelect')[1].vm.$emit('update:modelValue', 'pending')
    expect(vm.filterForm.entity_type).toBe('supported_village')
    expect(vm.filterForm.status).toBe('pending')
  })
})
