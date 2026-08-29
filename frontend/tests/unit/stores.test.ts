import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useUserStore } from '@/stores/user'

vi.mock('@/api/request', () => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  del: vi.fn(),
  apiRequest: vi.fn(),
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

import { get, post, put, del } from '@/api/request'
const mockGet = get as ReturnType<typeof vi.fn>
const mockPost = post as ReturnType<typeof vi.fn>
const mockPut = put as ReturnType<typeof vi.fn>
const mockDel = del as ReturnType<typeof vi.fn>

vi.mock('@/utils/authStorage', () => ({
  AuthStorage: { clear: vi.fn(), getUser: vi.fn(() => null), getToken: vi.fn(() => null) },
}))

describe('useUserStore', () => {
  let store: ReturnType<typeof useUserStore>
  beforeEach(() => {
    setActivePinia(createPinia())
    store = useUserStore()
    vi.clearAllMocks()
  })

  it('initializes with empty defaults', () => {
    expect(store.userList).toEqual([])
    expect(store.total).toBe(0)
    expect(store.loading).toBe(false)
    expect(store.error).toBeNull()
  })

  it('fetchUsers populates list and total', async () => {
    mockGet.mockResolvedValueOnce({
      code: 200,
      data: { items: [{ id: 1, username: 'alice' }], total: 1 },
    })
    await store.fetchUsers()
    expect(store.userList).toHaveLength(1)
    expect(store.total).toBe(1)
    expect(store.loading).toBe(false)
  })

  it('fetchUsers handles error', async () => {
    mockGet.mockRejectedValueOnce(new Error('Network error'))
    await store.fetchUsers()
    expect(store.error).toBeTruthy()
    expect(store.loading).toBe(false)
  })

  it('fetchUser loads single user', async () => {
    mockGet.mockResolvedValueOnce({ code: 200, data: { id: 1, username: 'bob' } })
    await store.fetchUser(1)
    expect(store.currentUser).toEqual({ id: 1, username: 'bob' })
  })

  it('createUser adds to list and increments total', async () => {
    mockPost.mockResolvedValueOnce({ code: 200, data: { id: 1, username: 'new' } })
    await store.createUser({ username: 'new' })
    expect(store.userList).toHaveLength(1)
    expect(store.total).toBe(1)
  })

  it('deleteUser removes from list', async () => {
    store.userList = [{ id: 1, username: 'a' }, { id: 2, username: 'b' }]
    store.total = 2
    mockDel.mockResolvedValueOnce({ code: 200 })
    await store.deleteUser(1)
    expect(store.userList).toHaveLength(1)
    expect(store.total).toBe(1)
  })

  it('logout clears auth', async () => {
    const { AuthStorage } = await import('@/utils/authStorage')
    await store.logout()
    expect(AuthStorage.clear).toHaveBeenCalled()
  })
})
