<template>
  <div class="map-page-container">
    <div v-if="loading" class="map-loading">
      <el-skeleton :rows="8" animated />
    </div>
    <div v-else-if="error" class="map-error">
      <el-result icon="error" title="地图加载失败" :sub-title="error">
        <template #extra>
          <el-button type="primary" @click="loadData">重试</el-button>
        </template>
      </el-result>
    </div>
    <div v-else-if="stats.totalVillages === 0 && stats.totalSchools === 0" class="map-empty">
      <el-result icon="info" title="暂无帮扶点数据" sub-title="请先录入帮扶村或学校信息">
        <template #extra>
          <el-button type="primary" @click="pushSafe('/supported-villages')"
            >前往录入帮扶村</el-button
          >
        </template>
      </el-result>
    </div>
    <template v-else>
      <div class="map-toolbar">
        <el-radio-group v-model="viewMode" size="small">
          <el-radio-button value="geographic">地理视图</el-radio-button>
          <el-radio-button value="statistical">统计视图</el-radio-button>
        </el-radio-group>

        <!-- 坐标定位 -->
        <template v-if="viewMode === 'geographic'">
          <!-- 名称搜索 -->
          <el-input
            v-model="searchKeyword"
            placeholder="搜索村名/学校名/区县..."
            size="small"
            clearable
            style="width: 240px; margin-left: 16px"
            @keyup.enter="handleSearch"
          >
            <template #append>
              <el-button size="small" :loading="searching" @click="handleSearch">
                <el-icon><Search /></el-icon>
              </el-button>
            </template>
          </el-input>

          <!-- 搜索结果下拉 -->
          <el-popover
            v-if="searchResults.length > 0"
            :visible="showSearchResults"
            placement="bottom"
            :width="300"
            trigger="click"
          >
            <div class="search-results">
              <div
                v-for="item in searchResults"
                :key="`${item.type}-${item.id}`"
                class="search-result-item"
                @click="locateSearchResult(item)"
              >
                <el-tag size="small" :type="item.type === 'village' ? 'success' : 'primary'">
                  {{ item.type === 'village' ? '村' : '校' }}
                </el-tag>
                <span class="result-name">{{ item.name }}</span>
                <span class="result-area">{{ item.county || item.district || '' }}</span>
              </div>
            </div>
          </el-popover>

          <!-- 坐标定位 -->
          <el-input
            v-model="coordInput"
            placeholder="输入经纬度定位, 如: 26.5,107.5"
            size="small"
            clearable
            style="width: 260px; margin-left: 8px"
            @keyup.enter="handleLocate"
          >
            <template #append>
              <el-button size="small" :loading="locating" @click="handleLocate">定位</el-button>
            </template>
          </el-input>

          <!-- 路线计算 -->
          <el-button
            v-if="originCoord"
            size="small"
            type="warning"
            :loading="routeLoading"
            style="margin-left: 8px"
            @click="handleCalcRoutes"
          >
            <el-icon><Van /></el-icon> 计算到全部帮扶点的路线
          </el-button>

          <el-button
            v-if="routeResults.length"
            size="small"
            style="margin-left: 8px"
            @click="routeResults = []"
          >
            清除路线
          </el-button>
        </template>

        <span class="map-stats">
          <el-tag size="small" type="success">村庄 {{ stats.totalVillages }}</el-tag>
          <el-tag size="small" type="warning">学校 {{ stats.totalSchools }}</el-tag>
        </span>
      </div>

      <!-- 路线摘要条 -->
      <div v-if="routeResults.length" class="route-summary">
        <span>出发点: {{ coordInput }}</span>
        <span style="margin-left: 24px">
          最近: {{ nearestResult?.destinationName }} ({{ nearestResult?.straightDistanceKm }}km /
          {{ nearestResult?.formattedTime }})
        </span>
        <span style="margin-left: 16px">
          最远: {{ farthestResult?.destinationName }} ({{ farthestResult?.straightDistanceKm }}km /
          {{ farthestResult?.formattedTime }})
        </span>
      </div>

      <!-- 地理视图：ECharts 矢量地图 + 标记点 + 路线 -->
      <OfflineMap
        v-if="viewMode === 'geographic'"
        :markers="geographicMarkers"
        :region-data="geographicRegionData"
        :route-lines="routeLines"
        :origin-marker="originCoord"
        height="calc(100vh - 180px)"
        @marker-click="handleMarkerClick"
        @region-click="handleRegionClick"
      />

      <!-- 统计视图：图表 + 表格 -->
      <MapVisualization
        v-if="viewMode === 'statistical'"
        :markers="markers"
        :region-data="regionData"
        :stats="stats"
        :show-legend="true"
        :show-stats="false"
        height="calc(100vh - 180px)"
        @marker-click="handleMarkerClick"
        @region-click="handleRegionClick"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, shallowRef, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouterSafe } from '@/composables/useRouterSafe'
import { getMapMarkers, getRegions } from '@/api/map'
import { parseCoordinate, calculateRoute, type LatLng, type RouteResult } from '@/utils/geo'

interface RouteResultWithName extends RouteResult {
  destinationName?: string
}
import OfflineMap from '@/components/map/OfflineMap.vue'
import MapVisualization from './MapVisualization.vue'
import { Van, Search } from '@element-plus/icons-vue'
import { get } from '@/api/request'
import { logger } from '@/utils/logger'

const { pushSafe } = useRouterSafe()
const loading = ref(true)
const error = ref('')
const viewMode = ref<'geographic' | 'statistical'>('geographic')

// Single source of truth: raw API response data
const rawVillages = shallowRef<any[]>([])
const rawSchools = shallowRef<any[]>([])

const stats = ref({ totalVillages: 0, totalSchools: 0 })

// Coordinate input & route state
const coordInput = ref('')
const locating = ref(false)

// ── 名称搜索 ──
const searchKeyword = ref('')
const searching = ref(false)
const searchResults = ref<
  Array<{
    id: number
    name: string
    lng: number
    lat: number
    type: string
    county?: string
    district?: string
  }>
>([])
const showSearchResults = ref(false)
const routeLoading = ref(false)
const originCoord = ref<LatLng | null>(null)
const routeResults = shallowRef<RouteResultWithName[]>([])

/** Route lines to render on map: [[lng1,lat1], [lng2,lat2], ...] */
const routeLines = computed(() => {
  if (!originCoord.value || !routeResults.value.length) return []
  return routeResults.value
    .filter((r) => r.straightDistanceKm > 0)
    .map((r) => ({
      coords: [
        [originCoord.value!.lng, originCoord.value!.lat],
        [r.destination.lng, r.destination.lat],
      ] as [number, number][],
      label: `${r.destinationName || '目标'} | ${r.formattedTime}`,
    }))
})

const nearestResult = computed(
  () => [...routeResults.value].sort((a, b) => a.straightDistanceKm - b.straightDistanceKm)[0]
)
const farthestResult = computed(
  () => [...routeResults.value].sort((a, b) => b.straightDistanceKm - a.straightDistanceKm)[0]
)

/** Geographic: {lng, lat, name, type} format for ECharts scatter map */
const geographicMarkers = computed(() => [
  ...rawVillages.value
    .filter((v: any) => v.lng != null && v.lat != null)
    .map((v: any) => ({
      lng: v.lng,
      lat: v.lat,
      name: v.name,
      type: 'village' as const,
      value: 1,
    })),
  ...rawSchools.value
    .filter((s: any) => s.lng != null && s.lat != null)
    .map((s: any) => ({
      lng: s.lng,
      lat: s.lat,
      name: s.name,
      type: 'school' as const,
      value: 1,
    })),
])

/** Geographic: county-level village count for choropleth */
const geographicRegionData = computed(() => {
  const countyMap: Record<string, number> = {}
  rawVillages.value.forEach((v: any) => {
    if (v.county) countyMap[v.county] = (countyMap[v.county] || 0) + 1
  })
  return Object.entries(countyMap).map(([name, value]) => ({ name, value }))
})

/** Statistical: full-attribute marker list (derived from same raw data) */
const markers = computed(() => [
  ...rawVillages.value.map((v: any) => ({
    id: v.id,
    name: v.name,
    lng: v.lng,
    lat: v.lat,
    type: 'village' as const,
    county: v.county,
    department: v.department,
    supportUnit: v.supportUnit,
    isRevitalizationTier: v.isRevitalizationTier,
    isThreeRegions: v.isThreeRegions,
    isKeyCounty: v.isKeyCounty,
    isProvincialDemo: v.isProvincialDemo,
  })),
  ...rawSchools.value.map((s: any) => ({
    id: s.id,
    name: s.name,
    lng: s.lng,
    lat: s.lat,
    type: 'school' as const,
    district: s.district,
    schoolType: s.type,
    supportStatus: s.supportStatus,
  })),
])

/** Statistical: region data */
const regionData = shallowRef<any[]>([])

async function loadData() {
  loading.value = true
  error.value = ''
  try {
    const [markerResult, regionResult] = await Promise.allSettled([
      getMapMarkers('all'),
      getRegions('county'),
    ])
    const markerData =
      markerResult.status === 'fulfilled' ? markerResult.value : { villages: [], schools: [] }
    const regionResp =
      regionResult.status === 'fulfilled' ? regionResult.value : { total: 0, items: [] }

    rawVillages.value = markerData?.villages || []
    rawSchools.value = markerData?.schools || []
    regionData.value = (regionResp.items || []).map((r: any) => ({
      code: r.code,
      name: r.name,
      centerLng: r.centerLng,
      centerLat: r.centerLat,
      geometry: r.geometry,
    }))

    stats.value = {
      totalVillages: rawVillages.value.length,
      totalSchools: rawSchools.value.length,
    }
  } catch (e: any) {
    error.value = e?.message || '地图数据加载失败'
  } finally {
    loading.value = false
  }
}

function handleMarkerClick(marker: any) {
  if (marker.type === 'village') {
    pushSafe(`/supported-villages/${marker.id}`)
  }
}

function handleRegionClick(region: any) {
  logger.debug('Region clicked', region)
}

/** 输入经纬度定位 */
function handleLocate() {
  const coord = parseCoordinate(coordInput.value)
  if (!coord) {
    // 格式错误用轻提示，不触发页面级"地图加载失败"分支
    ElMessage.warning('坐标格式错误，请输入如: 26.5,107.5（纬度,经度 或 经度,纬度 均可）')
    return
  }
  originCoord.value = coord
  routeResults.value = []
}

// ── 名称搜索 ──
async function handleSearch() {
  if (!searchKeyword.value.trim()) return
  searching.value = true
  showSearchResults.value = false
  try {
    const res = await get<any>('/map/search', { q: searchKeyword.value.trim() })
    const data = res.data || res
    const results: any[] = []
    if (data.villages) {
      results.push(...data.villages.map((v: any) => ({ ...v, type: 'village' })))
    }
    if (data.schools) {
      results.push(...data.schools.map((s: any) => ({ ...s, type: 'school' })))
    }
    searchResults.value = results
    showSearchResults.value = results.length > 0
  } catch (e: any) {
    error.value = '搜索失败: ' + (e.message || '未知错误')
  } finally {
    searching.value = false
  }
}

function locateSearchResult(item: { lng: number; lat: number; name: string }) {
  originCoord.value = { lng: item.lng, lat: item.lat }
  showSearchResults.value = false
  searchKeyword.value = item.name
  routeResults.value = []
}

/** 计算从当前出发点到一个帮扶村/学校的路线（含驾驶时间估算） */
function handleCalcRoutes() {
  if (!originCoord.value) return
  routeLoading.value = true

  const allTargets = [
    ...rawVillages.value
      .filter((v: any) => v.lng != null && v.lat != null)
      .map((v: any) => ({
        lng: v.lng,
        lat: v.lat,
        name: v.name,
        type: 'village' as const,
      })),
    ...rawSchools.value
      .filter((s: any) => s.lng != null && s.lat != null)
      .map((s: any) => ({
        lng: s.lng,
        lat: s.lat,
        name: s.name,
        type: 'school' as const,
      })),
  ]

  const results: RouteResultWithName[] = allTargets.map((t) => {
    const r = calculateRoute(originCoord.value!, { lat: t.lat, lng: t.lng })
    return { ...r, destinationName: t.name }
  })

  // Sort by distance
  results.sort((a, b) => a.straightDistanceKm - b.straightDistanceKm)
  routeResults.value = results
  routeLoading.value = false
}

onMounted(loadData)
</script>

<style scoped>
.map-page-container {
  height: 100%;
  display: flex;
  flex-direction: column;
}
.map-loading,
.map-error,
.map-empty {
  padding: 40px;
}
.map-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  padding: 8px 16px;
  background: var(--color-bg-hover);
  border-bottom: 1px solid var(--color-border-light);
}
.map-stats {
  display: flex;
  gap: 8px;
  margin-left: auto;
}
.route-summary {
  display: flex;
  align-items: center;
  padding: 6px 16px;
  background: #fef3e6;
  border-bottom: 1px solid #f5dab1;
  font-size: 13px;
  color: var(--color-text-regular);
}

/* 搜索结果样式 */
.search-results {
  max-height: 300px;
  overflow-y: auto;
}
.search-result-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  cursor: pointer;
  border-bottom: 1px solid var(--color-bg-hover);
  transition: background 0.2s;
}
.search-result-item:hover {
  background: var(--color-bg-hover);
}
.search-result-item .result-name {
  flex: 1;
  font-size: 13px;
  color: var(--color-text-primary);
}
.search-result-item .result-area {
  font-size: 12px;
  color: var(--color-info);
}
</style>
