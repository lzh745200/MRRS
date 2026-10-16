import { describe, it, expect, vi } from 'vitest'

const { mockGet } = vi.hoisted(() => ({ mockGet: vi.fn() }))
vi.mock('@/api/request', () => ({ get: mockGet,
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

import {
  getMonitorSnapshot,
  getDatabaseFileSize,
} from '@/api/systemMonitor'

describe('api/systemMonitor', () => {
  it('getMonitorSnapshot calls GET /system/monitor/snapshot', async () => {
    const resp = { success: true, data: { cpu_usage: 50, timestamp: '2026-01-01' } }
    mockGet.mockResolvedValue(resp)
    const r = await getMonitorSnapshot()
    expect(mockGet).toHaveBeenCalledWith('/system/monitor/snapshot')
    expect(r).toBe(resp)
  })

  it('getDatabaseFileSize calls GET /system/monitor/database-size', async () => {
    const resp = { success: true, data: { size_bytes: 1024, size_mb: 0.001 } }
    mockGet.mockResolvedValue(resp)
    const r = await getDatabaseFileSize()
    expect(mockGet).toHaveBeenCalledWith('/system/monitor/database-size')
    expect(r).toBe(resp)
  })
})
