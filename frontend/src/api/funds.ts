/**
 * 经费管理 API
 */
import { get, post, put, del, apiRequest } from '@/api/request'
import { downloadBlobAsFile } from '@/api/helpers/blobDownload'
import { unwrapList, type UnwrappedList } from '@/utils/unwrapList'

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

/** OCR 凭证识别结果（后端 /funds/ocr-voucher） */
export interface OcrVoucherResult {
  text?: string
  amount?: number | string | null
  date?: string | null
  confidence?: number | null
  engine?: string | null
}
const BUDGETS_BASE = '/fund-budgets'

export const fundApi = {
  /** 获取经费列表 */
  async list(params?: FundListParams): Promise<UnwrappedList<Fund>> {
    const response = await get<any>(FUNDS_BASE, params)
    return unwrapList<Fund>(response)
  },

  /** 获取经费详情 */
  async getById(id: number): Promise<Fund> {
    return get<Fund>(`${FUNDS_BASE}/${id}`)
  },

  /** 创建经费记录 */
  async create(data: Partial<Fund>): Promise<Fund> {
    return post<Fund>(FUNDS_BASE, data)
  },

  /** 更新经费记录 */
  async update(id: number, data: Partial<Fund>): Promise<Fund> {
    return put<Fund>(`${FUNDS_BASE}/${id}`, data)
  },

  /** 删除经费记录 */
  async delete(id: number): Promise<{ message: string }> {
    return del<{ message: string }>(`${FUNDS_BASE}/${id}`)
  },

  // ========== 工作流 ==========
  async approve(id: number, data?: WorkflowRequest) {
    return post(`${FUNDS_BASE}/${id}/approve`, data || {})
  },
  async reject(id: number, data?: WorkflowRequest) {
    return post(`${FUNDS_BASE}/${id}/reject`, data || {})
  },
  async allocate(id: number, data?: WorkflowRequest) {
    return post(`${FUNDS_BASE}/${id}/allocate`, data || {})
  },
  async startUse(id: number, data?: WorkflowRequest) {
    return post(`${FUNDS_BASE}/${id}/start-use`, data || {})
  },
  async complete(id: number, data?: WorkflowRequest) {
    return post(`${FUNDS_BASE}/${id}/complete`, data || {})
  },
  async audit(id: number, data?: WorkflowRequest) {
    return post(`${FUNDS_BASE}/${id}/audit`, data || {})
  },

  // ========== 统计 ==========
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
  // W5-T5：改用具名 apiRequest<Blob>（不再依赖默认导出的裸 axios 实例）；
  // 代价是不再解析响应头 Content-Disposition，文件名统一用下方兜底名。
  async exportList(
    params?: { search?: string; type?: string; status?: string },
    format: 'xlsx' | 'csv' = 'xlsx'
  ) {
    await downloadBlobAsFile(
      () =>
        apiRequest<Blob>({
          method: 'GET',
          url: '/export/funds',
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
  async listAttachments(fundId: number): Promise<UnwrappedList<unknown>> {
    const body = await get<any>(`${FUNDS_BASE}/${fundId}/attachments`)
    return unwrapList<unknown>(body)
  },
  async deleteAttachment(attachmentId: number) {
    return del(`${FUNDS_BASE}/attachments/${attachmentId}`)
  },
  getPreviewUrl(attachmentId: number) {
    return `/api/v1${FUNDS_BASE}/attachments/${attachmentId}/preview`
  },
  getDownloadUrl(attachmentId: number) {
    return `/api/v1${FUNDS_BASE}/attachments/${attachmentId}/download`
  },
  /** 认证下载附件（通过 apiRequest 携带 token，兼容 Electron） */
  async downloadAttachment(attachmentId: number, fileName?: string) {
    await downloadBlobAsFile(
      () =>
        apiRequest<Blob>({
          method: 'GET',
          url: `${FUNDS_BASE}/attachments/${attachmentId}/download`,
          responseType: 'blob',
        }),
      { fallbackFileName: fileName || '附件下载' }
    )
  },
  /** 认证获取附件 Blob（用于预览，兼容 Electron） */
  async getAttachmentBlob(attachmentId: number): Promise<Blob> {
    return apiRequest<Blob>({
      method: 'GET',
      url: `${FUNDS_BASE}/attachments/${attachmentId}/preview`,
      responseType: 'blob',
    })
  },

  // ========== 经费状态/字段/操作历史 ==========
  async getStatusHistory(fundId: number) {
    return get(`${FUNDS_BASE}/${fundId}/history/status`)
  },
  async getFieldHistory(fundId: number) {
    return get(`${FUNDS_BASE}/${fundId}/history/fields`)
  },
  async getOperationHistory(fundId: number) {
    return get(`${FUNDS_BASE}/${fundId}/history/operations`)
  },

  // ========== 预算 ==========
  async listBudgets(year?: number): Promise<UnwrappedList<unknown>> {
    const body = await get<any>(`${BUDGETS_BASE}`, year ? { year } : undefined)
    return unwrapList<unknown>(body)
  },
  async createBudget(data: {
    year: number
    category: string
    budget_amount: number
    used_amount: number
    remaining_reason?: string
    remarks?: string
  }) {
    return post(BUDGETS_BASE, data)
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
    return put(`${BUDGETS_BASE}/${budgetId}`, data)
  },
  async deleteBudget(budgetId: number) {
    return del(`${BUDGETS_BASE}/${budgetId}`)
  },

  // ========== 预算告警与汇总 ==========
  async getBudgetAlerts() {
    return get(`${BUDGETS_BASE}/alerts`)
  },
  // W8-T019：getBudgetSummary 已删除（全仓零消费方）。

  // ========== 帮扶村/学校经费汇总 ==========
  async getVillageFundSummary(villageId: number, year?: number) {
    return get(`${FUNDS_BASE}/village/${villageId}/summary`, year ? { year } : undefined)
  },
  async getSchoolFundSummary(schoolId: number, year?: number) {
    return get(`${FUNDS_BASE}/school/${schoolId}/summary`, year ? { year } : undefined)
  },

  // ========== 预算交易记录 ==========
  async listTransactions(budgetId: number): Promise<UnwrappedList<unknown>> {
    const body = await apiRequest<any>({
      method: 'GET',
      url: `${BUDGETS_BASE}/transactions`,
      params: { budget_id: budgetId },
    })
    return unwrapList<unknown>(body)
  },
  async createTransaction(budgetId: number, data: Record<string, any>) {
    return post(`${BUDGETS_BASE}/transactions`, {
      ...data,
      budget_id: budgetId,
    })
  },
  async deleteTransaction(transactionId: number) {
    return del(`${BUDGETS_BASE}/transactions/${transactionId}`)
  },

  // ── ⑤ OCR 凭证识别（2026-10-25）────────────────────────────────────────
  /**
   * 识别经费凭证图片 → `{text, amount, date, confidence, engine}`。
   *
   * 后端在引擎不可用时返回 503（前端提示手工录入，不阻断经费业务）；
   * 因此这里**不吞错**，交给调用方按 503 给出友好提示。
   */
  async ocrVoucher(file: File): Promise<OcrVoucherResult> {
    const formData = new FormData()
    formData.append('file', file)
    return post(`${FUNDS_BASE}/ocr-voucher`, formData)
  },
}
