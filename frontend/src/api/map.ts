/**
 * 地图可视化API
 */
import { get, put } from '@/api/request'

const BASE_URL = '/map'

export interface VillageMarker {
  id: number
  name: string
  lng: number
  lat: number
  county: string
  department: string
  supportUnit: string
  regionScope: string
  isThreeRegions: boolean
  isKeyCounty: boolean
  isBorderArea: boolean
  isProvincialDemo: boolean
  isHundredVillageDemo: boolean
  isRevitalizationTier: boolean
}

export interface SchoolMarker {
  id: number
  name: string
  lng: number
  lat: number
  district: string
  type: string
  supportStatus: string
  supportUnit: string
  studentCount: number
  teacherCount: number
}

export interface MapMarkers {
  villages?: VillageMarker[]
  schools?: SchoolMarker[]
}

export interface CountyCoord {
  lng: number
  lat: number
}

export interface CountyCoordsResponse {
  center: CountyCoord
  counties: Record<string, CountyCoord>
}

/**
 * 获取地图标注数据
 */
export async function getMapMarkers(
  markerType: 'all' | 'villages' | 'schools' = 'all'
): Promise<MapMarkers> {
  return get(BASE_URL + '/markers', { marker_type: markerType })
}

export async function getCountyCoords(): Promise<CountyCoordsResponse> {
  return get(BASE_URL + '/county-coords')
}

export interface RegionItem {
  code: string
  name: string
  level: string
  parentCode: string | null
  centerLng: number | null
  centerLat: number | null
  geometry: any
}

export async function getRegions(
  level?: string,
  parentCode?: string
): Promise<{ total: number; items: RegionItem[] }> {
  const params: Record<string, string> = {}
  if (level) params.level = level
  if (parentCode) params.parent_code = parentCode
  return get(BASE_URL + '/regions', params)
}

export async function updateMarkerCoordinates(
  markerType: 'village' | 'school',
  markerId: number,
  latitude: number,
  longitude: number
) {
  return put(`${BASE_URL}/markers/${markerType}/${markerId}/coordinates`, {
    latitude,
    longitude,
  })
}

export async function getMapConfig(): Promise<Record<string, any>> {
  return get(BASE_URL + '/config')
}

export async function getTileInfo(): Promise<Record<string, any>> {
  return get(BASE_URL + '/tile-info')
}
