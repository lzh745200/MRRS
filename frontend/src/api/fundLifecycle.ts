/**
 * 经费全生命周期管理 API
 * 对应后端 /api/v1/fund-lifecycle 前缀
 */
import { get, post, put, del } from '@/api/request'

const BASE = '/fund-lifecycle'

// ==================== 类型定义 ====================

export interface PhaseInfo {
  id: number
  phase: number
  phase_label: string
  status: string
  entered_at: string | null
  completed_at: string | null
  operator: string | null
  remarks: string | null
}

export interface PhasesData {
  project_id: number
  current_phase: number
  phases: PhaseInfo[]
}

export interface TransferVoucher {
  id: number
  fund_id: number | null
  project_id: number | null
  voucher_no: string
  direction: string
  direction_label: string
  amount: number
  payer_account: string | null
  payee_account: string | null
  transfer_date: string | null
  status: string
  status_label: string
  confirmed_by: string | null
  confirmed_at: string | null
  remarks: string | null
  created_by: string | null
  created_at: string | null
}

export interface Contract {
  id: number
  fund_id: number | null
  project_id: number | null
  contract_no: string
  contract_name: string
  party_a: string | null
  party_b: string | null
  contract_amount: number
  paid_amount: number
  payment_progress: number
  sign_date: string | null
  deadline: string | null
  status: string
  status_label: string
  remarks: string | null
  created_by: string | null
  created_at: string | null
  payments?: ContractPayment[]
}

export interface ContractPayment {
  id: number
  contract_id: number
  payment_no: string
  amount: number
  payment_date: string
  purpose: string | null
  voucher_no: string | null
  status: string
  operator: string | null
  remarks: string | null
  created_at: string | null
}

export interface Anomaly {
  id: number
  fund_id: number | null
  project_id: number | null
  anomaly_type: string
  anomaly_type_label: string
  severity: string
  severity_label: string
  description: string
  detected_at: string | null
  resolved: boolean
  resolved_by: string | null
  resolved_at: string | null
  resolution: string | null
}

export interface Settlement {
  id: number
  project_id: number
  fund_id: number | null
  settlement_no: string
  total_budget: number
  total_spent: number
  total_remaining: number
  settlement_date: string | null
  status: string
  status_label: string
  auditor: string | null
  audit_opinion: string | null
  performance_score: number | null
  performance_level: string | null
  performance_level_label: string
  remarks: string | null
  created_by: string | null
  created_at: string | null
}

export interface HealthScore {
  health_score: number
  details: Record<string, { score: number; weight: number }>
}

// ==================== API 方法 ====================

export const fundLifecycleApi = {
  // ========== 阶段管理 ==========
  async getPhases(projectId: number): Promise<PhasesData> {
    const res = await get(`${BASE}/phases/${projectId}`)
    return res.data || res
  },

  async advancePhase(projectId: number, remarks?: string) {
    const res = await post(`${BASE}/phases/${projectId}/advance`, {
      remarks,
    })
    return res
  },

  async rollbackPhase(projectId: number, remarks?: string) {
    const res = await post(`${BASE}/phases/${projectId}/rollback`, {
      remarks,
    })
    return res
  },

  // ========== 阶段1 - 论证立项 ==========
  async initiate(projectId: number) {
    const res = await post(`${BASE}/initiate/${projectId}`)
    return res
  },

  async getReportTemplate(projectId: number) {
    const res = await get(`${BASE}/report-template/${projectId}`)
    return res.data || res
  },

  // ========== 阶段2 - 汇总审核 ==========
  async lockBudget(projectId: number) {
    const res = await post(`${BASE}/budget-lock/${projectId}`)
    return res
  },

  async complianceCheck(projectId: number) {
    const res = await get(`${BASE}/compliance-check/${projectId}`)
    return res.data || res
  },

  async budgetAggregation(params?: { group_by?: string; year?: number }) {
    const res = await get(`${BASE}/budget-aggregation`, params)
    return res.data || res
  },

  // ========== 阶段3 - 计划下达与资金拨付 ==========
  async quotaLock(fundId: number) {
    const res = await post(`${BASE}/quota-lock/${fundId}`)
    return res
  },

  async allocationPlan(projectId: number) {
    const res = await get(`${BASE}/allocation-plan/${projectId}`)
    return res.data || res
  },

  // ========== 分配调拨订单 ==========
  async listAllocationOrders(params?: Record<string, any>) {
    const res = await get(`${BASE}/allocation-orders`, params)
    return res.data || res
  },

  async createAllocationOrder(data: Record<string, any>) {
    const res = await post(`${BASE}/allocation-orders`, data)
    return res.data
  },

  async issueAllocationOrder(orderId: number) {
    const res = await post(`${BASE}/allocation-orders/${orderId}/issue`)
    return res.data
  },

  // ========== 配额调整 ==========
  async quotaAdjust(fundId: number, data: Record<string, any>) {
    const res = await put(`${BASE}/quota-adjust/${fundId}`, data)
    return res.data
  },

  // ========== 阶段4 - 对接与资金划转 ==========
  async listTransferVouchers(params?: Record<string, any>) {
    const res = await get(`${BASE}/transfer-vouchers`, params)
    return res.data || res
  },

  async createTransferVoucher(data: Record<string, any>) {
    const res = await post(`${BASE}/transfer-vouchers`, data)
    return res.data
  },

  async getTransferVoucher(id: number) {
    const res = await get(`${BASE}/transfer-vouchers/${id}`)
    return res.data || res
  },

  async updateTransferVoucher(id: number, data: Record<string, any>) {
    const res = await put(`${BASE}/transfer-vouchers/${id}`, data)
    return res.data
  },

  async deleteTransferVoucher(id: number) {
    const res = await del(`${BASE}/transfer-vouchers/${id}`)
    return res.data
  },

  async confirmTransferVoucher(id: number) {
    const res = await post(`${BASE}/transfer-vouchers/${id}/confirm`)
    return res.data
  },

  async transferLedger(projectId: number) {
    const res = await get(`${BASE}/transfer-ledger/${projectId}`)
    return res.data || res
  },

  async uploadVoucherAttachment(voucherId: number, file: File) {
    const fd = new FormData()
    fd.append('file', file)
    const res = await post(`${BASE}/transfer-vouchers/${voucherId}/attachments`, fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return res.data
  },

  // ========== 阶段5 - 实施监管 ==========
  async listContracts(params?: Record<string, any>) {
    const res = await get(`${BASE}/contracts`, params)
    return res.data || res
  },

  async createContract(data: Record<string, any>) {
    const res = await post(`${BASE}/contracts`, data)
    return res.data
  },

  async getContract(id: number) {
    const res = await get(`${BASE}/contracts/${id}`)
    return res.data || res
  },

  async updateContract(id: number, data: Record<string, any>) {
    const res = await put(`${BASE}/contracts/${id}`, data)
    return res.data
  },

  async deleteContract(id: number) {
    const res = await del(`${BASE}/contracts/${id}`)
    return res.data
  },

  async createContractPayment(contractId: number, data: Record<string, any>) {
    const res = await post(`${BASE}/contracts/${contractId}/payments`, data)
    return res.data
  },

  async listContractAttachments(contractId: number) {
    const res = await get(`${BASE}/contracts/${contractId}/attachments`)
    return res.data || res
  },

  async uploadContractAttachment(contractId: number, data: Record<string, any>) {
    const res = await post(`${BASE}/contracts/${contractId}/attachments`, data)
    return res.data || res
  },

  async monitoringDeviation(projectId: number) {
    const res = await get(`${BASE}/monitoring/deviation/${projectId}`)
    return res.data || res
  },

  async fundFlow(projectId: number) {
    const res = await get(`${BASE}/monitoring/fund-flow/${projectId}`)
    return res.data || res
  },

  // ========== 阶段6 - 核查督查 ==========
  async listAnomalies(params?: Record<string, any>) {
    const res = await get(`${BASE}/anomalies`, params)
    return res.data || res
  },

  async detectAnomalies(projectId: number) {
    const res = await post(`${BASE}/anomalies/detect/${projectId}`)
    return res
  },

  async resolveAnomaly(id: number, resolution: string) {
    const res = await post(`${BASE}/anomalies/${id}/resolve`, {
      resolution,
    })
    return res
  },

  async getInspectionClues(projectId: number) {
    const res = await get(`${BASE}/inspection-clues/${projectId}`)
    return res.data || res
  },

  // ========== 阶段7 - 决算与绩效 ==========
  async createSettlement(projectId: number, data?: Record<string, any>) {
    const res = await post(`${BASE}/settlement/${projectId}`, data || {})
    return res
  },

  async updateSettlement(id: number, data: Record<string, any>) {
    const res = await put(`${BASE}/settlement/${id}`, data)
    return res.data
  },

  async approveSettlement(id: number, data?: Record<string, any>) {
    const res = await post(`${BASE}/settlement/${id}/approve`, data || {})
    return res.data
  },

  async verifyAsset(settlementId: number, data: Record<string, any>) {
    const res = await post(`${BASE}/settlement/${settlementId}/verify-asset`, data)
    return res.data
  },

  async getPerformance(projectId: number) {
    const res = await get(`${BASE}/performance/${projectId}`)
    return res.data || res
  },

  async getPerformanceReport(projectId: number) {
    const res = await get(`${BASE}/performance-report/${projectId}`)
    return res.data || res
  },

  async getFeasibilityReport(projectId: number) {
    const res = await get(`${BASE}/feasibility-report/${projectId}`)
    return res.data || res
  },

  // ========== 资金流向树 ==========
  async getFundFlowTree(projectId: number) {
    const res = await get(`${BASE}/monitoring/fund-flow-tree/${projectId}`)
    return res.data || res
  },

  // ========== 健康度 ==========
  async getHealth(projectId: number): Promise<HealthScore> {
    const res = await get(`${BASE}/health/${projectId}`)
    return res.data || res
  },

  async batchHealth(projectIds: number[]): Promise<Record<number, number | null>> {
    const res = await post(`${BASE}/health/batch`, {
      project_ids: projectIds,
    })
    return res.data || res
  },
}

// HealthScore 和 PhaseInfo 已在文件顶部定义为 interface，此处不重复导出 type
