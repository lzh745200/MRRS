import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockGet = vi.fn()
const mockPut = vi.fn()

vi.mock('@/api/request', () => ({
  default: { get: (...args: any[]) => mockGet(...args), put: (...args: any[]) => mockPut(...args) },
  get: (...args: any[]) => mockGet(...args),
  put: (...args: any[]) => mockPut(...args),
  getCsrfToken: vi.fn(() => Promise.resolve('test-csrf')),
}))

import {
  getMapMarkers,
  getCountyCoords,
  getRegions,
  updateMarkerCoordinates,
  getMapConfig,
  getDistances,
  getTileInfo,
} from '@/api/map'

describe('api/map', () => {
  beforeEach(() => vi.clearAllMocks())

  it('getMapMarkers 默认 all', async () => {
    mockGet.mockResolvedValueOnce({ villages: [], schools: [] })
    await getMapMarkers()
    expect(mockGet).toHaveBeenCalledWith('/map/markers', { marker_type: 'all' })
  })

  it('getMapMarkers 指定 villages', async () => {
    mockGet.mockResolvedValueOnce({ villages: [] })
    await getMapMarkers('villages')
    expect(mockGet).toHaveBeenCalledWith('/map/markers', { marker_type: 'villages' })
  })

  it('getMapMarkers 指定 schools', async () => {
    mockGet.mockResolvedValueOnce({ schools: [] })
    await getMapMarkers('schools')
    expect(mockGet).toHaveBeenCalledWith('/map/markers', { marker_type: 'schools' })
  })

  it('getCountyCoords GET /map/county-coords', async () => {
    mockGet.mockResolvedValueOnce({ center: { lng: 1, lat: 2 }, counties: {} })
    await getCountyCoords()
    expect(mockGet).toHaveBeenCalledWith('/map/county-coords')
  })

  it('getRegions 无参', async () => {
    mockGet.mockResolvedValueOnce({ total: 0, items: [] })
    await getRegions()
    expect(mockGet).toHaveBeenCalledWith('/map/regions', {})
  })

  it('getRegions level + parentCode', async () => {
    mockGet.mockResolvedValueOnce({ total: 0, items: [] })
    await getRegions('city', '110000')
    expect(mockGet).toHaveBeenCalledWith('/map/regions', { level: 'city', parent_code: '110000' })
  })

  it('getRegions 只传 level', async () => {
    mockGet.mockResolvedValueOnce({ total: 0, items: [] })
    await getRegions('province')
    expect(mockGet).toHaveBeenCalledWith('/map/regions', { level: 'province' })
  })

  it('updateMarkerCoordinates PUT /map/markers/{type}/{id}/coordinates', async () => {
    mockPut.mockResolvedValueOnce({ success: true })
    await updateMarkerCoordinates('village', 5, 40.0, 116.0)
    expect(mockPut).toHaveBeenCalledWith('/map/markers/village/5/coordinates', {
      latitude: 40.0,
      longitude: 116.0,
    })
  })

  it('getMapConfig GET /map/config 透传返回值', async () => {
    const body = { center: [116, 40], zoom: 8 }
    mockGet.mockResolvedValueOnce(body)
    const r = await getMapConfig()
    expect(mockGet).toHaveBeenCalledWith('/map/config')
    expect(r).toBe(body)
  })

  it('getDistances 无参', async () => {
    mockGet.mockResolvedValueOnce({})
    await getDistances()
    expect(mockGet).toHaveBeenCalledWith('/map/distances', undefined)
  })

  it('getDistances 带 from_id/to_id', async () => {
    const body = { distance_km: 12.3 }
    mockGet.mockResolvedValueOnce(body)
    const r = await getDistances({ from_id: 1, to_id: 2 })
    expect(mockGet).toHaveBeenCalledWith('/map/distances', { from_id: 1, to_id: 2 })
    expect(r).toBe(body)
  })

  it('getTileInfo GET /map/tile-info', async () => {
    const body = { version: 'v1' }
    mockGet.mockResolvedValueOnce(body)
    const r = await getTileInfo()
    expect(mockGet).toHaveBeenCalledWith('/map/tile-info')
    expect(r).toBe(body)
  })
})
