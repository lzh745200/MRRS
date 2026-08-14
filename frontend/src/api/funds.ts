/**
 * 经费管理 API
 */
import { get, post, put, del, apiRequest } from '@/api/request'
import request from '@/api/request'
import { downloadBlobAsFile } from '@/api/helpers/blobDownload'
import type { PaginatedResponse } from '@/types/api'

/** 经费记录 */
export interface Fund {
  id: number
  name?: string
  date?: string
  type?: string
  code?: string
  fund_type?: string
  fund_source?: string
  amount: number
  planned_amount?: number
  approved_amount?: number
  allocated_amount?: number
  used_amount?: number
  remaining_amount?: number
  project_id?: number
  project_name?: string
  village_id?: number
  school_id?: number
  purpose?: string
  source?: string
  operator?: string
  applicant?: string
  application_date?: string
  approved_by?: string
  approval_date?: string
  allocation_date?: string
  allocation_method?: string
  receiver?: string
  usage_description?: string
  start_date?: string
  end_date?: string
  audit_date?: string
  audit_result?: string
  audit_opinion?: string
  status?: string
  remarks?: string
  created_at?: string
  updated_at?: string
}

/** 经费列表查询参数 */
export interface FundListParams {
  page?: number
  page_size?: number
  keyword?: string
  fund_type?: string
  status?: string
}

/** 工作流操作请求 */
export interface WorkflowRequest {
  opinion?: string
  allocated_amount?: number
  allocation_method?: string
  audit_result?: string
}

const FUNDS_BASE = '/funds'
const BUDGETS_BASE = '/fund-budgets'

export const fundApi = {
  /** 获取经费列表 */
  async list(params?: FundListParams): Promise<PaginatedResponse<Fund>> {
    const response = await get(FUNDS_BASE, params)
    return response.data
  },

  /** 获取经费详情 */
  async getById(id: number): Promise<Fund> {
    const response = await get(`${FUNDS_BASE}/${id}`)
    return response.data
  },

  /** 创建经费记录 */
  async create(data: Partial<Fund>): Promise<Fund> {
    const response = await post(FUNDS_BASE, data)
    return response.data
  },

  /** 更新经费记录 */
  async update(id: number, data: Partial<Fund>): Promise<Fund> {
    const response = await put(`${FUNDS_BASE}/${id}`, data)
    return response.data
  },

  /** 删除经费记录 */
  async delete(id: number): Promise<{ message: string }> {
    const response = await del(`${FUNDS_BASE}/${id}`)
    return response.data
  },

  // ========== 工作流 ==========
  async approve(id: number, data?: WorkflowRequest) {
    const response = await post(`${FUNDS_BASE}/${id}/approve`, data || {})
    return response.data
  },
  async reject(id: number, data?: WorkflowRequest) {
    const response = await post(`${FUNDS_BASE}/${id}/reject`, data || {})
    return response.data
  },
  async allocate(id: number, data?: WorkflowRequest) {
    const response = await post(`${FUNDS_BASE}/${id}/allocate`, data || {})
    return response.data
  },
  async startUse(id: number, data?: WorkflowRequest) {
    const response = await post(`${FUNDS_BASE}/${id}/start-use`, data || {})
    return response.data
  },
  async complete(id: number, data?: WorkflowRequest) {
    const response = await post(`${FUNDS_BASE}/${id}/complete`, data || {})
    return response.data
  },
  async audit(id: number, data?: WorkflowRequest) {
    const response = await post(`${FUNDS_BASE}/${id}/audit`, data || {})
    return response.data
  },

  // ========== 统计 ==========
  async statisticsOverview(year?: number) {
    const response = year
      ? await get(`${FUNDS_BASE}/statistics/overview`, { year })
      : await get(`${FUNDS_BASE}/statistics/overview`)
    return response.data
  },
  async statisticsMultiDimension(params?: Record<string, string | number | boolean>) {
    // 注意：get() 已自动解包（返回 res.data）。此处必须原样返回，
    // 不能再次取 .data —— 否则会得到裸数组，调用方 .success 守卫永远为 false，
    // 导致 Report.vue / Analysis.vue 图表空数据。
    const response = await get(`${FUNDS_BASE}/statistics/multi-dimension`, params)
    return response
  },

  // ========== 导出（真实导出端点 /export/funds，xlsx/csv 文件下载） ==========
  // 修复 2026-08-14：旧实现下载 /funds/export（后端返回 JSON），用户得到
  // 名为 .csv 的 JSON 文本文件。现改为调用真实文件导出端点。
  async exportList(
    params?: { search?: string; type?: string; status?: string },
    format: 'xlsx' | 'csv' = 'xlsx'
  ) {
    await downloadBlobAsFile(
      () =>
        request.get('/export/funds', {
          params: {
            keyword: params?.search || undefined,
            fund_type: params?.type || undefined,
            status: params?.status || undefined,
            format,
          },
          responseType: 'blob',
        }),
      { fallbackFileName: `经费列表_${new Date().toISOString().slice(0, 10)}.${format}` }
    )
  },

  // ========== 附件 ==========
  async listAttachments(fundId: number) {
    const res = await get(`${FUNDS_BASE}/${fundId}/attachments`)
    const body: any = res.data
    const items = Array.isArray(body) ? body : body?.items || body?.data || []
    return { items, total: items.length } as {
      items: unknown[]
      total: number
    }
  },
  async deleteAttachment(attachmentId: number) {
    const response = await del(`${FUNDS_BASE}/attachments/${attachmentId}`)
    return response.data
  },
  getPreviewUrl(attachmentId: number) {
    return `/api/v1${FUNDS_BASE}/attachments/${attachmentId}/preview`
  },
  getDownloadUrl(attachmentId: number) {
    return `/api/v1${FUNDS_BASE}/attachments/${attachmentId}/download`
  },
  /** 认证下载附件（通过 axios 携带 token，兼容 Electron） */
  async downloadAttachment(attachmentId: number, fileName?: string) {
    await downloadBlobAsFile(
      () =>
        request.get(`${FUNDS_BASE}/attachments/${attachmentId}/download`, { responseType: 'blob' }),
      { fallbackFileName: fileName || '附件下载' }
    )
  },
  /** 认证获取附件 Blob（用于预览，兼容 Electron） */
  async getAttachmentBlob(attachmentId: number): Promise<Blob> {
    const res = await request.get(`${FUNDS_BASE}/attachments/${attachmentId}/preview`, {
      responseType: 'blob',
    })
    return res.data as Blob
  },

  // ========== 经费状态/字段/操作历史 ==========
  async getStatusHistory(fundId: number) {
    const response = await get(`${FUNDS_BASE}/${fundId}/history/status`)
    return response.data
  },
  async getFieldHistory(fundId: number) {
    const response = await get(`${FUNDS_BASE}/${fundId}/history/fields`)
    return response.data
  },
  async getOperationHistory(fundId: number) {
    const response = await get(`${FUNDS_BASE}/${fundId}/history/operations`)
    return response.data
  },

  // ========== 预算 ==========
  async listBudgets(year?: number) {
    const res = await get(`${BUDGETS_BASE}`, year ? { year } : undefined)
    const body: any = res.data
    const items = Array.isArray(body) ? body : body?.items || body?.data || []
    return { items, total: items.length } as {
      items: unknown[]
      total: number
    }
  },
  async createBudget(data: {
    year: number
    category: string
    budget_amount: number
    used_amount: number
    remaining_reason?: string
    remarks?: string
  }) {
    const response = await post(BUDGETS_BASE, data)
    return response.data
  },
  async updateBudget(
    budgetId: number,
    data: Partial<{
      year: number
      category: string
      budget_amount: number
      used_amount: number
      remaining_reason?: string
      remarks?: string
    }>
  ) {
    const response = await put(`${BUDGETS_BASE}/${budgetId}`, data)
    return response.data
  },
  async deleteBudget(budgetId: number) {
    const response = await del(`${BUDGETS_BASE}/${budgetId}`)
    return response.data
  },

  // ========== 预算告警与汇总 ==========
  async getBudgetAlerts() {
    const response = await get(`${BUDGETS_BASE}/alerts`)
    return response.data
  },
  async getBudgetSummary() {
    const response = await get(`${BUDGETS_BASE}/summary`)
    return response.data
  },

  // ========== 帮扶村/学校经费汇总 ==========
  async getVillageFundSummary(villageId: number, year?: number) {
    const response = await get(
      `${FUNDS_BASE}/village/${villageId}/summary`,
      year ? { year } : undefined
    )
    return response.data
  },
  async getSchoolFundSummary(schoolId: number, year?: number) {
    const response = await get(
      `${FUNDS_BASE}/school/${schoolId}/summary`,
      year ? { year } : undefined
    )
    return response.data
  },

  // ========== 预算交易记录 ==========
  async listTransactions(budgetId: number) {
    const res = await apiRequest({
      method: 'GET',
      url: `${BUDGETS_BASE}/transactions`,
      params: { budget_id: budgetId },
    })
    const body: any = res.data
    const items = Array.isArray(body) ? body : body?.items || body?.data || []
    return { items, total: items.length } as {
      items: unknown[]
      total: number
    }
  },
  async createTransaction(budgetId: number, data: Record<string, any>) {
    const response = await post(`${BUDGETS_BASE}/transactions`, {
      ...data,
      budget_id: budgetId,
    })
    return response.data
  },
  async deleteTransaction(transactionId: number) {
    const response = await del(`${BUDGETS_BASE}/transactions/${transactionId}`)
    return response.data
  },
}
