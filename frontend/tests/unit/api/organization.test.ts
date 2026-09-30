import { describe, it, expect, vi, beforeEach } from 'vitest'

// organization.ts 只从 '@/api/request' 导入 get/post/put/del（自动拆信封，resolve body 即可）
const { mockGet, mockPost, mockPut, mockDel } = vi.hoisted(() => ({
  mockGet: vi.fn().mockResolvedValue({}),
  mockPost: vi.fn().mockResolvedValue({}),
  mockPut: vi.fn().mockResolvedValue({}),
  mockDel: vi.fn().mockResolvedValue({}),
}))

vi.mock('@/api/request', () => ({
  get: (...args: any[]) => mockGet(...args),
  post: (...args: any[]) => mockPost(...args),
  put: (...args: any[]) => mockPut(...args),
  del: (...args: any[]) => mockDel(...args),
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

import {
  getOrganizations,
  getOrganization,
  getOrganizationTree,
  createOrganization,
  updateOrganization,
  deleteOrganization,
  batchUpdateSortOrders,
  getMyOrganization,
  getSubordinates,
  getTypeOptions,
  getChildren,
  getAncestors,
  moveOrganization,
  activateOrganization,
  deactivateOrganization,
  getOrganizationStatistics,
  getOrganizationMembers,
  getOrganizationDetail,
} from '@/api/organization'

describe('api/organization', () => {
  beforeEach(() => vi.clearAllMocks())

  it('getOrganizations GET /organizations with params', async () => {
    const body = { items: [], total: 0 }
    mockGet.mockResolvedValueOnce(body)
    const r = await getOrganizations({ page: 1 })
    expect(mockGet).toHaveBeenCalledWith('/organizations', { page: 1 })
    expect(r).toBe(body)
  })

  it('getOrganization GET /organizations/{id}', async () => {
    const body = { id: 3, name: 'X' }
    mockGet.mockResolvedValueOnce(body)
    const r = await getOrganization(3)
    expect(mockGet).toHaveBeenCalledWith('/organizations/3')
    expect(r).toBe(body)
  })

  it('getOrganizationTree GET /organizations/tree', async () => {
    const body = [{ id: 1, children: [] }]
    mockGet.mockResolvedValueOnce(body)
    const r = await getOrganizationTree()
    expect(mockGet).toHaveBeenCalledWith('/organizations/tree')
    expect(r).toBe(body)
  })

  it('createOrganization POST /organizations', async () => {
    const body = { id: 9 }
    mockPost.mockResolvedValueOnce(body)
    const data = { name: '新单位' }
    const r = await createOrganization(data)
    expect(mockPost).toHaveBeenCalledWith('/organizations', data)
    expect(r).toBe(body)
  })

  it('updateOrganization PUT /organizations/{id}', async () => {
    const body = { id: 4, name: 'Y' }
    mockPut.mockResolvedValueOnce(body)
    const r = await updateOrganization(4, { name: 'Y' })
    expect(mockPut).toHaveBeenCalledWith('/organizations/4', { name: 'Y' })
    expect(r).toBe(body)
  })

  // 后端 DELETE /organizations/{id} 的 confirm_password 为 Query 且必填语义
  // （空值恒 400「二次确认失败」），故前端 fail-closed：缺密码不发请求。
  it('deleteOrganization 缺密码时 fail-closed 抛错且不发请求', async () => {
    mockDel.mockClear()
    await expect(deleteOrganization(4)).rejects.toThrow('删除组织需要二次确认密码')
    await expect(deleteOrganization(4, '')).rejects.toThrow('删除组织需要二次确认密码')
    expect(mockDel).not.toHaveBeenCalled()
  })

  it('deleteOrganization 非法 id fail-closed', async () => {
    mockDel.mockClear()
    await expect(deleteOrganization(0, 'pass123')).rejects.toThrow('无效的组织 ID')
    await expect(deleteOrganization(1.5, 'pass123')).rejects.toThrow('无效的组织 ID')
    expect(mockDel).not.toHaveBeenCalled()
  })

  it('deleteOrganization 携带 confirm_password 二次确认（URL 编码）', async () => {
    const body = { success: true }
    mockDel.mockResolvedValueOnce(body)
    const r = await deleteOrganization(4, 'p@ss 1&2')
    expect(mockDel).toHaveBeenCalledWith('/organizations/4?confirm_password=p%40ss%201%262')
    expect(r).toBe(body)
  })

  it('batchUpdateSortOrders POST /organizations/batch-update-sort', async () => {
    mockPost.mockResolvedValueOnce({ updated: 2 })
    const d = [
      { id: 1, sort_order: 1 },
      { id: 2, sort_order: 2 },
    ]
    await batchUpdateSortOrders(d)
    expect(mockPost).toHaveBeenCalledWith('/organizations/batch-update-sort', d)
  })

  it('getMyOrganization GET /organizations/my-organization', async () => {
    const body = { id: 1 }
    mockGet.mockResolvedValueOnce(body)
    const r = await getMyOrganization()
    expect(mockGet).toHaveBeenCalledWith('/organizations/my-organization')
    expect(r).toBe(body)
  })

  it('getSubordinates GET /organizations/subordinates', async () => {
    const body = [{ id: 2 }]
    mockGet.mockResolvedValueOnce(body)
    const r = await getSubordinates()
    expect(mockGet).toHaveBeenCalledWith('/organizations/subordinates')
    expect(r).toBe(body)
  })

  it('getTypeOptions GET /organizations/types/options', async () => {
    const body = [{ value: 'army', label: '部队' }]
    mockGet.mockResolvedValueOnce(body)
    const r = await getTypeOptions()
    expect(mockGet).toHaveBeenCalledWith('/organizations/types/options')
    expect(r).toBe(body)
  })

  it('getChildren GET /organizations/{id}/children', async () => {
    mockGet.mockResolvedValueOnce([])
    await getChildren(6)
    expect(mockGet).toHaveBeenCalledWith('/organizations/6/children')
  })

  it('getAncestors GET /organizations/{id}/ancestors', async () => {
    mockGet.mockResolvedValueOnce([])
    await getAncestors(6)
    expect(mockGet).toHaveBeenCalledWith('/organizations/6/ancestors')
  })

  it('moveOrganization POST /organizations/{id}/move', async () => {
    mockPost.mockResolvedValueOnce({ success: true })
    const data = { parent_id: 10 }
    await moveOrganization(6, data)
    expect(mockPost).toHaveBeenCalledWith('/organizations/6/move', data)
  })

  it('activateOrganization POST /organizations/{id}/activate', async () => {
    mockPost.mockResolvedValueOnce({ success: true })
    await activateOrganization(7)
    expect(mockPost).toHaveBeenCalledWith('/organizations/7/activate')
  })

  it('deactivateOrganization POST /organizations/{id}/deactivate', async () => {
    mockPost.mockResolvedValueOnce({ success: true })
    await deactivateOrganization(7)
    expect(mockPost).toHaveBeenCalledWith('/organizations/7/deactivate')
  })

  it('getOrganizationStatistics GET /organizations/statistics/summary', async () => {
    const body = { total: 10 }
    mockGet.mockResolvedValueOnce(body)
    const r = await getOrganizationStatistics()
    expect(mockGet).toHaveBeenCalledWith('/organizations/statistics/summary')
    expect(r).toBe(body)
  })

  it('getOrganizationMembers GET /organizations/{id}/members 带 params', async () => {
    const body = { items: [] }
    mockGet.mockResolvedValueOnce(body)
    const r = await getOrganizationMembers(8, { page: 1 })
    expect(mockGet).toHaveBeenCalledWith('/organizations/8/members', { page: 1 })
    expect(r).toBe(body)
  })

  it('getOrganizationMembers 无 params', async () => {
    mockGet.mockResolvedValueOnce({ items: [] })
    await getOrganizationMembers(8)
    expect(mockGet).toHaveBeenCalledWith('/organizations/8/members', undefined)
  })

  it('getOrganizationDetail GET /organizations/{id}/detail', async () => {
    const body = { id: 8, name: 'X', member_count: 3 }
    mockGet.mockResolvedValueOnce(body)
    const r = await getOrganizationDetail(8)
    expect(mockGet).toHaveBeenCalledWith('/organizations/8/detail')
    expect(r).toBe(body)
  })
})
