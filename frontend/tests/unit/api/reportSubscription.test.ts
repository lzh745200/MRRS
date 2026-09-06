/**
 * 报表订阅 API 客户端测试（工单 003）
 * 契约：list=GET ok_list 信封；create=POST 裸对象；update=PUT；
 * delete=DELETE；toggle/generate-now=POST。逐一断言 URL 与参数。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'

const { mockGet, mockPost, mockPut, mockDel } = vi.hoisted(() => ({
  mockGet: vi.fn(),
  mockPost: vi.fn(),
  mockPut: vi.fn(),
  mockDel: vi.fn(),
}))

vi.mock('@/api/request', () => ({
  get: mockGet,
  post: mockPost,
  put: mockPut,
  del: mockDel,
  apiRequest: vi.fn(),
  downloadBlob: vi.fn(),
}))

import {
  listSubscriptions,
  createSubscription,
  updateSubscription,
  deleteSubscription,
  toggleSubscription,
  generateSubscriptionNow,
} from '@/api/reportSubscription'

describe('reportSubscription API 客户端', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGet.mockResolvedValue({ items: [], total: 0 })
    mockPost.mockResolvedValue({})
    mockPut.mockResolvedValue({})
    mockDel.mockResolvedValue({})
  })

  it('listSubscriptions → GET /reports/subscriptions 平铺参数', async () => {
    await listSubscriptions({ page: 2, page_size: 10, is_active: true })
    expect(mockGet).toHaveBeenCalledWith('/reports/subscriptions', {
      page: 2,
      page_size: 10,
      is_active: true,
    })
  })

  it('listSubscriptions 无参数', async () => {
    await listSubscriptions()
    expect(mockGet).toHaveBeenCalledWith('/reports/subscriptions', undefined)
  })

  it('createSubscription → POST /reports/subscriptions', async () => {
    const payload = {
      name: '每月汇总',
      report_type: 'comprehensive',
      format: 'xlsx',
      frequency: 'monthly' as const,
      send_day: 15,
      send_time: '08:00',
    }
    await createSubscription(payload)
    expect(mockPost).toHaveBeenCalledWith('/reports/subscriptions', payload)
  })

  it('updateSubscription → PUT /reports/subscriptions/:id', async () => {
    await updateSubscription(7, { name: '改名', is_active: false })
    expect(mockPut).toHaveBeenCalledWith('/reports/subscriptions/7', {
      name: '改名',
      is_active: false,
    })
  })

  it('deleteSubscription → DELETE /reports/subscriptions/:id', async () => {
    await deleteSubscription(9)
    expect(mockDel).toHaveBeenCalledWith('/reports/subscriptions/9')
  })

  it('toggleSubscription → POST .../toggle', async () => {
    await toggleSubscription(3)
    expect(mockPost).toHaveBeenCalledWith('/reports/subscriptions/3/toggle', {})
  })

  it('generateSubscriptionNow → POST .../generate-now', async () => {
    await generateSubscriptionNow(5)
    expect(mockPost).toHaveBeenCalledWith('/reports/subscriptions/5/generate-now', {})
  })
})
