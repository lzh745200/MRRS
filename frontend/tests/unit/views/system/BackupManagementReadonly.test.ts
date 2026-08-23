/**
 * 备份管理页 普通用户只读模式测试 (T11)
 * canOperateBackup 角色矩阵：user=false；admin/super_admin/is_superuser=true。
 * 页面写按钮/只读标记均由此标志驱动，写接口另有后端 require_admin 兜底。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const { mockGet, getUserMock } = vi.hoisted(() => ({
  mockGet: vi.fn(),
  getUserMock: vi.fn(),
}))

vi.mock('element-plus', () => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  ElMessageBox: { confirm: vi.fn(), prompt: vi.fn() },
}))

vi.mock('@/api/request', () => ({
  get: mockGet,
  post: vi.fn(),
  put: vi.fn(),
  del: vi.fn(),
  apiRequest: vi.fn(),
  getCsrfToken: vi.fn(() => Promise.resolve('test-csrf')),
}))

vi.mock('@/api/backup', () => ({
  uploadRestoreBackup: vi.fn(),
}))

vi.mock('@/utils/authStorage', () => ({
  AuthStorage: { getToken: vi.fn(() => 'tok'), getUser: getUserMock },
}))

import BackupManagement from '@/views/system/BackupManagement.vue'

function mountComp() {
  return mount(BackupManagement)
}

beforeEach(() => {
  vi.clearAllMocks()
  mockGet.mockResolvedValue({ data: {} })
})

describe('备份管理只读模式（T11）', () => {
  it('user 角色：canOperateBackup=false（写按钮与只读标记随该标志隐藏/显示）', async () => {
    getUserMock.mockReturnValue({ role: 'user', is_superuser: false })
    const w = mountComp()
    await flushPromises()
    expect((w.vm as any).canOperateBackup).toBe(false)
    w.unmount()
  })

  it('admin 角色：canOperateBackup=true', async () => {
    getUserMock.mockReturnValue({ role: 'admin', is_superuser: false })
    const w = mountComp()
    await flushPromises()
    expect((w.vm as any).canOperateBackup).toBe(true)
    w.unmount()
  })

  it('super_admin 与 is_superuser 均具备操作权', async () => {
    getUserMock.mockReturnValue({ role: 'super_admin', is_superuser: false })
    const w = mountComp()
    await flushPromises()
    expect((w.vm as any).canOperateBackup).toBe(true)
    w.unmount()

    getUserMock.mockReturnValue({ role: 'user', is_superuser: true })
    const w2 = mountComp()
    await flushPromises()
    expect((w2.vm as any).canOperateBackup).toBe(true)
    w2.unmount()
  })
})
