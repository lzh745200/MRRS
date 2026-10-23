/**
 * api/selfCheck.ts 测试：URL / data 解包两侧。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'

const { mockGet } = vi.hoisted(() => ({ mockGet: vi.fn() }))

vi.mock('@/api/request', () => ({ get: mockGet }))

import { getSelfCheck } from '@/api/selfCheck'

describe('api/selfCheck', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('GET /system/self-check，优先取 data', async () => {
    mockGet.mockResolvedValue({ data: { status: 'ok', checks: [] } })
    const res = await getSelfCheck()
    expect(mockGet).toHaveBeenCalledWith('/system/self-check')
    expect(res.status).toBe('ok')
  })

  it('无 data 包裹时直返响应', async () => {
    mockGet.mockResolvedValue({ status: 'warn', checks: [] })
    const res = await getSelfCheck()
    expect(res.status).toBe('warn')
  })
})
