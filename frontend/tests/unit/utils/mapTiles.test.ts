/**
 * 离线瓦片底图纯逻辑单测（utils/mapTiles.ts）
 *
 * 覆盖：瓦片 URL 离线红线、tile-info 归一化、可用性判断、GCJ-02 判定与坐标修正、
 * 体积/缩放级别/时间文案、ODbL 署名判定、导入包校验与导入响应归一化。
 */
import { describe, it, expect } from 'vitest'
import {
  GCJ02_HINT,
  LABEL_CELL_HEIGHT,
  LABEL_CELL_WIDTH,
  LABEL_MAX_COUNT,
  LABEL_MIN_ZOOM_SCHOOL,
  LABEL_MIN_ZOOM_VILLAGE,
  OSM_ATTRIBUTION,
  PARTIAL_COVERAGE_HINT,
  TILE_ATTRIBUTION,
  TILE_BOUNDS_PADDING_DEGREES,
  TILE_COVERAGE_FALLBACK_BBOX,
  TILE_FALLBACK_ERROR_THRESHOLD,
  TILE_FALLBACK_WATCHDOG_MS,
  TILE_FIT_MAX_ZOOM,
  TILE_LOAD_FAILED_HINT,
  TILE_MAP_MAX_ZOOM,
  TILE_MAP_MIN_ZOOM,
  TILE_MAX_OVERZOOM,
  TILE_MAX_UNDERZOOM,
  TILE_PACKAGE_MAX_BYTES,
  TILE_URL_TEMPLATE,
  TRANSPARENT_TILE_DATA_URI,
  convertMarkersForTiles,
  formatManifestTime,
  formatTileBytes,
  formatZoomRange,
  isGcj02,
  isLocalTileUrl,
  isTileMapUsable,
  labelZoomForType,
  normalizeTileImportResult,
  nearestNativeZoom,
  normalizeTileInfo,
  parseTileBbox,
  selectVisibleLabels,
  shouldFallbackToVector,
  tileAttribution,
  tileCoverageBbox,
  tileCoverageBounds,
  tileInfoHint,
  tileZoomLimits,
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
      bbox: null,
      source: '',
      reason: null,
    })
  })

  it('诊断字段透传：bbox / source / reason（含去空格与非法 bbox 归一）', () => {
    const info = normalizeTileInfo({
      available: true,
      tileCount: 4,
      bbox: ['103.6', 24.6, '109.6', 29.2],
      source: '  osm-guizhou  ',
      reason: '   ',
    })
    expect(info.bbox).toEqual([103.6, 24.6, 109.6, 29.2])
    expect(info.source).toBe('osm-guizhou')
    expect(info.reason).toBeNull() // 全空白视为无原因

    const reason = normalizeTileInfo({ reason: '瓦片目录为空' })
    expect(reason.reason).toBe('瓦片目录为空')
    expect(reason.source).toBe('')
    expect(reason.bbox).toBeNull()

    // 非法 bbox（长度/顺序）→ null，交给覆盖范围解析兜底
    expect(normalizeTileInfo({ bbox: [1, 2, 3] }).bbox).toBeNull()
    expect(normalizeTileInfo({ bbox: [110, 30, 100, 20] }).bbox).toBeNull()
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

describe('tileZoomLimits — 显示层级与瓦片原生层级解耦', () => {
  it('单层 z14 交付包：仍保留可交互缩放区间（旧实现 14/14 导致完全无法缩放）', () => {
    const limits = tileZoomLimits({ ...usable, zoomLevels: [14] })

    expect(limits).toEqual({
      minZoom: 14 - TILE_MAX_UNDERZOOM,
      maxZoom: 14 + TILE_MAX_OVERZOOM,
      minNativeZoom: 14,
      maxNativeZoom: 14,
    })
    expect(limits.maxZoom).toBeGreaterThan(limits.minZoom)
  })

  it('多级省级包：显示下限不低于 4，上限允许 2 档超采样', () => {
    const limits = tileZoomLimits(usable)

    expect(limits).toEqual({
      minZoom: TILE_MAP_MIN_ZOOM,
      maxZoom: 11 + TILE_MAX_OVERZOOM,
      minNativeZoom: 5,
      maxNativeZoom: 11,
    })
  })

  it('乱序层级取真实最小/最大；上限不超过全局 18', () => {
    const limits = tileZoomLimits({ ...usable, zoomLevels: [12, 5, 8] })
    expect(limits.minNativeZoom).toBe(5)
    expect(limits.maxNativeZoom).toBe(12)
    expect(limits.maxZoom).toBe(12 + TILE_MAX_OVERZOOM)

    const high = tileZoomLimits({ ...usable, zoomLevels: [17, 22] })
    expect(high.maxNativeZoom).toBe(22)
    expect(high.maxZoom).toBe(TILE_MAP_MAX_ZOOM)
  })

  it('空层级/异常低层级：minZoom 不高于 maxZoom，避免 Leaflet 建图直接抛错', () => {
    const empty = tileZoomLimits({ ...usable, zoomLevels: [] })
    expect(empty.minZoom).toBe(TILE_MAP_MIN_ZOOM)
    expect(empty.maxZoom).toBeGreaterThanOrEqual(empty.minZoom)

    const zero = tileZoomLimits({ ...usable, zoomLevels: [0] })
    expect(zero.minZoom).toBe(TILE_MAP_MIN_ZOOM)
    expect(zero.maxZoom).toBeGreaterThanOrEqual(zero.minZoom)

    const nullInfo = tileZoomLimits(null)
    expect(nullInfo.maxZoom).toBeGreaterThanOrEqual(nullInfo.minZoom)
  })
})

describe('nearestNativeZoom — 稀疏层级回退', () => {
  it('存在精确层级时直接使用', () => {
    expect(nearestNativeZoom([5, 6, 7, 8], 7)).toBe(7)
  })

  it('层级空洞取最近一级；距离相同取较低级', () => {
    expect(nearestNativeZoom([5, 11, 14], 12)).toBe(11)
    expect(nearestNativeZoom([5, 11, 14], 13)).toBe(14)
    expect(nearestNativeZoom([5, 11, 14], 9)).toBe(11)
    expect(nearestNativeZoom([5, 11, 14], 16)).toBe(14)
  })

  it('无层级/非法层级时原样返回，避免除零或 NaN 层级', () => {
    expect(nearestNativeZoom([], 9)).toBe(9)
    expect(nearestNativeZoom(undefined, 9)).toBe(9)
    expect(nearestNativeZoom([Number.NaN, 8], 9)).toBe(8)
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

describe('覆盖范围 bbox 与回退阈值（边缘 404 不支持整体回退）', () => {
  it('parseTileBbox：合法值原样，长度/非数值/顺序/越界全部 null', () => {
    expect(parseTileBbox([103.6, 24.6, 109.6, 29.2])).toEqual([103.6, 24.6, 109.6, 29.2])
    expect(parseTileBbox('x')).toBeNull()
    expect(parseTileBbox(null)).toBeNull()
    expect(parseTileBbox([1, 2, 3])).toBeNull()
    expect(parseTileBbox([1, 2, 3, 'x'])).toBeNull()
    expect(parseTileBbox([110, 20, 110, 30])).toBeNull() // 经度 min>=max
    expect(parseTileBbox([100, 30, 110, 30])).toBeNull() // 纬度 min>=max
    expect(parseTileBbox([-190, 20, 110, 30])).toBeNull() // 经度越界
    expect(parseTileBbox([100, 20, 190, 30])).toBeNull()
    expect(parseTileBbox([100, -95, 110, 30])).toBeNull() // 纬度越界
    expect(parseTileBbox([100, 20, 110, 95])).toBeNull()
  })

  it('tileCoverageBbox 优先级：info.bbox → manifest.region.bbox → manifest.bbox → 贵州兜底', () => {
    expect(tileCoverageBbox({ ...usable, bbox: [100, 20, 110, 30] })).toEqual([100, 20, 110, 30])
    expect(
      tileCoverageBbox({
        ...usable,
        bbox: null,
        manifest: { provider: 'osm', region: { bbox: [101, 21, 111, 31] } },
      })
    ).toEqual([101, 21, 111, 31])
    expect(
      tileCoverageBbox({
        ...usable,
        bbox: null,
        manifest: { provider: 'osm', bbox: [102, 22, 112, 32] },
      })
    ).toEqual([102, 22, 112, 32])
    // 非法/缺失逐级回退到兜底
    expect(tileCoverageBbox({ ...usable, bbox: [0, 0, 0, 0], manifest: null })).toEqual(
      TILE_COVERAGE_FALLBACK_BBOX
    )
    expect(tileCoverageBbox(null)).toEqual(TILE_COVERAGE_FALLBACK_BBOX)
    expect(tileCoverageBbox(undefined)).toEqual(TILE_COVERAGE_FALLBACK_BBOX)
    expect(
      tileCoverageBbox({
        ...usable,
        bbox: null,
        manifest: { provider: 'osm', region: { bbox: 'bad' }, bbox: [1, 2] },
      })
    ).toEqual(TILE_COVERAGE_FALLBACK_BBOX)
  })

  it('tileCoverageBounds 转成 Leaflet 的 [[south, west], [north, east]]', () => {
    expect(tileCoverageBounds({ ...usable, bbox: [103.6, 24.6, 109.6, 29.2] })).toEqual([
      [24.6, 103.6],
      [29.2, 109.6],
    ])
    expect(tileCoverageBounds(null)).toEqual([
      [24.6, 103.6],
      [29.2, 109.6],
    ])
  })

  it('常量契约：贵州兜底 bbox / 外扩 / fitBounds 上限 / 看门狗 / 阈值 / 部分覆盖文案', () => {
    expect(TILE_COVERAGE_FALLBACK_BBOX).toEqual([103.6, 24.6, 109.6, 29.2])
    expect(TILE_BOUNDS_PADDING_DEGREES).toBe(0.05)
    expect(TILE_FIT_MAX_ZOOM).toBe(9)
    expect(TILE_FALLBACK_WATCHDOG_MS).toBe(5000)
    expect(TILE_FALLBACK_ERROR_THRESHOLD).toBe(8)
    expect(PARTIAL_COVERAGE_HINT).toContain('超出预置瓦片范围')
    expect(PARTIAL_COVERAGE_HINT).toContain('属正常')
  })

  it('透明瓦片是 1×1 PNG data URI（边缘 404 不显示破图）', () => {
    expect(TRANSPARENT_TILE_DATA_URI.startsWith('data:image/png;base64,')).toBe(true)
    expect(TRANSPARENT_TILE_DATA_URI).toContain('iVBORw0KGgo') // PNG 魔数
  })

  it('shouldFallbackToVector：只有"一张未成功且失败≥8"才回退', () => {
    expect(shouldFallbackToVector({ loaded: 0, errors: 8 })).toBe(true)
    expect(shouldFallbackToVector({ loaded: 0, errors: 99 })).toBe(true)
    // 少量 404（边缘越界是常态）绝不回退
    expect(shouldFallbackToVector({ loaded: 0, errors: 7 })).toBe(false)
    // 只要有一张成功，即使失败很多也不整体回退
    expect(shouldFallbackToVector({ loaded: 1, errors: 100 })).toBe(false)
    expect(shouldFallbackToVector({ loaded: 0, errors: 0 })).toBe(false)
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

describe('瓦片底图常显标签（zoom 阈值 / 碰撞 / 上限 / 优先级）', () => {
  const label = (name: string, type: string | undefined, x: number, y: number) => ({
    id: name,
    name,
    type,
    x,
    y,
  })
  const viewport = { width: 800, height: 600 }

  it('labelZoomForType：村 ≥12、学校 ≥13、其它类型永不常显', () => {
    expect(labelZoomForType('village')).toBe(12)
    expect(labelZoomForType('school')).toBe(13)
    expect(labelZoomForType('project')).toBe(Number.POSITIVE_INFINITY)
    expect(labelZoomForType(undefined)).toBe(Number.POSITIVE_INFINITY)
    expect(labelZoomForType('')).toBe(Number.POSITIVE_INFINITY)
    expect(LABEL_MIN_ZOOM_VILLAGE).toBe(12)
    expect(LABEL_MIN_ZOOM_SCHOOL).toBe(13)
    expect(LABEL_MAX_COUNT).toBe(120)
    expect(LABEL_CELL_WIDTH).toBe(64)
    expect(LABEL_CELL_HEIGHT).toBe(20)
  })

  it('z11 不常显任何标签；z12 只常显村；z13 村与学校都常显', () => {
    const labels = [
      label('甲村', 'village', 100, 100),
      label('乙小学', 'school', 300, 100),
      label('丙项目', 'project', 500, 100),
    ]
    expect(selectVisibleLabels(labels, 11, viewport)).toEqual([])
    expect(selectVisibleLabels(labels, 12, viewport).map((l) => l.name)).toEqual(['甲村'])
    expect(
      selectVisibleLabels(labels, 13, viewport)
        .map((l) => l.name)
        .sort()
    ).toEqual(['乙小学', '甲村'].sort())
    // 学校在 z12 不提前出现
    expect(selectVisibleLabels([label('乙小学', 'school', 10, 10)], 12, viewport)).toEqual([])
  })

  it('碰撞：同一 64×20 格只保留一个，学校优先于村（即使村更近中心）', () => {
    const labels = [label('甲村', 'village', 400, 300), label('乙小学', 'school', 405, 302)]
    expect(selectVisibleLabels(labels, 13, viewport).map((l) => l.name)).toEqual(['乙小学'])
  })

  it('碰撞：同类型按到视野中心距离近者优先', () => {
    const labels = [label('远村', 'village', 395, 300), label('近村', 'village', 401, 300)]
    // 两点同属一格 (6,15)，中心 (400,300) → 近村更近
    expect(selectVisibleLabels(labels, 12, viewport).map((l) => l.name)).toEqual(['近村'])
  })

  it('上限：默认 120，可用 opts.maxLabels 收窄（含 0）', () => {
    const many = Array.from({ length: 200 }, (_, i) =>
      label(`村${i}`, 'village', (i % 10) * 70, Math.floor(i / 10) * 25)
    )
    expect(selectVisibleLabels(many, 12, viewport)).toHaveLength(LABEL_MAX_COUNT)
    expect(selectVisibleLabels(many, 12, viewport, { maxLabels: 5 })).toHaveLength(5)
    expect(selectVisibleLabels(many, 12, viewport, { maxLabels: 0 })).toHaveLength(0)
  })

  it('视野外的点不参与；opts.margin 可放宽容差', () => {
    const labels = [
      label('左外', 'village', -5, 100),
      label('下外', 'village', 100, 605),
      label('内', 'village', 200, 200),
    ]
    expect(selectVisibleLabels(labels, 12, viewport).map((l) => l.name)).toEqual(['内'])
    expect(
      selectVisibleLabels(labels, 12, viewport, { margin: 16 })
        .map((l) => l.name)
        .sort()
    ).toEqual(['下外', '内', '左外'].sort())
  })

  it('格尺寸可覆盖：默认同格的两点，缩小格宽后不再互斥', () => {
    const labels = [label('甲', 'village', 100, 100), label('乙', 'village', 110, 100)]
    expect(selectVisibleLabels(labels, 12, viewport)).toHaveLength(1)
    expect(selectVisibleLabels(labels, 12, viewport, { cellWidth: 4 })).toHaveLength(2)
    // 格高覆盖：纵向两点默认不同格（y/20 → 4 与 5），拉高格高到 40 后同格互斥
    const vertical = [label('上', 'village', 100, 85), label('下', 'village', 100, 100)]
    expect(selectVisibleLabels(vertical, 12, viewport)).toHaveLength(2)
    expect(selectVisibleLabels(vertical, 12, viewport, { cellHeight: 40 })).toHaveLength(1)
  })

  it('结果顺序稳定：学校优先，其次按中心距离由近到远', () => {
    const labels = [
      label('远村', 'village', 10, 10),
      label('近村', 'village', 400, 300),
      label('学校', 'school', 790, 590),
    ]
    expect(selectVisibleLabels(labels, 13, viewport).map((l) => l.name)).toEqual([
      '学校',
      '近村',
      '远村',
    ])
  })

  it('空输入 / 空视口尺寸安全', () => {
    expect(selectVisibleLabels([], 13, viewport)).toEqual([])
    expect(selectVisibleLabels([label('甲村', 'village', 10, 10)], 13, { width: 0, height: 0 })).toEqual(
      []
    )
  })
})
