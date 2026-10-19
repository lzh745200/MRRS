/**
 * api/orgGrants.ts 测试
 * 覆盖：4 个端点的 URL/载荷透传、`res.data ?? res` 两侧回退、
 * 导出时的响应头文件名解析与 blob 落盘。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'

const { mockGet, mockPost, mockPut, mockRequestPost, mockDownloadBlob, mockParseCd } = vi.hoisted(
  () => ({
    mockGet: vi.fn(),
    mockPost: vi.fn(),
    mockPut: vi.fn(),
    mockRequestPost: vi.fn(),
    mockDownloadBlob: vi.fn(),
    mockParseCd: vi.fn(() => 'grant-C001-v3.json'),
  })
)

vi.mock('@/api/request', () => ({
  default: { post: mockRequestPost },
  get: mockGet,
  post: mockPost,
  put: mockPut,
  getCsrfToken: vi.fn(() => Promise.resolve('test-csrf')),
  downloadBlob: mockDownloadBlob,
  parseContentDisposition: mockParseCd,
}))

import {
  exportGrantPackage,
  getOrgGrants,
  importGrantPackage,
  setOrgGrants,
} from '@/api/orgGrants'

describe('api/orgGrants', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockParseCd.mockReturnValue('grant-C001-v3.json')
  })

  it('getOrgGrants：GET /org-grants/{id}，优先取 data', async () => {
    mockGet.mockResolvedValue({ data: { organization_id: 1, grants: { projects: 'edit' } } })
    const res = await getOrgGrants(1)
    expect(mockGet).toHaveBeenCalledWith('/org-grants/1')
    expect(res.organization_id).toBe(1)
    expect(res.grants).toEqual({ projects: 'edit' })
  })

  it('getOrgGrants：无 data 包裹时直返响应', async () => {
    mockGet.mockResolvedValue({ organization_id: 2, grants: {} })
    const res = await getOrgGrants(2)
    expect(res.organization_id).toBe(2)
  })

  it('setOrgGrants：PUT /org-grants/{id}，载荷为 {grants}', async () => {
    mockPut.mockResolvedValue({ data: { organization_id: 1, grant_version: 2, modules: 1 } })
    const res = await setOrgGrants(1, { projects: 'view' })
    expect(mockPut).toHaveBeenCalledWith('/org-grants/1', { grants: { projects: 'view' } })
    expect(res.grant_version).toBe(2)
  })

  it('setOrgGrants：无 data 包裹时直返响应', async () => {
    mockPut.mockResolvedValue({ organization_id: 1, grant_version: 3, modules: 0 })
    const res = await setOrgGrants(1, {})
    expect(res.grant_version).toBe(3)
  })

  it('importGrantPackage：POST /org-grants/import，FormData 携带 file', async () => {
    mockPost.mockResolvedValue({ data: { org_code: 'C001', version: 1, modules: 2, signed: true } })
    const file = new File(['{}'], 'pkg.json', { type: 'application/json' })
    const res = await importGrantPackage(file)

    const [url, form] = mockPost.mock.calls[0]
    expect(url).toBe('/org-grants/import')
    expect(form).toBeInstanceOf(FormData)
    expect((form as FormData).get('file')).toBe(file)
    expect(res).toEqual({ org_code: 'C001', version: 1, modules: 2, signed: true })
  })

  it('importGrantPackage：无 data 包裹时直返响应', async () => {
    mockPost.mockResolvedValue({ org_code: 'C002', version: 5, modules: 1, signed: false })
    const res = await importGrantPackage(new File(['{}'], 'p.json'))
    expect(res.version).toBe(5)
  })

  it('exportGrantPackage：blob 请求 + 按响应头文件名落盘', async () => {
    const blob = new Blob(['{}'])
    mockRequestPost.mockResolvedValue({
      data: blob,
      headers: { 'content-disposition': 'attachment; filename="grant-C001-v3.json"' },
    })
    const name = await exportGrantPackage(7)

    expect(mockRequestPost).toHaveBeenCalledWith('/org-grants/7/export', null, {
      responseType: 'blob',
    })
    expect(mockParseCd).toHaveBeenCalled()
    expect(mockDownloadBlob).toHaveBeenCalledWith(blob, 'grant-C001-v3.json')
    expect(name).toBe('grant-C001-v3.json')
  })

  it('exportGrantPackage：解析失败时用兜底文件名', async () => {
    const blob = new Blob(['{}'])
    mockParseCd.mockReturnValue('grant-9.json')
    mockRequestPost.mockResolvedValue({ data: blob, headers: {} })
    const name = await exportGrantPackage(9)
    expect(name).toBe('grant-9.json')
    expect(mockDownloadBlob).toHaveBeenCalledWith(blob, 'grant-9.json')
  })
})
