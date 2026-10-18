/**
 * api/bigscreen.ts 单元测试（四指标 100%）
 *
 * 只验证薄封装：请求 URL / 参数透传、返回值透传（envelope 解包由 @/api/request 负责）。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'

const { mockGet } = vi.hoisted(() => ({ mockGet: vi.fn() }))

vi.mock('@/api/request', () => ({
  get: mockGet,
}))

import { getBigScreenFilters, getBigScreenOverview } from '@/api/bigscreen'

describe('api/bigscreen', () => {
  beforeEach(() => vi.clearAllMocks())

  it('getBigScreenFilters：GET /bigscreen/filters 并透传返回值', async () => {
    const body = { villages: [], schools: [], units: [] }
    mockGet.mockResolvedValueOnce(body)
    const result = await getBigScreenFilters()
    expect(mockGet).toHaveBeenCalledWith('/bigscreen/filters')
    expect(result).toBe(body)
  })

  it('getBigScreenOverview：GET /bigscreen/overview 透传 scope 参数与返回值', async () => {
    const body = { scope: { type: 'village' }, kpis: [] }
    mockGet.mockResolvedValueOnce(body)
    const params = { scope_type: 'village' as const, scope_id: 3, scope_name: '甲村', years: 5 }
    const result = await getBigScreenOverview(params)
    expect(mockGet).toHaveBeenCalledWith('/bigscreen/overview', params)
    expect(result).toBe(body)
  })

  it('getBigScreenOverview：全部对象只传 scope_type/years', async () => {
    mockGet.mockResolvedValueOnce({ scope: {}, kpis: [] })
    await getBigScreenOverview({ scope_type: 'all', years: 5 })
    expect(mockGet).toHaveBeenCalledWith('/bigscreen/overview', { scope_type: 'all', years: 5 })
  })

  it('getBigScreenOverview：单位按 scope_name 定位', async () => {
    mockGet.mockResolvedValueOnce({ scope: {}, kpis: [] })
    await getBigScreenOverview({ scope_type: 'unit', scope_name: '帮扶单位甲', years: 5 })
    expect(mockGet).toHaveBeenCalledWith('/bigscreen/overview', {
      scope_type: 'unit',
      scope_name: '帮扶单位甲',
      years: 5,
    })
  })
})
