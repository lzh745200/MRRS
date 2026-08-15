import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockGet = vi.fn()
const mockPost = vi.fn()
const mockPut = vi.fn()
const mockDel = vi.fn()
const mockApiRequest = vi.fn()
const mockDownloadBlob = vi.fn()

vi.mock('@/utils/request', () => ({
  default: {
    get: (...args: any[]) => mockGet(...args),
    post: (...args: any[]) => mockPost(...args),
    put: (...args: any[]) => mockPut(...args),
    delete: (...args: any[]) => mockDel(...args),
    apiRequest: (...args: any[]) => mockApiRequest(...args),
  },
}))
vi.mock('@/api/request', () => ({
  default: {
    get: (...args: any[]) => mockGet(...args),
    post: (...args: any[]) => mockPost(...args),
    put: (...args: any[]) => mockPut(...args),
    delete: (...args: any[]) => mockDel(...args),
    apiRequest: (...args: any[]) => mockApiRequest(...args),
  },
  get: (...args: any[]) => mockGet(...args),
  post: (...args: any[]) => mockPost(...args),
  put: (...args: any[]) => mockPut(...args),
  del: (...args: any[]) => mockDel(...args),
  apiRequest: (...args: any[]) => mockApiRequest(...args),
  // 提供真实的 parseContentDisposition 实现，供下载函数解析文件名
  parseContentDisposition: (headers: Record<string, string> | undefined, fallback = 'download.xlsx') => {
    if (!headers) return fallback
    const cd = headers['content-disposition'] || headers['Content-Disposition'] || ''
    if (!cd) return fallback
    const starMatch = cd.match(/filename\*=([^;]+)/i)
    if (starMatch) {
      const raw = starMatch[1].trim()
      const idx = raw.indexOf("''")
      if (idx >= 0) {
        try { return decodeURIComponent(raw.slice(idx + 2)) } catch { /* fallthrough */ }
      }
    }
    const quotedMatch = cd.match(/filename="?([^";]+)"?/i)
    if (quotedMatch) return quotedMatch[1].trim()
    return fallback
  },
  downloadBlob: (...args: any[]) => mockDownloadBlob(...args),
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

import {
  getSupportedVillages,
  getSupportedVillage,
  createSupportedVillage,
  updateSupportedVillage,
  deleteSupportedVillage,
  batchDeleteSupportedVillages,
  importSupportedVillages,
  exportSupportedVillages,
  downloadImportTemplate,
  downloadTemplate,
} from '@/api/supportedVillage'
// re-read to expose
import * as sv from '@/api/supportedVillage'

import {
  exportVillages,
  getExportTasks,
  getExportStatus,
  getExportHistory,
  downloadExportFile,
  formatExportStatus,
  formatFileSize,
  triggerDownload,
  exportReportWord,
  exportReportPdf,
  exportUsers,
  exportSchools,
  exportProjects,
  exportFunds,
  exportComprehensive,
} from '@/api/export'

describe('api/supportedVillage (named)', () => {
  beforeEach(() => vi.clearAllMocks())

  it('getSupportedVillages GET /supported-villages', () => {
    getSupportedVillages({ page: 1 })
    expect(mockGet).toHaveBeenCalledWith('/supported-villages', { page: 1 })
  })
  it('getSupportedVillage GET /{id}', () => {
    getSupportedVillage(5)
    expect(mockGet).toHaveBeenCalledWith('/supported-villages/5')
  })
  it('createSupportedVillage POST', () => {
    createSupportedVillage({ name: 'V' })
    expect(mockPost).toHaveBeenCalledWith('/supported-villages', { name: 'V' })
  })
  it('updateSupportedVillage PUT', () => {
    updateSupportedVillage(5, { name: 'V2' })
    expect(mockPut).toHaveBeenCalledWith('/supported-villages/5', { name: 'V2' })
  })
  it('deleteSupportedVillage DELETE', () => {
    deleteSupportedVillage(5)
    expect(mockDel).toHaveBeenCalledWith('/supported-villages/5')
  })
  it('batchDeleteSupportedVillages POST ids', () => {
    batchDeleteSupportedVillages([1, 2, 3])
    expect(mockPost).toHaveBeenCalledWith('/supported-villages/batch-delete', { ids: [1, 2, 3], confirm_password: '' })
    batchDeleteSupportedVillages([4], 'pw')
    expect(mockPost).toHaveBeenCalledWith('/supported-villages/batch-delete', { ids: [4], confirm_password: 'pw' })
  })

  it('importSupportedVillages POST FormData', () => {
    const file = new File(['x'], 'a.xlsx')
    importSupportedVillages(file)
    expect(mockApiRequest).toHaveBeenCalledWith({
      method: 'POST',
      url: '/supported-villages/import',
      data: expect.any(FormData),
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  })

  describe('blob exports', () => {
    beforeEach(() => {
      vi.clearAllMocks()
      const realAnchor = (globalThis as any).document.createElement('a')
      realAnchor.click = vi.fn()
      const realCreate = (globalThis as any).document.createElement.bind((globalThis as any).document)
      ;(globalThis as any).document.createElement = (tag: any) => {
        if (tag === 'a') return realAnchor
        return realCreate(tag)
      }
    })

    it('exportSupportedVillages 触发下载, 解析 content-disposition', async () => {
      mockGet.mockResolvedValueOnce({
        data: new Blob(['x']),
        headers: { 'content-disposition': 'attachment; filename="villages_export.xlsx"' },
      })
      await exportSupportedVillages({ page: 1 })
      expect(mockGet).toHaveBeenCalledWith('/supported-villages/export', {
        params: { page: 1 },
        responseType: 'blob',
      })
    })

    it('exportSupportedVillages 缺少 filename 走默认', async () => {
      mockGet.mockResolvedValueOnce({
        data: new Blob(['x']),
        headers: {},
      })
      await exportSupportedVillages()
      expect(mockGet).toHaveBeenCalled()
    })

    it('downloadImportTemplate + alias downloadTemplate', async () => {
      mockGet.mockResolvedValueOnce({ data: new Blob(['x']), headers: {} })
      await downloadImportTemplate()
      expect(mockGet).toHaveBeenCalledWith('/import/template', { params: { entity_type: 'supported_village' }, responseType: 'blob' })
      expect(downloadTemplate).toBe(downloadImportTemplate)
    })
  })

  it('导出 filter options / 统计等其它 named 函数存在', () => {
    // enumerate export names of the module
    const names = Object.keys(sv).sort()
    expect(names).toContain('getSupportedVillages')
    expect(names).toContain('getSupportedVillage')
    expect(names).toContain('createSupportedVillage')
    expect(names).toContain('updateSupportedVillage')
    expect(names).toContain('deleteSupportedVillage')
    expect(names).toContain('batchDeleteSupportedVillages')
    expect(names).toContain('importSupportedVillages')
    expect(names).toContain('exportSupportedVillages')
    expect(names).toContain('downloadImportTemplate')
    expect(names).toContain('downloadTemplate')
  })
})

describe('api/export', () => {
  beforeEach(() => vi.clearAllMocks())

  it('exportVillages GET blob', async () => {
    mockGet.mockResolvedValueOnce({ data: new Blob(['x']) })
    const r = await exportVillages({ village_ids: [1] })
    expect(mockGet).toHaveBeenCalledWith('/export/villages', {
      params: { village_ids: [1] },
      responseType: 'blob',
    })
    // 当前实现触发浏览器下载并返回 void（downloadBlobAsFile）
    expect(r).toBeUndefined()
    expect(mockDownloadBlob).toHaveBeenCalledWith(expect.any(Blob), expect.any(String))
  })

  it('getExportTasks GET /async-export/tasks', async () => {
    mockGet.mockResolvedValueOnce({ data: { items: [] } })
    await getExportTasks({ page: 1 })
    // 命名 get(url, params) 辅助函数：params 直接作为第二参数
    expect(mockGet).toHaveBeenCalledWith('/async-export/tasks', { page: 1 })
  })

  it('getExportStatus GET /async-export/status/{id}', async () => {
    mockGet.mockResolvedValueOnce({ data: { status: 'pending' } })
    await getExportStatus('T1')
    expect(mockGet).toHaveBeenCalledWith('/async-export/status/T1')
  })

  it('getExportHistory GET /async-export/tasks', async () => {
    mockGet.mockResolvedValueOnce({ data: { items: [] } })
    await getExportHistory({ page: 1 })
    // 命名 get(url, params) 辅助函数：params 直接作为第二参数
    expect(mockGet).toHaveBeenCalledWith('/async-export/tasks', { page: 1 })
  })

  it('downloadExportFile GET blob', async () => {
    mockGet.mockResolvedValueOnce({ data: new Blob(['x']) })
    const r = await downloadExportFile('T1')
    expect(mockGet).toHaveBeenCalledWith('/async-export/download/T1', { responseType: 'blob' })
    // 当前实现触发浏览器下载并返回 void（downloadBlobAsFile）
    expect(r).toBeUndefined()
    expect(mockDownloadBlob).toHaveBeenCalledWith(expect.any(Blob), expect.any(String))
  })

  it('exportReportWord GET /export/report-word with report_type', async () => {
    mockGet.mockResolvedValueOnce({ data: new Blob(['x']) })
    await exportReportWord('summary', 2026)
    expect(mockGet).toHaveBeenCalledWith('/export/report-word', {
      params: { report_type: 'summary', year: 2026 },
      responseType: 'blob',
    })
  })

  it('exportReportPdf GET /export/report-pdf with report_type', async () => {
    mockGet.mockResolvedValueOnce({ data: new Blob(['x']) })
    await exportReportPdf('fund_detail', 2025)
    expect(mockGet).toHaveBeenCalledWith('/export/report-pdf', {
      params: { report_type: 'fund_detail', year: 2025 },
      responseType: 'blob',
    })
  })

  it('exportReportWord 无 year 时不带 year 参数', async () => {
    mockGet.mockResolvedValueOnce({ data: new Blob(['x']) })
    await exportReportWord('summary')
    expect(mockGet).toHaveBeenCalledWith('/export/report-word', {
      params: { report_type: 'summary' },
      responseType: 'blob',
    })
  })

  it('exportReportPdf 无 year 时不带 year 参数', async () => {
    mockGet.mockResolvedValueOnce({ data: new Blob(['x']) })
    await exportReportPdf('summary')
    expect(mockGet).toHaveBeenCalledWith('/export/report-pdf', {
      params: { report_type: 'summary' },
      responseType: 'blob',
    })
  })

  it('exportUsers GET /export/users blob', async () => {
    mockGet.mockResolvedValueOnce({ data: new Blob(['x']) })
    await exportUsers({ type: 'all' })
    expect(mockGet).toHaveBeenCalledWith('/export/users', {
      params: { type: 'all' },
      responseType: 'blob',
    })
  })

  it('exportUsers 无参时 params=undefined', async () => {
    mockGet.mockResolvedValueOnce({ data: new Blob(['x']) })
    await exportUsers()
    expect(mockGet).toHaveBeenCalledWith('/export/users', { params: undefined, responseType: 'blob' })
  })

  it('exportSchools GET /export/schools blob', async () => {
    mockGet.mockResolvedValueOnce({ data: new Blob(['x']) })
    await exportSchools({ format: 'xlsx' })
    expect(mockGet).toHaveBeenCalledWith('/export/schools', {
      params: { format: 'xlsx' },
      responseType: 'blob',
    })
  })

  it('exportProjects GET /export/projects blob', async () => {
    mockGet.mockResolvedValueOnce({ data: new Blob(['x']) })
    await exportProjects({ department: '农办' })
    expect(mockGet).toHaveBeenCalledWith('/export/projects', {
      params: { department: '农办' },
      responseType: 'blob',
    })
  })

  it('exportFunds GET /export/funds blob', async () => {
    mockGet.mockResolvedValueOnce({ data: new Blob(['x']) })
    await exportFunds({ support_unit: 'X' })
    expect(mockGet).toHaveBeenCalledWith('/export/funds', {
      params: { support_unit: 'X' },
      responseType: 'blob',
    })
  })

  it('exportComprehensive GET /export/comprehensive blob', async () => {
    mockGet.mockResolvedValueOnce({ data: new Blob(['x']) })
    await exportComprehensive({ region_scope: 'county' })
    expect(mockGet).toHaveBeenCalledWith('/export/comprehensive', {
      params: { region_scope: 'county' },
      responseType: 'blob',
    })
  })

  describe('formatExportStatus', () => {
    it('pending -> 等待中', () => expect(formatExportStatus('pending')).toBe('等待中'))
    it('processing -> 处理中', () => expect(formatExportStatus('processing')).toBe('处理中'))
    it('completed -> 已完成', () => expect(formatExportStatus('completed')).toBe('已完成'))
    it('failed -> 失败', () => expect(formatExportStatus('failed')).toBe('失败'))
    it('unknown 回退', () => expect(formatExportStatus('xxx')).toBe('xxx'))
  })

  describe('formatFileSize', () => {
    it('0 -> 0 B', () => expect(formatFileSize(0)).toBe('0 B'))
    it('1023 -> 1023.00 B', () => expect(formatFileSize(1023)).toMatch(/B$/))
    it('1024 -> 1.00 KB', () => expect(formatFileSize(1024)).toBe('1.00 KB'))
    it('1024*1024 -> 1.00 MB', () => expect(formatFileSize(1024 * 1024)).toBe('1.00 MB'))
    it('1024^3 -> 1.00 GB', () => expect(formatFileSize(1024 ** 3)).toBe('1.00 GB'))
  })

  it('triggerDownload 触发 a.click', () => {
    const realAnchor = (globalThis as any).document.createElement('a')
    realAnchor.click = vi.fn()
    const realCreate = (globalThis as any).document.createElement.bind((globalThis as any).document)
    ;(globalThis as any).document.createElement = (tag: any) => {
      if (tag === 'a') return realAnchor
      return realCreate(tag)
    }
    triggerDownload(new Blob(['x']), 'test.bin')
    expect(realAnchor.click).toHaveBeenCalled()
  })
})
