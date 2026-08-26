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
})

