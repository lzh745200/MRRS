import { describe, it, expect, vi, beforeEach } from 'vitest'

// src/api/fundLifecycle.ts 从 '@/api/request' 导入命名导出 { get, post, put, del }，
// 这些辅助函数返回已解包的 envelope body，因此 mock 也按命名导出提供。
const { mockGet, mockPost, mockPut, mockDelete } = vi.hoisted(() => ({
  mockGet: vi.fn(),
  mockPost: vi.fn(),
  mockPut: vi.fn(),
  mockDelete: vi.fn(),
}))

vi.mock('@/api/request', () => ({
  get: mockGet,
  post: mockPost,
  put: mockPut,
  del: mockDelete,
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

import { fundLifecycleApi } from '@/api/fundLifecycle'

describe('api/fundLifecycle (30 methods)', () => {
  beforeEach(() => vi.clearAllMocks())

  it('getPhases', async () => {
    mockGet.mockResolvedValueOnce({ data: { data: { phases: [] } } })
    await fundLifecycleApi.getPhases(1)
    expect(mockGet).toHaveBeenCalledWith('/fund-lifecycle/phases/1')
  })

  it('advancePhase POST 含 remarks', async () => {
    mockPost.mockResolvedValueOnce({ data: { success: true } })
    await fundLifecycleApi.advancePhase(1, 'ok')
    expect(mockPost).toHaveBeenCalledWith('/fund-lifecycle/phases/1/advance', { remarks: 'ok' })
  })

  it('rollbackPhase POST', async () => {
    mockPost.mockResolvedValueOnce({ data: { success: true } })
    await fundLifecycleApi.rollbackPhase(1, 'revert')
    expect(mockPost).toHaveBeenCalledWith('/fund-lifecycle/phases/1/rollback', { remarks: 'revert' })
  })

  it('initiate POST', async () => {
    mockPost.mockResolvedValueOnce({ data: { success: true } })
    await fundLifecycleApi.initiate(1)
    expect(mockPost).toHaveBeenCalledWith('/fund-lifecycle/initiate/1')
  })

  it('getReportTemplate GET', async () => {
    mockGet.mockResolvedValueOnce({ data: { data: { tpl: 'x' } } })
    await fundLifecycleApi.getReportTemplate(1)
    expect(mockGet).toHaveBeenCalledWith('/fund-lifecycle/report-template/1')
  })

  it('lockBudget POST', async () => {
    mockPost.mockResolvedValueOnce({ data: { success: true } })
    await fundLifecycleApi.lockBudget(1)
    expect(mockPost).toHaveBeenCalledWith('/fund-lifecycle/budget-lock/1')
  })

  it('complianceCheck GET', async () => {
    mockGet.mockResolvedValueOnce({ data: { data: { ok: true } } })
    await fundLifecycleApi.complianceCheck(1)
    expect(mockGet).toHaveBeenCalledWith('/fund-lifecycle/compliance-check/1')
  })

  it('budgetAggregation GET with params', async () => {
    mockGet.mockResolvedValueOnce({ data: { data: [] } })
    await fundLifecycleApi.budgetAggregation({ group_by: 'year' })
    expect(mockGet).toHaveBeenCalledWith('/fund-lifecycle/budget-aggregation', { group_by: 'year' })
  })

  it('quotaLock POST', async () => {
    mockPost.mockResolvedValueOnce({ data: { success: true } })
    await fundLifecycleApi.quotaLock(5)
    expect(mockPost).toHaveBeenCalledWith('/fund-lifecycle/quota-lock/5')
  })

  it('allocationPlan GET', async () => {
    mockGet.mockResolvedValueOnce({ data: { data: { plan: {} } } })
    await fundLifecycleApi.allocationPlan(1)
    expect(mockGet).toHaveBeenCalledWith('/fund-lifecycle/allocation-plan/1')
  })

  it('listTransferVouchers GET', async () => {
    mockGet.mockResolvedValueOnce({ data: { data: [] } })
    await fundLifecycleApi.listTransferVouchers({ page: 1 })
    expect(mockGet).toHaveBeenCalledWith('/fund-lifecycle/transfer-vouchers', { page: 1 })
  })

  it('createTransferVoucher POST', async () => {
    mockPost.mockResolvedValueOnce({ data: { id: 1 } })
    await fundLifecycleApi.createTransferVoucher({ amount: 100 })
    expect(mockPost).toHaveBeenCalledWith('/fund-lifecycle/transfer-vouchers', { amount: 100 })
  })

  it('getTransferVoucher GET', async () => {
    mockGet.mockResolvedValueOnce({ data: { id: 1 } })
    await fundLifecycleApi.getTransferVoucher(1)
    expect(mockGet).toHaveBeenCalledWith('/fund-lifecycle/transfer-vouchers/1')
  })

  it('updateTransferVoucher PUT', async () => {
    mockPut.mockResolvedValueOnce({ data: { success: true } })
    await fundLifecycleApi.updateTransferVoucher(1, { amount: 200 })
    expect(mockPut).toHaveBeenCalledWith('/fund-lifecycle/transfer-vouchers/1', { amount: 200 })
  })

  it('deleteTransferVoucher DELETE', async () => {
    mockDelete.mockResolvedValueOnce({ data: { success: true } })
    await fundLifecycleApi.deleteTransferVoucher(1)
    expect(mockDelete).toHaveBeenCalledWith('/fund-lifecycle/transfer-vouchers/1')
  })

  it('confirmTransferVoucher POST', async () => {
    mockPost.mockResolvedValueOnce({ data: { success: true } })
    await fundLifecycleApi.confirmTransferVoucher(1)
    expect(mockPost).toHaveBeenCalledWith('/fund-lifecycle/transfer-vouchers/1/confirm')
  })

  it('transferLedger GET', async () => {
    mockGet.mockResolvedValueOnce({ data: { data: { ledger: [] } } })
    await fundLifecycleApi.transferLedger(1)
    expect(mockGet).toHaveBeenCalledWith('/fund-lifecycle/transfer-ledger/1')
  })

  it('listContracts GET', async () => {
    mockGet.mockResolvedValueOnce({ data: { data: [] } })
    await fundLifecycleApi.listContracts({ status: 'active' })
    expect(mockGet).toHaveBeenCalledWith('/fund-lifecycle/contracts', { status: 'active' })
  })

  it('createContract POST', async () => {
    mockPost.mockResolvedValueOnce({ data: { id: 1 } })
    await fundLifecycleApi.createContract({ name: 'c1' })
    expect(mockPost).toHaveBeenCalledWith('/fund-lifecycle/contracts', { name: 'c1' })
  })

  it('getContract GET', async () => {
    mockGet.mockResolvedValueOnce({ data: { id: 1 } })
    await fundLifecycleApi.getContract(1)
    expect(mockGet).toHaveBeenCalledWith('/fund-lifecycle/contracts/1')
  })

  it('updateContract PUT', async () => {
    mockPut.mockResolvedValueOnce({ data: { success: true } })
    await fundLifecycleApi.updateContract(1, { name: 'c2' })
    expect(mockPut).toHaveBeenCalledWith('/fund-lifecycle/contracts/1', { name: 'c2' })
  })

  it('deleteContract DELETE', async () => {
    mockDelete.mockResolvedValueOnce({ data: { success: true } })
    await fundLifecycleApi.deleteContract(1)
    expect(mockDelete).toHaveBeenCalledWith('/fund-lifecycle/contracts/1')
  })

  it('createContractPayment POST', async () => {
    mockPost.mockResolvedValueOnce({ data: { success: true } })
    await fundLifecycleApi.createContractPayment(1, { amount: 100 })
    expect(mockPost).toHaveBeenCalledWith('/fund-lifecycle/contracts/1/payments', { amount: 100 })
  })

  it('monitoringDeviation GET', async () => {
    mockGet.mockResolvedValueOnce({ data: { data: { dev: 0 } } })
    await fundLifecycleApi.monitoringDeviation(1)
    expect(mockGet).toHaveBeenCalledWith('/fund-lifecycle/monitoring/deviation/1')
  })

  // W8-T019：fundFlow/getFundFlowTree 死 API 已删除，用例同步移除。

  it('listAnomalies GET', async () => {
    mockGet.mockResolvedValueOnce({ data: { data: [] } })
    await fundLifecycleApi.listAnomalies({ severity: 'high' })
    expect(mockGet).toHaveBeenCalledWith('/fund-lifecycle/anomalies', { severity: 'high' })
  })

  it('detectAnomalies POST', async () => {
    mockPost.mockResolvedValueOnce({ data: { anomalies: [] } })
    await fundLifecycleApi.detectAnomalies(1)
    expect(mockPost).toHaveBeenCalledWith('/fund-lifecycle/anomalies/detect/1')
  })

  it('resolveAnomaly POST', async () => {
    mockPost.mockResolvedValueOnce({ data: { success: true } })
    await fundLifecycleApi.resolveAnomaly(5, 'fixed')
    expect(mockPost).toHaveBeenCalledWith('/fund-lifecycle/anomalies/5/resolve', { resolution: 'fixed' })
  })

  it('createSettlement POST', async () => {
    mockPost.mockResolvedValueOnce({ data: { success: true } })
    await fundLifecycleApi.createSettlement(1, { amount: 1000 })
    expect(mockPost).toHaveBeenCalledWith('/fund-lifecycle/settlement/1', { amount: 1000 })
  })

  it('createSettlement 无 data 用 {}', async () => {
    mockPost.mockResolvedValueOnce({ data: { success: true } })
    await fundLifecycleApi.createSettlement(1)
    expect(mockPost).toHaveBeenCalledWith('/fund-lifecycle/settlement/1', {})
  })

  it('updateSettlement PUT', async () => {
    mockPut.mockResolvedValueOnce({ data: { success: true } })
    await fundLifecycleApi.updateSettlement(2, { amount: 2000 })
    expect(mockPut).toHaveBeenCalledWith('/fund-lifecycle/settlement/2', { amount: 2000 })
  })

  it('approveSettlement POST', async () => {
    mockPost.mockResolvedValueOnce({ data: { success: true } })
    await fundLifecycleApi.approveSettlement(2, { approved: true })
    expect(mockPost).toHaveBeenCalledWith('/fund-lifecycle/settlement/2/approve', { approved: true })
  })

  it('approveSettlement 无 data 用 {}', async () => {
    mockPost.mockResolvedValueOnce({ data: { success: true } })
    await fundLifecycleApi.approveSettlement(2)
    expect(mockPost).toHaveBeenCalledWith('/fund-lifecycle/settlement/2/approve', {})
  })

  it('getPerformance GET', async () => {
    mockGet.mockResolvedValueOnce({ data: { data: { score: 90 } } })
    await fundLifecycleApi.getPerformance(1)
    expect(mockGet).toHaveBeenCalledWith('/fund-lifecycle/performance/1')
  })

  it('getHealth GET', async () => {
    mockGet.mockResolvedValueOnce({ data: { data: { score: 85 } } })
    await fundLifecycleApi.getHealth(1)
    expect(mockGet).toHaveBeenCalledWith('/fund-lifecycle/health/1')
  })

  it('batchHealth POST with project_ids', async () => {
    mockPost.mockResolvedValueOnce({ data: { data: { 1: 80, 2: 90 } } })
    await fundLifecycleApi.batchHealth([1, 2])
    expect(mockPost).toHaveBeenCalledWith('/fund-lifecycle/health/batch', { project_ids: [1, 2] })
  })

  it('listAllocationOrders GET', async () => {
    mockGet.mockResolvedValueOnce({ data: { data: [] } })
    await fundLifecycleApi.listAllocationOrders({ status: 'issued' })
    expect(mockGet).toHaveBeenCalledWith('/fund-lifecycle/allocation-orders', { status: 'issued' })
  })

  it('createAllocationOrder POST', async () => {
    mockPost.mockResolvedValueOnce({ data: { id: 1 } })
    await fundLifecycleApi.createAllocationOrder({ amount: 100 })
    expect(mockPost).toHaveBeenCalledWith('/fund-lifecycle/allocation-orders', { amount: 100 })
  })

  it('issueAllocationOrder POST', async () => {
    mockPost.mockResolvedValueOnce({ data: { success: true } })
    await fundLifecycleApi.issueAllocationOrder(9)
    expect(mockPost).toHaveBeenCalledWith('/fund-lifecycle/allocation-orders/9/issue')
  })

  it('quotaAdjust PUT', async () => {
    mockPut.mockResolvedValueOnce({ data: { success: true } })
    await fundLifecycleApi.quotaAdjust(5, { amount: 50 })
    expect(mockPut).toHaveBeenCalledWith('/fund-lifecycle/quota-adjust/5', { amount: 50 })
  })

  it('uploadVoucherAttachment POST FormData', async () => {
    mockPost.mockResolvedValueOnce({ data: { id: 1 } })
    const file = new File(['x'], 'v.png')
    await fundLifecycleApi.uploadVoucherAttachment(9, file)
    const [url, fd, config] = mockPost.mock.calls[0]
    expect(url).toBe('/fund-lifecycle/transfer-vouchers/9/attachments')
    expect(fd).toBeInstanceOf(FormData)
    expect(fd.get('file')).toBe(file)
    expect(config.headers['Content-Type']).toBe('multipart/form-data')
  })

  it('getInspectionClues GET', async () => {
    mockGet.mockResolvedValueOnce({ data: { data: { clues: [] } } })
    await fundLifecycleApi.getInspectionClues(1)
    expect(mockGet).toHaveBeenCalledWith('/fund-lifecycle/inspection-clues/1')
  })

  it('verifyAsset POST', async () => {
    mockPost.mockResolvedValueOnce({ data: { success: true } })
    await fundLifecycleApi.verifyAsset(2, { asset_ok: true })
    expect(mockPost).toHaveBeenCalledWith('/fund-lifecycle/settlement/2/verify-asset', { asset_ok: true })
  })

  it('getPerformanceReport GET', async () => {
    mockGet.mockResolvedValueOnce({ data: { data: { report: {} } } })
    await fundLifecycleApi.getPerformanceReport(1)
    expect(mockGet).toHaveBeenCalledWith('/fund-lifecycle/performance-report/1')
  })

  it('getFeasibilityReport GET', async () => {
    mockGet.mockResolvedValueOnce({ data: { data: { report: {} } } })
    await fundLifecycleApi.getFeasibilityReport(1)
    expect(mockGet).toHaveBeenCalledWith('/fund-lifecycle/feasibility-report/1')
  })
})

describe('api/fundLifecycle res.data 回退（响应无 data 字段时原样返回）', () => {
  beforeEach(() => vi.clearAllMocks())

  const cases: Array<[string, () => Promise<any>, string]> = [
    ['getPhases', () => fundLifecycleApi.getPhases(1), '/fund-lifecycle/phases/1'],
    ['getReportTemplate', () => fundLifecycleApi.getReportTemplate(1), '/fund-lifecycle/report-template/1'],
    ['complianceCheck', () => fundLifecycleApi.complianceCheck(1), '/fund-lifecycle/compliance-check/1'],
    ['budgetAggregation', () => fundLifecycleApi.budgetAggregation(), '/fund-lifecycle/budget-aggregation'],
    ['allocationPlan', () => fundLifecycleApi.allocationPlan(1), '/fund-lifecycle/allocation-plan/1'],
    ['listAllocationOrders', () => fundLifecycleApi.listAllocationOrders(), '/fund-lifecycle/allocation-orders'],
    ['listTransferVouchers', () => fundLifecycleApi.listTransferVouchers(), '/fund-lifecycle/transfer-vouchers'],
    ['getTransferVoucher', () => fundLifecycleApi.getTransferVoucher(1), '/fund-lifecycle/transfer-vouchers/1'],
    ['transferLedger', () => fundLifecycleApi.transferLedger(1), '/fund-lifecycle/transfer-ledger/1'],
    ['listContracts', () => fundLifecycleApi.listContracts(), '/fund-lifecycle/contracts'],
    ['getContract', () => fundLifecycleApi.getContract(1), '/fund-lifecycle/contracts/1'],
    ['monitoringDeviation', () => fundLifecycleApi.monitoringDeviation(1), '/fund-lifecycle/monitoring/deviation/1'],
    ['fundFlow', () => fundLifecycleApi.fundFlow(1), '/fund-lifecycle/monitoring/fund-flow/1'],
    ['listAnomalies', () => fundLifecycleApi.listAnomalies(), '/fund-lifecycle/anomalies'],
    ['getInspectionClues', () => fundLifecycleApi.getInspectionClues(1), '/fund-lifecycle/inspection-clues/1'],
    ['getPerformance', () => fundLifecycleApi.getPerformance(1), '/fund-lifecycle/performance/1'],
    ['getPerformanceReport', () => fundLifecycleApi.getPerformanceReport(1), '/fund-lifecycle/performance-report/1'],
    ['getFeasibilityReport', () => fundLifecycleApi.getFeasibilityReport(1), '/fund-lifecycle/feasibility-report/1'],
    ['getFundFlowTree', () => fundLifecycleApi.getFundFlowTree(1), '/fund-lifecycle/monitoring/fund-flow-tree/1'],
    ['getHealth', () => fundLifecycleApi.getHealth(1), '/fund-lifecycle/health/1'],
  ]

  it.each(cases)('%s 响应无 data 字段时返回原始响应', async (_name, fn) => {
    const raw = { raw: true }
    mockGet.mockResolvedValueOnce(raw)
    const r = await fn()
    expect(mockGet).toHaveBeenCalled()
    expect(r).toBe(raw)
  })

  it('batchHealth 响应无 data 字段时返回原始响应', async () => {
    const raw = { raw: true }
    mockPost.mockResolvedValueOnce(raw)
    const r = await fundLifecycleApi.batchHealth([1])
    expect(r).toBe(raw)
  })
})



describe('fundLifecycleApi 合同附件', () => {
  it('listContractAttachments GET /fund-lifecycle/contracts/:id/attachments', async () => {
    mockGet.mockResolvedValueOnce({ data: { data: { items: [] } } })
    await fundLifecycleApi.listContractAttachments(5)
    expect(mockGet).toHaveBeenCalledWith('/fund-lifecycle/contracts/5/attachments')
  })

  it('uploadContractAttachment POST 携带 data', async () => {
    mockPost.mockResolvedValueOnce({ data: { data: { items: [] } } })
    await fundLifecycleApi.uploadContractAttachment(5, { url: '/u/a.pdf', file_name: 'a.pdf' })
    expect(mockPost).toHaveBeenCalledWith('/fund-lifecycle/contracts/5/attachments', {
      url: '/u/a.pdf',
      file_name: 'a.pdf',
    })
  })

  it('附件接口 res 无 data 时回退到 res 本身', async () => {
    mockGet.mockResolvedValueOnce({ data: { items: ['x'] } })
    const listRes = await fundLifecycleApi.listContractAttachments(6)
    expect(listRes.items).toContain('x')
    mockPost.mockResolvedValueOnce({ data: { items: ['y'] } })
    const upRes = await fundLifecycleApi.uploadContractAttachment(6, { url: '/u/b.pdf' })
    expect(upRes.items).toContain('y')
    // 假分支: res.data 为空时返回 res 本身
    mockGet.mockResolvedValueOnce({ items: ['z'] })
    const listRes2 = await fundLifecycleApi.listContractAttachments(7)
    expect(listRes2.items).toContain('z')
    mockPost.mockResolvedValueOnce({ items: ['w'] })
    const upRes2 = await fundLifecycleApi.uploadContractAttachment(7, { url: '/u/c.pdf' })
    expect(upRes2.items).toContain('w')
  })
})
