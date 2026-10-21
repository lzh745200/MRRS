/**
 * 离线瓦片底图纯逻辑单测（utils/mapTiles.ts）
 *
 * 覆盖：瓦片 URL 离线红线、tile-info 归一化、可用性判断、GCJ-02 判定与坐标修正、
 * 体积/缩放级别文案、导入包校验与导入响应归一化。
 */
import { describe, it, expect } from 'vitest'
import {
  GCJ02_HINT,
  TILE_ATTRIBUTION,
  TILE_LOAD_FAILED_HINT,
  TILE_PACKAGE_MAX_BYTES,
  TILE_URL_TEMPLATE,
  convertMarkersForTiles,
  formatManifestTime,
  formatTileBytes,
  formatZoomRange,
  isGcj02,
  isLocalTileUrl,
  isTileMapUsable,
  normalizeTileImportResult,
  normalizeTileInfo,
  tileInfoHint,
  toDisplayCoord,
  toFiniteNumber,
  validateTilePackage,
  wgs84ToGcj02,
} from '@/utils/mapTiles'
import type { TileInfo } from '@/api/map'

describe('utils/mapTiles — 离线瓦片 URL 红线', () => {
  it('TILE_URL_TEMPLATE 指向本机后端且不含外网 scheme', () => {
    expect(TILE_URL_TEMPLATE).toBe('/api/v1/map/tiles/{z}/{x}/{y}.png')
    expect(isLocalTileUrl(TILE_URL_TEMPLATE)).toBe(true)
    expect(isLocalTileUrl(TILE_ATTRIBUTION)).toBe(true) // 非 URL 文案也不含 scheme
  })

  it('拒绝空串 / 协议相对 / 带 scheme 的外网地址', () => {
    expect(isLocalTileUrl('')).toBe(false)
    expect(isLocalTileUrl('   ')).toBe(false)
    expect(isLocalTileUrl('//tile.openstreetmap.org/{z}/{x}/{y}.png')).toBe(false)
    expect(isLocalTileUrl('https://webrd01.is.autonavi.com/appmaptile?x={x}')).toBe(false)
    expect(isLocalTileUrl('HTTP://example.com/{z}.png')).toBe(false)
  })

  it('接受本机相对路径', () => {
    expect(isLocalTileUrl('/api/v1/map/tiles/{z}/{x}/{y}.png')).toBe(true)
    expect(isLocalTileUrl('api/v1/map/tiles/{z}/{x}/{y}.png')).toBe(true)
  })
})

describe('utils/mapTiles — toFiniteNumber', () => {
  it('解析数字与数字字符串', () => {
    expect(toFiniteNumber(12)).toBe(12)
    expect(toFiniteNumber('12.5')).toBe(12.5)
    expect(toFiniteNumber(0)).toBe(0)
  })

  it('非法值归一为 null', () => {
    expect(toFiniteNumber('')).toBeNull()
    expect(toFiniteNumber('  ')).toBeNull()
    expect(toFiniteNumber('abc')).toBeNull()
    expect(toFiniteNumber(Number.NaN)).toBeNull()
    expect(toFiniteNumber(Number.POSITIVE_INFINITY)).toBeNull()
    expect(toFiniteNumber(true)).toBeNull()
    expect(toFiniteNumber(null)).toBeNull()
    expect(toFiniteNumber(undefined)).toBeNull()
  })
})

describe('utils/mapTiles — normalizeTileInfo', () => {
  it('null / 非对象 → 全零默认值', () => {
    const info = normalizeTileInfo(null)
    expect(info).toEqual({
      available: false,
      tileCount: 0,
      zoomLevels: [],
      totalBytes: 0,
      dir: '',
      manifest: null,
    })
    expect(normalizeTileInfo([1, 2, 3]).tileCount).toBe(0)
    expect(normalizeTileInfo('oops').available).toBe(false)
  })

  it('后端 envelope（data 内层）→ 归一化并升序缩放级别', () => {
    const info = normalizeTileInfo({
      code: 200,
      success: true,
      data: {
        available: true,
        tileCount: 128,
        zoomLevels: [8, 4, 6],
        totalBytes: 2048,
        dir: '/app/data/map_tiles',
        manifest: { provider: 'osm', generatedAt: '2026-10-01T10:00:00Z' },
      },
    })
    expect(info.available).toBe(true)
    expect(info.tileCount).toBe(128)
    expect(info.zoomLevels).toEqual([4, 6, 8])
    expect(info.totalBytes).toBe(2048)
    expect(info.dir).toBe('/app/data/map_tiles')
    expect(info.manifest).toEqual({ provider: 'osm', generatedAt: '2026-10-01T10:00:00Z' })
  })

  it('裸对象（无 envelope）+ 字符串数字 / 非法缩放值 → 容错', () => {
    const info = normalizeTileInfo({
      available: true,
      tileCount: '9',
      zoomLevels: ['5', 7, 'bad', null],
      totalBytes: '1024',
      dir: 123,
      manifest: 'not-an-object',
    })
    expect(info.tileCount).toBe(9)
    expect(info.zoomLevels).toEqual([5, 7])
    expect(info.totalBytes).toBe(1024)
    expect(info.dir).toBe('')
    expect(info.manifest).toBeNull()
  })

  it('zoomLevels 非数组 → []；available 非 true → false', () => {
    const info = normalizeTileInfo({ available: 'yes', zoomLevels: '4,5' })
    expect(info.available).toBe(false)
    expect(info.zoomLevels).toEqual([])
    expect(info.manifest).toBeNull()
  })
})

describe('utils/mapTiles — 可用性判断与中文提示', () => {
  const usable: TileInfo = {
    available: true,
    tileCount: 10,
    zoomLevels: [4, 5],
    totalBytes: 1024,
    dir: '/tiles',
    manifest: null,
  }

  it('isTileMapUsable：需同时满足 available / tileCount>0 / zoomLevels 非空', () => {
    expect(isTileMapUsable(usable)).toBe(true)
    expect(isTileMapUsable(null)).toBe(false)
    expect(isTileMapUsable(undefined)).toBe(false)
    expect(isTileMapUsable({ ...usable, available: false })).toBe(false)
    expect(isTileMapUsable({ ...usable, tileCount: 0 })).toBe(false)
    expect(isTileMapUsable({ ...usable, zoomLevels: [] })).toBe(false)
  })

  it('tileInfoHint：不可用 / 空目录 / 缺缩放级别 / 可用', () => {
    expect(tileInfoHint(undefined)).toContain('尚未预置离线瓦片')
    expect(tileInfoHint({ ...usable, available: false })).toContain('尚未预置离线瓦片')
    expect(tileInfoHint({ ...usable, tileCount: 0 })).toBe('瓦片目录为空，地图将使用内置矢量底图。')
    expect(tileInfoHint({ ...usable, zoomLevels: [] })).toContain('缺少缩放级别信息')
    expect(tileInfoHint(usable)).toBe('')
  })
})

describe('utils/mapTiles — GCJ-02 判定与偏移修正', () => {
  it('isGcj02：高德系 provider 为真，其他为假', () => {
    expect(isGcj02(null)).toBe(false)
    expect(isGcj02(undefined)).toBe(false)
    expect(isGcj02({})).toBe(false)
    expect(isGcj02({ provider: '  ' })).toBe(false)
    expect(isGcj02({ provider: 123 } as any)).toBe(false)
    expect(isGcj02({ provider: 'AMAP' })).toBe(true)
    expect(isGcj02({ provider: 'gaode' })).toBe(true)
    expect(isGcj02({ provider: 'GCJ-02' })).toBe(true)
    expect(isGcj02({ provider: '高德' })).toBe(true)
    expect(isGcj02({ provider: 'osm' })).toBe(false)
  })

  it('GCJ02_HINT 文案提示偏移', () => {
    expect(GCJ02_HINT).toContain('GCJ-02')
    expect(GCJ02_HINT).toContain('偏移')
  })

  it('wgs84ToGcj02：境内坐标有小幅偏移，境外原样返回', () => {
    // 贵阳附近
    const guiyang = wgs84ToGcj02(26.65, 106.71)
    expect(guiyang.lat).not.toBe(26.65)
    expect(guiyang.lng).not.toBe(106.71)
    expect(Math.abs(guiyang.lat - 26.65)).toBeLessThan(0.01)
    expect(Math.abs(guiyang.lng - 106.71)).toBeLessThan(0.01)

    // 境外（纽约）不做偏移
    expect(wgs84ToGcj02(40.7, -74.0)).toEqual({ lat: 40.7, lng: -74.0 })
  })

  it('toDisplayCoord：GCJ-02 时转换，WGS-84 时原样返回', () => {
    expect(toDisplayCoord({ lat: 26.65, lng: 106.71 }, false)).toEqual({ lat: 26.65, lng: 106.71 })
    const converted = toDisplayCoord({ lat: 26.65, lng: 106.71 }, true)
    expect(converted).toEqual(wgs84ToGcj02(26.65, 106.71))
    expect(converted.lat).not.toBe(26.65)
    // 境外坐标即使 GCJ-02 底图也不偏移
    expect(toDisplayCoord({ lat: 40.7, lng: -74.0 }, true)).toEqual({ lat: 40.7, lng: -74.0 })
  })

  it('convertMarkersForTiles：GCJ-02 底图时才偏移，且不修改入参', () => {
    const markers = [
      { id: 1, name: '甲村', lat: 26.65, lng: 106.71 },
      { id: 2, name: '乙村', lat: 27.1, lng: 107.2 },
    ]
    const unchanged = convertMarkersForTiles(markers, false)
    expect(unchanged).toBe(markers)

    const converted = convertMarkersForTiles(markers, true)
    expect(converted).not.toBe(markers)
    expect(converted[0].id).toBe(1)
    expect(converted[0].lat).not.toBe(26.65)
    expect(markers[0].lat).toBe(26.65) // 入参未被修改
  })
})

describe('utils/mapTiles — 展示文案', () => {
  it('formatTileBytes：0 / 负数 / B / KB / MB / GB / TB 上限', () => {
    expect(formatTileBytes(0)).toBe('0 B')
    expect(formatTileBytes(-8)).toBe('0 B')
    expect(formatTileBytes(null)).toBe('0 B')
    expect(formatTileBytes(undefined)).toBe('0 B')
    expect(formatTileBytes(512)).toBe('512 B')
    expect(formatTileBytes(2048)).toBe('2.0 KB')
    expect(formatTileBytes(5 * 1024 * 1024)).toBe('5.0 MB')
    expect(formatTileBytes(150 * 1024 * 1024)).toBe('150 MB')
    expect(formatTileBytes(2 * 1024 ** 4)).toBe('2.0 TB')
    expect(formatTileBytes(2 * 1024 ** 5)).toBe('2048 TB') // 超出单位表后钳制
  })

  it('formatZoomRange：空 / 单级 / 多级', () => {
    expect(formatZoomRange([])).toBe('—')
    expect(formatZoomRange([8])).toBe('8 级')
    expect(formatZoomRange([12, 4])).toBe('4 – 12 级')
  })

  it('formatManifestTime：缺省 — / 非法 — / 正常值 trim', () => {
    expect(formatManifestTime(null)).toBe('—')
    expect(formatManifestTime(undefined)).toBe('—')
    expect(formatManifestTime({})).toBe('—')
    expect(formatManifestTime({ generatedAt: '   ' })).toBe('—')
    expect(formatManifestTime({ generatedAt: 123 as any })).toBe('—')
    expect(formatManifestTime({ generatedAt: ' 2026-10-01 12:00 ' })).toBe('2026-10-01 12:00')
  })

  it('TILE_LOAD_FAILED_HINT 为中文失败说明', () => {
    expect(TILE_LOAD_FAILED_HINT).toContain('瓦片加载失败')
  })
})

describe('utils/mapTiles — 瓦片包校验', () => {
  it('未选择文件 / 无文件名', () => {
    expect(validateTilePackage(null).ok).toBe(false)
    expect(validateTilePackage(undefined).message).toBe('未选择瓦片包文件')
    expect(validateTilePackage({}).message).toBe('未选择瓦片包文件')
  })

  it('非 .zip 被拒绝', () => {
    const result = validateTilePackage({ name: 'tiles.rar', size: 10 })
    expect(result.ok).toBe(false)
    expect(result.message).toBe('仅支持 .zip 格式的瓦片包')
  })

  it('空文件 / 大小缺失被拒绝', () => {
    expect(validateTilePackage({ name: 'tiles.zip', size: 0 }).message).toBe('瓦片包为空，无法导入')
    expect(validateTilePackage({ name: 'tiles.zip' }).ok).toBe(false)
  })

  it('超过 512MB 上限被拒绝并展示体积', () => {
    const result = validateTilePackage({ name: 'tiles.zip', size: TILE_PACKAGE_MAX_BYTES + 1 })
    expect(result.ok).toBe(false)
    expect(result.message).toContain('512MB')
    expect(result.message).toContain('MB')
  })

  it('合法 .zip（大小写不敏感）通过', () => {
    expect(validateTilePackage({ name: 'guizhou.ZIP', size: 1024 }).ok).toBe(true)
    expect(validateTilePackage({ name: 'guizhou.zip', size: TILE_PACKAGE_MAX_BYTES }).ok).toBe(true)
  })
})

describe('utils/mapTiles — 导入响应归一化', () => {
  it('envelope 形态：message + tileCount', () => {
    const outcome = normalizeTileImportResult({
      code: 200,
      success: true,
      message: '瓦片包导入完成',
      data: { tileCount: 256 },
    })
    expect(outcome).toEqual({ ok: true, message: '瓦片包导入完成', tileCount: 256 })
  })

  it('裸对象形态：缺 message 时用默认成功文案', () => {
    expect(normalizeTileImportResult({ success: true })).toEqual({
      ok: true,
      message: '瓦片包导入成功',
      tileCount: 0,
    })
  })

  it('显式 success=false 视为失败，并透出后端原因', () => {
    expect(normalizeTileImportResult({ success: false, message: '压缩包结构不合法' })).toEqual({
      ok: false,
      message: '压缩包结构不合法',
      tileCount: 0,
    })
    expect(normalizeTileImportResult({ success: false }).message).toBe('瓦片包导入失败')
  })

  it('异常输入 → 默认成功文案（HTTP 200 视为已受理）', () => {
    expect(normalizeTileImportResult(null)).toEqual({
      ok: true,
      message: '瓦片包导入成功',
      tileCount: 0,
    })
  })
})
