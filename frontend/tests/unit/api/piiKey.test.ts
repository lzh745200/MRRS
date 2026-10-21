/**
 * api/piiKey.ts 测试
 * 覆盖：状态查询、密钥导出、密钥导入三个端点的 URL/载荷透传。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'

const { mockGet, mockPost } = vi.hoisted(() => ({
  mockGet: vi.fn(),
  mockPost: vi.fn(),
}))

vi.mock('@/api/request', () => ({
  get: mockGet,
  post: mockPost,
}))

import { getPiiKeyStatus, exportPiiKey, importPiiKey, piiKeyApi } from '@/api/piiKey'

describe('api/piiKey', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('getPiiKeyStatus：GET /system/pii-key', async () => {
    mockGet.mockResolvedValue({ fingerprint: 'abc', source: 'runtime', available: true })
    const res = await getPiiKeyStatus()
    expect(mockGet).toHaveBeenCalledWith('/system/pii-key')
    expect(res.fingerprint).toBe('abc')
  })

  it('exportPiiKey：GET /system/pii-key/export', async () => {
    mockGet.mockResolvedValue({
      fingerprint: 'abc',
      key: 'secret',
      source: 'env',
      available: true,
    })
    const res = await exportPiiKey()
    expect(mockGet).toHaveBeenCalledWith('/system/pii-key/export')
    expect(res.key).toBe('secret')
    expect(res.source).toBe('env')
  })

  it('importPiiKey：POST /system/pii-key/import，载荷为 {key}', async () => {
    mockPost.mockResolvedValue({ fingerprint: 'new', source: 'runtime', available: true })
    const res = await importPiiKey('new-secret')
    expect(mockPost).toHaveBeenCalledWith('/system/pii-key/import', { key: 'new-secret' })
    expect(res.fingerprint).toBe('new')
  })

  it('分组导出绑定同一批实现', () => {
    expect(piiKeyApi.status).toBe(getPiiKeyStatus)
    expect(piiKeyApi.exportKey).toBe(exportPiiKey)
    expect(piiKeyApi.importKey).toBe(importPiiKey)
  })
})
