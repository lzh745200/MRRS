import { describe, it, expect, vi, beforeEach } from 'vitest'

const { mockGet } = vi.hoisted(() => ({
  mockGet: vi.fn(),
}))

vi.mock('@/api/request', () => ({
  get: mockGet,
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

import { getUsers, getUserById, getCurrentUser, listStaff } from '@/api/queries/user'

describe('api/queries/user', () => {
  beforeEach(() => vi.clearAllMocks())

  it('getUsers 无参 GET /users', async () => {
    const body = { items: [], total: 0 }
    mockGet.mockResolvedValueOnce(body)
    const r = await getUsers()
    expect(mockGet).toHaveBeenCalledWith('/users', undefined)
    expect(r).toBe(body)
  })

  it('getUsers 带分页参数', async () => {
    const body = { items: [{ id: '1' }], total: 1 }
    mockGet.mockResolvedValueOnce(body)
    const r = await getUsers({ page: 2, page_size: 10 })
    expect(mockGet).toHaveBeenCalledWith('/users', { page: 2, page_size: 10 })
    expect(r).toBe(body)
  })

  it('listStaff GET /users/staff-list（审批转交/任务分配用）', async () => {
    const body = { items: [], total: 0 }
    mockGet.mockResolvedValueOnce(body)
    const r = await listStaff({ page_size: 50, keyword: '张' })
    expect(mockGet).toHaveBeenCalledWith('/users/staff-list', { page_size: 50, keyword: '张' })
    expect(r).toBe(body)
  })

  it('getUserById GET /users/:id', async () => {
    const body = { id: 'u1', name: '张三' }
    mockGet.mockResolvedValueOnce(body)
    const r = await getUserById('u1')
    expect(mockGet).toHaveBeenCalledWith('/users/u1')
    expect(r).toBe(body)
  })

  it('getCurrentUser GET /auth/me', async () => {
    const body = { id: 'u1', username: 'admin' }
    mockGet.mockResolvedValueOnce(body)
    const r = await getCurrentUser()
    expect(mockGet).toHaveBeenCalledWith('/auth/me')
    expect(r).toBe(body)
  })
})
