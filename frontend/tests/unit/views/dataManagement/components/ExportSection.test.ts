/**
 * views/dataManagement/components/ExportSection.vue 覆盖率攻坚（四指标 100%）
 * 覆盖：onMounted 加载导出历史（data.items/items 两种形态、失败）、handleExport 成功/失败
 * （筛选条件四个 if 真/假侧）、handleDownload 成功/失败、resetForm、formatTime（空/分钟补零）、
 * 模板：开始导出/重置/刷新/下载按钮、radio/select/switch/input v-model、历史行状态标签与大小三元。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

const {
  ElMessage,
  mockExportVillages,
  mockExportFunds,
  mockGetExportTasks,
  mockDownloadExportFile,
  formatExportStatus,
  formatFileSize,
} = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  mockExportVillages: vi.fn(),
  mockExportFunds: vi.fn(),
  mockGetExportTasks: vi.fn(),
  mockDownloadExportFile: vi.fn(),
  formatExportStatus: vi.fn((s: string) => ({ type: 'success', text: `状态${s}` })),
  formatFileSize: vi.fn((b: number) => `${b}B`),
}))

vi.mock('element-plus', () => ({ ElMessage }))

vi.mock('@/api/export', () => ({
  exportVillages: mockExportVillages,
  exportFunds: mockExportFunds,
  getExportTasks: mockGetExportTasks,
  downloadExportFile: mockDownloadExportFile,
  formatExportStatus,
  formatFileSize,
}))

import ExportSection from '@/views/dataManagement/components/ExportSection.vue'

const rowA = {
  export_type: 'villages',
  status: 'completed',
  file_size: 2048,
  created_at: '2024-06-01 10:05:00',
  is_downloadable: true,
  task_id: 't1',
}
const rowB = {
  export_type: 'yearly_stats',
  status: 'failed',
  file_size: 0,
  created_at: '',
  is_downloadable: false,
  task_id: 't2',
}

function mountComp() {
  return mount(ExportSection, {
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
            '<div class="el-table-column-stub"><slot :row="rowA" /><slot :row="rowB" /></div>',
          data() {
            return { rowA, rowB }
          },
        },
        'el-select': {
          name: 'ElSelect',
          template: '<div class="el-select-stub"><slot /></div>',
          emits: ['update:modelValue'],
        },
        'el-radio-group': {
          name: 'ElRadioGroup',
          template: '<div class="el-radio-group-stub"><slot /></div>',
          emits: ['update:modelValue'],
        },
        'el-switch': {
          name: 'ElSwitch',
          props: ['modelValue'],
          template:
            '<button class="el-switch-stub" @click="$emit(\'update:modelValue\', !modelValue)" />',
        },
        'el-input': {
          name: 'ElInput',
          template: '<div class="el-input-stub" />',
          emits: ['update:modelValue'],
        },
        'el-divider': {
          name: 'ElDivider',
          template: '<div class="el-divider-stub" />',
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
  formatExportStatus.mockImplementation((s: string) => ({ type: 'success', text: `状态${s}` }))
  formatFileSize.mockImplementation((b: number) => `${b}B`)
  mockGetExportTasks.mockResolvedValue({ data: { items: [rowA, rowB] } })
  mockExportVillages.mockResolvedValue(undefined)
  mockDownloadExportFile.mockResolvedValue(undefined)
})

describe('挂载与导出历史', () => {
  it('onMounted：res.data.items 形态加载历史', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(mockGetExportTasks).toHaveBeenCalledWith({ page: 1, page_size: 10 })
    expect(vm.historyList).toEqual([rowA, rowB])
    expect(vm.loadingHistory).toBe(false)
    // 模板：状态标签、大小、时间、下载按钮 v-if 两侧
    const text = wrapper.text()
    expect(text).toContain('状态completed')
    expect(text).toContain('2048B')
    expect(text).toContain('6/1 10:05')
    expect(text).toContain('-') // rowB file_size 0 → falsy → '-'
  })

  it('res.items 形态；失败 → logger 兜底', async () => {
    mockGetExportTasks.mockResolvedValue({ items: [rowA] })
    let wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).historyList).toEqual([rowA])

    mockGetExportTasks.mockRejectedValue(new Error('net'))
    wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).historyList).toEqual([])
    expect((wrapper.vm as any).loadingHistory).toBe(false)
  })

  it('空对象/null 响应 → historyList 兜底为空数组', async () => {
    mockGetExportTasks.mockResolvedValue({})
    let wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).historyList).toEqual([])

    mockGetExportTasks.mockResolvedValue(null)
    wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).historyList).toEqual([])
  })

  it('刷新按钮触发 loadHistory', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const base = mockGetExportTasks.mock.calls.length
    const refresh = wrapper
      .findAll('el-button-stub')
      .find((b: any) => b.text().trim() === '')
    expect(refresh).toBeTruthy()
    await refresh.trigger('click')
    await flushPromises()
    expect(mockGetExportTasks.mock.calls.length).toBe(base + 1)
  })
})

describe('handleExport', () => {
  it('全筛选条件 → 载荷包含全部字段；成功提示 + emit + 刷新历史', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    Object.assign(vm.exportForm.filters, {
      department: '作战处',
      support_unit: '帮扶队',
      region_scope: '都匀市',
      is_revitalization_tier: true,
    })
    await vm.handleExport()
    expect(mockExportVillages).toHaveBeenCalledWith({
      type: 'villages',
      format: 'xlsx',
      department: '作战处',
      support_unit: '帮扶队',
      region_scope: '都匀市',
      is_revitalization_tier: true,
    })
    expect(ElMessage.success).toHaveBeenCalledWith('导出成功')
    expect(wrapper.emitted('export-complete')).toHaveLength(1)
    expect(mockGetExportTasks).toHaveBeenCalled()
    expect(vm.exporting).toBe(false)
  })

  it('无筛选条件 → 仅 type/format；模板「开始导出」按钮点击触发', async () => {
    const wrapper = mountComp()
    await flushPromises()
    await findBtn(wrapper, '开始导出').trigger('click')
    await flushPromises()
    expect(mockExportVillages).toHaveBeenCalledWith({ type: 'villages', format: 'xlsx' })
  })

  it('导出异常 → error 提示，finally 复位', async () => {
    mockExportVillages.mockRejectedValue(new Error('net'))
    const wrapper = mountComp()
    await flushPromises()
    await (wrapper.vm as any).handleExport()
    expect(ElMessage.error).toHaveBeenCalledWith('导出失败')
    expect((wrapper.vm as any).exporting).toBe(false)
  })

  it('dataType=yearly_stats 走 exportVillages 年度统计', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.exportForm.dataType = 'yearly_stats'
    mockExportVillages.mockClear()
    await vm.handleExport()
    expect(mockExportVillages).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'yearly_stats', format: 'xlsx' })
    )
    expect(ElMessage.success).toHaveBeenCalledWith('导出成功')
  })

  it('dataType=industry 走 exportVillages 产业帮扶', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.exportForm.dataType = 'industry'
    mockExportVillages.mockClear()
    await vm.handleExport()
    expect(mockExportVillages).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'industry', format: 'xlsx' })
    )
  })

  it('dataType=funding 走 exportFunds', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.exportForm.dataType = 'funding'
    mockExportVillages.mockClear()
    await vm.handleExport()
    expect(mockExportFunds).toHaveBeenCalled()
    expect(mockExportVillages).not.toHaveBeenCalled()
  })
})

describe('handleDownload / resetForm / formatTime', () => {
  it('handleDownload 成功与失败（模板下载按钮点击）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    await findBtn(wrapper, '下载').trigger('click') // rowA
    await flushPromises()
    expect(mockDownloadExportFile).toHaveBeenCalledWith('t1')
    expect(ElMessage.success).toHaveBeenCalledWith('下载成功')

    mockDownloadExportFile.mockRejectedValue(new Error('net'))
    await findBtn(wrapper, '下载').trigger('click')
    await flushPromises()
    expect(ElMessage.error).toHaveBeenCalledWith('下载失败')
  })

  it('resetForm 还原表单；「重置」按钮点击', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.exportForm.dataType = 'funding'
    vm.exportForm.format = 'pdf'
    vm.exportForm.filters.department = 'x'
    await findBtn(wrapper, '重置').trigger('click')
    expect(vm.exportForm.dataType).toBe('villages')
    expect(vm.exportForm.format).toBe('xlsx')
    expect(vm.exportForm.filters.department).toBe('')
    expect(vm.exportForm.filters.is_revitalization_tier).toBe(false)
  })

  it('formatTime：空串 → "-"；分钟个位数补零', () => {
    const wrapper = mountComp()
    const vm = wrapper.vm as any
    expect(vm.formatTime('')).toBe('-')
    const out = vm.formatTime('2024-01-01T08:05:00')
    expect(out).toContain('8:05')
  })
})

describe('表单 v-model', () => {
  it('dataType/format/filters 各控件同步', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    wrapper.findAllComponents({ name: 'ElSelect' })[0].vm.$emit('update:modelValue', 'funding')
    expect(vm.exportForm.dataType).toBe('funding')
    wrapper.findAllComponents({ name: 'ElRadioGroup' })[0].vm.$emit('update:modelValue', 'csv')
    expect(vm.exportForm.format).toBe('csv')
    const inputs = wrapper.findAllComponents({ name: 'ElInput' })
    inputs[0].vm.$emit('update:modelValue', '部门A')
    expect(vm.exportForm.filters.department).toBe('部门A')
    inputs[1].vm.$emit('update:modelValue', '单位B')
    expect(vm.exportForm.filters.support_unit).toBe('单位B')
    wrapper.findAllComponents({ name: 'ElSwitch' })[0].vm.$emit('update:modelValue', true)
    expect(vm.exportForm.filters.is_revitalization_tier).toBe(true)
    // 地区范围下拉 v-model 后再次导出 → 经费类型走 exportFunds，region_scope 进入载荷
    wrapper.findAllComponents({ name: 'ElSelect' })[1].vm.$emit('update:modelValue', '长顺县')
    await vm.handleExport()
    expect(mockExportFunds).toHaveBeenCalledWith(
      expect.objectContaining({ region_scope: '长顺县', type: 'funding' })
    )
  })
})
