<template>
  <div class="big-screen" :class="{ fullscreen: isFullscreen }">
    <header class="bs-header">
      <h1>帮扶管理信息系统 · 帮扶成效总览大屏</h1>
      <div class="bs-header-right">
        <span class="bs-clock">{{ clock }}</span>
        <el-button size="small" @click="toggleFullscreen">
          {{ isFullscreen ? '退出全屏' : '全屏展示' }}
        </el-button>
      </div>
    </header>

    <!-- KPI 总览 -->
    <section class="bs-kpi">
      <div v-for="k in kpis" :key="k.label" class="kpi-item">
        <div class="kpi-value">{{ k.value }}</div>
        <div class="kpi-label">{{ k.label }}</div>
      </div>
    </section>

    <!-- 图表区 -->
    <section class="bs-charts">
      <div class="chart-card wide">
        <div class="chart-title">经费执行趋势</div>
        <BaseChart :option="fundTrendOption" class="chart-body" />
      </div>
      <div class="chart-card">
        <div class="chart-title">帮扶成效排名</div>
        <BaseChart :option="rankOption" class="chart-body" />
      </div>
      <div class="chart-card">
        <div class="chart-title">项目状态分布</div>
        <BaseChart :option="projectStatusOption" class="chart-body" />
      </div>
      <div class="chart-card">
        <div class="chart-title">年度对比</div>
        <BaseChart :option="yearlyOption" class="chart-body" />
      </div>
    </section>

    <footer class="bs-footer">数据来源：本地数据库 · 自动轮播 5 秒 · 汇报展示模式</footer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { logger } from '@/utils/logger'
import BaseChart from '@/components/common/BaseChart.vue'
import { getDashboardStats, getYearlyTrends } from '@/api/dashboard'
import { getRankings } from '@/api/effectiveness'
import { getSummaryStatistics } from '@/api/analytics'

const isFullscreen = ref(false)
const clock = ref('')
const stats = ref<any>({})
const yearlyTrends = ref<any[]>([])
const rankings = ref<any[]>([])
const summary = ref<any>({})

let clockTimer: number | null = null
let rotateTimer: number | null = null

const kpis = computed(() => {
  const s = stats.value ?? {}
  return [
    { label: '帮扶村', value: s.total_villages ?? s.village_count ?? 0 },
    { label: '帮扶项目', value: s.total_projects ?? s.project_count ?? 0 },
    { label: '帮扶学校', value: s.total_schools ?? s.school_count ?? 0 },
    { label: '完成率', value: s.completion_rate != null ? `${s.completion_rate}%` : '—' },
    { label: '经费总额(万)', value: s.total_amount_mb ?? s.total_amount ?? 0 },
  ]
})

const fundTrendOption = computed(() => {
  const data = yearlyTrends.value ?? []
  return {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    grid: { left: 40, right: 16, top: 24, bottom: 28 },
    xAxis: { type: 'category', data: data.map((d: any) => d.year ?? '') },
    yAxis: { type: 'value' },
    series: [
      {
        name: '计划投入',
        type: 'line',
        smooth: true,
        data: data.map((d: any) => d.total_planned ?? d.planned ?? 0),
        itemStyle: { color: '#36cfc9' },
      },
      {
        name: '实际投入',
        type: 'line',
        smooth: true,
        data: data.map((d: any) => d.total_actual ?? d.actual ?? 0),
        itemStyle: { color: '#ffd666' },
      },
    ],
  }
})

const rankOption = computed(() => {
  const rows = rankings.value ?? []
  return {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    grid: { left: 90, right: 24, top: 16, bottom: 24 },
    xAxis: { type: 'value' },
    yAxis: {
      type: 'category',
      data: rows.map((r: any) => r.village_name ?? r.name ?? r.village_id ?? ''),
    },
    series: [
      {
        type: 'bar',
        data: rows.map((r: any) => r.score ?? r.total_score ?? 0),
        itemStyle: { color: '#40a9ff' },
      },
    ],
  }
})

const projectStatusOption = computed(() => {
  const s = summary.value ?? {}
  const statuses: Record<string, number> = s.by_status ?? s.project_status ?? {}
  const labels: Record<string, string> = {
    completed: '已完成',
    approved: '已审批',
    active: '进行中',
    pending: '待审批',
  }
  return {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'item' },
    legend: { bottom: 0, textStyle: { color: '#aaa' } },
    series: [
      {
        type: 'pie',
        radius: ['40%', '68%'],
        data: Object.entries(statuses).map(([k, v]) => ({
          name: labels[k] ?? k,
          value: Number(v) || 0,
        })),
      },
    ],
  }
})

const yearlyOption = computed(() => {
  const data = yearlyTrends.value ?? []
  const counts = data.map((d: any) => d.project_count ?? d.count ?? 0)
  return {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    grid: { left: 40, right: 16, top: 24, bottom: 28 },
    xAxis: { type: 'category', data: data.map((d: any) => d.year ?? '') },
    yAxis: { type: 'value' },
    series: [{ type: 'bar', data: counts, itemStyle: { color: '#b37feb' }, barWidth: '40%' }],
  }
})

async function loadAll() {
  let failedCount = 0
  try {
    const s = await getDashboardStats(true)
    stats.value = s ?? {}
  } catch {
    failedCount++
  }
  try {
    const y = await getYearlyTrends(5)
    yearlyTrends.value = y?.trends ?? y ?? []
  } catch {
    failedCount++
  }
  try {
    const r = await getRankings(new Date().getFullYear(), 10)
    rankings.value = r?.items ?? r ?? []
  } catch {
    failedCount++
  }
  try {
    const sm = await getSummaryStatistics()
    summary.value = sm ?? {}
  } catch {
    failedCount++
  }
  if (failedCount > 0) {
    logger.warn(`[BigScreen] ${failedCount} 个数据接口加载失败，已静默降级`)
    if (failedCount === 4) {
      ElMessage.warning('大屏数据加载失败，请检查服务连接')
    }
  }
}

function tickClock() {
  const d = new Date()
  clock.value = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}:${String(d.getSeconds()).padStart(2, '0')}`
}

function toggleFullscreen() {
  if (!document.fullscreenElement) {
    document.documentElement.requestFullscreen?.().catch(() => {})
    isFullscreen.value = true
  } else {
    document.exitFullscreen?.().catch(() => {})
    isFullscreen.value = false
  }
}

function onFullscreenChange() {
  isFullscreen.value = !!document.fullscreenElement
}

onMounted(() => {
  loadAll()
  tickClock()
  clockTimer = window.setInterval(tickClock, 1000)
  rotateTimer = window.setInterval(loadAll, 30000)
  document.addEventListener('fullscreenchange', onFullscreenChange)
})

onUnmounted(() => {
  if (clockTimer) clearInterval(clockTimer)
  if (rotateTimer) clearInterval(rotateTimer)
  document.removeEventListener('fullscreenchange', onFullscreenChange)
})
</script>

<style scoped>
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
  font-size: 22px;
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
  gap: 12px;
}
.bs-clock {
  font-family: Consolas, monospace;
  color: #ffd666;
  font-size: 14px;
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
  font-size: 26px;
  font-weight: 700;
  color: #40a9ff;
}
.kpi-label {
  font-size: 13px;
  color: #9fc6ef;
  margin-top: 4px;
}
.bs-charts {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  flex: 1;
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
  font-size: 13px;
  color: #9fc6ef;
  margin-bottom: 4px;
}
.chart-body {
  flex: 1;
  min-height: 160px;
}
.bs-footer {
  text-align: center;
  font-size: 12px;
  color: #5a7ba8;
  padding: 6px 0 2px;
}
</style>
