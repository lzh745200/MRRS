import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockGet = vi.fn()
const mockPost = vi.fn()
const mockDelete = vi.fn()

vi.mock('@/api/request', () => ({
  get: (...args: any[]) => mockGet(...args),
  post: (...args: any[]) => mockPost(...args),
  del: (...args: any[]) => mockDelete(...args),
  getCsrfToken: vi.fn(() => Promise.resolve('test-csrf')),
}))

import { offlineMapApi, clearTiles, downloadTiles, getMapStatus } from '@/api/offlineMap'

describe('api/offlineMap', () => {
  beforeEach(() => vi.clearAllMocks())

  it('offlineMapApi.getTiles with z/x/y', () => {
    offlineMapApi.getTiles(10, 512, 256)
    expect(mockGet).toHaveBeenCalledWith('/offline-map/tiles/10/512/256')
  })
  it('offlineMapApi.getStatus', () => {
    offlineMapApi.getStatus()
    expect(mockGet).toHaveBeenCalledWith('/offline-map/status')
  })
  it('clearTiles DELETE /offline-map/clear', () => {
    clearTiles()
    expect(mockDelete).toHaveBeenCalledWith('/offline-map/clear')
  })
  it('downloadTiles POST /offline-map/download with params', () => {
    downloadTiles({
      min_lat: 30,
      max_lat: 40,
      min_lon: 110,
      max_lon: 120,
      min_zoom: 4,
      max_zoom: 12,
    })
    expect(mockPost).toHaveBeenCalledWith('/offline-map/download', null, {
      params: { min_lat: 30, max_lat: 40, min_lon: 110, max_lon: 120, min_zoom: 4, max_zoom: 12 },
    })
  })
  it('getMapStatus GET', () => {
    getMapStatus()
    expect(mockGet).toHaveBeenCalledWith('/offline-map/status')
  })
})
