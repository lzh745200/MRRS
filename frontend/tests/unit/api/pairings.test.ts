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
  getCsrfToken: vi.fn(() => Promise.resolve('test-csrf')),
}))

import {
  createPairing,
  createVisit,
  deletePairing,
  deleteVisit,
  getPairing,
  getPairingStats,
  getPairings,
  getVisits,
  updatePairing,
  updateVisit,
} from '@/api/pairings'

describe('api/pairings', () => {
  beforeEach(() => vi.clearAllMocks())

  it('getPairings → GET /pairings（带查询参数）', async () => {
    const body = { items: [{ id: 1, title: '对口帮扶' }], total: 1, page: 1, page_size: 20 }
    mockGet.mockResolvedValueOnce(body)
    const result = await getPairings({ page: 2, page_size: 10, keyword: '帮扶' })
    expect(mockGet).toHaveBeenCalledWith('/pairings', { page: 2, page_size: 10, keyword: '帮扶' })
    expect(result).toBe(body)
  })

  it('getPairings → 缺省参数为空对象', async () => {
    mockGet.mockResolvedValueOnce({ items: [], total: 0, page: 1, page_size: 20 })
    await getPairings()
    expect(mockGet).toHaveBeenCalledWith('/pairings', {})
  })

  it('getPairingStats → GET /pairings/stats', async () => {
    const body = {
      total: 3,
      active: 2,
      ended: 1,
      villages: 1,
      schools: 1,
      students: 1,
      visits: 5,
    }
    mockGet.mockResolvedValueOnce(body)
    const result = await getPairingStats()
    expect(mockGet).toHaveBeenCalledWith('/pairings/stats')
    expect(result).toBe(body)
  })

  it('getPairing → GET /pairings/{id}', async () => {
    const body = { id: 7, title: '助学' }
    mockGet.mockResolvedValueOnce(body)
    const result = await getPairing(7)
    expect(mockGet).toHaveBeenCalledWith('/pairings/7')
    expect(result).toBe(body)
  })

  it('createPairing → POST /pairings', async () => {
    const payload = { subject_type: 'unit', subject_name: '某单位', title: '对口帮扶' }
    mockPost.mockResolvedValueOnce({ id: 9, ...payload })
    const result = await createPairing(payload)
    expect(mockPost).toHaveBeenCalledWith('/pairings', payload)
    expect(result.id).toBe(9)
  })

  it('updatePairing → PUT /pairings/{id}', async () => {
    mockPut.mockResolvedValueOnce({ id: 9, title: '新事项' })
    const result = await updatePairing(9, { title: '新事项' })
    expect(mockPut).toHaveBeenCalledWith('/pairings/9', { title: '新事项' })
    expect(result.title).toBe('新事项')
  })

  it('deletePairing → DELETE /pairings/{id}', async () => {
    mockDel.mockResolvedValueOnce({ id: 9 })
    const result = await deletePairing(9)
    expect(mockDel).toHaveBeenCalledWith('/pairings/9')
    expect(result).toEqual({ id: 9 })
  })

  it('getVisits → GET /pairings/{id}/visits（带分页参数 / 缺省）', async () => {
    const body = { items: [{ id: 1, visitors: '甲' }], total: 1, page: 1, page_size: 20 }
    mockGet.mockResolvedValueOnce(body)
    const result = await getVisits(5, { page: 1, page_size: 10 })
    expect(mockGet).toHaveBeenCalledWith('/pairings/5/visits', { page: 1, page_size: 10 })
    expect(result).toBe(body)

    mockGet.mockResolvedValueOnce({ items: [], total: 0, page: 1, page_size: 20 })
    await getVisits(5)
    expect(mockGet).toHaveBeenLastCalledWith('/pairings/5/visits', {})
  })

  it('createVisit → POST /pairings/{id}/visits', async () => {
    const payload = { visit_date: '2026-03-05', visitors: '甲' }
    mockPost.mockResolvedValueOnce({ id: 2, pairing_id: 5, ...payload })
    const result = await createVisit(5, payload)
    expect(mockPost).toHaveBeenCalledWith('/pairings/5/visits', payload)
    expect(result.id).toBe(2)
  })

  it('updateVisit → PUT /pairings/{id}/visits/{visitId}', async () => {
    mockPut.mockResolvedValueOnce({ id: 2, visitors: '乙' })
    const result = await updateVisit(5, 2, { visitors: '乙' })
    expect(mockPut).toHaveBeenCalledWith('/pairings/5/visits/2', { visitors: '乙' })
    expect(result.visitors).toBe('乙')
  })

  it('deleteVisit → DELETE /pairings/{id}/visits/{visitId}', async () => {
    mockDel.mockResolvedValueOnce({ id: 2 })
    const result = await deleteVisit(5, 2)
    expect(mockDel).toHaveBeenCalledWith('/pairings/5/visits/2')
    expect(result).toEqual({ id: 2 })
  })
})
