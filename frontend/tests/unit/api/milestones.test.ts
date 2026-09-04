import { describe, it, expect, vi, beforeEach } from 'vitest'

const { mockGet, mockPost, mockPut, mockDel } = vi.hoisted(() => ({
  mockGet: vi.fn(),
  mockPost: vi.fn().mockResolvedValue({ data: {} }),
  mockPut: vi.fn().mockResolvedValue({ data: {} }),
  mockDel: vi.fn().mockResolvedValue({ data: {} }),
}))

vi.mock('@/api/request', () => ({
  get: (...args: unknown[]) => mockGet(...args),
  post: (...args: unknown[]) => mockPost(...args),
  put: (...args: unknown[]) => mockPut(...args),
  del: (...args: unknown[]) => mockDel(...args),
}))

import {
  listMilestones,
  createMilestone,
  updateMilestone,
  deleteMilestone,
  milestoneProgress,
} from '@/api/milestones'

describe('api/milestones', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGet.mockResolvedValue({ data: {} })
  })

  it('listMilestones GET /projects/{id}/milestones', async () => {
    await listMilestones(5)
    expect(mockGet).toHaveBeenCalledWith('/projects/5/milestones')
  })

  it('createMilestone POST', async () => {
    await createMilestone(5, { name: '开工' })
    expect(mockPost).toHaveBeenCalledWith('/projects/5/milestones', { name: '开工' })
  })

  it('updateMilestone PUT 子路径', async () => {
    await updateMilestone(5, 9, { status: 'completed' })
    expect(mockPut).toHaveBeenCalledWith('/projects/5/milestones/9', { status: 'completed' })
  })

  it('deleteMilestone DELETE 子路径', async () => {
    await deleteMilestone(5, 9)
    expect(mockDel).toHaveBeenCalledWith('/projects/5/milestones/9')
  })

  it('milestoneProgress 数组：完成比例四舍五入', async () => {
    mockGet.mockResolvedValue([
      { status: 'completed' },
      { status: 'completed' },
      { status: 'pending' },
    ] as any)
    const r = await milestoneProgress(5)
    expect(r).toEqual({ total: 3, completed: 2, progress_percent: 67 })
  })

  it('milestoneProgress 信封 items 形态', async () => {
    mockGet.mockResolvedValue({ items: [{ status: 'completed' }] } as any)
    const r = await milestoneProgress(5)
    expect(r).toEqual({ total: 1, completed: 1, progress_percent: 100 })
  })

  it('milestoneProgress 空列表 → 0%', async () => {
    mockGet.mockResolvedValue([] as any)
    const r = await milestoneProgress(5)
    expect(r).toEqual({ total: 0, completed: 0, progress_percent: 0 })
  })
})

/**
 * milestoneProgress 的 `(items as any)?.items ?? []` 兜底链。
 * 上方用例只走了数组、`{items:[...]}`、空数组三种形态；
 * 可选链短路侧与 `?? []` 侧（非数组且无 items 键）尚未触达。
 * 这些形态在真实后端上确实会出现：项目无里程碑时部分接口返回 `{}`/`null`。
 */
describe('api/milestones milestoneProgress 非数组入参兜底', () => {
  beforeEach(() => vi.clearAllMocks())

  it('items 为 null → 可选链短路 + `?? []` → 0%', async () => {
    mockGet.mockResolvedValue(null as any)
    expect(await milestoneProgress(5)).toEqual({
      total: 0,
      completed: 0,
      progress_percent: 0,
    })
  })

  it('items 为 undefined → 同样回落 0%', async () => {
    mockGet.mockResolvedValue(undefined as any)
    expect(await milestoneProgress(7)).toEqual({
      total: 0,
      completed: 0,
      progress_percent: 0,
    })
  })

  it('items 为不含 items 键的对象 → `?? []` 侧生效', async () => {
    // 后端异常负载（如 {detail: '...'}）不能让前端抛 TypeError
    mockGet.mockResolvedValue({ detail: 'Not Found' } as any)
    expect(await milestoneProgress(5)).toEqual({
      total: 0,
      completed: 0,
      progress_percent: 0,
    })
  })

  it('items 为 { items: null } → 嵌套 nullish 仍回落空数组', async () => {
    mockGet.mockResolvedValue({ items: null } as any)
    expect(await milestoneProgress(5)).toEqual({
      total: 0,
      completed: 0,
      progress_percent: 0,
    })
  })

  it('items 为 { items: [...] } 但无 completed → 0%（不误入四舍五入分支）', async () => {
    mockGet.mockResolvedValue({ items: [{ status: 'pending' }, { status: 'overdue' }] } as any)
    expect(await milestoneProgress(5)).toEqual({
      total: 2,
      completed: 0,
      progress_percent: 0,
    })
  })

  it('四舍五入边界：1/8 = 12.5% → 13；1/4 = 25% → 25', async () => {
    mockGet.mockResolvedValue(
      Array.from({ length: 8 }, (_, i) => ({ status: i === 0 ? 'completed' : 'pending' })) as any
    )
    expect(await milestoneProgress(5)).toEqual({
      total: 8,
      completed: 1,
      progress_percent: 13,
    })

    mockGet.mockResolvedValue(
      Array.from({ length: 4 }, (_, i) => ({ status: i === 0 ? 'completed' : 'pending' })) as any
    )
    expect(await milestoneProgress(5)).toEqual({
      total: 4,
      completed: 1,
      progress_percent: 25,
    })
  })
})
