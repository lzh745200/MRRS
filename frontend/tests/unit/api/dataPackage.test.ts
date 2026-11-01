import { describe, it, expect, vi, beforeEach } from 'vitest'

const mocks = vi.hoisted(() => ({
  mockGet: vi.fn(),
  mockPost: vi.fn(),
  mockApiRequest: vi.fn(),
}))
const { mockGet, mockPost, mockApiRequest } = mocks

// src/api/dataPackage.ts 导入的是 { get, post, apiRequest } 命名导出，
// 它们返回的是已解包的 envelope body，因此 mock 的 resolved 值即 body 本身
// （源码对 get/post 的返回值再取 .data，即 envelope body 内的 data 字段）。
vi.mock('@/api/request', () => ({
  get: mocks.mockGet,
  post: mocks.mockPost,
  apiRequest: mocks.mockApiRequest,
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

import {
  getDataPackages,
  getDataPackage,
  exportDataPackage,
  importDataPackage,
  validateDataPackage,
  previewDataPackage,
  confirmImport,
  dryRunDataPackage,
  downloadDataPackage,
  deleteDataPackage,
  getPackageHistory,
  getDownloadUrl,
  oneClickReport,
  previewExport,
} from '@/api/dataPackage'

describe('api/dataPackage', () => {
  beforeEach(() => vi.clearAllMocks())

  it('getDataPackages GET /data-packages', async () => {
    mockGet.mockResolvedValueOnce({ data: { items: [], total: 0 } })
    await getDataPackages({ page: 1, page_size: 10 })
    expect(mockGet).toHaveBeenCalledWith('/data-packages', { page: 1, page_size: 10 })
  })

  it('getDataPackage GET /data-packages/{id}', async () => {
    mockGet.mockResolvedValueOnce({ data: { id: 1 } })
    await getDataPackage(1)
    expect(mockGet).toHaveBeenCalledWith('/data-packages/1')
  })

  it('exportDataPackage POST /data-packages/export', async () => {
    mockPost.mockResolvedValueOnce({ data: { package_id: 1 } })
    await exportDataPackage({ data_types: ['village'] } as any)
    expect(mockPost).toHaveBeenCalledWith('/data-packages/export', { data_types: ['village'] })
  })

  it('importDataPackage POST FormData (no orgId)', async () => {
    mockPost.mockResolvedValueOnce({ data: { success: true } })
    const file = new File(['x'], 'a.zip')
    await importDataPackage(file)
    const [url, fd, config] = mockPost.mock.calls[0]
    expect(url).toBe('/data-packages/import')
    expect(fd).toBeInstanceOf(FormData)
    expect(fd.get('file')).toBe(file)
    expect(config.params).toEqual({})
    expect(config.headers['Content-Type']).toBe('multipart/form-data')
  })

  it('importDataPackage POST FormData (with orgId)', async () => {
    mockPost.mockResolvedValueOnce({ data: { success: true } })
    const file = new File(['x'], 'a.zip')
    await importDataPackage(file, 5)
    expect(mockPost.mock.calls[0][2].params).toEqual({ org_id: 5 })
  })

  it('validateDataPackage POST /data-packages/{id}/validate', async () => {
    mockPost.mockResolvedValueOnce({ data: { valid: true } })
    await validateDataPackage(3)
    expect(mockPost).toHaveBeenCalledWith('/data-packages/3/validate')
  })

  it('previewDataPackage GET /data-packages/{id}/preview', async () => {
    mockGet.mockResolvedValueOnce({ data: [] })
    await previewDataPackage(3)
    expect(mockGet).toHaveBeenCalledWith('/data-packages/3/preview')
  })

  it('confirmImport POST /data-packages/{id}/confirm', async () => {
    mockPost.mockResolvedValueOnce({ data: { success: true } })
    await confirmImport(3, { strategy: 'merge' } as any)
    expect(mockPost).toHaveBeenCalledWith('/data-packages/3/confirm', { strategy: 'merge' })
  })

  it('confirmImport 无 data 时用 {}', async () => {
    mockPost.mockResolvedValueOnce({ data: { success: true } })
    await confirmImport(3)
    expect(mockPost).toHaveBeenCalledWith('/data-packages/3/confirm', {})
  })

  it('downloadDataPackage GET blob', async () => {
    mockApiRequest.mockResolvedValueOnce(new Blob(['x']))
    const result = await downloadDataPackage(3)
    expect(mockApiRequest).toHaveBeenCalledWith({
      method: 'GET',
      url: '/data-packages/3/download',
      responseType: 'blob',
    })
    expect(result).toBeInstanceOf(Blob)
  })

  it('deleteDataPackage DELETE (no reason)', async () => {
    mockApiRequest.mockResolvedValueOnce({ message: 'ok' })
    await deleteDataPackage(3)
    expect(mockApiRequest).toHaveBeenCalledWith({
      method: 'DELETE',
      url: '/data-packages/3',
      params: undefined,
    })
  })

  it('deleteDataPackage DELETE (with reason)', async () => {
    mockApiRequest.mockResolvedValueOnce({ message: 'ok' })
    await deleteDataPackage(3, 'cleanup')
    expect(mockApiRequest).toHaveBeenCalledWith({
      method: 'DELETE',
      url: '/data-packages/3',
      params: { reason: 'cleanup' },
    })
  })

  it('getPackageHistory GET /data-packages/{id}/history', async () => {
    mockGet.mockResolvedValueOnce({ data: { package_id: 1, items: [] } })
    await getPackageHistory(1, { page: 1 })
    expect(mockGet).toHaveBeenCalledWith('/data-packages/1/history', { page: 1 })
  })

  // 长期项「两阶段导入」：演练走独立只读端点，绝不能复用 confirm
  it('dryRunDataPackage POST /data-packages/{id}/dry-run（带参数）', async () => {
    mockPost.mockResolvedValueOnce({ data: { success: true, total_to_create: 2 } })
    await dryRunDataPackage(3, { overwrite_existing: true } as any)
    expect(mockPost).toHaveBeenCalledWith('/data-packages/3/dry-run', { overwrite_existing: true })
  })

  it('dryRunDataPackage 无 data 时用 {}', async () => {
    mockPost.mockResolvedValueOnce({ data: { success: true } })
    await dryRunDataPackage(3)
    expect(mockPost).toHaveBeenCalledWith('/data-packages/3/dry-run', {})
  })

  it('getDownloadUrl 返回 URL 字符串', () => {
    const url = getDownloadUrl(5)
    expect(url).toMatch(/\/api\/v1\/data-packages\/5\/download$/)
  })

  it('oneClickReport POST /data-packages/one-click-report', async () => {
    mockPost.mockResolvedValueOnce({ data: { report_url: 'x' } })
    await oneClickReport({ year: 2025 })
    expect(mockPost).toHaveBeenCalledWith('/data-packages/one-click-report', { year: 2025 })
  })

  it('previewExport POST /data-packages/preview', async () => {
    mockPost.mockResolvedValueOnce({ data: { preview: [] } })
    await previewExport({ data_types: ['village'] })
    expect(mockPost).toHaveBeenCalledWith('/data-packages/preview', { data_types: ['village'] })
  })
})
