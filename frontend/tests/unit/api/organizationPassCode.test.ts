import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockGet = vi.fn()
const mockPost = vi.fn()
const mockDel = vi.fn()
const mockApiRequest = vi.fn()

vi.mock('@/api/request', () => ({
  get: (...args: any[]) => mockGet(...args),
  post: (...args: any[]) => mockPost(...args),
  del: (...args: any[]) => mockDel(...args),
  // downloadBlobAsFile（src/api/helpers/blobDownload.ts）内部从 '@/api/request'
  // 导入 downloadBlob / parseContentDisposition，需一并提供
  downloadBlob: (blob: Blob, filename: string) => {
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    link.click()
  },
  parseContentDisposition: vi.fn(() => 'download.xlsx'),
  // W5-T5：exportOrganizationPassCodes 改用具名 apiRequest<Blob>（返回值即 Blob），
  // 不再依赖默认导出的裸 axios 实例
  apiRequest: (...args: any[]) => mockApiRequest(...args),
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

import {
  getOrganizationVerificationCode,
  createOrganizationPassCode,
  getOrganizationPassCodeList,
  exportOrganizationPassCodes,
  deleteOrganizationPassCode,
} from '@/api/organizationPassCode'

describe('api/organizationPassCode', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('getOrganizationVerificationCode GET /machine-code/organization/{id}/verification-code', () => {
    getOrganizationVerificationCode(3)
    expect(mockGet).toHaveBeenCalledWith('/machine-code/organization/3/verification-code')
  })

  it('createOrganizationPassCode POST /machine-code/organization/create', () => {
    createOrganizationPassCode({
      organization_id: 1,
      verification_code: 'VC',
      allow_subordinate_generation: true,
    })
    expect(mockPost).toHaveBeenCalledWith('/machine-code/organization/create', {
      organization_id: 1,
      verification_code: 'VC',
      allow_subordinate_generation: true,
    })
  })

  it('getOrganizationPassCodeList GET /machine-code/organization/list with params', () => {
    getOrganizationPassCodeList({ organization_id: 1, status: 'active', page: 1, page_size: 10 })
    expect(mockGet).toHaveBeenCalledWith('/machine-code/organization/list', {
      organization_id: 1,
      status: 'active',
      page: 1,
      page_size: 10,
    })
  })

  it('getOrganizationPassCodeList 无参', () => {
    getOrganizationPassCodeList()
    expect(mockGet).toHaveBeenCalledWith('/machine-code/organization/list', undefined)
  })

  it('exportOrganizationPassCodes 触发下载', async () => {
    mockApiRequest.mockResolvedValueOnce(new Blob(['test']))
    const createObjectURL = vi.fn(() => 'blob:fake')
    const revokeObjectURL = vi.fn()
    const click = vi.fn()
    URL.createObjectURL = createObjectURL
    URL.revokeObjectURL = revokeObjectURL
    const a = document.createElement('a')
    a.click = click
    const realCreate = document.createElement.bind(document)
    vi.spyOn(document, 'createElement').mockImplementation((tag: any) => {
      if (tag === 'a') return a
      return realCreate(tag)
    })
    await exportOrganizationPassCodes({ status: 'active' })
    expect(mockApiRequest).toHaveBeenCalledWith({
      method: 'GET',
      url: '/machine-code/organization/export',
      params: { status: 'active' },
      responseType: 'blob',
    })
    expect(click).toHaveBeenCalled()
  })

  it('deleteOrganizationPassCode DELETE /machine-code/organization/{id}', () => {
    deleteOrganizationPassCode(5)
    expect(mockDel).toHaveBeenCalledWith('/machine-code/organization/5')
  })
})
