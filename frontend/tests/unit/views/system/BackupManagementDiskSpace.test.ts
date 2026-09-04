/**
 * W12-T045: BackupManagement.vue 磁盘空间不足警告 UI 测试
 * 覆盖：fetchBackupStats 写入 diskSpace；diskSpaceWarning computed 在
 * backup_dir.sufficient=false 时输出警告文案；模板 el-alert 可见。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const { ElMessage, confirmMock, mockGet, mockPost, mockPut, mockDel, getTokenMock } = vi.hoisted(
  () => ({
    ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
    confirmMock: vi.fn(),
    mockGet: vi.fn(),
    mockPost: vi.fn(),
    mockPut: vi.fn(),
    mockDel: vi.fn(),
    getTokenMock: vi.fn(),
  })
)

vi.mock('element-plus', () => ({
  ElMessage,
  ElMessageBox: { confirm: confirmMock },
}))

vi.mock('@/api/request', () => ({
  get: mockGet,
  post: mockPost,
  put: mockPut,
  del: mockDel,
  apiRequest: vi.fn(),
  getCsrfToken: vi.fn(() => Promise.resolve('test-csrf')),
}))

vi.mock('@/utils/authStorage', () => ({
  AuthStorage: { getToken: getTokenMock },
}))

import BackupManagement from '@/views/system/BackupManagement.vue'

function statsPayload(sufficient: boolean) {
  return {
    data: {
      data: {
        totalBackups: 1,
        totalSize: 1024,
        disk_space: {
          threshold_mb: 500,
          backup_dir: { path: '/bak', free_mb: sufficient ? 99999 : 12, total_mb: 100000, sufficient },
          db_dir: { path: '/db', free_mb: sufficient ? 99999 : 12, total_mb: 100000, sufficient },
        },
      },
    },
  }
}

describe('BackupManagement 磁盘空间警告', () => {
  beforeEach(() => {
    mockGet.mockReset()
    localStorage.clear()
  })

  it('低空间时显示警告 alert', async () => {
    mockGet.mockImplementation(async (url: string) => {
      if (url === '/system/backup/stats') return statsPayload(false)
      return { data: { data: { items: [] } } }
    })

    const wrapper = mount(BackupManagement, { attachTo: document.body })
    await flushPromises()

    const alert = wrapper.find('el-alert')
    expect(alert.exists()).toBe(true)
    expect(wrapper.html()).toContain('磁盘剩余空间不足')
    wrapper.unmount()
  })

  it('充足空间时不显示警告', async () => {
    mockGet.mockImplementation(async (url: string) => {
      if (url === '/system/backup/stats') return statsPayload(true)
      return { data: { data: { items: [] } } }
    })

    const wrapper = mount(BackupManagement, { attachTo: document.body })
    await flushPromises()

    expect(wrapper.find('el-alert').exists()).toBe(false)
    wrapper.unmount()
  })

  // diskSpaceWarning 分支矩阵：branch@367(@368/@369/@371×2)
  it('diskSpaceWarning：db_dir 回退 / 无目录 / sufficient 缺省 / ?? 兜底 / 空间充足', async () => {
    mockGet.mockResolvedValue({ data: { data: {} } })
    const wrapper = mount(BackupManagement, { attachTo: document.body })
    await flushPromises()
    const vm = wrapper.vm as any

    // diskSpace 为 null → branch@367 真侧
    expect(vm.diskSpace).toBeNull()
    expect(vm.diskSpaceWarning).toBeNull()

    // 无 backup_dir 时回退 db_dir（branch@368 第二操作数），且 threshold_mb 显式提供
    vm.diskSpace = { threshold_mb: 200, db_dir: { path: '/db', free_mb: 10, sufficient: false } }
    expect(vm.diskSpaceWarning).toBe('磁盘剩余空间不足（10MB < 200MB），备份/恢复可能被拒绝')

    // 两个目录均缺省 → !dir 真侧
    vm.diskSpace = { threshold_mb: 200 }
    expect(vm.diskSpaceWarning).toBeNull()

    // dir.sufficient === undefined → branch@369 第二操作数真侧
    vm.diskSpace = { backup_dir: { path: '/bak', free_mb: 10 } }
    expect(vm.diskSpaceWarning).toBeNull()

    // free_mb 与 threshold_mb 均缺省 → branch@371 两个 ?? 右侧（-1 / 500）
    vm.diskSpace = { backup_dir: { path: '/bak', sufficient: false } }
    expect(vm.diskSpaceWarning).toBe('磁盘剩余空间不足（-1MB < 500MB），备份/恢复可能被拒绝')

    // sufficient === true → 末尾 return null
    vm.diskSpace = { backup_dir: { path: '/bak', free_mb: 999, sufficient: true } }
    expect(vm.diskSpaceWarning).toBeNull()
    wrapper.unmount()
  })
})

