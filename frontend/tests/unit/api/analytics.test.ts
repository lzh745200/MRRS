import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockGet = vi.fn()
const mockPost = vi.fn()
const mockApiRequest = vi.fn()

vi.mock('@/api/request', () => ({
  default: {
    get: (...args: any[]) => mockGet(...args),
    post: (...args: any[]) => mockPost(...args),
  },
  get: (...args: any[]) => mockGet(...args),
  post: (...args: any[]) => mockPost(...args),
  apiRequest: (...args: any[]) => mockApiRequest(...args),
  getCsrfToken: vi.fn(() => Promise.resolve('test-csrf')),
}))

import {
  getFilterOptions,
  filterVillages,
  drillDown,
  compareVillages,
  compareYears,
  getSummaryStatistics,
} from '@/api/analytics'

describe('api/analytics', () => {
  beforeEach(() => vi.clearAllMocks())

  it('getFilterOptions GET filter-options', async () => {
    mockGet.mockResolvedValueOnce({ departments: [] })
    await getFilterOptions()
    expect(mockGet).toHaveBeenCalledWith('/reports/analytics/filter-options')
  })

  it('filterVillages POST with default page=1 size=20', async () => {
    mockApiRequest.mockResolvedValueOnce({
      total: 0,
      page: 1,
      page_size: 20,
      pages: 0,
      items: [],
    })
    await filterVillages({ department: 'X' } as any)
    expect(mockApiRequest).toHaveBeenCalledWith({
      method: 'POST',
      url: '/reports/analytics/filter',
      data: { department: 'X' },
      params: { page: 1, page_size: 20 },
    })
  })

  it('filterVillages 自定义 page + size', async () => {
    mockApiRequest.mockResolvedValueOnce({
      total: 0,
      page: 2,
      page_size: 50,
      pages: 0,
      items: [],
    })
    const r = await filterVillages({} as any, 2, 50)
    expect(mockApiRequest.mock.calls[0][0].params).toEqual({ page: 2, page_size: 50 })
    expect(r.pageSize).toBe(50)
  })

  it('drillDown POST dimension + value（后端无 target_dimension）', async () => {
    mockPost.mockResolvedValueOnce({ items: [] })
    await drillDown({
      dimension: 'province',
      value: '北京',
      filters: {},
    } as any)
    expect(mockPost).toHaveBeenCalledWith('/reports/analytics/drill-down', {
      dimension: 'province',
      value: '北京',
      filters: {},
    })
  })

  it('compareVillages POST，metrics 走重复查询键（后端 List[str]）', async () => {
    mockApiRequest.mockResolvedValueOnce({ items: [] })
    await compareVillages([1, 2], 2026, ['gdp', 'population'])
    expect(mockApiRequest).toHaveBeenCalledWith({
      method: 'POST',
      url: '/reports/analytics/compare-villages',
      data: [1, 2],
      params: { year: 2026, metrics: ['gdp', 'population'] },
      // indexes:null → ?metrics=gdp&metrics=population（axios 默认会序列化成 metrics[]）
      paramsSerializer: { indexes: null },
    })
  })

  it('compareVillages 无 metrics', async () => {
    mockApiRequest.mockResolvedValueOnce({ items: [] })
    await compareVillages([1], 2026)
    expect(mockApiRequest.mock.calls[0][0].params.metrics).toBeUndefined()
  })

  it('compareYears GET with years joined', async () => {
    mockGet.mockResolvedValueOnce({ items: [] })
    await compareYears(1, [2024, 2025, 2026], ['gdp'])
    expect(mockGet).toHaveBeenCalledWith('/reports/analytics/compare-years/1', {
      years: '2024,2025,2026',
      metrics: 'gdp',
    })
  })

  it('getSummaryStatistics GET with snake_case params', async () => {
    mockGet.mockResolvedValueOnce({ total: 0 })
    await getSummaryStatistics({
      year: 2026,
      department: 'X',
      isThreeRegions: true,
      isKeyCounty: false,
    })
    expect(mockGet).toHaveBeenCalledWith('/reports/analytics/summary', {
      year: 2026,
      department: 'X',
      is_three_regions: true,
      is_key_county: false,
    })
  })

  it('getSummaryStatistics 无参', async () => {
    mockGet.mockResolvedValueOnce({ total: 0 })
    await getSummaryStatistics()
    expect(mockGet).toHaveBeenCalledWith('/reports/analytics/summary', {
      year: undefined,
      department: undefined,
      is_three_regions: undefined,
      is_key_county: undefined,
    })
  })
})
