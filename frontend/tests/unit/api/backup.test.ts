import { describe, it, expect, vi, beforeEach } from 'vitest'

const { mockGet, mockPost, mockDel, mockPut } = vi.hoisted(() => ({
  mockGet: vi.fn(),
  mockPost: vi.fn(),
  mockDel: vi.fn(),
  mockPut: vi.fn(),
}))

// src/api/backup.ts 实际 import：import { get, post, del, put } from '@/api/request'
vi.mock('@/api/request', () => ({
  get: mockGet,
  post: mockPost,
  del: mockDel,
  put: mockPut,
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

import {
  getBackupList,
  createBackup,
  restoreBackup,
  deleteBackup,
  getBackupStats,
  getBackupDirs,
  setBackupTarget,
} from '@/api/backup'

describe('api/backup', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('getBackupList 调用 GET /system/backup 并透传分页参数与返回值', async () => {
    const body = { items: [], total: 0 }
    mockGet.mockResolvedValue(body)
    const result = await getBackupList({ page: 1, page_size: 20 })
    expect(mockGet).toHaveBeenCalledWith('/system/backup', { page: 1, page_size: 20 })
    expect(result).toBe(body)
  })

  it('createBackup 调用 POST /system/backup 并透传载荷', async () => {
    const body = { success: true }
    mockPost.mockResolvedValue(body)
    const data = { description: '手动备份', include_uploads: true }
    const result = await createBackup(data)
    expect(mockPost).toHaveBeenCalledWith('/system/backup', data)
    expect(result).toBe(body)
  })

  it('restoreBackup 调用 POST /system/backup/restore 带 filename 与 password', async () => {
    const body = { success: true }
    mockPost.mockResolvedValue(body)
    const result = await restoreBackup('backup-2024.zip', 'secret')
    expect(mockPost).toHaveBeenCalledWith('/system/backup/restore', {
      filename: 'backup-2024.zip',
      password: 'secret',
    })
    expect(result).toBe(body)
  })

  it('deleteBackup 调用 DELETE /system/backup/{filename}', async () => {
    mockDel.mockResolvedValue({ success: true })
    await deleteBackup('backup-2024.zip')
    expect(mockDel).toHaveBeenCalledWith('/system/backup/backup-2024.zip')
  })

  it('deleteBackup 对文件名做路径段编码（# / ? 不再改写路由）', async () => {
    mockDel.mockResolvedValue({ success: true })
    await deleteBackup('bk#1?.zip')
    expect(mockDel).toHaveBeenCalledWith('/system/backup/bk%231%3F.zip')
  })

  it('deleteBackup 对空文件名 / 含分隔符或 .. 的名字 fail-closed 抛错', async () => {
    mockDel.mockClear()
    await expect(deleteBackup('')).rejects.toThrow('备份文件名不能为空')
    await expect(deleteBackup('   ')).rejects.toThrow('备份文件名不能为空')
    await expect(deleteBackup('a/b.zip')).rejects.toThrow('备份文件名非法')
    await expect(deleteBackup('..\\etc\\passwd')).rejects.toThrow('备份文件名非法')
    await expect(deleteBackup('..%2Fx.zip')).rejects.toThrow('备份文件名非法')
    expect(mockDel).not.toHaveBeenCalled()
  })

  it('getBackupStats 调用 GET /system/backup/stats 并透传返回值', async () => {
    const body = { total_backups: 3, total_size: 1024, auto_backup_enabled: true }
    mockGet.mockResolvedValue(body)
    const result = await getBackupStats()
    expect(mockGet).toHaveBeenCalledWith('/system/backup/stats')
    expect(result).toBe(body)
  })

  it('getBackupDirs 调用 GET /system/backup/dirs 并透传返回值', async () => {
    const body = {
      dirs: [{ path: '/mnt/usb', type: 'usb', available: true }],
      current: '/mnt/usb',
      default_dir: '/data/backup',
    }
    mockGet.mockResolvedValue(body)
    const result = await getBackupDirs()
    expect(mockGet).toHaveBeenCalledWith('/system/backup/dirs')
    expect(result).toBe(body)
  })

  it('setBackupTarget 调用 PUT /system/backup/target 携带 target_dir', async () => {
    mockPut.mockResolvedValue({ success: true })
    await setBackupTarget('/mnt/usb')
    expect(mockPut).toHaveBeenCalledWith('/system/backup/target', { target_dir: '/mnt/usb' })
  })

  it('restoreBackup 无 password 时仍调用 restore 端点', async () => {
    mockPost.mockResolvedValue({ success: true })
    await restoreBackup('backup-2024.zip')
    expect(mockPost).toHaveBeenCalledWith('/system/backup/restore', {
      filename: 'backup-2024.zip',
      password: undefined,
    })
  })
})
