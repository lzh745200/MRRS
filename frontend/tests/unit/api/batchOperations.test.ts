import { describe, it, expect, vi, beforeEach } from 'vitest'
import axios from 'axios'

const { mockGet, mockPost } = vi.hoisted(() => ({
  mockGet: vi.fn(),
  mockPost: vi.fn(),
}))

vi.mock('@/api/request', () => ({
  get: mockGet,
  post: mockPost,
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

import {
  batchUpdate,
  batchDelete,
  batchExport,
  validateBatch,
  getBatchStatus,
} from '@/api/batchOperations'

describe('api/batchOperations', () => {
  beforeEach(() => vi.clearAllMocks())

  it('batchUpdate POST /batch/update', async () => {
    const body = { updated: 2 }
    mockPost.mockResolvedValueOnce(body)
    const data = { table_name: 'villages', ids: [1, 2], updates: { status: 'active' } }
    const r = await batchUpdate(data)
    expect(mockPost).toHaveBeenCalledWith('/batch/update', data)
    expect(r).toBe(body)
  })

  it('batchDelete POST /batch/delete', async () => {
    const body = { deleted: 2 }
    mockPost.mockResolvedValueOnce(body)
    const data = { table_name: 'villages', ids: [1, 2], soft_delete: true }
    const r = await batchDelete(data)
    expect(mockPost).toHaveBeenCalledWith('/batch/delete', data)
    expect(r).toBe(body)
  })

  it('batchExport POST /batch/export', async () => {
    const body = { file_url: '/files/x.xlsx' }
    mockPost.mockResolvedValueOnce(body)
    const data = { table_name: 'villages', ids: [1], format: 'xlsx' }
    const r = await batchExport(data)
    expect(mockPost).toHaveBeenCalledWith('/batch/export', data)
    expect(r).toBe(body)
  })

  it('validateBatch POST /batch/validate 带 query 参数', async () => {
    const body = { valid: true }
    mockPost.mockResolvedValueOnce(body)
    const r = await validateBatch('villages', [1, 2])
    expect(mockPost).toHaveBeenCalledWith('/batch/validate', null, {
      params: { table_name: 'villages', ids: [1, 2] },
      // 后端 ids: List[int] = Query(...) 需要重复键 ids=1&ids=2；
      // axios 默认发 ids[]=… → 后端取不到 ids 恒 422（回归：见下一条用例）
      paramsSerializer: { indexes: null },
    })
    expect(r).toBe(body)
  })

  it('validateBatch 序列化结果为重复同名键 ids=1&ids=2（不是 ids[]=1）', () => {
    // 用真实 axios 验证序列化语义：这是该端点 422 缺陷的根因断言
    const url = axios.getUri({
      url: '/batch/validate',
      params: { table_name: 'villages', ids: [1, 2] },
      paramsSerializer: { indexes: null },
    })
    expect(url).toBe('/batch/validate?table_name=villages&ids=1&ids=2')
    const defaultUrl = axios.getUri({
      url: '/batch/validate',
      params: { table_name: 'villages', ids: [1, 2] },
    })
    // 记录 axios 默认行为（方括号形式）——证明必须显式 indexes:null
    expect(defaultUrl).toContain('ids%5B%5D=1')
  })

  it('getBatchStatus GET /batch/status', async () => {
    const body = { running: 0 }
    mockGet.mockResolvedValueOnce(body)
    const r = await getBatchStatus()
    expect(mockGet).toHaveBeenCalledWith('/batch/status')
    expect(r).toBe(body)
  })
})
