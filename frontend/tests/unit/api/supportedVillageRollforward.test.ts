/**
 * api/supportedVillage —— 年度数据滚动填报（prefill / rollforward）接口测试
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'

const { mockGet, mockPost } = vi.hoisted(() => ({
  mockGet: vi.fn(),
  mockPost: vi.fn(),
}))

vi.mock('@/api/request', () => ({
  get: (url: string, ...rest: any[]) => (rest.length > 0 ? mockGet(url, rest[0]) : mockGet(url)),
  post: (url: string, ...rest: any[]) => (rest.length > 0 ? mockPost(url, rest[0]) : mockPost(url)),
  put: vi.fn(),
  del: vi.fn(),
  apiRequest: vi.fn(),
  parseContentDisposition: vi.fn(),
  downloadBlob: vi.fn(),
  getCsrfToken: vi.fn(() => Promise.resolve('test-csrf')),
  default: { get: vi.fn(), post: vi.fn() },
}))

vi.mock('@/api/helpers/blobDownload', () => ({
  downloadBlobAsFile: vi.fn(),
}))

import { getYearlyPrefill, rollforwardYearlyData } from '@/api/supportedVillage'

describe('api/supportedVillage 年度滚动填报', () => {
  beforeEach(() => vi.clearAllMocks())

  it('getYearlyPrefill：缺省来源年份时不传查询参数', async () => {
    const payload = { villageId: 3, year: 2026, fromYear: 2025, sections: [] }
    mockGet.mockResolvedValueOnce(payload)
    const result = await getYearlyPrefill(3, 2026)
    expect(mockGet).toHaveBeenCalledWith('/supported-villages/3/yearly/2026/prefill', undefined)
    expect(result).toBe(payload)
  })

  it('getYearlyPrefill：显式来源年份透传 from_year', async () => {
    mockGet.mockResolvedValueOnce({ fromYear: 2024 })
    const result = await getYearlyPrefill(3, 2026, 2024)
    expect(mockGet).toHaveBeenCalledWith('/supported-villages/3/yearly/2026/prefill', {
      from_year: 2024,
    })
    expect(result).toEqual({ fromYear: 2024 })
  })

  it('rollforwardYearlyData：默认只填空语义（overwrite=false）', async () => {
    const payload = { appliedFields: 2, appliedSections: ['income'] }
    mockPost.mockResolvedValueOnce(payload)
    const result = await rollforwardYearlyData(3, 2026, { sectionKeys: ['income'] })
    expect(mockPost).toHaveBeenCalledWith('/supported-villages/3/yearly/2026/rollforward', {
      section_keys: ['income'],
      from_year: undefined,
      overwrite: false,
    })
    expect(result).toBe(payload)
  })

  it('rollforwardYearlyData：覆盖语义与来源年份透传', async () => {
    mockPost.mockResolvedValueOnce({ appliedFields: 0 })
    await rollforwardYearlyData(3, 2026, {
      sectionKeys: ['income', 'population'],
      fromYear: 2024,
      overwrite: true,
    })
    expect(mockPost).toHaveBeenCalledWith('/supported-villages/3/yearly/2026/rollforward', {
      section_keys: ['income', 'population'],
      from_year: 2024,
      overwrite: true,
    })
  })
})
