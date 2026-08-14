import { describe, it, expect, vi, beforeEach } from 'vitest'

const { mockGet, mockPost, mockPut, mockDelete, mockApiRequest, mockDownloadBlob } = vi.hoisted(() => ({
  mockGet: vi.fn(),
  mockPost: vi.fn(),
  mockPut: vi.fn(),
  mockDelete: vi.fn(),
  mockApiRequest: vi.fn(),
  mockDownloadBlob: vi.fn(),
}))

// src/api/funds.ts 实际 import：
//   import { get, post, put, del, apiRequest } from '@/api/request'  // 命名辅助，返回已解包的 envelope body
//   import request from '@/api/request'                              // 默认导出（原始 axios 实例，exportList 用）
// src/api/helpers/blobDownload.ts 还 import 了 parseContentDisposition / downloadBlob。
// 因此 mock 必须提供全部命名导出 + default。
vi.mock('@/api/request', () => ({
  // 命名 get(url, params)：适配为 axios 风格断言 mockGet(url, { params })，
  // 用 rest 参数区分 get(url) 与 get(url, undefined)（测试对两者断言不同）
  get: (url: string, ...rest: any[]) =>
    rest.length > 0 ? mockGet(url, { params: rest[0] }) : mockGet(url),
  post: (url: string, data?: any) => mockPost(url, data),
  put: (url: string, data?: any) => mockPut(url, data),
  del: (url: string) => mockDelete(url),
  apiRequest: (...args: any[]) => mockApiRequest(...args),
  parseContentDisposition: (_headers: any, fallback = 'download') => fallback,
  downloadBlob: (...args: any[]) => mockDownloadBlob(...args),
  // 默认导出：原始 axios 实例（exportList 走 request.get(url, config)）
  default: {
    get: (url: string, config?: any) => mockGet(url, config),
    post: (url: string, data?: any, config?: any) => mockPost(url, data, config),
    put: (url: string, data?: any) => mockPut(url, data),
    delete: (url: string) => mockDelete(url),
  },
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

import { fundApi } from '@/api/funds'

describe('api/funds', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('CRUD', () => {
    it('list 调用 GET /funds', async () => {
      mockGet.mockResolvedValue({ data: { items: [], total: 0 } })
      await fundApi.list({ page: 1 })
      expect(mockGet).toHaveBeenCalledWith('/funds', { params: { page: 1 } })
    })

    it('list 无参时 params=undefined', async () => {
      mockGet.mockResolvedValue({ data: { items: [], total: 0 } })
      await fundApi.list()
      expect(mockGet).toHaveBeenCalledWith('/funds', { params: undefined })
    })

    it('getById 调用 GET /funds/{id}', async () => {
      mockGet.mockResolvedValue({ data: { id: 1, amount: 100 } })
      const result = await fundApi.getById(1)
      expect(mockGet).toHaveBeenCalledWith('/funds/1')
      expect(result).toEqual({ id: 1, amount: 100 })
    })

    it('create 调用 POST /funds', async () => {
      mockPost.mockResolvedValue({ data: { id: 1 } })
      await fundApi.create({ amount: 100 })
      expect(mockPost).toHaveBeenCalledWith('/funds', { amount: 100 })
    })

    it('update 调用 PUT /funds/{id}', async () => {
      mockPut.mockResolvedValue({ data: { id: 1, amount: 200 } })
      await fundApi.update(1, { amount: 200 })
      expect(mockPut).toHaveBeenCalledWith('/funds/1', { amount: 200 })
    })

    it('delete 调用 DELETE /funds/{id}', async () => {
      mockDelete.mockResolvedValue({ data: { message: 'ok' } })
      await fundApi.delete(1)
      expect(mockDelete).toHaveBeenCalledWith('/funds/1')
    })
  })

  describe('工作流', () => {
    it('approve 调用 POST /funds/{id}/approve', async () => {
      mockPost.mockResolvedValue({ data: {} })
      await fundApi.approve(1, { opinion: 'ok' })
      expect(mockPost).toHaveBeenCalledWith('/funds/1/approve', { opinion: 'ok' })
    })

    it('approve 无 data 时传空对象', async () => {
      mockPost.mockResolvedValue({ data: {} })
      await fundApi.approve(1)
      expect(mockPost).toHaveBeenCalledWith('/funds/1/approve', {})
    })

    it('reject 调用 POST /funds/{id}/reject', async () => {
      mockPost.mockResolvedValue({ data: {} })
      await fundApi.reject(1, { opinion: 'no' })
      expect(mockPost).toHaveBeenCalledWith('/funds/1/reject', { opinion: 'no' })
    })

    it('reject 无 data 时传空对象', async () => {
      mockPost.mockResolvedValue({ data: {} })
      await fundApi.reject(1)
      expect(mockPost).toHaveBeenCalledWith('/funds/1/reject', {})
    })

    it('allocate 调用 POST /funds/{id}/allocate', async () => {
      mockPost.mockResolvedValue({ data: {} })
      await fundApi.allocate(1, { allocated_amount: 5000 })
      expect(mockPost).toHaveBeenCalledWith('/funds/1/allocate', { allocated_amount: 5000 })
    })

    it('startUse 调用 POST /funds/{id}/start-use', async () => {
      mockPost.mockResolvedValue({ data: {} })
      await fundApi.startUse(1)
      expect(mockPost).toHaveBeenCalledWith('/funds/1/start-use', {})
    })

    it('complete 调用 POST /funds/{id}/complete', async () => {
      mockPost.mockResolvedValue({ data: {} })
      await fundApi.complete(1)
      expect(mockPost).toHaveBeenCalledWith('/funds/1/complete', {})
    })

    it('audit 调用 POST /funds/{id}/audit', async () => {
      mockPost.mockResolvedValue({ data: {} })
      await fundApi.audit(1, { audit_result: 'pass' })
      expect(mockPost).toHaveBeenCalledWith('/funds/1/audit', { audit_result: 'pass' })
    })

    it('audit 无 data 时传空对象', async () => {
      mockPost.mockResolvedValue({ data: {} })
      await fundApi.audit(1)
      expect(mockPost).toHaveBeenCalledWith('/funds/1/audit', {})
    })

    it('allocate 无 data 时传空对象', async () => {
      mockPost.mockResolvedValue({ data: {} })
      await fundApi.allocate(1)
      expect(mockPost).toHaveBeenCalledWith('/funds/1/allocate', {})
    })
  })

  describe('统计', () => {
    it('statisticsOverview 调用 GET /funds/statistics/overview', async () => {
      mockGet.mockResolvedValue({ data: {} })
      await fundApi.statisticsOverview()
      expect(mockGet).toHaveBeenCalledWith('/funds/statistics/overview')
    })

    it('statisticsOverview 带 year 参数走携带分支', async () => {
      mockGet.mockResolvedValue({ data: {} })
      await fundApi.statisticsOverview(2024)
      expect(mockGet).toHaveBeenCalledWith('/funds/statistics/overview', { params: { year: 2024 } })
    })

    it('statisticsMultiDimension 带 params', async () => {
      mockGet.mockResolvedValue({ data: {} })
      await fundApi.statisticsMultiDimension({ year: 2024 })
      expect(mockGet).toHaveBeenCalledWith(
        '/funds/statistics/multi-dimension',
        { params: { year: 2024 } },
      )
    })
  })

  describe('附件', () => {
    it('listAttachments 调用 GET /funds/{id}/attachments', async () => {
      mockGet.mockResolvedValue({ data: { items: [], total: 0 } })
      await fundApi.listAttachments(1)
      expect(mockGet).toHaveBeenCalledWith('/funds/1/attachments')
    })

    it('listAttachments 响应为数组时直接返回', async () => {
      mockGet.mockResolvedValue({ data: [{ id: 1 }] })
      const r = await fundApi.listAttachments(1)
      expect(r.items).toHaveLength(1)
    })

    it('listAttachments 响应仅含 data 字段', async () => {
      mockGet.mockResolvedValue({ data: { data: [{ id: 2 }] } })
      const r = await fundApi.listAttachments(1)
      expect(r.items).toHaveLength(1)
    })

    it('listAttachments 响应为空对象时回退 []', async () => {
      mockGet.mockResolvedValue({ data: {} })
      const r = await fundApi.listAttachments(1)
      expect(r).toEqual({ items: [], total: 0 })
    })

    it('deleteAttachment 调用 DELETE /funds/attachments/{id}', async () => {
      mockDelete.mockResolvedValue({ data: {} })
      await fundApi.deleteAttachment(5)
      expect(mockDelete).toHaveBeenCalledWith('/funds/attachments/5')
    })

    it('downloadAttachment 调用 blob GET 并触发下载', async () => {
      mockGet.mockResolvedValue({ data: new Blob(['x']) })
      await fundApi.downloadAttachment(5, '发票.pdf')
      expect(mockGet).toHaveBeenCalledWith('/funds/attachments/5/download', { responseType: 'blob' })
      expect(mockDownloadBlob).toHaveBeenCalled()
    })

    it('downloadAttachment 无文件名用默认名', async () => {
      mockGet.mockResolvedValue({ data: new Blob(['x']) })
      await fundApi.downloadAttachment(5)
      expect(mockDownloadBlob).toHaveBeenCalledWith(expect.any(Blob), '附件下载')
    })

    it('getAttachmentBlob 返回 Blob', async () => {
      const blob = new Blob(['x'])
      mockGet.mockResolvedValue({ data: blob })
      const r = await fundApi.getAttachmentBlob(5)
      expect(mockGet).toHaveBeenCalledWith('/funds/attachments/5/preview', { responseType: 'blob' })
      expect(r).toBe(blob)
    })

    it('getPreviewUrl 返回 /api/v1/funds/attachments/{id}/preview', () => {
      expect(fundApi.getPreviewUrl(5)).toBe('/api/v1/funds/attachments/5/preview')
    })

    it('getDownloadUrl 返回 /api/v1/funds/attachments/{id}/download', () => {
      expect(fundApi.getDownloadUrl(5)).toBe('/api/v1/funds/attachments/5/download')
    })
  })

  describe('预算', () => {
    it('listBudgets 调用 GET /fund-budgets', async () => {
      mockGet.mockResolvedValue({ data: { items: [], total: 0 } })
      await fundApi.listBudgets(2024)
      expect(mockGet).toHaveBeenCalledWith('/fund-budgets', { params: { year: 2024 } })
    })

    it('listBudgets 无 year 时 params=undefined', async () => {
      mockGet.mockResolvedValue({ data: { items: [], total: 0 } })
      await fundApi.listBudgets()
      expect(mockGet).toHaveBeenCalledWith('/fund-budgets', { params: undefined })
    })

    it('listBudgets 响应为数组时直接返回', async () => {
      mockGet.mockResolvedValue({ data: [{ year: 2024 }] })
      const r = await fundApi.listBudgets(2024)
      expect(r.items).toHaveLength(1)
    })

    it('listBudgets 响应仅含 data 字段', async () => {
      mockGet.mockResolvedValue({ data: { data: [{ year: 2025 }] } })
      const r = await fundApi.listBudgets(2025)
      expect(r.items).toHaveLength(1)
    })

    it('listBudgets 响应为空对象时回退 []', async () => {
      mockGet.mockResolvedValue({ data: {} })
      const r = await fundApi.listBudgets(2025)
      expect(r).toEqual({ items: [], total: 0 })
    })

    it('createBudget 调用 POST /fund-budgets', async () => {
      mockPost.mockResolvedValue({ data: {} })
      await fundApi.createBudget({ year: 2024, category: 'project', budget_amount: 1000, used_amount: 200 })
      expect(mockPost).toHaveBeenCalled()
    })

    it('updateBudget 调用 PUT /fund-budgets/{id}', async () => {
      mockPut.mockResolvedValue({ data: {} })
      await fundApi.updateBudget(1, { year: 2024 })
      expect(mockPut).toHaveBeenCalledWith('/fund-budgets/1', { year: 2024 })
    })

    it('deleteBudget 调用 DELETE /fund-budgets/{id}', async () => {
      mockDelete.mockResolvedValue({ data: {} })
      await fundApi.deleteBudget(1)
      expect(mockDelete).toHaveBeenCalledWith('/fund-budgets/1')
    })

    it('getBudgetAlerts 调用 GET /fund-budgets/alerts', async () => {
      mockGet.mockResolvedValue({ data: { alerts: [] } })
      await fundApi.getBudgetAlerts()
      expect(mockGet).toHaveBeenCalledWith('/fund-budgets/alerts')
    })

    it('getBudgetSummary 调用 GET /fund-budgets/summary', async () => {
      mockGet.mockResolvedValue({ data: { summary: {} } })
      await fundApi.getBudgetSummary()
      expect(mockGet).toHaveBeenCalledWith('/fund-budgets/summary')
    })

    it('getVillageFundSummary 带 year', async () => {
      mockGet.mockResolvedValue({ data: { total: 1 } })
      await fundApi.getVillageFundSummary(3, 2025)
      expect(mockGet).toHaveBeenCalledWith('/funds/village/3/summary', { params: { year: 2025 } })
    })

    it('getVillageFundSummary 无 year', async () => {
      mockGet.mockResolvedValue({ data: { total: 1 } })
      await fundApi.getVillageFundSummary(3)
      expect(mockGet).toHaveBeenCalledWith('/funds/village/3/summary', { params: undefined })
    })

    it('getSchoolFundSummary 带 year', async () => {
      mockGet.mockResolvedValue({ data: { total: 1 } })
      await fundApi.getSchoolFundSummary(4, 2025)
      expect(mockGet).toHaveBeenCalledWith('/funds/school/4/summary', { params: { year: 2025 } })
    })

    it('getSchoolFundSummary 无 year', async () => {
      mockGet.mockResolvedValue({ data: { total: 1 } })
      await fundApi.getSchoolFundSummary(4)
      expect(mockGet).toHaveBeenCalledWith('/funds/school/4/summary', { params: undefined })
    })

    it('listTransactions 调用 apiRequest GET 且 items 为数组', async () => {
      mockApiRequest.mockResolvedValue({ data: { items: [{ id: 1 }] } })
      const r = await fundApi.listTransactions(9)
      expect(mockApiRequest).toHaveBeenCalledWith({
        method: 'GET',
        url: '/fund-budgets/transactions',
        params: { budget_id: 9 },
      })
      expect(r.items).toHaveLength(1)
    })

    it('listTransactions 响应为数组时直接返回', async () => {
      mockApiRequest.mockResolvedValue({ data: [{ id: 1 }] })
      const r = await fundApi.listTransactions(9)
      expect(r.items).toHaveLength(1)
    })

    it('listTransactions 响应仅含 data 字段', async () => {
      mockApiRequest.mockResolvedValue({ data: { data: [{ id: 2 }] } })
      const r = await fundApi.listTransactions(9)
      expect(r.items).toHaveLength(1)
    })

    it('listTransactions 响应为空对象时回退 []', async () => {
      mockApiRequest.mockResolvedValue({ data: {} })
      const r = await fundApi.listTransactions(9)
      expect(r).toEqual({ items: [], total: 0 })
    })

    it('createTransaction 调用 POST 并附带 budget_id', async () => {
      mockPost.mockResolvedValue({ data: { id: 1 } })
      await fundApi.createTransaction(9, { amount: 100 })
      expect(mockPost).toHaveBeenCalledWith('/fund-budgets/transactions', { amount: 100, budget_id: 9 })
    })

    it('deleteTransaction 调用 DELETE /fund-budgets/transactions/{id}', async () => {
      mockDelete.mockResolvedValue({ data: { success: true } })
      await fundApi.deleteTransaction(7)
      expect(mockDelete).toHaveBeenCalledWith('/fund-budgets/transactions/7')
    })
  })

  describe('操作历史', () => {
    it('getStatusHistory GET /funds/{id}/history/status', async () => {
      mockGet.mockResolvedValue({ data: { items: [] } })
      await fundApi.getStatusHistory(1)
      expect(mockGet).toHaveBeenCalledWith('/funds/1/history/status')
    })

    it('getFieldHistory GET /funds/{id}/history/fields', async () => {
      mockGet.mockResolvedValue({ data: { items: [] } })
      await fundApi.getFieldHistory(1)
      expect(mockGet).toHaveBeenCalledWith('/funds/1/history/fields')
    })

    it('getOperationHistory GET /funds/{id}/history/operations', async () => {
      mockGet.mockResolvedValue({ data: { items: [] } })
      await fundApi.getOperationHistory(1)
      expect(mockGet).toHaveBeenCalledWith('/funds/1/history/operations')
    })
  })

  describe('exportList', () => {
    it('调用 GET /export/funds（真实文件导出端点）with blob responseType', async () => {
      mockGet.mockResolvedValue({ data: new Blob(['test']) })
      await fundApi.exportList({ type: 'project' })
      // 修复 2026-08-14：旧实现请求 /funds/export（返回 JSON），导出的是 JSON 文本；
      // 现改为 /export/funds 真实 xlsx 导出，参数映射 search→keyword / type→fund_type
      expect(mockGet).toHaveBeenCalledWith('/export/funds', {
        params: { keyword: undefined, fund_type: 'project', status: undefined, format: 'xlsx' },
        responseType: 'blob',
      })
      // 下载流程经 downloadBlobAsFile → downloadBlob 触发
      expect(mockDownloadBlob).toHaveBeenCalled()
    })

    it('csv 格式显式指定', async () => {
      mockGet.mockResolvedValue({ data: new Blob(['test']) })
      await fundApi.exportList({ search: '桥' }, 'csv')
      expect(mockGet).toHaveBeenCalledWith('/export/funds', {
        params: { keyword: '桥', fund_type: undefined, status: undefined, format: 'csv' },
        responseType: 'blob',
      })
    })
  })
})
