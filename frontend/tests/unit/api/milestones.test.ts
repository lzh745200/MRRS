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
