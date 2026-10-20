<template>
  <div class="chart-row">
    <div class="chart-card app-card">
      <h3 class="chart-title">项目进度跟踪</h3>
      <div v-if="loading" class="app-loading chart-loading" data-testid="chart-loading">
        <el-skeleton animated :rows="5" class="chart-skeleton" />
      </div>
      <div
        v-else-if="error"
        class="chart-state chart-state--error app-error"
        data-testid="chart-error"
      >
        <span>数据加载失败，请稍后重试</span>
        <el-button type="primary" @click="loadAndRender">重试</el-button>
      </div>
      <div v-else-if="!hasProjects" class="chart-empty app-empty" data-testid="chart-empty">
        <p>暂无项目数据</p>
      </div>
      <div v-else ref="barRef" class="chart-body" />
    </div>
    <div class="chart-card app-card">
      <h3 class="chart-title">经费使用概览</h3>
      <div v-if="loading" class="app-loading chart-loading" data-testid="chart-loading">
        <el-skeleton animated :rows="5" class="chart-skeleton" />
      </div>
      <div
        v-else-if="error"
        class="chart-state chart-state--error app-error"
        data-testid="chart-error"
      >
        <span>数据加载失败，请稍后重试</span>
        <el-button type="primary" @click="loadAndRender">重试</el-button>
      </div>
      <div v-else-if="!hasFunds" class="chart-empty app-empty" data-testid="chart-empty">
        <p>暂无经费数据</p>
      </div>
      <div v-else ref="pieRef" class="chart-body" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { unwrapList } from '@/utils/unwrapList'
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import echarts from '@/utils/echarts'
import { COLOR_PALETTE, themeColor } from '@/utils/echarts-theme'
import { get, apiRequest } from '@/api/request'
import { logger } from '@/utils/logger'

const barRef = ref<HTMLElement>()
const pieRef = ref<HTMLElement>()
let barChart: echarts.ECharts | null = null
let pieChart: echarts.ECharts | null = null

const loading = ref(true)
const error = ref(false)
const retried = ref(false)
// 失败自动重试的定时器句柄：组件卸载时必须清理，否则销毁后仍会触发一次 loadData
let retryTimer: ReturnType<typeof setTimeout> | undefined
const projects = ref<any[]>([])
const funds = ref({ allocated: 0, pending: 0, planned: 0 })

const hasProjects = computed(() => projects.value.length > 0)
const hasFunds = computed(
  () => funds.value.allocated + funds.value.pending + funds.value.planned > 0
)

async function loadData() {
  loading.value = true
  error.value = false
  try {
    const [projRes, fundRes] = await Promise.all([
      // W8-018：params 曾携带 /projects 后端列表接口不存在的 summary 幽灵参数
      // （FastAPI 会静默忽略），已移除。
      apiRequest({ method: 'GET', url: '/projects', params: { page_size: 5 } }),
      get('/dashboard/stats', { refresh: true }),
    ])
    const unwrappedProjects = unwrapList(projRes).items
    projects.value = unwrappedProjects.length
      ? unwrappedProjects
      : projRes?.data?.data || projRes?.items || []
    // get() 已解包响应，fundRes 直接是数据对象
    funds.value = {
      // 必须用 ?? 而非 ||：funds_allocated 合法为 0（全部未拨付）时，
      // || 会回退到 total_funds，把「已拨付」虚增为经费总额
      allocated: fundRes?.funds_allocated ?? fundRes?.total_funds ?? 0,
      pending: fundRes?.funds_pending || 0,
      planned: fundRes?.funds_planned || 0,
    }
  } catch (e) {
    // 接口失败时置零（空数据），不展示编造的假数字；页面内给出重试入口
    logger.error('图表数据加载失败', e)
    error.value = true
    projects.value = []
    funds.value = { allocated: 0, pending: 0, planned: 0 }
    // 后端可能仍在冷启动: 2 秒后自动重试一次,避免首次打开即报错
    if (!retried.value) {
      retried.value = true
      retryTimer = setTimeout(() => {
        if (error.value) loadData()
      }, 2000)
    }
  } finally {
    loading.value = false
  }
}

function buildBarOption(projectList: any[]): echarts.EChartsCoreOption {
  const names = projectList.map((p: any) => p.name || p.project_name || '')
  const values = projectList.map((p: any) => p.progress ?? p.completion_rate ?? 0)
  return {
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(255,255,255,.96)',
      borderColor: themeColor('--color-border-light', '#e2e8f0'),
      borderRadius: 8,
      textStyle: { color: themeColor('--color-text-primary', '#1e293b'), fontSize: 13 },
    },
    grid: { left: 8, right: 24, top: 8, bottom: 8 },
    xAxis: {
      type: 'value',
      max: 100,
      axisLabel: { color: themeColor('--color-border-dark', '#94a3b8'), fontSize: 11 },
      splitLine: {
        lineStyle: { color: themeColor('--color-border-lighter', '#f1f5f9'), type: 'dashed' },
      },
    },
    yAxis: {
      type: 'category',
      data: names.reverse(),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: themeColor('--color-text-regular', '#475569'), fontSize: 12 },
    },
    series: [
      {
        type: 'bar',
        data: values.reverse(),
        barWidth: 16,
        itemStyle: {
          borderRadius: [0, 6, 6, 0],
          color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
            { offset: 0, color: COLOR_PALETTE[1] },
            { offset: 1, color: COLOR_PALETTE[4] },
          ]),
        },
        label: {
          show: true,
          position: 'right',
          color: themeColor('--color-text-secondary', '#64748b'),
          fontSize: 11,
          formatter: '{c}%',
        },
      },
    ],
  }
}

function buildPieOption(fundsData: {
  allocated: number
  pending: number
  planned: number
}): echarts.EChartsCoreOption {
  return {
    color: [COLOR_PALETTE[1], COLOR_PALETTE[0], COLOR_PALETTE[5]],
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(255,255,255,.96)',
      borderColor: themeColor('--color-border-light', '#e2e8f0'),
      borderRadius: 8,
      textStyle: { color: themeColor('--color-text-primary', '#1e293b'), fontSize: 13 },
      formatter: (p: any) => `${p.marker} ${p.name}: <b>${p.value}万</b> (${p.percent}%)`,
    },
    legend: {
      bottom: 0,
      textStyle: { color: themeColor('--color-text-secondary', '#64748b'), fontSize: 11 },
    },
    series: [
      {
        type: 'pie',
        radius: ['55%', '78%'],
        center: ['50%', '46%'],
        itemStyle: {
          borderRadius: 4,
          borderColor: themeColor('--color-bg-card', '#fff'),
          borderWidth: 3,
        },
        label: { show: false },
        emphasis: {
          itemStyle: { shadowBlur: 16, shadowColor: 'rgba(0,0,0,.12)' },
        },
        data: [
          { value: fundsData.allocated, name: '已拨付' },
          { value: fundsData.pending, name: '待拨付' },
          { value: fundsData.planned, name: '计划中' },
        ],
      },
    ],
  }
}

function renderCharts() {
  barChart?.dispose()
  barChart = null
  pieChart?.dispose()
  pieChart = null
  if (error.value) return
  if (barRef.value && hasProjects.value) {
    barChart = echarts.init(barRef.value)
    barChart.setOption(buildBarOption(projects.value))
  }
  if (pieRef.value && hasFunds.value) {
    pieChart = echarts.init(pieRef.value)
    pieChart.setOption(buildPieOption(funds.value))
  }
}

async function loadAndRender() {
  await loadData()
  await nextTick()
  renderCharts()
}

function handleResize() {
  barChart?.resize()
  pieChart?.resize()
}

onMounted(async () => {
  await loadAndRender()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  clearTimeout(retryTimer) // 传入 undefined 亦为安全空操作，无需分支
  barChart?.dispose()
  pieChart?.dispose()
})
</script>

<style scoped lang="scss">
.chart-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--spacing-md, 16px);

  @media (max-width: 900px) {
    grid-template-columns: 1fr;
  }
}

.chart-card {
  background: var(--color-bg-card);
  border: 1px solid var(--color-card-border, var(--color-border-light));
  border-radius: var(--radius-card, 8px);
  padding: var(--spacing-lg, 20px);
  box-shadow: var(--shadow-card);
  min-width: 0;
}

.chart-title {
  font-size: var(--text-lg, 16px);
  font-weight: 600;
  color: var(--color-text-primary);
  margin: 0 0 var(--spacing-sm, 12px) 0;
  display: flex;
  align-items: center;
  gap: 8px;

  &::before {
    content: '';
    display: inline-block;
    width: 4px;
    height: 16px;
    border-radius: 2px;
    background: var(--color-primary);
  }
}

.chart-body {
  width: 100%;
  height: 260px;
}

.chart-loading,
.chart-skeleton {
  height: 260px;
}

.chart-state {
  height: 260px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-sm, 12px);
  color: var(--color-text-secondary);
  font-size: var(--text-md, 14px);
}

.chart-empty {
  height: 260px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--color-text-secondary);

  p {
    margin: 0;
    font-size: var(--text-sm, 13px);
  }
}
</style>
