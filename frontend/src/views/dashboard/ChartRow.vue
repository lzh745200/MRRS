<template>
  <div class="chart-row">
    <div class="chart-card">
      <h3 class="chart-title">项目进度跟踪</h3>
      <el-skeleton v-if="loading" animated :rows="5" class="chart-skeleton" />
      <div v-else-if="error" class="chart-state chart-state--error">
        <span>数据加载失败，请稍后重试</span>
        <el-button size="small" type="primary" @click="loadAndRender">重试</el-button>
      </div>
      <el-empty v-else-if="!hasProjects" class="chart-empty" description="暂无项目数据" :image-size="72" />
      <div v-else ref="barRef" class="chart-body" />
    </div>
    <div class="chart-card">
      <h3 class="chart-title">经费使用概览</h3>
      <el-skeleton v-if="loading" animated :rows="5" class="chart-skeleton" />
      <div v-else-if="error" class="chart-state chart-state--error">
        <span>数据加载失败，请稍后重试</span>
        <el-button size="small" type="primary" @click="loadAndRender">重试</el-button>
      </div>
      <el-empty v-else-if="!hasFunds" class="chart-empty" description="暂无经费数据" :image-size="72" />
      <div v-else ref="pieRef" class="chart-body" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import echarts from '@/utils/echarts'
import { get, apiRequest } from '@/api/request'
import { logger } from '@/utils/logger'

const barRef = ref<HTMLElement>()
const pieRef = ref<HTMLElement>()
let barChart: echarts.ECharts | null = null
let pieChart: echarts.ECharts | null = null

const loading = ref(true)
const error = ref(false)
const retried = ref(false)
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
      apiRequest({ method: 'GET', url: '/projects', params: { summary: true, page_size: 5 } }),
      get('/dashboard/stats', { refresh: true }),
    ])
    projects.value = projRes?.data?.items || projRes?.data?.data || projRes?.items || []
    // get() 已解包响应，fundRes 直接是数据对象
    funds.value = {
      allocated: fundRes?.funds_allocated || fundRes?.total_funds || 0,
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
      setTimeout(() => {
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
      borderColor: '#e2e8f0',
      borderRadius: 8,
      textStyle: { color: '#1e293b', fontSize: 13 },
    },
    grid: { left: 8, right: 24, top: 8, bottom: 8 },
    xAxis: {
      type: 'value',
      max: 100,
      axisLabel: { color: '#94a3b8', fontSize: 11 },
      splitLine: { lineStyle: { color: '#f1f5f9', type: 'dashed' } },
    },
    yAxis: {
      type: 'category',
      data: names.reverse(),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#475569', fontSize: 12 },
    },
    series: [
      {
        type: 'bar',
        data: values.reverse(),
        barWidth: 16,
        itemStyle: {
          borderRadius: [0, 6, 6, 0],
          color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
            { offset: 0, color: '#2d6a4f' },
            { offset: 1, color: '#52b788' },
          ]),
        },
        label: {
          show: true,
          position: 'right',
          color: '#64748b',
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
    color: ['#2d6a4f', '#1e4d8c', '#f59e0b'],
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(255,255,255,.96)',
      borderColor: '#e2e8f0',
      borderRadius: 8,
      textStyle: { color: '#1e293b', fontSize: 13 },
      formatter: (p: any) => `${p.marker} ${p.name}: <b>${p.value}万</b> (${p.percent}%)`,
    },
    legend: { bottom: 0, textStyle: { color: '#64748b', fontSize: 11 } },
    series: [
      {
        type: 'pie',
        radius: ['55%', '78%'],
        center: ['50%', '46%'],
        itemStyle: { borderRadius: 4, borderColor: '#fff', borderWidth: 3 },
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
  barChart?.dispose()
  pieChart?.dispose()
})
</script>

<style scoped lang="scss">
.chart-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  @media (max-width: 900px) {
    grid-template-columns: 1fr;
  }
}
.chart-card {
  background: #fff;
  border-radius: 12px;
  padding: 20px 24px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}
.chart-title {
  font-size: 15px;
  font-weight: 600;
  color: #1e293b;
  margin: 0 0 12px 0;
  display: flex;
  align-items: center;
  gap: 8px;
  &::before {
    content: '';
    display: inline-block;
    width: 4px;
    height: 16px;
    border-radius: 2px;
    background: linear-gradient(180deg, #1e4d8c, var(--color-primary));
  }
}
.chart-body {
  width: 100%;
  height: 260px;
}
.chart-skeleton {
  height: 260px;
}
.chart-state {
  height: 260px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: $spacing-sm;
  color: $color-text-secondary;
  font-size: $font-size-md;
}
.chart-empty {
  height: 260px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;

  :deep(.el-empty__description p) {
    color: $color-text-secondary;
    font-size: $font-size-sm;
  }
}
</style>
