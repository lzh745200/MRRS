import { describe, it, expect, vi, beforeEach } from 'vitest'

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  del: vi.fn(),
  apiRequest: vi.fn(),
  requestGet: vi.fn(),
}))

vi.mock('@/api/request', () => ({
  default: {
    get: mocks.requestGet,
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
  get: mocks.get,
  post: mocks.post,
  put: mocks.put,
  del: mocks.del,
  apiRequest: mocks.apiRequest,
  // @/api/helpers/blobDownload 依赖这两个导出
  parseContentDisposition: vi.fn(() => 'download.xlsx'),
  downloadBlob: vi.fn(),
}))

import { projectsApi, projectApi } from '@/api/projects'

describe('projectsApi', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('list calls GET /projects', async () => {
    mocks.get.mockResolvedValueOnce({ items: [] })
    await projectsApi.list({ page: 1 })
    expect(mocks.get).toHaveBeenCalledWith('/projects', { page: 1 })
  })

  it('get calls GET /projects/:id', async () => {
    mocks.get.mockResolvedValueOnce({ id: 1 })
    await projectsApi.get(1)
    expect(mocks.get).toHaveBeenCalledWith('/projects/1')
  })

  it('create calls POST /projects', async () => {
    mocks.post.mockResolvedValueOnce({ id: 1 })
    await projectsApi.create({ name: 'New' })
    expect(mocks.post).toHaveBeenCalledWith('/projects', { name: 'New' })
  })

  it('update calls PUT /projects/:id', async () => {
    mocks.put.mockResolvedValueOnce({ id: 1 })
    await projectsApi.update(1, { name: 'Updated' })
    expect(mocks.put).toHaveBeenCalledWith('/projects/1', { name: 'Updated' })
  })

  it('delete calls DELETE /projects/:id', async () => {
    mocks.del.mockResolvedValueOnce({})
    await projectsApi.delete(1)
    expect(mocks.del).toHaveBeenCalledWith('/projects/1')
  })

  it('getById calls GET /projects/:id', async () => {
    mocks.get.mockResolvedValueOnce({ id: 1 })
    await projectsApi.getById(1)
    expect(mocks.get).toHaveBeenCalledWith('/projects/1')
  })

  it('getStats calls GET /projects/stats', async () => {
    mocks.get.mockResolvedValueOnce({})
    await projectsApi.getStats()
    expect(mocks.get).toHaveBeenCalledWith('/projects/stats')
  })

  it('exportList calls with responseType blob', async () => {
    mocks.requestGet.mockResolvedValueOnce({ data: new Blob(['data']), headers: {} })
    await projectsApi.exportList({ format: 'xlsx' })
    expect(mocks.requestGet).toHaveBeenCalledWith('/projects/export', {
      params: { format: 'xlsx' },
      responseType: 'blob',
    })
  })

  it('importData sends FormData', async () => {
    mocks.post.mockResolvedValueOnce({ count: 5 })
    const file = new File(['data'], 'test.xlsx')
    await projectsApi.importData(file)
    expect(mocks.post).toHaveBeenCalled()
    const callArgs = mocks.post.mock.calls[0]
    expect(callArgs[0]).toBe('/projects/import')
    expect(callArgs[1]).toBeInstanceOf(FormData)
    expect(callArgs[2]?.headers?.['Content-Type']).toBe('multipart/form-data')
  })

  it('uploadFiles sends FormData with multiple files', async () => {
    mocks.post.mockResolvedValueOnce({ files: [] })
    const files = [new File(['a'], 'a.txt'), new File(['b'], 'b.txt')]
    await projectsApi.uploadFiles(1, 'document', files)
    expect(mocks.post).toHaveBeenCalled()
    const callArgs = mocks.post.mock.calls[0]
    expect(callArgs[0]).toBe('/projects/1/files')
    expect(callArgs[1]).toBeInstanceOf(FormData)
    expect(callArgs[1].get('category')).toBe('document')
  })

  it('listFiles calls GET /projects/:id/files', async () => {
    mocks.get.mockResolvedValueOnce([])
    await projectsApi.listFiles(1)
    expect(mocks.get).toHaveBeenCalledWith('/projects/1/files')
  })

  it('deleteFile calls DELETE', async () => {
    mocks.del.mockResolvedValueOnce({})
    await projectsApi.deleteFile(1, 2)
    expect(mocks.del).toHaveBeenCalledWith('/projects/1/files/2')
  })

  it('previewFile calls apiRequest blob', async () => {
    mocks.apiRequest.mockResolvedValueOnce(new Blob(['pdf']))
    await projectsApi.previewFile(1, 2)
    expect(mocks.apiRequest).toHaveBeenCalledWith({
      method: 'GET',
      url: '/projects/1/files/2/preview',
      responseType: 'blob',
    })
  })

  it('getChangeHistory calls GET', async () => {
    mocks.get.mockResolvedValueOnce([])
    await projectsApi.getChangeHistory(1)
    expect(mocks.get).toHaveBeenCalledWith('/projects/1/history/changes')
  })

  it('getFunds calls GET', async () => {
    mocks.get.mockResolvedValueOnce([])
    await projectsApi.getFunds(1)
    expect(mocks.get).toHaveBeenCalledWith('/projects/1/funds')
  })

  it('addFund calls POST', async () => {
    mocks.post.mockResolvedValueOnce({ id: 1 })
    await projectsApi.addFund(1, { amount: 1000 })
    expect(mocks.post).toHaveBeenCalledWith('/projects/1/funds', { amount: 1000 })
  })

  it('getTasks calls GET', async () => {
    mocks.get.mockResolvedValueOnce([])
    await projectsApi.getTasks(1)
    expect(mocks.get).toHaveBeenCalledWith('/projects/1/tasks')
  })

  it('createTask calls POST', async () => {
    mocks.post.mockResolvedValueOnce({ id: 1 })
    await projectsApi.createTask(1, { title: 'Task' })
    expect(mocks.post).toHaveBeenCalledWith('/projects/1/tasks', { title: 'Task' })
  })

  it('updateTask calls PUT', async () => {
    mocks.put.mockResolvedValueOnce({ id: 1 })
    await projectsApi.updateTask(1, 2, { status: 'done' })
    expect(mocks.put).toHaveBeenCalledWith('/projects/1/tasks/2', { status: 'done' })
  })

  it('deleteTask calls DELETE', async () => {
    mocks.del.mockResolvedValueOnce({})
    await projectsApi.deleteTask(1, 2)
    expect(mocks.del).toHaveBeenCalledWith('/projects/1/tasks/2')
  })

  it('projectApi is an alias of projectsApi', () => {
    expect(projectApi).toBe(projectsApi)
  })
})
