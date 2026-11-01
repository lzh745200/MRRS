import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

const mockGetDataPackages = vi.fn()
const mockGetDataPackage = vi.fn()
const mockExportDataPackage = vi.fn()
const mockImportDataPackage = vi.fn()
const mockPreviewDataPackage = vi.fn()
const mockConfirmImport = vi.fn()
const mockDryRunDataPackage = vi.fn()
const mockDownloadDataPackage = vi.fn()
const mockDeleteDataPackage = vi.fn()

vi.mock('@/api/dataPackage', () => ({
  getDataPackages: (...args: any[]) => mockGetDataPackages(...args),
  getDataPackage: (...args: any[]) => mockGetDataPackage(...args),
  exportDataPackage: (...args: any[]) => mockExportDataPackage(...args),
  importDataPackage: (...args: any[]) => mockImportDataPackage(...args),
  previewDataPackage: (...args: any[]) => mockPreviewDataPackage(...args),
  confirmImport: (...args: any[]) => mockConfirmImport(...args),
  dryRunDataPackage: (...args: any[]) => mockDryRunDataPackage(...args),
  downloadDataPackage: (...args: any[]) => mockDownloadDataPackage(...args),
  deleteDataPackage: (...args: any[]) => mockDeleteDataPackage(...args),
}))

import { useDataPackageStore } from '@/stores/dataPackage'

describe('useDataPackageStore', () => {
  let store: ReturnType<typeof useDataPackageStore>
  beforeEach(() => {
    vi.clearAllMocks()
    setActivePinia(createPinia())
    store = useDataPackageStore()
  })

  it('initial state: all empty/zero', () => {
    expect(store.packages).toEqual([])
    expect(store.currentPackage).toBeNull()
    expect(store.previewData).toEqual([])
    expect(store.importResult).toBeNull()
    expect(store.exportResult).toBeNull()
    expect(store.loading).toBe(false)
    expect(store.exporting).toBe(false)
    expect(store.importing).toBe(false)
    expect(store.error).toBeNull()
    expect(store.total).toBe(0)
  })

  it('validatedPackages getter 过滤 status=validated', () => {
    store.packages = [
      { id: 1, status: 'validated' } as any,
      { id: 2, status: 'imported' } as any,
    ]
    expect(store.validatedPackages).toHaveLength(1)
  })

  it('importedPackages getter 过滤 status=imported', () => {
    store.packages = [
      { id: 1, status: 'validated' } as any,
      { id: 2, status: 'imported' } as any,
    ]
    expect(store.importedPackages).toHaveLength(1)
  })

  it('failedPackages getter 过滤 status=failed', () => {
    store.packages = [
      { id: 1, status: 'failed' } as any,
      { id: 2, status: 'imported' } as any,
    ]
    expect(store.failedPackages).toHaveLength(1)
  })

  it('fetchPackages 成功时填充 packages + total', async () => {
    mockGetDataPackages.mockResolvedValueOnce({ items: [{ id: 1 }], total: 1 })
    await store.fetchPackages({ page: 1 })
    expect(mockGetDataPackages).toHaveBeenCalledWith({ page: 1 })
    expect(store.packages).toHaveLength(1)
    expect(store.total).toBe(1)
  })

  it('fetchPackages 失败时设置 error + 抛出', async () => {
    mockGetDataPackages.mockRejectedValueOnce(new Error('boom'))
    await expect(store.fetchPackages()).rejects.toThrow('boom')
    expect(store.error).toBe('boom')
  })

  it('fetchPackage 成功时设置 currentPackage', async () => {
    const pkg = { id: 5, name: 'X' }
    mockGetDataPackage.mockResolvedValueOnce(pkg)
    await store.fetchPackage(5)
    expect(store.currentPackage).toEqual(pkg)
  })

  it('exportPackage 成功时设置 exportResult', async () => {
    const result = { url: 'http://x' }
    mockExportDataPackage.mockResolvedValueOnce(result)
    await store.exportPackage({ org_id: 1, items: [] })
    expect(store.exportResult).toEqual(result)
    expect(store.exporting).toBe(false)
  })

  it('importPackage 成功 + valid 时加入 packages 列表', async () => {
    const result = {
      package_id: 99,
      package_code: 'PKG-001',
      status: 'validated',
      validation: { is_valid: true },
      manifest: { version: '2.0' },
    }
    mockImportDataPackage.mockResolvedValueOnce(result)
    await store.importPackage(new File([], 'pkg.zip'), 1)
    expect(store.importResult).toEqual(result)
    expect(store.packages[0].id).toBe(99)
    expect(store.packages[0].status).toBe('validated')
  })

  it('importPackage 成功 + invalid 时不加入 packages', async () => {
    const result = { validation: { is_valid: false }, package_id: 0 }
    mockImportDataPackage.mockResolvedValueOnce(result)
    await store.importPackage(new File([], 'bad.zip'))
    expect(store.packages).toEqual([])
  })

  it('importPackage valid 且无 orgId 时 org_id 回退 0', async () => {
    const result = {
      package_id: 77,
      package_code: 'PKG-NO-ORG',
      status: 'validated',
      validation: { is_valid: true },
      manifest: { version: '3.0' },
    }
    mockImportDataPackage.mockResolvedValueOnce(result)
    await store.importPackage(new File([], 'no-org.zip'))
    expect(store.packages[0].org_id).toBe(0)
    expect(store.packages[0].id).toBe(77)
  })

  it('importPackage valid 且无 manifest 时 version 回退 1.0', async () => {
    const result = {
      package_id: 88,
      package_code: 'PKG-NO-MANIFEST',
      status: 'validated',
      validation: { is_valid: true },
    }
    mockImportDataPackage.mockResolvedValueOnce(result)
    await store.importPackage(new File([], 'no-manifest.zip'), 2)
    expect(store.packages[0].org_id).toBe(2)
    expect(store.packages[0].version).toBe('1.0')
  })

  it('previewPackage 成功时填充 previewData', async () => {
    const data = [{ id: 1, value: 'x' }]
    mockPreviewDataPackage.mockResolvedValueOnce(data)
    await store.previewPackage(1)
    expect(store.previewData).toEqual(data)
  })

  it('previewPackage 兼容 { data: [...] } 信封形态', async () => {
    mockPreviewDataPackage.mockResolvedValueOnce({ data: [{ id: 2, value: 'y' }] })
    await store.previewPackage(1)
    expect(store.previewData).toEqual([{ id: 2, value: 'y' }])
  })

  it('previewPackage：响应既非数组也无 data → 回落空数组', async () => {
    mockPreviewDataPackage.mockResolvedValueOnce({})
    await store.previewPackage(1)
    expect(store.previewData).toEqual([])
  })

  it('confirmImport 成功时更新 status=imported', async () => {
    store.packages = [{ id: 1, status: 'validated' } as any]
    mockConfirmImport.mockResolvedValueOnce({ success: true })
    await store.confirmImport(1, {})
    expect(store.packages[0].status).toBe('imported')
  })

  it('confirmImport 失败时 packages 状态不变', async () => {
    store.packages = [{ id: 1, status: 'validated' } as any]
    mockConfirmImport.mockResolvedValueOnce({ success: false })
    await store.confirmImport(1, {})
    expect(store.packages[0].status).toBe('validated')
  })

  it('deletePackage 成功时从 packages 移除', async () => {
    store.packages = [{ id: 1 } as any, { id: 2 } as any]
    mockDeleteDataPackage.mockResolvedValueOnce({})
    await store.deletePackage(1, 'reason')
    expect(store.packages).toHaveLength(1)
    expect(store.packages[0].id).toBe(2)
  })

  it('deletePackage 成功时清除 currentPackage (如果 ID 匹配)', async () => {
    store.currentPackage = { id: 1 } as any
    store.packages = [{ id: 1 } as any]
    mockDeleteDataPackage.mockResolvedValueOnce({})
    await store.deletePackage(1)
    expect(store.currentPackage).toBeNull()
  })

  it('setCurrentPackage 设置值', () => {
    const pkg = { id: 5 } as any
    store.setCurrentPackage(pkg)
    expect(store.currentPackage).toEqual(pkg)
    store.setCurrentPackage(null)
    expect(store.currentPackage).toBeNull()
  })

  it('clearImportResult 清空 importResult', () => {
    store.importResult = { x: 1 } as any
    store.clearImportResult()
    expect(store.importResult).toBeNull()
  })

  it('clearExportResult 清空 exportResult', () => {
    store.exportResult = { y: 1 } as any
    store.clearExportResult()
    expect(store.exportResult).toBeNull()
  })

  it('clearPreviewData 清空 previewData', () => {
    store.previewData = [{ x: 1 }] as any
    store.clearPreviewData()
    expect(store.previewData).toEqual([])
  })

  it('clearError 清空 error', () => {
    store.error = 'something'
    store.clearError()
    expect(store.error).toBeNull()
  })

  it('$reset 重置所有 state', () => {
    store.packages = [{ id: 1 }] as any
    store.error = 'x'
    store.total = 5
    store.$reset()
    expect(store.packages).toEqual([])
    expect(store.error).toBeNull()
    expect(store.total).toBe(0)
  })

  it('fetchPackage 失败时设置 error + 抛出', async () => {
    mockGetDataPackage.mockRejectedValueOnce(new Error('pkg boom'))
    await expect(store.fetchPackage(5)).rejects.toThrow('pkg boom')
    expect(store.error).toBe('pkg boom')
    expect(store.loading).toBe(false)
  })

  it('exportPackage 失败时设置 error + 抛出', async () => {
    mockExportDataPackage.mockRejectedValueOnce(new Error('export boom'))
    await expect(store.exportPackage({ org_id: 1 } as any)).rejects.toThrow('export boom')
    expect(store.error).toBe('export boom')
    expect(store.exporting).toBe(false)
  })

  it('importPackage 失败时设置 error + 抛出', async () => {
    mockImportDataPackage.mockRejectedValueOnce(new Error('import boom'))
    await expect(store.importPackage(new File([], 'x.zip'))).rejects.toThrow('import boom')
    expect(store.error).toBe('import boom')
    expect(store.importing).toBe(false)
  })

  it('previewPackage 失败时设置 error + 抛出', async () => {
    mockPreviewDataPackage.mockRejectedValueOnce(new Error('preview boom'))
    await expect(store.previewPackage(1)).rejects.toThrow('preview boom')
    expect(store.error).toBe('preview boom')
    expect(store.loading).toBe(false)
  })

  it('confirmImport 失败时设置 error + 抛出且状态不变', async () => {
    store.packages = [{ id: 1, status: 'validated' } as any]
    mockConfirmImport.mockRejectedValueOnce(new Error('confirm boom'))
    await expect(store.confirmImport(1, {})).rejects.toThrow('confirm boom')
    expect(store.error).toBe('confirm boom')
    expect(store.packages[0].status).toBe('validated')
  })

  it('confirmImport 成功但 pkg 不在列表时仅返回结果', async () => {
    mockConfirmImport.mockResolvedValueOnce({ success: true })
    const result = await store.confirmImport(999, {})
    expect(result).toEqual({ success: true })
    expect(store.packages).toEqual([])
  })

  it('downloadPackage 成功时创建下载链接', async () => {
    const createObjectURL = vi.fn(() => 'blob:mock')
    const revokeObjectURL = vi.fn()
    ;(window.URL as any).createObjectURL = createObjectURL
    ;(window.URL as any).revokeObjectURL = revokeObjectURL
    const link = document.createElement('a')
    link.click = vi.fn()
    const realCreate = document.createElement.bind(document)
    vi.spyOn(document, 'createElement').mockImplementation((tag: any) =>
      tag === 'a' ? link : realCreate(tag)
    )
    store.packages = [{ id: 1, file_name: 'pkg-1.zip' } as any]
    mockDownloadDataPackage.mockResolvedValueOnce(new Blob(['x']))
    await store.downloadPackage(1)
    expect(createObjectURL).toHaveBeenCalled()
    expect(link.download).toBe('pkg-1.zip')
    expect(link.click).toHaveBeenCalled()
    expect(revokeObjectURL).toHaveBeenCalled()
    expect(store.loading).toBe(false)
  })

  it('downloadPackage 无 file_name 时使用默认文件名', async () => {
    const createObjectURL = vi.fn(() => 'blob:mock')
    const revokeObjectURL = vi.fn()
    ;(window.URL as any).createObjectURL = createObjectURL
    ;(window.URL as any).revokeObjectURL = revokeObjectURL
    const link = document.createElement('a')
    link.click = vi.fn()
    const realCreate = document.createElement.bind(document)
    vi.spyOn(document, 'createElement').mockImplementation((tag: any) =>
      tag === 'a' ? link : realCreate(tag)
    )
    mockDownloadDataPackage.mockResolvedValueOnce(new Blob(['x']))
    await store.downloadPackage(7)
    expect(link.download).toBe('package_7.zip')
  })

  it('downloadPackage 失败时设置 error + 抛出', async () => {
    mockDownloadDataPackage.mockRejectedValueOnce(new Error('dl boom'))
    await expect(store.downloadPackage(1)).rejects.toThrow('dl boom')
    expect(store.error).toBe('dl boom')
    expect(store.loading).toBe(false)
  })

  it('deletePackage 失败时设置 error + 抛出', async () => {
    store.packages = [{ id: 1 } as any]
    mockDeleteDataPackage.mockRejectedValueOnce(new Error('del boom'))
    await expect(store.deletePackage(1)).rejects.toThrow('del boom')
    expect(store.error).toBe('del boom')
    expect(store.packages).toHaveLength(1)
    expect(store.loading).toBe(false)
  })

  it('deletePackage 成功但 currentPackage 非该 id 时不清除', async () => {
    store.currentPackage = { id: 2 } as any
    store.packages = [{ id: 1 } as any]
    mockDeleteDataPackage.mockResolvedValueOnce({})
    await store.deletePackage(1)
    expect(store.currentPackage).toEqual({ id: 2 })
  })

  // 长期项「两阶段导入」第一阶段：演练只读，不触碰包状态
  it('dryRunPackage 成功时写入 dryRunReport 且不改包状态', async () => {
    store.packages = [{ id: 3, status: 'validated' } as any]
    const report = {
      success: true,
      package_id: 3,
      package_code: 'PKG-3',
      status: 'validated',
      overwrite_existing: false,
      types: [],
      total_records: 10,
      total_to_create: 6,
      total_to_update: 0,
      total_rejected: 4,
      rejected: [],
      message: '',
    }
    mockDryRunDataPackage.mockResolvedValueOnce(report)

    const result = await store.dryRunPackage(3)

    expect(result).toEqual(report)
    expect(store.dryRunReport).toEqual(report)
    expect(store.packages[0].status).toBe('validated')
    expect(store.loading).toBe(false)
    expect(store.error).toBeNull()
  })

  it('dryRunPackage 失败时设置 error + 抛出且 report 保持为空', async () => {
    mockDryRunDataPackage.mockRejectedValueOnce(new Error('dry boom'))
    await expect(store.dryRunPackage(3)).rejects.toThrow('dry boom')
    expect(store.error).toBe('dry boom')
    expect(store.dryRunReport).toBeNull()
    expect(store.loading).toBe(false)
  })

  it('$reset 清空 dryRunReport', async () => {
    mockDryRunDataPackage.mockResolvedValueOnce({ success: true, types: [] })
    await store.dryRunPackage(3)
    store.$reset()
    expect(store.dryRunReport).toBeNull()
  })
})