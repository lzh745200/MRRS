import { describe, it, expect, vi, beforeEach } from 'vitest'

// src/api/import.ts 实际 import：
//   import request, { post, apiRequest } from '@/api/request'
//   import { downloadBlobAsFile } from '@/api/helpers/blobDownload'
// blobDownload.ts 又 import 了 parseContentDisposition / downloadBlob，
// 因此 mock 必须提供命名导出 + default。
// post(url, data, extra) 原样透传；helper 已自动拆信封，mockResolvedValue(body)。
const { mockPost, mockApiRequest, mockRequestGet, mockDownloadBlob } = vi.hoisted(() => ({
  mockPost: vi.fn(),
  mockApiRequest: vi.fn(),
  mockRequestGet: vi.fn(),
  mockDownloadBlob: vi.fn(),
}))

vi.mock('@/api/request', () => ({
  post: (url: string, ...rest: any[]) => mockPost(url, ...rest),
  apiRequest: (...args: any[]) => mockApiRequest(...args),
  parseContentDisposition: (_headers: any, fallback = 'download') => fallback,
  downloadBlob: (...args: any[]) => mockDownloadBlob(...args),
  default: {
    get: (url: string, config?: any) => mockRequestGet(url, config),
  },
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

import {
  downloadImportTemplateAndSave,
  importEntities,
  previewImportData,
  validateImport,
} from '@/api/import'

describe('api/import — downloadImportTemplateAndSave', () => {
  beforeEach(() => vi.clearAllMocks())

  it('GET /import/template blob 并以默认兜底名触发下载', async () => {
    mockRequestGet.mockResolvedValueOnce({ data: new Blob(['x']), headers: {} })
    await downloadImportTemplateAndSave('school')
    expect(mockRequestGet).toHaveBeenCalledWith('/import/template', {
      params: { entity_type: 'school' },
      responseType: 'blob',
    })
    expect(mockDownloadBlob).toHaveBeenCalledWith(expect.any(Blob), '导入模板.xlsx')
  })

  it('自定义 fallbackName 拼扩展名；响应头文件名优先', async () => {
    mockRequestGet.mockResolvedValueOnce({
      data: new Blob(['x']),
      headers: { 'content-disposition': 'attachment; filename="tpl.xlsx"' },
    })
    await downloadImportTemplateAndSave('fund', '资金模板')
    // content-disposition 有 filename → 用解析结果而非兜底名
    expect(mockDownloadBlob).toHaveBeenCalledWith(expect.any(Blob), 'tpl.xlsx')

    mockRequestGet.mockResolvedValueOnce({ data: new Blob(['x']), headers: {} })
    await downloadImportTemplateAndSave('fund', '资金模板')
    expect(mockDownloadBlob).toHaveBeenCalledWith(expect.any(Blob), '资金模板.xlsx')
  })
})

describe('api/import — importEntities', () => {
  beforeEach(() => vi.clearAllMocks())

  it('默认 entity_type=supported_village / mode=incremental 走 Query 参数，透传返回值', async () => {
    const body = { success: true, total_rows: 10, success_rows: 9, failed_rows: 1, skipped_rows: 0 }
    mockPost.mockResolvedValueOnce(body)
    const file = new File(['x'], 'data.xlsx')
    const result = await importEntities(file)
    const [url, fd, config] = mockPost.mock.calls[0]
    expect(url).toBe('/import/entities')
    expect(fd).toBeInstanceOf(FormData)
    expect(fd.get('file')).toBe(file)
    // entity_type/mode 经 Query 参数传递（后端 Query 接收），不写入 FormData
    expect(fd.get('entity_type')).toBeNull()
    expect(fd.get('mode')).toBeNull()
    expect(config.params).toEqual({ entity_type: 'supported_village', mode: 'incremental' })
    expect(config.headers['Content-Type']).toBe('multipart/form-data')
    expect(config.timeout).toBe(120000)
    expect(result).toBe(body)
  })

  it('自定义 entityType / mode 写入 Query 参数（后端仅支持 incremental/full）', async () => {
    mockPost.mockResolvedValueOnce({ success: true })
    await importEntities(new File(['x'], 'p.xlsx'), 'project', 'full')
    const config = mockPost.mock.calls[0][2]
    expect(config.params).toEqual({ entity_type: 'project', mode: 'full' })
  })
})

describe('api/import — previewImportData', () => {
  beforeEach(() => vi.clearAllMocks())

  it('POST /import/preview FormData（timeout 60000，entity_type 走 Query）并透传返回值', async () => {
    const body = { rows: [{ a: 1 }], total: 1, columns: ['a'] }
    mockPost.mockResolvedValueOnce(body)
    const file = new File(['x'], 'preview.xlsx')
    const result = await previewImportData(file, 'school')
    const [url, fd, config] = mockPost.mock.calls[0]
    expect(url).toBe('/import/preview')
    expect(fd.get('file')).toBe(file)
    expect(fd.get('entity_type')).toBeNull()
    expect(config.params).toEqual({ entity_type: 'school' })
    expect(config.headers['Content-Type']).toBe('multipart/form-data')
    expect(config.timeout).toBe(60000)
    expect(result).toBe(body)
  })
})

describe('api/import — validateImport', () => {
  beforeEach(() => vi.clearAllMocks())

  it('带文件 → POST /import/validate FormData（含 entity_type）', async () => {
    mockPost.mockResolvedValueOnce({ valid: true })
    const file = new File(['x'], 'v.xlsx')
    const result = await validateImport({ file, entity_type: 'school' })
    const [url, fd, config] = mockPost.mock.calls[0]
    expect(url).toBe('/import/validate')
    expect(fd).toBeInstanceOf(FormData)
    expect(fd.get('file')).toBe(file)
    expect(fd.get('entity_type')).toBe('school')
    expect(config.headers['Content-Type']).toBe('multipart/form-data')
    expect(config.timeout).toBe(120000)
    expect(result).toEqual({ valid: true })
  })

  it('带文件但无 entity_type → FormData 不含 entity_type', async () => {
    mockPost.mockResolvedValueOnce({ valid: false, errors: [] })
    await validateImport({ file: new File(['x'], 'v.xlsx') })
    const fd = mockPost.mock.calls[0][1] as FormData
    expect(fd.get('entity_type')).toBeNull()
  })

  it('不带文件 → POST /import/validate 原始 data 对象', async () => {
    mockPost.mockResolvedValueOnce({ valid: true })
    const result = await validateImport({ entity_type: 'fund' })
    expect(mockPost).toHaveBeenCalledWith('/import/validate', { entity_type: 'fund' })
    expect(result).toEqual({ valid: true })
  })
})
