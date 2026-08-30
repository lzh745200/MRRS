import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockGet = vi.fn()
const mockPost = vi.fn()
const mockPut = vi.fn()
const mockDel = vi.fn()
const mockApiRequest = vi.fn()

vi.mock('@/api/request', () => ({
  default: {
    get: (...args: any[]) => mockGet(...args),
    post: (...args: any[]) => mockPost(...args),
    put: (...args: any[]) => mockPut(...args),
    delete: (...args: any[]) => mockDel(...args),
  },
  get: (...args: any[]) => mockGet(...args),
  post: (...args: any[]) => mockPost(...args),
  put: (...args: any[]) => mockPut(...args),
  del: (...args: any[]) => mockDel(...args),
  apiRequest: (...args: any[]) => mockApiRequest(...args),
  getCsrfToken: vi.fn(() => Promise.resolve('test-csrf')),
}))

import {
  getMessages,
  getUnreadCount,
  markAsRead,
  markAllAsRead,
  deleteMessages,
  getMessage,
  getStats,
  getRecentActivities,
  getNotificationPreferences,
  updateNotificationPreferences,
  formatMessageType,
  formatRelativeTime,
} from '@/api/message'

describe('api/message', () => {
  beforeEach(() => vi.clearAllMocks())

  it('getMessages GET /messages', async () => {
    mockGet.mockResolvedValueOnce({ items: [], total: 0, page: 1, page_size: 20, unread_count: 0 })
    await getMessages({ page: 1 })
    expect(mockGet).toHaveBeenCalledWith('/messages', { page: 1 })
  })

  it('getUnreadCount GET /messages/unread-count', async () => {
    mockGet.mockResolvedValueOnce({ count: 5 })
    const r = await getUnreadCount()
    expect(mockGet).toHaveBeenCalledWith('/messages/unread-count')
    expect(r).toBe(5)
  })

  it('getUnreadCount 后端 total 字段（无 count）', async () => {
    mockGet.mockResolvedValueOnce({ total: 3, by_type: { system: 3 } })
    const r = await getUnreadCount()
    expect(r).toBe(3)
  })

  it('getUnreadCount 无 total/count → 0 兜底', async () => {
    mockGet.mockResolvedValueOnce({ by_type: {} })
    const r = await getUnreadCount()
    expect(r).toBe(0)
  })

  it('markAsRead POST with message_ids', async () => {
    mockPost.mockResolvedValueOnce({ count: 3 })
    const r = await markAsRead([1, 2, 3])
    expect(mockPost).toHaveBeenCalledWith('/messages/mark-read', { message_ids: [1, 2, 3] })
    expect(r).toBe(3)
  })

  it('markAllAsRead POST', async () => {
    mockPost.mockResolvedValueOnce({ count: 7 })
    const r = await markAllAsRead()
    expect(mockPost).toHaveBeenCalledWith('/messages/mark-all-read', {})
    expect(r).toBe(7)
  })

  it('deleteMessages DELETE with apiRequest', async () => {
    mockApiRequest.mockResolvedValueOnce({ count: 2 })
    const r = await deleteMessages([1, 2])
    expect(mockApiRequest).toHaveBeenCalledWith({
      method: 'DELETE',
      url: '/messages',
      data: { message_ids: [1, 2] },
    })
    expect(r).toBe(2)
  })

  it('getNotificationPreferences GET', async () => {
    mockGet.mockResolvedValueOnce({ email_approval: true })
    await getNotificationPreferences()
    expect(mockGet).toHaveBeenCalledWith('/notifications/preferences')
  })

  it('updateNotificationPreferences PUT', async () => {
    mockPut.mockResolvedValueOnce({ email_approval: false })
    await updateNotificationPreferences({ email_approval: false })
    expect(mockPut).toHaveBeenCalledWith('/notifications/preferences', { email_approval: false })
  })

  it('getMessage GET /messages/{id} 透传返回值', async () => {
    const body = { id: 9, title: 't' }
    mockGet.mockResolvedValueOnce(body)
    const r = await getMessage(9)
    expect(mockGet).toHaveBeenCalledWith('/messages/9')
    expect(r).toBe(body)
  })

  it('getStats GET /messages/stats/summary', async () => {
    const body = { total: 10, unread: 2, read: 8, by_type: { system: 10 } }
    mockGet.mockResolvedValueOnce(body)
    const r = await getStats()
    expect(mockGet).toHaveBeenCalledWith('/messages/stats/summary')
    expect(r).toBe(body)
  })

  it('getRecentActivities GET 数组透传', async () => {
    const body = [{ id: 1 }, { id: 2 }]
    mockGet.mockResolvedValueOnce(body)
    const r = await getRecentActivities({ limit: 5 })
    expect(mockGet).toHaveBeenCalledWith('/messages/recent-activities', { limit: 5 })
    expect(r).toBe(body)
  })

  it('getRecentActivities 非数组回退 []', async () => {
    mockGet.mockResolvedValueOnce({ items: [] })
    const r = await getRecentActivities()
    expect(mockGet).toHaveBeenCalledWith('/messages/recent-activities', undefined)
    expect(r).toEqual([])
  })

  it('formatMessageType system -> 系统通知 / info', () => {
    expect(formatMessageType('system')).toEqual({ text: '系统通知', type: 'info' })
  })
  it('formatMessageType approval -> 审批通知 / warning', () => {
    expect(formatMessageType('approval')).toEqual({ text: '审批通知', type: 'warning' })
  })
  it('formatMessageType task -> 任务提醒 / primary', () => {
    expect(formatMessageType('task')).toEqual({ text: '任务提醒', type: 'primary' })
  })
  it('formatMessageType 未知类型回退', () => {
    expect(formatMessageType('unknown' as any)).toEqual({ text: 'unknown', type: 'info' })
  })

  it('formatRelativeTime 刚刚 (< 1 min)', () => {
    const d = new Date(Date.now() - 30_000).toISOString()
    expect(formatRelativeTime(d)).toBe('刚刚')
  })
  it('formatRelativeTime 分钟级', () => {
    const d = new Date(Date.now() - 5 * 60_000).toISOString()
    expect(formatRelativeTime(d)).toBe('5分钟前')
  })
  it('formatRelativeTime 小时级', () => {
    const d = new Date(Date.now() - 3 * 3_600_000).toISOString()
    expect(formatRelativeTime(d)).toBe('3小时前')
  })
  it('formatRelativeTime 天级', () => {
    const d = new Date(Date.now() - 2 * 86_400_000).toISOString()
    expect(formatRelativeTime(d)).toBe('2天前')
  })
  it('formatRelativeTime 超过 7 天走 zh-CN 日期', () => {
    const d = new Date(Date.now() - 30 * 86_400_000).toISOString()
    expect(formatRelativeTime(d)).toMatch(/\d/)
  })
})
