import { describe, it, expect, vi, beforeEach } from 'vitest'

// search.ts 只从 '@/api/request' 导入 get（自动拆信封，resolve body 即可）
const { mockGet } = vi.hoisted(() => ({ mockGet: vi.fn().mockResolvedValue({}) }))

vi.mock('@/api/request', () => ({
  get: (...args: any[]) => mockGet(...args),
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

import { globalSearch, SEARCH_TYPE_LABELS, SEARCH_TYPE_ICONS } from '@/api/search'

describe('api/search', () => {
  beforeEach(() => vi.clearAllMocks())

  it('globalSearch 默认 limit=20', async () => {
    const body = {
      total: 1,
      items: [{ id: 1, type: 'village', title: 'X村', link: '/villages/1' }],
    }
    mockGet.mockResolvedValueOnce(body)
    const r = await globalSearch('X村')
    expect(mockGet).toHaveBeenCalledWith('/search', { q: 'X村', limit: 20 })
    expect(r).toBe(body)
  })

  it('globalSearch 自定义 limit', async () => {
    const body = { total: 0, items: [] }
    mockGet.mockResolvedValueOnce(body)
    const r = await globalSearch('政策', 50)
    expect(mockGet).toHaveBeenCalledWith('/search', { q: '政策', limit: 50 })
    expect(r).toBe(body)
  })

  it('SEARCH_TYPE_LABELS 覆盖全部 6 类', () => {
    expect(SEARCH_TYPE_LABELS).toEqual({
      village: '帮扶村',
      project: '项目',
      policy: '政策法规',
      school: '学校',
      fund: '经费',
      user: '用户',
    })
  })

  it('SEARCH_TYPE_ICONS 覆盖全部 6 类', () => {
    expect(Object.keys(SEARCH_TYPE_ICONS).sort()).toEqual(
      ['fund', 'policy', 'project', 'school', 'user', 'village'].sort()
    )
  })
})
