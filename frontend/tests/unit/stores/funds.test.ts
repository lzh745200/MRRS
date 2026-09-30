import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

const mockApiRequest = vi.fn()
const mockPost = vi.fn()
const mockPut = vi.fn()
const mockDel = vi.fn()

vi.mock('@/api/request', () => ({
  apiRequest: (...args: any[]) => mockApiRequest(...args),
  post: (...args: any[]) => mockPost(...args),
  put: (...args: any[]) => mockPut(...args),
  del: (...args: any[]) => mockDel(...args),
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

vi.mock('@/utils/unwrapList', () => ({
  unwrapList: (res: any) => ({
    items: res?.items ?? res?.data?.items ?? [],
    total: res?.total ?? res?.data?.total ?? 0,
  }),
}))

import { useFundsStore } from '@/stores/funds'

describe('useFundsStore', () => {
  let store: ReturnType<typeof useFundsStore>

  beforeEach(() => {
    vi.clearAllMocks()
    setActivePinia(createPinia())
    store = useFundsStore()
  })

  it('initializes with default values', () => {
    expect(store.fundList).toEqual([])
    expect(store.current).toBeNull()
    expect(store.loading).toBe(false)
    expect(store.total).toBe(0)
    expect(store.totalFunds).toBe(0)
    expect(store.usedFunds).toBe(0)
    expect(store.remainFunds).toBe(0)
  })

  it('totalFunds computes sum of fund amounts', () => {
    store.fundList = [
      { id: 1, amount: 100, used_amount: 30 },
      { id: 2, amount: 200, used_amount: 50 },
    ] as any[]
    expect(store.totalFunds).toBe(300)
    expect(store.usedFunds).toBe(80)
    expect(store.remainFunds).toBe(220)
  })

  it('handles empty fundList gracefully', () => {
    store.fundList = []
    expect(store.totalFunds).toBe(0)
    expect(store.usedFunds).toBe(0)
    expect(store.remainFunds).toBe(0)
  })

  it('handles missing amount fields as zero', () => {
    store.fundList = [{ id: 1 }, { id: 2, amount: 50 }] as any[]
    expect(store.totalFunds).toBe(50)
    expect(store.usedFunds).toBe(0)
  })

  it('handles string amounts via Number conversion', () => {
    store.fundList = [{ id: 1, amount: '30.5', used_amount: '10.25' }] as any[]
    expect(store.totalFunds).toBe(30.5)
    expect(store.usedFunds).toBe(10.25)
    expect(store.remainFunds).toBe(20.25)
  })

  describe('fetchFunds', () => {
    it('成功时填充列表与总数并传入参数', async () => {
      mockApiRequest.mockResolvedValueOnce({ items: [{ id: 1, amount: 10 }], total: 1 })
      await store.fetchFunds({ page: 1 })
      expect(mockApiRequest).toHaveBeenCalledWith({
        method: 'GET',
        url: '/funds',
        params: { page: 1 },
        timeout: 15000,
      })
      expect(store.fundList).toHaveLength(1)
      expect(store.total).toBe(1)
      expect(store.loading).toBe(false)
    })

    it('失败时清空列表并置零', async () => {
      mockApiRequest.mockRejectedValueOnce(new Error('network'))
      await store.fetchFunds()
      expect(store.fundList).toEqual([])
      expect(store.total).toBe(0)
      expect(store.loading).toBe(false)
    })
  })

  describe('createFund', () => {
    it('POST 成功后重新拉取列表', async () => {
      mockPost.mockResolvedValueOnce({ code: 200 })
      mockApiRequest.mockResolvedValueOnce({ items: [{ id: 2 }], total: 1 })
      await store.createFund({ name: 'fund-a' })
      expect(mockPost).toHaveBeenCalledWith('/funds', { name: 'fund-a' })
      expect(store.fundList).toHaveLength(1)
      expect(store.total).toBe(1)
    })
  })

  describe('updateFund', () => {
    it('存在时合并更新本地条目', async () => {
      mockPut.mockResolvedValueOnce({ code: 200 })
      store.fundList.push({ id: 1, amount: 100 } as any)
      await store.updateFund(1, { amount: 200 })
      expect(mockPut).toHaveBeenCalledWith('/funds/1', { amount: 200 })
      expect(store.fundList[0].amount).toBe(200)
    })

    it('不存在时跳过本地更新', async () => {
      mockPut.mockResolvedValueOnce({ code: 200 })
      await store.updateFund(9, { amount: 1 })
      expect(store.fundList).toEqual([])
    })
  })

  describe('deleteFund', () => {
    it('删除匹配条目并减少 total', async () => {
      mockDel.mockResolvedValueOnce({ code: 200 })
      store.fundList.push({ id: 1 } as any, { id: 2 } as any)
      store.total = 2
      await store.deleteFund(1)
      expect(mockDel).toHaveBeenCalledWith('/funds/1')
      expect(store.fundList).toHaveLength(1)
      expect(store.fundList[0].id).toBe(2)
      expect(store.total).toBe(1)
    })

    it('删除的记录不在当前页时 total 不变（服务端总数不可臆减）', async () => {
      mockDel.mockResolvedValueOnce({ code: 200 })
      store.fundList = [{ id: 1 } as any]
      store.total = 30 // 服务端分页总数：当前页只有 1 条
      await store.deleteFund(999)
      expect(store.fundList).toHaveLength(1)
      expect(store.total).toBe(30)
    })

    it('total 永不为负（原实现无条件 -- 会减成负数）', async () => {
      mockDel.mockResolvedValueOnce({ code: 200 })
      store.fundList = [{ id: 1 } as any]
      store.total = 0
      await store.deleteFund(1)
      expect(store.total).toBe(0)
    })
  })

  describe('getSummary', () => {
    it('返回 res.data', async () => {
      mockApiRequest.mockResolvedValueOnce({ data: { total_amount: 5 } })
      expect(await store.getSummary()).toEqual({ total_amount: 5 })
    })

    it('无 data 时返回 res', async () => {
      mockApiRequest.mockResolvedValueOnce({ total_amount: 6 })
      expect(await store.getSummary()).toEqual({ total_amount: 6 })
    })

    it('响应完全为空时返回空对象', async () => {
      mockApiRequest.mockResolvedValueOnce(null)
      expect(await store.getSummary()).toEqual({})
    })

    it('失败时返回默认统计', async () => {
      mockApiRequest.mockRejectedValueOnce(new Error('network'))
      expect(await store.getSummary()).toEqual({
        total_amount: 0,
        total_allocated: 0,
        total_count: 0,
        by_status: {},
      })
    })
  })

  describe('approveFund', () => {
    it('存在时置为 approved', async () => {
      mockPost.mockResolvedValueOnce({ code: 200 })
      store.fundList.push({ id: 1, status: 'pending' } as any)
      await store.approveFund(1)
      expect(mockPost).toHaveBeenCalledWith('/funds/1/approve', {})
      expect(store.fundList[0].status).toBe('approved')
    })

    it('不存在时跳过本地更新', async () => {
      mockPost.mockResolvedValueOnce({ code: 200 })
      await store.approveFund(5)
      expect(store.fundList).toEqual([])
    })
  })
})
