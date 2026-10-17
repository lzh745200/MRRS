import { describe, it, expect, vi, beforeEach } from 'vitest'

const { mockGet, mockPost } = vi.hoisted(() => ({
  mockGet: vi.fn(),
  mockPost: vi.fn(),
}))

vi.mock('@/api/request', () => ({
  get: mockGet,
  post: mockPost,
  getCsrfToken: vi.fn(() => Promise.resolve('test-csrf')),
}))

import {
  getReminders,
  triggerReminderScan,
  handleReminder,
  ignoreReminder,
  snoozeReminder,
  reopenReminder,
} from '@/api/reminders'

describe('api/reminders', () => {
  beforeEach(() => vi.clearAllMocks())

  it('getReminders → GET /reminders', async () => {
    const body = {
      items: [
        {
          id: 1,
          type: 'approval_timeout',
          title: '审批超时',
          content: 'x',
          created_at: '2026-01-01T00:00:00',
          is_read: false,
        },
      ],
      total: 1,
      unread: 1,
    }
    mockGet.mockResolvedValueOnce(body)
    const result = await getReminders()
    expect(mockGet).toHaveBeenCalledWith('/reminders')
    expect(result).toBe(body)
  })

  it('getReminders(includeIgnored) → 带 include_ignored 参数', async () => {
    mockGet.mockResolvedValueOnce({ items: [], total: 0, unread: 0 })
    await getReminders(true)
    expect(mockGet).toHaveBeenCalledWith('/reminders', { include_ignored: true })
  })

  it('triggerReminderScan → POST /reminders/scan', async () => {
    const body = { created: 3 }
    mockPost.mockResolvedValueOnce(body)
    const result = await triggerReminderScan()
    expect(mockPost).toHaveBeenCalledWith('/reminders/scan')
    expect(result).toBe(body)
  })

  it('handleReminder → POST /reminders/{id}/handle（含说明）', async () => {
    const body = { message_id: 5, state: 'handled' }
    mockPost.mockResolvedValueOnce(body)
    const result = await handleReminder(5, '已核实')
    expect(mockPost).toHaveBeenCalledWith('/reminders/5/handle', { note: '已核实' })
    expect(result).toBe(body)
  })

  it('handleReminder → 缺省 note 为空串', async () => {
    mockPost.mockResolvedValueOnce({ message_id: 5, state: 'handled' })
    await handleReminder(5)
    expect(mockPost).toHaveBeenCalledWith('/reminders/5/handle', { note: '' })
  })

  it('ignoreReminder → POST /reminders/{id}/ignore（note 承载原因）', async () => {
    mockPost.mockResolvedValueOnce({ message_id: 5, state: 'ignored' })
    await ignoreReminder(5, '重复提醒')
    expect(mockPost).toHaveBeenCalledWith('/reminders/5/ignore', { note: '重复提醒' })
  })

  it('ignoreReminder → 缺省原因为空串', async () => {
    mockPost.mockResolvedValueOnce({ message_id: 5, state: 'ignored' })
    await ignoreReminder(5)
    expect(mockPost).toHaveBeenCalledWith('/reminders/5/ignore', { note: '' })
  })

  it('snoozeReminder → POST /reminders/{id}/snooze（指定/缺省天数）', async () => {
    mockPost.mockResolvedValueOnce({ message_id: 5, state: 'open' })
    await snoozeReminder(5, 3)
    expect(mockPost).toHaveBeenCalledWith('/reminders/5/snooze', { days: 3 })

    mockPost.mockResolvedValueOnce({ message_id: 5, state: 'open' })
    await snoozeReminder(5)
    expect(mockPost).toHaveBeenLastCalledWith('/reminders/5/snooze', { days: 7 })
  })

  it('reopenReminder → POST /reminders/{id}/reopen', async () => {
    mockPost.mockResolvedValueOnce({ message_id: 5, state: 'open' })
    await reopenReminder(5)
    expect(mockPost).toHaveBeenCalledWith('/reminders/5/reopen', { note: '' })
  })

  it('reminder 项支持缺失 created_at', async () => {
    mockGet.mockResolvedValueOnce({
      items: [{ id: 2, type: 'budget_warning', title: '预算预警', content: 'y', is_read: true }],
      total: 1,
      unread: 0,
    })
    const result = await getReminders()
    expect(result.items[0].created_at).toBeUndefined()
    expect(result.unread).toBe(0)
  })
})
