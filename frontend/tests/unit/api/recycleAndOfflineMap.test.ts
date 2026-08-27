import { describe, it, expect, vi, beforeEach } from 'vitest'

const { mockGet, mockPost } = vi.hoisted(() => ({
  mockGet: vi.fn().mockResolvedValue({ data: {} }),
  mockPost: vi.fn().mockResolvedValue({ data: {} }),
}))

vi.mock('@/api/request', () => {
  const requestInstance = {
    get: (...args: unknown[]) => mockGet(...args),
    post: (...args: unknown[]) => mockPost(...args),
  }
  return {
    default: requestInstance,
    get: requestInstance.get,
    post: requestInstance.post,
  }
})

import { restoreFund, previewPurgeFund, purgeFund } from '@/api/fundsRecycle'
import { restoreSchool, previewPurgeSchool, purgeSchool } from '@/api/schoolsRecycle'
import { offlineMapApi, getMapStatus } from '@/api/offlineMap'

describe('api/fundsRecycle', () => {
  beforeEach(() => vi.clearAllMocks())

  it('restoreFund POST /funds/{id}/restore', async () => {
    await restoreFund(7)
    expect(mockPost).toHaveBeenCalledWith('/funds/7/restore', {})
  })

  it('previewPurgeFund GET /funds/{id}/purge/preview', async () => {
    await previewPurgeFund(7)
    expect(mockGet).toHaveBeenCalledWith('/funds/7/purge/preview')
  })

  it('purgeFund 携带确认密码；缺省时为空串', async () => {
    await purgeFund(7, 'pw')
    expect(mockPost).toHaveBeenCalledWith('/funds/7/purge', { confirm_password: 'pw' })
    await purgeFund(7)
    expect(mockPost).toHaveBeenCalledWith('/funds/7/purge', { confirm_password: '' })
  })
})

describe('api/schoolsRecycle', () => {
  beforeEach(() => vi.clearAllMocks())

  it('restoreSchool POST /schools/{id}/restore', async () => {
    await restoreSchool(3)
    expect(mockPost).toHaveBeenCalledWith('/schools/3/restore', {})
  })

  it('previewPurgeSchool GET /schools/{id}/purge/preview', async () => {
    await previewPurgeSchool(3)
    expect(mockGet).toHaveBeenCalledWith('/schools/3/purge/preview')
  })

  it('purgeSchool 携带确认密码', async () => {
    await purgeSchool(3, 'pw')
    expect(mockPost).toHaveBeenCalledWith('/schools/3/purge', { confirm_password: 'pw' })
  })
})

describe('api/offlineMap', () => {
  beforeEach(() => vi.clearAllMocks())

  it('getTiles / getStatus / getMapStatus 路径正确', async () => {
    await offlineMapApi.getTiles(10, 1, 2)
    expect(mockGet).toHaveBeenCalledWith('/offline-map/tiles/10/1/2')
    await offlineMapApi.getStatus()
    expect(mockGet).toHaveBeenCalledWith('/offline-map/status')
    await getMapStatus()
    expect(mockGet).toHaveBeenCalledWith('/offline-map/status')
  })
})
