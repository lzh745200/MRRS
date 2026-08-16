/**
 * api/permissionPack.ts 测试
 * 覆盖：6 个端点的 URL/载荷透传，列表三形态解包（数组直返/data/items/空兜底），
 * 写操作 res.data ?? res 回退两侧。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'

const { mockGet, mockPost, mockPut, mockDel } = vi.hoisted(() => ({
  mockGet: vi.fn(),
  mockPost: vi.fn(),
  mockPut: vi.fn(),
  mockDel: vi.fn(),
}))

// src/api/permissionPack.ts 实际 import：import { get, post, put, del } from '@/api/request'
vi.mock('@/api/request', () => ({
  get: mockGet,
  post: mockPost,
  put: mockPut,
  del: mockDel,
  getCsrfToken: vi.fn(() => Promise.resolve('test-csrf')),
}))

import {
  listPermissionPacks,
  createPermissionPack,
  updatePermissionPack,
  deletePermissionPack,
  bindPackUsers,
  unbindPackUsers,
} from '@/api/permissionPack'

describe('api/permissionPack', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('listPermissionPacks：GET /permission-packs，响应为数组时直返', async () => {
    const list = [{ id: 1, name: '基础包' }]
    mockGet.mockResolvedValue(list)
    const result = await listPermissionPacks()
    expect(mockGet).toHaveBeenCalledWith('/permission-packs')
    expect(result).toEqual(list)
  })

  it('listPermissionPacks：信封 {data:[...]} 与 {items:[...]} 两种形态', async () => {
    mockGet.mockResolvedValue({ data: [{ id: 2, name: 'A' }] })
    expect(await listPermissionPacks()).toEqual([{ id: 2, name: 'A' }])

    mockGet.mockResolvedValue({ items: [{ id: 3, name: 'B' }] })
    expect(await listPermissionPacks()).toEqual([{ id: 3, name: 'B' }])
  })

  it('listPermissionPacks：空响应/异常形态 → []', async () => {
    mockGet.mockResolvedValue(undefined)
    expect(await listPermissionPacks()).toEqual([])
    mockGet.mockResolvedValue({ data: 'not-array' })
    expect(await listPermissionPacks()).toEqual([])
  })

  it('createPermissionPack：POST 透传载荷，res.data / res 两侧', async () => {
    const payload = { name: '包A', description: 'd', menu_keys: ['dashboard'], is_active: true }
    mockPost.mockResolvedValue({ data: { id: 1, ...payload } })
    expect(await createPermissionPack(payload)).toEqual({ id: 1, ...payload })
    expect(mockPost).toHaveBeenCalledWith('/permission-packs', payload)

    mockPost.mockResolvedValue({ id: 2 })
    expect((await createPermissionPack(payload)).id).toBe(2)
  })

  it('updatePermissionPack：PUT /permission-packs/{id} 部分字段，res 兜底', async () => {
    mockPut.mockResolvedValue({ data: { id: 5, name: '新名' } })
    expect(await updatePermissionPack(5, { name: '新名' })).toEqual({ id: 5, name: '新名' })
    expect(mockPut).toHaveBeenCalledWith('/permission-packs/5', { name: '新名' })

    mockPut.mockResolvedValue(undefined)
    expect(await updatePermissionPack(5, { name: 'x' })).toBeUndefined()
  })

  it('deletePermissionPack：DELETE /permission-packs/{id}', async () => {
    mockDel.mockResolvedValue({})
    await deletePermissionPack(7)
    expect(mockDel).toHaveBeenCalledWith('/permission-packs/7')
  })

  it('bindPackUsers：POST bind-users 携带 user_ids，res.data / res 两侧', async () => {
    mockPost.mockResolvedValue({ data: { bound_user_ids: [1, 2] } })
    expect(await bindPackUsers(9, [1, 2])).toEqual({ bound_user_ids: [1, 2] })
    expect(mockPost).toHaveBeenCalledWith('/permission-packs/9/bind-users', { user_ids: [1, 2] })

    mockPost.mockResolvedValue({ bound_user_ids: [3] })
    expect(await bindPackUsers(9, [3])).toEqual({ bound_user_ids: [3] })
  })

  it('unbindPackUsers：POST unbind-users 携带 user_ids，res 兜底', async () => {
    mockPost.mockResolvedValue({ data: { unbound_user_ids: [4] } })
    expect(await unbindPackUsers(9, [4])).toEqual({ unbound_user_ids: [4] })
    expect(mockPost).toHaveBeenCalledWith('/permission-packs/9/unbind-users', { user_ids: [4] })

    mockPost.mockResolvedValue(undefined)
    expect(await unbindPackUsers(9, [])).toBeUndefined()
  })
})
