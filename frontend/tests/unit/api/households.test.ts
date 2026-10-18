/**
 * api/households.ts 单元测试（四指标 100%）
 *
 * 覆盖契约 §2 /households 全部端点的 URL/参数透传、返回值透传，
 * 以及导出的 blob 链式下载（triggerDownload 文件名分支）。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  del: vi.fn(),
  requestGet: vi.fn(),
  triggerDownload: vi.fn(),
}))

vi.mock('@/api/request', () => ({
  default: { get: mocks.requestGet },
  get: mocks.get,
  post: mocks.post,
  put: mocks.put,
  del: mocks.del,
}))

vi.mock('@/api/export', () => ({
  triggerDownload: mocks.triggerDownload,
}))

import {
  closeHouseholdRiskRecord,
  createHousehold,
  createHouseholdMember,
  createHouseholdRiskRecord,
  deleteHousehold,
  deleteHouseholdMember,
  exportHouseholds,
  getHousehold,
  getHouseholdAlerts,
  getHouseholdMembers,
  getHouseholds,
  rollupHouseholds,
  updateHousehold,
  updateHouseholdMember,
} from '@/api/households'

describe('api/households', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.get.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 10 })
    mocks.post.mockResolvedValue({ id: 1 })
    mocks.put.mockResolvedValue({ id: 1 })
    mocks.del.mockResolvedValue({ id: 1 })
    mocks.requestGet.mockResolvedValue({ data: new Blob(['x']) })
  })

  it('列表：GET /households 透传筛选参数与响应', async () => {
    const body = { items: [{ id: 1 }], total: 1, page: 2, page_size: 20 }
    mocks.get.mockResolvedValueOnce(body)
    const result = await getHouseholds({ page: 2, page_size: 20, risk_level: 'high' })
    expect(mocks.get).toHaveBeenCalledWith('/households', {
      page: 2,
      page_size: 20,
      risk_level: 'high',
    })
    expect(result).toBe(body)
  })

  it('详情：GET /households/:id', async () => {
    const body = { id: 7, household_name: '张三户' }
    mocks.get.mockResolvedValueOnce(body)
    const result = await getHousehold(7)
    expect(mocks.get).toHaveBeenCalledWith('/households/7')
    expect(result).toBe(body)
  })

  it('新建 / 更新 / 软删', async () => {
    mocks.post.mockResolvedValueOnce({ id: 9 })
    await createHousehold({ household_name: '李四户' })
    expect(mocks.post).toHaveBeenCalledWith('/households', { household_name: '李四户' })

    mocks.put.mockResolvedValueOnce({ id: 9 })
    await updateHousehold(9, { household_name: '李四户2' })
    expect(mocks.put).toHaveBeenCalledWith('/households/9', { household_name: '李四户2' })

    mocks.del.mockResolvedValueOnce({ id: 9 })
    await deleteHousehold(9)
    expect(mocks.del).toHaveBeenCalledWith('/households/9')
  })

  it('家庭成员：列表 / 新增 / 更新 / 删除', async () => {
    mocks.get.mockResolvedValueOnce([{ id: 1, name: '张三' }])
    const list = await getHouseholdMembers(3)
    expect(mocks.get).toHaveBeenCalledWith('/households/3/members')
    expect(list).toEqual([{ id: 1, name: '张三' }])

    mocks.post.mockResolvedValueOnce({ id: 2 })
    await createHouseholdMember(3, { name: '李四' })
    expect(mocks.post).toHaveBeenCalledWith('/households/3/members', { name: '李四' })

    mocks.put.mockResolvedValueOnce({ id: 2 })
    await updateHouseholdMember(3, 2, { name: '李四2' })
    expect(mocks.put).toHaveBeenCalledWith('/households/3/members/2', { name: '李四2' })

    mocks.del.mockResolvedValueOnce({ id: 2 })
    await deleteHouseholdMember(3, 2)
    expect(mocks.del).toHaveBeenCalledWith('/households/3/members/2')
  })

  it('预警清单：默认 / 指定等级', async () => {
    mocks.get.mockResolvedValueOnce([{ household_id: 1 }])
    const alerts = await getHouseholdAlerts()
    expect(mocks.get).toHaveBeenCalledWith('/households/alerts', {})
    expect(alerts).toEqual([{ household_id: 1 }])

    await getHouseholdAlerts({ level: 'high' })
    expect(mocks.get).toHaveBeenCalledWith('/households/alerts', { level: 'high' })
  })

  it('风险记录：登记 / 关闭（默认与带说明）', async () => {
    mocks.post.mockResolvedValueOnce({ id: 5 })
    await createHouseholdRiskRecord(1, { risk_type: 'income_drop', reason: '收入下降' })
    expect(mocks.post).toHaveBeenCalledWith('/households/1/risk-records', {
      risk_type: 'income_drop',
      reason: '收入下降',
    })

    mocks.put.mockResolvedValueOnce({ id: 5 })
    await closeHouseholdRiskRecord(5)
    expect(mocks.put).toHaveBeenCalledWith('/households/risk-records/5/close', {})

    await closeHouseholdRiskRecord(6, { closed_note: '已处理' })
    expect(mocks.put).toHaveBeenCalledWith('/households/risk-records/6/close', {
      closed_note: '已处理',
    })
  })

  it('汇总回填：POST /households/rollup 以 query 传 village_id/year', async () => {
    mocks.post.mockResolvedValueOnce({ total_households: 3 })
    const result = await rollupHouseholds({ village_id: 8, year: 2026 })
    expect(mocks.post).toHaveBeenCalledWith('/households/rollup', undefined, {
      params: { village_id: 8, year: 2026 },
    })
    expect(result).toEqual({ total_households: 3 })
  })

  it('导出 xlsx（带村筛选）：blob 链式下载，文件名含村 id', async () => {
    await exportHouseholds({ format: 'xlsx', village_id: 3, risk_level: 'high' })
    expect(mocks.requestGet).toHaveBeenCalledWith('/households/export', {
      params: { format: 'xlsx', village_id: 3, risk_level: 'high' },
      responseType: 'blob',
    })
    expect(mocks.triggerDownload).toHaveBeenCalledTimes(1)
    expect(mocks.triggerDownload.mock.calls[0][1]).toBe('一户一档台账_村3.xlsx')
  })

  it('导出 csv（无村筛选）：文件名无村后缀', async () => {
    await exportHouseholds({ format: 'csv' })
    expect(mocks.requestGet).toHaveBeenCalledWith('/households/export', {
      params: { format: 'csv' },
      responseType: 'blob',
    })
    expect(mocks.triggerDownload.mock.calls[0][1]).toBe('一户一档台账.csv')
  })
})
