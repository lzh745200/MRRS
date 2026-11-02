import { describe, it, expect, vi, beforeEach } from 'vitest'

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  apiRequest: vi.fn(),
  downloadBlob: vi.fn(),
  parseContentDisposition: vi.fn(() => 'download.xlsx'),
}))

// src/api/import.ts 实际 import：default (request)、{ post, apiRequest }
// 间接依赖 blobDownload.ts 还引用了 parseContentDisposition / downloadBlob
vi.mock('@/api/request', () => ({
  default: {
    get: mocks.get,
    post: mocks.post,
  },
  get: mocks.get,
  post: mocks.post,
  apiRequest: mocks.apiRequest,
  parseContentDisposition: mocks.parseContentDisposition,
  downloadBlob: mocks.downloadBlob,
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

import {
  downloadImportTemplate,
  exportFillTemplateAndSave,
  importVillages,
  getImportHistory,
  formatImportStatus,
} from '@/api/import'

describe('api/import', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('downloadImportTemplate GET /import/template with entity_type', async () => {
    const blob = new Blob(['test'])
    mocks.apiRequest.mockResolvedValueOnce(blob)
    const result = await downloadImportTemplate('village')
    expect(mocks.apiRequest).toHaveBeenCalledWith({
      method: 'GET',
      url: '/import/template',
      params: { entity_type: 'village' },
      responseType: 'blob',
    })
    expect(result).toBe(blob)
  })

  it('importVillages POST /import/entities with FormData (default entity_type=supported_village)', async () => {
    mocks.post.mockResolvedValueOnce({
      success: true, total_rows: 10, success_rows: 10, failed_rows: 0, skipped_rows: 0,
    })
    const file = new File(['test'], 'villages.xlsx')
    const result = await importVillages(file)
    expect(mocks.post).toHaveBeenCalled()
    const [url, formData, config] = mocks.post.mock.calls[0]
    expect(url).toBe('/import/entities')
    expect(formData).toBeInstanceOf(FormData)
    expect(formData.get('file')).toBe(file)
    // entity_type/mode 通过 Query 参数传递（后端 Query 校验），不放入 FormData
    expect(formData.get('entity_type')).toBeNull()
    expect(config.params).toEqual({ entity_type: 'supported_village', mode: 'incremental' })
    expect(config.headers['Content-Type']).toBe('multipart/form-data')
    expect(config.timeout).toBe(120000)
    expect(result.success).toBe(true)
  })

  it('importVillages mode=full', async () => {
    mocks.post.mockResolvedValueOnce({
      success: true, total_rows: 5, success_rows: 5, failed_rows: 0, skipped_rows: 0,
    })
    const file = new File(['test'], 'data.xlsx')
    await importVillages(file, 'full')
    const config = mocks.post.mock.calls[0][2]
    expect(config.params).toEqual({ entity_type: 'supported_village', mode: 'full' })
  })

  it('getImportHistory 默认 page=1, pageSize=10', async () => {
    mocks.apiRequest.mockResolvedValueOnce({ items: [], total: 0 })
    const result = await getImportHistory()
    expect(mocks.apiRequest).toHaveBeenCalledWith({
      method: 'GET',
      url: '/import/history',
      params: { page: 1, page_size: 10 },
    })
    expect(result).toEqual({ items: [], total: 0 })
  })

  it('getImportHistory 自定义 page + pageSize', async () => {
    mocks.apiRequest.mockResolvedValueOnce({ items: [], total: 0 })
    const result = await getImportHistory(2, 25)
    expect(mocks.apiRequest).toHaveBeenCalledWith({
      method: 'GET',
      url: '/import/history',
      params: { page: 2, page_size: 25 },
    })
    expect(result).toEqual({ items: [], total: 0 })
  })

  describe('formatImportStatus', () => {
    it('pending -> 等待中 / info', () => {
      expect(formatImportStatus('pending')).toEqual({ text: '等待中', type: 'info' })
    })
    it('processing -> 处理中 / warning', () => {
      expect(formatImportStatus('processing')).toEqual({ text: '处理中', type: 'warning' })
    })
    it('completed -> 已完成 / success', () => {
      expect(formatImportStatus('completed')).toEqual({ text: '已完成', type: 'success' })
    })
    it('failed -> 失败 / danger', () => {
      expect(formatImportStatus('failed')).toEqual({ text: '失败', type: 'danger' })
    })
    it('未知状态回退', () => {
      expect(formatImportStatus('xyz')).toEqual({ text: 'xyz', type: 'info' })
    })
  })

  describe('exportFillTemplateAndSave', () => {
    const downloadResponse = () => ({
      data: new Blob(['x']),
      headers: { 'content-disposition': 'attachment; filename="x.xlsx"' },
    })

    it('数组 ids 合并为逗号串并触发下载', async () => {
      mocks.get.mockResolvedValueOnce(downloadResponse())
      await exportFillTemplateAndSave('project', [1, 2], '项目填报')
      const [url, config] = mocks.get.mock.calls[0]
      expect(url).toBe('/import/export-fill')
      expect(config.params).toEqual({ entity_type: 'project', ids: '1,2' })
      expect(config.responseType).toBe('blob')
      expect(mocks.downloadBlob).toHaveBeenCalledWith(expect.any(Blob), 'download.xlsx')
    })

    it('字符串 ids 去除首尾空格后传出', async () => {
      mocks.get.mockResolvedValueOnce(downloadResponse())
      await exportFillTemplateAndSave('fund', '  3,7  ', '资金填报')
      expect(mocks.get.mock.calls[0][1].params).toEqual({ entity_type: 'fund', ids: '3,7' })
    })

    it('ids 为空时只传 entity_type（导出全部）', async () => {
      mocks.get.mockResolvedValueOnce(downloadResponse())
      await exportFillTemplateAndSave('school', undefined, '学校填报')
      expect(mocks.get.mock.calls[0][1].params).toEqual({ entity_type: 'school' })
    })
  })
})
