import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { usePolicyStore } from '@/stores/policy'

const mockGet = vi.fn()
const mockPost = vi.fn()
const mockPut = vi.fn()
const mockDel = vi.fn()

vi.mock('@/api/request', () => ({
  get: (...args: any[]) => mockGet(...args),
  post: (...args: any[]) => mockPost(...args),
  put: (...args: any[]) => mockPut(...args),
  del: (...args: any[]) => mockDel(...args),
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

describe('usePolicyStore', () => {
  let store: ReturnType<typeof usePolicyStore>
  beforeEach(() => {
    vi.clearAllMocks()
    setActivePinia(createPinia())
    store = usePolicyStore()
  })

  it('初始: policyList=[], current=null, total=0', () => {
    expect(store.policyList).toEqual([])
    expect(store.current).toBeNull()
    expect(store.total).toBe(0)
  })

  it('fetchPolicies 成功时填充 policyList + total', async () => {
    mockGet.mockResolvedValueOnce({
      code: 200,
      data: [{ id: 1, title: 'A' }, { id: 2, title: 'B' }],
      total: 2,
    })
    await store.fetchPolicies({ page: 1 })
    expect(mockGet).toHaveBeenCalledWith('/policies', { page: 1 })
    expect(store.policyList).toHaveLength(2)
    expect(store.total).toBe(2)
  })

  it('fetchPolicies 无 total 时用 data.length', async () => {
    mockGet.mockResolvedValueOnce({ code: 200, data: [{ id: 1 }] })
    await store.fetchPolicies()
    expect(store.total).toBe(1)
  })

  it('fetchPolicies 失败时静默', async () => {
    mockGet.mockRejectedValueOnce(new Error('boom'))
    await store.fetchPolicies()
    expect(store.policyList).toEqual([])
    expect(store.loading).toBe(false)
  })

  it('fetchPolicy 成功时设置 current', async () => {
    mockGet.mockResolvedValueOnce({ code: 200, data: { id: 1, title: 'X' } })
    await store.fetchPolicy(1)
    expect(mockGet).toHaveBeenCalledWith('/policies/1')
    expect(store.current).toEqual({ id: 1, title: 'X' })
  })

  it('createPolicy 成功时插入到头部 + total++', async () => {
    mockPost.mockResolvedValueOnce({ code: 200, data: { id: 99, title: 'New' } })
    await store.createPolicy({ title: 'New' })
    expect(store.policyList[0]).toEqual({ id: 99, title: 'New' })
    expect(store.total).toBe(1)
  })

  it('updatePolicy 成功时合并数据', async () => {
    store.policyList = [{ id: 1, title: 'Old', status: 'draft' }]
    store.total = 1
    mockPut.mockResolvedValueOnce({ code: 200 })
    await store.updatePolicy(1, { status: 'published' })
    expect(store.policyList[0].status).toBe('published')
    expect(store.policyList[0].title).toBe('Old')
  })

  it('deletePolicy 成功时移除 + total--', async () => {
    store.policyList = [{ id: 1 }, { id: 2 }]
    store.total = 2
    mockDel.mockResolvedValueOnce({ code: 200 })
    await store.deletePolicy(1)
    expect(store.policyList).toHaveLength(1)
    expect(store.total).toBe(1)
  })
})
