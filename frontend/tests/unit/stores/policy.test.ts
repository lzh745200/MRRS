import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

vi.mock('@/api/request', () => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  del: vi.fn(),
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

import { usePolicyStore } from '@/stores/policy'
import { get, post, put, del } from '@/api/request'

const mockGet = get as ReturnType<typeof vi.fn>
const mockPost = post as ReturnType<typeof vi.fn>
const mockPut = put as ReturnType<typeof vi.fn>
const mockDel = del as ReturnType<typeof vi.fn>

describe('usePolicyStore', () => {
  let store: ReturnType<typeof usePolicyStore>

  beforeEach(() => {
    setActivePinia(createPinia())
    store = usePolicyStore()
    vi.clearAllMocks()
  })

  it('initializes with defaults', () => {
    expect(store.policyList).toEqual([])
    expect(store.current).toBeNull()
    expect(store.loading).toBe(false)
    expect(store.total).toBe(0)
  })

  it('fetchPolicies populates list', async () => {
    mockGet.mockResolvedValueOnce({
      code: 200,
      data: [{ id: 1, title: 'Policy A' }],
      total: 1,
    })
    await store.fetchPolicies()
    expect(store.policyList).toHaveLength(1)
    expect(store.total).toBe(1)
  })

  it('fetchPolicies handles error gracefully', async () => {
    mockGet.mockRejectedValueOnce(new Error('Network error'))
    await store.fetchPolicies()
    expect(store.policyList).toEqual([])
    expect(store.loading).toBe(false)
  })

  it('fetchPolicy loads single policy', async () => {
    mockGet.mockResolvedValueOnce({ code: 200, data: { id: 1, title: 'Test' } })
    await store.fetchPolicy(1)
    expect(store.current).toEqual({ id: 1, title: 'Test' })
  })

  it('createPolicy adds to list', async () => {
    mockPost.mockResolvedValueOnce({
      code: 200,
      data: { id: 1, title: 'New Policy' },
    })
    await store.createPolicy({ title: 'New Policy' })
    expect(store.policyList).toHaveLength(1)
    expect(store.total).toBe(1)
  })

  it('updatePolicy modifies existing item', async () => {
    store.policyList = [{ id: 1, title: 'Old' }]
    mockPut.mockResolvedValueOnce({ code: 200 })
    await store.updatePolicy(1, { title: 'Updated' })
    expect(store.policyList[0].title).toBe('Updated')
  })

  it('deletePolicy removes item', async () => {
    store.policyList = [{ id: 1, title: 'To Delete' }, { id: 2, title: 'Keep' }]
    store.total = 2
    mockDel.mockResolvedValueOnce({ code: 200 })
    await store.deletePolicy(1)
    expect(store.policyList).toHaveLength(1)
    expect(store.total).toBe(1)
  })
})

describe('setFilters 合并', () => {
  it('合并传入过滤条件', () => {
    const store = usePolicyStore()
    store.setFilters({ status: 'active' })
    expect(store.filters.status).toBe('active')
    store.setFilters({ order_by: 'publish_date' })
    expect(store.filters.order_by).toBe('publish_date')
    expect(store.filters.status).toBe('active')
  })
})

describe('fetchPolicies 响应形态', () => {
  it('items 形态与 data 数组形态', async () => {
    const store = usePolicyStore()
    mockGet.mockResolvedValueOnce({ code: 200, data: { items: [{ id: 1 }], total: 1 } })
    await store.fetchPolicies({})
    expect(store.policyList.length).toBe(1)
    mockGet.mockResolvedValueOnce({ code: 200, data: [{ id: 2 }] })
    await store.fetchPolicies({})
    expect(store.policyList.length).toBe(1)
  })
})

describe('fetchPolicies 响应形态补充', () => {
  beforeEach(() => { vi.clearAllMocks() })
  it('信封 data.items → 赋值', async () => {
    ;(get as any).mockResolvedValue({ code: 200, data: { items: [{ id: 3 }], total: 1 } })
    const s = usePolicyStore()
    await s.fetchPolicies()
    expect(s.policyList).toEqual([{ id: 3 }])
  })
  it('data 为空对象 → 空列表', async () => {
    ;(get as any).mockResolvedValue({ code: 200, data: {} })
    const s = usePolicyStore()
    await s.fetchPolicies()
    expect(s.policyList).toEqual([])
  })
})
