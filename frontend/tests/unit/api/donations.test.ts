import { describe, it, expect, vi, beforeEach } from 'vitest'

const { mockGet, mockPost, mockPut, mockDel } = vi.hoisted(() => ({
  mockGet: vi.fn(),
  mockPost: vi.fn(),
  mockPut: vi.fn(),
  mockDel: vi.fn(),
}))

vi.mock('@/api/request', () => ({
  get: mockGet,
  post: mockPost,
  put: mockPut,
  del: mockDel,
}))

import {
  DONATION_CATEGORIES,
  DONATION_DESTINATIONS,
  createDonation,
  deleteDonation,
  getDonation,
  getDonationStats,
  getDonations,
  updateDonation,
} from '@/api/donations'

describe('api/donations', () => {
  beforeEach(() => vi.clearAllMocks())

  it('类别/去向下拉常量与后端取值一致', () => {
    expect(DONATION_CATEGORIES.map((c) => c.value)).toEqual(['book', 'equipment', 'material'])
    expect(DONATION_DESTINATIONS.map((d) => d.value)).toEqual(['village', 'school', 'project'])
  })

  it('getDonations → GET /donations（带查询参数）', async () => {
    const body = { items: [{ id: 1, name: '图书' }], total: 1, page: 1, page_size: 20 }
    mockGet.mockResolvedValueOnce(body)
    const result = await getDonations({ page: 2, page_size: 10, keyword: '图书' })
    expect(mockGet).toHaveBeenCalledWith('/donations', { page: 2, page_size: 10, keyword: '图书' })
    expect(result).toBe(body)
  })

  it('getDonations → 缺省参数为空对象', async () => {
    mockGet.mockResolvedValueOnce({ items: [], total: 0, page: 1, page_size: 20 })
    await getDonations()
    expect(mockGet).toHaveBeenCalledWith('/donations', {})
  })

  it('getDonationStats → GET /donations/stats', async () => {
    const body = { total: 3, quantity: 10, valuation: 5 }
    mockGet.mockResolvedValueOnce(body)
    expect(await getDonationStats()).toBe(body)
    expect(mockGet).toHaveBeenCalledWith('/donations/stats')
  })

  it('getDonation → GET /donations/{id}', async () => {
    const body = { id: 7, name: '设备' }
    mockGet.mockResolvedValueOnce(body)
    expect(await getDonation(7)).toBe(body)
    expect(mockGet).toHaveBeenCalledWith('/donations/7')
  })

  it('createDonation → POST /donations', async () => {
    const payload = { name: '物资', category: 'material', destination_type: 'village' }
    mockPost.mockResolvedValueOnce({ id: 9 })
    expect(await createDonation(payload)).toEqual({ id: 9 })
    expect(mockPost).toHaveBeenCalledWith('/donations', payload)
  })

  it('updateDonation → PUT /donations/{id}', async () => {
    const payload = { name: '改名' }
    mockPut.mockResolvedValueOnce({ id: 9 })
    expect(await updateDonation(9, payload)).toEqual({ id: 9 })
    expect(mockPut).toHaveBeenCalledWith('/donations/9', payload)
  })

  it('deleteDonation → DELETE /donations/{id}', async () => {
    mockDel.mockResolvedValueOnce({ id: 9 })
    expect(await deleteDonation(9)).toEqual({ id: 9 })
    expect(mockDel).toHaveBeenCalledWith('/donations/9')
  })
})
