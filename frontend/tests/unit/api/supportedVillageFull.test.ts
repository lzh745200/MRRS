import { describe, it, expect, vi, beforeEach } from 'vitest'

// src/api/supportedVillage.ts 实际 import：
//   import request, { get, post, put, del, apiRequest } from '@/api/request'
//   import { downloadBlobAsFile } from '@/api/helpers/blobDownload'
// blobDownload.ts 又 import 了 parseContentDisposition / downloadBlob，
// 因此 mock 必须提供全部命名导出 + default。
// 命名 get(url, params)：第二参数直接是 params；用 rest 区分 get(url) 与 get(url, undefined)。
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
  post: (url: string, ...rest: any[]) => (rest.length > 0 ? mockPost(url, rest[0]) : mockPost(url)),
  put: (url: string, ...rest: any[]) => (rest.length > 0 ? mockPut(url, rest[0]) : mockPut(url)),
  del: (url: string) => mockDel(url),
  apiRequest: (...args: any[]) => mockApiRequest(...args),
  parseContentDisposition: (_headers: any, fallback = 'download') => fallback,
  downloadBlob: (...args: any[]) => mockDownloadBlob(...args),
  default: {
    get: (url: string, config?: any) => mockGet(url, config),
    post: (url: string, data?: any, config?: any) => mockPost(url, data, config),
  },
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

import {
  getFilterOptions,
  getChangeHistory,
  getYearlyData,
  copyYearData,
  validateYearlyData,
  saveYearlySectionData,
  saveIncomeData,
  saveIndustryData,
  saveInfrastructureData,
  saveEducationData,
  saveForceInvestmentData,
  savePartyBuildingData,
  saveMedicalData,
  saveConsumptionData,
  saveEmploymentData,
  savePopulationData,
  getSectionAttachments,
  saveSectionData,
  saveCommitteeData,
  uploadSectionAttachment,
  deleteSectionAttachment,
  getTransitionFunding,
  saveTransitionFunding,
  importSectionData,
  downloadAllTemplates,
  importAllSectionsData,
  getExportModules,
  getExportFormats,
  previewExport,
} from '@/api/supportedVillage'

describe('api/supportedVillage — 过滤/年度数据', () => {
  beforeEach(() => vi.clearAllMocks())

  it('getFilterOptions GET /supported-villages/filter-options', async () => {
    mockGet.mockResolvedValueOnce({ years: [2024] })
    const result = await getFilterOptions()
    expect(mockGet).toHaveBeenCalledWith('/supported-villages/filter-options')
    expect(result).toEqual({ years: [2024] })
  })

  it('getChangeHistory 调用后端变更历史接口', async () => {
    mockGet.mockResolvedValueOnce({ items: [{ id: 1 }], total: 1 })
    const result = await getChangeHistory(5)
    expect(mockGet).toHaveBeenCalledWith('/supported-villages/5/change-history')
    expect(result).toEqual({ items: [{ id: 1 }], total: 1 })
  })

  it('getYearlyData GET /{id}/yearly/{year} 并透传返回值', async () => {
    const body = { income: { total: 100 } }
    mockGet.mockResolvedValueOnce(body)
    const result = await getYearlyData(3, 2024)
    expect(mockGet).toHaveBeenCalledWith('/supported-villages/3/yearly/2024')
    expect(result).toBe(body)
  })

  it('copyYearData POST /{id}/yearly/copy with fromYear/toYear', async () => {
    mockPost.mockResolvedValueOnce({ copied: true })
    const result = await copyYearData(3, 2023, 2024)
    expect(mockPost).toHaveBeenCalledWith('/supported-villages/3/yearly/copy', {
      fromYear: 2023,
      toYear: 2024,
    })
    expect(result).toEqual({ copied: true })
  })

  it('validateYearlyData POST /{id}/yearly/{year}/validate', async () => {
    mockPost.mockResolvedValueOnce({ valid: true })
    const result = await validateYearlyData(3, 2024)
    expect(mockPost).toHaveBeenCalledWith('/supported-villages/3/yearly/2024/validate')
    expect(result).toEqual({ valid: true })
  })

  it('saveYearlySectionData POST /{id}/yearly/{year}/{section}', async () => {
    mockPost.mockResolvedValueOnce({ saved: true })
    const result = await saveYearlySectionData(1, 2024, 'income', { total: 5 })
    expect(mockPost).toHaveBeenCalledWith('/supported-villages/1/yearly/2024/income', { total: 5 })
    expect(result).toEqual({ saved: true })
  })

  it('10 个 save* 兼容别名各自映射到正确 section', async () => {
    mockPost.mockResolvedValue({ ok: true })
    const cases: Array<[Function, string]> = [
      [saveIncomeData, 'income'],
      [saveIndustryData, 'industry'],
      [saveInfrastructureData, 'infrastructure'],
      [saveEducationData, 'education'],
      [saveForceInvestmentData, 'force-investment'],
      [savePartyBuildingData, 'party-building'],
      [saveMedicalData, 'medical'],
      [saveConsumptionData, 'consumption'],
      [saveEmploymentData, 'employment'],
      [savePopulationData, 'population'],
    ]
    for (const [fn, section] of cases) {
      mockPost.mockClear()
      await fn(2, 2024, { v: 1 })
      expect(mockPost).toHaveBeenCalledWith(`/supported-villages/2/yearly/2024/${section}`, {
        v: 1,
      })
    }
  })
})

describe('api/supportedVillage — 板块与附件', () => {
  beforeEach(() => vi.clearAllMocks())

  it('getSectionAttachments 优先取 items', async () => {
    mockGet.mockResolvedValueOnce({ items: [{ id: 1 }], data: [{ id: 2 }] })
    const result = await getSectionAttachments(1, 'income')
    expect(mockGet).toHaveBeenCalledWith('/supported-villages/1/sections/income/attachments')
    expect(result).toEqual([{ id: 1 }])
  })

  it('getSectionAttachments 无 items 时回退 data，再回退 []', async () => {
    mockGet.mockResolvedValueOnce({ data: [{ id: 2 }] })
    expect(await getSectionAttachments(1, 'income')).toEqual([{ id: 2 }])
    mockGet.mockResolvedValueOnce({})
    expect(await getSectionAttachments(1, 'income')).toEqual([])
  })

  it('saveSectionData POST /{id}/yearly/{year}/{section}', async () => {
    mockPost.mockResolvedValueOnce({ ok: 1 })
    await saveSectionData(1, 2024, 'industry', { x: 1 })
    expect(mockPost).toHaveBeenCalledWith('/supported-villages/1/yearly/2024/industry', { x: 1 })
  })

  it('saveCommitteeData POST /{id}/committee', async () => {
    mockPost.mockResolvedValueOnce({ ok: 1 })
    await saveCommitteeData(1, { members: 3 })
    expect(mockPost).toHaveBeenCalledWith('/supported-villages/1/committee', { members: 3 })
  })

  it('uploadSectionAttachment apiRequest multipart FormData', async () => {
    mockApiRequest.mockResolvedValueOnce({ id: 9 })
    const file = new File(['x'], 'proof.pdf')
    const result = await uploadSectionAttachment(1, 'income', file)
    expect(mockApiRequest).toHaveBeenCalledWith({
      method: 'POST',
      url: '/supported-villages/1/sections/income/attachments',
      data: expect.any(FormData),
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    const fd = mockApiRequest.mock.calls[0][0].data as FormData
    expect(fd.get('file')).toBe(file)
    expect(result).toEqual({ id: 9 })
  })

  it('deleteSectionAttachment DELETE /{id}/sections/{section}/attachments/{aid}', async () => {
    mockDel.mockResolvedValueOnce({ deleted: true })
    const result = await deleteSectionAttachment(1, 'income', 9)
    expect(mockDel).toHaveBeenCalledWith('/supported-villages/1/sections/income/attachments/9')
    expect(result).toEqual({ deleted: true })
  })
})

describe('api/supportedVillage — 衔接资金/导入导出', () => {
  beforeEach(() => vi.clearAllMocks())

  it('getTransitionFunding GET /{id}/transition-funding', async () => {
    mockGet.mockResolvedValueOnce({ amount: 50 })
    const result = await getTransitionFunding(1)
    expect(mockGet).toHaveBeenCalledWith('/supported-villages/1/transition-funding')
    expect(result).toEqual({ amount: 50 })
  })

  it('saveTransitionFunding POST /{id}/transition-funding', async () => {
    mockPost.mockResolvedValueOnce({ ok: 1 })
    await saveTransitionFunding(1, { amount: 50 })
    expect(mockPost).toHaveBeenCalledWith('/supported-villages/1/transition-funding', {
      amount: 50,
    })
  })

  it('importSectionData apiRequest 带 year/section_key params 与 FormData', async () => {
    mockApiRequest.mockResolvedValueOnce({ success_rows: 10 })
    const file = new File(['x'], 'income.xlsx')
    const result = await importSectionData(1, 2024, 'income', file)
    expect(mockApiRequest).toHaveBeenCalledWith({
      method: 'POST',
      url: '/supported-villages/1/sections/import',
      params: { year: 2024, section_key: 'income' },
      data: expect.any(FormData),
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    const fd = mockApiRequest.mock.calls[0][0].data as FormData
    expect(fd.get('file')).toBe(file)
    expect(result).toEqual({ success_rows: 10 })
  })

  it('downloadAllTemplates 走 request.get blob 并触发 downloadBlob（解析文件名）', async () => {
    mockGet.mockResolvedValueOnce({
      data: new Blob(['x']),
      headers: { 'content-disposition': 'attachment; filename="templates_2024.xlsx"' },
    })
    await downloadAllTemplates(2024)
    expect(mockGet).toHaveBeenCalledWith('/supported-villages/templates/all', {
      params: { year: 2024 },
      responseType: 'blob',
    })
    expect(mockDownloadBlob).toHaveBeenCalledWith(expect.any(Blob), 'templates_2024.xlsx')
  })

  it('downloadAllTemplates 无文件名头时用兜底文件名', async () => {
    mockGet.mockResolvedValueOnce({ data: new Blob(['x']), headers: {} })
    await downloadAllTemplates()
    expect(mockDownloadBlob).toHaveBeenCalledWith(expect.any(Blob), '全部板块模板.xlsx')
  })

  it('importAllSectionsData apiRequest /sections/import-all with year param', async () => {
    mockApiRequest.mockResolvedValueOnce({ success_rows: 99 })
    const file = new File(['x'], 'all.xlsx')
    const result = await importAllSectionsData(1, 2024, file)
    expect(mockApiRequest).toHaveBeenCalledWith({
      method: 'POST',
      url: '/supported-villages/1/sections/import-all',
      params: { year: 2024 },
      data: expect.any(FormData),
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    const fd = mockApiRequest.mock.calls[0][0].data as FormData
    expect(fd.get('file')).toBe(file)
    expect(result).toEqual({ success_rows: 99 })
  })

  it('getExportModules GET /supported-villages/export/modules', async () => {
    mockGet.mockResolvedValueOnce(['income'])
    const result = await getExportModules()
    expect(mockGet).toHaveBeenCalledWith('/supported-villages/export/modules')
    expect(result).toEqual(['income'])
  })

  it('getExportFormats GET /supported-villages/export/formats', async () => {
    mockGet.mockResolvedValueOnce(['xlsx'])
    const result = await getExportFormats()
    expect(mockGet).toHaveBeenCalledWith('/supported-villages/export/formats')
    expect(result).toEqual(['xlsx'])
  })

  it('previewExport GET /supported-villages/export/preview with params', async () => {
    mockGet.mockResolvedValueOnce({ rows: [] })
    const result = await previewExport({ year: 2024 })
    expect(mockGet).toHaveBeenCalledWith('/supported-villages/export/preview', { year: 2024 })
    expect(result).toEqual({ rows: [] })
  })
})
