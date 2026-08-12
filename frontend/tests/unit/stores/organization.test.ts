import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

vi.mock('@/api/request', () => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  del: vi.fn(),
  apiRequest: vi.fn(),
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

import { useOrganizationStore } from '@/stores/organization'
import { get, post, put, del } from '@/api/request'

const mockGet = get as ReturnType<typeof vi.fn>
const mockPost = post as ReturnType<typeof vi.fn>
const mockPut = put as ReturnType<typeof vi.fn>
const mockDel = del as ReturnType<typeof vi.fn>

describe('useOrganizationStore', () => {
  let store: ReturnType<typeof useOrganizationStore>

  beforeEach(() => {
    setActivePinia(createPinia())
    store = useOrganizationStore()
    vi.clearAllMocks()
  })

  it('initializes with defaults', () => {
    expect(store.orgs).toEqual([])
    expect(store.current).toBeNull()
    expect(store.tree).toEqual([])
    expect(store.loading).toBe(false)
  })

  it('fetchOrganizations populates orgs', async () => {
    mockGet.mockResolvedValueOnce({
      code: 200,
      data: [{ id: 1, name: 'Org A' }],
    })
    await store.fetchOrganizations()
    expect(store.orgs).toHaveLength(1)
    expect(store.loading).toBe(false)
  })

  it('fetchOrganization loads single org', async () => {
    mockGet.mockResolvedValueOnce({ code: 200, data: { id: 1, name: 'Org A' } })
    await store.fetchOrganization(1)
    expect(store.current).toEqual({ id: 1, name: 'Org A' })
  })

  it('fetchTree populates tree', async () => {
    mockGet.mockResolvedValueOnce({
      code: 200,
      data: [{ id: 1, name: 'Root', children: [] }],
    })
    await store.fetchTree()
    expect(store.tree).toHaveLength(1)
  })

  it('fetchTree 后端直接返回数组（裸格式兼容）', async () => {
    mockGet.mockResolvedValueOnce([{ id: 2, name: 'Root2', children: [] }])
    await store.fetchTree()
    expect(store.tree).toHaveLength(1)
    expect(store.tree[0].name).toBe('Root2')
  })

  it('createOrganization adds to list', async () => {
    mockPost.mockResolvedValueOnce({
      code: 200,
      data: { id: 1, name: 'New Org' },
    })
    await store.createOrganization({ name: 'New Org' })
    expect(store.orgs).toHaveLength(1)
  })

  it('updateOrganization modifies item', async () => {
    store.orgs = [{ id: 1, name: 'Old' }]
    mockPut.mockResolvedValueOnce({ code: 200 })
    await store.updateOrganization(1, { name: 'Updated' })
    expect(store.orgs[0].name).toBe('Updated')
  })

  it('deleteOrganization removes item', async () => {
    store.orgs = [{ id: 1 }, { id: 2 }]
    mockDel.mockResolvedValueOnce({ code: 200 })
    await store.deleteOrganization(1)
    expect(store.orgs).toHaveLength(1)
  })

  it('fetchOrganizations handles errors', async () => {
    mockGet.mockRejectedValueOnce(new Error('fail'))
    await store.fetchOrganizations()
    expect(store.orgs).toEqual([])
    expect(store.loading).toBe(false)
  })

  it('fetchOrganizations 非 200 code 时不清空 orgs', async () => {
    store.orgs = [{ id: 1, name: 'keep' }]
    mockGet.mockResolvedValueOnce({ code: 400, data: null })
    await store.fetchOrganizations()
    expect(store.orgs).toEqual([{ id: 1, name: 'keep' }])
    expect(store.loading).toBe(false)
  })

  it('fetchOrganizations data 为对象时回退到 res.items', async () => {
    mockGet.mockResolvedValueOnce({
      code: 200,
      data: { count: 2 },
      items: [{ id: 10, name: 'FromItems' }],
    })
    await store.fetchOrganizations()
    expect(store.orgs).toEqual([{ id: 10, name: 'FromItems' }])
  })

  it('fetchOrganizations 无 items 时回退为空数组', async () => {
    store.orgs = [{ id: 1 }]
    mockGet.mockResolvedValueOnce({ code: 200, data: { count: 2 } })
    await store.fetchOrganizations()
    expect(store.orgs).toEqual([])
  })

  it('fetchOrganization 非 200 code 时不更新 current', async () => {
    store.current = { id: 1 }
    mockGet.mockResolvedValueOnce({ code: 404, data: null })
    await store.fetchOrganization(99)
    expect(store.current).toEqual({ id: 1 })
  })

  it('fetchOrganization 异常时静默并复位 loading', async () => {
    mockGet.mockRejectedValueOnce(new Error('boom'))
    await store.fetchOrganization(1)
    expect(store.loading).toBe(false)
  })

  it('fetchTree 非 200 code 时不更新 tree', async () => {
    store.tree = [{ id: 1 }]
    mockGet.mockResolvedValueOnce({ code: 500, data: null })
    await store.fetchTree()
    expect(store.tree).toEqual([{ id: 1 }])
  })

  it('fetchTree 异常时静默', async () => {
    mockGet.mockRejectedValueOnce(new Error('boom'))
    await store.fetchTree()
    expect(store.tree).toEqual([])
  })

  it('createOrganization 非 200 code 时不入列表', async () => {
    mockPost.mockResolvedValueOnce({ code: 400 })
    const res = await store.createOrganization({ name: 'X' })
    expect(store.orgs).toEqual([])
    expect(res.code).toBe(400)
  })

  it('createOrganization 成功后清空 tree', async () => {
    store.tree = [{ id: 1 }]
    mockPost.mockResolvedValueOnce({ code: 200, data: { id: 2, name: 'New' } })
    await store.createOrganization({ name: 'New' })
    expect(store.tree).toEqual([])
    expect(store.orgs).toHaveLength(1)
  })

  it('updateOrganization 非 200 code 时不修改', async () => {
    store.orgs = [{ id: 1, name: 'Old' }]
    mockPut.mockResolvedValueOnce({ code: 500 })
    await store.updateOrganization(1, { name: 'New' })
    expect(store.orgs[0].name).toBe('Old')
  })

  it('updateOrganization id 不存在时跳过列表更新但清空 tree', async () => {
    store.orgs = [{ id: 1 }]
    mockPut.mockResolvedValueOnce({ code: 200 })
    await store.updateOrganization(999, { name: 'Ghost' })
    expect(store.orgs).toHaveLength(1)
    expect(store.tree).toEqual([])
  })

  it('deleteOrganization 非 200 code 时不移除', async () => {
    store.orgs = [{ id: 1 }]
    mockDel.mockResolvedValueOnce({ code: 403 })
    await store.deleteOrganization(1)
    expect(store.orgs).toHaveLength(1)
  })

  it('fetchMyOrganization 成功时设置 current', async () => {
    mockGet.mockResolvedValueOnce({ code: 200, data: { id: 7, name: 'My Org' } })
    await store.fetchMyOrganization()
    expect(store.current).toEqual({ id: 7, name: 'My Org' })
  })

  it('fetchMyOrganization 非 200 code 时忽略', async () => {
    store.current = null
    mockGet.mockResolvedValueOnce({ code: 404 })
    await store.fetchMyOrganization()
    expect(store.current).toBeNull()
  })

  it('fetchMyOrganization 异常时静默', async () => {
    mockGet.mockRejectedValueOnce(new Error('not configured'))
    await store.fetchMyOrganization()
    expect(store.current).toBeNull()
  })

  it('fetchSubordinateOrganizations 成功时取 res.data', async () => {
    const { apiRequest } = await import('@/api/request')
    const mockApiRequest = apiRequest as ReturnType<typeof vi.fn>
    mockApiRequest.mockResolvedValueOnce({ data: [{ id: 1, name: 'Sub' }] })
    await store.fetchSubordinateOrganizations()
    expect(store.subordinateOrganizations).toEqual([{ id: 1, name: 'Sub' }])
    expect(mockApiRequest).toHaveBeenCalledWith({
      method: 'GET',
      url: '/organizations/subordinates',
      timeout: 10000,
    })
  })

  it('fetchSubordinateOrganizations 后端直接返回数组（裸格式兼容）', async () => {
    const { apiRequest } = await import('@/api/request')
    const mockApiRequest = apiRequest as ReturnType<typeof vi.fn>
    mockApiRequest.mockResolvedValueOnce([{ id: 9, name: 'SubArr' }])
    await store.fetchSubordinateOrganizations()
    expect(store.subordinateOrganizations).toEqual([{ id: 9, name: 'SubArr' }])
  })

  it('fetchSubordinateOrganizations 成功时回退到 res.items', async () => {
    const { apiRequest } = await import('@/api/request')
    const mockApiRequest = apiRequest as ReturnType<typeof vi.fn>
    mockApiRequest.mockResolvedValueOnce({ items: [{ id: 2, name: 'Item' }] })
    await store.fetchSubordinateOrganizations()
    expect(store.subordinateOrganizations).toEqual([{ id: 2, name: 'Item' }])
  })

  it('fetchSubordinateOrganizations 无 data/items 时置空', async () => {
    const { apiRequest } = await import('@/api/request')
    const mockApiRequest = apiRequest as ReturnType<typeof vi.fn>
    mockApiRequest.mockResolvedValueOnce({ ok: true })
    await store.fetchSubordinateOrganizations()
    expect(store.subordinateOrganizations).toEqual([])
  })

  it('fetchSubordinateOrganizations 异常时置空', async () => {
    const { apiRequest } = await import('@/api/request')
    const mockApiRequest = apiRequest as ReturnType<typeof vi.fn>
    mockApiRequest.mockRejectedValueOnce(new Error('boom'))
    await store.fetchSubordinateOrganizations()
    expect(store.subordinateOrganizations).toEqual([])
  })
})
