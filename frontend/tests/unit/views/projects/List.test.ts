/**
 * views/projects/List.vue 覆盖率攻坚（四指标 100%）
 * 覆盖：onMounted 加载列表与统计、搜索/重置/分页/统计卡片点击、
 * 字典函数全分支、删除/批量删除（取消/部分成功/全失败）、批量导出、
 * 表格列插槽、v-model 事件。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const {
  ElMessage,
  confirmMock,
  projectApiMock,
  pushSafeMock,
  logError,
  promptMock,
  authState,
} = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  confirmMock: vi.fn(),
  projectApiMock: {
    getStats: vi.fn(),
    list: vi.fn(),
    delete: vi.fn(),
    exportList: vi.fn(),
    restore: vi.fn(),
    purgePreview: vi.fn(),
    purge: vi.fn(),
  },
  pushSafeMock: vi.fn(),
  logError: vi.fn(),
  promptMock: vi.fn(),
  authState: { user: { role: 'admin', id: 1 }, canViewDeleted: true },
}))

vi.mock('element-plus', () => ({
  ElMessage,
  ElMessageBox: { confirm: confirmMock, prompt: promptMock },
  ElTable: {
    name: 'ElTable',
    template:
      '<div class="el-table-stub" @click="$emit(\'selection-change\', [rowA])"><slot name="default" /></div>',
    methods: {
      clearSelection() {
        this.$emit('selection-change', [])
      },
    },
  },
}))

vi.mock('@/api/projects', () => ({
  projectApi: projectApiMock,
  projectsApi: projectApiMock,
  restoreProject: projectApiMock.restore,
  previewPurgeProject: projectApiMock.purgePreview,
  purgeProject: projectApiMock.purge,
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => authState,
}))

vi.mock('@/composables/useRouterSafe', () => ({
  useRouterSafe: () => ({ pushSafe: pushSafeMock }),
}))

vi.mock('@/composables/useDesensitize', () => ({
  useDesensitize: () => ({
    ds: (value: any, _type: string) => String(value ?? ''),
    role: 'viewer',
  }),
}))

vi.mock('@/utils/logger', () => ({
  logger: { error: logError, warn: vi.fn(), info: vi.fn(), debug: vi.fn() },
}))

import List from '@/views/projects/List.vue'

const projectRow = {
  id: 1,
  code: 'XM-001',
  name: '产业路',
  type: 'infrastructure',
  status: 'in_progress',
  progress: 90,
  budget: 100,
  responsible_person: '张三',
}

const projectRow2 = {
  id: 2,
  code: 'XM-002',
  name: '教育项目',
  type: 'education',
  status: 'completed',
  progress: 50,
  budget: 50,
}

const projectRow3 = {
  id: 3,
  code: 'XM-003',
  name: '医疗项目',
  type: 'other',
  status: 'cancelled',
  progress: 10,
  budget: 0,
}

const projectRow4 = { id: 4, code: 'XM-004', name: '缺字段项目', type: 'unknown', status: 'suspended' }

function mountComp() {
  return mount(List, {
    global: {
      renderStubDefaultSlot: true,
      stubs: {
        'el-table': {
          name: 'ElTable',
          template:
            '<div class="el-table-stub" @click="$emit(\'selection-change\', [rowA])"><slot name="default" /></div>',
          methods: {
            clearSelection() {
              this.$emit('selection-change', [])
            },
          },
        },
        'el-table-column': {
          name: 'ElTableColumn',
          template:
            '<div class="el-table-column-stub"><slot :row="rowA" /><slot :row="rowB" /><slot :row="rowC" /><slot :row="rowD" /></div>',
          data() {
            return {
              rowA: { ...projectRow },
              rowB: { ...projectRow2 },
              rowC: { ...projectRow3 },
              rowD: { ...projectRow4 },
            }
          },
        },
        'el-form': { template: '<div class="el-form-stub"><slot /></div>' },
        'el-form-item': { template: '<div class="el-form-item-stub"><slot /></div>' },
        'el-input': {
          template:
            '<div class="el-input-stub" @click="$emit(\'update:modelValue\', \'kw\')" />',
        },
        'el-input-number': {
          template:
            '<div class="el-input-number-stub" @click="$emit(\'update:modelValue\', 2024)" />',
        },
        'el-select': {
          template:
            '<div class="el-select-stub" @click="$emit(\'update:modelValue\', \'x\')"><slot /></div>',
        },
        'el-option': { template: '<div class="el-option-stub" />' },
        'el-button': {
          template: '<button class="el-button-stub" @click="$emit(\'click\')"><slot /></button>',
          emits: ['click'],
        },
        'el-icon': { template: '<span class="el-icon-stub"><slot /></span>' },
        'el-tag': { template: '<span class="el-tag-stub"><slot /></span>' },
        'el-progress': { template: '<div class="el-progress-stub" />' },
        'el-link': {
          template: '<a class="el-link-stub" @click="$emit(\'click\')"><slot /></a>',
          emits: ['click'],
        },
        'el-popconfirm': {
          template:
            '<div class="el-popconfirm-stub" @click="$emit(\'confirm\', rowA)"><slot name="reference" /></div>',
        },
        'el-pagination': {
          template:
            '<div class="el-pagination-stub" @click="$emit(\'size-change\'); $emit(\'current-change\'); $emit(\'update:currentPage\', 2); $emit(\'update:pageSize\', 50)" />',
        },
        // 默认桩不会 emit update:modelValue，导致 v-model 编译产物
        // onUpdate:modelValue@110（el-switch）/ @145（el-radio-group）永远不被执行。
        'el-switch': {
          props: { modelValue: { type: Boolean, default: false } },
          emits: ['update:modelValue', 'change'],
          template:
            '<button type="button" class="el-switch-stub" :data-on="String(modelValue)"' +
            ' @click="$emit(\'update:modelValue\', !modelValue); $emit(\'change\', !modelValue)"><slot /></button>',
        },
        'el-radio-group': {
          props: { modelValue: { type: String, default: '' } },
          emits: ['update:modelValue'],
          template:
            '<div class="el-radio-group-stub" :data-mode="modelValue">' +
            '<button type="button" class="to-gantt" @click="$emit(\'update:modelValue\', \'gantt\')">gantt</button>' +
            '<button type="button" class="to-table" @click="$emit(\'update:modelValue\', \'table\')">table</button>' +
            '<slot /></div>',
        },
        'el-radio-button': { template: '<span class="el-radio-button-stub"><slot /></span>' },
        // GanttView 内部依赖 echarts，此处只需验证切换分支渲染，无需真实图表
        GanttView: { props: ['items'], template: '<div class="gantt-stub" />' },
      },
    },
  })
}

beforeEach(() => {
  vi.resetAllMocks()
  projectApiMock.getStats.mockResolvedValue({
    data: { total: 10, in_progress: 5, completed: 3, total_budget: 123.6 },
  })
  projectApiMock.list.mockResolvedValue({
    data: { items: [projectRow, projectRow2, projectRow3], total: 3 },
  })
  projectApiMock.delete.mockResolvedValue({})
  projectApiMock.exportList.mockResolvedValue({})
  confirmMock.mockResolvedValue(undefined)
  promptMock.mockResolvedValue({ value: 'pw' })
  projectApiMock.restore.mockResolvedValue({})
  projectApiMock.purgePreview.mockResolvedValue({ data: { total_references: 0, details: {} } })
  projectApiMock.purge.mockResolvedValue({ data: { deleted_records: 0 } })
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('挂载与加载', () => {
  it('onMounted 加载列表与统计', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(projectApiMock.list).toHaveBeenCalledWith(
      expect.objectContaining({ page: 1, page_size: 10 })
    )
    expect(projectApiMock.getStats).toHaveBeenCalled()
    expect(vm.projectList).toHaveLength(3)
    expect(vm.pagination.total).toBe(3)
    expect(vm.stats.total).toBe(10)
    expect(vm.stats.inProgress).toBe(5)
    expect(vm.stats.completed).toBe(3)
    expect(vm.stats.totalBudget).toBe(123.6)
  })

  it('getStats 数据扁平格式', async () => {
    projectApiMock.getStats.mockResolvedValue({
      total: 1,
      in_progress: 1,
      completed: 0,
      total_budget: 5,
    })
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).stats.total).toBe(1)
  })

  it('getStats 缺字段 → ?? 0 兜底', async () => {
    projectApiMock.getStats.mockResolvedValue({ data: {} })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.stats.inProgress).toBe(0)
    expect(vm.stats.completed).toBe(0)
    expect(vm.stats.totalBudget).toBe(0)
  })

  it('getStats 失败 → 不阻塞', async () => {
    projectApiMock.getStats.mockRejectedValue(new Error('net'))
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).stats.total).toBe(0)
  })

  it('loadData 失败 → 错误提示 + 清空', async () => {
    projectApiMock.list.mockRejectedValue(new Error('net'))
    const wrapper = mountComp()
    await flushPromises()
    expect(logError).toHaveBeenCalled()
    expect(ElMessage.error).toHaveBeenCalledWith('加载项目列表失败')
    expect((wrapper.vm as any).projectList).toEqual([])
    expect((wrapper.vm as any).pagination.total).toBe(0)
  })

  it('list 响应直返 items 格式', async () => {
    projectApiMock.list.mockResolvedValue({ items: [projectRow], total: 1 })
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).projectList).toHaveLength(1)
  })

  it('list 响应空对象 → total 0 兜底', async () => {
    projectApiMock.list.mockResolvedValue({})
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).projectList).toEqual([])
    expect((wrapper.vm as any).pagination.total).toBe(0)
  })

  it('筛选参数组装（含 cancelled include_cancelled）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.filterForm.name = '项目'
    vm.filterForm.type = 'education'
    vm.filterForm.status = 'cancelled'
    projectApiMock.list.mockClear()
    await vm.loadData()
    expect(projectApiMock.list).toHaveBeenCalledWith(
      expect.objectContaining({
        keyword: '项目',
        project_type: 'education',
        status: 'cancelled',
        include_cancelled: true,
      })
    )
  })
})

describe('搜索/重置/分页', () => {
  it('handleSearch 回第 1 页', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.pagination.page = 3
    projectApiMock.list.mockClear()
    vm.handleSearch()
    await flushPromises()
    expect(vm.pagination.page).toBe(1)
    expect(projectApiMock.list).toHaveBeenCalled()
  })

  it('handleReset 清空筛选', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.filterForm.name = 'x'
    vm.filterForm.status = 'y'
    vm.filterForm.type = 'z'
    vm.filterForm.region = 'r'
    vm.filterForm.year = 2024
    vm.handleReset()
    expect(vm.filterForm).toEqual({ name: '', status: '', type: '', region: '', year: null })
    expect(vm.pagination.page).toBe(1)
  })

  it('handleSizeChange/handlePageChange', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.pagination.page = 5
    projectApiMock.list.mockClear()
    vm.handleSizeChange()
    await flushPromises()
    expect(vm.pagination.page).toBe(1)
    expect(projectApiMock.list).toHaveBeenCalled()

    projectApiMock.list.mockClear()
    vm.handlePageChange()
    await flushPromises()
    expect(projectApiMock.list).toHaveBeenCalled()
  })

  it('handleStatClick 按状态筛选', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    projectApiMock.list.mockClear()
    vm.handleStatClick('completed')
    expect(vm.filterForm.status).toBe('completed')
    expect(vm.filterForm.name).toBe('')
    expect(vm.filterForm.type).toBe('')
    expect(vm.pagination.page).toBe(1)
    expect(projectApiMock.list).toHaveBeenCalled()
  })

  it('筛选表单 v-model 更新', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await wrapper.find('.el-input-stub').trigger('click')
    await wrapper.find('.el-input-number-stub').trigger('click')
    for (const sel of wrapper.findAll('.el-select-stub')) {
      await sel.trigger('click')
    }
    await flushPromises()
    expect(vm.filterForm.name).toBe('kw')
    expect(vm.filterForm.year).toBe(2024)
    expect(vm.filterForm.status).toBe('x')
    expect(vm.filterForm.type).toBe('x')
    expect(vm.filterForm.region).toBe('x')
  })
})

describe('导航与 CRUD', () => {
  it('handleCreate → pushSafe', async () => {
    const wrapper = mountComp()
    await flushPromises()
    ;(wrapper.vm as any).handleCreate()
    expect(pushSafeMock).toHaveBeenCalledWith('/projects/create')
  })

  it('handleView/handleEdit 无 id → 错误', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleView({})
    expect(ElMessage.error).toHaveBeenCalledWith('无法查看：项目 ID 无效')
    vm.handleEdit({})
    expect(ElMessage.error).toHaveBeenCalledWith('无法编辑：项目 ID 无效')
  })

  it('handleView/handleEdit → pushSafe', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleView(projectRow)
    expect(pushSafeMock).toHaveBeenCalledWith('/projects/1')
    vm.handleEdit(projectRow)
    expect(pushSafeMock).toHaveBeenCalledWith('/projects/1/edit')
  })

  it('批量导入/数据统计按钮', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const btns = wrapper.findAll('.el-button-stub')
    const batch = btns.find((b) => b.text().includes('批量导入'))
    await batch!.trigger('click')
    expect(pushSafeMock).toHaveBeenCalledWith('/data-package')
    const stats = btns.find((b) => b.text().includes('数据统计'))
    await stats!.trigger('click')
    expect(pushSafeMock).toHaveBeenCalledWith('/data-analysis')
  })

  it('handleDelete 无 id → 错误', async () => {
    const wrapper = mountComp()
    await flushPromises()
    await (wrapper.vm as any).handleDelete({})
    expect(ElMessage.error).toHaveBeenCalledWith('无法删除：项目 ID 无效')
  })

  it('handleDelete 成功 → 刷新列表与统计', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    projectApiMock.list.mockClear()
    projectApiMock.getStats.mockClear()
    await vm.handleDelete(projectRow)
    expect(projectApiMock.delete).toHaveBeenCalledWith(1)
    // 成功静默：删除成功不弹提示
    expect(ElMessage.success).not.toHaveBeenCalled()
    expect(vm.pagination.page).toBe(1)
    expect(projectApiMock.list).toHaveBeenCalled()
    expect(projectApiMock.getStats).toHaveBeenCalled()
  })

  it('handleDelete 失败 → 错误提示', async () => {
    const wrapper = mountComp()
    await flushPromises()
    projectApiMock.delete.mockRejectedValueOnce(new Error('net'))
    await (wrapper.vm as any).handleDelete(projectRow)
    expect(ElMessage.error).toHaveBeenCalledWith('删除失败')
  })

  it('名称链接 → handleView', async () => {
    const wrapper = mountComp()
    await flushPromises()
    pushSafeMock.mockClear()
    const link = wrapper.find('.el-link-stub')
    await link.trigger('click')
    expect(pushSafeMock).toHaveBeenCalledWith('/projects/1')
  })

  it('popconfirm confirm → handleDelete', async () => {
    const wrapper = mountComp()
    await flushPromises()
    projectApiMock.delete.mockClear()
    await wrapper.find('.el-popconfirm-stub').trigger('click')
    await flushPromises()
    expect(projectApiMock.delete).toHaveBeenCalled()
  })
})

describe('导出', () => {
  it('handleExport 成功/失败', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.filterForm.name = 'kw'
    vm.filterForm.type = 'education'
    vm.filterForm.status = 'pending'
    await vm.handleExport()
    expect(projectApiMock.exportList).toHaveBeenCalledWith({
      keyword: 'kw',
      project_type: 'education',
      status: 'pending',
    })
    expect(ElMessage.success).toHaveBeenCalledWith('导出成功')

    projectApiMock.exportList.mockRejectedValueOnce(new Error('net'))
    await vm.handleExport()
    expect(ElMessage.error).toHaveBeenCalledWith('net')
  })

  it('导出按钮 → handleExport', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const btn = wrapper.findAll('.el-button-stub').find((b) => b.text().includes('导出'))
    await btn!.trigger('click')
    await flushPromises()
    expect(projectApiMock.exportList).toHaveBeenCalled()
  })
})

describe('批量操作', () => {
  it('handleSelectionChange / clearSelection', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.tableRef = { clearSelection: vi.fn() }
    vm.handleSelectionChange([projectRow])
    expect(vm.selectedRows).toHaveLength(1)
    vm.clearSelection()
    expect(vm.tableRef.clearSelection).toHaveBeenCalled()
    expect(vm.selectedRows).toEqual([])
  })

  it('批量删除：取消确认 → 不执行', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.selectedRows = [projectRow]
    confirmMock.mockRejectedValueOnce('cancel')
    await vm.handleBatchDelete()
    expect(projectApiMock.delete).not.toHaveBeenCalled()
  })

  it('批量删除：部分成功', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.selectedRows = [projectRow, projectRow2, projectRow3]
    projectApiMock.delete.mockImplementation((id: number) => {
      if (id === 2) return Promise.reject(new Error('x'))
      return Promise.resolve({})
    })
    projectApiMock.list.mockClear()
    projectApiMock.getStats.mockClear()
    await vm.handleBatchDelete()
    expect(ElMessage.success).toHaveBeenCalledWith('成功删除 2 个项目')
    expect(ElMessage.warning).toHaveBeenCalledWith('1 个项目删除失败')
    expect(vm.selectedRows).toEqual([])
    expect(projectApiMock.list).toHaveBeenCalled()
    expect(projectApiMock.getStats).toHaveBeenCalled()
    expect(vm.batchDeleting).toBe(false)
  })

  it('批量删除：全部失败', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.selectedRows = [projectRow]
    projectApiMock.delete.mockRejectedValueOnce(new Error('x'))
    await vm.handleBatchDelete()
    expect(ElMessage.success).not.toHaveBeenCalled()
    expect(ElMessage.warning).toHaveBeenCalledWith('1 个项目删除失败')
  })

  it('批量删除：空选择或进行中 → 直接返回', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleBatchDelete()
    expect(confirmMock).not.toHaveBeenCalled()

    vm.selectedRows = [projectRow]
    vm.batchDeleting = true
    await vm.handleBatchDelete()
    expect(confirmMock).not.toHaveBeenCalled()
  })

  it('批量导出：成功/失败/空选择', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleBatchExport()
    expect(projectApiMock.exportList).not.toHaveBeenCalled()

    vm.selectedRows = [projectRow, projectRow2]
    await vm.handleBatchExport()
    expect(projectApiMock.exportList).toHaveBeenCalledWith({ ids: [1, 2] })
    expect(ElMessage.success).toHaveBeenCalledWith('已导出 2 条项目记录')

    projectApiMock.exportList.mockRejectedValueOnce(new Error('net'))
    await vm.handleBatchExport()
    expect(ElMessage.error).toHaveBeenCalledWith('导出失败')
  })

  it('表格 selection-change 事件', async () => {
    const wrapper = mountComp()
    await flushPromises()
    await wrapper.find('.el-table-stub').trigger('click')
    expect((wrapper.vm as any).selectedRows.length).toBeGreaterThan(0)
  })

  it('批量删除/导出/取消选择按钮', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.selectedRows = [projectRow, projectRow2]
    await wrapper.vm.$nextTick()
    const btns = wrapper.findAll('.el-button-stub')

    const exp = btns.find((b) => b.text().includes('批量导出'))
    await exp!.trigger('click')
    await flushPromises()
    expect(projectApiMock.exportList).toHaveBeenCalled()

    const del = btns.find((b) => b.text().includes('批量删除'))
    await del!.trigger('click')
    await flushPromises()
    expect(confirmMock).toHaveBeenCalled()

    vm.selectedRows = [projectRow, projectRow2]
    await wrapper.vm.$nextTick()
    const cancel = wrapper.findAll('.el-button-stub').find((b) => b.text().includes('取消选择'))
    await cancel!.trigger('click')
    expect(vm.selectedRows).toEqual([])
  })

  it('分页 size/current 事件', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    projectApiMock.list.mockClear()
    await wrapper.find('.el-pagination-stub').trigger('click')
    await flushPromises()
    expect(vm.pagination.page).toBe(2)
    expect(vm.pagination.pageSize).toBe(50)
    expect(projectApiMock.list).toHaveBeenCalled()
  })
})

describe('字典与统计卡片', () => {
  it('getTypeText 全映射与兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.getTypeText('infrastructure')).toBe('基础设施')
    expect(vm.getTypeText('education')).toBe('教育帮扶')
    expect(vm.getTypeText('industry')).toBe('产业发展')
    expect(vm.getTypeText('medical')).toBe('医疗卫生')
    expect(vm.getTypeText('healthcare')).toBe('医疗卫生')
    expect(vm.getTypeText('agriculture')).toBe('农业发展')
    expect(vm.getTypeText('other')).toBe('其他')
    expect(vm.getTypeText('unknown')).toBe('unknown')
  })

  it('getStatusType/getStatusText 全映射与兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.getStatusType('draft')).toBe('info')
    expect(vm.getStatusType('pending')).toBe('info')
    expect(vm.getStatusType('approved')).toBe('primary')
    expect(vm.getStatusType('planning')).toBe('info')
    expect(vm.getStatusType('in_progress')).toBe('warning')
    expect(vm.getStatusType('completed')).toBe('success')
    expect(vm.getStatusType('cancelled')).toBe('danger')
    expect(vm.getStatusType('suspended')).toBe('danger')
    expect(vm.getStatusType('unknown')).toBe('info')
    expect(vm.getStatusText('draft')).toBe('草稿')
    expect(vm.getStatusText('pending')).toBe('待审批')
    expect(vm.getStatusText('approved')).toBe('已审批')
    expect(vm.getStatusText('planning')).toBe('规划中')
    expect(vm.getStatusText('in_progress')).toBe('进行中')
    expect(vm.getStatusText('completed')).toBe('已完成')
    expect(vm.getStatusText('cancelled')).toBe('已取消')
    expect(vm.getStatusText('suspended')).toBe('已暂停')
    expect(vm.getStatusText('unknown')).toBe('unknown')
  })

  it('getProgressColor 三分支', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.getProgressColor(90)).toBe('#40916c')
    expect(vm.getProgressColor(50)).toBe('#e6a23c')
    expect(vm.getProgressColor(10)).toBe('#f56c6c')
  })

  it('统计卡片点击（项目总数/进行中/已完成）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    projectApiMock.list.mockClear()
    vm.handleStatClick('')
    await flushPromises()
    expect(projectApiMock.list).toHaveBeenCalled()

    const cards = wrapper.findAll('.stat-clickable')
    expect(cards.length).toBe(3)
    projectApiMock.list.mockClear()
    await cards[0].trigger('click')
    await flushPromises()
    expect(vm.filterForm.status).toBe('')
    expect(projectApiMock.list).toHaveBeenCalled()

    projectApiMock.list.mockClear()
    await cards[1].trigger('click')
    await flushPromises()
    expect(vm.filterForm.status).toBe('in_progress')

    projectApiMock.list.mockClear()
    await cards[2].trigger('click')
    await flushPromises()
    expect(vm.filterForm.status).toBe('completed')
  })

  it('行内 查看/编辑 按钮点击', async () => {
    const wrapper = mountComp()
    await flushPromises()
    pushSafeMock.mockClear()
    const viewBtn = wrapper.findAll('.el-button-stub').find((b) => b.text().includes('查看'))
    await viewBtn!.trigger('click')
    expect(pushSafeMock).toHaveBeenCalledWith('/projects/1')

    pushSafeMock.mockClear()
    const editBtns = wrapper.findAll('.el-button-stub').filter((b) => b.text().includes('编辑'))
    await editBtns[0].trigger('click')
    expect(pushSafeMock).toHaveBeenCalledWith('/projects/1/edit')
    await editBtns[editBtns.length - 1].trigger('click')
    expect(pushSafeMock).toHaveBeenCalledWith('/projects/4/edit')
  })
})

// ─────────────────────────────────────────────
// 回收站深度分支 + 视图切换 v-model
// 缺口：funcs inputValidator@558 / handleBatchRestore@579 / handleBatchPurge@601 /
//        onUpdate:modelValue@110 / onUpdate:modelValue@145 / onClick@238 / onClick@239
//       branch@154,190,237,512,519,529×2,531,536,537,561,562,570,572
// ─────────────────────────────────────────────
describe('回收站深度分支与视图切换', () => {
  it('el-switch v-model：点击 → showDeletedOnly 翻转（onUpdate:modelValue@110）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.canViewDeleted).toBe(true)
    const sw = wrapper.find('.el-switch-stub')
    expect(sw.exists()).toBe(true)
    expect(sw.attributes('data-on')).toBe('false')

    vm.pagination.page = 4
    projectApiMock.list.mockClear()
    await sw.trigger('click')
    await flushPromises()

    expect(vm.showDeletedOnly).toBe(true)
    expect(wrapper.find('.el-switch-stub').attributes('data-on')).toBe('true')
    // @change → handleToggleDeleted：页码归 1 + 重新拉取 + 携带 include_deleted
    expect(vm.pagination.page).toBe(1)
    expect(projectApiMock.list).toHaveBeenCalledWith(
      expect.objectContaining({ page: 1, include_deleted: true })
    )
  })

  it('canViewDeleted=false → el-switch 不渲染（v-if 假侧）', async () => {
    authState.canViewDeleted = false
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).canViewDeleted).toBe(false)
    expect(wrapper.find('.el-switch-stub').exists()).toBe(false)
    authState.canViewDeleted = true
  })

  it('el-radio-group v-model：切到甘特图 → GanttView 渲染、el-table 卸载（onUpdate:modelValue@145 / branch@190）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.viewMode).toBe('table')
    expect(wrapper.find('.el-table-stub').exists()).toBe(true)
    expect(wrapper.find('.gantt-stub').exists()).toBe(false)

    await wrapper.find('.to-gantt').trigger('click')
    await flushPromises()
    expect(vm.viewMode).toBe('gantt')
    expect(wrapper.find('.gantt-stub').exists()).toBe(true)
    expect(wrapper.find('.el-table-stub').exists()).toBe(false)

    await wrapper.find('.to-table').trigger('click')
    await flushPromises()
    expect(vm.viewMode).toBe('table')
    expect(wrapper.find('.el-table-stub').exists()).toBe(true)
  })

  it('批量工具栏：正常模式 → 批量删除/批量导出（branch@154 v-else 侧）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.selectedRows = [{ ...projectRow }, { ...projectRow2 }]
    await flushPromises()
    expect(wrapper.find('.batch-toolbar').exists()).toBe(true)
    const texts = wrapper.findAll('.el-button-stub').map((b) => b.text())
    expect(texts.some((t) => t.includes('批量删除 (2)'))).toBe(true)
    expect(texts.some((t) => t.includes('批量导出 (2)'))).toBe(true)
    expect(texts.some((t) => t.includes('批量恢复'))).toBe(false)

    // selectedRows 清空 → 工具栏整体隐藏（v-if 假侧）
    vm.selectedRows = []
    await flushPromises()
    expect(wrapper.find('.batch-toolbar').exists()).toBe(false)
  })

  it('批量工具栏：回收站模式 → 批量恢复/批量彻底删除（branch@154 v-if 真侧）且按钮转发 handler', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.selectedRows = [{ ...projectRow }, { ...projectRow2 }]
    vm.showDeletedOnly = true
    await flushPromises()

    const batchRestoreBtn = wrapper
      .findAll('.el-button-stub')
      .find((b) => b.text().includes('批量恢复'))
    const batchPurgeBtn = wrapper
      .findAll('.el-button-stub')
      .find((b) => b.text().includes('批量彻底删除'))
    expect(batchRestoreBtn).toBeTruthy()
    expect(batchPurgeBtn).toBeTruthy()
    expect(batchRestoreBtn!.text()).toContain('(2)')
    // v-else 侧的批量删除/导出 已不渲染
    expect(wrapper.findAll('.el-button-stub').some((b) => b.text().includes('批量导出'))).toBe(false)

    await batchRestoreBtn!.trigger('click')
    await flushPromises()
    expect(confirmMock).toHaveBeenCalledWith(
      '确定批量恢复 2 个项目吗？', '批量恢复确认',
      expect.objectContaining({ confirmButtonText: '确认恢复', type: 'info' })
    )
    expect(projectApiMock.restore).toHaveBeenCalledTimes(2)
    expect(ElMessage.success).toHaveBeenCalledWith('已恢复 2 个项目')
    // clearSelection 已清空选中
    expect(vm.selectedRows).toEqual([])

    // 再验证批量彻底删除按钮转发
    vm.selectedRows = [{ ...projectRow }]
    await flushPromises()
    const purgeBtn = wrapper
      .findAll('.el-button-stub')
      .find((b) => b.text().includes('批量彻底删除'))
    await purgeBtn!.trigger('click')
    await flushPromises()
    expect(promptMock).toHaveBeenCalledWith(
      '批量彻底删除需二次确认，请输入登录密码：', '二次确认',
      expect.objectContaining({ confirmButtonText: '确认', inputType: 'password' })
    )
    expect(projectApiMock.purge).toHaveBeenCalledWith(1, 'pw')
    expect(ElMessage.success).toHaveBeenCalledWith('已彻底删除 1 个项目及关联数据')
  })

  it('操作列：回收站模式 → 恢复/彻底删除（branch@237）；点击转发 handleRestore/handlePurge（onClick@238/@239）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // 默认假侧：编辑 + el-popconfirm
    expect(wrapper.find('.el-popconfirm-stub').exists()).toBe(true)
    expect(wrapper.findAll('.el-button-stub').some((b) => b.text().includes('彻底删除'))).toBe(false)

    vm.showDeletedOnly = true
    await flushPromises()
    expect(wrapper.find('.el-popconfirm-stub').exists()).toBe(false)
    const restoreBtn = wrapper.findAll('.el-button-stub').find((b) => b.text() === '恢复')
    const purgeBtn = wrapper.findAll('.el-button-stub').find((b) => b.text() === '彻底删除')
    expect(restoreBtn).toBeTruthy()
    expect(purgeBtn).toBeTruthy()

    await restoreBtn!.trigger('click')
    await flushPromises()
    expect(confirmMock).toHaveBeenCalledWith(
      '确定恢复项目【产业路】吗？恢复后将重新出现在正常列表中。',
      '恢复确认', expect.anything()
    )
    expect(projectApiMock.restore).toHaveBeenCalledWith(1)

    await purgeBtn!.trigger('click')
    await flushPromises()
    expect(projectApiMock.purgePreview).toHaveBeenCalledWith(1)
    expect(confirmMock).toHaveBeenCalledWith(
      expect.stringContaining('彻底删除后【产业路】及其关联的 0 条数据将无法恢复'),
      '彻底删除警告', expect.anything()
    )
  })

  describe('handleRestore 异常分支', () => {
    it('confirm 取消 → return（branch@512）', async () => {
      confirmMock.mockRejectedValueOnce('cancel')
      const wrapper = mountComp()
      await flushPromises()
      await (wrapper.vm as any).handleRestore({ id: 1, name: '产业路' })
      await flushPromises()
      expect(projectApiMock.restore).not.toHaveBeenCalled()
      expect(ElMessage.success).not.toHaveBeenCalled()
      expect(ElMessage.error).not.toHaveBeenCalled()
    })

    it('restoreProject 失败 → 「恢复失败」（branch@519）', async () => {
      projectApiMock.restore.mockRejectedValueOnce(new Error('boom'))
      const wrapper = mountComp()
      await flushPromises()
      projectApiMock.list.mockClear()
      await (wrapper.vm as any).handleRestore({ id: 1, name: '产业路' })
      await flushPromises()
      expect(ElMessage.error).toHaveBeenCalledWith('恢复失败')
      expect(projectApiMock.list).not.toHaveBeenCalled()
    })
  })

  describe('handlePurge 预览与提示分支', () => {
    it('preview 无 data 包装 → 直接取 preview（branch@529 第二操作数），details 排序/截取前三拼接级联提示', async () => {
      projectApiMock.purgePreview.mockResolvedValueOnce({
        total_references: 9,
        details: { funds: 2, schools: 5, contracts: 1, milestones: 1 },
      })
      const wrapper = mountComp()
      await flushPromises()
      await (wrapper.vm as any).handlePurge({ id: 1, name: '产业路' })
      await flushPromises()
      const msg = confirmMock.mock.calls.at(-1)?.[0] as string
      expect(msg).toContain('关联的 9 条数据将无法恢复')
      // 按条数降序取前 3：schools 5、funds 2、contracts/milestones 1 中先出现的一个
      expect(msg).toContain('（含 schools 5条、funds 2条、')
      expect(msg).toContain('等）！此操作不可撤销。')
      expect(msg).not.toContain('milestones')
    })

    it('preview 为 null → || {} 兑底（branch@529 第三操作数），totalRefs=0、cascadeHint 空（branch@531/536）', async () => {
      projectApiMock.purgePreview.mockResolvedValueOnce(null)
      const wrapper = mountComp()
      await flushPromises()
      await (wrapper.vm as any).handlePurge({ id: 1, name: '产业路' })
      await flushPromises()
      const msg = confirmMock.mock.calls.at(-1)?.[0] as string
      expect(msg).toBe('彻底删除后【产业路】及其关联的 0 条数据将无法恢复！此操作不可撤销。')
      expect(msg).not.toContain('（含')
    })

    it('preview 异常 → 静默吞掉，cascadeHint 仍为空（branch@537）', async () => {
      projectApiMock.purgePreview.mockRejectedValueOnce(new Error('preview down'))
      const wrapper = mountComp()
      await flushPromises()
      const vm = wrapper.vm as any
      await vm.handlePurge({ id: 1, name: 'X' })
      await flushPromises()
      expect(confirmMock).toHaveBeenCalledWith(
        '彻底删除后【X】及其关联的 0 条数据将无法恢复！此操作不可撤销。',
        '彻底删除警告', expect.anything()
      )
      expect(projectApiMock.purge).toHaveBeenCalledWith(1, 'pw')
      expect(vm.loading).toBe(false)
    })

    it('confirm 取消 → 不进入 prompt（branch@546）', async () => {
      confirmMock.mockRejectedValueOnce('cancel')
      const wrapper = mountComp()
      await flushPromises()
      const vm = wrapper.vm as any
      await vm.handlePurge({ id: 1, name: 'X' })
      await flushPromises()
      expect(promptMock).not.toHaveBeenCalled()
      expect(projectApiMock.purge).not.toHaveBeenCalled()
      expect(vm.loading).toBe(false)
    })

    it('inputValidator（funcs@558）：空密码 → 错误文案；非空 → true；value 为空 → confirmPassword 回退空串（branch@561）', async () => {
      promptMock.mockResolvedValueOnce({ value: undefined })
      const wrapper = mountComp()
      await flushPromises()
      await (wrapper.vm as any).handlePurge({ id: 1, name: 'X' })
      await flushPromises()
      const opts = promptMock.mock.calls[0][2]
      expect(opts).toMatchObject({ confirmButtonText: '确认彻底删除', cancelButtonText: '取消', inputType: 'password' })
      expect(typeof opts.inputValidator).toBe('function')
      expect(opts.inputValidator('')).toBe('密码不能为空')
      expect(opts.inputValidator('   ')).toBe(true) // 仅判 falsy，空白串视为已输入
      expect(opts.inputValidator('pw')).toBe(true)
      expect(projectApiMock.purge).toHaveBeenCalledWith(1, '')
    })

    it('prompt 取消 → return（branch@562）', async () => {
      promptMock.mockRejectedValueOnce('cancel')
      const wrapper = mountComp()
      await flushPromises()
      const vm = wrapper.vm as any
      await vm.handlePurge({ id: 1, name: 'X' })
      await flushPromises()
      expect(confirmMock).toHaveBeenCalledTimes(1)
      expect(projectApiMock.purge).not.toHaveBeenCalled()
      expect(vm.loading).toBe(false)
    })

    it('purge 成功：本地剔除该行 + total 递减（Math.max 下限 0）+ deleted_records 取值（branch@570 左侧）', async () => {
      projectApiMock.purge.mockResolvedValueOnce({ data: { deleted_records: 4 } })
      const wrapper = mountComp()
      await flushPromises()
      const vm = wrapper.vm as any
      expect(vm.projectList).toHaveLength(3)
      expect(vm.pagination.total).toBe(3)
      // 成功后的 loadData() 会重新拉回完整列表并覆盖本地剔除结果，
      // 故把刷新挂起，以便观察 purge 后的中间态（剔除 + total 递减）。
      projectApiMock.list.mockClear()
      projectApiMock.list.mockImplementation(() => new Promise(() => {}))

      await vm.handlePurge({ id: 2, name: '教育项目' })
      await flushPromises()

      expect(projectApiMock.purge).toHaveBeenCalledWith(2, 'pw')
      expect(vm.projectList.map((p: any) => p.id)).toEqual([1, 3])
      expect(vm.pagination.total).toBe(2)
      expect(ElMessage.success).toHaveBeenCalledWith('已彻底删除及清理 4 条关联数据')
      expect(projectApiMock.list).toHaveBeenCalledTimes(1) // 成功后触发刷新（已挂起）
      expect(vm.loading).toBe(false) // finally 已释放
    })

    it('purge 返回 null → result?.data?.deleted_records ?? 0（branch@570 右侧）；total 已为 0 → Math.max 兵底', async () => {
      projectApiMock.purge.mockResolvedValueOnce(null)
      const wrapper = mountComp()
      await flushPromises()
      const vm = wrapper.vm as any
      vm.pagination.total = 0
      projectApiMock.list.mockImplementation(() => new Promise(() => {}))
      await vm.handlePurge({ id: 99, name: '不存在' })
      await flushPromises()
      expect(ElMessage.success).toHaveBeenCalledWith('已彻底删除及清理 0 条关联数据')
      expect(vm.pagination.total).toBe(0) // Math.max(0, 0 - 1) → 0，不为负
      expect(vm.projectList).toHaveLength(3) // id 不在列表中 → filter 全部保留
      expect(vm.loading).toBe(false)
    })

    it('purge 失败 → 「彻底删除失败」，finally 仍释放 loading（branch@572）', async () => {
      projectApiMock.purge.mockRejectedValueOnce(new Error('fail'))
      const wrapper = mountComp()
      await flushPromises()
      const vm = wrapper.vm as any
      projectApiMock.list.mockClear()
      await vm.handlePurge({ id: 1, name: 'X' })
      await flushPromises()
      expect(ElMessage.error).toHaveBeenCalledWith('彻底删除失败')
      expect(vm.loading).toBe(false)
      expect(projectApiMock.list).not.toHaveBeenCalled()
      expect(vm.projectList).toHaveLength(3) // 未剔除
    })
  })

  describe('handleBatchRestore（funcs@579）', () => {
    it('confirm 取消 → 不调用 restore', async () => {
      confirmMock.mockRejectedValueOnce('cancel')
      const wrapper = mountComp()
      await flushPromises()
      const vm = wrapper.vm as any
      vm.selectedRows = [{ ...projectRow }]
      await vm.handleBatchRestore()
      await flushPromises()
      expect(projectApiMock.restore).not.toHaveBeenCalled()
      expect(ElMessage.success).not.toHaveBeenCalled()
      expect(vm.selectedRows).toHaveLength(1) // 未清空
    })

    it('逐项恢复成功 → 成功提示 + clearSelection + loadData', async () => {
      const wrapper = mountComp()
      await flushPromises()
      const vm = wrapper.vm as any
      vm.selectedRows = [{ ...projectRow }, { ...projectRow2 }, { ...projectRow3 }]
      projectApiMock.list.mockClear()
      await vm.handleBatchRestore()
      await flushPromises()
      expect(projectApiMock.restore).toHaveBeenCalledTimes(3)
      expect(projectApiMock.restore.mock.calls.map((c: any[]) => c[0])).toEqual([1, 2, 3])
      expect(ElMessage.success).toHaveBeenCalledWith('已恢复 3 个项目')
      expect(vm.selectedRows).toEqual([])
      expect(projectApiMock.list).toHaveBeenCalled()
      expect(ElMessage.error).not.toHaveBeenCalled()
    })

    it('中途失败 → 「批量恢复失败」，不清空选中也不刷新', async () => {
      projectApiMock.restore
        .mockResolvedValueOnce({})
        .mockRejectedValueOnce(new Error('boom'))
      const wrapper = mountComp()
      await flushPromises()
      const vm = wrapper.vm as any
      vm.selectedRows = [{ ...projectRow }, { ...projectRow2 }, { ...projectRow3 }]
      projectApiMock.list.mockClear()
      await vm.handleBatchRestore()
      await flushPromises()
      // for-of 在第 2 项抛错后中断，第 3 项未调用
      expect(projectApiMock.restore).toHaveBeenCalledTimes(2)
      expect(ElMessage.error).toHaveBeenCalledWith('批量恢复失败')
      expect(ElMessage.success).not.toHaveBeenCalled()
      expect(vm.selectedRows).toHaveLength(3)
      expect(projectApiMock.list).not.toHaveBeenCalled()
    })

    it('选中为空数组 → 循环不执行，仍提示已恢复 0 个', async () => {
      const wrapper = mountComp()
      await flushPromises()
      const vm = wrapper.vm as any
      vm.selectedRows = []
      await vm.handleBatchRestore()
      await flushPromises()
      expect(projectApiMock.restore).not.toHaveBeenCalled()
      expect(ElMessage.success).toHaveBeenCalledWith('已恢复 0 个项目')
    })
  })

  describe('handleBatchPurge（funcs@601）', () => {
    it('prompt 取消 → 不调用 purge，loading 未被置起', async () => {
      promptMock.mockRejectedValueOnce('cancel')
      const wrapper = mountComp()
      await flushPromises()
      const vm = wrapper.vm as any
      vm.selectedRows = [{ ...projectRow }]
      await vm.handleBatchPurge()
      await flushPromises()
      expect(projectApiMock.purge).not.toHaveBeenCalled()
      expect(vm.loading).toBe(false)
      expect(vm.selectedRows).toHaveLength(1)
    })

    it('inputValidator（funcs@607）与 value 为空回退空串', async () => {
      promptMock.mockResolvedValueOnce({ value: undefined })
      const wrapper = mountComp()
      await flushPromises()
      const vm = wrapper.vm as any
      vm.selectedRows = [{ ...projectRow }]
      await vm.handleBatchPurge()
      await flushPromises()
      const opts = promptMock.mock.calls[0][2]
      expect(opts.inputValidator('')).toBe('密码不能为空')
      expect(opts.inputValidator('pw')).toBe(true)
      expect(projectApiMock.purge).toHaveBeenCalledWith(1, '')
    })

    it('逐项彻底删除成功 → 成功提示 + clearSelection + loadData + finally 释放 loading', async () => {
      const wrapper = mountComp()
      await flushPromises()
      const vm = wrapper.vm as any
      vm.selectedRows = [{ ...projectRow }, { ...projectRow2 }]
      projectApiMock.list.mockClear()
      await vm.handleBatchPurge()
      await flushPromises()
      expect(projectApiMock.purge).toHaveBeenCalledTimes(2)
      expect(projectApiMock.purge).toHaveBeenCalledWith(1, 'pw')
      expect(projectApiMock.purge).toHaveBeenCalledWith(2, 'pw')
      expect(ElMessage.success).toHaveBeenCalledWith('已彻底删除 2 个项目及关联数据')
      expect(vm.selectedRows).toEqual([])
      expect(projectApiMock.list).toHaveBeenCalled()
      expect(vm.loading).toBe(false)
    })

    it('中途失败 → 「批量彻底删除失败」，finally 仍释放 loading', async () => {
      projectApiMock.purge
        .mockResolvedValueOnce({})
        .mockRejectedValueOnce(new Error('fail'))
      const wrapper = mountComp()
      await flushPromises()
      const vm = wrapper.vm as any
      vm.selectedRows = [{ ...projectRow }, { ...projectRow2 }]
      projectApiMock.list.mockClear()
      await vm.handleBatchPurge()
      await flushPromises()
      expect(projectApiMock.purge).toHaveBeenCalledTimes(2)
      expect(ElMessage.error).toHaveBeenCalledWith('批量彻底删除失败')
      expect(ElMessage.success).not.toHaveBeenCalled()
      expect(vm.loading).toBe(false)
      expect(vm.selectedRows).toHaveLength(2)
      expect(projectApiMock.list).not.toHaveBeenCalled()
    })
  })
})
