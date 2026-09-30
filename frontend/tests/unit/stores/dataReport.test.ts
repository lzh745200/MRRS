import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

const mockApiRequest = vi.fn()

vi.mock('@/api/request', () => ({
  apiRequest: (...args: any[]) => mockApiRequest(...args),
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

vi.mock('@/utils/unwrapList', () => ({
  unwrapList: (res: any) => {
    if (Array.isArray(res)) return { items: res, total: res.length }
    if (res?.data?.items) return { items: res.data.items, total: res.data.total ?? res.data.items.length }
    return { items: [], total: 0 }
  },
}))

import { useDataReportStore } from '@/stores/dataReport'

describe('useDataReportStore', () => {
  let store: ReturnType<typeof useDataReportStore>
  beforeEach(() => {
    vi.clearAllMocks()
    setActivePinia(createPinia())
    store = useDataReportStore()
  })

  it('初始: reports=[], receivedReports=[]', () => {
    expect(store.reports).toEqual([])
    expect(store.receivedReports).toEqual([])
    expect(store.receivedTotal).toBe(0)
  })

  it('fetchReceivedReports 成功时填充 receivedReports + total', async () => {
    mockApiRequest.mockResolvedValueOnce({
      data: { items: [{ id: 1 }, { id: 2 }], total: 2 },
    })
    await store.fetchReceivedReports({ page: 1 })
    expect(mockApiRequest).toHaveBeenCalledWith(expect.objectContaining({
      method: 'GET',
      url: '/data-reports/received',
      params: { page: 1 },
    }))
    expect(store.receivedReports).toHaveLength(2)
    expect(store.receivedTotal).toBe(2)
  })

  it('fetchReceivedReports 失败时清空 + 设置 error', async () => {
    mockApiRequest.mockRejectedValueOnce(new Error('boom'))
    await store.fetchReceivedReports()
    expect(store.receivedReports).toEqual([])
    expect(store.error).toBe('boom')
  })

  it('fetchReceivedReports axios 错误格式', async () => {
    mockApiRequest.mockRejectedValueOnce({ response: { data: { message: '服务器错误' } } })
    await store.fetchReceivedReports()
    expect(store.error).toBe('服务器错误')
  })

  it('fetchReports 成功时填充 reports', async () => {
    mockApiRequest.mockResolvedValueOnce({
      data: { items: [{ id: 1 }] },
    })
    await store.fetchReports()
    expect(store.reports).toHaveLength(1)
  })

  it('fetchReports 失败时设置 error', async () => {
    mockApiRequest.mockRejectedValueOnce(new Error('network'))
    await store.fetchReports()
    expect(store.error).toBe('network')
  })

  it('previewReport 调用 GET /data-reports/{id}', async () => {
    mockApiRequest.mockResolvedValueOnce({ data: { id: 5, content: 'x' } })
    await store.previewReport(5)
    expect(mockApiRequest).toHaveBeenCalledWith(expect.objectContaining({
      method: 'GET',
      url: '/data-reports/5',
    }))
  })

  it('receiveReport 调用 POST /data-reports/{id}/approve', async () => {
    mockApiRequest.mockResolvedValueOnce({})
    await store.receiveReport(3)
    expect(mockApiRequest).toHaveBeenCalledWith(expect.objectContaining({
      method: 'POST',
      url: '/data-reports/3/approve',
    }))
  })

  it('rejectReport 调用 POST /data-reports/{id}/review with decision=reject', async () => {
    mockApiRequest.mockResolvedValueOnce({})
    await store.rejectReport(3, '数据不完整')
    expect(mockApiRequest).toHaveBeenCalledWith(expect.objectContaining({
      method: 'POST',
      url: '/data-reports/3/review',
      data: { decision: 'reject', comment: '数据不完整' },
    }))
  })

  it('downloadReport 调用 GET /data-reports/{id}/package', async () => {
    mockApiRequest.mockResolvedValueOnce({ data: { url: 'http://x' } })
    await store.downloadReport(7)
    expect(mockApiRequest).toHaveBeenCalledWith(expect.objectContaining({
      method: 'GET',
      url: '/data-reports/7/package',
    }))
  })

  it('submitReport 调用 POST /data-reports', async () => {
    mockApiRequest.mockResolvedValueOnce({})
    await store.submitReport({ content: 'new' })
    expect(mockApiRequest).toHaveBeenCalledWith(expect.objectContaining({
      method: 'POST',
      url: '/data-reports',
      data: { content: 'new' },
    }))
  })

  // 原实现：previewReport/receiveReport/rejectReport/downloadReport/submitReport
  // 均无 try/catch —— 失败既不写 error 也不重置 loading，与两个 fetch* 的标准不一致。
  describe('读写方法错误可观测性', () => {
    it('previewReport 失败：写 error、重置 loading 并向上抛出', async () => {
      mockApiRequest.mockRejectedValueOnce(new Error('preview boom'))
      await expect(store.previewReport(5)).rejects.toThrow('preview boom')
      expect(store.error).toBe('preview boom')
      expect(store.loading).toBe(false)
    })

    it('receiveReport 失败：写 error、重置 loading 并向上抛出', async () => {
      mockApiRequest.mockRejectedValueOnce(new Error('receive boom'))
      await expect(store.receiveReport(3)).rejects.toThrow('receive boom')
      expect(store.error).toBe('receive boom')
      expect(store.loading).toBe(false)
    })

    it('rejectReport 失败：写 error 并向上抛出', async () => {
      mockApiRequest.mockRejectedValueOnce(new Error('reject boom'))
      await expect(store.rejectReport(3, '原因')).rejects.toThrow('reject boom')
      expect(store.error).toBe('reject boom')
    })

    it('downloadReport 失败：写 error 并向上抛出', async () => {
      mockApiRequest.mockRejectedValueOnce(new Error('download boom'))
      await expect(store.downloadReport(7)).rejects.toThrow('download boom')
      expect(store.error).toBe('download boom')
    })

    it('submitReport 失败：写 error 并向上抛出', async () => {
      mockApiRequest.mockRejectedValueOnce(new Error('submit boom'))
      await expect(store.submitReport({ content: 'x' })).rejects.toThrow('submit boom')
      expect(store.error).toBe('submit boom')
    })

    it('无 message 时回退中文兜底文案（不外泄原始异常形态）', async () => {
      mockApiRequest.mockRejectedValueOnce({})
      await expect(store.submitReport({})).rejects.toEqual({})
      expect(store.error).toBe('提交上报失败')
    })

    it('成功时清空 error 并复位 loading', async () => {
      store.error = '旧错误'
      mockApiRequest.mockResolvedValueOnce({ data: { id: 1 } })
      await store.previewReport(1)
      expect(store.error).toBeNull()
      expect(store.loading).toBe(false)
    })
  })
})
