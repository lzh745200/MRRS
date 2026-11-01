/**
 * views/dataPackage/List.vue 覆盖率攻坚（四指标 100%）
 *
 * 覆盖：onMounted 加载列表/组织、loadPackages 成功失败、resetFilters、
 * getStatusLabel/getStatusType/getDataTypeLabel 已知未知、formatFileSize 四分支、
 * formatDate 两分支、handlePreview 成功失败、handleConfirmImport 全分支
 * （确认/取消/失败 message 与兜底）、handleDownload 成功失败、handleDelete 全分支、
 * handleExportSuccess/handleImportSuccess、分页 size/current change、筛选 v-model 与查询重置、
 * 预览对话框 tabs/列渲染与空态。
 *
 * 方案：真实 Pinia + 真实 store（dataPackage/organization），mock 底层 '@/api/request'
 * 按 URL 路由；mock element-plus；stub ExportDialog/ImportDialog 与 el 组件。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'

const { ElMessage, confirmMock, mockGet, mockPost, mockApiRequest, logError } = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  confirmMock: vi.fn(),
  mockGet: vi.fn(),
  mockPost: vi.fn(),
  mockApiRequest: vi.fn(),
  logError: vi.fn(),
}))

vi.mock('element-plus', () => ({
  ElMessage,
  ElMessageBox: { confirm: confirmMock },
}))

vi.mock('@/api/request', () => ({
  get: (...args: any[]) => mockGet(...args),
  post: (...args: any[]) => mockPost(...args),
  put: vi.fn(),
  del: vi.fn(),
  apiRequest: (...args: any[]) => mockApiRequest(...args),
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

vi.mock('@/utils/logger', () => ({
  logger: { error: logError, warn: vi.fn(), info: vi.fn(), debug: vi.fn() },
}))

import List from '@/views/dataPackage/List.vue'
import { useOrganizationStore } from '@/stores/organization'

// ── 样本数据 ──
const pkg1 = {
  id: 1,
  package_code: 'PKG-001',
  file_name: '数据包1.zip',
  file_size: 512,
  record_count: 100,
  status: 'validated',
  created_at: '2024-01-01T01:00:00',
}
const pkg2 = {
  id: 2,
  package_code: 'PKG-002',
  file_name: '数据包2.zip',
  file_size: 2048,
  record_count: 0,
  status: 'pending',
  created_at: '2024-02-01T01:00:00',
}
const pkg3 = {
  id: 3,
  package_code: 'PKG-003',
  file_name: '数据包3.zip',
  file_size: 5 * 1024 * 1024,
  status: 'imported',
}
const pkg4 = {
  id: 4,
  package_code: 'PKG-004',
  file_name: '数据包4.zip',
  status: 'weird',
  created_at: '2024-03-01T01:00:00',
}

const previewData = [
  { data_type: 'villages', total: 2, columns: ['id', 'name'], sample: [{ id: 1, name: '甲村' }] },
  { data_type: 'mystery', total: 0, columns: [], sample: [] },
]

// el-table-column 插槽样本行（4 行覆盖 formatFileSize/状态/日期全部分支）
const rowA = pkg1
const rowB = pkg2
const rowC = pkg3
const rowD = pkg4

function defaultApiImpl(url: string): Promise<any> {
  if (url === '/data-packages') return Promise.resolve({ items: [pkg1, pkg2, pkg3, pkg4], total: 4 })
  if (url === '/data-packages/1/preview') return Promise.resolve(previewData)
  if (url === '/organizations/my') return Promise.resolve({ code: 200, data: { id: 5, name: '单位甲' } })
  return Promise.resolve({})
}

const stubs = {
  'el-card': { name: 'ElCard', template: '<div class="el-card-stub"><slot name="header" /><slot /></div>' },
  'el-form': { name: 'ElForm', template: '<div class="el-form-stub"><slot /></div>' },
  'el-form-item': { name: 'ElFormItem', template: '<div class="el-form-item-stub"><slot /></div>' },
  'el-select': {
    name: 'ElSelect',
    props: ['modelValue'],
    template: '<div class="el-select-stub"><slot /></div>',
    emits: ['update:modelValue', 'change'],
  },
  'el-option': { name: 'ElOption', template: '<div />' },
  'el-button': { name: 'ElButton', template: '<button class="el-button-stub" @click="$emit(\'click\')"><slot /></button>', emits: ['click'] },
  'ExportEncryptedDialog': { name: 'ExportEncryptedDialog', props: ['modelValue'], emits: ['update:modelValue', 'success'], template: '<div class="eed-stub" />' },
  'ImportEncryptedDialog': { name: 'ImportEncryptedDialog', props: ['modelValue'], emits: ['update:modelValue', 'success'], template: '<div class="ied-stub" />' },
  'el-icon': { name: 'ElIcon', template: '<span class="el-icon-stub"><slot /></span>' },
  'el-table': {
    name: 'ElTable',
    template: '<div class="el-table-stub"><slot /></div>',
    props: ['data'],
  },
  'el-table-column': {
    name: 'ElTableColumn',
    props: ['prop', 'label'],
    template:
      '<div class="el-table-column-stub" :label="label"><slot :row="rowA" /><slot :row="rowB" /><slot :row="rowC" /><slot :row="rowD" /><span class="col-prop">{{ prop }}:{{ rowA[prop] }}</span></div>',
    data() {
      return { rowA, rowB, rowC, rowD }
    },
  },
  'el-tag': { name: 'ElTag', template: '<span class="el-tag-stub"><slot /></span>' },
  'el-dialog': {
    name: 'ElDialog',
    props: ['modelValue', 'title'],
    template: '<div class="el-dialog-stub"><slot /></div>',
    emits: ['update:modelValue', 'close'],
  },
  'el-tabs': { name: 'ElTabs', template: '<div class="el-tabs-stub"><slot /></div>' },
  'el-tab-pane': {
    name: 'ElTabPane',
    props: ['label'],
    template: '<div class="el-tab-pane-stub">{{ label }}<slot /></div>',
  },
  'el-empty': {
    name: 'ElEmpty',
    props: ['description'],
    template: '<div class="el-empty-stub">{{ description }}</div>',
  },
  'el-pagination': {
    name: 'ElPagination',
    template: '<div class="el-pagination-stub" />',
    emits: ['update:currentPage', 'update:pageSize', 'size-change', 'current-change'],
  },
  ExportDialog: {
    name: 'ExportDialog',
    props: ['modelValue'],
    template: '<div class="export-dialog-stub" />',
    emits: ['update:modelValue'],
  },
  ImportDialog: {
    name: 'ImportDialog',
    props: ['modelValue'],
    template: '<div class="import-dialog-stub" />',
    emits: ['update:modelValue'],
  },
  ExportEncryptedDialog: {
    name: 'ExportEncryptedDialog',
    props: ['modelValue'],
    template: '<div />',
    emits: ['update:modelValue'],
  },
  ImportEncryptedDialog: {
    name: 'ImportEncryptedDialog',
    props: ['modelValue'],
    template: '<div />',
    emits: ['update:modelValue'],
  },
}

function mountComp() {
  const pinia = createPinia()
  setActivePinia(pinia)
  return mount(List, {
    global: { plugins: [pinia], renderStubDefaultSlot: true, stubs },
  })
}

async function clickBtn(wrapper: any, text: string, index = 0) {
  const btns = wrapper.findAll('.el-button-stub').filter((b: any) => b.text().trim().includes(text))
  const all = wrapper.findAll('.el-button-stub').map((b: any) => b.text().trim())
  expect(btns.length, `按钮「${text}」; 实际=[${all.join(' | ')}]`).toBeGreaterThan(index)
  await btns[index].trigger('click')
  await flushPromises()
}

beforeEach(() => {
  vi.resetAllMocks()
  mockGet.mockImplementation(defaultApiImpl)
  // 两阶段导入：confirm 之前先调 dry-run，演练报告带「新增/覆盖/拒绝」计数
  mockPost.mockImplementation((url: string) => {
    if (typeof url === 'string' && url.endsWith('/dry-run')) {
      return Promise.resolve({
        success: true,
        total_records: 10,
        total_to_create: 6,
        total_to_update: 0,
        total_rejected: 4,
      })
    }
    return Promise.resolve({ success: true })
  })
  mockApiRequest.mockResolvedValue({})
  confirmMock.mockResolvedValue('confirm')
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('挂载与列表', () => {
  it('onMounted 加载列表与组织；表格 4 行样本渲染全部列分支', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(mockGet).toHaveBeenCalledWith('/data-packages', expect.objectContaining({ page: 1, page_size: 20 }))
    expect(vm.packages.length).toBe(4)
    expect(vm.total).toBe(4)
    expect(vm.currentOrgId).toBe(5)
    const text = wrapper.text()
    expect(text).toContain('数据包管理')
    expect(text).toContain('PKG-001')
    expect(text).toContain('512 B') // formatFileSize <1024
    expect(text).toContain('2.00 KB') // <1MB
    expect(text).toContain('5.00 MB') // >=1MB
    expect(text).toContain('-') // file_size 缺失
    expect(text).toContain('已验证') // validated → success
    expect(text).toContain('待处理') // pending → warning
    expect(text).toContain('已导入') // imported → primary
    expect(text).toContain('weird') // 未知回退
    wrapper.unmount()
  })

  it('loadPackages 失败 → 错误提示；fetchMyOrganization 失败 → logger 记录', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    mockGet.mockImplementation((url: string) => {
      if (url === '/data-packages') return Promise.reject(new Error('boom'))
      return defaultApiImpl(url)
    })
    await vm.loadPackages()
    expect(ElMessage.error).toHaveBeenCalledWith('加载数据包列表失败')
    expect(vm.loading).toBe(false)
    wrapper.unmount()

    // 组织加载失败 → onMounted .catch → logger.error
    const pinia = createPinia()
    setActivePinia(pinia)
    const orgStore = useOrganizationStore()
    vi.spyOn(orgStore, 'fetchMyOrganization').mockRejectedValue(new Error('org down'))
    const wrapper2 = mount(List, { global: { plugins: [pinia], renderStubDefaultSlot: true, stubs } })
    await flushPromises()
    expect(logError).toHaveBeenCalledWith('[DataPackage/List] 加载组织失败', expect.any(Error))
    wrapper2.unmount()
  })

  it('空列表 → 表格无数据且 total=0', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/data-packages') return Promise.resolve({ items: [], total: 0 })
      return defaultApiImpl(url)
    })
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).packages.length).toBe(0)
    wrapper.unmount()
  })

  it('筛选：状态 v-model + 查询携带 status；重置清空并重新加载', async () => {
    const wrapper = mountComp()
    await flushPromises()
    mockGet.mockClear()
    const select = wrapper.findComponent({ name: 'ElSelect' })
    select.vm.$emit('update:modelValue', 'pending')
    await nextTick()
    await clickBtn(wrapper, '查询')
    const call = mockGet.mock.calls.find((c: any) => c[0] === '/data-packages')
    expect(call[1]).toMatchObject({ status: 'pending' })

    // 重置 → status 清空、page=1、重新加载
    const vm = wrapper.vm as any
    vm.pagination.page = 3
    mockGet.mockClear()
    await clickBtn(wrapper, '重置')
    expect(vm.filters.status).toBe('')
    expect(vm.pagination.page).toBe(1)
    const resetCall = mockGet.mock.calls.find((c: any) => c[0] === '/data-packages')
    expect(resetCall[1].status).toBeUndefined()
    wrapper.unmount()
  })

  it('分页：size-change / current-change 触发加载', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const pager = wrapper.findComponent({ name: 'ElPagination' })
    pager.vm.$emit('update:currentPage', 2)
    pager.vm.$emit('update:pageSize', 50)
    await nextTick()
    const vm = wrapper.vm as any
    expect(vm.pagination.page).toBe(2)
    expect(vm.pagination.pageSize).toBe(50)
    mockGet.mockClear()
    pager.vm.$emit('size-change', 50)
    await flushPromises()
    pager.vm.$emit('current-change', 3)
    await flushPromises()
    expect(mockGet.mock.calls.filter((c: any) => c[0] === '/data-packages').length).toBe(2)
    wrapper.unmount()
  })
})

describe('列表操作', () => {
  it('handlePreview 成功 → 打开预览对话框并渲染 tabs/列；失败 → 提示', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await clickBtn(wrapper, '预览', 0) // pkg1
    expect(mockGet).toHaveBeenCalledWith('/data-packages/1/preview')
    expect(vm.previewData).toEqual(previewData)
    expect(vm.showPreviewDialog).toBe(true)
    await nextTick()
    const labels = wrapper.findAll('.el-tab-pane-stub').map((t: any) => t.text())
    expect(labels.some((l: string) => l.includes('村庄数据 (2)'))).toBe(true)
    expect(labels.some((l: string) => l.includes('mystery (0)'))).toBe(true)
    wrapper.unmount()

    mockGet.mockImplementation((url: string) => {
      if (url === '/data-packages/1/preview') return Promise.reject(new Error('down'))
      return defaultApiImpl(url)
    })
    const wrapper2 = mountComp()
    await flushPromises()
    await clickBtn(wrapper2, '预览', 0)
    expect(ElMessage.error).toHaveBeenCalledWith('加载预览数据失败')
    wrapper2.unmount()
  })

  it('预览无数据 → el-empty 渲染「暂无预览数据」', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/data-packages/1/preview') return Promise.resolve([])
      return defaultApiImpl(url)
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.previewData = []
    vm.showPreviewDialog = true
    await nextTick()
    const empties = wrapper.findAll('.el-empty-stub')
    expect(empties.some((e: any) => e.text().includes('暂无预览数据'))).toBe(true)
    wrapper.unmount()
  })

  it('handleConfirmImport：确认 → 导入成功 + 回第 1 页刷新；取消静默；失败提示', async () => {
    pkg1.status = 'validated'
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.pagination.page = 2
    mockPost.mockClear()
    expect(vm.packages.map((p: any) => p.status)).toEqual(['validated', 'pending', 'imported', 'weird'])
    await clickBtn(wrapper, '确认导入', 0) // pkg1 validated
    // 两阶段导入：先 dry-run 拿到差异摘要，再弹确认框（文案含计数）
    expect(mockPost).toHaveBeenCalledWith('/data-packages/1/dry-run', {})
    expect(confirmMock).toHaveBeenCalledWith(
      expect.stringContaining('本次将新增 6 条、覆盖 0 条、拒绝 4 条'),
      '确认导入',
      expect.anything(),
    )
    expect(mockPost).toHaveBeenCalledWith('/data-packages/1/confirm', {})
    expect(ElMessage.success).toHaveBeenCalledWith('导入成功')
    expect(vm.pagination.page).toBe(1)

    // 取消 → 静默
    confirmMock.mockRejectedValueOnce('cancel')
    await vm.handleConfirmImport(pkg1 as any)
    expect(ElMessage.error).not.toHaveBeenCalledWith('导入失败')

    // 失败 → error.message
    mockPost.mockRejectedValueOnce(new Error('冲突'))
    await vm.handleConfirmImport(pkg1 as any)
    expect(ElMessage.error).toHaveBeenCalledWith('冲突')
    // 失败无 message → 兜底
    mockPost.mockRejectedValueOnce({})
    await vm.handleConfirmImport(pkg1 as any)
    expect(ElMessage.error).toHaveBeenCalledWith('导入失败')
    wrapper.unmount()
  })

  it('handleDownload 成功与失败', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await clickBtn(wrapper, '下载', 0)
    expect(mockApiRequest).toHaveBeenCalledWith(
      expect.objectContaining({ method: 'GET', url: '/data-packages/1/download', responseType: 'blob' })
    )
    mockApiRequest.mockRejectedValueOnce(new Error('net'))
    await vm.handleDownload(pkg1 as any)
    expect(ElMessage.error).toHaveBeenCalledWith('下载失败')
    wrapper.unmount()
  })

  it('handleDelete：确认 → 删除成功 + 刷新；取消静默；失败 message 与兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.pagination.page = 2
    mockApiRequest.mockClear()
    await clickBtn(wrapper, '删除', 0)
    expect(confirmMock).toHaveBeenCalledWith('确定要删除此数据包吗？', '删除确认', expect.anything())
    expect(mockApiRequest).toHaveBeenCalledWith(
      expect.objectContaining({ method: 'DELETE', url: '/data-packages/1' })
    )
    expect(ElMessage.success).toHaveBeenCalledWith('删除成功')
    expect(vm.pagination.page).toBe(1)

    confirmMock.mockRejectedValueOnce('cancel')
    await vm.handleDelete(pkg1 as any)
    expect(ElMessage.error).not.toHaveBeenCalled()

    mockApiRequest.mockRejectedValueOnce(new Error('拒绝'))
    await vm.handleDelete(pkg1 as any)
    expect(ElMessage.error).toHaveBeenCalledWith('拒绝')
    mockApiRequest.mockRejectedValueOnce({})
    await vm.handleDelete(pkg1 as any)
    expect(ElMessage.error).toHaveBeenCalledWith('删除失败')
    wrapper.unmount()
  })
})

describe('导出导入对话框', () => {
  it('打开导出/导入对话框按钮；handleExportSuccess 刷新；handleImportSuccess 关闭并刷新', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await clickBtn(wrapper, '导出数据')
    expect(vm.showExportDialog).toBe(true)
    await clickBtn(wrapper, '导入数据')
    expect(vm.showImportDialog).toBe(true)

    vm.pagination.page = 3
    mockGet.mockClear()
    vm.handleExportSuccess()
    expect(vm.pagination.page).toBe(1)
    expect(mockGet.mock.calls.some((c: any) => c[0] === '/data-packages')).toBe(true)

    vm.pagination.page = 2
    mockGet.mockClear()
    vm.handleImportSuccess()
    expect(vm.showImportDialog).toBe(false)
    expect(vm.pagination.page).toBe(1)
    expect(mockGet.mock.calls.some((c: any) => c[0] === '/data-packages')).toBe(true)

    // 三个对话框 v-model 内联关闭处理器（ExportDialog/ImportDialog/el-dialog）
    vm.showExportDialog = true
    vm.showImportDialog = true
    vm.showPreviewDialog = true
    await nextTick()
    wrapper.findComponent({ name: 'ExportDialog' }).vm.$emit('update:modelValue', false)
    wrapper.findComponent({ name: 'ImportDialog' }).vm.$emit('update:modelValue', false)
    wrapper.findComponent({ name: 'ElDialog' }).vm.$emit('update:modelValue', false)
    await nextTick()
    expect(vm.showExportDialog).toBe(false)
    expect(vm.showImportDialog).toBe(false)
    expect(vm.showPreviewDialog).toBe(false)
    wrapper.unmount()
  })
})

describe('辅助函数', () => {
  it('getStatusLabel/getStatusType/getDataTypeLabel/formatFileSize/formatDate 全分支', () => {
    const wrapper = mountComp()
    const vm = wrapper.vm as any
    expect(vm.getStatusLabel('pending')).toBe('待处理')
    expect(vm.getStatusLabel('unknown')).toBe('unknown')
    expect(vm.getStatusType('validated')).toBe('success')
    expect(vm.getStatusType('pending')).toBe('warning')
    expect(vm.getStatusType('imported')).toBe('primary')
    expect(vm.getStatusType('failed')).toBe('danger')
    expect(vm.getStatusType('cancelled')).toBe('info')
    expect(vm.getStatusType('weird')).toBe('info')
    expect(vm.getDataTypeLabel('villages')).toBe('村庄数据')
    expect(vm.getDataTypeLabel('projects')).toBe('项目数据')
    expect(vm.getDataTypeLabel('funds')).toBe('资金数据')
    expect(vm.getDataTypeLabel('schools')).toBe('学校数据')
    expect(vm.getDataTypeLabel('mystery')).toBe('mystery')
    expect(vm.formatFileSize(undefined)).toBe('-')
    expect(vm.formatFileSize(0)).toBe('-')
    expect(vm.formatFileSize(500)).toBe('500 B')
    expect(vm.formatFileSize(2048)).toBe('2.00 KB')
    expect(vm.formatFileSize(5 * 1024 * 1024)).toBe('5.00 MB')
    expect(vm.formatDate(undefined)).toBe('-')
    expect(vm.formatDate('2024-01-01T00:00:00')).toContain('2024')
    wrapper.unmount()
  })


  it('加密导出/导入对话框 v-model 事件处理器', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // 点击加密导出/导入按钮(行 15/19 事件箭头)
    await clickBtn(wrapper, '加密导出')
    expect(vm.showEncryptedExportDialog).toBe(true)
    await clickBtn(wrapper, '加密导入')
    expect(vm.showEncryptedImportDialog).toBe(true)
    await wrapper.vm.$nextTick()
    // 触发加密对话框 update:modelValue(ExportEncryptedDialog/ImportEncryptedDialog 的 v-model)
    wrapper.findComponent({ name: 'ExportEncryptedDialog' }).vm.$emit('update:modelValue', false)
    expect(vm.showEncryptedExportDialog).toBe(false)
    vm.showEncryptedImportDialog = true
    await wrapper.vm.$nextTick()
    wrapper.findComponent({ name: 'ImportEncryptedDialog' }).vm.$emit('update:modelValue', false)
    expect(vm.showEncryptedImportDialog).toBe(false)
    wrapper.unmount()
  })
})


