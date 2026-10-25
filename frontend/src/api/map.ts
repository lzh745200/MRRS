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

/** 瓦片覆盖范围：[minLon, minLat, maxLon, maxLat]（WGS-84/底图坐标系） */
export type TileBbox = [number, number, number, number]

/**
 * 离线瓦片包清单（随瓦片包一起由运维生成，后端 `/map/tile-info` 透出）。
 * 关键字段：provider —— 'amap'/'gaode' 表示底图为 GCJ-02 坐标系（标记点需偏移修正）。
 */
export interface TileManifest {
  /** 瓦片来源：如 'amap'（GCJ-02）/ 'osm'（WGS-84）/ 自建离线包标识 */
  provider?: string
  /** 瓦片包生成时间（ISO 字符串，直接展示给运维） */
  generatedAt?: string
  /** 瓦片包版本/名称 */
  version?: string
  /** 瓦片覆盖范围 [minLon, minLat, maxLon, maxLat]（可选，随包清单下发） */
  bbox?: TileBbox
  /** 瓦片包区域信息（可选，部分包把 bbox 放在 region 内） */
  region?: { bbox?: TileBbox; [key: string]: unknown }
  [key: string]: unknown
}

/**
 * 本机离线瓦片信息（GET /map/tile-info）。
 * 归一化后字段恒定存在，缺省值见 `@/utils/mapTiles` 的 normalizeTileInfo。
 */
export interface TileInfo {
  /** 后端声明瓦片是否可用（瓦片目录存在且含 .png） */
  available: boolean
  /** .png 瓦片总数 */
  tileCount: number
  /** 已预置的缩放级别（升序） */
  zoomLevels: number[]
  /** 瓦片总字节数 */
  totalBytes: number
  /** 瓦片根目录（便于运维核对） */
  dir: string
  /** 瓦片包清单 */
  manifest: TileManifest | null
  /**
   * 瓦片覆盖范围 [minLon, minLat, maxLon, maxLat]（后端诊断字段）。
   * 缺失/非法时前端回退到贵州兜底 bbox，避免把视野放到无瓦片区。
   */
  bbox?: TileBbox | null
  /** 瓦片来源标识（后端诊断字段，如 'osm' / 'amap'） */
  source?: string
  /** 瓦片不可用原因（后端诊断字段，缺失为 null） */
  reason?: string | null
}

export async function getTileInfo(): Promise<TileInfo> {
  return get(BASE_URL + '/tile-info')
}
