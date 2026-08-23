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
  mockGet,
  mockPost,
  mockPut,
  mockDel,
  getSupportedVillagesMock,
  restoreMock,
  previewPurgeMock,
  purgeMock,
  pushSafe,
} = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  confirmMock: vi.fn(),
  promptMock: vi.fn(),
  mockGet: vi.fn(),
  mockPost: vi.fn(),
  mockPut: vi.fn(),
  mockDel: vi.fn(),
  getSupportedVillagesMock: vi.fn(),
  restoreMock: vi.fn(),
  previewPurgeMock: vi.fn(),
  purgeMock: vi.fn(),
  pushSafe: vi.fn(),
}))

vi.mock('element-plus', () => ({
  ElMessage,
  ElMessageBox: { confirm: confirmMock, prompt: promptMock },
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
  importSupportedVillages: vi.fn(),
  exportSupportedVillages: vi.fn(),
  downloadImportTemplate: vi.fn(),
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
