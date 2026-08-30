import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockGet = vi.fn()
const mockPost = vi.fn()
const mockPut = vi.fn()
const mockDelete = vi.fn()

vi.mock('@/api/request', () => ({
  default: {
    get: (...args: any[]) => mockGet(...args),
    post: (...args: any[]) => mockPost(...args),
    put: (...args: any[]) => mockPut(...args),
    delete: (...args: any[]) => mockDelete(...args),
  },
  // 命名导出（返回已解包 body 的辅助函数）
  get: (...args: any[]) => mockGet(...args),
  post: (...args: any[]) => mockPost(...args),
  put: (...args: any[]) => mockPut(...args),
  del: (...args: any[]) => mockDelete(...args),
  apiRequest: vi.fn(),
  // @/api/helpers/blobDownload 依赖的两个工具
  parseContentDisposition: vi.fn(),
  downloadBlob: vi.fn(),
  getCsrfToken: vi.fn(() => Promise.resolve('test-csrf')),
}))

import { projectsApi, projectApi } from '@/api/projects'
import { schoolsApi, schoolApi } from '@/api/schools'

describe('api/projects', () => {
  beforeEach(() => vi.clearAllMocks())

  it('list GET /projects', () => {
    projectsApi.list({ page: 1 })
    expect(mockGet).toHaveBeenCalledWith('/projects', { page: 1 })
  })
  it('get GET /projects/{id}', () => {
    projectsApi.get(5)
    expect(mockGet).toHaveBeenCalledWith('/projects/5')
  })
  it('create POST /projects', () => {
    projectsApi.create({ name: 'P1' })
    expect(mockPost).toHaveBeenCalledWith('/projects', { name: 'P1' })
  })
  it('update PUT /projects/{id}', () => {
    projectsApi.update(5, { name: 'P2' })
    expect(mockPut).toHaveBeenCalledWith('/projects/5', { name: 'P2' })
  })
  it('delete DELETE /projects/{id}', () => {
    projectsApi.delete(5)
    expect(mockDelete).toHaveBeenCalledWith('/projects/5')
  })
  it('getById 别名', () => {
    projectsApi.getById(5)
    expect(mockGet).toHaveBeenCalledWith('/projects/5')
  })
  it('getStats GET /projects/stats', () => {
    projectsApi.getStats()
    expect(mockGet).toHaveBeenCalledWith('/projects/stats')
  })

  it('exportList GET blob', async () => {
    mockGet.mockResolvedValueOnce({ data: new Blob(['x']) })
    await projectsApi.exportList({ page: 1 })
    expect(mockGet).toHaveBeenCalledWith('/projects/export', {
      params: { page: 1 },
      responseType: 'blob',
    })
  })

  it('importData POST FormData', () => {
    const file = new File(['x'], 'a.xlsx')
    projectsApi.importData(file)
    const [url, fd, config] = mockPost.mock.calls[0]
    expect(url).toBe('/projects/import')
    expect(fd).toBeInstanceOf(FormData)
    expect(fd.get('file')).toBe(file)
    expect(config.headers['Content-Type']).toBe('multipart/form-data')
  })

  it('uploadFiles POST FormData with files[]', () => {
    const f1 = new File(['1'], 'a.txt')
    const f2 = new File(['2'], 'b.txt')
    projectsApi.uploadFiles(5, 'attachment', [f1, f2])
    const fd = mockPost.mock.calls[0][1]
    expect(mockPost.mock.calls[0][0]).toBe('/projects/5/files')
    expect(fd).toBeInstanceOf(FormData)
    expect(fd.get('category')).toBe('attachment')
    expect(fd.getAll('files')).toEqual([f1, f2])
  })

  it('listFiles GET /projects/{id}/files', () => {
    projectsApi.listFiles(5)
    expect(mockGet).toHaveBeenCalledWith('/projects/5/files')
  })

  it('getFileDownloadUrl 返回 URL 字符串', () => {
    expect(projectsApi.getFileDownloadUrl(5, 7)).toBe('/api/v1/projects/5/files/7/download')
  })

  it('deleteFile DELETE /projects/{id}/files/{fileId}', () => {
    projectsApi.deleteFile(5, 7)
    expect(mockDelete).toHaveBeenCalledWith('/projects/5/files/7')
  })

  it('projectApi 别名等同 projectsApi', () => {
    expect(projectApi).toBe(projectsApi)
  })
})

describe('api/schools', () => {
  beforeEach(() => vi.clearAllMocks())

  it('list GET /schools', () => {
    schoolsApi.list({ page: 1 })
    expect(mockGet).toHaveBeenCalledWith('/schools', { page: 1 })
  })
  it('get GET /schools/{id}', () => {
    schoolsApi.get(5)
    expect(mockGet).toHaveBeenCalledWith('/schools/5')
  })
  it('create POST /schools', () => {
    schoolsApi.create({ name: 'S' })
    expect(mockPost).toHaveBeenCalledWith('/schools', { name: 'S' })
  })
  it('update PUT /schools/{id}', () => {
    schoolsApi.update(5, { name: 'S2' })
    expect(mockPut).toHaveBeenCalledWith('/schools/5', { name: 'S2' })
  })
  it('delete DELETE /schools/{id}', () => {
    schoolsApi.delete(5)
    expect(mockDelete).toHaveBeenCalledWith('/schools/5')
  })
  it('schoolApi 别名等同 schoolsApi', () => {
    expect(schoolApi).toBe(schoolsApi)
  })
})
