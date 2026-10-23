<template>
  <div class="map-raster-layer" :style="{ height: height }">
    <div ref="containerRef" class="map-raster-canvas" />

    <div v-if="noticeText" class="map-raster-notice" role="alert">
      <span class="map-raster-notice-text">{{ noticeText }}</span>
      <button class="map-raster-fallback" @click="handleFallback">返回矢量视图</button>
    </div>

    <div v-if="gcj02" class="map-raster-gcj02">{{ GCJ02_HINT }}</div>
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
 * 失败语义：
 * - `tile-info` 不可用 → 不创建地图，显示中文说明 + 返回矢量视图按钮
 * - Leaflet `tileerror`（后端 404）→ 中文说明 + emit('tile-error')，由父页面回退矢量视图
 * - GCJ-02 底图 → 显示偏移提示，标注点自动做 WGS-84 → GCJ-02 修正
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
  TILE_LOAD_FAILED_HINT,
  TILE_URL_TEMPLATE,
  convertMarkersForTiles,
  isGcj02,
  isTileMapUsable,
  tileAttribution,
  tileInfoHint,
  toDisplayCoord,
} from '@/utils/mapTiles'

/** 瓦片底图上叠加的标注点（与 ECharts 矢量视图使用同一批数据） */
interface TileMapMarker {
  id?: number | string
  name: string
  lng: number
  lat: number
  type?: string
}

const props = withDefaults(
  defineProps<{
    /** 地图中心（WGS-84，GCJ-02 底图时组件内部自动修正） */
    center?: { lng: number; lat: number }
    zoom?: number
    height?: string
    visible?: boolean
    markers?: TileMapMarker[]
    /** `/map/tile-info` 归一化结果 */
    tileInfo?: TileInfo | null
  }>(),
  {
    center: () => ({ lng: 106.71, lat: 26.65 }),
    zoom: 7,
    height: '500px',
    visible: true,
    markers: () => [],
    tileInfo: null,
  }
)

const emit = defineEmits<{
  (e: 'marker-click', marker: TileMapMarker): void
  (e: 'tile-error'): void
  (e: 'fallback'): void
}>()

const containerRef = ref<HTMLDivElement>()
const tileFailed = ref(false)

let map: L.Map | null = null
let tileLayer: L.TileLayer | null = null
let markerLayer: L.LayerGroup | null = null

const gcj02 = computed(() => isGcj02(props.tileInfo?.manifest))
const noticeText = computed(() =>
  tileFailed.value ? TILE_LOAD_FAILED_HINT : tileInfoHint(props.tileInfo)
)

function markerColor(type?: string): string {
  if (type === 'school') return chartColor('success')
  if (type === 'project') return chartColor('warning')
  return chartColorPrimary()
}

/** 瓦片错误只处理一次：连续多张 404 不应刷屏 */
function handleTileError() {
  if (tileFailed.value) return
  tileFailed.value = true
  emit('tile-error')
}

function handleFallback() {
  emit('fallback')
}

/** 视图中心（已按底图坐标系修正：GCJ-02 底图与标注点走同一转换） */
function displayCenter(): [number, number] {
  const center = toDisplayCoord(props.center, gcj02.value)
  return [center.lat, center.lng]
}

/** 用瓦片信息创建地图（仅在 tileInfo 可用时调用，缩放级别必然非空） */
function initMap(info: TileInfo) {
  map = L.map(containerRef.value as HTMLDivElement, {
    center: displayCenter(),
    zoom: props.zoom,
    minZoom: info.zoomLevels[0],
    maxZoom: info.zoomLevels[info.zoomLevels.length - 1],
    attributionControl: true,
  })
  tileLayer = L.tileLayer(TILE_URL_TEMPLATE, {
    minZoom: info.zoomLevels[0],
    maxZoom: info.zoomLevels[info.zoomLevels.length - 1],
    noWrap: true,
    // OSM/ODbL 衍生底图必须显示署名（见 utils/mapTiles.tileAttribution）
    attribution: tileAttribution(info.manifest),
  })
  tileLayer.on('tileerror', handleTileError)
  tileLayer.addTo(map)
  renderMarkers()
  map.invalidateSize()
}

function renderMarkers() {
  if (!map) return
  if (!markerLayer) markerLayer = L.layerGroup().addTo(map)
  const group = markerLayer
  group.clearLayers()
  convertMarkersForTiles(props.markers, gcj02.value).forEach((marker) => {
    const point = L.circleMarker([marker.lat, marker.lng], {
      radius: 6,
      weight: 1,
      color: chartColor('info'),
      fillColor: markerColor(marker.type),
      fillOpacity: 0.9,
    })
    point.bindTooltip(marker.name)
    point.on('click', () => emit('marker-click', marker))
    point.addTo(group)
  })
}

function applyView() {
  if (!map) return
  map.setView(displayCenter(), props.zoom)
}

function destroyMap() {
  if (tileLayer) {
    tileLayer.off('tileerror', handleTileError)
    tileLayer.remove()
    tileLayer = null
  }
  if (markerLayer) {
    markerLayer.remove()
    markerLayer = null
  }
  if (map) {
    map.remove()
    map = null
  }
  tileFailed.value = false
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
  () => [props.center.lng, props.center.lat],
  () => applyView()
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
</style>
