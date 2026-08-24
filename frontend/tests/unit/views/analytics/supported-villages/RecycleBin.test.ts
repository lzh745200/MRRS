/**
 * views/analytics/supported-villages/List.vue 回收站行为测试 (T04)
 * 覆盖：正常/回收站双模式操作列切换、恢复回环、彻底删除（预览→警告→密码→调用）、取消分支。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const {
  ElMessage,
  confirmMock,
  promptMock,
  alertMock,
  mockGet,
  mockPost,
  mockPut,
  mockDel,
  getSupportedVillagesMock,
  restoreMock,
  previewPurgeMock,
  purgeMock,
  exportSupportedVillagesMock,
  importSupportedVillagesMock,
  downloadImportTemplateMock,
  pushSafe,
} = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  confirmMock: vi.fn(),
  promptMock: vi.fn(),
  alertMock: vi.fn(),
  mockGet: vi.fn(),
  mockPost: vi.fn(),
  mockPut: vi.fn(),
  mockDel: vi.fn(),
  getSupportedVillagesMock: vi.fn(),
  restoreMock: vi.fn(),
  previewPurgeMock: vi.fn(),
  purgeMock: vi.fn(),
  exportSupportedVillagesMock: vi.fn(),
  importSupportedVillagesMock: vi.fn(),
  downloadImportTemplateMock: vi.fn(),
  pushSafe: vi.fn(),
}))

vi.mock('element-plus', () => ({
  ElMessage,
  ElMessageBox: { confirm: confirmMock, prompt: promptMock, alert: alertMock },
}))

vi.mock('@/api/request', () => ({
  default: { get: mockGet, post: mockPost },
  get: mockGet,
  post: mockPost,
  put: mockPut,
  del: mockDel,
  apiRequest: vi.fn(),
  getCsrfToken: vi.fn(() => Promise.resolve('test-csrf')),
}))

vi.mock('@/api/supportedVillage', () => ({
  getSupportedVillages: getSupportedVillagesMock,
  deleteSupportedVillage: mockDel,
  batchDeleteSupportedVillages: mockPost,
  createSupportedVillage: mockPost,
  updateSupportedVillage: mockPut,
  saveTransitionFunding: mockPost,
  importSupportedVillages: importSupportedVillagesMock,
  exportSupportedVillages: exportSupportedVillagesMock,
  downloadImportTemplate: downloadImportTemplateMock,
  getFilterOptions: vi.fn(() =>
    Promise.resolve({ data: { departments: [], supportUnits: [], counties: [] } })
  ),
  restoreSupportedVillage: restoreMock,
  previewPurgeSupportedVillage: previewPurgeMock,
  purgeSupportedVillage: purgeMock,
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    user: { role: 'admin', id: 1 },
    canViewDeleted: true,
  }),
}))

vi.mock('@/composables/useRouterSafe', () => ({
  useRouterSafe: () => ({ pushSafe }),
}))

import SupportedVillageList from '@/views/analytics/supported-villages/List.vue'

const rows = [
  { id: 11, villageName: '软删村A', isDeleted: true },
  { id: 12, villageName: '软删村B', isDeleted: true },
]

function mountList() {
  return mount(SupportedVillageList)
}

beforeEach(() => {
  vi.clearAllMocks()
  getSupportedVillagesMock.mockResolvedValue({
    data: { items: rows, total: rows.length },
  })
})

async function openRecycleBin(wrapper: any) {
  // 切换回收站开关（el-switch 已 stub，直接改组件状态并触发 change）
  const vm = wrapper.vm as any
  vm.showDeletedOnly = true
  await vm.handleToggleDeleted?.(true)
  await flushPromises()
}

describe('帮扶村列表 回收站操作', () => {
  it('回收站开关切换后重新加载列表（include_deleted）', async () => {
    const wrapper = mountList()
    await flushPromises()
    const callsBefore = getSupportedVillagesMock.mock.calls.length
    await openRecycleBin(wrapper)
    expect(getSupportedVillagesMock.mock.calls.length).toBeGreaterThan(callsBefore)
    const lastCall = getSupportedVillagesMock.mock.calls.at(-1)?.[0] || {}
    expect(lastCall.include_deleted).toBe(true)
    wrapper.unmount()
  })

  it('恢复：确认后调用恢复接口并刷新列表', async () => {
    confirmMock.mockResolvedValue({ value: undefined })
    restoreMock.mockResolvedValue({})
    const wrapper = mountList()
    await flushPromises()

    const callsBefore = getSupportedVillagesMock.mock.calls.length
    const vm = wrapper.vm as any
    await vm.handleRestore({ id: 11, villageName: '软删村A' })
    await flushPromises()

    expect(confirmMock).toHaveBeenCalled()
    expect(restoreMock).toHaveBeenCalledWith(11)
    expect(getSupportedVillagesMock.mock.calls.length).toBeGreaterThan(callsBefore)
    expect(ElMessage.success).toHaveBeenCalledWith('恢复成功')
    wrapper.unmount()
  })

  it('恢复：用户取消则不调用接口', async () => {
    confirmMock.mockRejectedValue('cancel')
    const wrapper = mountList()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleRestore({ id: 11, villageName: '软删村A' })
    await flushPromises()

    expect(restoreMock).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('彻底删除：预览级联 → 警告确认 → 密码输入 → 调用接口带密码', async () => {
    previewPurgeMock.mockResolvedValue({
      data: {
        id: 11,
        total_references: 3,
        details: { projects: 2, funds: 1 },
      },
    })
    confirmMock.mockResolvedValue({ value: undefined })
    promptMock.mockResolvedValue({ value: 'pw-123' })
    purgeMock.mockResolvedValue({ data: { deleted_records: 4 } })

    const wrapper = mountList()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handlePurge({ id: 11, villageName: '软删村A' })
    await flushPromises()

    expect(previewPurgeMock).toHaveBeenCalledWith(11)
    expect(confirmMock).toHaveBeenCalledTimes(1)
    expect(promptMock).toHaveBeenCalledTimes(1)
    expect(purgeMock).toHaveBeenCalledWith(11, 'pw-123')
    expect(ElMessage.success).toHaveBeenCalled()
    wrapper.unmount()
  })

  it('彻底删除：警告确认取消则不调用接口', async () => {
    previewPurgeMock.mockResolvedValue({
      data: { id: 11, total_references: 0, details: {} },
    })
    confirmMock.mockRejectedValue('cancel')

    const wrapper = mountList()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handlePurge({ id: 11, villageName: '软删村A' })
    await flushPromises()

    expect(purgeMock).not.toHaveBeenCalled()
    expect(promptMock).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('彻底删除：密码弹窗取消则不调用接口', async () => {
    previewPurgeMock.mockResolvedValue({
      data: { id: 11, total_references: 0, details: {} },
    })
    confirmMock.mockResolvedValue({ value: undefined })
    promptMock.mockRejectedValue('cancel')

    const wrapper = mountList()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handlePurge({ id: 11, villageName: '软删村A' })
    await flushPromises()

    expect(purgeMock).not.toHaveBeenCalled()
    wrapper.unmount()
  })
})

describe('回收站覆盖率补齐（List.vue 遗留处理器）', () => {
  beforeEach(() => {
    // 本组用例自管理 post 行为，避免跨用例残留实现/队列
    mockPost.mockReset()
    getSupportedVillagesMock.mockResolvedValue({
      data: { items: rows, total: rows.length },
    })
  })

  it('彻底删除：预览失败不阻断 + API 失败走错误提示', async () => {
    previewPurgeMock.mockRejectedValue(new Error('preview down'))
    confirmMock.mockResolvedValue({ value: undefined })
    promptMock.mockResolvedValue({ value: 'pw' })
    purgeMock.mockRejectedValue(new Error('api down'))

    const wrapper = mountList()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handlePurge({ id: 11, villageName: '软删村A' })
    await flushPromises()

    expect(purgeMock).toHaveBeenCalledWith(11, 'pw')
    expect(ElMessage.error).toHaveBeenCalledWith('彻底删除失败')
    expect(vm.loading).toBe(false)
    wrapper.unmount()
  })

  it('handleSelectionChange 记录选中行', async () => {
    const wrapper = mountList()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleSelectionChange([{ id: 1 }, { id: 2 }])
    expect(vm.selectedRows).toHaveLength(2)
    wrapper.unmount()
  })

  it('批量删除：密码确认 → 调用接口 → 乐观移除并刷新', async () => {
    promptMock.mockResolvedValue({ value: 'pw-batch' })
    mockPost.mockResolvedValue({ message: '已删除 2 条记录' })
    const wrapper = mountList()
    await flushPromises()
    const callsBefore = getSupportedVillagesMock.mock.calls.length
    const vm = wrapper.vm as any
    vm.handleSelectionChange([{ id: 11 }, { id: 12 }])
    await vm.handleBatchDelete()
    await flushPromises()
    await flushPromises()

    expect(mockPost).toHaveBeenCalledTimes(1)
    expect(mockPost).toHaveBeenCalledWith([11, 12], 'pw-batch')
    expect(getSupportedVillagesMock.mock.calls.length).toBeGreaterThan(callsBefore)
    expect(vm.batchDeleting).toBe(false)
    wrapper.unmount()
  })

  it('批量删除：密码取消 → 不调用接口', async () => {
    promptMock.mockRejectedValue('cancel')
    const wrapper = mountList()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleSelectionChange([{ id: 11 }])
    await vm.handleBatchDelete()
    await flushPromises()
    expect(mockPost).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('批量删除：接口失败 → 错误提示并复位 loading', async () => {
    promptMock.mockResolvedValue({ value: 'pw' })
    mockPost.mockRejectedValue(new Error('down'))
    const wrapper = mountList()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleSelectionChange([{ id: 11 }])
    await vm.handleBatchDelete()
    await flushPromises()
    expect(ElMessage.error).toHaveBeenCalledWith('批量删除失败')
    expect(vm.batchDeleting).toBe(false)
    wrapper.unmount()
  })

  it('表单提交：创建成功（含过渡资金）→ 关闭弹窗并刷新', async () => {
    mockPost.mockImplementation((url: any) => {
      const u = String(url)
      if (u === '/supported-villages') return Promise.resolve({ data: { id: 99 } })
      if (u.includes('/transition-funding')) return Promise.resolve({})
      return Promise.resolve({ data: {} })
    })
    const wrapper = mountList()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.dialogMode = 'create'
    vm.currentVillage = null
    vm.dialogVisible = true
    await vm.handleFormSubmit({
      villageName: '新村庄',
      _transitionFundingItems: [{ year: 2026 }],
    } as any)
    await flushPromises()
    await flushPromises()

    expect(vm.dialogVisible).toBe(false)
    wrapper.unmount()
  })

  it('表单提交：编辑成功 / 创建失败 / 编辑失败三分支', async () => {
    const wrapper = mountList()
    await flushPromises()
    const vm = wrapper.vm as any

    mockPut.mockResolvedValueOnce({})
    vm.dialogMode = 'edit'
    vm.currentVillage = { id: 11, villageName: 'X' } as any
    await vm.handleFormSubmit({ villageName: 'X2' } as any)

    mockPost.mockRejectedValueOnce(new Error('dup'))
    vm.dialogMode = 'create'
    vm.currentVillage = null
    await vm.handleFormSubmit({ villageName: 'Y' } as any)
    expect(ElMessage.error).toHaveBeenCalledWith('创建失败')

    mockPut.mockRejectedValueOnce(new Error('lock'))
    vm.dialogMode = 'edit'
    vm.currentVillage = { id: 12, villageName: 'Z' } as any
    await vm.handleFormSubmit({ villageName: 'Z2' } as any)
    expect(ElMessage.error).toHaveBeenCalledWith('更新失败')
    wrapper.unmount()
  })

  it('导出：成功静默 / 失败提示', async () => {
    exportSupportedVillagesMock.mockResolvedValue(undefined)
    const wrapper = mountList()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleExport()
    expect(vm.exporting).toBe(false)

    exportSupportedVillagesMock.mockRejectedValueOnce(new Error('offline'))
    await vm.handleExport()
    expect(ElMessage.error).toHaveBeenCalledWith('导出功能需要后端支持，请先启动后端服务')
    wrapper.unmount()
  })

  it('导入：文件选择 → 成功无错误 / 成功含错误明细 / 接口失败', async () => {
    const inputs: HTMLInputElement[] = []
    const orig = document.createElement.bind(document)
    const spy = vi.spyOn(document, 'createElement').mockImplementation((tag: any) => {
      const el = orig(tag)
      if (String(tag).toLowerCase() === 'input') inputs.push(el as HTMLInputElement)
      return el
    })
    const wrapper = mountList()
    await flushPromises()
    const vm = wrapper.vm as any

    importSupportedVillagesMock.mockResolvedValueOnce({ imported: 3, failed: 0 })
    vm.handleImport()
    const fileOk = new File(['x'], 'a.xlsx')
    Object.defineProperty(inputs[0], 'files', { value: [fileOk], configurable: true })
    ;(inputs[0] as any).onchange({ target: { files: [fileOk] } })
    await flushPromises()
    expect(ElMessage.success).toHaveBeenCalledWith('导入成功：3条，失败：0条')

    importSupportedVillagesMock.mockResolvedValueOnce({
      imported: 1,
      failed: 2,
      errors: [{ row: 2, error: 'bad' }, { row_index: 3, message: 'worse' }],
    })
    alertMock.mockResolvedValue(undefined)
    vm.handleImport()
    const fileBad = new File(['x'], 'b.xlsx')
    Object.defineProperty(inputs[1], 'files', { value: [fileBad], configurable: true })
    ;(inputs[1] as any).onchange({ target: { files: [fileBad] } })
    await flushPromises()
    expect(alertMock).toHaveBeenCalled()
    expect(ElMessage.warning).toHaveBeenCalledWith('有2条数据导入失败，请检查数据格式')

    importSupportedVillagesMock.mockRejectedValueOnce(new Error('down'))
    vm.handleImport()
    const fileErr = new File(['x'], 'c.xlsx')
    Object.defineProperty(inputs[2], 'files', { value: [fileErr], configurable: true })
    ;(inputs[2] as any).onchange({ target: { files: [fileErr] } })
    await flushPromises()
    expect(ElMessage.error).toHaveBeenCalledWith('导入功能需要后端支持，请先启动后端服务')

    spy.mockRestore()
    wrapper.unmount()
  })

  it('下载模板：成功静默 / 失败提示', async () => {
    downloadImportTemplateMock.mockResolvedValue(undefined)
    const wrapper = mountList()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleDownloadTemplate()
    expect(vm.exporting).toBe(false)

    downloadImportTemplateMock.mockRejectedValueOnce(new Error('offline'))
    await vm.handleDownloadTemplate()
    expect(ElMessage.error).toHaveBeenCalledWith('下载模板功能需要后端支持，请先启动后端服务')
    wrapper.unmount()
  })
})
describe('回收站分支收尾（569-570 / 689-694）', () => {
  it('恢复：接口失败 → 错误提示', async () => {
    restoreMock.mockRejectedValue(new Error('restore down'))
    confirmMock.mockResolvedValue({ value: undefined })
    const wrapper = mountList()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleRestore({ id: 11, villageName: '软删村A' })
    await flushPromises()
    expect(ElMessage.error).toHaveBeenCalledWith('恢复失败')
    wrapper.unmount()
  })

  it('创建成功但未返回 id → 跳过过渡资金保存', async () => {
    mockPost.mockReset()
    mockPost.mockImplementation((url: any) => {
      if (String(url) === '/supported-villages') return Promise.resolve({ data: {} })
      return Promise.resolve({ data: {} })
    })
    const wrapper = mountList()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.dialogMode = 'create'
    vm.currentVillage = null
    await vm.handleFormSubmit({
      villageName: '无ID村',
      _transitionFundingItems: [{ year: 2026 }],
    } as any)
    await flushPromises()
    expect(vm.dialogVisible).toBe(false)
    wrapper.unmount()
  })

  it('过渡资金保存失败仅记日志不阻断创建', async () => {
    mockPost.mockReset()
    mockPost.mockImplementation((url: any) => {
      const u = String(url)
      if (u === '/supported-villages') return Promise.resolve({ data: { id: 77 } })
      if (u.includes('/transition-funding')) return Promise.reject(new Error('tf down'))
      return Promise.resolve({ data: {} })
    })
    const wrapper = mountList()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.dialogMode = 'create'
    vm.currentVillage = null
    await vm.handleFormSubmit({
      villageName: '资金失败村',
      _transitionFundingItems: [{ year: 2026 }],
    } as any)
    await flushPromises()
    expect(vm.dialogVisible).toBe(false)
    wrapper.unmount()
  })
})
