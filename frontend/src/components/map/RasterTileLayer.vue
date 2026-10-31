<template>
  <div class="map-raster-layer" :style="{ height: height }">
    <div ref="containerRef" class="map-raster-canvas" />

    <div v-if="noticeText" class="map-raster-notice" role="alert">
      <span class="map-raster-notice-text">{{ noticeText }}</span>
      <button class="map-raster-fallback" @click="handleFallback">返回矢量视图</button>
    </div>

    <div v-if="partialCoverageText" class="map-raster-partial">{{ partialCoverageText }}</div>

    <div v-if="gcj02" class="map-raster-gcj02">{{ GCJ02_HINT }}</div>

    <!-- 右侧图例 / 图注：符号说明 + 当前覆盖信息 + 地图数据署名 -->
    <aside v-if="isTileMapUsable(tileInfo)" class="map-raster-legend" aria-label="地图图例">
      <div class="legend-head">
        <span class="legend-title">图例</span>
        <button class="legend-toggle" @click="legendOpen = !legendOpen">
          {{ legendOpen ? '收起' : '展开' }}
        </button>
      </div>
      <template v-if="legendOpen">
        <ul class="legend-items">
          <li><i class="legend-swatch legend-swatch--village" />帮扶村（z≥12 常显名称）</li>
          <li><i class="legend-swatch legend-swatch--school" />学校（z≥13 常显名称）</li>
          <li><i class="legend-swatch legend-swatch--place" />乡镇 / 县市（底图注记）</li>
          <li><i class="legend-swatch legend-swatch--road" />道路 / 水系 / 行政界</li>
        </ul>
        <dl class="legend-meta">
          <div>
            <dt>瓦片</dt>
            <dd>{{ coverageSummary }}</dd>
          </div>
          <div>
            <dt>层级</dt>
            <dd>{{ zoomSummary }}</dd>
          </div>
          <div>
            <dt>来源</dt>
            <dd>{{ sourceLabel }}</dd>
          </div>
        </dl>
        <p class="legend-attribution">{{ attributionText }}</p>
      </template>
    </aside>

    <button
      v-if="isTileMapUsable(tileInfo) && !overviewMissing"
      class="map-raster-province"
      title="缩放到全省范围"
      @click="fitProvince"
    >
      全省视图
    </button>

    <div v-if="overviewMissing" class="map-raster-warn" role="alert">
      当前瓦片缺少 z5–8 全省概览，最小只能看到 z{{ minAvailableZoom }}；请导入
      <code>guizhou-overview_z5-8.zip</code>（0.8MB）后即可缩放查看全省。
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * 离线栅格瓦片底图（Leaflet）
 *
 * 数据源只允许本机后端 `/api/v1/map/tiles/{z}/{x}/{y}.png`，不产生任何外网请求。
 * 该端点无需鉴权（backend/app/api/v1/map.py serve_tile），因此 TileLayer 直接以
 * <img> 方式加载，不经过 axios、不拼接 token。
 *
 * 回退语义（关键，勿退回"单张 404 即回退"）：
 * - 视野超出预置 bbox 时 Leaflet 边缘请求必然 404，这是**常态**：
 *   tileerror 只累加计数，且 `errorTileUrl` 让边缘瓦片渲染为透明像素；
 * - 仅当"一张都没成功且累计失败 ≥8 张"（`shouldFallbackToVector`）才 emit('tile-error')
 *   让父页面回退矢量；5s 看门狗兜底"视口只请求了很少瓦片却全 404"的情况；
 * - 有成功瓦片但存在失败时，仅显示非阻塞提示「部分区域超出预置瓦片范围」。
 *
 * 视野约束：`maxBounds`（bbox 外扩 0.05°）+ `maxBoundsViscosity=1` 防止拖出覆盖范围，
 * 初始视图用 `fitBounds` 贴合 bbox（固定 zoom 7 在 1080p 下视野约 21° 宽 > 贵州 6°，
 * 必然请求到无瓦片区）。
 *
 * 本组件仅由地图页按需懒加载（defineAsyncComponent），默认视图仍是 ECharts 矢量地图。
 */
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import type { TileInfo } from '@/api/map'
import { chartColor, chartColorPrimary } from '@/utils/chartColors'
import {
  GCJ02_HINT,
  LABEL_MIN_ZOOM_SCHOOL,
  PARTIAL_COVERAGE_HINT,
  TILE_BOUNDS_PADDING_DEGREES,
  TILE_FALLBACK_WATCHDOG_MS,
  TILE_FIT_MAX_ZOOM,
  TILE_LOAD_FAILED_HINT,
  TILE_URL_TEMPLATE,
  TRANSPARENT_TILE_DATA_URI,
  convertMarkersForTiles,
  isGcj02,
  isTileMapUsable,
  nearestNativeZoom,
  selectVisibleLabels,
  shouldFallbackToVector,
  tileAttribution,
  tileCoverageBbox,
  tileCoverageBounds,
  tileInfoHint,
  tileOverviewMissing,
  tileViewBounds,
  tileZoomLimits,
  formatTileBytes,
  toDisplayCoord,
} from '@/utils/mapTiles'

/**
 * 支持「稀疏原生层级」的瓦片层。
 * Leaflet 默认只会在 minNativeZoom~maxNativeZoom 连续区间内取图；
 * 本子类改为始终取最接近的可用户层级，补齐 z12/z13 这类空洞。
 */
type NativeZoomTileLayerOptions = L.TileLayerOptions & { nativeZooms?: number[] }
type TileLayerConstructor = new (url: string, options?: NativeZoomTileLayerOptions) => L.TileLayer
type ExtendableTileLayer = {
  extend(props: Record<string, unknown>): TileLayerConstructor
}
const NearestNativeTileLayer = (L.TileLayer as unknown as ExtendableTileLayer).extend({
  _clampZoom(this: { options: NativeZoomTileLayerOptions }, zoom: number): number {
    return nearestNativeZoom(this.options.nativeZooms, zoom)
  },
})

/** 瓦片底图上叠加的标注点（与 ECharts 矢量视图使用同一批数据） */
interface TileMapMarker {
  id?: number | string
  name: string
  lng: number
  lat: number
  type?: string
}

/** 标签显示模式：hover=仅悬停；small/large=常显（字号两档） */
type LabelMode = 'hover' | 'small' | 'large'

/** 标注点条目：保留 circle 以便缩放/移动后按需重绑标签 */
interface MarkerEntry {
  marker: TileMapMarker
  circle: L.CircleMarker
  labelMode: LabelMode | null
}

const props = withDefaults(
  defineProps<{
    /**
     * 地图中心（WGS-84，GCJ-02 底图时组件内部自动修正）。
     * 缺省时停在瓦片覆盖范围（fitBounds），避免固定 zoom 7 把视野拉出 bbox。
     */
    center?: { lng: number; lat: number } | null
    zoom?: number
    height?: string
    visible?: boolean
    markers?: TileMapMarker[]
    /** `/map/tile-info` 归一化结果 */
    tileInfo?: TileInfo | null
    /** 全 404 看门狗时长（毫秒），默认 5s；测试可注入短值 */
    watchdogMs?: number
  }>(),
  {
    center: null,
    zoom: 7,
    height: '500px',
    visible: true,
    markers: () => [],
    tileInfo: null,
    watchdogMs: TILE_FALLBACK_WATCHDOG_MS,
  }
)

const emit = defineEmits<{
  (e: 'marker-click', marker: TileMapMarker): void
  (e: 'tile-error'): void
  (e: 'fallback'): void
}>()

const containerRef = ref<HTMLDivElement>()
/** 是否已请求父页面回退矢量（保证只通知一次） */
const fallbackRequested = ref(false)
/** 成功加载的瓦片张数（用于区分"边缘少量 404"与"整屏加载不出来"） */
const loadedTiles = ref(0)
/** 加载失败的瓦片张数（404 计数） */
const failedTiles = ref(0)

let map: L.Map | null = null
let tileLayer: L.TileLayer | null = null
let markerLayer: L.LayerGroup | null = null
let watchdogTimer: ReturnType<typeof setTimeout> | null = null
/** 当前标注点（点击仍是 marker-click；标签按 zoom/位置从这些条目里挑选） */
let markerEntries: MarkerEntry[] = []

const gcj02 = computed(() => isGcj02(props.tileInfo?.manifest))
const noticeText = computed(() =>
  fallbackRequested.value ? TILE_LOAD_FAILED_HINT : tileInfoHint(props.tileInfo)
)
/** 有成功瓦片但存在 404 → 非阻塞提示（不回退） */
const partialCoverageText = computed(() =>
  loadedTiles.value > 0 && failedTiles.value > 0 ? PARTIAL_COVERAGE_HINT : ''
)

/** 图例展开/收起（默认展开：用户要求“侧面有标注”） */
const legendOpen = ref(true)
/** 是否缺 z5–8 全省概览（只导入 z13/z14 时为 true） */
const overviewMissing = computed(() => tileOverviewMissing(props.tileInfo))
/** 当前最低可用层级（缺概览时用于提示“最小只能看到 z13”） */
const minAvailableZoom = computed(() => {
  const levels = (props.tileInfo?.zoomLevels ?? []).filter((level) => Number.isFinite(level))
  return levels.length > 0 ? Math.min(...levels) : TILE_FIT_MAX_ZOOM + 1
})
/** 图例：瓦片数量与体积 */
const coverageSummary = computed(() => {
  const info = props.tileInfo
  return `${info?.tileCount ?? 0} 张 · ${formatTileBytes(info?.totalBytes ?? 0)}`
})
/** 图例：层级范围（稀疏层级逐档列出，如 5–8 / 14） */
const zoomSummary = computed(() => {
  const levels = [...(props.tileInfo?.zoomLevels ?? [])].filter((level) => Number.isFinite(level))
  if (levels.length === 0) return '—'
  return levels.join(' / ')
})
/** 图例：瓦片来源 */
const sourceLabel = computed(() => {
  const source = props.tileInfo?.source
  if (source === 'env') return '安装包内置 / 环境指定'
  if (source === 'meipass') return '程序内置'
  if (source === 'dev') return '开发目录'
  return '本机瓦片目录'
})
/** 图例：地图数据署名（OSM/ODbL 等） */
const attributionText = computed(() => tileAttribution(props.tileInfo?.manifest))

function markerColor(type?: string): string {
  if (type === 'school') return chartColor('success')
  if (type === 'project') return chartColor('warning')
  return chartColorPrimary()
}

/** 瓦片加载成功计数：只要有一张成功就说明本机瓦片链路可用 */
function handleTileLoad() {
  loadedTiles.value += 1
}

/**
 * 单张瓦片失败只累加计数，绝不立即回退。
 * 视野超出预置 bbox 时边缘 404 是常态；只有"一张都未成功且失败达阈值"才回退。
 */
function handleTileError() {
  failedTiles.value += 1
  if (shouldFallbackToVector({ loaded: loadedTiles.value, errors: failedTiles.value })) {
    requestFallback()
  }
}

/** 请求父页面回退矢量视图（同一实例只发一次） */
function requestFallback() {
  if (fallbackRequested.value) return
  fallbackRequested.value = true
  emit('tile-error')
}

function handleFallback() {
  emit('fallback')
}

function stopWatchdog() {
  if (watchdogTimer !== null) {
    clearTimeout(watchdogTimer)
    watchdogTimer = null
  }
}

/** 看门狗：覆盖"视口请求数不足阈值但全都 404"的白屏场景 */
function startWatchdog() {
  stopWatchdog()
  watchdogTimer = setTimeout(() => {
    if (shouldFallbackToVector({ loaded: loadedTiles.value, errors: failedTiles.value })) {
      requestFallback()
    }
  }, props.watchdogMs)
}

/** 覆盖范围中心（bbox 已是底图坐标系，不再做 GCJ 偏移） */
function bboxCenter(): [number, number] {
  const [[south, west], [north, east]] = tileCoverageBounds(props.tileInfo)
  return [(south + north) / 2, (west + east) / 2]
}

/** 视图中心：显式 center 走坐标系修正，缺省回落到 bbox 中心 */
function displayCenter(): [number, number] {
  const center = props.center
  if (!center) return bboxCenter()
  const converted = toDisplayCoord(center, gcj02.value)
  return [converted.lat, converted.lng]
}

/** 显式 center 是否落在瓦片覆盖范围内（决定 fitBounds 后是否 panTo） */
function centerWithinBbox(info: TileInfo): boolean {
  const center = props.center
  if (!center) return false
  const [minLon, minLat, maxLon, maxLat] = tileCoverageBbox(info)
  return (
    center.lng >= minLon && center.lng <= maxLon && center.lat >= minLat && center.lat <= maxLat
  )
}

/** 覆盖范围外扩 padding，用于 maxBounds（防止拖出无瓦片区） */
function expandBounds(
  bounds: [[number, number], [number, number]]
): [[number, number], [number, number]] {
  const [[south, west], [north, east]] = bounds
  const pad = TILE_BOUNDS_PADDING_DEGREES
  return [
    [south - pad, west - pad],
    [north + pad, east + pad],
  ]
}

/** 用瓦片信息创建地图（仅在 tileInfo 可用时调用） */
function initMap(info: TileInfo) {
  const bounds = tileCoverageBounds(info)
  // 视图范围 = 已导入覆盖范围 ∪ 全省范围：只导入市州包时也不把视野锁死在该市州，
  // 否则缩放到全省会被 maxBounds 弹回（现场“缩放看不到全貌”的根因之一）。
  const viewBounds = tileViewBounds(info)
  // 修复缩放失效：显示层级不得等于瓦片原生层级。单层 z14 包的原始
  // minZoom=maxZoom=14 会让滚轮/双击/按钮全部无效；这里改为可交互区间 +
  // 原生层级分离，由 Leaflet 自动降采样/超采样。
  const { minZoom, maxZoom, minNativeZoom, maxNativeZoom } = tileZoomLimits(info)

  map = L.map(containerRef.value as HTMLDivElement, {
    center: displayCenter(),
    zoom: props.zoom,
    minZoom,
    maxZoom,
    // 视野不得拖出「覆盖范围 ∪ 全省」，外扩 0.05° 吸收边缘
    maxBounds: expandBounds(viewBounds),
    maxBoundsViscosity: 1.0,
    worldCopyJump: false,
    attributionControl: true,
    // 显式声明全部缩放交互，避免容器/全局样式或未来配置改动静默禁用
    zoomControl: true,
    scrollWheelZoom: true,
    doubleClickZoom: true,
    touchZoom: true,
    boxZoom: true,
    keyboard: true,
  })
  // 比例尺（图注的一部分）：地图缩放时自动更新
  L.control.scale({ position: 'bottomleft', imperial: false, maxWidth: 140 }).addTo(map)
  tileLayer = new NearestNativeTileLayer(TILE_URL_TEMPLATE, {
    minZoom,
    maxZoom,
    // 瓦片真实层级：显示层级超出此范围时由 Leaflet 缩放边缘瓦片
    minNativeZoom,
    maxNativeZoom,
    // 稀疏层级支持：缺层时取最近的已有瓦片，而不是向空目录发请求
    nativeZooms: [...info.zoomLevels],
    noWrap: true,
    // 只在覆盖范围内请求瓦片，边缘不再向无瓦片区要图
    bounds,
    // 边缘 404 渲染为透明像素，不显示破图
    errorTileUrl: TRANSPARENT_TILE_DATA_URI,
    // OSM/ODbL 衍生底图必须显示署名（见 utils/mapTiles.tileAttribution）
    attribution: tileAttribution(info.manifest),
  })
  tileLayer.on('tileerror', handleTileError)
  tileLayer.on('tileload', handleTileLoad)
  tileLayer.addTo(map)
  // 常显标签随缩放档位变化 / 拖动后像素位置变化而重算
  map.on('zoomend', refreshLabels)
  map.on('moveend', refreshLabels)
  renderMarkers()
  // 初始视野贴合预置范围（固定 zoom 7 在 1080p 下视野约 21° 宽 > 贵州 6°，必请求无瓦区）
  map.fitBounds(bounds, { padding: [16, 16], maxZoom: TILE_FIT_MAX_ZOOM })
  if (centerWithinBbox(info)) {
    map.panTo(displayCenter())
  }
  map.invalidateSize()
  startWatchdog()
}

/** 「全省视图」：缩放到覆盖范围 ∪ 全省，用户随时能看全貌（缺概览时仍会提示补装） */
function fitProvince() {
  if (!map) return
  map.fitBounds(tileViewBounds(props.tileInfo), {
    padding: [16, 16],
    maxZoom: TILE_FIT_MAX_ZOOM,
  })
}

/**
 * 常显标签（方案 A）：z≥12 帮扶村、z≥13 学校**直接显示名称**（用户诉求），
 * z<12 或未被选中的仍只悬停显示。
 *
 * - 选谁常显由纯函数 `selectVisibleLabels` 决定（像素格碰撞 64×20 + 学校优先 + 距离中心优先 + 上限 120）；
 * - 标签用 permanent tooltip 且 `interactive:false`（配 CSS pointer-events:none），
 *   因此不拦截地图拖拽；标注点本身的点击仍走既有 `marker-click`；
 * - 仅在显示模式变化时才重新 bindTooltip，避免拖动时对上百标注反复绑定。
 */
function applyLabelMode(entry: MarkerEntry, mode: LabelMode) {
  if (entry.labelMode === mode) return
  entry.labelMode = mode
  if (mode === 'hover') {
    entry.circle.bindTooltip(entry.marker.name)
    return
  }
  entry.circle.bindTooltip(entry.marker.name, {
    permanent: true,
    direction: 'right',
    offset: [8, 0],
    interactive: false,
    className: mode === 'large' ? 'map-raster-label map-raster-label--lg' : 'map-raster-label',
  })
}

/** 按当前 zoom/视野重算常显标签（缩放、拖动、标注变化时调用） */
function refreshLabels() {
  const currentMap = map
  if (!currentMap) return
  const zoom = currentMap.getZoom()
  const size = currentMap.getSize()
  const selected = selectVisibleLabels(
    markerEntries.map(({ marker }) => {
      const point = currentMap.latLngToContainerPoint([marker.lat, marker.lng])
      return { id: marker.id, name: marker.name, type: marker.type, x: point.x, y: point.y }
    }),
    zoom,
    { width: size.x, height: size.y }
  )
  const visibleKeys = new Set(selected.map((label) => String(label.id ?? label.name)))
  // 字号两档：z12 小字、z≥13 大字（学校常显起点）
  const large = zoom >= LABEL_MIN_ZOOM_SCHOOL
  for (const entry of markerEntries) {
    const key = String(entry.marker.id ?? entry.marker.name)
    if (!visibleKeys.has(key)) {
      applyLabelMode(entry, 'hover')
      continue
    }
    applyLabelMode(entry, large ? 'large' : 'small')
  }
}

function renderMarkers() {
  if (!map) return
  if (!markerLayer) markerLayer = L.layerGroup().addTo(map)
  const group = markerLayer
  group.clearLayers()
  markerEntries = []
  convertMarkersForTiles(props.markers, gcj02.value).forEach((marker) => {
    const point = L.circleMarker([marker.lat, marker.lng], {
      radius: 6,
      weight: 1,
      color: chartColor('info'),
      fillColor: markerColor(marker.type),
      fillOpacity: 0.9,
    })
    point.on('click', () => emit('marker-click', marker))
    point.addTo(group)
    markerEntries.push({ marker, circle: point, labelMode: null })
  })
  refreshLabels()
}

function applyView() {
  if (!map) return
  map.setView(displayCenter(), props.zoom)
}

function destroyMap() {
  stopWatchdog()
  if (tileLayer) {
    tileLayer.off('tileerror', handleTileError)
    tileLayer.off('tileload', handleTileLoad)
    tileLayer.remove()
    tileLayer = null
  }
  if (markerLayer) {
    markerLayer.remove()
    markerLayer = null
  }
  if (map) {
    map.off('zoomend', refreshLabels)
    map.off('moveend', refreshLabels)
    map.remove()
    map = null
  }
  markerEntries = []
  fallbackRequested.value = false
  loadedTiles.value = 0
  failedTiles.value = 0
}

function syncMap() {
  const info = props.tileInfo
  if (!props.visible || !isTileMapUsable(info)) {
    destroyMap()
    return
  }
  if (map) return
  initMap(info)
}

watch(
  () => props.visible,
  () => syncMap()
)
watch(
  () => props.tileInfo,
  () => syncMap()
)
watch(
  () => props.center,
  () => applyView(),
  { deep: true }
)
watch(
  () => props.zoom,
  () => applyView()
)
watch(
  () => props.markers,
  () => renderMarkers(),
  { deep: true }
)
watch(
  () => gcj02.value,
  () => renderMarkers()
)

onMounted(async () => {
  await nextTick()
  syncMap()
})

onBeforeUnmount(() => {
  destroyMap()
})
</script>

<style scoped>
.map-raster-layer {
  position: relative;
  width: 100%;
  min-height: 400px;
  border: 1px solid var(--color-border-light);
  border-radius: 4px;
  overflow: hidden;
  background: var(--color-bg-hover);
}

.map-raster-canvas {
  width: 100%;
  height: 100%;
  min-height: 400px;
}

.map-raster-notice {
  position: absolute;
  top: 16px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 900;
  display: flex;
  align-items: center;
  gap: 12px;
  max-width: 80%;
  padding: 10px 16px;
  border: 1px solid var(--color-warning);
  border-radius: 6px;
  background: var(--color-bg-card);
  color: var(--color-text-primary);
  font-size: 13px;
  box-shadow: var(--shadow-card);
}

/* 非阻塞提示：边缘越界 404 属正常，不遮挡地图、不触发回退 */
.map-raster-partial {
  position: absolute;
  left: 12px;
  bottom: 12px;
  z-index: 900;
  padding: 6px 10px;
  border-radius: 4px;
  background: var(--color-bg-card);
  color: var(--color-text-regular);
  font-size: 12px;
  pointer-events: none;
}

/* 提示条内的"返回矢量视图"为文字链接样式（地图浮层内不引入按钮组件） */
.map-raster-fallback {
  flex-shrink: 0;
  padding: 0;
  border: none;
  background: none;
  color: var(--color-primary);
  font-size: 13px;
  text-decoration: underline;
  cursor: pointer;
}

.map-raster-fallback:hover {
  color: var(--color-primary-dark-1);
}

.map-raster-gcj02 {
  position: absolute;
  right: 12px;
  bottom: 12px;
  z-index: 900;
  padding: 6px 10px;
  border-radius: 4px;
  background: var(--color-bg-card);
  color: var(--color-text-regular);
  font-size: 12px;
}

/* 常显标签（Leaflet 自己创建 tooltip DOM，故用 :deep 穿透 scoped 作用域）
 * 颜色全部走 design token；pointer-events:none 保证标签不拦截地图拖拽。 */
:deep(.map-raster-label.leaflet-tooltip) {
  padding: 1px 4px;
  border: 1px solid var(--color-border-light);
  border-radius: 3px;
  background: var(--color-bg-card);
  color: var(--color-text-primary);
  font-size: var(--font-size-xs);
  line-height: 1.2;
  white-space: nowrap;
  pointer-events: none;
  box-shadow: none;
}

/* 小三角与标签边框同色，避免出现深色描边 */
:deep(.map-raster-label.leaflet-tooltip-right::before) {
  border-right-color: var(--color-border-light);
}

/* 大字档：z≥13（学校常显起点）时名称更易读 */
:deep(.map-raster-label--lg.leaflet-tooltip) {
  font-size: var(--font-size-sm);
}

/* 右侧图例 / 图注（用户要求“侧面有标注”）：符号说明 + 覆盖信息 + 数据署名 */
.map-raster-legend {
  position: absolute;
  top: 12px;
  right: 12px;
  z-index: 900;
  width: 214px;
  padding: 10px 12px;
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-card);
  background: var(--color-bg-card);
  box-shadow: var(--shadow-card);
  color: var(--color-text-regular);
  font-size: 12px;
  line-height: 1.5;
}

.legend-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}

.legend-title {
  color: var(--color-text-primary);
  font-size: 13px;
  font-weight: 600;
}

.legend-toggle {
  padding: 0;
  border: none;
  background: none;
  color: var(--color-primary);
  font-size: 12px;
  cursor: pointer;
}

.legend-items {
  display: grid;
  gap: 4px;
  margin: 0 0 8px;
  padding: 0;
  list-style: none;
}

.legend-items li {
  display: flex;
  align-items: center;
  gap: 6px;
}

.legend-swatch {
  display: inline-block;
  flex: 0 0 auto;
  width: 10px;
  height: 10px;
  border-radius: 2px;
}

.legend-swatch--village {
  border-radius: 50%;
  background: var(--color-primary);
}

.legend-swatch--school {
  background: var(--color-success);
}

.legend-swatch--place {
  border-radius: 50%;
  background: var(--color-text-secondary);
}

.legend-swatch--road {
  background: var(--color-border-light);
  border: 1px solid var(--color-text-secondary);
}

.legend-meta {
  display: grid;
  gap: 2px;
  margin: 0 0 6px;
}

.legend-meta div {
  display: flex;
  justify-content: space-between;
  gap: 8px;
}

.legend-meta dt {
  color: var(--color-text-secondary);
}

.legend-meta dd {
  margin: 0;
  color: var(--color-text-primary);
  text-align: right;
  word-break: break-all;
}

.legend-attribution {
  margin: 0;
  color: var(--color-text-secondary);
  font-size: 11px;
  line-height: 1.4;
}

/* 「全省视图」快捷按钮：图例下方/右下角，随时缩放到全貌 */
.map-raster-province {
  position: absolute;
  right: 12px;
  bottom: 44px;
  z-index: 900;
  padding: 6px 12px;
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-card);
  background: var(--color-bg-card);
  color: var(--color-primary);
  font-size: 12px;
  cursor: pointer;
  box-shadow: var(--shadow-card);
}

.map-raster-province:hover {
  background: var(--color-bg-hover);
}

/* 缺概览瓦片：明确告知补装包，避免“缩放没反应”被误判为故障 */
.map-raster-warn {
  position: absolute;
  left: 50%;
  bottom: 12px;
  z-index: 900;
  max-width: 78%;
  padding: 6px 10px;
  border-radius: 4px;
  background: var(--color-warning-light-9);
  color: var(--color-text-primary);
  font-size: 12px;
  transform: translateX(-50%);
}

.map-raster-warn code {
  padding: 0 3px;
  border-radius: 3px;
  background: var(--color-bg-hover);
  font-family: var(--font-family-mono);
}
</style>
