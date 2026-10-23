/**
 * 离线瓦片底图纯逻辑单测（utils/mapTiles.ts）
 *
 * 覆盖：瓦片 URL 离线红线、tile-info 归一化、可用性判断、GCJ-02 判定与坐标修正、
 * 体积/缩放级别/时间文案、ODbL 署名判定、导入包校验与导入响应归一化。
 */
import { describe, it, expect } from 'vitest'
import {
  GCJ02_HINT,
  OSM_ATTRIBUTION,
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
  tileAttribution,
  tileInfoHint,
  toDisplayCoord,
  toFiniteNumber,
  validateTilePackage,
  wgs84ToGcj02,
} from '@/utils/mapTiles'
import type { TileInfo } from '@/api/map'

const usable: TileInfo = {
  available: true,
  tileCount: 1423,
  zoomLevels: [5, 6, 7, 8, 9, 10, 11],
  totalBytes: 1623205,
  dir: 'map-tiles',
  manifest: { provider: 'osm', license: 'ODbL-1.0', generatedAt: '2026-10-22T09:00:00Z' },
}

describe('常量与离线红线', () => {
  it('瓦片 URL 模板指向本机后端相对路径', () => {
    expect(TILE_URL_TEMPLATE).toBe('/api/v1/map/tiles/{z}/{x}/{y}.png')
    expect(isLocalTileUrl(TILE_URL_TEMPLATE)).toBe(true)
  })

  it('URL 必须是本机相对路径：拒绝空串、协议相对、任何 scheme', () => {
    expect(isLocalTileUrl('')).toBe(false)
    expect(isLocalTileUrl('   ')).toBe(false)
    expect(isLocalTileUrl('//evil.example/tiles/{z}/{x}/{y}.png')).toBe(false)
    expect(isLocalTileUrl('http://evil.example/{z}/{x}/{y}.png')).toBe(false)
    expect(isLocalTileUrl('https://tile.openstreetmap.org/{z}/{x}/{y}.png')).toBe(false)
    expect(isLocalTileUrl('ftp://host/x.png')).toBe(false)
    expect(isLocalTileUrl('/tiles/{z}/{x}/{y}.png')).toBe(true)
  })

  it('提示文案与署名常量非空且为约定值', () => {
    expect(GCJ02_HINT).toContain('GCJ-02')
    expect(TILE_LOAD_FAILED_HINT).toContain('瓦片加载失败')
    expect(OSM_ATTRIBUTION).toBe('© OpenStreetMap contributors')
    expect(TILE_ATTRIBUTION).toBe('离线瓦片')
    expect(TILE_PACKAGE_MAX_BYTES).toBe(512 * 1024 * 1024)
  })
})

describe('toFiniteNumber', () => {
  it('数字与数字字符串正常转换', () => {
    expect(toFiniteNumber(12)).toBe(12)
    expect(toFiniteNumber('12.5')).toBe(12.5)
    expect(toFiniteNumber(' 7 ')).toBe(7)
    expect(toFiniteNumber(0)).toBe(0)
  })

  it('非法值一律 null（含布尔、空串、NaN、对象）', () => {
    expect(toFiniteNumber(null)).toBeNull()
    expect(toFiniteNumber(undefined)).toBeNull()
    expect(toFiniteNumber('')).toBeNull()
    expect(toFiniteNumber('abc')).toBeNull()
    expect(toFiniteNumber(Number.NaN)).toBeNull()
    expect(toFiniteNumber(Number.POSITIVE_INFINITY)).toBeNull()
    expect(toFiniteNumber(true)).toBeNull()
    expect(toFiniteNumber({})).toBeNull()
  })
})

describe('normalizeTileInfo', () => {
  it('兼容 axios 解包后的 envelope：data 内层字段提到顶层', () => {
    const info = normalizeTileInfo({
      code: 200,
      data: { available: true, tileCount: 9, zoomLevels: [9, 8], totalBytes: 2048, dir: 'd' },
    })
    expect(info.available).toBe(true)
    expect(info.tileCount).toBe(9)
    expect(info.zoomLevels).toEqual([8, 9]) // 排序 + 数值化
    expect(info.totalBytes).toBe(2048)
    expect(info.dir).toBe('d')
    expect(info.manifest).toBeNull()
  })

  it('裸对象同样可读，缺失字段回落默认值', () => {
    const info = normalizeTileInfo({ available: false })
    expect(info).toEqual({
      available: false,
      tileCount: 0,
      zoomLevels: [],
      totalBytes: 0,
      dir: '',
      manifest: null,
    })
  })

  it('异常输入（null/字符串/数组）返回默认结构且不抛错', () => {
    for (const raw of [null, undefined, 'x', 42, []]) {
      expect(normalizeTileInfo(raw)).toMatchObject({ available: false, tileCount: 0 })
    }
  })

  it('zoomLevels 过滤非法值，manifest 保留对象原样', () => {
    const info = normalizeTileInfo({
      available: true,
      tileCount: '3',
      zoomLevels: [8, '9', 'x', null],
      manifest: { provider: 'osm', zRange: [8, 9] },
    })
    expect(info.tileCount).toBe(3)
    expect(info.zoomLevels).toEqual([8, 9])
    expect(info.manifest).toEqual({ provider: 'osm', zRange: [8, 9] })
  })
})

describe('isTileMapUsable / tileInfoHint', () => {
  it('可用判定要求 available + tileCount>0 + zoomLevels 非空', () => {
    expect(isTileMapUsable(usable)).toBe(true)
    expect(isTileMapUsable(null)).toBe(false)
    expect(isTileMapUsable({ ...usable, available: false })).toBe(false)
    expect(isTileMapUsable({ ...usable, tileCount: 0 })).toBe(false)
    expect(isTileMapUsable({ ...usable, zoomLevels: [] })).toBe(false)
  })

  it('不可用原因逐分支给出中文说明，可用时为空串', () => {
    expect(tileInfoHint(usable)).toBe('')
    expect(tileInfoHint(null)).toContain('尚未预置离线瓦片')
    expect(tileInfoHint({ ...usable, available: false })).toContain('尚未预置离线瓦片')
    expect(tileInfoHint({ ...usable, tileCount: 0 })).toContain('瓦片目录为空')
    expect(tileInfoHint({ ...usable, zoomLevels: [] })).toContain('缺少缩放级别')
  })
})

describe('isGcj02 / tileAttribution', () => {
  it('GCJ-02 来源判定（amap/gaode/gcj-02/高德）', () => {
    for (const provider of ['amap', 'gaode', 'GCJ-02', 'gcj02', '高德']) {
      expect(isGcj02({ provider })).toBe(true)
    }
    for (const provider of ['osm', 'tianditu', 'local-schematic', '']) {
      expect(isGcj02({ provider })).toBe(false)
    }
    expect(isGcj02(null)).toBe(false)
    expect(isGcj02(undefined)).toBe(false)
  })

  it('OSM/ODbL 来源必须显示 OpenStreetMap 署名', () => {
    expect(tileAttribution({ provider: 'osm' })).toBe(OSM_ATTRIBUTION)
    expect(tileAttribution({ provider: 'osm-guizhou' })).toBe(OSM_ATTRIBUTION)
    expect(tileAttribution({ provider: 'local', license: 'ODbL-1.0' })).toBe(OSM_ATTRIBUTION)
    expect(tileAttribution({ provider: 'x', license: '© OpenStreetMap contributors' })).toBe(
      OSM_ATTRIBUTION
    )
  })

  it('非 OSM 来源回退"离线瓦片"，空 manifest 不报错', () => {
    expect(tileAttribution(null)).toBe(TILE_ATTRIBUTION)
    expect(tileAttribution(undefined)).toBe(TILE_ATTRIBUTION)
    expect(tileAttribution({ provider: 'local-schematic' })).toBe(TILE_ATTRIBUTION)
    expect(tileAttribution({ provider: 'tianditu', license: '天地图授权' })).toBe(TILE_ATTRIBUTION)
  })
})

describe('格式化函数', () => {
  it('formatTileBytes：0/非法值 → 0 B，其余按 KB/MB 折算', () => {
    expect(formatTileBytes(0)).toBe('0 B')
    expect(formatTileBytes(null)).toBe('0 B')
    expect(formatTileBytes(-1)).toBe('0 B')
    expect(formatTileBytes(512)).toBe('512 B')
    expect(formatTileBytes(1024)).toBe('1.0 KB')
    expect(formatTileBytes(1536)).toBe('1.5 KB')
    expect(formatTileBytes(1024 * 1024 * 2.5)).toBe('2.5 MB')
    expect(formatTileBytes(1024 ** 3 * 150)).toBe('150 GB')
  })

  it('formatZoomRange：空 → —，单级 → "N 级"，多级 → 区间', () => {
    expect(formatZoomRange([])).toBe('—')
    expect(formatZoomRange([8])).toBe('8 级')
    expect(formatZoomRange([9, 4, 12])).toBe('4 – 12 级')
    expect(formatZoomRange([5, 11])).toBe('5 – 11 级')
  })

  it('formatManifestTime：有值去空格，无值 → —', () => {
    expect(formatManifestTime({ generatedAt: ' 2026-10-22T09:00:00Z ' })).toBe(
      '2026-10-22T09:00:00Z'
    )
    expect(formatManifestTime({})).toBe('—')
    expect(formatManifestTime(null)).toBe('—')
  })
})

describe('validateTilePackage', () => {
  it('未选择文件 / 非 zip / 空文件 / 超限 均拒绝', () => {
    expect(validateTilePackage(null).ok).toBe(false)
    expect(validateTilePackage({}).ok).toBe(false)
    expect(validateTilePackage({ name: 'tiles.tar', size: 10 }).message).toContain('.zip')
    expect(validateTilePackage({ name: 'tiles.zip', size: 0 }).message).toContain('为空')
    const big = validateTilePackage({ name: 'tiles.zip', size: TILE_PACKAGE_MAX_BYTES + 1 })
    expect(big.ok).toBe(false)
    expect(big.message).toContain('512MB')
  })

  it('合法 zip 通过（后缀大小写不敏感）', () => {
    expect(validateTilePackage({ name: 'tiles.zip', size: 1024 }).ok).toBe(true)
    expect(validateTilePackage({ name: 'TILES.ZIP', size: 1024 }).ok).toBe(true)
  })

  it('size 缺失或非数值 → 按 0 处理并判为空文件', () => {
    // `toFiniteNumber(file.size) ?? 0` 的 null 侧：浏览器拿不到真实 size 时
    // 必须按"空文件"拒绝，而不是把 undefined 当成合法大小放过去。
    expect(validateTilePackage({ name: 'tiles.zip' }).ok).toBe(false)
    expect(validateTilePackage({ name: 'tiles.zip' }).message).toContain('为空')
    expect(validateTilePackage({ name: 'tiles.zip', size: undefined }).message).toContain('为空')
    expect(validateTilePackage({ name: 'tiles.zip', size: NaN }).message).toContain('为空')
    expect(
      validateTilePackage({ name: 'tiles.zip', size: 'abc' as unknown as number }).message
    ).toContain('为空')
  })
})

describe('normalizeTileImportResult', () => {
  it('嵌套 data 与顶层 message 都能读到', () => {
    const out = normalizeTileImportResult({
      success: true,
      message: '瓦片包导入完成',
      data: { tileCount: 1215 },
    })
    expect(out).toEqual({ ok: true, message: '瓦片包导入完成', tileCount: 1215 })
  })

  it('显式 success=false 视为失败并透出后端原因', () => {
    expect(normalizeTileImportResult({ success: false, message: '压缩包结构不合法' })).toEqual({
      ok: false,
      message: '压缩包结构不合法',
      tileCount: 0,
    })
    expect(normalizeTileImportResult({ success: false }).message).toBe('瓦片包导入失败')
  })

  it('缺 message 时给默认文案，异常输入视为已受理', () => {
    expect(normalizeTileImportResult({ success: true, tileCount: '3' })).toEqual({
      ok: true,
      message: '瓦片包导入成功',
      tileCount: 3,
    })
    expect(normalizeTileImportResult(null)).toEqual({
      ok: true,
      message: '瓦片包导入成功',
      tileCount: 0,
    })
  })
})

describe('WGS-84 → GCJ-02 坐标修正', () => {
  it('中国境外原样返回', () => {
    expect(wgs84ToGcj02(51.5074, -0.1278)).toEqual({ lat: 51.5074, lng: -0.1278 }) // 伦敦
    expect(toDisplayCoord({ lat: 35.6762, lng: 139.6503 }, true)).toEqual({
      lat: 35.6762,
      lng: 139.6503,
    })
  })

  it('境内偏移量在数百米量级（0.0001°~0.02°），且不等于原值', () => {
    const wgs = { lat: 26.258205, lng: 107.517021 } // 都匀市
    const gcj = wgs84ToGcj02(wgs.lat, wgs.lng)
    expect(gcj.lat).not.toBe(wgs.lat)
    expect(gcj.lng).not.toBe(wgs.lng)
    expect(Math.abs(gcj.lat - wgs.lat)).toBeLessThan(0.02)
    expect(Math.abs(gcj.lng - wgs.lng)).toBeLessThan(0.02)
    expect(Math.abs(gcj.lat - wgs.lat)).toBeGreaterThan(0.0001)
  })

  it('转换是确定性的（同输入同输出）', () => {
    const a = wgs84ToGcj02(26.65, 106.63)
    const b = wgs84ToGcj02(26.65, 106.63)
    expect(a).toEqual(b)
  })

  it('toDisplayCoord：gcj02=false 原样，true 走转换', () => {
    const wgs = { lat: 26.65, lng: 106.63 }
    expect(toDisplayCoord(wgs, false)).toEqual(wgs)
    expect(toDisplayCoord(wgs, true)).toEqual(wgs84ToGcj02(wgs.lat, wgs.lng))
  })

  it('convertMarkersForTiles：非 GCJ 底图原样返回，GCJ 底图返回新数组且不改入参', () => {
    const markers = [
      { name: 'a', lat: 26.65, lng: 106.63 },
      { name: 'b', lat: 27.7, lng: 106.9 },
    ]
    expect(convertMarkersForTiles(markers, false)).toBe(markers)
    const converted = convertMarkersForTiles(markers, true)
    expect(converted).not.toBe(markers)
    expect(converted[0]).not.toEqual(markers[0])
    expect(converted[0].name).toBe('a')
    expect(markers[0]).toEqual({ name: 'a', lat: 26.65, lng: 106.63 })
  })
})
