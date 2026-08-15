/**
 * views/export/ReportExport.vue 覆盖率攻坚（四指标 100%）
 * 覆盖：报表类型选择与三个专属配置区 v-if、全部表单 v-model 同步、
 * handleExport（无类型/Blob 下载/非 Blob 异步任务/异常 message 与默认）、
 * getReportFileName 已知与未知类型、handleExportOfficial（word/pdf、year 有/无、
 * 名称命中与兜底、detail 与默认）、打印预览、重置、
 * loadHistory（items/缺省/失败）、downloadExport 成败、历史表槽位（状态/时间/操作）。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises, enableAutoUnmount } from '@vue/test-utils'
import { nextTick } from 'vue'

enableAutoUnmount(afterEach)

const {
  ElMessage,
  mockPost,
  mockDownloadBlob,
  mockGetExportHistory,
  mockDownloadExportFile,
  mockFormatFileSize,
  mockExportReportWord,
  mockExportReportPdf,
  logError,
} = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  mockPost: vi.fn(),
  mockDownloadBlob: vi.fn(),
  mockGetExportHistory: vi.fn(),
  mockDownloadExportFile: vi.fn(),
  mockFormatFileSize: vi.fn((bytes: number) => `${bytes} B`),
  mockExportReportWord: vi.fn(),
  mockExportReportPdf: vi.fn(),
  logError: vi.fn(),
}))

vi.mock('element-plus', () => ({ ElMessage }))

vi.mock('@/api/request', () => ({
  post: mockPost,
  downloadBlob: mockDownloadBlob,
  get: vi.fn(),
  put: vi.fn(),
  del: vi.fn(),
  apiRequest: vi.fn(),
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

vi.mock('@/api/export', () => ({
  getExportHistory: mockGetExportHistory,
  downloadExportFile: mockDownloadExportFile,
  formatFileSize: mockFormatFileSize,
  exportReportWord: mockExportReportWord,
  exportReportPdf: mockExportReportPdf,
}))

vi.mock('@/utils/logger', () => ({
  logger: { error: logError, warn: vi.fn(), info: vi.fn(), debug: vi.fn(), log: vi.fn() },
}))

import ReportExport from '@/views/export/ReportExport.vue'

const historyRows = [
  { task_id: 't1', export_type: 'village_summary', file_name: '报表1.xlsx', file_size: 2048, status: 'completed', created_at: '2024-06-01T00:00:00' },
  { task_id: 't2', report_type: 'annual_summary', file_name: '报表2.xlsx', file_size: 0, status: 'processing' },
  { task_id: 't3', export_type: 'mystery', file_name: '报表3.xlsx', file_size: 1024, status: 'failed', created_at: '2024-06-02T00:00:00' },
]

const stubs = {
  'el-button': {
    name: 'ElButton',
    props: ['disabled', 'loading'],
    template: '<button class="el-button-stub" :disabled="disabled"><slot /></button>',
  },
  'el-card': {
    name: 'ElCard',
    template: '<div class="el-card-stub"><slot name="header" /><slot /></div>',
  },
  'el-table-column': {
    name: 'ElTableColumn',
    template:
      '<div class="el-table-column-stub"><slot :row="rowA" /><slot :row="rowB" /><slot :row="rowC" /></div>',
    data() {
      return { rowA: historyRows[0], rowB: historyRows[1], rowC: historyRows[2] }
    },
  },
  'el-select': {
    name: 'ElSelect',
    template: '<div class="el-select-stub"><slot /></div>',
    emits: ['update:modelValue', 'change'],
  },
  'el-radio-group': {
    name: 'ElRadioGroup',
    template: '<div class="el-radio-group-stub"><slot /></div>',
    emits: ['update:modelValue', 'change'],
  },
  'el-checkbox-group': {
    name: 'ElCheckboxGroup',
    template: '<div class="el-checkbox-group-stub"><slot /></div>',
    emits: ['update:modelValue', 'change'],
  },
  'el-switch': {
    name: 'ElSwitch',
    template: '<div class="el-switch-stub" />',
    emits: ['update:modelValue', 'change'],
  },
  'el-date-picker': {
    name: 'ElDatePicker',
    template: '<div class="el-date-picker-stub" />',
    emits: ['update:modelValue', 'change'],
  },
  'el-icon': { name: 'ElIcon', template: '<span class="el-icon-stub"><slot /></span>' },
}

function mountComp() {
  return mount(ReportExport, {
    global: { renderStubDefaultSlot: true, stubs },
  })
}

const findBtn = (wrapper: any, text: string) => {
  const btn = wrapper.findAll('.el-button-stub').find((b: any) => b.text().trim().includes(text))
  expect(btn, `按钮「${text}」`).toBeTruthy()
  return btn!
}

const printSpy = vi.fn()

beforeEach(() => {
  vi.resetAllMocks() // 清空 mock*Once 队列，避免跨测试污染
  Object.defineProperty(window, 'print', { value: printSpy, writable: true, configurable: true })
  mockGetExportHistory.mockResolvedValue({ items: historyRows })
  mockPost.mockResolvedValue(new Blob(['x'], { type: 'application/vnd.ms-excel' }))
  mockExportReportWord.mockResolvedValue(undefined)
  mockExportReportPdf.mockResolvedValue(undefined)
  mockDownloadExportFile.mockResolvedValue(undefined)
})

describe('挂载与历史渲染', () => {
  it('onMounted 加载历史并渲染各列（名称映射/大小/状态/时间/操作分支）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(mockGetExportHistory).toHaveBeenCalledWith({ page: 1, page_size: 10 })
    expect(vm.exportHistory).toHaveLength(3)
    expect(vm.loadingHistory).toBe(false)
    expect(vm.selectedType).toBe('') // 未选择 → 导出配置区隐藏
    expect(wrapper.find('.export-config').exists()).toBe(false)
    const text = wrapper.text()
    expect(text).toContain('帮扶村汇总报表') // getReportTypeName 命中
    expect(text).toContain('年度工作总结报表')
    expect(text).toContain('mystery') // 未知类型透传
    expect(text).toContain('已完成')
    expect(text).toContain('处理中')
    expect(text).toContain('失败')
    expect(wrapper.findAll('.el-button-stub').some((b: any) => b.text().trim() === '下载')).toBe(true)
    expect(
      wrapper.findAll('.el-button-stub').some((b: any) => b.text().includes('处理中...'))
    ).toBe(true)
  })

  it('loadHistory：空响应 → []；失败 → logger.error', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    mockGetExportHistory.mockResolvedValueOnce({})
    await vm.loadHistory()
    expect(vm.exportHistory).toEqual([])
    mockGetExportHistory.mockRejectedValueOnce(new Error('net'))
    await vm.loadHistory()
    expect(logError).toHaveBeenCalled()
    expect(vm.loadingHistory).toBe(false)
  })

  it('「刷新」按钮重新加载历史', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const before = mockGetExportHistory.mock.calls.length
    await findBtn(wrapper, '刷新').trigger('click')
    await flushPromises()
    expect(mockGetExportHistory.mock.calls.length).toBe(before + 1)
  })

  it('历史「下载」按钮 → downloadExportFile(task_id)；失败提示', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await findBtn(wrapper, '下载').trigger('click')
    expect(mockDownloadExportFile).toHaveBeenCalledWith('t1')
    mockDownloadExportFile.mockRejectedValueOnce(new Error('x'))
    await vm.downloadExport(historyRows[0])
    expect(ElMessage.error).toHaveBeenCalledWith('下载失败')
  })
})

describe('报表类型选择与导出配置', () => {
  it('选择报表类型：导出配置区显隐与 active 高亮；三类专属选项区', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    await vm.handleExport() // 未选择类型 → 警告
    expect(ElMessage.warning).toHaveBeenCalledWith('请选择报表类型')
    expect(mockPost).not.toHaveBeenCalled()

    // 通过模板 type-card 点击触发 selectReportType（覆盖 onClick 包装函数）
    await wrapper.find('.type-card').trigger('click')
    await nextTick()
    expect(vm.selectedType).toBe('village_summary')
    expect(wrapper.find('.export-config').exists()).toBe(true)
    expect(wrapper.find('.el-checkbox-group-stub').exists()).toBe(true) // 统计维度

    vm.selectReportType('fund_analysis')
    await nextTick()
    expect(wrapper.find('.el-checkbox-group-stub').exists()).toBe(true) // 资金类型

    vm.selectReportType('project_progress')
    await nextTick()
    expect(wrapper.find('.el-checkbox-group-stub').exists()).toBe(true) // 项目状态
  })

  it('导出配置全部 v-model 同步（日期范围/数据范围/格式/图表/三组复选/公文件度）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    // 初始（未选类型）仅存在公文年度选择器
    let datePicks = wrapper.findAllComponents({ name: 'ElDatePicker' })
    datePicks[0].vm.$emit('update:modelValue', '2025')
    expect(vm.officialForm.year).toBe('2025')

    vm.selectReportType('village_summary')
    await nextTick()
    const d1 = new Date('2024-01-01T00:00:00Z')
    const d2 = new Date('2024-12-31T00:00:00Z')
    datePicks = wrapper.findAllComponents({ name: 'ElDatePicker' })
    datePicks[0].vm.$emit('update:modelValue', [d1, d2])
    expect(vm.exportForm.dateRange).toEqual([d1, d2])
    datePicks[1].vm.$emit('update:modelValue', '2024')
    expect(vm.officialForm.year).toBe('2024')

    wrapper.findComponent({ name: 'ElSelect' }).vm.$emit('update:modelValue', 'all')
    expect(vm.exportForm.scope).toBe('all')
    wrapper.findComponent({ name: 'ElRadioGroup' }).vm.$emit('update:modelValue', 'pdf')
    expect(vm.exportForm.format).toBe('pdf')
    wrapper.findComponent({ name: 'ElSwitch' }).vm.$emit('update:modelValue', false)
    expect(vm.exportForm.includeCharts).toBe(false)
    wrapper.findComponent({ name: 'ElCheckboxGroup' }).vm.$emit('update:modelValue', ['region'])
    expect(vm.exportForm.dimensions).toEqual(['region'])

    vm.selectReportType('fund_analysis')
    await nextTick()
    wrapper.findComponent({ name: 'ElCheckboxGroup' }).vm.$emit('update:modelValue', ['balance'])
    expect(vm.exportForm.fundTypes).toEqual(['balance'])

    vm.selectReportType('project_progress')
    await nextTick()
    wrapper.findComponent({ name: 'ElCheckboxGroup' }).vm.$emit('update:modelValue', ['completed'])
    expect(vm.exportForm.projectStatus).toEqual(['completed'])
  })

  it('打印预览：无类型警告 / 有类型调用 window.print', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handlePrintPreview()
    expect(ElMessage.warning).toHaveBeenCalledWith('请先选择报表类型')
    expect(printSpy).not.toHaveBeenCalled()
    vm.selectReportType('school_statistics')
    await vm.handlePrintPreview()
    expect(printSpy).toHaveBeenCalled()
  })

  it('重置：dateRange/scope/format/includeCharts 复位（其余字段不动）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.exportForm.dateRange = [new Date(), new Date()]
    vm.exportForm.scope = 'all'
    vm.exportForm.format = 'csv'
    vm.exportForm.includeCharts = false
    vm.exportForm.dimensions = ['year']
    vm.resetForm()
    expect(vm.exportForm.dateRange).toBeNull()
    expect(vm.exportForm.scope).toBe('self')
    expect(vm.exportForm.format).toBe('xlsx')
    expect(vm.exportForm.includeCharts).toBe(true)
    expect(vm.exportForm.dimensions).toEqual(['year'])
  })
})

describe('handleExport 主流程', () => {
  it('Blob 返回：downloadBlob 下载（含日期范围与未知类型文件名兜底）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const d1 = new Date('2024-01-01T00:00:00Z')
    const d2 = new Date('2024-12-31T00:00:00Z')
    vm.exportForm.dateRange = [d1, d2]
    vm.selectReportType('comprehensive')
    await nextTick()
    await findBtn(wrapper, '开始导出').trigger('click')
    await flushPromises()
    expect(mockPost).toHaveBeenCalledWith(
      '/async-export/reports',
      expect.objectContaining({
        report_type: 'comprehensive',
        format: 'xlsx',
        scope: 'self',
        include_charts: true,
        start_date: d1.toISOString(),
        end_date: d2.toISOString(),
        options: expect.any(Object),
      }),
      { responseType: 'blob' }
    )
    expect(mockDownloadBlob).toHaveBeenCalledWith(
      expect.any(Blob),
      expect.stringContaining('综合数据报表_')
    )
    expect(ElMessage.success).toHaveBeenCalledWith('报表导出成功')
    expect(vm.exporting).toBe(false)

    // 未知类型文件名兜底 + dateRange 为 null 分支
    mockPost.mockResolvedValueOnce(new Blob(['y']))
    vm.exportForm.dateRange = null
    vm.selectReportType('mystery_report')
    await vm.handleExport()
    expect(mockDownloadBlob).toHaveBeenLastCalledWith(
      expect.any(Blob),
      expect.stringContaining('报表导出_')
    )
  })

  it('非 Blob 返回：提示异步任务并刷新历史', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    mockPost.mockResolvedValueOnce({ data: { task_id: 'x' } })
    vm.selectReportType('school_statistics')
    await nextTick()
    const before = mockGetExportHistory.mock.calls.length
    await findBtn(wrapper, '开始导出').trigger('click')
    await flushPromises()
    expect(ElMessage.warning).toHaveBeenCalledWith('报表导出中，请稍后在导出历史查看进度')
    expect(mockGetExportHistory.mock.calls.length).toBe(before + 1)
    expect(mockDownloadBlob).not.toHaveBeenCalled()
  })

  it('接口异常：error.message 与默认「导出失败」', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.selectReportType('fund_analysis')
    mockPost.mockRejectedValueOnce(new Error('boom'))
    await vm.handleExport()
    expect(ElMessage.error).toHaveBeenLastCalledWith('boom')
    mockPost.mockRejectedValueOnce({})
    await vm.handleExport()
    expect(ElMessage.error).toHaveBeenLastCalledWith('导出失败')
    expect(vm.exporting).toBe(false)
  })

  it('getReportFileName：已知/未知类型与格式拼接', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const name = vm.getReportFileName('village_summary', 'pdf')
    expect(name).toMatch(/^帮扶村汇总报表_\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}\.pdf$/)
    expect(vm.getReportFileName('nope', 'csv')).toMatch(/^报表导出_.*\.csv$/)
  })
})

describe('公文报告导出', () => {
  it('Word/PDF：year 有/无、名称命中与兜底、成功提示', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    vm.officialForm.year = '2025'
    await findBtn(wrapper, '导出 Word').trigger('click')
    await flushPromises()
    expect(mockExportReportWord).toHaveBeenCalledWith('summary', 2025)
    expect(ElMessage.success).toHaveBeenLastCalledWith('年度帮扶工作总结 导出成功')

    vm.officialForm.year = '' // falsy → undefined
    await findBtn(wrapper, '导出 PDF').trigger('click')
    await flushPromises()
    expect(mockExportReportPdf).toHaveBeenCalledWith('summary', undefined)
    expect(ElMessage.success).toHaveBeenLastCalledWith('年度帮扶工作总结 导出成功')

    // 未知类型名称兜底（直接调用）
    vm.officialForm.year = '2024'
    await vm.handleExportOfficial('unknown_type', 'word')
    expect(mockExportReportWord).toHaveBeenLastCalledWith('unknown_type', 2024)
    expect(ElMessage.success).toHaveBeenLastCalledWith('unknown_type 导出成功')
    expect(vm.officialLoading.unknown_type_word).toBe(false)
  })

  it('导出失败：detail 与默认「WORD/PDF 导出失败」', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    mockExportReportWord.mockRejectedValueOnce({ response: { data: { detail: '模板缺失' } } })
    await vm.handleExportOfficial('summary', 'word')
    expect(ElMessage.error).toHaveBeenLastCalledWith('模板缺失')

    mockExportReportWord.mockRejectedValueOnce({})
    await vm.handleExportOfficial('summary', 'word')
    expect(ElMessage.error).toHaveBeenLastCalledWith('WORD 导出失败')

    mockExportReportPdf.mockRejectedValueOnce({})
    await vm.handleExportOfficial('summary', 'pdf')
    expect(ElMessage.error).toHaveBeenLastCalledWith('PDF 导出失败')
    expect(vm.officialLoading.summary_pdf).toBe(false)
  })
})

describe('映射工具', () => {
  it('getReportTypeName / getExportStatusLabel / getExportStatusType / formatDate', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.getReportTypeName('village_summary')).toBe('帮扶村汇总报表')
    expect(vm.getReportTypeName('zzz')).toBe('zzz')
    expect(vm.getExportStatusLabel('completed')).toBe('已完成')
    expect(vm.getExportStatusLabel('zzz')).toBe('zzz')
    expect(vm.getExportStatusType('completed')).toBe('success')
    expect(vm.getExportStatusType('processing')).toBe('warning')
    expect(vm.getExportStatusType('failed')).toBe('danger')
    expect(vm.getExportStatusType('zzz')).toBe('info')
    expect(vm.formatDate(undefined)).toBe('-')
    expect(vm.formatDate('2024-06-01T10:00:00')).not.toBe('-')
  })
})
