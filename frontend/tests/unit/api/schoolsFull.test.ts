import { describe, it, expect, vi, beforeEach } from 'vitest'

// src/api/schools.ts 实际 import：
//   import request, { get, post, put, del, apiRequest } from '@/api/request'
//   import { downloadBlobAsFile } from '@/api/helpers/blobDownload'
// blobDownload.ts 又 import 了 parseContentDisposition / downloadBlob，
// 因此 mock 必须提供全部命名导出 + default。
// 命名 get(url, params)：第二参数直接是 params；post(url, data, extra) 原样透传。
const { mockGet, mockPost, mockPut, mockDel, mockApiRequest, mockDownloadBlob } = vi.hoisted(
  () => ({
    mockGet: vi.fn(),
    mockPost: vi.fn(),
    mockPut: vi.fn(),
    mockDel: vi.fn(),
    mockApiRequest: vi.fn(),
    mockDownloadBlob: vi.fn(),
  })
)

vi.mock('@/api/request', () => ({
  get: (url: string, ...rest: any[]) => (rest.length > 0 ? mockGet(url, rest[0]) : mockGet(url)),
  post: (url: string, ...rest: any[]) => mockPost(url, ...rest),
  put: (url: string, ...rest: any[]) => (rest.length > 0 ? mockPut(url, rest[0]) : mockPut(url)),
  del: (url: string) => mockDel(url),
  apiRequest: (...args: any[]) => mockApiRequest(...args),
  // 忠实反映真实解析语义（"响应头文件名优先"的断言必须能测到实现）
  parseContentDisposition: (headers: any, fallback = 'download') => {
    const cd = headers?.['content-disposition'] || headers?.['Content-Disposition']
    if (!cd) return fallback
    const star = cd.match(/filename\*=([^;]+)/i)
    if (star) {
      const raw = star[1].trim()
      const i = raw.indexOf("''")
      if (i >= 0) {
        try {
          const decoded = decodeURIComponent(raw.slice(i + 2))
          if (decoded) return decoded
        } catch {
          /* fallthrough */
        }
      }
    }
    const quoted = cd.match(/filename="?([^";]+)"?/i)
    if (quoted && quoted[1].trim()) return quoted[1].trim()
    return fallback
  },
  downloadBlob: (...args: any[]) => mockDownloadBlob(...args),
  default: {
    get: (url: string, config?: any) => mockGet(url, config),
  },
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

import { schoolsApi } from '@/api/schools'

describe('api/schools — 统计与选项', () => {
  beforeEach(() => vi.clearAllMocks())

  it('getStatistics GET /schools/statistics 并透传返回值', async () => {
    const body = { total: 12 }
    mockGet.mockResolvedValueOnce(body)
    const result = await schoolsApi.getStatistics()
    expect(mockGet).toHaveBeenCalledWith('/schools/statistics')
    expect(result).toBe(body)
  })

  it('getTypeOptions GET /schools/options/types', async () => {
    mockGet.mockResolvedValueOnce(['小学'])
    const result = await schoolsApi.getTypeOptions()
    expect(mockGet).toHaveBeenCalledWith('/schools/options/types')
    expect(result).toEqual(['小学'])
  })

  it('getStatusOptions GET /schools/options/statuses', async () => {
    mockGet.mockResolvedValueOnce(['在办'])
    const result = await schoolsApi.getStatusOptions()
    expect(mockGet).toHaveBeenCalledWith('/schools/options/statuses')
    expect(result).toEqual(['在办'])
  })
})

describe('api/schools — 导入导出', () => {
  beforeEach(() => vi.clearAllMocks())

  it('importExcel POST FormData 到 /schools/import/excel', async () => {
    mockPost.mockResolvedValueOnce({ success_rows: 5 })
    const file = new File(['x'], 'schools.xlsx')
    const result = await schoolsApi.importExcel(file)
    const [url, fd, config] = mockPost.mock.calls[0]
    expect(url).toBe('/schools/import/excel')
    expect(fd).toBeInstanceOf(FormData)
    expect(fd.get('file')).toBe(file)
    expect(config.headers['Content-Type']).toBe('multipart/form-data')
    expect(result).toEqual({ success_rows: 5 })
  })

  it('exportExcel 走 request.get blob 并触发 downloadBlob（解析文件名）', async () => {
    mockGet.mockResolvedValueOnce({
      data: new Blob(['x']),
      headers: { 'content-disposition': 'attachment; filename="schools_2024.xlsx"' },
    })
    await schoolsApi.exportExcel({ page: 1 })
    expect(mockGet).toHaveBeenCalledWith('/schools/export/excel', {
      params: { page: 1 },
      responseType: 'blob',
    })
    expect(mockDownloadBlob).toHaveBeenCalledWith(expect.any(Blob), 'schools_2024.xlsx')
  })

  it('exportExcel 无文件名头时用兜底文件名', async () => {
    mockGet.mockResolvedValueOnce({ data: new Blob(['x']), headers: {} })
    await schoolsApi.exportExcel()
    expect(mockDownloadBlob).toHaveBeenCalledWith(expect.any(Blob), '学校数据导出.xlsx')
  })
})

describe('api/schools — 帮扶项目', () => {
  beforeEach(() => vi.clearAllMocks())

  it('listProjects GET /schools/{id}/projects', async () => {
    mockGet.mockResolvedValueOnce([{ id: 1 }])
    const result = await schoolsApi.listProjects(5)
    expect(mockGet).toHaveBeenCalledWith('/schools/5/projects')
    expect(result).toEqual([{ id: 1 }])
  })

  it('createProject POST /schools/{id}/projects', async () => {
    mockPost.mockResolvedValueOnce({ id: 1 })
    await schoolsApi.createProject(5, { name: 'P' })
    expect(mockPost).toHaveBeenCalledWith('/schools/5/projects', { name: 'P' })
  })

  it('updateProject PUT /schools/{id}/projects/{pid}', async () => {
    mockPut.mockResolvedValueOnce({ id: 7 })
    await schoolsApi.updateProject(5, 7, { name: 'P2' })
    expect(mockPut).toHaveBeenCalledWith('/schools/5/projects/7', { name: 'P2' })
  })

  it('deleteProject DELETE /schools/{id}/projects/{pid}', async () => {
    mockDel.mockResolvedValueOnce({ deleted: true })
    await schoolsApi.deleteProject(5, 7)
    expect(mockDel).toHaveBeenCalledWith('/schools/5/projects/7')
  })
})

describe('api/schools — 资助学生', () => {
  beforeEach(() => vi.clearAllMocks())

  it('listScholarshipStudents 带 year → params { year }', async () => {
    mockGet.mockResolvedValueOnce([{ id: 1 }])
    await schoolsApi.listScholarshipStudents(5, 2024)
    expect(mockGet).toHaveBeenCalledWith('/schools/5/scholarship-students', { year: 2024 })
  })

  it('listScholarshipStudents 无 year → params undefined', async () => {
    mockGet.mockResolvedValueOnce([])
    await schoolsApi.listScholarshipStudents(5)
    expect(mockGet).toHaveBeenCalledWith('/schools/5/scholarship-students', undefined)
  })

  it('createScholarshipStudent POST /schools/{id}/scholarship-students', async () => {
    mockPost.mockResolvedValueOnce({ id: 1 })
    await schoolsApi.createScholarshipStudent(5, { name: 'S' })
    expect(mockPost).toHaveBeenCalledWith('/schools/5/scholarship-students', { name: 'S' })
  })

  it('updateScholarshipStudent PUT /schools/{id}/scholarship-students/{sid}', async () => {
    mockPut.mockResolvedValueOnce({ id: 8 })
    await schoolsApi.updateScholarshipStudent(5, 8, { name: 'S2' })
    expect(mockPut).toHaveBeenCalledWith('/schools/5/scholarship-students/8', { name: 'S2' })
  })

  it('deleteScholarshipStudent DELETE /schools/{id}/scholarship-students/{sid}', async () => {
    mockDel.mockResolvedValueOnce({ deleted: true })
    await schoolsApi.deleteScholarshipStudent(5, 8)
    expect(mockDel).toHaveBeenCalledWith('/schools/5/scholarship-students/8')
  })

  it('importScholarshipStudents POST FormData 到 .../scholarship-students/import', async () => {
    mockPost.mockResolvedValueOnce({ success_rows: 3 })
    const file = new File(['x'], 'students.xlsx')
    const result = await schoolsApi.importScholarshipStudents(5, file)
    const [url, fd, config] = mockPost.mock.calls[0]
    expect(url).toBe('/schools/5/scholarship-students/import')
    expect(fd).toBeInstanceOf(FormData)
    expect(fd.get('file')).toBe(file)
    expect(config.headers['Content-Type']).toBe('multipart/form-data')
    expect(result).toEqual({ success_rows: 3 })
  })
})

describe('api/schools — 附件管理', () => {
  beforeEach(() => vi.clearAllMocks())

  it('listAttachments GET /schools/{id}/attachments', async () => {
    mockGet.mockResolvedValueOnce([{ id: 1 }])
    const result = await schoolsApi.listAttachments(5)
    expect(mockGet).toHaveBeenCalledWith('/schools/5/attachments')
    expect(result).toEqual([{ id: 1 }])
  })

  it('uploadAttachment POST FormData 到 /schools/{id}/attachments', async () => {
    mockPost.mockResolvedValueOnce({ id: 9 })
    const file = new File(['x'], 'proof.pdf')
    const result = await schoolsApi.uploadAttachment(5, file)
    const [url, fd, config] = mockPost.mock.calls[0]
    expect(url).toBe('/schools/5/attachments')
    expect(fd).toBeInstanceOf(FormData)
    expect(fd.get('file')).toBe(file)
    expect(config.headers['Content-Type']).toBe('multipart/form-data')
    expect(result).toEqual({ id: 9 })
  })

  it('deleteAttachment DELETE /schools/attachments/{aid}', async () => {
    mockDel.mockResolvedValueOnce({ deleted: true })
    const result = await schoolsApi.deleteAttachment(9)
    expect(mockDel).toHaveBeenCalledWith('/schools/attachments/9')
    expect(result).toEqual({ deleted: true })
  })

  it('downloadAttachment apiRequest GET blob 并透传返回值', async () => {
    const blob = new Blob(['x'])
    mockApiRequest.mockResolvedValueOnce(blob)
    const result = await schoolsApi.downloadAttachment(9)
    expect(mockApiRequest).toHaveBeenCalledWith({
      method: 'GET',
      url: '/schools/attachments/9/download',
      responseType: 'blob',
    })
    expect(result).toBe(blob)
  })
})
