<template>
  <div ref="chartRef" class="offline-map-container" :style="{ width: width, height: height }" />
</template>

<script setup lang="ts">
/**
 * 离线地图组件 — 贵州省行政区划矢量地图
 *
 * 使用 ECharts 渲染真实地理边界的贵州省地图。
 * - 88 个县市区：虚线边框
 * - 9 个地州市：按 prefecture 分组着色
 * - 支持标记点（村庄、学校等）、路线连线、出发点标注
 */
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { logger } from '@/utils/logger'
import { chartColor, chartColorPrimary } from '@/utils/chartColors'
import echarts from '@/utils/echarts'

interface Marker {
  lng: number
  lat: number
  name: string
  type: string
  value?: number
}

interface RegionData {
  name: string
  value: number
}

interface RouteLine {
  coords: [number, number][]
  label: string
}

const props = withDefaults(
  defineProps<{
    width?: string
    height?: string
    markers?: Marker[]
    regionData?: RegionData[]
    routeLines?: RouteLine[]
    originMarker?: { lng: number; lat: number } | null
    viewLevel?: string
    geoJsonData?: object
  }>(),
  {
    width: '100%',
    height: '500px',
    markers: () => [],
    regionData: () => [],
    routeLines: () => [],
    originMarker: null,
    viewLevel: 'province',
    geoJsonData: undefined,
  }
)

const emit = defineEmits<{
  (
    e: 'region-click',
    region: { name: string; lng?: number | null; lat?: number | null; code?: string }
  ): void
  (e: 'marker-click', marker: Marker): void
}>()

const chartRef = ref<HTMLDivElement>()
let chart: echarts.ECharts | null = null
let geoJson: object | null = null

onMounted(async () => {
  if (props.geoJsonData) {
    geoJson = props.geoJsonData
  } else {
    try {
      const module = await import('@/assets/geo/guizhou.json')
      geoJson = module.default || module
    } catch {
      logger.warn('[OfflineMap] 贵州 GeoJSON 加载失败，使用空地图')
      geoJson = { type: 'FeatureCollection', features: [] }
    }
  }

  await nextTick()
  initChart()
})

function initChart() {
  if (!chartRef.value || !geoJson) return

  chart = echarts.init(chartRef.value)
  echarts.registerMap('guizhou', geoJson as any)

  renderMap()

  // Click on map regions (counties) — emit with lng/lat
  chart.on('click', 'series', (params: any) => {
    if (params.seriesType === 'scatter' || params.seriesType === 'effectScatter') {
      const marker = props.markers.find((m) => m.name === params.name)
      if (marker) emit('marker-click', marker)
    } else if (params.seriesType === 'map') {
      // 优先从 GeoJSON cp 获取中心点；若无则从点击像素转换
      const cp = params.data?.cp || null
      if (cp && cp[0] != null && cp[1] != null) {
        emit('region-click', { name: params.name, lng: cp[0], lat: cp[1] })
      } else if (chart && params.event) {
        const px = [params.event.offsetX, params.event.offsetY]
        const point = chart.convertFromPixel({ geoIndex: 0 }, px)
        if (point && !isNaN(point[0]) && !isNaN(point[1])) {
          emit('region-click', { name: params.name, lng: point[0], lat: point[1] })
        }
      }
    }
  })
  // Click on map background (not on markers/regions) — emit coordinates
  chart.getZr().on('click', (params: any) => {
    if (params.target) return // skip clicks on series elements (handled above)
    if (!chart) return
    const point = chart.convertFromPixel({ geoIndex: 0 }, [params.offsetX, params.offsetY])
    if (point && !isNaN(point[0]) && !isNaN(point[1])) {
      emit('region-click', { name: '', lng: point[0], lat: point[1] })
    }
  })

  window.addEventListener('resize', handleResize)
}

function renderMap() {
  if (!chart) return

  const features = (geoJson as any)?.features || []

  // Build county → prefecture mapping
  const prefList: string[] = []
  const prefSet = new Set<string>()
  const countyPrefMap: Record<string, string> = {}
  features.forEach((f: any) => {
    const pref = f.properties?.prefecture || ''
    const name = f.properties?.name || ''
    if (pref && !prefSet.has(pref)) {
      prefSet.add(pref)
      prefList.push(pref)
    }
    if (name && pref) countyPrefMap[name] = pref
  })

  // 按 prefecture index 给每个县赋值（用于 series data）
  const mapData = features.map((f: any) => {
    const pref = f.properties?.prefecture || ''
    const idx = prefList.indexOf(pref)
    return { name: f.properties?.name || '', value: idx >= 0 ? idx : 0 }
  })

  // Scatter markers
  const scatterData = props.markers.map((m) => ({
    name: m.name,
    value: [m.lng, m.lat, m.value || 1],
    itemStyle: { color: getMarkerColor(m.type) },
  }))

  // 地州市配色数组（按 prefList 顺序）
  const prefColors = prefList.map((_, i) => {
    const hues = [120, 45, 210, 350, 280, 190, 50, 260, 30]
    return `hsla(${hues[i] || i * 40}, 35%, 85%, 0.7)`
  })

  const option: echarts.EChartsCoreOption = {
    tooltip: {
      trigger: 'item',
      formatter: (params: any) => {
        if (params.seriesType === 'scatter' || params.seriesType === 'effectScatter') {
          const pref = countyPrefMap[params.name] || ''
          const prefLabel = pref ? ` (${pref})` : ''
          return `${params.name}${prefLabel}<br/>类型: 标记点`
        }
        const pref = countyPrefMap[params.name] || ''
        const prefLabel = pref ? `【${pref}】` : ''
        return `${prefLabel}${params.name}`
      },
    },
    visualMap: {
      min: 0,
      max: prefList.length - 1,
      show: false,
      inRange: { color: prefColors },
    },
    geo: {
      map: 'guizhou',
      roam: true,
      zoom: 1.15,
      center: [106.71, 26.65],
      aspectScale: 0.85,
      label: {
        show: true,
        fontSize: 8,
        color: '#555',
      },
      emphasis: {
        focus: 'self',
        label: { show: true, fontSize: 13, fontWeight: 'bold', color: '#222' },
        itemStyle: {
          areaColor: '#ffe082',
          borderColor: '#e65100',
          borderWidth: 2,
        },
      },
      itemStyle: {
        borderColor: '#999',
        borderWidth: 0.5,
        borderType: 'dashed' as any,
        areaColor: '#f8f8f8',
      },
    },
    series: [
      // 县市区层
      {
        name: '帮扶统计',
        type: 'map',
        geoIndex: 0,
        data: props.regionData.length > 0 ? props.regionData : mapData,
        label: { show: false },
      },
      // 标记点
      {
        name: '标记点',
        type: 'scatter',
        coordinateSystem: 'geo',
        data: scatterData,
        symbolSize: (val: any) => Math.min(Math.max((val[2] || 1) * 8, 6), 20),
        label: {
          show: true,
          position: 'right',
          fontSize: 10,
          color: '#333',
          formatter: (p: any) => p.name,
        },
      },
      // 路线线段
      ...(props.routeLines || []).map((line, i) => ({
        name: `路线-${i}`,
        type: 'lines',
        coordinateSystem: 'geo',
        polyline: false,
        data: [{ coords: line.coords }],
        lineStyle: {
          color: chartColor('warning'),
          width: 2,
          type: 'dashed' as const,
          opacity: 0.7,
        },
        effect: {
          show: true,
          period: 6,
          trailLength: 0.3,
          symbol: 'arrow',
          symbolSize: 6,
        },
        label: {
          show: true,
          position: 'middle' as const,
          fontSize: 11,
          color: chartColor('warning'),
          formatter: (_p: any) => line.label,
        },
      })),
      // 出发点标记
      ...(props.originMarker
        ? [
            {
              name: '出发点',
              type: 'effectScatter',
              coordinateSystem: 'geo',
              data: [
                {
                  name: '出发点',
                  value: [props.originMarker.lng, props.originMarker.lat, 1],
                },
              ],
              symbolSize: 16,
              symbol: 'pin',
              itemStyle: { color: chartColor('danger') },
              label: {
                show: true,
                position: 'top' as const,
                fontSize: 12,
                fontWeight: 'bold' as const,
                color: chartColor('danger'),
                formatter: '出发点',
              },
            },
          ]
        : []),
    ],
  }

  chart.setOption(option, true)
}

function getMarkerColor(type: string): string {
  // canvas 无法解析 var()，运行时取 tokens.scss 语义色计算值
  const colorMap: Record<string, string> = {
    village: chartColorPrimary(),
    school: chartColor('success'),
    project: chartColor('warning'),
    hospital: chartColor('danger'),
    default: chartColor('info'),
  }
  return colorMap[type] || colorMap.default
}

function handleResize() {
  chart?.resize()
}

watch(
  () => [props.markers, props.regionData, props.routeLines, props.originMarker, props.geoJsonData],
  async () => {
    if (props.geoJsonData && props.geoJsonData !== geoJson) {
      geoJson = props.geoJsonData
      echarts.registerMap('guizhou', geoJson as any)
    }
    await nextTick()
    renderMap()
  },
  { deep: true }
)

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  chart?.dispose()
  chart = null
})
</script>

<style scoped>
.offline-map-container {
  min-height: 400px;
  border: 1px solid var(--color-border-light);
  border-radius: 4px;
  background: #fafafa;
}
</style>
