/**
 * 离线瓦片底图 —— 纯逻辑工具（与 Leaflet 解耦，可直接在 jsdom 里单测）
 *
 * 离线验收红线：瓦片只能来自本机后端 `/api/v1/map/tiles/{z}/{x}/{y}.png`，
 * 任何外网 tile URL（含协议相对 `//host`）都必须被拒绝。
 *
 * 坐标系统：瓦片默认按 WGS-84 / 标准 Web Mercator 组织；若 manifest.provider
 * 为高德系（GCJ-02），标注点需做 WGS-84 → GCJ-02 偏移修正，并提示用户。
 */
import type { TileInfo, TileManifest } from '@/api/map'

/** 本机后端瓦片 URL 模板：Leaflet TileLayer 直接展开 {z}/{x}/{y} */
export const TILE_URL_TEMPLATE = '/api/v1/map/tiles/{z}/{x}/{y}.png'

/** 瓦片版权标注（离线包无外网来源，标注为本机离线瓦片） */
export const TILE_ATTRIBUTION = '离线瓦片'

/** OSM/ODbL 署名（ODbL 要求在任何使用 OSM 数据的成品上显示） */
export const OSM_ATTRIBUTION = '© OpenStreetMap contributors'

/** 导入瓦片包上限：后端 multipart 默认上限 512MB（app/middleware/body_size_limit.py） */
export const TILE_PACKAGE_MAX_BYTES = 512 * 1024 * 1024

/** GCJ-02 底图提示（高德等国内厂商瓦片存在 WGS-84 → GCJ-02 偏移） */
export const GCJ02_HINT = '底图为 GCJ-02 坐标系，标记点可能存在偏移'

/** 瓦片加载失败提示（Leaflet tileerror：后端 404 表示该层级未预置） */
export const TILE_LOAD_FAILED_HINT =
  '瓦片加载失败：本机后端未提供当前层级的瓦片文件，无法显示瓦片底图，请返回矢量视图。'

/** 判定为 GCJ-02 的来源标识（小写比较） */
const GCJ02_PROVIDERS = ['amap', 'gaode', 'gcj02', 'gcj-02', '高德']

type Dict = Record<string, unknown>

/** 安全地当作普通对象读取（数组 / null / 原始值都归一为空对象） */
function asDict(value: unknown): Dict {
  return value !== null && typeof value === 'object' && !Array.isArray(value) ? (value as Dict) : {}
}

/**
 * 取响应载荷：axios 响应拦截器会把 envelope.data 的字段提到顶层，
 * 但裸返回（无 envelope）同样可能出现，两种形态都要能读。
 */
function payloadOf(raw: unknown): Dict {
  const root = asDict(raw)
  const inner = asDict(root.data)
  return Object.keys(inner).length > 0 ? { ...root, ...inner } : root
}

/**
 * 瓦片 URL 必须是本机后端相对路径。
 * 拒绝：空串、协议相对 `//host`、任何 `scheme://` 绝对地址（http/https/ftp…）。
 */
export function isLocalTileUrl(url: string): boolean {
  const value = url.trim()
  if (!value) return false
  if (value.startsWith('//')) return false
  return !/^[a-z][a-z0-9+.-]*:\/\//i.test(value)
}

/** 数字/数字字符串 → 有限数字；其余（null/undefined/NaN/布尔/空串）→ null */
export function toFiniteNumber(value: unknown): number | null {
  const parsed = typeof value === 'string' && value.trim() !== '' ? Number(value) : value
  return typeof parsed === 'number' && Number.isFinite(parsed) ? parsed : null
}

/**
 * 归一化 `/map/tile-info` 响应（envelope / 裸对象均可）。
 * 返回字段恒定存在，便于模板直接展示；兼容后端尚未返回 totalBytes/manifest 的过渡期。
 */
export function normalizeTileInfo(raw: unknown): TileInfo {
  const payload = payloadOf(raw)
  const zoomLevels = Array.isArray(payload.zoomLevels)
    ? payload.zoomLevels
        .map((level) => toFiniteNumber(level))
        .filter((level): level is number => level !== null)
        .sort((a, b) => a - b)
    : []
  const manifest = asDict(payload.manifest)
  return {
    available: payload.available === true,
    tileCount: toFiniteNumber(payload.tileCount) ?? 0,
    zoomLevels,
    totalBytes: toFiniteNumber(payload.totalBytes) ?? 0,
    dir: typeof payload.dir === 'string' ? payload.dir : '',
    manifest: Object.keys(manifest).length > 0 ? (manifest as TileManifest) : null,
  }
}

/** 是否可切换到瓦片底图：后端声明可用 + 有瓦片文件 + 有缩放级别（类型守卫） */
export function isTileMapUsable(info: TileInfo | null | undefined): info is TileInfo {
  return Boolean(info && info.available && info.tileCount > 0 && info.zoomLevels.length > 0)
}

/** 不可用原因的中文说明（可用时返回空串，模板据此隐藏提示） */
export function tileInfoHint(info: TileInfo | null | undefined): string {
  if (!info || !info.available) {
    return '本机尚未预置离线瓦片，地图将使用内置矢量底图。请运维生成瓦片包后在「地图瓦片管理」页导入。'
  }
  if (info.tileCount === 0) {
    return '瓦片目录为空，地图将使用内置矢量底图。'
  }
  if (info.zoomLevels.length === 0) {
    return '瓦片包缺少缩放级别信息，地图将使用内置矢量底图。'
  }
  return ''
}

/** 底图是否为 GCJ-02 坐标系（amap/gaode 等国内厂商瓦片） */
export function isGcj02(manifest: TileManifest | null | undefined): boolean {
  const provider = manifest?.provider
  if (typeof provider !== 'string' || !provider.trim()) return false
  return GCJ02_PROVIDERS.includes(provider.trim().toLowerCase())
}

/**
 * 底图署名文案：OSM 衍生瓦片必须显示 ODbL 署名，其余用"离线瓦片"。
 * 判定依据：manifest.provider 含 osm，或 license 含 ODbL/OpenStreetMap（不区分大小写）。
 */
export function tileAttribution(manifest: TileManifest | null | undefined): string {
  const provider = typeof manifest?.provider === 'string' ? manifest.provider.toLowerCase() : ''
  const license = typeof manifest?.license === 'string' ? manifest.license.toLowerCase() : ''
  const isOsm =
    provider.includes('osm') ||
    license.includes('osm') ||
    license.includes('openstreetmap') ||
    license.includes('odbl')
  return isOsm ? OSM_ATTRIBUTION : TILE_ATTRIBUTION
}

/** 字节数 → 人类可读体积（0 / 非法值 → '0 B'） */
export function formatTileBytes(bytes: number | null | undefined): string {
  const value = toFiniteNumber(bytes) ?? 0
  if (value <= 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const exponent = Math.min(Math.floor(Math.log(value) / Math.log(1024)), units.length - 1)
  if (exponent === 0) return `${value} B`
  const scaled = value / 1024 ** exponent
  const digits = scaled >= 100 ? 0 : 1
  return `${scaled.toFixed(digits)} ${units[exponent]}`
}

/** 缩放级别数组 → 区间文案（如 "4 – 12 级" / "8 级" / "—"） */
export function formatZoomRange(zoomLevels: number[]): string {
  if (zoomLevels.length === 0) return '—'
  const sorted = [...zoomLevels].sort((a, b) => a - b)
  const min = sorted[0]
  const max = sorted[sorted.length - 1]
  return min === max ? `${min} 级` : `${min} – ${max} 级`
}

/** manifest 生成时间文案（缺省 "—"） */
export function formatManifestTime(manifest: TileManifest | null | undefined): string {
  const generatedAt = manifest?.generatedAt
  return typeof generatedAt === 'string' && generatedAt.trim() ? generatedAt.trim() : '—'
}

/** 瓦片包上传前校验结果 */
export interface TilePackageValidation {
  ok: boolean
  message: string
}

/**
 * 上传前校验瓦片包：必须是 .zip、非空、且不超过 512MB。
 * 后端 multipart 上限同为 512MB，前端提前拦截可避免整包上传后才失败。
 */
export function validateTilePackage(
  file: { name?: string; size?: number } | null | undefined
): TilePackageValidation {
  if (!file || !file.name) return { ok: false, message: '未选择瓦片包文件' }
  if (!/\.zip$/i.test(file.name)) return { ok: false, message: '仅支持 .zip 格式的瓦片包' }
  const size = toFiniteNumber(file.size) ?? 0
  if (size <= 0) return { ok: false, message: '瓦片包为空，无法导入' }
  if (size > TILE_PACKAGE_MAX_BYTES) {
    return { ok: false, message: `瓦片包超过 512MB 上限（当前 ${formatTileBytes(size)}）` }
  }
  return { ok: true, message: '' }
}

/** 导入响应归一化结果 */
export interface TileImportOutcome {
  ok: boolean
  message: string
  tileCount: number
}

/** 归一化 `POST /map/tiles/import` 响应（显式 success=false 视为失败） */
export function normalizeTileImportResult(raw: unknown): TileImportOutcome {
  const payload = payloadOf(raw)
  const ok = payload.success !== false
  const tileCount = toFiniteNumber(payload.tileCount) ?? 0
  const message = typeof payload.message === 'string' ? payload.message.trim() : ''
  if (message) return { ok, message, tileCount }
  return { ok, message: ok ? '瓦片包导入成功' : '瓦片包导入失败', tileCount }
}

// ── WGS-84 → GCJ-02（GCJ-02 底图上标注点偏移修正） ──

const GCJ_A = 6378245.0
const GCJ_EE = 0.006693421622965943

/** 中国境外不做偏移（与 GCJ-02 官方实现一致的粗略边界） */
function outOfChina(lat: number, lng: number): boolean {
  return lng < 72.004 || lng > 137.8347 || lat < 0.8293 || lat > 55.8271
}

function deltaLat(x: number, y: number): number {
  let delta = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * Math.sqrt(Math.abs(x))
  delta += ((20.0 * Math.sin(6.0 * x * Math.PI) + 20.0 * Math.sin(2.0 * x * Math.PI)) * 2.0) / 3.0
  delta += ((20.0 * Math.sin(y * Math.PI) + 40.0 * Math.sin((y / 3.0) * Math.PI)) * 2.0) / 3.0
  delta +=
    ((160.0 * Math.sin((y / 12.0) * Math.PI) + 320 * Math.sin((y * Math.PI) / 30.0)) * 2.0) / 3.0
  return delta
}

function deltaLng(x: number, y: number): number {
  let delta = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * Math.sqrt(Math.abs(x))
  delta += ((20.0 * Math.sin(6.0 * x * Math.PI) + 20.0 * Math.sin(2.0 * x * Math.PI)) * 2.0) / 3.0
  delta += ((20.0 * Math.sin(x * Math.PI) + 40.0 * Math.sin((x / 3.0) * Math.PI)) * 2.0) / 3.0
  delta +=
    ((150.0 * Math.sin((x / 12.0) * Math.PI) + 300.0 * Math.sin((x / 30.0) * Math.PI)) * 2.0) / 3.0
  return delta
}

/** WGS-84 经纬度 → GCJ-02（境外原样返回） */
export function wgs84ToGcj02(lat: number, lng: number): { lat: number; lng: number } {
  if (outOfChina(lat, lng)) return { lat, lng }
  const dLat = deltaLat(lng - 105.0, lat - 35.0)
  const dLng = deltaLng(lng - 105.0, lat - 35.0)
  const radLat = (lat / 180.0) * Math.PI
  let magic = Math.sin(radLat)
  magic = 1 - GCJ_EE * magic * magic
  const sqrtMagic = Math.sqrt(magic)
  const convertedLat =
    lat + (dLat * 180.0) / (((GCJ_A * (1 - GCJ_EE)) / (magic * sqrtMagic)) * Math.PI)
  const convertedLng = lng + (dLng * 180.0) / ((GCJ_A / sqrtMagic) * Math.cos(radLat) * Math.PI)
  return { lat: convertedLat, lng: convertedLng }
}

/**
 * 单个坐标适配底图坐标系：GCJ-02 底图时 WGS-84 → GCJ-02，否则原样返回。
 * 地图中心与标注点必须走同一出口，否则底图与标注会整体错位。
 */
export function toDisplayCoord(
  coord: { lat: number; lng: number },
  gcj02: boolean
): { lat: number; lng: number } {
  return gcj02 ? wgs84ToGcj02(coord.lat, coord.lng) : { lat: coord.lat, lng: coord.lng }
}

/**
 * 标注点坐标适配底图坐标系：GCJ-02 底图时把 WGS-84 点位偏移到 GCJ-02，
 * 否则原样返回（WGS-84 底图）。返回新数组，不修改入参。
 */
export function convertMarkersForTiles<T extends { lat: number; lng: number }>(
  markers: T[],
  gcj02: boolean
): T[] {
  if (!gcj02) return markers
  return markers.map((marker) => ({ ...marker, ...toDisplayCoord(marker, true) }))
}
