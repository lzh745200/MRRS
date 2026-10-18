import { describe, it, expect, vi, beforeEach } from 'vitest'

// dataSync.ts 从 '@/api/request' 导入 get/post/apiRequest（自动拆信封，resolve body 即可）；
// W5-T5 后 downloadExportPackage 改用 apiRequest<Blob>（返回值即 Blob），不再依赖默认导出。
// import 链还经过 '@/api/helpers/blobDownload'，因此 mock 必须额外提供
// parseContentDisposition/downloadBlob。
const { mockGet, mockPost, mockApiRequest, mockDownloadBlob } = vi.hoisted(() => ({
  mockGet: vi.fn().mockResolvedValue({}),
  mockPost: vi.fn().mockResolvedValue({}),
  mockApiRequest: vi.fn().mockResolvedValue({}),
  mockDownloadBlob: vi.fn(),
}))

vi.mock('@/api/request', () => ({
  get: (...args: any[]) => mockGet(...args),
  post: (...args: any[]) => mockPost(...args),
  apiRequest: (...args: any[]) => mockApiRequest(...args),
  parseContentDisposition: (_headers: any, fallback: string) => fallback,
  downloadBlob: (...args: any[]) => mockDownloadBlob(...args),
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

import {
  importData,
  importEncryptedData,
  exportData,
  exportEncryptedData,
  downloadExportPackage,
  getSyncLogs,
  getConflicts,
  resolveConflict,
  dataSyncApi,
} from '@/api/dataSync'

describe('api/dataSync', () => {
  beforeEach(() => vi.clearAllMocks())

  it('importData POST FormData 默认 strategy=overwrite', () => {
    const file = new File(['x'], 'data.json')
    importData(file)
    const [url, fd, config] = mockPost.mock.calls[0]
    expect(url).toBe('/data-sync/import')
    expect(fd).toBeInstanceOf(FormData)
    expect(fd.get('file')).toBe(file)
    expect(fd.get('strategy')).toBe('overwrite')
    expect(config.headers['Content-Type']).toBe('multipart/form-data')
  })

  it('importData 自定义 strategy', () => {
    const file = new File(['x'], 'data.json')
    importData(file, 'merge')
    const fd = mockPost.mock.calls[0][1]
    expect(fd.get('strategy')).toBe('merge')
  })

  it('importEncryptedData POST FormData with password', () => {
    const file = new File(['x'], 'data.enc')
    importEncryptedData(file, 'secret')
    const [url, fd, config] = mockPost.mock.calls[0]
    expect(url).toBe('/data-sync/import-encrypted')
    expect(fd).toBeInstanceOf(FormData)
    expect(fd.get('file')).toBe(file)
    expect(fd.get('password')).toBe('secret')
    expect(config.headers['Content-Type']).toBe('multipart/form-data')
  })

  it('exportData POST /data-sync/export 透传返回值', async () => {
    const body = { task_id: 't1' }
    mockPost.mockResolvedValueOnce(body)
    const r = await exportData({ modules: ['villages'] })
    expect(mockPost).toHaveBeenCalledWith('/data-sync/export', { modules: ['villages'] })
    expect(r).toBe(body)
  })

  it('exportEncryptedData POST /data-sync/export-encrypted', async () => {
    const body = { task_id: 't2' }
    mockPost.mockResolvedValueOnce(body)
    const params = { password: 'p', export_type: 'full' as const }
    const r = await exportEncryptedData(params)
    expect(mockPost).toHaveBeenCalledWith('/data-sync/export-encrypted', params)
    expect(r).toBe(body)
  })

  it('downloadExportPackage 无扩展名时补 .rrs 兜底文件名', async () => {
    mockApiRequest.mockResolvedValue(new Blob(['x']))
    await downloadExportPackage('pkg1')
    expect(mockApiRequest).toHaveBeenCalledWith({
      method: 'GET',
      url: '/data-sync/export/download/pkg1',
      responseType: 'blob',
    })
    expect(mockDownloadBlob).toHaveBeenCalledWith(expect.any(Blob), 'pkg1.rrs')
  })

  it('downloadExportPackage 已含扩展名时原样作兜底文件名', async () => {
    mockApiRequest.mockResolvedValue(new Blob(['x']))
    await downloadExportPackage('pkg1.zip')
    expect(mockApiRequest).toHaveBeenCalledWith({
      method: 'GET',
      url: '/data-sync/export/download/pkg1.zip',
      responseType: 'blob',
    })
    expect(mockDownloadBlob).toHaveBeenCalledWith(expect.any(Blob), 'pkg1.zip')
  })

  it('getSyncLogs GET /data-sync/logs with params', async () => {
    const body = { items: [], total: 0 }
    mockGet.mockResolvedValueOnce(body)
    const r = await getSyncLogs({ page: 2 })
    expect(mockGet).toHaveBeenCalledWith('/data-sync/logs', { page: 2 })
    expect(r).toBe(body)
  })

  it('getSyncLogs 无参', async () => {
    mockGet.mockResolvedValueOnce({})
    await getSyncLogs()
    expect(mockGet).toHaveBeenCalledWith('/data-sync/logs', undefined)
  })

  it('getConflicts GET /data-sync/conflicts/{id}', async () => {
    const body = [{ id: 'c1' }]
    mockGet.mockResolvedValueOnce(body)
    const r = await getConflicts(5)
    expect(mockGet).toHaveBeenCalledWith('/data-sync/conflicts/5')
    expect(r).toBe(body)
  })

  it('resolveConflict POST /data-sync/resolve-conflict', async () => {
    const body = { success: true }
    mockPost.mockResolvedValueOnce(body)
    const params = { conflict_id: 1, resolution: 'remote' }
    const r = await resolveConflict(params)
    expect(mockPost).toHaveBeenCalledWith('/data-sync/resolve-conflict', params)
    expect(r).toBe(body)
  })

  it('dataSyncApi 对象形式与具名函数一致', () => {
    expect(dataSyncApi.importData).toBe(importData)
    expect(dataSyncApi.importEncryptedData).toBe(importEncryptedData)
    expect(dataSyncApi.exportData).toBe(exportData)
    expect(dataSyncApi.exportEncryptedData).toBe(exportEncryptedData)
    expect(dataSyncApi.downloadExportPackage).toBe(downloadExportPackage)
    expect(dataSyncApi.getSyncLogs).toBe(getSyncLogs)
    expect(dataSyncApi.getConflicts).toBe(getConflicts)
    expect(dataSyncApi.resolveConflict).toBe(resolveConflict)
  })
})
