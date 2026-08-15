/**
 * views/import/DataImport.vue 覆盖率攻坚（四指标 100%）
 * 覆盖：模板下载成功/错误三分支（message/detail/默认、非字符串兜底）、
 * 文件选择/移除/重置（uploadRef 有/无）、预览成败（无文件早退、detail/message/默认）、
 * 导入成功/失败/异常（无文件/无预览警告、errors?.length 两侧）、
 * 导入历史加载（items/缺省 []/失败）、分页显隐与翻页、
 * 状态标签映射、预览区与导入结果区模板渲染（skipped/failed/errors 两侧）。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises, enableAutoUnmount } from '@vue/test-utils'
import { nextTick } from 'vue'

enableAutoUnmount(afterEach)

const {
  ElMessage,
  mockDownloadTemplate,
  mockImportEntities,
  mockPreviewImportData,
  mockGetImportHistory,
  mockFormatImportStatus,
} = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  mockDownloadTemplate: vi.fn(),
  mockImportEntities: vi.fn(),
  mockPreviewImportData: vi.fn(),
  mockGetImportHistory: vi.fn(),
  mockFormatImportStatus: vi.fn((s: string) => {
    const map: Record<string, { text: string; type: string }> = {
      pending: { text: '等待中', type: 'info' },
      processing: { text: '处理中', type: 'warning' },
      completed: { text: '已完成', type: 'success' },
      failed: { text: '失败', type: 'danger' },
    }
    return map[s] || { text: s, type: 'info' }
  }),
}))

vi.mock('element-plus', () => ({ ElMessage }))

vi.mock('@/api/import', () => ({
  downloadImportTemplateAndSave: mockDownloadTemplate,
  importEntities: mockImportEntities,
  previewImportData: mockPreviewImportData,
  getImportHistory: mockGetImportHistory,
  formatImportStatus: mockFormatImportStatus,
}))

import DataImport from '@/views/import/DataImport.vue'

const historyRows = [
  {
    id: 1,
    file_name: '帮扶村.xlsx',
    status: 'completed',
    total_rows: 10,
    success_rows: 9,
    failed_rows: 1,
    created_at: '2024-06-01T10:00:00.000Z',
  },
  {
    id: 2,
    file_name: '项目.xlsx',
    status: 'weird',
    total_rows: 0,
    success_rows: 0,
    failed_rows: 0,
  },
]

// 后端预览响应形状：{total_rows, rows:[{data, has_error}], invalid_rows}，视图 handlePreview 会归一化
const previewResponse = {
  total_rows: 12,
  invalid_rows: 2,
  rows: [
    { data: { 村名: '甲村', 县市: '都匀市' }, has_error: false },
    { data: { 村名: '乙村', 县市: '荔波县' }, has_error: true },
  ],
}

// handlePreview 归一化后的 previewData 形状（rows 取自 r.data，columns 为 data 键并集）
const normalizedPreview = {
  rows: [
    { 村名: '甲村', 县市: '都匀市' },
    { 村名: '乙村', 县市: '荔波县' },
  ],
  total: 12,
  columns: ['村名', '县市'],
  invalid_rows: 2,
}

const successResult = {
  success: true,
  total_rows: 10,
  success_rows: 8,
  failed_rows: 1,
  skipped_rows: 1,
  errors: [{ row_number: 3, field_name: '村名', message: '为空' }],
}

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
  'el-alert': {
    name: 'ElAlert',
    props: ['title', 'type'],
    template:
      '<div class="el-alert-stub"><span class="alert-title">{{ title }}</span><slot /><slot name="title" /></div>',
  },
  'el-table-column': {
    name: 'ElTableColumn',
    template: '<div class="el-table-column-stub"><slot :row="rowA" /><slot :row="rowB" /></div>',
    data() {
      return { rowA: historyRows[0], rowB: historyRows[1] }
    },
  },
  'el-upload': {
    name: 'ElUpload',
    template: '<div class="el-upload-stub"><slot /></div>',
    methods: { clearFiles() {} },
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
  'el-pagination': {
    name: 'ElPagination',
    props: ['total', 'pageSize', 'currentPage'],
    emits: ['current-change', 'update:currentPage'],
    template: '<div class="el-pagination-stub" />',
  },
}

function mountComp() {
  return mount(DataImport, {
    global: { renderStubDefaultSlot: true, stubs },
  })
}

const findBtn = (wrapper: any, text: string) => {
  const btn = wrapper.findAll('.el-button-stub').find((b: any) => b.text().trim().includes(text))
  expect(btn, `按钮「${text}」`).toBeTruthy()
  return btn!
}

const file = new File(['x'], 'data.xlsx', {
  type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
})

beforeEach(() => {
  vi.clearAllMocks()
  mockGetImportHistory.mockResolvedValue({ items: historyRows, total: 2 })
  mockPreviewImportData.mockResolvedValue(previewResponse)
  mockImportEntities.mockResolvedValue(successResult)
  mockDownloadTemplate.mockResolvedValue(undefined)
})

describe('挂载与导入历史', () => {
  it('onMounted 加载历史并渲染状态/时间列（completed 命中、未知状态透传、created_at 缺省）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(mockGetImportHistory).toHaveBeenCalledWith(1, 10)
    expect(vm.history).toHaveLength(2)
    expect(vm.historyTotal).toBe(2)
    expect(vm.historyLoading).toBe(false)
    expect(vm.previewData).toBeNull()
    expect(vm.importResult).toBeNull()
    const text = wrapper.text()
    expect(text).toContain('数据导入')
    expect(text).toContain('已完成') // statusLabel(completed)
    expect(text).toContain('weird') // statusLabel(未知) 透传
    expect(text).toContain('2024-06-01T10:00:00') // created_at 截断
    expect(wrapper.find('.el-pagination-stub').exists()).toBe(false) // total<=10
  })

  it('loadHistory：空响应 → []；接口失败 → [] 且不抛错', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    mockGetImportHistory.mockResolvedValueOnce({})
    await vm.loadHistory()
    expect(vm.history).toEqual([])
    expect(vm.historyTotal).toBe(0)
    mockGetImportHistory.mockRejectedValueOnce(new Error('net'))
    await vm.loadHistory()
    expect(vm.history).toEqual([])
    expect(vm.historyLoading).toBe(false)
  })

  it('historyTotal>10 时显示分页；翻页触发 loadHistory(新页码)', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.historyTotal = 12
    await nextTick()
    const pagination = wrapper.findComponent({ name: 'ElPagination' })
    expect(pagination.exists()).toBe(true)
    pagination.vm.$emit('update:currentPage', 2)
    pagination.vm.$emit('current-change', 2)
    await flushPromises()
    expect(mockGetImportHistory).toHaveBeenLastCalledWith(2, 10)
    expect(vm.historyPage).toBe(2)
  })
})

describe('模板下载', () => {
  it('下载成功：调用 downloadImportTemplateAndSave(type, 模板)，loading 复位', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.downloadingType = 'project' // 模板按钮 loading 命中态
    await nextTick()
    expect(vm.downloadingType).toBe('project')
    await findBtn(wrapper, '下载模板').trigger('click')
    await flushPromises()
    expect(mockDownloadTemplate).toHaveBeenCalledWith('supported_village', '模板')
    expect(vm.downloadingType).toBe('')
  })

  it('下载失败三分支：message 字符串 / response.detail / 默认文案；非字符串 message 兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    mockDownloadTemplate.mockRejectedValueOnce({ message: '网络错误' })
    await vm.handleDownloadTemplate('project')
    expect(ElMessage.error).toHaveBeenLastCalledWith('网络错误')

    mockDownloadTemplate.mockRejectedValueOnce({ response: { data: { detail: '模板不存在' } } })
    await vm.handleDownloadTemplate('fund')
    expect(ElMessage.error).toHaveBeenLastCalledWith('模板不存在')

    mockDownloadTemplate.mockRejectedValueOnce({})
    await vm.handleDownloadTemplate('school')
    expect(ElMessage.error).toHaveBeenLastCalledWith('模板下载失败，请重试')

    mockDownloadTemplate.mockRejectedValueOnce({ message: 42 })
    await vm.handleDownloadTemplate('supported_village')
    expect(ElMessage.error).toHaveBeenLastCalledWith('模板下载失败')
    expect(vm.downloadingType).toBe('')
  })
})

describe('文件选择 / 预览 / 重置', () => {
  it('handleFileChange/handleFileRemove 切换 selectedFile', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleFileChange({ raw: file })
    expect(vm.selectedFile).toBe(file)
    vm.handleFileRemove()
    expect(vm.selectedFile).toBeNull()
  })

  it('handleReset：uploadRef 有 clearFiles 与无 uploadRef 两侧', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const clearFiles = vi.fn()
    vm.uploadRef = { clearFiles }
    vm.selectedFile = file
    vm.previewData = normalizedPreview
    vm.importResult = { success: true }
    vm.handleReset()
    expect(clearFiles).toHaveBeenCalled()
    expect(vm.selectedFile).toBeNull()
    expect(vm.previewData).toBeNull()
    expect(vm.importResult).toBeNull()

    vm.uploadRef = undefined
    expect(() => vm.handleReset()).not.toThrow()
  })

  it('handlePreview：无文件早退；成功归一化 {total_rows,rows:[{data}]} → {rows,total,columns,invalid_rows}', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handlePreview()
    expect(mockPreviewImportData).not.toHaveBeenCalled()

    vm.handleFileChange({ raw: file })
    await vm.handlePreview()
    expect(mockPreviewImportData).toHaveBeenCalledWith(file, 'supported_village')
    expect(vm.previewData).toEqual(normalizedPreview)
    expect(vm.previewing).toBe(false)
    await nextTick()
    expect(wrapper.text()).toContain('共 12 条数据')
    expect(wrapper.text()).toContain('（仅显示前 10 条，共 12 条）')
  })

  it('handlePreview：total<=10 不显示提示；错误 detail/message/默认三分支', async () => {
    mockPreviewImportData.mockResolvedValueOnce({
      total_rows: 5,
      rows: [{ data: { 村名: '甲村' } }],
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleFileChange({ raw: file })
    await vm.handlePreview()
    await nextTick()
    expect(wrapper.text()).not.toContain('仅显示前 10 条')
    expect(vm.previewData).toEqual({
      rows: [{ 村名: '甲村' }],
      total: 5,
      columns: ['村名'],
      invalid_rows: 0, // 后端未返回 invalid_rows → ?? 0 兜底
    })

    mockPreviewImportData.mockRejectedValueOnce({ response: { data: { detail: '格式错误' } } })
    await vm.handlePreview()
    expect(ElMessage.error).toHaveBeenLastCalledWith('格式错误')

    mockPreviewImportData.mockRejectedValueOnce({ message: '解析失败' })
    await vm.handlePreview()
    expect(ElMessage.error).toHaveBeenLastCalledWith('解析失败')

    mockPreviewImportData.mockRejectedValueOnce({})
    await vm.handlePreview()
    expect(ElMessage.error).toHaveBeenLastCalledWith('数据预览失败，请检查文件格式')
    expect(vm.previewing).toBe(false)
  })

  it('handlePreview 归一化兜底：rows 非数组、行无 data、total_rows 缺省', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleFileChange({ raw: file })

    // rows 非数组 → rawRows=[]，total 走 rawRows.length，invalid_rows 兜底 0
    mockPreviewImportData.mockResolvedValueOnce({ rows: 'not-an-array' })
    await vm.handlePreview()
    expect(vm.previewData).toEqual({ rows: [], total: 0, columns: [], invalid_rows: 0 })

    // 行无 data 字段 → r?.data ?? r 回退到原始行；columns 跳过无 data 行
    mockPreviewImportData.mockResolvedValueOnce({
      rows: [{ data: { 村名: '甲村' } }, { 村名: '乙村' }],
    })
    await vm.handlePreview()
    expect(vm.previewData).toEqual({
      rows: [{ 村名: '甲村' }, { 村名: '乙村' }],
      total: 2, // total_rows 缺省 → rawRows.length
      columns: ['村名'],
      invalid_rows: 0,
    })
  })
})

describe('确认导入', () => {
  it('无文件/无预览时警告且不发请求', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleImport()
    expect(ElMessage.warning).toHaveBeenCalledWith('请先选择文件')
    expect(mockImportEntities).not.toHaveBeenCalled()

    vm.selectedFile = file
    await vm.handleImport()
    expect(ElMessage.warning).toHaveBeenCalledWith('请先预览数据确认无误后再导入')
    expect(mockImportEntities).not.toHaveBeenCalled()
  })

  it('导入成功：success 提示、调用参数（mode/entityType）、清空文件/预览但保留 importResult、刷新历史', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleFileChange({ raw: file })
    vm.previewData = normalizedPreview
    vm.importForm.entityType = 'project'
    vm.importForm.mode = 'full'
    await nextTick() // 等待 disabled 绑定重渲染后再点击
    const before = mockGetImportHistory.mock.calls.length
    await findBtn(wrapper, '确认导入').trigger('click')
    await flushPromises()
    expect(mockImportEntities).toHaveBeenCalledWith(file, 'project', 'full')
    expect(ElMessage.success).toHaveBeenCalledWith('导入完成：8 条成功')
    expect(mockGetImportHistory.mock.calls.length).toBe(before + 1) // loadHistory
    expect(vm.importResult).toEqual(successResult) // 关键：结果保留展示，不再被 handleReset 清掉
    expect(vm.selectedFile).toBeNull()
    expect(vm.previewData).toBeNull()
    expect(vm.importing).toBe(false)
  })

  it('导入失败结果：errors?.length 两侧文案', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.selectedFile = file
    vm.previewData = normalizedPreview
    mockImportEntities.mockResolvedValueOnce({ success: false, errors: [] })
    await vm.handleImport()
    expect(ElMessage.error).toHaveBeenLastCalledWith('导入失败：0 个错误')

    vm.selectedFile = file // handleImport 已清空文件与预览，重新设置
    vm.previewData = normalizedPreview
    mockImportEntities.mockResolvedValueOnce({
      success: false,
      errors: [{ row_number: 1 }, { row_number: 2 }, { row_number: 3 }],
    })
    await vm.handleImport()
    expect(ElMessage.error).toHaveBeenLastCalledWith('导入失败：3 个错误')
  })

  it('导入接口异常：detail/message/默认三分支', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    vm.selectedFile = file
    vm.previewData = normalizedPreview
    mockImportEntities.mockRejectedValueOnce({ response: { data: { detail: '服务繁忙' } } })
    await vm.handleImport()
    expect(ElMessage.error).toHaveBeenLastCalledWith('服务繁忙')

    vm.selectedFile = file
    vm.previewData = normalizedPreview
    mockImportEntities.mockRejectedValueOnce({ message: '超时' })
    await vm.handleImport()
    expect(ElMessage.error).toHaveBeenLastCalledWith('超时')

    vm.selectedFile = file
    vm.previewData = normalizedPreview
    mockImportEntities.mockRejectedValueOnce({})
    await vm.handleImport()
    expect(ElMessage.error).toHaveBeenLastCalledWith('导入失败')
    expect(vm.importing).toBe(false)
  })

  it('导入结果区渲染：success 真/假侧、skipped/failed/errors 有/无侧、field_name 兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // success 且各项非零 → 全部渲染
    vm.importResult = {
      success: true,
      total_rows: 10,
      success_rows: 8,
      failed_rows: 1,
      skipped_rows: 1,
      errors: [
        { row_number: 3, field_name: '村名', message: '为空' },
        { row_number: 5, field_name: '县市', message: '' },
      ],
    }
    await nextTick()
    let text = wrapper.text()
    expect(text).toContain('导入成功')
    expect(text).toContain('总 10 条，成功 8 条')
    expect(text).toContain('，跳过 1 条')
    expect(text).toContain('，失败 1 条')
    expect(text).toContain('行3: 为空')
    expect(text).toContain('行5: 县市') // message 空 → field_name

    // success=false → 失败标题
    vm.importResult = { success: false, total_rows: 3, success_rows: 0, failed_rows: 3, skipped_rows: 0 }
    await nextTick()
    text = wrapper.text()
    expect(text).toContain('导入失败')

    // 全零 → skipped/failed/errors 分支不渲染
    vm.importResult = { success: true, total_rows: 5, success_rows: 5, failed_rows: 0, skipped_rows: 0 }
    await nextTick()
    text = wrapper.text()
    expect(text).toContain('总 5 条，成功 5 条')
    expect(text).not.toContain('，跳过')
    expect(text).not.toContain('，失败')
  })
})

describe('状态映射工具', () => {
  it('statusTagType / statusLabel 直接调用', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.statusTagType('completed')).toBe('success')
    expect(vm.statusLabel('completed')).toBe('已完成')
    expect(vm.statusTagType('unknown')).toBe('info')
    expect(vm.statusLabel('unknown')).toBe('unknown')
  })

  it('表单 v-model：导入类型下拉与导入模式单选项 update:modelValue 同步', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const select = wrapper.findComponent({ name: 'ElSelect' })
    select.vm.$emit('update:modelValue', 'fund')
    expect(vm.importForm.entityType).toBe('fund')
    const radioGroup = wrapper.findComponent({ name: 'ElRadioGroup' })
    radioGroup.vm.$emit('update:modelValue', 'full')
    expect(vm.importForm.mode).toBe('full')
  })
})
