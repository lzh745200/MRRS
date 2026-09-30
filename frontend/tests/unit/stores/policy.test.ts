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

  it('deletePolicy 删除非当前页记录时 total 不变，且不为负', async () => {
    store.policyList = [{ id: 1, title: 'A' }]
    store.total = 20
    mockDel.mockResolvedValueOnce({ code: 200 })
    await store.deletePolicy(999)
    expect(store.policyList).toHaveLength(1)
    expect(store.total).toBe(20)

    mockDel.mockResolvedValueOnce({ code: 200 })
    store.total = 0
    await store.deletePolicy(1)
    expect(store.total).toBe(0)
  })

  // 原实现：读操作 catch { /* silent */ }（失败无痕迹），写操作无 try/catch
  // （未处理拒绝且 store 不产出任何提示）。以下用例锁定"记录错误 + 上报"的新语义。
  describe('错误可观测性（不再静默吞错）', () => {
    it('fetchPolicies 失败时写入 error 且不抛出', async () => {
      mockGet.mockRejectedValueOnce(new Error('Network error'))
      await expect(store.fetchPolicies()).resolves.toBeUndefined()
      expect(store.error).toBe('Network error')
      expect(store.loading).toBe(false)
    })

    it('fetchPolicies 优先采用请求层净化的 userMessage', async () => {
      mockGet.mockRejectedValueOnce(Object.assign(new Error('raw'), { userMessage: '网络连接失败' }))
      await store.fetchPolicies()
      expect(store.error).toBe('网络连接失败')
    })

    it('fetchPolicy 失败时写入 error 且不抛出', async () => {
      mockGet.mockRejectedValueOnce(new Error('boom'))
      await expect(store.fetchPolicy(9)).resolves.toBeUndefined()
      expect(store.error).toBe('boom')
    })

    it('createPolicy 失败时写入 error 并向上抛出（调用方仍能感知失败）', async () => {
      mockPost.mockRejectedValueOnce(new Error('create failed'))
      await expect(store.createPolicy({ title: 'x' })).rejects.toThrow('create failed')
      expect(store.error).toBe('create failed')
    })

    it('updatePolicy 失败时写入 error 并向上抛出', async () => {
      mockPut.mockRejectedValueOnce(new Error('update failed'))
      await expect(store.updatePolicy(1, { title: 'x' })).rejects.toThrow('update failed')
      expect(store.error).toBe('update failed')
    })

    it('deletePolicy 失败时写入 error 并向上抛出', async () => {
      mockDel.mockRejectedValueOnce(new Error('delete failed'))
      await expect(store.deletePolicy(1)).rejects.toThrow('delete failed')
      expect(store.error).toBe('delete failed')
    })

    it('成功调用会清空上一次的 error', async () => {
      store.error = '旧的错误'
      mockGet.mockResolvedValueOnce({ code: 200, data: [] })
      await store.fetchPolicies()
      expect(store.error).toBeNull()
    })
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
