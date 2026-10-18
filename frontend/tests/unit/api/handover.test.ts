import { describe, it, expect, vi, beforeEach } from 'vitest'

const { mockGet, mockPost } = vi.hoisted(() => ({
  mockGet: vi.fn(),
  mockPost: vi.fn(),
}))

vi.mock('@/api/request', () => ({
  get: mockGet,
  post: mockPost,
  getCsrfToken: vi.fn(() => Promise.resolve('test-csrf')),
}))

import {
  ASSET_ROLE_LABELS,
  ASSET_TYPE_LABELS,
  executeHandover,
  getHandoverCandidates,
  getHandoverHistory,
  getHandoverInventory,
} from '@/api/handover'

describe('api/handover', () => {
  beforeEach(() => vi.clearAllMocks())

  it('标签常量与后端 ASSET_TYPES / ASSET_LABELS 对齐', () => {
    expect(ASSET_TYPE_LABELS).toEqual({
      village: '帮扶村',
      project: '帮扶项目',
      todo: '待办事项',
      approval: '审批中申请',
    })
    expect(ASSET_ROLE_LABELS.owner).toBe('责任人')
    expect(ASSET_ROLE_LABELS.both).toBe('我发起且待我审批')
  })

  it('getHandoverInventory → GET /handover/inventory', async () => {
    const body = { groups: [], total: 0, generated_at: '2026-10-17T00:00:00Z' }
    mockGet.mockResolvedValueOnce(body)
    const result = await getHandoverInventory()
    expect(mockGet).toHaveBeenCalledWith('/handover/inventory')
    expect(result).toBe(body)
  })

  it('getHandoverCandidates → GET /handover/candidates（带查询参数 / 缺省空对象）', async () => {
    const body = { items: [{ id: 2, username: 'lisi' }], total: 1 }
    mockGet.mockResolvedValueOnce(body)
    const result = await getHandoverCandidates({ keyword: 'li', limit: 10 })
    expect(mockGet).toHaveBeenCalledWith('/handover/candidates', { keyword: 'li', limit: 10 })
    expect(result).toBe(body)

    mockGet.mockResolvedValueOnce({ items: [], total: 0 })
    await getHandoverCandidates()
    expect(mockGet).toHaveBeenLastCalledWith('/handover/candidates', {})
  })

  it('executeHandover → POST /handover/execute（完整载荷）', async () => {
    const payload = {
      to_user_id: 2,
      scope: ['village', 'todo'] as const,
      item_ids: { village: [1], todo: [3] },
      note: '轮岗',
    }
    const receipt = {
      record_id: 10,
      record_no: 'HO-1',
      from_user: { id: 7, username: 'zhangsan' },
      to_user: { id: 2, username: 'lisi' },
      items: [],
      counts: { village: 1, project: 0, todo: 1, approval: 0 },
      total: 2,
    }
    mockPost.mockResolvedValueOnce(receipt)
    const result = await executeHandover({ ...payload, scope: [...payload.scope] })
    expect(mockPost).toHaveBeenCalledWith('/handover/execute', {
      ...payload,
      scope: ['village', 'todo'],
    })
    expect(result.record_no).toBe('HO-1')
    expect(result.total).toBe(2)
  })

  it('executeHandover → 最小载荷', async () => {
    mockPost.mockResolvedValueOnce({ record_no: 'HO-2', total: 0 })
    await executeHandover({ to_user_id: 2 })
    expect(mockPost).toHaveBeenCalledWith('/handover/execute', { to_user_id: 2 })
  })

  it('getHandoverHistory → GET /handover/history（带分页/日期参数 / 缺省空对象）', async () => {
    const body = { items: [], total: 0, page: 1, page_size: 10 }
    mockGet.mockResolvedValueOnce(body)
    const result = await getHandoverHistory({
      page: 2,
      page_size: 10,
      date_from: '2026-10-01',
      date_to: '2026-10-31',
    })
    expect(mockGet).toHaveBeenCalledWith('/handover/history', {
      page: 2,
      page_size: 10,
      date_from: '2026-10-01',
      date_to: '2026-10-31',
    })
    expect(result).toBe(body)

    mockGet.mockResolvedValueOnce(body)
    await getHandoverHistory()
    expect(mockGet).toHaveBeenLastCalledWith('/handover/history', {})
  })
})
