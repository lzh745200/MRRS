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
} = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  confirmMock: vi.fn(),
  projectApiMock: {
    getStats: vi.fn(),
    list: vi.fn(),
    delete: vi.fn(),
    exportList: vi.fn(),
  },
  pushSafeMock: vi.fn(),
  logError: vi.fn(),
}))

vi.mock('element-plus', () => ({
  ElMessage,
  ElMessageBox: { confirm: confirmMock },
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

vi.mock('@/api/projects', () => ({ projectApi: projectApiMock, projectsApi: projectApiMock }))

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
    expect(vm.stats.totalBudget).toBe(124)
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
    expect(pushSafeMock).toHaveBeenCalledWith('/data-import/batch')
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
    expect(ElMessage.error).toHaveBeenCalledWith('导出失败，请稍后重试')
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
