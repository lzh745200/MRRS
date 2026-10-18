/**
 * api/consumption.ts 测试（四指标 100%）
 *
 * 覆盖：列表/统计/CRUD 端点与参数、导出（xlsx/csv）GET blob + Content-Disposition 兜底名、
 * 导出查询参数的可选字段裁剪分支。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'

const { mockGet, mockPost, mockPut, mockDel, mockRequestGet, mockDownload } = vi.hoisted(() => ({
  mockGet: vi.fn(),
  mockPost: vi.fn(),
  mockPut: vi.fn(),
  mockDel: vi.fn(),
  mockRequestGet: vi.fn(),
  mockDownload: vi.fn(),
}))

vi.mock('@/api/request', () => ({
  get: (...a: any[]) => mockGet(...a),
  post: (...a: any[]) => mockPost(...a),
  put: (...a: any[]) => mockPut(...a),
  del: (...a: any[]) => mockDel(...a),
  default: { get: (url: string, config?: any) => mockRequestGet(url, config) },
  getCsrfToken: vi.fn(() => Promise.resolve('test-csrf')),
}))

vi.mock('@/api/helpers/blobDownload', () => ({
  downloadBlobAsFile: (...a: any[]) => mockDownload(...a),
}))

import {
  CONSUMPTION_CATEGORY_LABELS,
  CONSUMPTION_SELLER_TYPE_LABELS,
  getConsumptionRecords,
  getConsumptionStatistics,
  createConsumptionRecord,
  updateConsumptionRecord,
  deleteConsumptionRecord,
  exportConsumption,
} from '@/api/consumption'

describe('api/consumption — 列表/统计/CRUD', () => {
  beforeEach(() => vi.clearAllMocks())

  it('getConsumptionRecords：无参/筛选参数透传', async () => {
    const list = { items: [{ id: 1 }], total: 1 }
    mockGet.mockResolvedValueOnce(list)
    expect(await getConsumptionRecords()).toBe(list)
    expect(mockGet).toHaveBeenCalledWith('/consumption', undefined)

    const params = {
      page: 1,
      page_size: 20,
      year: 2025,
      category: 'agriculture' as const,
      village_id: 8,
      keyword: '蜂蜜',
    }
    mockGet.mockResolvedValueOnce({ items: [], total: 0 })
    await getConsumptionRecords(params)
    expect(mockGet).toHaveBeenLastCalledWith('/consumption', params)
  })

  it('getConsumptionStatistics：年省略/null → 无参；有年份 → { year }', async () => {
    mockGet.mockResolvedValue({ total_amount: 0 })
    await getConsumptionStatistics()
    expect(mockGet).toHaveBeenLastCalledWith('/consumption/statistics', undefined)

    await getConsumptionStatistics(null)
    expect(mockGet).toHaveBeenLastCalledWith('/consumption/statistics', undefined)

    await getConsumptionStatistics(2025)
    expect(mockGet).toHaveBeenLastCalledWith('/consumption/statistics', { year: 2025 })
  })

  it('create/update/delete 端点与载荷', async () => {
    mockPost.mockResolvedValueOnce({ id: 3 })
    const payload = {
      category: 'agriculture' as const,
      item_name: '土蜂蜜',
      amount: 1200,
      year: 2025,
    }
    expect(await createConsumptionRecord(payload)).toEqual({ id: 3 })
    expect(mockPost).toHaveBeenCalledWith('/consumption', payload)

    mockPut.mockResolvedValueOnce({ id: 3 })
    await updateConsumptionRecord(3, { amount: 1300 })
    expect(mockPut).toHaveBeenCalledWith('/consumption/3', { amount: 1300 })

    mockDel.mockResolvedValueOnce(true)
    expect(await deleteConsumptionRecord(3)).toBe(true)
    expect(mockDel).toHaveBeenCalledWith('/consumption/3')
  })
})

describe('api/consumption — 导出', () => {
  beforeEach(() => vi.clearAllMocks())

  it('全量筛选参数：year/category/village_id/keyword 全部进入 query', async () => {
    mockDownload.mockImplementationOnce(async (requestFn: () => Promise<any>) => {
      await requestFn()
    })
    mockRequestGet.mockResolvedValueOnce({ data: new Blob(['x']), headers: {} })

    await exportConsumption({
      format: 'xlsx',
      year: 2025,
      category: 'livestock',
      village_id: 9,
      keyword: '鸡蛋',
    })

    expect(mockRequestGet).toHaveBeenCalledWith('/consumption/export', {
      params: {
        format: 'xlsx',
        year: 2025,
        category: 'livestock',
        village_id: 9,
        keyword: '鸡蛋',
      },
      responseType: 'blob',
    })
    expect(mockDownload).toHaveBeenCalledWith(expect.any(Function), {
      fallbackFileName: '消费帮扶台账.xlsx',
    })
  })

  it('可选字段为空/undefined 时裁剪，csv 兜底文件名按格式', async () => {
    mockDownload.mockImplementationOnce(async (requestFn: () => Promise<any>) => {
      await requestFn()
    })
    mockRequestGet.mockResolvedValueOnce({ data: new Blob(['x']), headers: {} })

    await exportConsumption({ format: 'csv', year: null, category: '', keyword: '' })

    expect(mockRequestGet).toHaveBeenCalledWith('/consumption/export', {
      params: { format: 'csv' },
      responseType: 'blob',
    })
    expect(mockDownload).toHaveBeenCalledWith(expect.any(Function), {
      fallbackFileName: '消费帮扶台账.csv',
    })
  })
})

describe('api/consumption — 标签常量', () => {
  it('品类与供货方类型中文标签齐全', () => {
    expect(CONSUMPTION_CATEGORY_LABELS).toEqual({
      agriculture: '农产品',
      livestock: '畜禽',
      handicraft: '手工',
      other: '其他',
    })
    expect(CONSUMPTION_SELLER_TYPE_LABELS).toEqual({
      farmer: '农户',
      cooperative: '合作社',
      enterprise: '企业',
    })
  })
})
