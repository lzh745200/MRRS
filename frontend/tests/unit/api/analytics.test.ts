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
  getDashboard,
  getVillageAnalysis,
  getFundingTrends,
  getPerformanceMetrics,
  getComparisonAnalysis,
  generateReport,
  exportData,
  getRealtimeStats,
  getKpiSummary,
  getAnalyticsHealth,
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

  it('drillDown POST dimension + targetDimension', async () => {
    mockPost.mockResolvedValueOnce({ items: [] })
    await drillDown({
      dimension: 'province',
      value: '北京',
      targetDimension: 'city',
      filters: {},
    } as any)
    expect(mockPost).toHaveBeenCalledWith('/reports/analytics/drill-down', {
      dimension: 'province',
      value: '北京',
      target_dimension: 'city',
      filters: {},
    })
  })

  it('compareVillages POST with metrics joined', async () => {
    mockApiRequest.mockResolvedValueOnce({ items: [] })
    await compareVillages([1, 2], 2026, ['gdp', 'population'])
    expect(mockApiRequest).toHaveBeenCalledWith({
      method: 'POST',
      url: '/reports/analytics/compare-villages',
      data: [1, 2],
      params: { year: 2026, metrics: 'gdp,population' },
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

  it('getDashboard GET with date_range + filters', async () => {
    mockGet.mockResolvedValueOnce({})
    await getDashboard('30d', 'dept:X')
    expect(mockGet).toHaveBeenCalledWith('/analytics/dashboard', {
      date_range: '30d',
      filters: 'dept:X',
    })
  })

  it('getDashboard 无参', async () => {
    mockGet.mockResolvedValueOnce({})
    await getDashboard()
    expect(mockGet).toHaveBeenCalledWith('/analytics/dashboard', {
      date_range: undefined,
      filters: undefined,
    })
  })

  it('getVillageAnalysis GET 透传返回值', async () => {
    const body = { items: [1, 2] }
    mockGet.mockResolvedValueOnce(body)
    const r = await getVillageAnalysis()
    expect(mockGet).toHaveBeenCalledWith('/analytics/village-analysis')
    expect(r).toBe(body)
  })

  it('getFundingTrends 默认 5 年', async () => {
    mockGet.mockResolvedValueOnce({})
    await getFundingTrends()
    expect(mockGet).toHaveBeenCalledWith('/analytics/funding-trends', { years: 5 })
  })

  it('getFundingTrends 自定义年数', async () => {
    mockGet.mockResolvedValueOnce({})
    await getFundingTrends(3)
    expect(mockGet).toHaveBeenCalledWith('/analytics/funding-trends', { years: 3 })
  })

  it('getPerformanceMetrics GET', async () => {
    const body = { kpis: [] }
    mockGet.mockResolvedValueOnce(body)
    const r = await getPerformanceMetrics()
    expect(mockGet).toHaveBeenCalledWith('/analytics/performance-metrics')
    expect(r).toBe(body)
  })

  it('getComparisonAnalysis POST /analytics/comparison', async () => {
    const body = { result: 'ok' }
    mockPost.mockResolvedValueOnce(body)
    const data = { province: '四川', compare_type: 'year', target_value: '2026' }
    const r = await getComparisonAnalysis(data)
    expect(mockPost).toHaveBeenCalledWith('/analytics/comparison', data)
    expect(r).toBe(body)
  })

  it('generateReport POST /analytics/generate-report', async () => {
    mockPost.mockResolvedValueOnce({ url: '/reports/1.pdf' })
    const data = { report_type: 'yearly', start_date: '2026-01-01', end_date: '2026-12-31' }
    await generateReport(data)
    expect(mockPost).toHaveBeenCalledWith('/analytics/generate-report', data)
  })

  it('exportData POST /analytics/export 透传返回值', async () => {
    const body = { file: 'x.xlsx' }
    mockPost.mockResolvedValueOnce(body)
    const data = { report_type: 'summary' }
    const r = await exportData(data)
    expect(mockPost).toHaveBeenCalledWith('/analytics/export', data)
    expect(r).toBe(body)
  })

  it('getRealtimeStats GET', async () => {
    const body = { online: 3 }
    mockGet.mockResolvedValueOnce(body)
    const r = await getRealtimeStats()
    expect(mockGet).toHaveBeenCalledWith('/analytics/realtime-stats')
    expect(r).toBe(body)
  })

  it('getKpiSummary 默认 period=month', async () => {
    mockGet.mockResolvedValueOnce({})
    await getKpiSummary()
    expect(mockGet).toHaveBeenCalledWith('/analytics/kpi-summary', { period: 'month' })
  })

  it('getKpiSummary 自定义 period', async () => {
    mockGet.mockResolvedValueOnce({})
    await getKpiSummary('year')
    expect(mockGet).toHaveBeenCalledWith('/analytics/kpi-summary', { period: 'year' })
  })

  it('getAnalyticsHealth GET', async () => {
    const body = { status: 'up' }
    mockGet.mockResolvedValueOnce(body)
    const r = await getAnalyticsHealth()
    expect(mockGet).toHaveBeenCalledWith('/analytics/health')
    expect(r).toBe(body)
  })
})
