<template>
  <div class="kpi-cards">
    <template v-if="loading">
      <div v-for="i in 5" :key="'skeleton-' + i" class="kpi-col">
        <el-skeleton animated :rows="2" class="stat-skeleton" />
      </div>
    </template>
    <div v-else-if="error" class="kpi-error">
      <span class="kpi-error__text">数据加载失败，请稍后重试</span>
      <el-button size="small" type="primary" @click="loadStats">重试</el-button>
    </div>
    <template v-else>
      <div v-for="(card, i) in cards" :key="i" class="kpi-col">
        <div
          class="stat-card"
          :class="card.theme"
          role="button"
          tabindex="0"
          @click="navigateTo(card.route)"
          @keydown.enter.prevent="navigateTo(card.route)"
          @keydown.space.prevent="navigateTo(card.route)"
        >
          <div class="stat-icon">
            <el-icon><component :is="card.icon" /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-label">{{ card.label }}</div>
            <div class="stat-value">
              <span class="data-number data-number--lg">{{ card.formatted }}</span>
              <span v-if="card.unit" class="data-unit">{{ card.unit }}</span>
            </div>
            <div class="stat-trend" :class="trendClass(card.trend)">
              <span class="trend-tag" :class="trendTagClass(card.trend)">
                <el-icon class="trend-tag__icon">
                  <component :is="trendIcon(card.trend)" />
                </el-icon>
                <template v-if="card.trend !== 0">{{ Math.abs(card.trend) }}%</template>
                <template v-else>持平</template>
              </span>
              <span class="trend-label">{{ card.trendLabel || '较上月' }}</span>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import {
  OfficeBuilding,
  Folder,
  School,
  Money,
  User,
  Top,
  Bottom,
  Minus,
} from '@element-plus/icons-vue'
import { get } from '@/api/request'
import { useRouterSafe } from '@/composables/useRouterSafe'
import { logger } from '@/utils/logger'

const { pushSafe } = useRouterSafe()

export interface DashboardStats {
  total_villages: number
  total_projects: number
  total_schools: number
  total_population: number
  total_funds: number
}
export interface KpiTrends {
  villages: number
  projects: number
  schools: number
  population: number
  funds: number
}

interface Props {
  trends?: KpiTrends
}
const props = withDefaults(defineProps<Props>(), {
  trends: () => ({
    villages: 0,
    projects: 0,
    schools: 0,
    population: 0,
    funds: 0,
  }),
})
const fetchedTrends = ref<KpiTrends>({
  villages: 0,
  projects: 0,
  schools: 0,
  population: 0,
  funds: 0,
})
const trends = computed<KpiTrends>(() => {
  const p = props.trends
  const hasExplicit = p && Object.values(p).some((v) => v !== 0)
  return hasExplicit ? p : fetchedTrends.value
})

const stats = ref<DashboardStats>({
  total_villages: 0,
  total_projects: 0,
  total_schools: 0,
  total_population: 0,
  total_funds: 0,
})
const loading = ref(true)
const error = ref(false)
const retryCount = ref(0)
let retryTimer: ReturnType<typeof setTimeout> | null = null

function fmt(v: number | undefined): string {
  return v != null ? v.toLocaleString() : '--'
}
function fmtFunds(v: number | undefined): string {
  return v != null ? (v / 10000).toFixed(0) : '--'
}
function fmtPop(v: number | undefined): string {
  if (v == null) return '--'
  return v >= 10000 ? (v / 10000).toFixed(1) + '万' : v.toLocaleString()
}
function trendClass(v: number) {
  return v > 0 ? 'stat-trend--up' : v < 0 ? 'stat-trend--down' : ''
}
function trendTagClass(v: number) {
  return v > 0 ? 'trend-tag--up' : v < 0 ? 'trend-tag--down' : 'trend-tag--flat'
}
function trendIcon(v: number) {
  return v > 0 ? Top : v < 0 ? Bottom : Minus
}

const icons: Record<string, any> = {
  OfficeBuilding,
  Folder,
  School,
  Money,
  User,
}

const cards = computed(() => [
  {
    theme: 'primary',
    icon: icons.OfficeBuilding,
    label: '帮扶村',
    formatted: fmt(stats.value.total_villages),
    unit: '个',
    trend: trends.value.villages,
    route: '/supported-villages',
  },
  {
    theme: 'success',
    icon: icons.Folder,
    label: '帮扶项目',
    formatted: fmt(stats.value.total_projects),
    unit: '个',
    trend: trends.value.projects,
    route: '/projects',
  },
  {
    theme: 'warning',
    icon: icons.School,
    label: '帮扶学校',
    formatted: fmt(stats.value.total_schools),
    unit: '所',
    trend: trends.value.schools,
    route: '/schools',
  },
  {
    theme: 'danger',
    icon: icons.Money,
    label: '帮扶经费',
    formatted: fmtFunds(stats.value.total_funds),
    unit: '万元',
    trend: trends.value.funds,
    route: '/funds',
  },
  {
    theme: 'info-card',
    icon: icons.User,
    label: '覆盖人口',
    formatted: fmtPop(stats.value.total_population),
    unit: undefined,
    trend: trends.value.population,
    trendLabel: '较去年',
    route: '/supported-villages',
  },
])

function navigateTo(route?: string) {
  if (!route) return
  pushSafe(route)
}

async function loadStats() {
  loading.value = true
  error.value = false
  try {
    const res = await get('/dashboard/stats', { refresh: true } as any)
    const d = (res || {}) as Record<string, number>
    if (d) {
      stats.value = {
        total_villages: d.total_villages ?? 0,
        total_projects: d.total_projects ?? 0,
        total_schools: d.total_schools ?? 0,
        total_population: d.total_population ?? 0,
        total_funds: d.total_funds ?? 0,
      }
      const t = (d as Record<string, any>).trends ?? {}
      fetchedTrends.value = {
        villages: t.villages ?? 0,
        projects: t.projects ?? 0,
        schools: t.schools ?? 0,
        population: t.population_yoy ?? 0,
        funds: t.funds ?? 0,
      }
      error.value = false
      retryCount.value = 0
    }
  } catch (e) {
    logger.error('KPI 统计数据加载失败', e)
    error.value = true
    // 失败（含路由导航取消请求的 CanceledError/后端冷启动）自动重试：
    // 最多 3 次、2s 间隔，成功即复位计数；卸载时清理定时器避免泄漏
    if (retryCount.value < 3) {
      retryCount.value += 1
      retryTimer = setTimeout(() => {
        if (error.value) loadStats()
      }, 2000)
    }
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await loadStats()
})

onBeforeUnmount(() => {
  if (retryTimer !== null) {
    clearTimeout(retryTimer)
    retryTimer = null
  }
})
</script>

<style scoped lang="scss">
.kpi-cards {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 16px;
  @media (max-width: 1200px) {
    grid-template-columns: repeat(3, 1fr);
  }
  @media (max-width: 768px) {
    grid-template-columns: repeat(2, 1fr);
  }
  @media (max-width: 480px) {
    grid-template-columns: 1fr;
  }
}

.stat-skeleton {
  background: $color-bg-card;
  padding: $spacing-md;
  border-radius: $radius-xl;
  box-shadow: $shadow-sm;
}

.kpi-error {
  grid-column: 1 / -1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: $spacing-md;
  padding: $spacing-xl;
  background: $color-bg-card;
  border-radius: $radius-xl;
  box-shadow: $shadow-sm;
  color: $color-text-secondary;
  font-size: $font-size-md;
}

.stat-card {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  background: #fff;
  padding: 18px 20px;
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
  transition:
    box-shadow 0.3s,
    transform 0.3s;
  cursor: pointer;
  position: relative;
  overflow: hidden;
  &:hover {
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.1);
    transform: translateY(-2px);
  }
  &::before {
    content: '';
    position: absolute;
    left: 0;
    top: 20%;
    height: 60%;
    width: 4px;
    border-radius: 0 4px 4px 0;
  }
  &.primary::before {
    background: $color-primary;
  }
  &.success::before {
    background: $color-success;
  }
  &.warning::before {
    background: $color-warning;
  }
  &.danger::before {
    background: $color-danger;
  }
  &.info-card::before {
    background: $color-info;
  }
}

.stat-icon {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  flex-shrink: 0;
  margin-right: 12px;
}
.primary .stat-icon {
  background: var(--color-primary-light-8);
  color: $color-primary;
}
.success .stat-icon {
  background: var(--color-success-lightest);
  color: $color-success;
}
.warning .stat-icon {
  background: var(--color-warning-lightest);
  color: $color-warning;
}
.danger .stat-icon {
  background: var(--color-danger-lightest);
  color: $color-danger;
}
.info-card .stat-icon {
  background: var(--color-info-lightest);
  color: $color-info;
}

.stat-content {
  flex: 1;
  min-width: 0;
}
.stat-label {
  font-size: 12px;
  color: $color-text-secondary;
  margin-bottom: 2px;
}
.stat-value {
  display: flex;
  align-items: baseline;
  gap: 2px;
}

.stat-trend {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 4px;
  font-size: 12px;
}
.stat-trend--up {
  color: $color-success;
}
.stat-trend--down {
  color: $color-danger;
}
.trend-label {
  color: $color-text-placeholder;
  font-size: 11px;
}
.trend-tag {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  font-weight: 600;
  font-family: 'DIN Alternate', 'Roboto Mono', monospace;
  font-size: 12px;
  padding: 1px 6px;
  border-radius: 10px;
}
.trend-tag--up {
  color: $color-success;
  background: var(--color-success-lightest);
}
.trend-tag--down {
  color: $color-danger;
  background: var(--color-danger-lightest);
}
.trend-tag--flat {
  color: $color-info;
  background: var(--color-info-lightest);
}
.trend-tag__icon {
  font-size: 12px;
}
</style>
