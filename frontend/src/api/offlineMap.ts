/**
 * 离线地图 / 瓦片包 API
 *
 * 后端契约（离线部署，禁止任何外网请求）：
 * - GET    /map/tile-info         本机瓦片预置信息 → `@/api/map` 的 getTileInfo
 * - GET    /map/tiles/{z}/{x}/{y}.png  本地瓦片文件（无鉴权、immutable 缓存），
 *                                     由 Leaflet TileLayer 按 URL 模板直接加载，
 *                                     不经过 axios —— 见 `@/utils/mapTiles` 的 TILE_URL_TEMPLATE
 * - POST   /map/tiles/import      导入 .zip 瓦片包（multipart，管理员）
 * - DELETE /offline-map/clear     清空本机瓦片缓存（管理员）
 *
 * 已下线（不要再调用）：
 * - GET  /offline-map/tiles/{z}/{x}/{y}  旧瓦片端点，改用 /map/tiles/...
 * - POST /offline-map/download           旧的"联网下载瓦片"端点，后端改为显式失败，
 *                                        瓦片改由运维离线生成瓦片包后导入。
 */
import { post, del } from '@/api/request'

/** 导入瓦片包响应（envelope 形态由 normalizeTileImportResult 归一化） */
export interface TileImportResult {
  success?: boolean
  message?: string
  tileCount?: number
  [key: string]: unknown
}

/** 清空瓦片缓存响应 */
export interface ClearTilesResult {
  success?: boolean
  message?: string
}

/**
 * 导入瓦片包（.zip，运维预先生成）。
 * multipart 字段名固定为 `file`（后端 UploadFile 参数名），CSRF 头由 request 拦截器补齐。
 *
 * 超时：全局 axios 超时是 30s，但大包解压落盘需要时间（实测 z14 全省包
 * 64,900 张 / 283.7MB 后端导入耗时 62.3s），30s 必然报“请求超时，请重试”。
 * 因此本接口单独放宽到 15 分钟，并把上传进度回调给页面展示。
 */
export const TILE_IMPORT_TIMEOUT_MS = 15 * 60 * 1000

export interface TileImportOptions {
  /** 覆盖默认 15 分钟超时（单测/特殊场景用） */
  timeoutMs?: number
  /** 上传进度 0~100；后端解压期间会停在 100，页面应提示“正在写入瓦片” */
  onProgress?: (percent: number) => void
}

export function importTiles(
  file: File,
  options: TileImportOptions = {}
): Promise<TileImportResult> {
  const form = new FormData()
  form.append('file', file)
  const { timeoutMs = TILE_IMPORT_TIMEOUT_MS, onProgress } = options
  return post<TileImportResult>('/map/tiles/import', form, {
    timeout: timeoutMs,
    onUploadProgress: (event: any) => {
      if (!onProgress) return
      const total = Number(event?.total ?? 0)
      if (total > 0) {
        const loaded = Number(event?.loaded ?? 0)
        onProgress(Math.min(100, Math.max(0, Math.round((loaded / total) * 100))))
      }
    },
  })
}

/** 清空本机瓦片缓存（管理员）；后端为整体清理，不支持按缩放级别 */
export function clearTiles(): Promise<ClearTilesResult> {
  return del<ClearTilesResult>('/offline-map/clear')
}
