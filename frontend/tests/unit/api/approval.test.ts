import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockGet = vi.fn()
const mockPost = vi.fn()
const mockPut = vi.fn()
const mockDel = vi.fn()

vi.mock('@/utils/request', () => ({
  get: (...args: any[]) => mockGet(...args),
  post: (...args: any[]) => mockPost(...args),
  put: (...args: any[]) => mockPut(...args),
  del: (...args: any[]) => mockDel(...args),
}))

vi.mock('@/api/request', () => ({
  get: (...args: any[]) => mockGet(...args),
  post: (...args: any[]) => mockPost(...args),
  put: (...args: any[]) => mockPut(...args),
  del: (...args: any[]) => mockDel(...args),
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

import {
  createWorkflow,
  getWorkflows,
  getWorkflow,
  updateWorkflow,
  deleteWorkflow,
  submitApproval,
  approveTask,
  rejectTask,
  transferTask,
  withdrawTask,
  getAllTasks,
  getPendingTasks,
  batchApprove,
  getTaskDiff,
  getApprovalHistory,
  getOverview,
  remindTask,
  resubmitTask,
  autoApproveSingleTask,
  autoApproveAll,
  submitAndAutoApprove,
  formatApprovalStatus,
  formatApprovalAction,
  formatEntityType,
} from '@/api/approval'

describe('api/approval', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('workflows', () => {
    it('createWorkflow POST /approval/workflows', async () => {
      mockPost.mockResolvedValueOnce({ id: 1, name: 'W', level_count: 3 })
      const result = await createWorkflow({
        name: 'W',
        entity_type: 'project',
        nodes: [],
      })
      expect(mockPost).toHaveBeenCalledWith('/approval/workflows', {
        name: 'W',
        entity_type: 'project',
        nodes: [],
      })
      expect(result.level_count).toBe(3)
    })

    it('getWorkflows GET /approval/workflows 带 params', async () => {
      mockGet.mockResolvedValueOnce([])
      await getWorkflows({ entity_type: 'project', skip: 0, limit: 20 })
      expect(mockGet).toHaveBeenCalledWith('/approval/workflows', {
        entity_type: 'project', skip: 0, limit: 20,
      })
    })

    it('getWorkflows 无参时 params=undefined', async () => {
      mockGet.mockResolvedValueOnce([])
      await getWorkflows()
      expect(mockGet).toHaveBeenCalledWith('/approval/workflows', undefined)
    })

    it('getWorkflow GET /approval/workflows/{id}', async () => {
      mockGet.mockResolvedValueOnce({ id: 5, name: 'W' })
      await getWorkflow(5)
      expect(mockGet).toHaveBeenCalledWith('/approval/workflows/5')
    })

    it('updateWorkflow PUT /approval/workflows/{id}', async () => {
      mockPut.mockResolvedValueOnce({ id: 5 })
      await updateWorkflow(5, { is_active: false })
      expect(mockPut).toHaveBeenCalledWith('/approval/workflows/5', { is_active: false })
    })

    it('deleteWorkflow DELETE /approval/workflows/{id}', async () => {
      mockDel.mockResolvedValueOnce(undefined)
      await deleteWorkflow(5)
      expect(mockDel).toHaveBeenCalledWith('/approval/workflows/5')
    })
  })

  describe('tasks', () => {
    it('submitApproval POST /approval/submit', async () => {
      mockPost.mockResolvedValueOnce({ task_id: 1, status: 'pending', current_level: 1 })
      const result = await submitApproval({
        entity_type: 'project',
        entity_id: 100,
        change_data: { name: 'X' },
      })
      expect(mockPost).toHaveBeenCalledWith('/approval/submit', {
        entity_type: 'project',
        entity_id: 100,
        change_data: { name: 'X' },
      })
      expect(result.status).toBe('pending')
    })

    it('approveTask POST /approval/tasks/{id}/approve', async () => {
      mockPost.mockResolvedValueOnce({ task_id: 1, status: 'approved', current_level: 2 })
      await approveTask(1, 'looks good')
      expect(mockPost).toHaveBeenCalledWith('/approval/tasks/1/approve', { opinion: 'looks good' })
    })

    it('approveTask 无 opinion', async () => {
      mockPost.mockResolvedValueOnce({ task_id: 1, status: 'approved', current_level: 2 })
      await approveTask(1)
      expect(mockPost).toHaveBeenCalledWith('/approval/tasks/1/approve', { opinion: undefined })
    })

    it('rejectTask POST /approval/tasks/{id}/reject', async () => {
      mockPost.mockResolvedValueOnce({ task_id: 1, status: 'rejected' })
      await rejectTask(1, 'not good')
      expect(mockPost).toHaveBeenCalledWith('/approval/tasks/1/reject', { opinion: 'not good' })
    })

    it('transferTask POST /approval/tasks/{id}/transfer with reason', async () => {
      mockPost.mockResolvedValueOnce({ task_id: 1, current_approver_id: 99 })
      await transferTask(1, 99, 'out of office')
      expect(mockPost).toHaveBeenCalledWith('/approval/tasks/1/transfer', {
        transfer_to_id: 99,
        reason: 'out of office',
      })
    })

    it('withdrawTask POST /approval/tasks/{id}/withdraw', async () => {
      mockPost.mockResolvedValueOnce({ task_id: 1, status: 'withdrawn' })
      await withdrawTask(1)
      expect(mockPost).toHaveBeenCalledWith('/approval/tasks/1/withdraw', {})
    })

    it('getAllTasks 返回数组 (非数组时回退为空)', async () => {
      mockGet.mockResolvedValueOnce([{ id: 1 }])
      const result = await getAllTasks({ status: 'pending' })
      expect(result).toEqual([{ id: 1 }])
    })

    it('getAllTasks 响应非数组时返回 []', async () => {
      mockGet.mockResolvedValueOnce({ items: [] })
      const result = await getAllTasks()
      expect(result).toEqual([])
    })

    it('getPendingTasks GET /approval/tasks/pending', async () => {
      mockGet.mockResolvedValueOnce([])
      await getPendingTasks({ skip: 0 })
      expect(mockGet).toHaveBeenCalledWith('/approval/tasks/pending', { skip: 0 })
    })

    it('batchApprove POST /approval/tasks/batch with task_ids array', async () => {
      mockPost.mockResolvedValueOnce({ success: [1, 2], failed: [] })
      await batchApprove([1, 2, 3], 'OK')
      expect(mockPost).toHaveBeenCalledWith('/approval/tasks/batch', {
        task_ids: [1, 2, 3],
        opinion: 'OK',
      })
    })

    it('getTaskDiff GET /approval/tasks/{id}/diff', async () => {
      mockGet.mockResolvedValueOnce({ changes: [] })
      await getTaskDiff(5)
      expect(mockGet).toHaveBeenCalledWith('/approval/tasks/5/diff')
    })

    it('getApprovalHistory GET /approval/history', async () => {
      mockGet.mockResolvedValueOnce([{ id: 1 }])
      await getApprovalHistory({ entity_type: 'project' })
      expect(mockGet).toHaveBeenCalledWith('/approval/history', {
        entity_type: 'project',
      })
    })

    it('getApprovalHistory 响应非数组时返回 []', async () => {
      mockGet.mockResolvedValueOnce({ items: [] })
      const result = await getApprovalHistory()
      expect(mockGet).toHaveBeenCalledWith('/approval/history', undefined)
      expect(result).toEqual([])
    })

    it('getPendingTasks 响应非数组时返回 []', async () => {
      mockGet.mockResolvedValueOnce({ items: [] })
      const result = await getPendingTasks()
      expect(mockGet).toHaveBeenCalledWith('/approval/tasks/pending', undefined)
      expect(result).toEqual([])
    })

    it('getOverview GET /approval 返回概览', async () => {
      const body = { pending_count: 1, approved_count: 2, rejected_count: 3, total_count: 6 }
      mockGet.mockResolvedValueOnce(body)
      const result = await getOverview()
      expect(mockGet).toHaveBeenCalledWith('/approval')
      expect(result).toBe(body)
    })

    it('remindTask POST /approval/tasks/{id}/remind', async () => {
      mockPost.mockResolvedValueOnce({ message: '已发送' })
      const result = await remindTask(5)
      expect(mockPost).toHaveBeenCalledWith('/approval/tasks/5/remind', {})
      expect(result.message).toBe('已发送')
    })

    it('resubmitTask 带 data POST /approval/tasks/{id}/resubmit', async () => {
      mockPost.mockResolvedValueOnce({ task_id: 5, status: 'pending' })
      const result = await resubmitTask(5, { change_data: { name: 'X' } })
      expect(mockPost).toHaveBeenCalledWith('/approval/tasks/5/resubmit', {
        change_data: { name: 'X' },
      })
      expect(result.status).toBe('pending')
    })

    it('resubmitTask 无 data 时传空对象', async () => {
      mockPost.mockResolvedValueOnce({ task_id: 5, status: 'pending' })
      await resubmitTask(5)
      expect(mockPost).toHaveBeenCalledWith('/approval/tasks/5/resubmit', {})
    })
  })

  describe('auto-approve (单机版)', () => {
    it('autoApproveSingleTask POST /approval/tasks/{id}/auto-approve', async () => {
      mockPost.mockResolvedValueOnce({ task_id: 1, status: 'approved' })
      await autoApproveSingleTask(1, 'fast')
      expect(mockPost).toHaveBeenCalledWith('/approval/tasks/1/auto-approve', { opinion: 'fast' })
    })

    it('autoApproveAll POST /approval/tasks/auto-approve-all', async () => {
      mockPost.mockResolvedValueOnce({ success: [1, 2], failed: [3] })
      const result = await autoApproveAll()
      expect(mockPost).toHaveBeenCalledWith('/approval/tasks/auto-approve-all', { opinion: undefined })
      expect(result.success).toEqual([1, 2])
    })

    it('submitAndAutoApprove POST /approval/submit-auto', async () => {
      mockPost.mockResolvedValueOnce({ task_id: 1, status: 'approved' })
      await submitAndAutoApprove({
        entity_type: 'project',
        entity_id: 1,
        change_data: {},
      })
      expect(mockPost).toHaveBeenCalledWith('/approval/submit-auto', {
        entity_type: 'project',
        entity_id: 1,
        change_data: {},
      })
    })
  })

  describe('formatters', () => {
    it('formatApprovalStatus 已知状态', () => {
      expect(formatApprovalStatus('pending')).toEqual({ text: '待审批', type: 'warning' })
      expect(formatApprovalStatus('approved')).toEqual({ text: '已通过', type: 'success' })
      expect(formatApprovalStatus('rejected')).toEqual({ text: '已拒绝', type: 'danger' })
      expect(formatApprovalStatus('withdrawn')).toEqual({ text: '已撤回', type: 'info' })
    })

    it('formatApprovalStatus 未知状态回退', () => {
      expect(formatApprovalStatus('xyz')).toEqual({ text: 'xyz', type: 'info' })
    })

    it('formatApprovalAction 已知操作', () => {
      expect(formatApprovalAction('approve')).toBe('通过')
      expect(formatApprovalAction('reject')).toBe('拒绝')
      expect(formatApprovalAction('transfer')).toBe('转交')
    })

    it('formatApprovalAction 未知操作回退原值', () => {
      expect(formatApprovalAction('xyz')).toBe('xyz')
    })

    it('formatEntityType 已知类型', () => {
      expect(formatEntityType('supported_village')).toBe('帮扶村')
      expect(formatEntityType('project')).toBe('项目')
      expect(formatEntityType('fund')).toBe('经费')
      expect(formatEntityType('school')).toBe('学校')
    })

    it('formatEntityType 未知类型回退原值', () => {
      expect(formatEntityType('xyz')).toBe('xyz')
    })
  })
})

describe('列表响应多形态解包', () => {
  it('getAllTasks/getPendingTasks 兼容对象形态(items/data/空)', async () => {
    const { getAllTasks, getPendingTasks } = await import('@/api/approval')
    mockGet.mockResolvedValueOnce({ items: [{ id: 1 }] })
    expect(await getAllTasks()).toEqual([{ id: 1 }])
    mockGet.mockResolvedValueOnce({ data: [{ id: 2 }] })
    expect(await getAllTasks()).toEqual([{ id: 2 }])
    mockGet.mockResolvedValueOnce({})
    expect(await getAllTasks()).toEqual([])
    mockGet.mockResolvedValueOnce({ items: [{ id: 3 }] })
    expect(await getPendingTasks()).toEqual([{ id: 3 }])
  })
})

describe('响应形态补充', () => {
  beforeEach(() => { vi.clearAllMocks() })
  it('getPendingTasks 收到 {data:[...]} 信封 → 解包', async () => {
    ;(mockGet as any).mockResolvedValue({ data: [{ task_id: 9 }] })
    const r = await getPendingTasks()
    expect(r).toEqual([{ task_id: 9 }])
  })
  it('getPendingTasks 收到空对象 → 空数组', async () => {
    ;(mockGet as any).mockResolvedValue({})
    const r = await getPendingTasks()
    expect(r).toEqual([])
  })
  it('getApprovalHistory 收到 {data:[...]} 信封 → 解包', async () => {
    ;(mockGet as any).mockResolvedValue({ data: [{ task_id: 7 }] })
    const r = await getApprovalHistory({ entity_type: 'policy' })
    expect(r).toEqual([{ task_id: 7 }])
  })
  it('getApprovalHistory 收到空对象 → 空数组', async () => {
    ;(mockGet as any).mockResolvedValue({})
    const r = await getApprovalHistory()
    expect(r).toEqual([])
  })
})
