/**
 * views/system/ErrorReports.vue 覆盖率攻坚
 * 覆盖：统计/列表加载、筛选/分页、详情弹窗、状态更新、工具函数
 *
 * 契约要点（与 ErrorReports.vue 当前实现一致）：
 * - 状态值：open / in_progress / resolved / ignored
 * - 列表/详情字段为 camelCase：createdAt / errorType / stackTrace / resolvedAt / resolutionNote
 * - showDetail 读取 res.data.resolutionNote || res.data.resolution_note
 * - updateForm 默认 status 为 'resolved'
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises, enableAutoUnmount } from '@vue/test-utils'
import { nextTick } from 'vue'

enableAutoUnmount(afterEach)

const { ElMessage, errorReportApi } = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  errorReportApi: {
    getStats: vi.fn(),
    listReports: vi.fn(),
    getReport: vi.fn(),
    updateReport: vi.fn(),
  },
}))

vi.mock('@/api/errorReport', () => ({
  errorReportApi,
}))

vi.mock('element-plus', () => ({
  ElMessage,
  ElMessageBox: { confirm: vi.fn(() => Promise.resolve('confirm')), alert: vi.fn() },
  ElNotification: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))

import ErrorReports from '@/views/system/ErrorReports.vue'

const statsData = {
  total: 10,
  open: 4,
  critical: 2,
  by_source: { frontend: 6, backend: 4 },
  by_severity: { critical: 2, error: 5, warning: 3 },
}

const listData = {
  success: true,
  data: {
    items: [
      { id: 1, source: 'frontend', errorType: 'TypeError', message: 'msg1', severity: 'critical', status: 'open', createdAt: '2024-01-01T10:00:00Z' },
      { id: 2, source: 'backend', errorType: 'ValueError', message: 'msg2', severity: 'warning', status: 'in_progress', createdAt: '2024-01-02T10:00:00Z' },
    ],
    total: 2,
  },
}

const detailData = {
  success: true,
  data: {
    id: 1,
    source: 'frontend',
    errorType: 'TypeError',
    message: 'msg1',
    severity: 'critical',
    status: 'open',
    reporter: 'admin',
    createdAt: '2024-01-01T10:00:00Z',
    resolvedAt: '2024-01-03T10:00:00Z',
    stackTrace: 'at fn (file.js:1:1)',
    context: { user: 'admin' },
    resolutionNote: '已修复',
  },
}

async function mountComp() {
  const w = mount(ErrorReports, {
    global: {
      renderStubDefaultSlot: true,
      stubs: {
        'el-row': { name: 'ElRow', template: '<div class="el-row-stub"><slot /></div>' },
        'el-col': { name: 'ElCol', template: '<div class="el-col-stub"><slot /></div>' },
        'el-card': {
          name: 'ElCard',
          template: '<div class="el-card-stub"><slot /><slot name="header" /></div>',
        },
        'el-icon': { name: 'ElIcon', template: '<span><slot /></span>' },
        'el-tag': { name: 'ElTag', template: '<span class="el-tag-stub"><slot /></span>' },
        'el-form': { name: 'ElForm', template: '<form><slot /></form>' },
        'el-form-item': { name: 'ElFormItem', template: '<div><slot /></div>' },
        'el-select': {
          name: 'ElSelect',
          props: ['modelValue'],
          emits: ['update:modelValue', 'change'],
          template:
            '<select class="el-select-stub" @change="$emit(\'update:modelValue\', $event.target.value); $emit(\'change\', $event.target.value)"><slot /></select>',
        },
        'el-option': { name: 'ElOption', props: ['value'], template: '<option :value="value"><slot /></option>' },
        'el-input': {
          name: 'ElInput',
          props: ['modelValue'],
          emits: ['update:modelValue', 'clear'],
          template:
            '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
        },
        'el-button': {
          name: 'ElButton',
          template: '<button class="el-button-stub"><slot /></button>',
        },
        'el-table': { name: 'ElTable', template: '<table class="el-table-stub"><slot /></table>' },
        'el-table-column': {
          name: 'ElTableColumn',
          template: '<div class="el-table-column-stub"><slot :row="rowA" /><slot :row="rowB" /></div>',
          data() {
            return {
              rowA: { id: 1, createdAt: '2024-01-01T10:00:00Z', source: 'frontend', errorType: 'TypeError', message: 'msg1', severity: 'critical', status: 'open' },
              rowB: { id: 2, createdAt: 'not-a-date', source: 'backend', errorType: 'ValueError', message: 'msg2', severity: 'unknown-sev', status: 'unknown-status' },
            }
          },
        },
        'el-pagination': {
          name: 'ElPagination',
          template: '<div class="el-pagination-stub"><slot /></div>',
        },
        'el-dialog': {
          name: 'ElDialog',
          template: '<div class="el-dialog-stub"><slot /><slot name="footer" /></div>',
          emits: ['update:modelValue'],
        },
        'el-skeleton': { name: 'ElSkeleton', template: '<div class="el-skeleton-stub" />' },
        'el-descriptions': { name: 'ElDescriptions', template: '<dl><slot /></dl>' },
        'el-descriptions-item': {
          name: 'ElDescriptionsItem',
          template: '<div class="el-desc-item-stub"><slot /></div>',
        },
        'el-divider': { name: 'ElDivider', template: '<div class="el-divider-stub"><slot /></div>' },
      },
    },
  })
  await flushPromises()
  await nextTick()
  return w
}

beforeEach(() => {
  vi.clearAllMocks()
  errorReportApi.getStats.mockResolvedValue({ success: true, data: statsData })
  errorReportApi.listReports.mockResolvedValue(listData)
  errorReportApi.getReport.mockResolvedValue(detailData)
  errorReportApi.updateReport.mockResolvedValue({ success: true, message: '状态更新成功' })
})

describe('ErrorReports.vue', () => {
  it('渲染并加载统计/列表', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    expect(errorReportApi.getStats).toHaveBeenCalled()
    expect(errorReportApi.listReports).toHaveBeenCalledWith({ page: 1, page_size: 20 })
    expect(vm.stats.total).toBe(10)
    expect(vm.tableData.length).toBe(2)
    expect(vm.tableTotal).toBe(2)
    expect(vm.stats.open).toBe(4)
    // 列表数据为 camelCase 字段
    expect(vm.tableData[0].errorType).toBe('TypeError')
    expect(vm.tableData[0].createdAt).toBe('2024-01-01T10:00:00Z')
    // 更新表单默认值：status = resolved
    expect(vm.updateForm.status).toBe('resolved')
    expect(vm.updateForm.resolution_note).toBe('')
  })

  it('加载统计失败 → 错误提示', async () => {
    errorReportApi.getStats.mockRejectedValue(new Error('stats failed'))
    const w = await mountComp()
    expect(ElMessage.error).toHaveBeenCalledWith('加载错误统计失败')
    expect((w.vm as any).statsLoading).toBe(false)
  })

  it('loadStats：success=false → 不更新统计', async () => {
    errorReportApi.getStats.mockResolvedValue({ success: false, data: null })
    const w = await mountComp()
    const vm = w.vm as any
    expect(vm.stats.total).toBe(0)
    expect(vm.stats.open).toBe(0)
  })

  it('loadStats：success=true 但 data 为空 → 不更新统计', async () => {
    errorReportApi.getStats.mockResolvedValue({ success: true, data: null })
    const w = await mountComp()
    expect((w.vm as any).stats.total).toBe(0)
  })

  it('加载列表失败 → 清空并提示', async () => {
    errorReportApi.listReports.mockRejectedValue(new Error('list failed'))
    const w = await mountComp()
    expect(ElMessage.error).toHaveBeenCalledWith('加载错误报告列表失败')
    expect((w.vm as any).tableData).toEqual([])
    expect((w.vm as any).tableTotal).toBe(0)
  })

  it('loadTableData：success=false → 列表保持为空', async () => {
    errorReportApi.listReports.mockResolvedValue({ success: false, data: null })
    const w = await mountComp()
    expect((w.vm as any).tableData).toEqual([])
    expect((w.vm as any).tableTotal).toBe(0)
  })

  it('handleSearch / handleReset / handlePageSizeChange', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    vm.filters.severity = 'critical'
    vm.filters.status = 'open'
    vm.filters.source = 'front'
    await vm.handleSearch()
    expect(errorReportApi.listReports).toHaveBeenLastCalledWith(
      expect.objectContaining({ severity: 'critical', status: 'open', source: 'front' })
    )
    await vm.handleReset()
    expect(vm.filters.severity).toBeUndefined()
    expect(errorReportApi.listReports).toHaveBeenCalled()
    vm.pagination.pageSize = 50
    await vm.handlePageSizeChange()
    expect(vm.pagination.page).toBe(1)
  })

  it('showDetail：成功 → 填充详情与更新表单', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    await vm.showDetail(1)
    expect(errorReportApi.getReport).toHaveBeenCalledWith(1)
    expect(vm.detail?.id).toBe(1)
    // 详情字段为 camelCase
    expect(vm.detail?.errorType).toBe('TypeError')
    expect(vm.detail?.stackTrace).toBe('at fn (file.js:1:1)')
    expect(vm.detail?.resolvedAt).toBe('2024-01-03T10:00:00Z')
    expect(vm.detail?.resolutionNote).toBe('已修复')
    expect(vm.updateForm.status).toBe('open')
    expect(vm.updateForm.resolution_note).toBe('已修复')
    expect(vm.detailLoading).toBe(false)
  })

  it('showDetail：失败 → 关闭弹窗并提示', async () => {
    errorReportApi.getReport.mockRejectedValue(new Error('detail failed'))
    const w = await mountComp()
    const vm = w.vm as any
    await vm.showDetail(1)
    expect(ElMessage.error).toHaveBeenCalledWith('加载错误详情失败')
    expect(vm.detailVisible).toBe(false)
  })

  it('showDetail：success=false → 不填充详情', async () => {
    errorReportApi.getReport.mockResolvedValue({ success: false, data: null })
    const w = await mountComp()
    const vm = w.vm as any
    await vm.showDetail(9)
    expect(vm.detail).toBeNull()
    expect(vm.detailLoading).toBe(false)
  })

  it('showDetail：resolutionNote 缺失 → 回退 resolution_note', async () => {
    errorReportApi.getReport.mockResolvedValue({
      success: true,
      data: { id: 4, source: 's', errorType: 'E', message: 'm', severity: 'info', status: 'ignored', createdAt: '2024-01-01T10:00:00Z', resolution_note: 'snake 备注' },
    })
    const w = await mountComp()
    const vm = w.vm as any
    await vm.showDetail(4)
    expect(vm.updateForm.resolution_note).toBe('snake 备注')
    expect(vm.updateForm.status).toBe('ignored')
  })

  it('showDetail：无 reporter/resolvedAt → 兜底渲染', async () => {
    errorReportApi.getReport.mockResolvedValue({
      success: true,
      data: { id: 3, source: 'x', errorType: 'y', message: 'm', severity: 'info', status: 'open', createdAt: '2024-01-01T10:00:00Z' },
    })
    const w = await mountComp()
    const vm = w.vm as any
    await vm.showDetail(3)
    expect(vm.detail?.reporter).toBeUndefined()
    expect(vm.updateForm.resolution_note).toBe('')
    // 更新时 resolution_note 为空 → undefined
    errorReportApi.updateReport.mockClear()
    errorReportApi.updateReport.mockResolvedValue({ success: true })
    await vm.handleUpdateStatus()
    expect(errorReportApi.updateReport).toHaveBeenCalledWith(3, {
      status: 'open',
      resolution_note: undefined,
    })
  })

  it('showDetail：列表 items/total 缺失 → 兜底', async () => {
    errorReportApi.listReports.mockResolvedValue({ success: true, data: {} })
    const w = await mountComp()
    expect((w.vm as any).tableData).toEqual([])
    expect((w.vm as any).tableTotal).toBe(0)
  })

  it('统计分类缺失 → 空对象兜底', async () => {
    errorReportApi.getStats.mockResolvedValue({
      success: true,
      data: { total: 1, open: 1, critical: 0 },
    })
    const w = await mountComp()
    const vm = w.vm as any
    expect(vm.stats.by_source).toBeUndefined()
    await nextTick()
    expect(w.find('.empty-hint').exists()).toBe(true)
  })

  it('handleUpdateStatus：无详情 → 返回', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    await vm.handleUpdateStatus()
    expect(errorReportApi.updateReport).not.toHaveBeenCalled()
  })

  it('handleUpdateStatus：更新成功', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    await vm.showDetail(1)
    await vm.handleUpdateStatus()
    expect(errorReportApi.updateReport).toHaveBeenCalledWith(1, {
      status: 'open',
      resolution_note: '已修复',
    })
    expect(ElMessage.success).toHaveBeenCalledWith('状态更新成功')
    expect(vm.detailVisible).toBe(false)
  })

  it('handleUpdateStatus：成功但无 message → 默认文案', async () => {
    errorReportApi.updateReport.mockResolvedValue({ success: true })
    const w = await mountComp()
    const vm = w.vm as any
    await vm.showDetail(1)
    await vm.handleUpdateStatus()
    expect(ElMessage.success).toHaveBeenCalledWith('状态更新成功')
  })

  it('handleUpdateStatus：接口返回失败 → 错误提示', async () => {
    errorReportApi.updateReport.mockResolvedValue({ success: false, message: '服务器拒绝' })
    const w = await mountComp()
    const vm = w.vm as any
    await vm.showDetail(1)
    await vm.handleUpdateStatus()
    expect(ElMessage.error).toHaveBeenCalledWith('服务器拒绝')
  })

  it('handleUpdateStatus：接口返回失败无 message → 默认文案', async () => {
    errorReportApi.updateReport.mockResolvedValue({ success: false })
    const w = await mountComp()
    const vm = w.vm as any
    await vm.showDetail(1)
    await vm.handleUpdateStatus()
    expect(ElMessage.error).toHaveBeenCalledWith('状态更新失败')
  })

  it('handleUpdateStatus：异常 → 错误提示', async () => {
    errorReportApi.updateReport.mockRejectedValue(new Error('update failed'))
    const w = await mountComp()
    const vm = w.vm as any
    await vm.showDetail(1)
    await vm.handleUpdateStatus()
    expect(ElMessage.error).toHaveBeenCalledWith('状态更新失败')
    expect(vm.updateLoading).toBe(false)
  })

  it('refreshAll 并行刷新', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    vi.clearAllMocks()
    errorReportApi.getStats.mockResolvedValue({ success: true, data: statsData })
    errorReportApi.listReports.mockResolvedValue(listData)
    await vm.refreshAll()
    expect(errorReportApi.getStats).toHaveBeenCalled()
    expect(errorReportApi.listReports).toHaveBeenCalled()
  })

  it('工具函数：标签/文本/时间', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    expect(vm.severityLabel('critical')).toBe('严重')
    expect(vm.severityLabel('error')).toBe('错误')
    expect(vm.severityLabel('warning')).toBe('警告')
    expect(vm.severityLabel('info')).toBe('信息')
    expect(vm.severityLabel('unknown')).toBe('unknown')
    expect(vm.severityTagType('critical')).toBe('danger')
    expect(vm.severityTagType('error')).toBe('danger')
    expect(vm.severityTagType('warning')).toBe('warning')
    expect(vm.severityTagType('info')).toBe('info')
    expect(vm.severityTagType('other')).toBe('info')
    // 状态：open / in_progress / resolved / ignored
    expect(vm.statusLabel('open')).toBe('待处理')
    expect(vm.statusLabel('in_progress')).toBe('处理中')
    expect(vm.statusLabel('resolved')).toBe('已解决')
    expect(vm.statusLabel('ignored')).toBe('已忽略')
    expect(vm.statusLabel('x')).toBe('x')
    expect(vm.statusTagType('open')).toBe('warning')
    expect(vm.statusTagType('in_progress')).toBe('primary')
    expect(vm.statusTagType('resolved')).toBe('success')
    expect(vm.statusTagType('ignored')).toBe('info')
    expect(vm.statusTagType('y')).toBe('info')
    expect(vm.formatTime(undefined)).toBe('')
    expect(vm.formatTime('2024-01-01T10:00:00Z')).toContain('2024-01-01')
    expect(vm.formatTime('not-a-date')).toBe('not-a-date')
  })

  it('筛选控件：严重程度/状态 select + 来源输入 + 查询/重置按钮', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    const selects = w.findAll('.el-select-stub')
    await selects[0].setValue('critical')
    expect(vm.filters.severity).toBe('critical')
    await selects[1].setValue('in_progress')
    expect(vm.filters.status).toBe('in_progress')
    const inputs = w.findAll('input')
    await inputs[0].setValue('backend')
    expect(vm.filters.source).toBe('backend')
    const searchBtn = w
      .findAll('button')
      .find((b) => b.text().includes('查询'))
    await searchBtn!.trigger('click')
    expect(errorReportApi.listReports).toHaveBeenLastCalledWith(
      expect.objectContaining({ severity: 'critical', status: 'in_progress', source: 'backend' })
    )
  })

  it('详情按钮（表格行）点击 → 打开详情', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    const detailBtns = w.findAll('button').filter((b) => b.text().includes('详情'))
    expect(detailBtns.length).toBeGreaterThan(0)
    await detailBtns[0].trigger('click')
    expect(errorReportApi.getReport).toHaveBeenCalled()
    expect(vm.detailVisible).toBe(true)
  })

  it('分页 current-change / size-change', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    const pagination = w.findComponent({ name: 'ElPagination' })
    pagination.vm.$emit('update:currentPage', 2)
    await nextTick()
    expect(vm.pagination.page).toBe(2)
    pagination.vm.$emit('update:pageSize', 50)
    await nextTick()
    expect(vm.pagination.pageSize).toBe(50)
    pagination.vm.$emit('size-change', 50)
    await nextTick()
    expect(errorReportApi.listReports).toHaveBeenCalled()
  })

  it('模板交互：刷新/重置/来源输入清除/回车/更新状态按钮', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    // 刷新按钮
    const refreshBtn = w
      .findAll('button')
      .find((b) => b.text().includes('刷新'))
    await refreshBtn!.trigger('click')
    expect(errorReportApi.getStats).toHaveBeenCalled()
    // 重置按钮
    const resetBtn = w
      .findAll('button')
      .find((b) => b.text().includes('重置'))
    await resetBtn!.trigger('click')
    expect(vm.filters.severity).toBeUndefined()
    expect(errorReportApi.listReports).toHaveBeenCalled()
    // 来源输入 v-model
    const inputs = w.findAll('input')
    await inputs[0].setValue('backend')
    expect(vm.filters.source).toBe('backend')
    // 来源输入 clear 事件
    const sourceInput = w.findAllComponents({ name: 'ElInput' })[0]
    sourceInput.vm.$emit('clear')
    await nextTick()
    expect(errorReportApi.listReports).toHaveBeenCalled()
    // 来源输入回车
    await inputs[0].trigger('keyup.enter')
    expect(errorReportApi.listReports).toHaveBeenCalled()
    // 打开详情 → 更新状态按钮
    await vm.showDetail(1)
    await nextTick()
    const updateBtn = w
      .findAll('button')
      .find((b) => b.text().includes('更新状态'))
    await updateBtn!.trigger('click')
    expect(errorReportApi.updateReport).toHaveBeenCalled()
    // 详情对话框关闭（update:modelValue）
    const dialog = w.findComponent({ name: 'ElDialog' })
    dialog.vm.$emit('update:modelValue', false)
    await nextTick()
    expect(vm.detailVisible).toBe(false)
    // 更新表单 select / 备注输入 v-model
    vm.detailVisible = true
    await nextTick()
    const detailSelects = w.findAll('.el-select-stub')
    await detailSelects[detailSelects.length - 1].setValue('resolved')
    expect(vm.updateForm.status).toBe('resolved')
    const detailInputs = w.findAll('.el-dialog-stub input')
    await detailInputs[detailInputs.length - 1].setValue('新备注')
    expect(vm.updateForm.resolution_note).toBe('新备注')
  })
})
