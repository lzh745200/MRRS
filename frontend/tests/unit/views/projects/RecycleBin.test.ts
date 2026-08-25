/**
 * views/projects/List.vue 回收站行为测试 (Phase C 推广)
 * 覆盖：开关切换 include_deleted、恢复回环、彻底删除（预览→警告→密码→调用）、取消分支。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const {
  ElMessage,
  confirmMock,
  promptMock,
  projectApiMock,
  pushSafe,
} = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  confirmMock: vi.fn(),
  promptMock: vi.fn(),
  projectApiMock: {
    getStats: vi.fn(),
    list: vi.fn(),
    delete: vi.fn(),
    exportList: vi.fn(),
    restore: vi.fn(),
    purgePreview: vi.fn(),
    purge: vi.fn(),
  },
  pushSafe: vi.fn(),
}))

vi.mock('element-plus', () => ({
  ElMessage,
  ElMessageBox: { confirm: confirmMock, prompt: promptMock },
  ElTable: { name: 'ElTable', template: '<div class="el-table-stub"><slot /></div>' },
}))

vi.mock('@/api/projects', () => ({
  projectApi: projectApiMock,
  projectsApi: projectApiMock,
  restoreProject: projectApiMock.restore,
  previewPurgeProject: projectApiMock.purgePreview,
  purgeProject: projectApiMock.purge,
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({ user: { role: 'admin', id: 1 }, canViewDeleted: true }),
}))

vi.mock('@/composables/useRouterSafe', () => ({ useRouterSafe: () => ({ pushSafe }) }))

import ProjectsList from '@/views/projects/List.vue'

function mountList() {
  return mount(ProjectsList)
}

beforeEach(() => {
  vi.clearAllMocks()
  projectApiMock.list.mockResolvedValue({
    data: { items: [{ id: 21, name: '软删项目A' }], total: 1 },
  })
  projectApiMock.getStats.mockResolvedValue({
    data: { total: 1, in_progress: 0, completed: 0, total_budget: 10 },
  })
})

describe('项目列表 回收站（Phase C）', () => {
  it('开关切换 → list 携带 include_deleted', async () => {
    const w = mountList()
    await flushPromises()
    const before = projectApiMock.list.mock.calls.length
    ;(w.vm as any).showDeletedOnly = true
    await (w.vm as any).handleToggleDeleted()
    expect(projectApiMock.list.mock.calls.length).toBeGreaterThan(before)
    const last = projectApiMock.list.mock.calls.at(-1)?.[0] || {}
    expect(last.include_deleted).toBe(true)
    w.unmount()
  })

  it('恢复：确认后调用 restore 并刷新', async () => {
    confirmMock.mockResolvedValue({ value: undefined })
    projectApiMock.restore.mockResolvedValue({})
    const w = mountList()
    await flushPromises()
    const before = projectApiMock.list.mock.calls.length
    await (w.vm as any).handleRestore({ id: 21, name: '软删项目A' })
    await flushPromises()

    expect(projectApiMock.restore).toHaveBeenCalledWith(21)
    expect(projectApiMock.list.mock.calls.length).toBeGreaterThan(before)
    expect(ElMessage.success).toHaveBeenCalledWith('恢复成功')
    w.unmount()
  })

  it('彻底删除：预览 → 警告 → 密码 → purge 携带密码', async () => {
    projectApiMock.purgePreview.mockResolvedValue({
      data: { id: 21, total_references: 2, details: { funds: 2 } },
    })
    confirmMock.mockResolvedValue({ value: undefined })
    promptMock.mockResolvedValue({ value: 'pw-9' })
    projectApiMock.purge.mockResolvedValue({ data: { deleted_records: 3 } })

    const w = mountList()
    await flushPromises()
    await (w.vm as any).handlePurge({ id: 21, name: '软删项目A' })
    await flushPromises()

    expect(projectApiMock.purgePreview).toHaveBeenCalledWith(21)
    expect(projectApiMock.purge).toHaveBeenCalledWith(21, 'pw-9')
    expect(ElMessage.success).toHaveBeenCalled()
    w.unmount()
  })

  it('彻底删除：警告取消 → 不调用接口', async () => {
    projectApiMock.purgePreview.mockResolvedValue({
      data: { id: 21, total_references: 0, details: {} },
    })
    confirmMock.mockRejectedValue('cancel')
    const w = mountList()
    await flushPromises()
    await (w.vm as any).handlePurge({ id: 21, name: 'X' })
    expect(projectApiMock.purge).not.toHaveBeenCalled()
    w.unmount()
  })
})
