<template>
  <div
    class="bigscreen big-screen"
    :class="{ fullscreen: isFullscreen }"
    data-theme="dark-bigscreen"
    :data-bigscreen-distance="distance"
    :data-carousel-view="carouselView"
  >
    <header class="bs-layer-header bs-header">
      <h1>帮扶管理信息系统 · 帮扶成效总览大屏</h1>
      <div class="bs-header-right">
        <!-- 距离字号分档：3m / 6m / 10m（默认 6m，仅影响大屏页字号） -->
        <div class="distance-switch" role="group" aria-label="大屏字号距离档">
          <el-button
            v-for="option in distanceOptions"
            :key="option.value"
            size="small"
            class="distance-option"
            :class="{ active: distance === option.value }"
            @click="onDistanceChange(option.value)"
          >
            {{ option.label }}
          </el-button>
        </div>
        <!-- 自动轮播：15s 切换「KPI 组 / 图表组」数据视角（默认关闭） -->
        <el-button class="carousel-toggle" @click="toggleCarousel">
          {{ carouselToggleLabel }}
        </el-button>
        <el-button v-if="carouselEnabled" class="carousel-pause" @click="toggleCarouselPause">
          {{ carouselPaused ? '继续' : '暂停' }}
        </el-button>
        <span v-if="carouselEnabled" class="carousel-status">{{ carouselViewLabel }}</span>
        <span class="bs-clock">{{ clock }}</span>
        <el-button class="settings-trigger" @click="openSettings">设置</el-button>
        <el-button @click="toggleFullscreen">
          {{ isFullscreen ? '退出全屏' : '全屏展示' }}
        </el-button>
        <el-button class="exit-bigscreen" @click="exitBigScreen">退出大屏</el-button>
      </div>
    </header>

    <!-- 对象筛选条：全部 / 帮扶村 / 帮扶学校 / 帮扶单位（筛选结果持久化） -->
    <section class="bs-filters">
      <span class="filter-label">查看对象</span>
      <el-radio-group
        class="scope-type-group"
        :model-value="config.scope.type"
        @update:model-value="onScopeTypeChange($event)"
      >
        <el-radio-button
          v-for="option in scopeTypeOptions"
          :key="option.value"
          :value="option.value"
          class="scope-type-option"
        >
          {{ option.label }}
        </el-radio-button>
      </el-radio-group>
      <el-select
        v-if="isScoped"
        class="scope-object-select"
        :model-value="scopeSelection"
        filterable
        placeholder="请选择对象"
        @update:model-value="onScopeObjectChange($event)"
      >
        <el-option
          v-for="option in scopeObjectOptions"
          :key="option.value"
          :label="option.label"
          :value="option.value"
        />
      </el-select>
      <el-button class="scope-reset" :disabled="!isScoped" @click="resetScope">
        <el-icon><Refresh /></el-icon>
        重置
      </el-button>
      <span v-if="scopeSubtitle" class="scope-subtitle">{{ scopeSubtitle }}</span>
    </section>

    <!-- 设置抽屉：卡片取舍与顺序 / 自动刷新频率 / 汇报脱敏（localStorage 持久化） -->
    <el-drawer v-model="settingsVisible" title="大屏设置" size="360px">
      <div class="settings-panel">
        <div class="settings-section">
          <div class="settings-title">卡片显示与顺序</div>
          <div v-for="(card, index) in config.cards" :key="card.key" class="settings-card-row">
            <el-switch
              :model-value="card.visible"
              @update:model-value="onCardVisibleChange(card, $event)"
            />
            <span class="settings-card-title">{{ card.title }}</span>
            <el-button size="small" :disabled="index === 0" @click="moveCard(index, -1)"
              >上移</el-button
            >
            <el-button
              size="small"
              :disabled="index === config.cards.length - 1"
              @click="moveCard(index, 1)"
              >下移</el-button
            >
          </div>
        </div>
        <div class="settings-section">
          <div class="settings-title">自动刷新频率</div>
          <el-radio-group
            class="settings-refresh"
            :model-value="config.refreshInterval"
            @update:model-value="onRefreshChange($event)"
          >
            <el-radio-button
              v-for="option in refreshOptions"
              :key="option.value"
              :value="option.value"
            >
              {{ option.label }}
            </el-radio-button>
          </el-radio-group>
        </div>
        <div class="settings-section">
          <div class="settings-title">汇报脱敏</div>
          <div class="settings-desensitize">
            <el-switch
              :model-value="config.desensitized"
              @update:model-value="onDesensitizeChange($event)"
            />
            <span class="settings-hint">隐藏金额精度与负责人姓名</span>
          </div>
        </div>
        <el-button class="settings-reset" @click="resetSettings">恢复默认</el-button>
      </div>
    </el-drawer>

    <!-- 第二层：KPI 大数字区（字号随距离档位缩放；轮播时高亮当前数据视角） -->
    <section class="bs-layer-kpi bs-kpi" :class="{ 'carousel-focus': carouselKpiActive }">
      <div v-for="kpi in kpis" :key="kpi.key" class="kpi-item">
        <div class="kpi-value">{{ kpi.value }}</div>
        <div class="kpi-label">
          {{ kpi.label }}<template v-if="kpi.unit">（{{ kpi.unit }}）</template>
        </div>
      </div>
    </section>

    <!-- 第三层：图表 / 负责人 / 对象档案 / 帮扶明细卡片（2-3 列，按设置开关与排序渲染） -->
    <section class="bs-layer-charts bs-charts" :class="{ 'carousel-focus': carouselChartsActive }">
      <div
        v-for="card in visibleCards"
        :key="card.key"
        class="chart-card"
        :class="{ wide: card.wide }"
      >
        <div class="chart-title">{{ card.title }}</div>
        <BaseChart v-if="card.key === 'fundTrend'" :option="fundTrendOption" class="chart-body" />
        <BaseChart v-else-if="card.key === 'rank'" :option="rankOption" class="chart-body" />
        <BaseChart
          v-else-if="card.key === 'projectStatus'"
          :option="projectStatusOption"
          class="chart-body"
        />
        <BaseChart v-else-if="card.key === 'yearly'" :option="yearlyOption" class="chart-body" />
        <ul v-else-if="card.key === 'leaders'" class="leader-list">
          <li v-for="row in leaderRows" :key="row.id" class="leader-item">
            <span class="leader-project">{{ row.project }}</span>
            <span class="leader-person">{{ row.person }}</span>
          </li>
        </ul>
        <div v-else-if="card.key === 'profile'" class="detail-body">
          <template v-if="profileData">
            <div class="profile-title">{{ profileData.title }}</div>
            <div
              v-for="section in profileData.sections"
              :key="section.title"
              class="profile-section"
            >
              <div class="profile-section-title">{{ section.title }}</div>
              <div class="profile-grid">
                <div v-for="item in section.items" :key="item.label" class="profile-item">
                  <span class="profile-item-label">{{ item.label }}</span>
                  <span class="profile-item-value">{{ item.value ?? '—' }}</span>
                </div>
              </div>
            </div>
            <div v-for="group in profileData.tags" :key="group.label" class="profile-tags">
              <span class="profile-item-label">{{ group.label }}</span>
              <el-tag v-for="tag in group.items" :key="tag" size="small" class="profile-tag">
                {{ tag }}
              </el-tag>
            </div>
          </template>
          <div v-else class="detail-empty">暂无对象档案数据</div>
        </div>
        <div v-else class="detail-body">
          <template v-if="detailsData">
            <div class="detail-section">
              <div class="detail-section-title">重点项目（Top 5）</div>
              <table class="detail-table">
                <thead>
                  <tr>
                    <th>项目名称</th>
                    <th>状态</th>
                    <th>金额(万元)</th>
                    <th>负责人</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="row in detailsProjects" :key="row.name" class="detail-row">
                    <td>{{ row.name }}</td>
                    <td>{{ row.statusText }}</td>
                    <td>{{ row.amountText }}</td>
                    <td>{{ row.person }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div class="detail-section">
              <div class="detail-section-title">帮扶经费（Top 5）</div>
              <table class="detail-table">
                <thead>
                  <tr>
                    <th>经费名称</th>
                    <th>年度</th>
                    <th>状态</th>
                    <th>金额(万元)</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="row in detailsFunds" :key="row.name" class="detail-row">
                    <td>{{ row.name }}</td>
                    <td>{{ row.year }}</td>
                    <td>{{ row.statusText }}</td>
                    <td>{{ row.amountText }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div class="detail-section">
              <div class="detail-section-title">结对帮扶</div>
              <div class="pairing-grid">
                <div class="pairing-item">
                  <span class="pairing-value">{{ pairingStats.total }}</span>
                  <span class="pairing-label">结对数</span>
                </div>
                <div class="pairing-item">
                  <span class="pairing-value">{{ pairingStats.active }}</span>
                  <span class="pairing-label">进行中</span>
                </div>
                <div class="pairing-item">
                  <span class="pairing-value">{{ pairingStats.visits }}</span>
                  <span class="pairing-label">走访次数</span>
                </div>
              </div>
            </div>
          </template>
          <div v-else class="detail-empty">暂无帮扶明细数据</div>
        </div>
      </div>
    </section>

    <footer class="bs-footer">{{ footerText }}</footer>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { logger } from '@/utils/logger'
import { useRouterSafe } from '@/composables/useRouterSafe'
import { Refresh } from '@element-plus/icons-vue'
import BaseChart from '@/components/common/BaseChart.vue'
import {
  getBigScreenFilters,
  getBigScreenOverview,
  type BigScreenFilters,
  type BigScreenKpi,
  type BigScreenOverview,
  type BigScreenOverviewParams,
} from '@/api/bigscreen'
import {
  BIG_SCREEN_SCOPE_OPTIONS,
  REFRESH_LABELS,
  REFRESH_OPTIONS,
  SCOPED_ONLY_CARD_KEYS,
  defaultBigScreenConfig,
  defaultBigScreenScope,
  formatLeaderName,
  hideAmountPrecision,
  loadBigScreenConfig,
  normalizeBigScreenScopeType,
  normalizeRefreshInterval,
  saveBigScreenConfig,
  type BigScreenCardConfig,
  type BigScreenConfig,
  type BigScreenScopeConfig,
  type RefreshInterval,
} from './bigscreenConfig'

/** overview 统计年度跨度（与后端 /bigscreen/overview 的 years 默认口径一致） */
const OVERVIEW_YEARS = 5

/** KPI 兜底：overview 未加载/加载失败时保留零值骨架，避免大屏整块空白 */
const FALLBACK_KPIS: BigScreenKpi[] = [
  { key: 'villages', label: '帮扶村', value: 0, unit: '个' },
  { key: 'projects', label: '帮扶项目', value: 0, unit: '个' },
  { key: 'schools', label: '帮扶学校', value: 0, unit: '所' },
  { key: 'completion', label: '完成率', value: '—', unit: '' },
  { key: 'funds', label: '经费总额', value: 0, unit: '万元' },
]

/** 筛选对象下拉项（value 带类型前缀，避免村/校 id 撞车） */
interface ScopeObjectOption {
  value: string
  label: string
  id: number | null
  name: string | null
}

const { pushSafe } = useRouterSafe()
const isFullscreen = ref(false)
const clock = ref('')
const filters = ref<BigScreenFilters>({ villages: [], schools: [], units: [] })
const filtersFailed = ref(false)
const overview = ref<BigScreenOverview | null>(null)
// 大屏配置：卡片开关与顺序、自动刷新频率、汇报脱敏、筛选对象；localStorage 持久化
const config = reactive<BigScreenConfig>(loadBigScreenConfig())
const settingsVisible = ref(false)
const refreshOptions = REFRESH_OPTIONS

// ─────────────────────────────────────────────
// W23 大屏 UI v2：距离字号分档 + 自动轮播
// ─────────────────────────────────────────────
/** 距离字号档位（契约 §0.4：3m 标准 / 6m ×1.25 / 10m ×1.5，默认 6m） */
export type BigScreenDistance = '3m' | '6m' | '10m'
const DEFAULT_BIGSCREEN_DISTANCE: BigScreenDistance = '6m'
const BIGSCREEN_DISTANCES: ReadonlyArray<{ value: BigScreenDistance; label: string }> = [
  { value: '3m', label: '3m' },
  { value: '6m', label: '6m' },
  { value: '10m', label: '10m' },
]
/** 大屏强制深色主题（仅本页挂载期间生效，卸载恢复原主题） */
const BIGSCREEN_DARK_THEME = 'dark-bigscreen'

/** 自动轮播间隔（15s）与数据视角（KPI 组 / 图表组） */
const CAROUSEL_INTERVAL_MS = 15000
const CAROUSEL_VIEWS = ['kpi', 'charts'] as const
type BigScreenCarouselView = (typeof CAROUSEL_VIEWS)[number]
const CAROUSEL_VIEW_LABELS: Record<BigScreenCarouselView, string> = {
  kpi: '指标视角',
  charts: '图表视角',
}

const distance = ref<BigScreenDistance>(DEFAULT_BIGSCREEN_DISTANCE)
const distanceOptions = BIGSCREEN_DISTANCES
const carouselEnabled = ref(false)
const carouselPaused = ref(false)
const carouselView = ref<BigScreenCarouselView>('kpi')
let carouselTimer: number | null = null
let previousTheme: string | null = null

/** 距离档位归一化：非法值回落默认 6m */
function normalizeDistance(value: unknown): BigScreenDistance {
  return BIGSCREEN_DISTANCES.some((option) => option.value === value)
    ? (value as BigScreenDistance)
    : DEFAULT_BIGSCREEN_DISTANCE
}

function onDistanceChange(value: unknown): void {
  distance.value = normalizeDistance(value)
}

/** 轮播开关按钮文案 */
const carouselToggleLabel = computed(() => (carouselEnabled.value ? '关闭轮播' : '自动轮播'))

/** 轮播当前数据视角文案 */
const carouselViewLabel = computed(() => CAROUSEL_VIEW_LABELS[carouselView.value])

/** 轮播运行时高亮当前视角（暂停时保持当前视角高亮） */
const carouselKpiActive = computed(() => carouselEnabled.value && carouselView.value === 'kpi')
const carouselChartsActive = computed(
  () => carouselEnabled.value && carouselView.value === 'charts'
)

/** 切换到下一个数据视角（KPI 组 ↔ 图表组） */
function nextCarouselView(): void {
  const index = CAROUSEL_VIEWS.indexOf(carouselView.value)
  carouselView.value = CAROUSEL_VIEWS[(index + 1) % CAROUSEL_VIEWS.length]
}

/** 按开关/暂停态重建轮播定时器；停止态不保留任何定时器 */
function applyCarouselTimer(): void {
  if (carouselTimer !== null) {
    clearInterval(carouselTimer)
    carouselTimer = null
  }
  if (carouselEnabled.value && !carouselPaused.value) {
    carouselTimer = window.setInterval(nextCarouselView, CAROUSEL_INTERVAL_MS)
  }
}

function startCarousel(): void {
  if (carouselEnabled.value) return
  carouselEnabled.value = true
  carouselPaused.value = false
  carouselView.value = 'kpi'
  applyCarouselTimer()
}

function stopCarousel(): void {
  carouselEnabled.value = false
  carouselPaused.value = false
  applyCarouselTimer()
}

/** 开关轮播：开启默认 KPI 视角；再次点击关闭并清理定时器 */
function toggleCarousel(): void {
  if (carouselEnabled.value) {
    stopCarousel()
    return
  }
  startCarousel()
}

/** 暂停/继续轮播（暂停时停止定时器并保留当前视角） */
function toggleCarouselPause(): void {
  carouselPaused.value = !carouselPaused.value
  applyCarouselTimer()
}

/** 强制大屏深色主题（记录原主题，卸载时恢复，避免影响其它页面） */
function applyPageTheme(): void {
  const root = document.documentElement
  previousTheme = root.getAttribute('data-theme')
  root.setAttribute('data-theme', BIGSCREEN_DARK_THEME)
}

function restorePageTheme(): void {
  const root = document.documentElement
  if (previousTheme) root.setAttribute('data-theme', previousTheme)
  else root.removeAttribute('data-theme')
}

let clockTimer: number | null = null
let refreshTimer: number | null = null
let overviewSeq = 0

/** 告警去重：同类降级在一个大屏实例生命周期内只提示一次 */
const warned = { filters: false, overview: false, scope: false }

function warnOnce(key: keyof typeof warned, message: string): void {
  if (warned[key]) return
  warned[key] = true
  ElMessage.warning(message)
}

/** 金额展示：脱敏模式隐藏小数精度，否则保持原口径（万元、最多 2 位小数） */
function displayMoney(value: unknown): number {
  if (config.desensitized) return hideAmountPrecision(value)
  if (value === null || value === undefined) return 0
  return Math.round(Number(value) * 100) / 100
}

/** KPI：直接渲染后端固定 5 项；脱敏模式对数值型 KPI 隐藏小数精度 */
const kpis = computed<BigScreenKpi[]>(() => {
  const rows = overview.value?.kpis
  if (!rows || rows.length === 0) return FALLBACK_KPIS
  return rows.map((kpi) => ({
    key: kpi.key,
    label: kpi.label,
    unit: kpi.unit,
    value:
      config.desensitized && typeof kpi.value === 'number'
        ? hideAmountPrecision(kpi.value)
        : kpi.value,
  }))
})

const fundTrendOption = computed(() => {
  const data = overview.value?.fund_trend ?? []
  return {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    grid: { left: 40, right: 16, top: 24, bottom: 28 },
    xAxis: { type: 'category', data: data.map((d) => d.year) },
    yAxis: { type: 'value' },
    series: [
      {
        name: '计划投入',
        type: 'line',
        smooth: true,
        data: data.map((d) => displayMoney(d.planned)),
        itemStyle: { color: '#36cfc9' },
      },
      {
        name: '实际投入',
        type: 'line',
        smooth: true,
        data: data.map((d) => displayMoney(d.actual)),
        itemStyle: { color: '#ffd666' },
      },
    ],
  }
})

const rankOption = computed(() => {
  const rows = overview.value?.rankings ?? []
  return {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    grid: { left: 90, right: 24, top: 16, bottom: 24 },
    xAxis: { type: 'value' },
    yAxis: { type: 'category', data: rows.map((row) => row.name) },
    series: [
      {
        type: 'bar',
        data: rows.map((row) => row.score),
        itemStyle: { color: '#40a9ff' },
      },
    ],
  }
})

const projectStatusOption = computed(() => {
  const rows = overview.value?.project_status ?? []
  return {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'item' },
    legend: { bottom: 0, textStyle: { color: '#aaa' } },
    series: [
      {
        type: 'pie',
        radius: ['40%', '68%'],
        data: rows.map((row) => ({
          // 后端未给中文标签时回退原始状态键，避免饼图出现空白扇区名
          name: row.label || row.key,
          value: Number(row.value) || 0,
        })),
      },
    ],
  }
})

const yearlyOption = computed(() => {
  const rows = overview.value?.yearly ?? []
  return {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    grid: { left: 40, right: 16, top: 24, bottom: 28 },
    xAxis: { type: 'category', data: rows.map((row) => row.year) },
    yAxis: { type: 'value' },
    series: [
      {
        type: 'bar',
        // project_count 为真实项目数；旧载荷缺该字段时回退经费记录数
        data: rows.map((row) => row.project_count ?? row.fund_count),
        itemStyle: { color: '#b37feb' },
        barWidth: '40%',
      },
    ],
  }
})

/** 可见卡片：按配置顺序；对象档案/帮扶明细仅在选中具体对象时渲染 */
const visibleCards = computed(() =>
  config.cards.filter(
    (card) => card.visible && (isScoped.value || !SCOPED_ONLY_CARD_KEYS.includes(card.key))
  )
)

/** 重点项目负责人：脱敏模式下姓名打码 */
const leaderRows = computed(() =>
  (overview.value?.leaders ?? []).slice(0, 5).map((row) => ({
    id: row.name,
    project: row.name || '—',
    person: formatLeaderName(row.person, config.desensitized),
  }))
)

/** 对象档案（scope = all 时后端返回 null） */
const profileData = computed(() => overview.value?.profile ?? null)

/** 帮扶明细（scope = all 时后端返回 null） */
const detailsData = computed(() => overview.value?.details ?? null)

/** 当前筛选范围副标题（后端回显，如覆盖统计） */
const scopeSubtitle = computed(() => overview.value?.scope?.subtitle ?? '')

/** 帮扶明细-项目 Top5（金额走统一脱敏口径） */
const detailsProjects = computed(() =>
  (detailsData.value?.projects ?? []).slice(0, 5).map((row) => ({
    name: row.name,
    statusText: row.label ?? row.status ?? '—',
    amountText: displayMoney(row.amount),
    person: formatLeaderName(row.person, config.desensitized),
  }))
)

/** 帮扶明细-经费 Top5（金额走统一脱敏口径） */
const detailsFunds = computed(() =>
  (detailsData.value?.funds ?? []).slice(0, 5).map((row) => ({
    name: row.name,
    year: row.year,
    statusText: row.label ?? row.status ?? '—',
    amountText: displayMoney(row.amount),
  }))
)

/** 结对统计（明细缺失时零值兜底） */
const pairingStats = computed(
  () => detailsData.value?.pairing ?? { total: 0, active: 0, visits: 0 }
)

/** 是否已选中具体对象（scope != all） */
const isScoped = computed(() => config.scope.type !== 'all')

/** 筛选类型选项：filters 加载失败时仅保留「全部」 */
const scopeTypeOptions = computed(() =>
  filtersFailed.value ? BIG_SCREEN_SCOPE_OPTIONS.slice(0, 1) : BIG_SCREEN_SCOPE_OPTIONS
)

/** 当前类型的对象下拉项（单位项展示村/校/项目覆盖统计） */
const scopeObjectOptions = computed<ScopeObjectOption[]>(() => {
  const scopeType = config.scope.type
  if (scopeType === 'village') {
    return filters.value.villages.map((village) => ({
      value: `village:${village.id}`,
      label: village.county ? `${village.name}（${village.county}）` : village.name,
      id: village.id,
      name: village.name,
    }))
  }
  if (scopeType === 'school') {
    return filters.value.schools.map((school) => ({
      value: `school:${school.id}`,
      label: school.district ? `${school.name}（${school.district}）` : school.name,
      id: school.id,
      name: school.name,
    }))
  }
  if (scopeType === 'unit') {
    return filters.value.units.map((unit) => ({
      value: `unit:${unit.name}`,
      label: `${unit.name}（村${unit.village_count}·校${unit.school_count}·项目${unit.project_count}）`,
      id: null,
      name: unit.name,
    }))
  }
  return []
})

/** 下拉选中值：单位用 name，村/校用 id */
const scopeSelection = computed(() => {
  const scope = config.scope
  if (scope.type === 'all') return ''
  if (scope.type === 'unit') return scope.name === null ? '' : `unit:${scope.name}`
  return scope.id === null ? '' : `${scope.type}:${scope.id}`
})

/** 页脚：自动刷新状态 + 汇报模式（脱敏态明确标注） */
const footerText = computed(() => {
  const refresh =
    config.refreshInterval === 0
      ? '自动刷新已关闭'
      : `数据每 ${REFRESH_LABELS[config.refreshInterval]}自动刷新`
  const mode = config.desensitized ? '汇报脱敏模式' : '汇报展示模式'
  return `数据来源：本地数据库 · ${refresh} · ${mode}`
})

/** filters 响应兜底：缺字段/类型非法一律按空数组处理 */
function normalizeFilters(raw: BigScreenFilters | null): BigScreenFilters {
  return {
    villages: Array.isArray(raw?.villages) ? raw.villages : [],
    schools: Array.isArray(raw?.schools) ? raw.schools : [],
    units: Array.isArray(raw?.units) ? raw.units : [],
  }
}

/** overview 请求参数：村/校按 id、单位按 name 定位 */
function buildOverviewParams(scope: BigScreenScopeConfig): BigScreenOverviewParams {
  const params: BigScreenOverviewParams = { scope_type: scope.type, years: OVERVIEW_YEARS }
  if (scope.type === 'village' || scope.type === 'school') {
    if (scope.id !== null) params.scope_id = scope.id
  } else if (scope.type === 'unit') {
    if (scope.name !== null) params.scope_name = scope.name
  }
  return params
}

/** 404 = 对象不存在或越权（后端数据域收敛） */
function isNotFoundError(error: unknown): boolean {
  const status = (error as { response?: { status?: number } } | null)?.response?.status
  return status === 404
}

function applyScope(scope: BigScreenScopeConfig): void {
  config.scope = { ...scope }
}

/**
 * 恢复的筛选范围在当前 filters 中不存在（对象被删除/越权返回）→ 回退「全部」。
 * 必须在 filters 加载（或失败）之后调用，避免用旧列表覆盖刚恢复的 scope。
 */
function validateRestoredScope(): void {
  const scope = config.scope
  if (scope.type === 'all') return
  const available =
    scope.type === 'village'
      ? filters.value.villages.some((village) => village.id === scope.id)
      : scope.type === 'school'
        ? filters.value.schools.some((school) => school.id === scope.id)
        : filters.value.units.some((unit) => unit.name === scope.name)
  if (available) return
  applyScope(defaultBigScreenScope())
  warnOnce('scope', '所选对象不存在，已恢复「全部」视图')
}

/** overview 失败降级：404 回退全部；全部失败仅提示一次；其余静默保留上次数据 */
function handleOverviewError(error: unknown, scope: BigScreenScopeConfig): void {
  if (scope.type !== 'all' && isNotFoundError(error)) {
    applyScope(defaultBigScreenScope())
    warnOnce('scope', '所选对象不存在或无权查看，已恢复「全部」视图')
    void loadOverview()
    return
  }
  logger.warn('[BigScreen] overview 加载失败，保留上次数据')
  if (scope.type === 'all') {
    warnOnce('overview', '大屏数据加载失败，请检查服务连接')
  }
}

/** 加载 overview（挂载 / 切换 scope / 自动轮询共用；过期响应直接丢弃） */
async function loadOverview(): Promise<void> {
  const scope: BigScreenScopeConfig = { ...config.scope }
  const seq = ++overviewSeq
  try {
    const data = await getBigScreenOverview(buildOverviewParams(scope))
    if (seq !== overviewSeq) return
    overview.value = data ?? null
  } catch (error) {
    if (seq !== overviewSeq) return
    handleOverviewError(error, scope)
  }
}

/** 加载筛选对象列表（仅挂载时一次），随后校验恢复的 scope 是否仍然有效 */
async function loadFilters(): Promise<void> {
  try {
    const data = await getBigScreenFilters()
    filters.value = normalizeFilters(data ?? null)
    filtersFailed.value = false
  } catch {
    filtersFailed.value = true
    filters.value = normalizeFilters(null)
    warnOnce('filters', '筛选对象加载失败，仅保留「全部」视图')
  }
  validateRestoredScope()
}

/** 首屏：先 filters 校验 scope，再拉 overview（避免用失效 scope 请求） */
async function initData(): Promise<void> {
  await loadFilters()
  await loadOverview()
}

// ── 筛选条交互 ──
function onScopeTypeChange(value: unknown): void {
  const type = normalizeBigScreenScopeType(value)
  if (type === 'all') {
    applyScope(defaultBigScreenScope())
    void loadOverview()
    return
  }
  applyScope({ type, id: null, name: null })
  const options = scopeObjectOptions.value
  if (options.length === 0) {
    applyScope(defaultBigScreenScope())
    warnOnce('scope', '暂无可选对象，已恢复「全部」视图')
    void loadOverview()
    return
  }
  const first = options[0]
  applyScope({ type, id: first.id, name: first.name })
  void loadOverview()
}

function onScopeObjectChange(value: unknown): void {
  const type = config.scope.type
  if (type === 'all') return
  const option = scopeObjectOptions.value.find((item) => item.value === value)
  if (!option) return
  applyScope({ type, id: option.id, name: option.name })
  void loadOverview()
}

function resetScope(): void {
  applyScope(defaultBigScreenScope())
  void loadOverview()
}

function tickClock(): void {
  const d = new Date()
  clock.value = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}:${String(d.getSeconds()).padStart(2, '0')}`
}

function toggleFullscreen(): void {
  if (!document.fullscreenElement) {
    document.documentElement.requestFullscreen?.().catch(() => {})
    isFullscreen.value = true
  } else {
    document.exitFullscreen?.().catch(() => {})
    isFullscreen.value = false
  }
}

/** 退出大屏：停轮播 → 若处于全屏先退出全屏 → 返回工作台（W22/W23） */
function exitBigScreen(): void {
  stopCarousel()
  if (document.fullscreenElement) {
    document.exitFullscreen?.().catch(() => {})
    isFullscreen.value = false
  }
  pushSafe('/dashboard')
}

function onFullscreenChange(): void {
  isFullscreen.value = !!document.fullscreenElement
}

// ── 设置抽屉：卡片取舍/顺序、刷新频率、脱敏 ──
function openSettings(): void {
  settingsVisible.value = true
}

function onCardVisibleChange(card: BigScreenCardConfig, value: unknown): void {
  card.visible = value === true
}

function moveCard(index: number, offset: number): void {
  const target = index + offset
  if (target < 0 || target >= config.cards.length) return
  const [card] = config.cards.splice(index, 1)
  config.cards.splice(target, 0, card)
}

function onRefreshChange(value: unknown): void {
  config.refreshInterval = normalizeRefreshInterval(value)
}

function onDesensitizeChange(value: unknown): void {
  config.desensitized = value === true
}

function resetSettings(): void {
  Object.assign(config, defaultBigScreenConfig())
  // scope 随配置回到「全部」，需要重新按全部对象拉取数据
  void loadOverview()
}

/** 按当前刷新频率重建轮询定时器；0 = 关闭自动刷新，不产生任何轮询请求 */
function applyRefreshTimer(interval: RefreshInterval): void {
  if (refreshTimer !== null) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
  if (interval > 0) {
    refreshTimer = window.setInterval(loadOverview, interval * 1000)
  }
}

// 配置变更：立即生效并写回 localStorage（深比较，卡片顺序/可见性/脱敏/scope 均会触发）
watch(config, () => saveBigScreenConfig(config), { deep: true })
watch(
  () => config.refreshInterval,
  (interval) => applyRefreshTimer(interval)
)

onMounted(() => {
  // W23：大屏页强制深色主题（卸载恢复）；默认 6m 距离档
  applyPageTheme()
  tickClock()
  clockTimer = window.setInterval(tickClock, 1000)
  applyRefreshTimer(config.refreshInterval)
  document.addEventListener('fullscreenchange', onFullscreenChange)
  void initData()
})

onUnmounted(() => {
  restorePageTheme()
  if (clockTimer) clearInterval(clockTimer)
  if (refreshTimer !== null) clearInterval(refreshTimer)
  if (carouselTimer !== null) clearInterval(carouselTimer)
  document.removeEventListener('fullscreenchange', onFullscreenChange)
})
</script>

<style lang="scss" scoped>
// ── W23 距离字号分档（契约 §0.4：3m 标准 / 6m ×1.25 / 10m ×1.5，默认 6m）──
// 优先消费 W1 提供的 --bs-text-* token；未提供时用本地 --bs-distance-scale 兜底，
// 保证大屏页在 token 落地前后都有正确的距离字号分档。
.bigscreen {
  --bs-distance-scale: 1.25;
}
.bigscreen[data-bigscreen-distance='3m'] {
  --bs-distance-scale: 1;
}
.bigscreen[data-bigscreen-distance='6m'] {
  --bs-distance-scale: 1.25;
}
.bigscreen[data-bigscreen-distance='10m'] {
  --bs-distance-scale: 1.5;
}
.big-screen {
  min-height: 100vh;
  background: radial-gradient(ellipse at top, #0b1e3a 0%, #060d1f 60%, #04070f 100%);
  color: #e6f1ff;
  padding: 16px 24px 8px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.big-screen.fullscreen {
  padding: 8px 24px;
}
.bs-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid rgba(64, 169, 255, 0.35);
  padding-bottom: 10px;
}
.bs-header h1 {
  font-size: var(--bs-text-title, calc(22px * var(--bs-distance-scale, 1.25)));
  font-weight: 600;
  letter-spacing: 2px;
  background: linear-gradient(90deg, #40a9ff, #ffd666);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  margin: 0;
}
.bs-header-right {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 12px;
}
.distance-switch {
  display: flex;
  align-items: center;
  gap: 4px;
}
.distance-option.active {
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
  border-color: var(--el-color-primary-light-5);
}
.carousel-status {
  font-size: 12px;
  color: var(--el-color-info);
}
.carousel-focus {
  border-radius: 8px;
  box-shadow: inset 0 0 0 2px var(--el-color-primary-light-5);
}
.bs-clock {
  font-family: var(--font-family-mono);
  color: #ffd666;
  font-size: 14px;
}
.settings-panel {
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.settings-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.settings-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-primary);
}
.settings-card-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.settings-card-title {
  flex: 1;
  font-size: 13px;
  color: var(--color-text-secondary);
}
.settings-desensitize {
  display: flex;
  align-items: center;
  gap: 10px;
}
.settings-hint {
  font-size: 12px;
  color: var(--color-text-secondary);
}
.settings-reset {
  align-self: flex-start;
}
.bs-kpi {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 12px;
}
.kpi-item {
  background: rgba(64, 169, 255, 0.08);
  border: 1px solid rgba(64, 169, 255, 0.25);
  border-radius: 8px;
  padding: 10px 8px;
  text-align: center;
}
.kpi-value {
  font-size: var(--bs-text-kpi, calc(34px * var(--bs-distance-scale, 1.25)));
  font-weight: 700;
  color: #40a9ff;
}
.kpi-label {
  font-size: var(--bs-text-body, calc(13px * var(--bs-distance-scale, 1.25)));
  color: #9fc6ef;
  margin-top: 4px;
}
.bs-charts {
  display: grid;
  // 2-3 列图表：宽屏 3 列（宽卡片占 2 列），窄屏回落 2 列
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  flex: 1;
}
@media (max-width: 1400px) {
  .bs-charts {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
.chart-card {
  background: rgba(9, 24, 48, 0.65);
  border: 1px solid rgba(64, 169, 255, 0.2);
  border-radius: 8px;
  padding: 8px 10px 6px;
  display: flex;
  flex-direction: column;
}
.chart-card.wide {
  grid-column: span 2;
  min-height: 220px;
}
.chart-title {
  font-size: var(--bs-text-chart-title, calc(13px * var(--bs-distance-scale, 1.25)));
  color: #9fc6ef;
  margin-bottom: 4px;
}
.chart-body {
  flex: 1;
  min-height: 160px;
}
.leader-list {
  list-style: none;
  margin: 0;
  padding: 4px 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.leader-item {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
}
.leader-person {
  color: var(--color-warning);
}
.bs-filters {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  padding: 8px 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  background: var(--el-fill-color-blank);
}
.filter-label,
.scope-subtitle {
  font-size: 13px;
  color: var(--color-text-secondary);
}
.scope-subtitle {
  font-size: 12px;
}
.detail-body {
  flex: 1;
  min-height: 160px;
  font-size: 13px;
}
.detail-empty {
  padding: 16px 0;
  text-align: center;
  font-size: 12px;
  color: var(--color-text-secondary);
}
.detail-section {
  margin-bottom: 8px;
}
.detail-section-title,
.profile-section-title {
  margin-bottom: 4px;
  font-size: 12px;
  color: var(--color-text-secondary);
}
.detail-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}
.detail-table th,
.detail-table td {
  padding: 2px 4px;
  text-align: left;
}
.detail-table th {
  font-weight: 500;
  color: var(--color-text-secondary);
}
.profile-title {
  margin-bottom: 6px;
  font-size: 13px;
  font-weight: 600;
}
.profile-section {
  margin-bottom: 8px;
}
.profile-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 4px 16px;
}
.profile-item {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  font-size: 12px;
}
.profile-item-label {
  color: var(--color-text-secondary);
}
.profile-tags {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
  margin-top: 4px;
}
.pairing-grid {
  display: flex;
  gap: 24px;
}
.pairing-item {
  display: flex;
  flex-direction: column;
  align-items: center;
}
.pairing-value {
  font-size: 18px;
  font-weight: 700;
  color: var(--el-color-primary);
}
.pairing-label {
  font-size: 12px;
  color: var(--color-text-secondary);
}
.bs-footer {
  text-align: center;
  font-size: 12px;
  color: #5a7ba8;
  padding: 6px 0 2px;
}
</style>
